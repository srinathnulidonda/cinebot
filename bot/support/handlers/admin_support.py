# bot/support/handlers/admin_support.py
import logging
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton as Btn, InlineKeyboardMarkup as Mk
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from bot.config import get_settings
from bot.models.engine import get_session
from bot.models.user import UserRepo
from bot.models.ticket import TicketRepo
from bot.models.database import TicketStatus
from bot.services import key_service
from bot.utils.validators import sanitize_html
from bot.utils.constants import (
    E_CHECK, E_CROSS, E_PERSON, E_CROWN, E_KEY, E_CHART,
    LINE, LINE_LIGHT, BADGE_PRO, KEY_TYPES,
)

logger = logging.getLogger(__name__)
_s = get_settings()


def _is_admin(telegram_id: int) -> bool:
    return telegram_id in _s.ADMIN_IDS


def _ticket_kb(ticket_id: int, user_telegram_id: int) -> Mk:
    return Mk([
        [
            Btn("💬 Reply", callback_data=f"sr:{ticket_id}"),
            Btn("📜 History", callback_data=f"sh:{ticket_id}"),
        ],
        [
            Btn("✅ Close", callback_data=f"sc:{ticket_id}"),
            Btn("👤 User", callback_data=f"su:{user_telegram_id}"),
        ],
        [
            Btn("🎁 Gift Pro", callback_data=f"sg:{user_telegram_id}"),
        ],
    ])


def _closed_ticket_kb(ticket_id: int) -> Mk:
    return Mk([
        [
            Btn("📜 History", callback_data=f"sh:{ticket_id}"),
            Btn("🔄 Reopen", callback_data=f"sro:{ticket_id}"),
        ],
    ])


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text("🚫 Admin only.")
        return
    async with get_session() as session:
        open_tickets, _ = await TicketRepo.get_all_tickets(session, TicketStatus.OPEN, 1, 100)
        open_count = len(open_tickets)
        total_users = await UserRepo.get_user_count(session)
        pro_users = await UserRepo.get_pro_user_count(session)

    lines = [
        "🛡️ <b>SUPPORT DASHBOARD</b>",
        LINE,
        "",
        f"📩 Open tickets: <b>{open_count}</b>",
        f"👥 Users: <b>{total_users}</b> (👑 {pro_users} Pro)",
        "",
        LINE_LIGHT,
        "",
        "/open — Open tickets",
        "/all — All tickets",
        "/ticket <code>ID</code> — View ticket",
        "/find <code>telegram_id</code> — User tickets",
        "/close <code>ID</code> — Close ticket",
        "/reopen <code>ID</code> — Reopen ticket",
        "/gift <code>telegram_id type</code> — Gift Pro",
        "/stats — Support stats",
    ]
    await update.message.reply_text("\n".join(lines))


async def open_tickets_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        return
    async with get_session() as session:
        tickets, total = await TicketRepo.get_all_tickets(session, TicketStatus.OPEN, 1, 20)
    if not tickets:
        await update.message.reply_text("📭 No open tickets!")
        return
    lines = [f"📩 <b>OPEN TICKETS</b> ({total})", LINE, ""]
    for t in tickets:
        user_name = t.user.display_name if t.user else "?"
        username = f"@{t.user.username}" if t.user and t.user.username else ""
        tier = "👑" if t.user and t.user.is_pro else "📋"
        age = (datetime.now(timezone.utc) - t.created_at).days if t.created_at else 0
        age_str = f"{age}d ago" if age > 0 else "today"
        msg_count = len(t.messages) if hasattr(t, 'messages') else 0
        lines.append(
            f"🔴 <b>#{t.id}</b> · {tier} {sanitize_html(user_name)} {username}\n"
            f"    💬 {msg_count} msgs · {age_str}"
        )
    await update.message.reply_text("\n".join(lines))
    if tickets:
        for t in tickets[:5]:
            await update.message.reply_text(
                f"📩 <b>Ticket #{t.id}</b>\n{LINE}\n"
                f"👤 {sanitize_html(t.user.display_name if t.user else '?')} "
                f"(<code>{t.user_telegram_id}</code>)",
                reply_markup=_ticket_kb(t.id, t.user_telegram_id),
            )


