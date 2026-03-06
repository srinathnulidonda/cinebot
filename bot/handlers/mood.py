# bot/handlers/mood.py
import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from bot.middleware.subscription_check import ensure_user
from bot.middleware.analytics import track_command
from bot.utils.keyboards import mood_kb
from bot.utils.constants import E_BRAIN

logger = logging.getLogger(__name__)


async def mood_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    await track_command(update, context)
    await update.message.reply_text(
        f"😊 <b>How are you feeling right now?</b>\n\nPick your mood and I'll find the perfect movie:",
        reply_markup=mood_kb(),
        parse_mode="HTML",
    )


def get_handlers() -> list:
    return [CommandHandler("mood", mood_command)]