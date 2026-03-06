# bot/handlers/watched.py
import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from bot.middleware.subscription_check import ensure_user
from bot.middleware.analytics import track_command, track_event
from bot.models.engine import get_session
from bot.models.user import UserRepo
from bot.models.watched import WatchedRepo
from bot.models.watchlist import WatchlistRepo
from bot.models.preference import PreferenceRepo
from bot.services import tmdb_service
from bot.utils.formatters import format_watched_item, check_milestone
from bot.utils.keyboards import rating_kb, search_results_kb, pagination_kb
from bot.utils.constants import E_FILM, E_CHECK, E_STAR, MSG_WATCHED_EMPTY, TMDB_GENRES
from bot.utils.pagination import AsyncPaginator
from bot.config import get_settings
from bot import CineBotError

logger = logging.getLogger(__name__)
_s = get_settings()


async def watched_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    await track_command(update, context)
    args = context.args or []
    if args:
        query = " ".join(args)
        try:
            data = await tmdb_service.search_movies(query)
            results = data.get("results", [])[:6]
            if not results:
                await update.message.reply_text("🔍 No movies found.", parse_mode="HTML")
                return
            await update.message.reply_text(
                f"{E_FILM} Select a movie to mark as watched:",
                reply_markup=search_results_kb(results),
                parse_mode="HTML",
            )
        except CineBotError as e:
            await update.message.reply_text(e.user_message, parse_mode="HTML")
        return
    await _show_watched(update, context, page=1)


async def _show_watched(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 1, message=None) -> None:
    user_db_id = context.user_data.get("db_user_id", 0)
    async with get_session() as session:
        items, total = await WatchedRepo.get_paginated(session, user_db_id, page, _s.ITEMS_PER_PAGE)
    if not items and page == 1:
        target = message or update.message or update.callback_query.message
        if message:
            await target.edit_text(MSG_WATCHED_EMPTY, parse_mode="HTML")
        else:
            await target.reply_text(MSG_WATCHED_EMPTY, parse_mode="HTML")
        return
    pag = AsyncPaginator(items, total, page, _s.ITEMS_PER_PAGE)
    lines = [f"{E_FILM} <b>Your Watched Movies</b> ({total} movies)\n"]
    offset = (page - 1) * _s.ITEMS_PER_PAGE
    for i, item in enumerate(items, offset + 1):
        lines.append(format_watched_item(item, i))
    lines.append(f"\n{pag.info}")
    text = "\n".join(lines)
    kb = pagination_kb("watched", page, pag.total_pages)
    target = message or update.message or update.callback_query.message
    if message:
        await target.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await target.reply_text(text, reply_markup=kb, parse_mode="HTML")


async def watched_add_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    movie_id = int(query.data.split(":")[1])
    await ensure_user(update, context)
    user_db_id = context.user_data.get("db_user_id", 0)

    async with get_session() as session:
        if await WatchedRepo.exists(session, user_db_id, movie_id):
            await query.answer("Already in your watched list!", show_alert=True)
            return

    try:
        movie = await tmdb_service.get_movie(movie_id)
        genre_ids = [g["id"] for g in movie.get("genres", [])]
        async with get_session() as session:
            await WatchedRepo.add(
                session, user_db_id, movie_id,
                movie.get("title", "Unknown"),
                movie.get("poster_path"),
                genre_ids=genre_ids,
            )
            await WatchlistRepo.remove(session, user_db_id, movie_id)
            count = await WatchedRepo.count(session, user_db_id)
            for gid in genre_ids:
                gname = TMDB_GENRES.get(gid, str(gid))
                await PreferenceRepo.increment_genre(session, user_db_id, str(gid), gname)
            cast = movie.get("credits", {}).get("cast", [])[:5]
            if cast:
                await PreferenceRepo.increment_actors(session, user_db_id, cast)

        await track_event("movie_watched", update.effective_user.id)
        await query.message.reply_text(
            f"{E_CHECK} <b>{movie.get('title')}</b> marked as watched!\n\nRate it:",
            reply_markup=rating_kb(movie_id),
            parse_mode="HTML",
        )

        milestone = check_milestone(count)
        if milestone:
            await query.message.reply_text(milestone, parse_mode="HTML")
    except CineBotError as e:
        await query.answer(e.user_message, show_alert=True)


async def rate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    parts = query.data.split(":")
    movie_id = int(parts[1])
    rating = float(parts[2])
    await query.answer(f"Rated {rating}/10!")
    await ensure_user(update, context)
    user_db_id = context.user_data.get("db_user_id", 0)

    async with get_session() as session:
        await WatchedRepo.update_rating(session, user_db_id, movie_id, rating)

    await query.edit_message_text(
        f"{E_STAR} Rated <b>{rating}/10</b>! Great taste! 🍿",
        parse_mode="HTML",
    )


async def review_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    movie_id = int(query.data.split(":")[1])
    await query.answer()
    context.user_data["awaiting_review_for"] = movie_id
    await query.edit_message_text(
        "📝 <b>Write your review:</b>\n\nSend your review as a text message.",
        parse_mode="HTML",
    )


async def review_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    movie_id = context.user_data.get("awaiting_review_for")
    if not movie_id:
        return
    await ensure_user(update, context)
    user_db_id = context.user_data.get("db_user_id", 0)
    review = update.message.text[:1000]

    async with get_session() as session:
        existing = await WatchedRepo.exists(session, user_db_id, movie_id)
        if existing:
            await WatchedRepo.update_rating(session, user_db_id, movie_id, 0, review)

    context.user_data.pop("awaiting_review_for", None)
    await update.message.reply_text(f"{E_CHECK} Review saved!", parse_mode="HTML")


async def watched_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    page = int(query.data.split(":")[2])
    await ensure_user(update, context)
    await _show_watched(update, context, page, message=query.message)


def get_handlers() -> list:
    return [
        CommandHandler("watched", watched_command),
        CallbackQueryHandler(watched_add_callback, pattern=r"^watched_add:\d+$"),
        CallbackQueryHandler(rate_callback, pattern=r"^rate:\d+:\d+$"),
        CallbackQueryHandler(review_callback, pattern=r"^review:\d+$"),
        CallbackQueryHandler(watched_page_callback, pattern=r"^watched:page:\d+$"),
    ]