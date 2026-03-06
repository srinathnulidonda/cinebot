# bot/handlers/explain.py
import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from bot.middleware.subscription_check import ensure_user
from bot.middleware.rate_limiter import check_rate_limit, increment_usage
from bot.middleware.analytics import track_command
from bot.models.engine import get_session
from bot.models.user import UserRepo
from bot.services import tmdb_service, openai_service
from bot.utils.keyboards import explain_type_kb, search_results_kb
from bot.utils.constants import E_ROBOT
from bot import CineBotError

logger = logging.getLogger(__name__)


async def explain_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    await track_command(update, context)
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text(
            f"{E_ROBOT} <b>AI Movie Explainer</b>\n\n"
            f"Usage: <code>/explain Movie Name</code>\n"
            f"Example: <code>/explain Inception</code>",
            parse_mode="HTML",
        )
        return

    telegram_id = update.effective_user.id
    async with get_session() as session:
        user = await UserRepo.get_by_telegram_id(session, telegram_id)
    is_pro = user.is_pro if user else False
    await check_rate_limit(telegram_id, "explain", is_pro)

    try:
        data = await tmdb_service.search_movies(query)
        results = data.get("results", [])
        if not results:
            await update.message.reply_text("🔍 No movies found.", parse_mode="HTML")
            return
        if len(results) == 1 or results[0].get("vote_count", 0) > 100:
            movie = results[0]
            await update.message.reply_text(
                f"{E_ROBOT} <b>What would you like explained about '{movie['title']}'?</b>",
                reply_markup=explain_type_kb(movie["id"]),
                parse_mode="HTML",
            )
        else:
            await update.message.reply_text(
                f"{E_ROBOT} Select a movie to explain:",
                reply_markup=search_results_kb(results[:6]),
                parse_mode="HTML",
            )
    except CineBotError as e:
        await update.message.reply_text(e.user_message, parse_mode="HTML")


async def explain_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    movie_id = int(query.data.split(":")[1])
    await query.message.reply_text(
        f"{E_ROBOT} <b>Choose explanation type:</b>",
        reply_markup=explain_type_kb(movie_id),
        parse_mode="HTML",
    )


async def explain_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer("Generating explanation...")
    parts = query.data.split(":")
    explain_type = parts[1]
    movie_id = int(parts[2])
    await ensure_user(update, context)

    telegram_id = update.effective_user.id
    async with get_session() as session:
        user = await UserRepo.get_by_telegram_id(session, telegram_id)
    is_pro = user.is_pro if user else False

    try:
        await check_rate_limit(telegram_id, "explain", is_pro)
    except CineBotError as e:
        await query.edit_message_text(e.user_message, parse_mode="HTML")
        return

    await query.edit_message_text(f"{E_ROBOT} Generating AI explanation...", parse_mode="HTML")

    try:
        movie = await tmdb_service.get_movie(movie_id)
        title = movie.get("title", "Unknown")
        year = movie.get("release_date", "")[:4]
        overview = movie.get("overview", "")
        explanation = await openai_service.explain_movie(title, year, overview, explain_type)
        await increment_usage(telegram_id, "explain")
        text = f"🎬 <b>{title}</b> ({year})\n\n{explanation}"
        if len(text) > 4096:
            text = text[:4090] + "..."
        await query.edit_message_text(text, parse_mode="HTML")
    except CineBotError as e:
        await query.edit_message_text(e.user_message, parse_mode="HTML")


def get_handlers() -> list:
    return [
        CommandHandler("explain", explain_command),
        CallbackQueryHandler(explain_menu_callback, pattern=r"^explain_menu:\d+$"),
        CallbackQueryHandler(explain_callback, pattern=r"^explain:(plot|ending|hidden|chars):\d+$"),
    ]