async def all_tickets_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        return
    args = context.args or []
    page = int(args[0]) if args else 1
    async with get_session() as session:
        tickets, total = await TicketRepo.get_all_tickets(session, page=page, per_page=15)
    if not tickets:
        await update.message.reply_text("📭 No tickets.")
        return
    status_dots = {"OPEN": "🔴", "REPLIED": "🟡", "CLOSED": "🟢"}
    lines = [f"📋 <b>ALL TICKETS</b> ({total})", LINE, ""]
    for t in tickets:
        dot = status_dots.get(t.status.value, "⚪")
        user_name = t.user.display_name if t.user else "?"
        lines.append(f"  {dot} <b>#{t.id}</b> · {sanitize_html(user_name)} · {t.status.value}")
    lines.append(f"\n📄 Page {page}")
    await update.message.reply_text("\n".join(lines))


async def view_ticket_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        return
    args = context.args or []
    if not args:
        await update.message.reply_text("Usage: <code>/ticket ID</code>")
        return
    try:
        ticket_id = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid ID.")
        return
    async with get_session() as session:
        ticket = await TicketRepo.get_by_id(session, ticket_id)
        if not ticket:
            await update.message.reply_text("❌ Ticket not found.")
            return
        user = await UserRepo.get_by_id(session, ticket.user_id)
        messages = await TicketRepo.get_ticket_history(session, ticket_id, 20)

    status_dots = {"OPEN": "🔴", "REPLIED": "🟡", "CLOSED": "🟢"}
    dot = status_dots.get(ticket.status.value, "⚪")
    tier = BADGE_PRO if user and user.is_pro else "📋 FREE"
    username = f"@{user.username}" if user and user.username else "N/A"

    lines = [
        f"📩 <b>TICKET #{ticket.id}</b>",
        LINE,
        "",
        f"👤 {sanitize_html(user.display_name if user else '?')} ({username})",
        f"🆔 <code>{ticket.user_telegram_id}</code> · {tier}",
        f"Status: {dot} <b>{ticket.status.value}</b>",
        f"Created: {ticket.created_at.strftime('%Y-%m-%d %H:%M') if ticket.created_at else 'N/A'}",
        "",
        f"─── ◆ Messages ({len(messages)}) ◆ ───",
    ]
    for msg in messages[-10:]:
        sender = "🛡️ Admin" if msg.is_admin else f"👤 User"
        time_str = msg.created_at.strftime("%m/%d %H:%M") if msg.created_at else ""
        text = sanitize_html(msg.message_text[:200])
        lines.append(f"\n{sender} · {time_str}")
        lines.append(f"  {text}")

    kb = _ticket_kb(ticket.id, ticket.user_telegram_id) if ticket.status != TicketStatus.CLOSED else _closed_ticket_kb(ticket.id)
    await update.message.reply_text("\n".join(lines), reply_markup=kb)


async def find_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        return
    args = context.args or []
    if not args:
        await update.message.reply_text("Usage: <code>/find telegram_id</code>")
        return
    try:
        telegram_id = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid ID.")
        return
    async with get_session() as session:
        user = await UserRepo.get_by_telegram_id(session, telegram_id)
        if not user:
            await update.message.reply_text("❌ User not found.")
            return
        from bot.utils.formatters import format_user_info
        await update.message.reply_text(format_user_info(user))
        ticket = await TicketRepo.get_by_user_telegram_id(session, telegram_id)
    if ticket:
        await update.message.reply_text(
            f"📩 Active ticket: <b>#{ticket.id}</b> ({ticket.status.value})",
            reply_markup=_ticket_kb(ticket.id, telegram_id),
        )
    else:
        await update.message.reply_text("📭 No active tickets for this user.")


