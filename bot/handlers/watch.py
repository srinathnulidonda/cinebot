# bot/handlers/watch.py
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from bot.middleware.subscription_check import ensure_user
from bot.middleware.analytics import track_command
from bot.services import tmdb_service
from bot.services.stream import get_movie_player_url, get_tv_player_url, get_tv_seasons
from bot.utils.constants import E_MOVIE, E_TV, E_STAR, E_PLAY, LINE
from bot.utils.validators import sanitize_html
from bot.utils.keyboards import search_results_kb, tv_search_results_kb
from bot import CineBotError

logger = logging.getLogger(__name__)


def watch_movie_kb(tmdb_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ Watch Now", url=get_movie_player_url(tmdb_id))],
        [
            InlineKeyboardButton("🎥 Trailer", callback_data=f"trailer:{tmdb_id}"),
            InlineKeyboardButton("📺 Stream", callback_data=f"where:{tmdb_id}"),
        ],
        [InlineKeyboardButton("📥 Save", callback_data=f"wl_add:{tmdb_id}")],
    ])


def watch_tv_kb(tmdb_id: int, season: int = 1, episode: int = 1) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"▶️ Watch S{season}E{episode}", url=get_tv_player_url(tmdb_id, season, episode))],
        [
            InlineKeyboardButton("📋 Episodes", callback_data=f"tv_eps:{tmdb_id}:{season}"),
            InlineKeyboardButton("📺 Stream", callback_data=f"where_tv:{tmdb_id}"),
        ],
        [InlineKeyboardButton("📥 Save", callback_data=f"wl_add_tv:{tmdb_id}")],
    ])


