# bot/handlers/inline.py
import logging
import hashlib
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import ContextTypes, InlineQueryHandler
from bot.services import tmdb_service
from bot.utils.formatters import genre_tags, star_rating, format_votes
from bot.utils.constants import TMDB_GENRES, E_MOVIE, E_STAR, E_TV, LINE

logger = logging.getLogger(__name__)


async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.inline_query.query.strip()
    if not query or len(query) < 2:
        return

    articles = []

    try:
        data = await tmdb_service.multi_search(query)
        results = data.get("results", [])[:10]
    except Exception:
        results = []

    for item in results:
        media_type = item.get("media_type")
        if media_type not in ("movie", "tv"):
            continue

        mid = item["id"]
        is_tv = media_type == "tv"

        title = item.get("name" if is_tv else "title", "Unknown")
        date_key = "first_air_date" if is_tv else "release_date"
        year = item.get(date_key, "")[:4]
        rating = item.get("vote_average", 0)
        votes = item.get("vote_count", 0)
        overview = item.get("overview", "No overview available.")[:200]
        tags = genre_tags(item.get("genre_ids"))
        stars = star_rating(rating)
        poster = item.get("poster_path")
        thumb_url = f"https://image.tmdb.org/t/p/w92{poster}" if poster else None

        icon = E_TV if is_tv else E_MOVIE
        type_label = "📺 TV" if is_tv else "🎬 Movie"

        from bot.services.stream import get_movie_player_url, get_tv_player_url
        player_url = get_tv_player_url(mid) if is_tv else get_movie_player_url(mid)

        text = (
            f"{icon} <b>{title}</b> ({year})\n"
            f"{LINE}\n"
            f"{E_STAR} <b>{rating:.1f}</b>/10 {stars} · 🗳 {format_votes(votes)}\n"
            f"🎭 {tags}\n"
            f"📌 {type_label}\n\n"
            f"📝 {overview}\n\n"
            f"▶️ <a href=\"{player_url}\">Watch Now</a>\n\n"
            f"<i>Powered by CineBot 🍿</i>"
        )

        result_id = hashlib.md5(f"{media_type}:{mid}".encode()).hexdigest()
        genre_str = ", ".join(
            TMDB_GENRES.get(g, "") for g in item.get("genre_ids", []) if g in TMDB_GENRES
        )[:50]

        articles.append(
            InlineQueryResultArticle(
                id=result_id,
                title=f"{icon} {title} ({year})",
                description=f"⭐ {rating:.1f} · {type_label} · {genre_str}",
                input_message_content=InputTextMessageContent(text, parse_mode="HTML"),
                thumbnail_url=thumb_url,
            )
        )

    await update.inline_query.answer(articles, cache_time=300, is_personal=False)


def get_handlers() -> list:
    return [InlineQueryHandler(inline_query)]