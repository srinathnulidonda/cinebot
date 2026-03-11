# bot/handlers/search.py
import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from bot.middleware.subscription_check import ensure_user
from bot.middleware.rate_limiter import check_rate_limit, increment_usage
from bot.middleware.analytics import track_command
from bot.services import tmdb_service
from bot.models.engine import get_session
from bot.models.user import UserRepo
from bot.models.watchlist import WatchlistRepo
from bot.utils.formatters import (
    format_movie_card, format_movie_credits, format_no_results,
    format_tv_card, format_tv_credits,
)
from bot.utils.keyboards import (
    movie_detail_kb, search_results_kb, no_results_kb,
    tv_detail_kb, tv_search_results_kb, multi_search_results_kb,
)
from bot.utils.validators import validate_movie_title
from bot.utils.constants import E_SEARCH, E_TV, LINE
from bot import MovieNotFoundError, CineBotError

logger = logging.getLogger(__name__)


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    await track_command(update, context)

    args = context.args or []
    if not args:
        await update.message.reply_text(
            f"{E_SEARCH} <b>SEARCH</b>\n"
            f"{LINE}\n\n"
            f"Usage:\n"
            f"<code>/search Movie Name</code>\n"
            f"<code>/search tv Show Name</code>\n\n"
            f"💡 <code>/search Inception</code>\n"
            f"💡 <code>/search tv Breaking Bad</code>\n\n"
            "Or just type any title!",
            parse_mode="HTML",
        )
        return

    is_tv = args[0].lower() == "tv"
    query = " ".join(args[1:]) if is_tv else " ".join(args)

    if not query:
        await update.message.reply_text(
            "❌ Please provide a title to search.", parse_mode="HTML",
        )
        return

    title = validate_movie_title(query)
    if not title:
        await update.message.reply_text(
            format_no_results(query), reply_markup=no_results_kb(), parse_mode="HTML",
        )
        return

    telegram_id = update.effective_user.id
    async with get_session() as session:
        user = await UserRepo.get_by_telegram_id(session, telegram_id)
    is_pro = user.is_pro if user else False
    await check_rate_limit(telegram_id, "search", is_pro)

    loading = await update.message.reply_text(
        f"{E_SEARCH} Searching \"<b>{title}</b>\"{'  📺' if is_tv else ''}...",
        parse_mode="HTML",
    )

    try:
        if is_tv:
            await _search_tv(loading, title, telegram_id, user)
        else:
            await _search_movie(loading, title, telegram_id, user)
    except MovieNotFoundError:
        await loading.edit_text(
            format_no_results(title), reply_markup=no_results_kb(), parse_mode="HTML",
        )
    except CineBotError as e:
        await loading.edit_text(e.user_message, parse_mode="HTML")


async def _search_movie(message, title: str, telegram_id: int, user) -> None:
    data = await tmdb_service.search_movies(title)
    results = data.get("results", [])
    if not results:
        await message.edit_text(
            format_no_results(title), reply_markup=no_results_kb(), parse_mode="HTML",
        )
        return
    await increment_usage(telegram_id, "search")

    if len(results) == 1 or results[0].get("vote_count", 0) > 100:
        await _show_movie_detail(message, results[0]["id"], user.id if user else 0)
    else:
        count = min(len(results), 8)
        await message.edit_text(
            f"{E_SEARCH} <b>{count} results</b> for \"<b>{title}</b>\"\n{LINE}\n\nSelect a movie:",
            reply_markup=search_results_kb(results),
            parse_mode="HTML",
        )


async def _search_tv(message, title: str, telegram_id: int, user) -> None:
    data = await tmdb_service.search_tv(title)
    results = data.get("results", [])
    if not results:
        await message.edit_text(
            format_no_results(title), reply_markup=no_results_kb(), parse_mode="HTML",
        )
        return
    await increment_usage(telegram_id, "search")

    if len(results) == 1 or results[0].get("vote_count", 0) > 100:
        await _show_tv_detail(message, results[0]["id"], user.id if user else 0)
    else:
        count = min(len(results), 8)
        await message.edit_text(
            f"{E_TV} <b>{count} results</b> for \"<b>{title}</b>\"\n{LINE}\n\nSelect a show:",
            reply_markup=tv_search_results_kb(results),
            parse_mode="HTML",
        )