async def watch_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    await track_command(update, context)

    args = context.args or []
    if not args:
        await update.message.reply_text(
            f"▶️ <b>WATCH</b>\n"
            f"{LINE}\n\n"
            "Usage:\n"
            "<code>/watch movie_name</code>\n"
            "<code>/watch tv show_name</code>\n\n"
            "💡 <code>/watch Inception</code>\n"
            "💡 <code>/watch tv Breaking Bad</code>",
            parse_mode="HTML",
        )
        return

    is_tv = args[0].lower() == "tv"
    query = " ".join(args[1:]) if is_tv else " ".join(args)

    if not query:
        await update.message.reply_text("❌ Please provide a title.", parse_mode="HTML")
        return

    loading = await update.message.reply_text(
        f"🔍 Searching \"{sanitize_html(query)}\"...", parse_mode="HTML",
    )

    try:
        if is_tv:
            await _handle_tv_search(loading, query)
        else:
            await _handle_movie_search(loading, query)
    except CineBotError as e:
        await loading.edit_text(e.user_message, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Watch command error: {e}")
        await loading.edit_text("⚠️ Something went wrong. Try again.", parse_mode="HTML")


async def _handle_movie_search(message, query: str) -> None:
    data = await tmdb_service.search_movies(query)
    results = data.get("results", [])
    if not results:
        await message.edit_text(
            f"❌ No movies found for \"{sanitize_html(query)}\"", parse_mode="HTML",
        )
        return

    if len(results) == 1 or results[0].get("vote_count", 0) > 100:
        movie = results[0]
        mid = movie["id"]
        title = sanitize_html(movie.get("title", "Unknown"))
        year = movie.get("release_date", "")[:4]
        rating = movie.get("vote_average", 0)
        overview = sanitize_html(movie.get("overview", ""))[:300]

        text = (
            f"▶️ <b>WATCH MOVIE</b>\n"
            f"{LINE}\n\n"
            f"{E_MOVIE} <b>{title}</b> ({year})\n"
            f"{E_STAR} {rating:.1f}/10\n\n"
            f"{overview}{'...' if len(movie.get('overview', '')) > 300 else ''}"
        )
        await message.edit_text(text, reply_markup=watch_movie_kb(mid), parse_mode="HTML")
    else:
        await message.edit_text(
            f"🔍 <b>Select a movie to watch:</b>\n{LINE}",
            reply_markup=search_results_kb(results[:6]),
            parse_mode="HTML",
        )


async def _handle_tv_search(message, query: str) -> None:
    data = await tmdb_service.search_tv(query)
    results = data.get("results", [])
    if not results:
        await message.edit_text(
            f"❌ No TV shows found for \"{sanitize_html(query)}\"", parse_mode="HTML",
        )
        return

    if len(results) == 1 or results[0].get("vote_count", 0) > 50:
        show = results[0]
        sid = show["id"]
        name = sanitize_html(show.get("name", "Unknown"))
        year = show.get("first_air_date", "")[:4]
        rating = show.get("vote_average", 0)
        overview = sanitize_html(show.get("overview", ""))[:300]

        text = (
            f"▶️ <b>WATCH TV SHOW</b>\n"
            f"{LINE}\n\n"
            f"{E_TV} <b>{name}</b> ({year})\n"
            f"{E_STAR} {rating:.1f}/10\n\n"
            f"{overview}{'...' if len(show.get('overview', '')) > 300 else ''}"
        )
        await message.edit_text(text, reply_markup=watch_tv_kb(sid), parse_mode="HTML")
    else:
        await message.edit_text(
            f"📺 <b>Select a show to watch:</b>\n{LINE}",
            reply_markup=tv_search_results_kb(results[:6]),
            parse_mode="HTML",
        )


async def watch_movie_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    movie_id = int(query.data.split(":")[1])
    await ensure_user(update, context)

    try:
        movie = await tmdb_service.get_movie(movie_id)
        title = sanitize_html(movie.get("title", "Unknown"))
        year = movie.get("release_date", "")[:4]
        rating = movie.get("vote_average", 0)

        text = (
            f"▶️ <b>{title}</b> ({year})\n"
            f"{LINE}\n"
            f"{E_STAR} {rating:.1f}/10\n\n"
            "Tap below to start watching:"
        )
        await query.message.reply_text(
            text, reply_markup=watch_movie_kb(movie_id), parse_mode="HTML",
        )
    except CineBotError as e:
        await query.answer(e.user_message, show_alert=True)


async def tv_episodes_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    parts = query.data.split(":")
    tmdb_id = int(parts[1])
    season = int(parts[2]) if len(parts) > 2 else 1
    await query.answer()

    seasons_data = await get_tv_seasons(tmdb_id)
    if not seasons_data:
        await query.answer("❌ Could not load episodes", show_alert=True)
        return

    show_name = sanitize_html(seasons_data.get("name", "Unknown"))
    target_season = None
    for s in seasons_data.get("seasons", []):
        if s["season_number"] == season:
            target_season = s
            break

    if not target_season:
        await query.answer("❌ Season not found", show_alert=True)
        return

    lines = [
        f"{E_TV} <b>{show_name}</b>",
        f"📋 <b>{target_season['name']}</b> ({target_season['episode_count']} episodes)",
        LINE,
        "",
    ]

    episodes = target_season.get("episodes", [])
    for ep in episodes[:20]:
        ep_num = ep["episode_number"]
        ep_name = sanitize_html(ep.get("name", f"Episode {ep_num}"))[:40]
        rating = ep.get("vote_average", 0)
        runtime = ep.get("runtime")
        rt_str = f" · {runtime}m" if runtime else ""
        lines.append(f"  {ep_num}. {ep_name} ⭐{rating:.1f}{rt_str}")

    buttons: list[list[InlineKeyboardButton]] = []

    ep_rows: list[InlineKeyboardButton] = []
    for ep in episodes[:24]:
        ep_num = ep["episode_number"]
        ep_rows.append(InlineKeyboardButton(
            f"E{ep_num}",
            url=get_tv_player_url(tmdb_id, season, ep_num),
        ))
    for i in range(0, len(ep_rows), 6):
        buttons.append(ep_rows[i:i + 6])

    season_nav: list[InlineKeyboardButton] = []
    total_seasons = seasons_data.get("number_of_seasons", 1)
    if season > 1:
        season_nav.append(InlineKeyboardButton("◀️ Prev", callback_data=f"tv_eps:{tmdb_id}:{season - 1}"))
    season_nav.append(InlineKeyboardButton(f"S{season}/{total_seasons}", callback_data="noop"))
    if season < total_seasons:
        season_nav.append(InlineKeyboardButton("Next ▶️", callback_data=f"tv_eps:{tmdb_id}:{season + 1}"))
    buttons.append(season_nav)

    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:3997] + "..."

    try:
        await query.edit_message_text(
            text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML",
        )
    except Exception:
        await query.message.reply_text(
            text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML",
        )


def get_handlers() -> list:
    return [
        CommandHandler("watch", watch_command),
        CallbackQueryHandler(watch_movie_callback, pattern=r"^watch_movie:\d+$"),
        CallbackQueryHandler(tv_episodes_callback, pattern=r"^tv_eps:\d+:\d+$"),
    ]