async def close_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        return
    args = context.args or []
    if not args:
        await update.message.reply_text("Usage: <code>/close ID</code>")
        return
    try:
        ticket_id = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid ID.")
        return
    await _close_ticket(update, context, ticket_id)


async def reopen_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        return
    args = context.args or []
    if not args:
        await update.message.reply_text("Usage: <code>/reopen ID</code>")
        return
    try:
        ticket_id = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid ID.")
        return
    async with get_session() as session:
        ticket = await TicketRepo.reopen_ticket(session, ticket_id)
    if ticket:
        await update.message.reply_text(
            f"🔄 Ticket <b>#{ticket_id}</b> reopened.",
            reply_markup=_ticket_kb(ticket_id, ticket.user_telegram_id),
        )
    else:
        await update.message.reply_text("❌ Ticket not found.")


async def gift_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        return
    args = context.args or []
    if len(args) < 2:
        types = " · ".join(KEY_TYPES.keys())
        await update.message.reply_text(
            f"🎁 <b>GIFT PRO</b>\n{LINE}\n\n"
            f"Usage: <code>/gift telegram_id type</code>\n"
            f"Types: {types}\n\n"
            f"💡 <code>/gift 123456789 1M</code>"
        )
        return
    try:
        target_id = int(args[0])
        key_type = args[1].upper()
        result = await key_service.gift_key(update.effective_user.id, target_id, key_type)
        await update.message.reply_text(
            f"🎁 <b>PRO GIFTED!</b>\n{LINE}\n\n"
            f"User: {result['user']} ({result['telegram_id']})\n"
            f"Duration: <b>{result['duration']}</b>\n"
            f"Key: <code>{result['key']}</code>"
        )
        try:
            from bot.main import _main_bot_app
            if _main_bot_app:
                await _main_bot_app.bot.send_message(
                    target_id,
                    f"🎁 <b>You've been upgraded to Pro!</b>\n{LINE}\n\n"
                    f"Duration: <b>{result['duration']}</b>\n"
                    "Enjoy unlimited access! ✨",
                )
        except Exception:
            pass
    except ValueError as e:
        await update.message.reply_text(f"❌ {e}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        return
    async with get_session() as session:
        open_count = await TicketRepo.get_open_count(session)
        all_tickets, total = await TicketRepo.get_all_tickets(session, page=1, per_page=1)
        total_users = await UserRepo.get_user_count(session)
        pro_users = await UserRepo.get_pro_user_count(session)
    await update.message.reply_text(
        f"{E_CHART} <b>SUPPORT STATS</b>\n{LINE}\n\n"
        f"📩 Open: <b>{open_count}</b>\n"
        f"📋 Total tickets: <b>{total}</b>\n"
        f"👥 Users: <b>{total_users}</b>\n"
        f"👑 Pro: <b>{pro_users}</b>"
    )


async def reply_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not _is_admin(query.from_user.id):
        await query.answer("Admin only.", show_alert=True)
        return
    ticket_id = int(query.data.split(":")[1])
    await query.answer()
    context.user_data["replying_ticket"] = ticket_id
    async with get_session() as session:
        ticket = await TicketRepo.get_by_id(session, ticket_id)
        last_msgs = await TicketRepo.get_ticket_history(session, ticket_id, 3)
    lines = [f"💬 <b>REPLYING TO #{ticket_id}</b>", LINE, ""]
    if last_msgs:
        lines.append("─── Last messages ───")
        for msg in last_msgs:
            sender = "🛡️" if msg.is_admin else "👤"
            lines.append(f"{sender} {sanitize_html(msg.message_text[:100])}")
    lines.append(f"\n<b>Type your reply:</b>")
    await query.message.reply_text("\n".join(lines))


async def history_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not _is_admin(query.from_user.id):
        await query.answer("Admin only.", show_alert=True)
        return
    ticket_id = int(query.data.split(":")[1])
    await query.answer()
    async with get_session() as session:
        messages = await TicketRepo.get_ticket_history(session, ticket_id, 30)
    if not messages:
        await query.message.reply_text(f"📜 Ticket #{ticket_id}: No messages.")
        return
    lines = [f"📜 <b>TICKET #{ticket_id} HISTORY</b> ({len(messages)} msgs)", LINE, ""]
    for msg in messages:
        sender = "🛡️ Admin" if msg.is_admin else "👤 User"
        time_str = msg.created_at.strftime("%m/%d %H:%M") if msg.created_at else ""
        text = sanitize_html(msg.message_text[:300])
        lines.append(f"{sender} · {time_str}")
        lines.append(f"  {text}")
        lines.append("")
    full_text = "\n".join(lines)
    if len(full_text) > 4096:
        full_text = full_text[:4090] + "\n..."
    await query.message.reply_text(full_text)


async def close_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not _is_admin(query.from_user.id):
        await query.answer("Admin only.", show_alert=True)
        return
    ticket_id = int(query.data.split(":")[1])
    await _close_ticket(update, context, ticket_id, via_callback=True)


async def _close_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE, ticket_id: int, via_callback: bool = False) -> None:
    async with get_session() as session:
        ticket = await TicketRepo.close_ticket(session, ticket_id)
    if not ticket:
        msg = "❌ Ticket not found."
        if via_callback:
            await update.callback_query.answer(msg, show_alert=True)
        else:
            await update.message.reply_text(msg)
        return
    if via_callback:
        await update.callback_query.answer("Ticket closed!")
        await update.callback_query.edit_message_text(
            f"✅ Ticket <b>#{ticket_id}</b> closed.",
            reply_markup=_closed_ticket_kb(ticket_id),
        )
    else:
        await update.message.reply_text(
            f"✅ Ticket <b>#{ticket_id}</b> closed.",
            reply_markup=_closed_ticket_kb(ticket_id),
        )
    try:
        from bot.main import _main_bot_app
        if _main_bot_app:
            await _main_bot_app.bot.send_message(
                ticket.user_telegram_id,
                f"{E_CHECK} <b>Ticket #{ticket_id} Resolved</b>\n\n"
                "Your support ticket has been closed.\n"
                "Use /contact to reach us again!",
            )
    except Exception:
        pass


