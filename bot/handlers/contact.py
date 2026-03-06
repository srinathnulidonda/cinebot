# bot/handlers/contact.py
import logging
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from bot.middleware.subscription_check import ensure_user
from bot.middleware.analytics import track_command
from bot.middleware.admin_check import admin_only
from bot.models.engine import redis_client, get_session
from bot.models.user import UserRepo
from bot.config import get_settings
from bot.utils.constants import E_SEND, E_CHECK, E_PERSON, E_CROWN, E_INFO
from bot.utils.validators import sanitize_html

logger = logging.getLogger(__name__)
_s = get_settings()


async def contact_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    await track_command(update, context)
    args = context.args or []
    if not args:
        await update.message.reply_text(
            f"💬 <b>Contact Admin</b>\n\n"
            f"Send your message to our team:\n"
            f"<code>/contact Your message here</code>\n\n"
            f"Examples:\n"
            f"• <code>/contact I want to buy Pro subscription</code>\n"
            f"• <code>/contact I have a question about features</code>\n"
            f"• <code>/contact Need help with my account</code>",
            parse_mode="HTML",
        )
        return

    message_text = " ".join(args)
    if len(message_text) > 1000:
        message_text = message_text[:1000]

    telegram_id = update.effective_user.id
    cooldown_key = f"contact_cd:{telegram_id}"
    last_sent = await redis_client.get(cooldown_key)
    if last_sent:
        await update.message.reply_text(
            "⏳ Please wait a few minutes before sending another message.",
            parse_mode="HTML",
        )
        return

    user = update.effective_user
    username = f"@{user.username}" if user.username else "N/A"
    display = user.first_name or username
    is_pro = context.user_data.get("is_pro", False)
    tier = "👑 PRO" if is_pro else "📋 FREE"

    ticket_id = await redis_client.incr("ticket_counter")
    ticket_key = f"ticket:{ticket_id}"
    await redis_client.hset(ticket_key, mapping={
        "user_id": str(telegram_id),
        "username": username,
        "display": display,
        "tier": tier,
        "message": message_text,
        "status": "open",
        "created": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    })
    await redis_client.expire(ticket_key, 604800)

    reply_kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💬 Reply", callback_data=f"ticket_reply:{ticket_id}"),
            InlineKeyboardButton("✅ Close", callback_data=f"ticket_close:{ticket_id}"),
        ],
        [
            InlineKeyboardButton(f"👤 User Info", callback_data=f"ticket_user:{telegram_id}"),
            InlineKeyboardButton(f"🎁 Gift Pro", callback_data=f"ticket_gift:{telegram_id}"),
        ],
    ])

    admin_text = (
        f"📩 <b>New Support Ticket #{ticket_id}</b>\n\n"
        f"{E_PERSON} <b>From:</b> {sanitize_html(display)} ({username})\n"
        f"🆔 <b>ID:</b> <code>{telegram_id}</code>\n"
        f"📋 <b>Plan:</b> {tier}\n\n"
        f"💬 <b>Message:</b>\n{sanitize_html(message_text)}"
    )

    sent_to = 0
    for admin_id in _s.ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id, admin_text, reply_markup=reply_kb, parse_mode="HTML",
            )
            sent_to += 1
        except Exception as e:
            logger.debug(f"Failed to notify admin {admin_id}: {e}")

    if sent_to == 0:
        async with get_session() as session:
            from sqlalchemy import select
            from bot.models.database import User
            result = await session.execute(
                select(User.telegram_id).where(User.is_admin == True)
            )
            db_admins = list(result.scalars().all())
        for admin_id in db_admins:
            try:
                await context.bot.send_message(
                    admin_id, admin_text, reply_markup=reply_kb, parse_mode="HTML",
                )
                sent_to += 1
            except Exception:
                pass

    await redis_client.setex(cooldown_key, 120, "1")

    await update.message.reply_text(
        f"{E_CHECK} <b>Message Sent!</b>\n\n"
        f"Ticket: <b>#{ticket_id}</b>\n"
        f"Our team will reply shortly.\n\n"
        f"You'll receive the response right here in this chat.",
        parse_mode="HTML",
    )


