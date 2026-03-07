# bot/handlers/contact.py
import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from bot.middleware.subscription_check import ensure_user
from bot.middleware.analytics import track_command
from bot.models.engine import get_session
from bot.models.user import UserRepo
from bot.models.ticket import TicketRepo
from bot.config import get_settings
from bot.utils.constants import E_CHECK, E_CROWN, LINE, LINE_LIGHT
from bot.utils.validators import sanitize_html

logger = logging.getLogger(__name__)
_s = get_settings()


async def contact_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    await track_command(update, context)
    args = context.args or []
    if not args:
        await update.message.reply_text(
            f"📞 <b>CONTACT SUPPORT</b>\n"
            f"{LINE}\n\n"
            "Send your message:\n"
            "<code>/contact Your message here</code>\n\n"
            "💡 Examples:\n"
            "• <code>/contact I want to buy Pro</code>\n"
            "• <code>/contact Need help with my account</code>",
            parse_mode="HTML",
        )
        return

    message_text = " ".join(args)[:1000]
    telegram_id = update.effective_user.id
    user_db_id = context.user_data.get("db_user_id", 0)

    if not user_db_id:
        await update.message.reply_text("⚠️ Please /start first.", parse_mode="HTML")
        return

    async with get_session() as session:
        ticket = await TicketRepo.get_or_create_open(session, user_db_id, telegram_id)
        await TicketRepo.add_message(session, ticket.id, telegram_id, message_text, is_admin=False)
        ticket_id = ticket.id

    tg_user = update.effective_user
    username = f"@{tg_user.username}" if tg_user.username else "N/A"
    display = tg_user.first_name or username
    is_pro = context.user_data.get("is_pro", False)
    tier = f"{E_CROWN} PRO" if is_pro else "📋 FREE"

    try:
        from bot.main import _support_bot_app
        if _support_bot_app:
            from telegram import InlineKeyboardButton as Btn, InlineKeyboardMarkup as Mk
            kb = Mk([
                [
                    Btn("💬 Reply", callback_data=f"sr:{ticket_id}"),
                    Btn("📜 History", callback_data=f"sh:{ticket_id}"),
                ],
                [
                    Btn("✅ Close", callback_data=f"sc:{ticket_id}"),
                    Btn("👤 User", callback_data=f"su:{telegram_id}"),
                ],
                [Btn("🎁 Gift Pro", callback_data=f"sg:{telegram_id}")],
            ])
            admin_text = (
                f"📩 <b>TICKET #{ticket_id}</b>\n"
                f"{LINE}\n\n"
                f"👤 {sanitize_html(display)} ({username})\n"
                f"🆔 <code>{telegram_id}</code> · {tier}\n\n"
                f"─── ◆ Message ◆ ───\n"
                f"{sanitize_html(message_text)}"
            )
            for admin_id in _s.ADMIN_IDS:
                try:
                    await _support_bot_app.bot.send_message(
                        admin_id, admin_text, reply_markup=kb, parse_mode="HTML",
                    )
                except Exception as e:
                    logger.debug(f"Failed to notify admin {admin_id}: {e}")
    except Exception as e:
        logger.error(f"Support bot notification failed: {e}")

    await update.message.reply_text(
        f"{E_CHECK} <b>MESSAGE SENT!</b>\n"
        f"{LINE}\n\n"
        f"Ticket: <b>#{ticket_id}</b>\n"
        "Our team will reply shortly.\n\n"
        "You'll receive the response right here.\n"
        f"{LINE_LIGHT}\n"
        "Send another /contact message to add to this ticket.",
        parse_mode="HTML",
    )


def get_handlers() -> list:
    return [
        CommandHandler("contact", contact_command),
    ]