async def reopen_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not _is_admin(query.from_user.id):
        await query.answer("Admin only.", show_alert=True)
        return
    ticket_id = int(query.data.split(":")[1])
    await query.answer()
    async with get_session() as session:
        ticket = await TicketRepo.reopen_ticket(session, ticket_id)
    if ticket:
        await query.edit_message_text(
            f"🔄 Ticket <b>#{ticket_id}</b> reopened.",
            reply_markup=_ticket_kb(ticket_id, ticket.user_telegram_id),
        )
    else:
        await query.message.reply_text("❌ Ticket not found.")


async def user_info_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not _is_admin(query.from_user.id):
        await query.answer("Admin only.", show_alert=True)
        return
    telegram_id = int(query.data.split(":")[1])
    await query.answer()
    async with get_session() as session:
        user = await UserRepo.get_by_telegram_id(session, telegram_id)
    if not user:
        await query.message.reply_text("❌ User not found.")
        return
    from bot.utils.formatters import format_user_info
    await query.message.reply_text(format_user_info(user))


async def gift_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not _is_admin(query.from_user.id):
        await query.answer("Admin only.", show_alert=True)
        return
    telegram_id = query.data.split(":")[1]
    await query.answer()
    buttons = [
        [Btn(f"💎 {v['label']} ({v['days']}d)", callback_data=f"sdg:{telegram_id}:{k}")]
        for k, v in KEY_TYPES.items()
    ]
    buttons.append([Btn("❌ Cancel", callback_data="scancel")])
    await query.message.reply_text(
        f"🎁 <b>GIFT PRO</b> → <code>{telegram_id}</code>\n{LINE}\n\nSelect duration:",
        reply_markup=Mk(buttons),
    )