async def ticket_reply_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    admin_id = query.from_user.id
    if admin_id not in _s.ADMIN_IDS:
        async with get_session() as session:
            admin_user = await UserRepo.get_by_telegram_id(session, admin_id)
        if not admin_user or not admin_user.is_admin:
            await query.answer("Admin only.", show_alert=True)
            return

    ticket_id = query.data.split(":")[1]
    await query.answer()
    context.user_data["replying_ticket"] = ticket_id
    ticket_data = await redis_client.hgetall(f"ticket:{ticket_id}")
    user_display = ticket_data.get("display", "Unknown")
    original_msg = ticket_data.get("message", "N/A")

    await query.message.reply_text(
        f"💬 <b>Reply to Ticket #{ticket_id}</b>\n"
        f"👤 User: {sanitize_html(user_display)}\n"
        f"📝 Original: {sanitize_html(original_msg[:200])}\n\n"
        f"<b>Type your reply now:</b>",
        parse_mode="HTML",
    )


async def ticket_close_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    admin_id = query.from_user.id
    if admin_id not in _s.ADMIN_IDS:
        async with get_session() as session:
            admin_user = await UserRepo.get_by_telegram_id(session, admin_id)
        if not admin_user or not admin_user.is_admin:
            await query.answer("Admin only.", show_alert=True)
            return

    ticket_id = query.data.split(":")[1]
    ticket_data = await redis_client.hgetall(f"ticket:{ticket_id}")
    if not ticket_data:
        await query.answer("Ticket not found.", show_alert=True)
        return

    await redis_client.hset(f"ticket:{ticket_id}", "status", "closed")
    await query.answer("Ticket closed!")
    await query.edit_message_text(
        query.message.text + f"\n\n✅ <b>Closed</b> by admin",
        parse_mode="HTML",
    )

    user_id = ticket_data.get("user_id")
    if user_id:
        try:
            await context.bot.send_message(
                int(user_id),
                f"{E_CHECK} <b>Ticket #{ticket_id} Closed</b>\n\n"
                f"Your support ticket has been resolved.\n"
                f"Use /contact to reach us again anytime!",
                parse_mode="HTML",
            )
        except Exception:
            pass


async def ticket_user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    admin_id = query.from_user.id
    if admin_id not in _s.ADMIN_IDS:
        async with get_session() as session:
            admin_user = await UserRepo.get_by_telegram_id(session, admin_id)
        if not admin_user or not admin_user.is_admin:
            await query.answer("Admin only.", show_alert=True)
            return

    telegram_id = int(query.data.split(":")[1])
    await query.answer()
    async with get_session() as session:
        user = await UserRepo.get_by_telegram_id(session, telegram_id)
    if not user:
        await query.message.reply_text("❌ User not found.", parse_mode="HTML")
        return
    from bot.utils.formatters import format_user_info
    await query.message.reply_text(format_user_info(user), parse_mode="HTML")


async def ticket_gift_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    admin_id = query.from_user.id
    if admin_id not in _s.ADMIN_IDS:
        async with get_session() as session:
            admin_user = await UserRepo.get_by_telegram_id(session, admin_id)
        if not admin_user or not admin_user.is_admin:
            await query.answer("Admin only.", show_alert=True)
            return

    telegram_id = query.data.split(":")[1]
    await query.answer()
    from bot.utils.constants import KEY_TYPES
    buttons = [
        [InlineKeyboardButton(
            f"{v['label']} ({v['days']}d)",
            callback_data=f"ticket_dogift:{telegram_id}:{k}",
        )]
        for k, v in KEY_TYPES.items()
    ]
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
    await query.message.reply_text(
        f"🎁 <b>Gift Pro to user {telegram_id}</b>\n\nSelect duration:",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="HTML",
    )


async def ticket_dogift_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    admin_id = query.from_user.id
    if admin_id not in _s.ADMIN_IDS:
        async with get_session() as session:
            admin_user = await UserRepo.get_by_telegram_id(session, admin_id)
        if not admin_user or not admin_user.is_admin:
            await query.answer("Admin only.", show_alert=True)
            return

    parts = query.data.split(":")
    telegram_id = int(parts[1])
    key_type = parts[2]
    await query.answer()

    try:
        from bot.services import key_service
        result = await key_service.gift_key(admin_id, telegram_id, key_type)
        await query.edit_message_text(
            f"🎁 <b>Pro Gifted!</b>\n\n"
            f"User: {result['user']} ({result['telegram_id']})\n"
            f"Duration: {result['duration']}\n"
            f"Key: <code>{result['key']}</code>",
            parse_mode="HTML",
        )
        try:
            await context.bot.send_message(
                telegram_id,
                f"🎁 <b>You've been upgraded to Pro!</b>\n\n"
                f"Duration: {result['duration']}\n"
                f"Enjoy unlimited access to all features! ✨\n\n"
                f"Use /pro to check your status.",
                parse_mode="HTML",
            )
        except Exception:
            pass
    except Exception as e:
        await query.edit_message_text(f"❌ Error: {e}", parse_mode="HTML")


