# bot/support/bot.py
import logging
from telegram import Update, BotCommand
from telegram.ext import (
    Application, ApplicationBuilder, CommandHandler,
    CallbackQueryHandler, MessageHandler, filters, Defaults,
)
from bot.config import get_settings
from bot.support.handlers import admin_support

logger = logging.getLogger(__name__)
_s = get_settings()

SUPPORT_COMMANDS = [
    BotCommand("start", "Dashboard"),
    BotCommand("open", "View open tickets"),
    BotCommand("all", "View all tickets"),
    BotCommand("ticket", "View ticket by ID"),
    BotCommand("find", "Find user tickets"),
    BotCommand("close", "Close a ticket"),
    BotCommand("reopen", "Reopen a ticket"),
    BotCommand("gift", "Gift Pro to user"),
    BotCommand("stats", "Support stats"),
]


async def support_error_handler(update: object, context) -> None:
    logger.error(f"Support bot error: {context.error}", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text("⚠️ Something went wrong.")
        except Exception:
            pass


async def support_post_init(application: Application) -> None:
    await application.bot.set_my_commands(SUPPORT_COMMANDS)
    logger.info("Support bot initialized")


def build_support_bot() -> Application:
    if not _s.SUPPORT_BOT_TOKEN:
        raise ValueError("SUPPORT_BOT_TOKEN not set")

    defaults = Defaults(parse_mode="HTML")
    app = (
        ApplicationBuilder()
        .token(_s.SUPPORT_BOT_TOKEN)
        .defaults(defaults)
        .post_init(support_post_init)
        .concurrent_updates(True)
        .connect_timeout(30.0)
        .read_timeout(30.0)
        .write_timeout(30.0)
        .build()
    )

    for handler in admin_support.get_handlers():
        app.add_handler(handler)

    app.add_error_handler(support_error_handler)
    return app