async def do_gift_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not _is_admin(query.from_user.id):
        await query.answer("Admin only.", show_alert=True)
        return
    parts = query.data.split(":")
    telegram_id = int(parts[1])
    key_type = parts[2]
    await query.answer()
    try:
        result = await key_service.gift_key(query.from_user.id, telegram_id, key_type)
        await query.edit_message_text(
            f"🎁 <b>PRO GIFTED!</b>\n{LINE}\n\n"
            f"User: {result['user']} ({result['telegram_id']})\n"
            f"Duration: <b>{result['duration']}</b>\n"
            f"Key: <code>{result['key']}</code>"
        )
        try:
            from bot.main import _main_bot_app
            if _main_bot_app:
                await _main_bot_app.bot.send_message(
                    telegram_id,
                    f"🎁 <b>You've been upgraded to Pro!</b>\n{LINE}\n\n"
                    f"Duration: <b>{result['duration']}</b>\n"
                    "Enjoy unlimited access! ✨\n\nUse /pro to check.",
                )
        except Exception:
            pass
    except Exception as e:
        await query.edit_message_text(f"❌ Error: {e}")


async def cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer("Cancelled.")
    await update.callback_query.edit_message_text("❌ Cancelled.")


async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update.effective_user.id):
        return
    ticket_id = context.user_data.get("replying_ticket")
    if not ticket_id:
        return
    context.user_data.pop("replying_ticket", None)
    reply_text = update.message.text[:2000]

    async with get_session() as session:
        ticket = await TicketRepo.get_by_id(session, ticket_id)
        if not ticket:
            await update.message.reply_text("❌ Ticket not found or expired.")
            return
        await TicketRepo.add_message(
            session, ticket_id, update.effective_user.id, reply_text, is_admin=True,
        )
        user_telegram_id = ticket.user_telegram_id

    try:
        from bot.main import _main_bot_app
        admin_name = update.effective_user.first_name or "Support"
        if _main_bot_app:
            await _main_bot_app.bot.send_message(
                user_telegram_id,
                f"💬 <b>Support Reply</b>\n{LINE}\n\n"
                f"👤 {sanitize_html(admin_name)}\n\n"
                f"{sanitize_html(reply_text)}\n\n"
                f"{LINE_LIGHT}\n"
                "<i>Reply with /contact to continue.</i>",
            )
        await update.message.reply_text(
            f"{E_CHECK} Reply sent to ticket <b>#{ticket_id}</b>",
            reply_markup=_ticket_kb(ticket_id, user_telegram_id),
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to send: {e}")


def get_handlers() -> list:
    return [
        CommandHandler("start", start_command),
        CommandHandler("open", open_tickets_command),
        CommandHandler("all", all_tickets_command),
        CommandHandler("ticket", view_ticket_command),
        CommandHandler("find", find_user_command),
        CommandHandler("close", close_command),
        CommandHandler("reopen", reopen_command),
        CommandHandler("gift", gift_command),
        CommandHandler("stats", stats_command),
        CallbackQueryHandler(reply_callback, pattern=r"^sr:\d+$"),
        CallbackQueryHandler(history_callback, pattern=r"^sh:\d+$"),
        CallbackQueryHandler(close_callback, pattern=r"^sc:\d+$"),
        CallbackQueryHandler(reopen_callback, pattern=r"^sro:\d+$"),
        CallbackQueryHandler(user_info_callback, pattern=r"^su:\d+$"),
        CallbackQueryHandler(gift_callback, pattern=r"^sg:\d+$"),
        CallbackQueryHandler(do_gift_callback, pattern=r"^sdg:\d+:\w+$"),
        CallbackQueryHandler(cancel_callback, pattern=r"^scancel$"),
        MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler),
    ]