async def movie_detail_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    movie_id = int(query.data.split(":")[1])
    await ensure_user(update, context)
    user_db_id = context.user_data.get("db_user_id", 0)
    await _show_movie_detail(query.message, movie_id, user_db_id, edit=True)


async def tv_show_detail_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    tv_id = int(query.data.split(":")[1])
    await ensure_user(update, context)
    user_db_id = context.user_data.get("db_user_id", 0)
    await _show_tv_detail(query.message, tv_id, user_db_id, edit=True)


async def _show_movie_detail(message, movie_id: int, user_db_id: int, edit: bool = True) -> None:
    try:
        movie = await tmdb_service.get_movie(movie_id)
        card_text = format_movie_card(movie)
        credits = movie.get("credits")
        if credits:
            credits_text = format_movie_credits(credits)
            if credits_text:
                card_text += f"\n\n{credits_text}"

        in_watchlist = False
        if user_db_id:
            async with get_session() as session:
                in_watchlist = await WatchlistRepo.exists(session, user_db_id, movie_id)

        kb = movie_detail_kb(movie_id, in_watchlist)

        if edit:
            try:
                await message.edit_text(card_text, reply_markup=kb, parse_mode="HTML")
            except Exception:
                await message.reply_text(card_text, reply_markup=kb, parse_mode="HTML")
        else:
            await message.reply_text(card_text, reply_markup=kb, parse_mode="HTML")
    except CineBotError as e:
        text = e.user_message
        if edit:
            await message.edit_text(text, parse_mode="HTML")
        else:
            await message.reply_text(text, parse_mode="HTML")


async def _show_tv_detail(message, tv_id: int, user_db_id: int, edit: bool = True) -> None:
    try:
        show = await tmdb_service.get_tv_show(tv_id)
        card_text = format_tv_card(show)
        credits = show.get("credits")
        if credits:
            credits_text = format_tv_credits(credits)
            if credits_text:
                card_text += f"\n\n{credits_text}"

        in_watchlist = False
        if user_db_id:
            async with get_session() as session:
                in_watchlist = await WatchlistRepo.exists(session, user_db_id, tv_id)

        kb = tv_detail_kb(tv_id, in_watchlist)

        if edit:
            try:
                await message.edit_text(card_text, reply_markup=kb, parse_mode="HTML")
            except Exception:
                await message.reply_text(card_text, reply_markup=kb, parse_mode="HTML")
        else:
            await message.reply_text(card_text, reply_markup=kb, parse_mode="HTML")
    except CineBotError as e:
        text = e.user_message
        if edit:
            await message.edit_text(text, parse_mode="HTML")
        else:
            await message.reply_text(text, parse_mode="HTML")


async def similar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer("Loading similar... 🎬")
    movie_id = int(query.data.split(":")[1])
    try:
        data = await tmdb_service.get_similar(movie_id)
        results = data.get("results", [])[:6]
        if not results:
            await query.answer("No similar movies found 🙈", show_alert=True)
            return
        await query.message.reply_text(
            f"🔍 <b>Similar Movies</b>\n{LINE}",
            reply_markup=search_results_kb(results),
            parse_mode="HTML",
        )
    except Exception:
        await query.answer("Failed to load 🙈", show_alert=True)


async def similar_tv_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer("Loading similar... 📺")
    tv_id = int(query.data.split(":")[1])
    try:
        data = await tmdb_service.get_tv_similar(tv_id)
        results = data.get("results", [])[:6]
        if not results:
            await query.answer("No similar shows found 🙈", show_alert=True)
            return
        await query.message.reply_text(
            f"🔍 <b>Similar TV Shows</b>\n{LINE}",
            reply_markup=tv_search_results_kb(results),
            parse_mode="HTML",
        )
    except Exception:
        await query.answer("Failed to load 🙈", show_alert=True)


def get_handlers() -> list:
    return [
        CommandHandler("search", search_command),
        CallbackQueryHandler(movie_detail_callback, pattern=r"^movie:\d+$"),
        CallbackQueryHandler(tv_show_detail_callback, pattern=r"^tv_show:\d+$"),
        CallbackQueryHandler(similar_callback, pattern=r"^similar:\d+$"),
        CallbackQueryHandler(similar_tv_callback, pattern=r"^similar_tv:\d+$"),
    ]