async def admin_reply_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ticket_id = context.user_data.get("replying_ticket")
    if not ticket_id:
        return
    admin_id = update.effective_user.id
    if admin_id not in _s.ADMIN_IDS:
        async with get_session() as session:
            admin_user = await UserRepo.get_by_telegram_id(session, admin_id)
        if not admin_user or not admin_user.is_admin:
            return

    context.user_data.pop("replying_ticket", None)
    reply_text = update.message.text[:2000]
    ticket_data = await redis_client.hgetall(f"ticket:{ticket_id}")
    if not ticket_data:
        await update.message.reply_text("❌ Ticket expired or not found.", parse_mode="HTML")
        return

    user_id = ticket_data.get("user_id")
    if not user_id:
        await update.message.reply_text("❌ User not found.", parse_mode="HTML")
        return

    admin_user = update.effective_user
    admin_name = admin_user.first_name or "Admin"

    try:
        await context.bot.send_message(
            int(user_id),
            f"💬 <b>Reply to Ticket #{ticket_id}</b>\n\n"
            f"👤 <b>From:</b> {sanitize_html(admin_name)} (Admin)\n\n"
            f"{sanitize_html(reply_text)}\n\n"
            f"<i>Reply with /contact to continue the conversation.</i>",
            parse_mode="HTML",
        )
        await redis_client.hset(f"ticket:{ticket_id}", "status", "replied")
        await update.message.reply_text(
            f"{E_CHECK} <b>Reply sent to user!</b>\n\nTicket #{ticket_id}",
            parse_mode="HTML",
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to send: {e}", parse_mode="HTML")


@admin_only
async def tickets_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    await track_command(update, context)
    keys = []
    cursor = 0
    while True:
        cursor, batch = await redis_client.scan(cursor, match="ticket:*", count=100)
        keys.extend(batch)
        if cursor == 0:
            break

    if not keys:
        await update.message.reply_text("📭 No support tickets.", parse_mode="HTML")
        return

    tickets = []
    for key in sorted(keys, reverse=True)[:20]:
        data = await redis_client.hgetall(key)
        if data:
            tid = key.split(":")[1]
            tickets.append((tid, data))

    open_tickets = [(t, d) for t, d in tickets if d.get("status") == "open"]
    replied_tickets = [(t, d) for t, d in tickets if d.get("status") == "replied"]
    closed_tickets = [(t, d) for t, d in tickets if d.get("status") == "closed"]

    lines = [f"📩 <b>Support Tickets</b>\n"]
    if open_tickets:
        lines.append(f"<b>🔴 Open ({len(open_tickets)}):</b>")
        for tid, data in open_tickets[:10]:
            display = data.get("display", "?")
            msg = data.get("message", "")[:50]
            created = data.get("created", "")
            lines.append(f"  #{tid} — {sanitize_html(display)}: {sanitize_html(msg)}...")
    if replied_tickets:
        lines.append(f"\n<b>🟡 Replied ({len(replied_tickets)}):</b>")
        for tid, data in replied_tickets[:5]:
            display = data.get("display", "?")
            lines.append(f"  #{tid} — {sanitize_html(display)}")
    if closed_tickets:
        lines.append(f"\n<b>🟢 Closed ({len(closed_tickets)}):</b>")
        for tid, data in closed_tickets[:5]:
            display = data.get("display", "?")
            lines.append(f"  #{tid} — {sanitize_html(display)}")

    lines.append(f"\n📊 Total: {len(tickets)}")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


def get_handlers() -> list:
    return [
        CommandHandler("contact", contact_command),
        CommandHandler("tickets", tickets_command),
        CallbackQueryHandler(ticket_reply_callback, pattern=r"^ticket_reply:\d+$"),
        CallbackQueryHandler(ticket_close_callback, pattern=r"^ticket_close:\d+$"),
        CallbackQueryHandler(ticket_user_callback, pattern=r"^ticket_user:\d+$"),
        CallbackQueryHandler(ticket_gift_callback, pattern=r"^ticket_gift:\d+$"),
        CallbackQueryHandler(ticket_dogift_callback, pattern=r"^ticket_dogift:\d+:\w+$"),
    ]