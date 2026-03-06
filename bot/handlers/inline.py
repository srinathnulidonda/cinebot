# bot/handlers/inline.py
import logging
import hashlib
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import ContextTypes, InlineQueryHandler
from bot.services import tmdb_service
from bot.utils.formatters import format_movie_card
from bot.utils.constants import TMDB_GENRES, E_MOVIE

logger = logging.getLogger(__name__)


async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.inline_query.query.strip()
    if not query or len(query) < 2:
        return

    try:
        data = await tmdb_service.search_movies(query)
        results = data.get("results", [])[:10]
    except Exception:
        results = []

    articles = []
    for movie in results:
        mid = movie["id"]
        title = movie.get("title", "Unknown")
        year = movie.get("release_date", "")[:4]
        rating = movie.get("vote_average", 0)
        overview = movie.get("overview", "No overview available.")[:200]
        genres = ", ".join(TMDB_GENRES.get(g, "") for g in movie.get("genre_ids", []) if g in TMDB_GENRES)
        poster = movie.get("poster_path")
        thumb_url = f"https://image.tmdb.org/t/p/w92{poster}" if poster else None

        text = (
            f"{E_MOVIE} <b>{title}</b> ({year})\n"
            f"⭐ {rating:.1f}/10\n"
            f"🎭 {genres}\n\n"
            f"📝 {overview}\n\n"
            f"<i>Powered by CineBot 🍿</i>"
        )

        result_id = hashlib.md5(f"{mid}".encode()).hexdigest()
        articles.append(
            InlineQueryResultArticle(
                id=result_id,
                title=f"🎬 {title} ({year})",
                description=f"⭐ {rating:.1f} | {genres[:50]}",
                input_message_content=InputTextMessageContent(text, parse_mode="HTML"),
                thumbnail_url=thumb_url,
            )
        )

    await update.inline_query.answer(articles, cache_time=300, is_personal=False)


def get_handlers() -> list:
    return [InlineQueryHandler(inline_query)]