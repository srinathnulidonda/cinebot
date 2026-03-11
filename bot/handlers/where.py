# bot/handlers/where.py
import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from bot.middleware.subscription_check import ensure_user
from bot.middleware.analytics import track_command
from bot.services import tmdb_service, streaming_service
from bot.utils.formatters import format_streaming, format_no_results
from bot.utils.keyboards import search_results_kb, tv_search_results_kb, no_results_kb
from bot.utils.constants import E_TV, LINE
from bot import CineBotError

logger = logging.getLogger(__name__)


async def where_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    await track_command(update, context)

    args = context.args or []
    if not args:
        await update.message.reply_text(
            f"{E_TV} <b>WHERE TO WATCH</b>\n"
            f"{LINE}\n\n"
            "Usage:\n"
            "<code>/where Movie Name</code>\n"
            "<code>/where tv Show Name</code>\n\n"
            "💡 <code>/where Interstellar</code>\n"
            "💡 <code>/where tv The Office</code>",
            parse_mode="HTML",
        )
        return

    is_tv = args[0].lower() == "tv"
    query = " ".join(args[1:]) if is_tv else " ".join(args)

    if not query:
        await update.message.reply_text("❌ Please provide a title.", parse_mode="HTML")
        return

    loading = await update.message.reply_text(
        f"{E_TV} Checking streaming options...", parse_mode="HTML",
    )
    try:
        if is_tv:
            data = await tmdb_service.search_tv(query)
            results = data.get("results", [])
            if not results:
                await loading.edit_text(
                    format_no_results(query), reply_markup=no_results_kb(), parse_mode="HTML",
                )
                return
            show = results[0]
            tv_id = show["id"]
            providers = await tmdb_service.get_tv_watch_providers(tv_id)
            country_data = providers.get("results", {}).get("US", {})
            info = None
            if country_data:
                info = {
                    "link": country_data.get("link", ""),
                    "flatrate": country_data.get("flatrate", []),
                    "rent": country_data.get("rent", []),
                    "buy": country_data.get("buy", []),
                }
            name = show.get("name", "Unknown")
            year = show.get("first_air_date", "")[:4]
            text = (
                f"📺 <b>{name}</b> ({year})\n"
                f"{LINE}\n\n"
                f"{format_streaming(info)}"
            )
            if info and info.get("link"):
                text += f"\n\n🔗 <a href=\"{info['link']}\">More info ↗️</a>"
            await loading.edit_text(text, parse_mode="HTML", disable_web_page_preview=True)
        else:
            data = await tmdb_service.search_movies(query)
            results = data.get("results", [])
            if not results:
                await loading.edit_text(
                    format_no_results(query), reply_markup=no_results_kb(), parse_mode="HTML",
                )
                return
            movie = results[0]
            movie_id = movie["id"]
            info = await streaming_service.get_streaming_info(movie_id)
            title = movie.get("title", "Unknown")
            year = movie.get("release_date", "")[:4]
            text = (
                f"🎬 <b>{title}</b> ({year})\n"
                f"{LINE}\n\n"
                f"{format_streaming(info)}"
            )
            if info and info.get("link"):
                text += f"\n\n🔗 <a href=\"{info['link']}\">More info ↗️</a>"
            await loading.edit_text(text, parse_mode="HTML", disable_web_page_preview=True)
    except CineBotError as e:
        await loading.edit_text(e.user_message, parse_mode="HTML")


async def where_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer("Checking streams... 📺")
    movie_id = int(query.data.split(":")[1])
    try:
        movie = await tmdb_service.get_movie(movie_id)
        info = await streaming_service.get_streaming_info(movie_id)
        title = movie.get("title", "Unknown")
        year = movie.get("release_date", "")[:4]
        text = (
            f"🎬 <b>{title}</b> ({year})\n"
            f"{LINE}\n\n"
            f"{format_streaming(info)}"
        )
        if info and info.get("link"):
            text += f"\n\n🔗 <a href=\"{info['link']}\">More info ↗️</a>"
        await query.message.reply_text(text, parse_mode="HTML", disable_web_page_preview=True)
    except CineBotError as e:
        await query.answer(e.user_message, show_alert=True)


async def where_tv_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer("Checking streams... 📺")
    tv_id = int(query.data.split(":")[1])
    try:
        show = await tmdb_service.get_tv_show(tv_id)
        providers = await tmdb_service.get_tv_watch_providers(tv_id)
        country_data = providers.get("results", {}).get("US", {})
        info = None
        if country_data:
            info = {
                "link": country_data.get("link", ""),
                "flatrate": country_data.get("flatrate", []),
                "rent": country_data.get("rent", []),
                "buy": country_data.get("buy", []),
            }
        name = show.get("name", "Unknown")
        year = show.get("first_air_date", "")[:4]
        text = (
            f"📺 <b>{name}</b> ({year})\n"
            f"{LINE}\n\n"
            f"{format_streaming(info)}"
        )
        if info and info.get("link"):
            text += f"\n\n🔗 <a href=\"{info['link']}\">More info ↗️</a>"
        await query.message.reply_text(text, parse_mode="HTML", disable_web_page_preview=True)
    except CineBotError as e:
        await query.answer(e.user_message, show_alert=True)


def get_handlers() -> list:
    return [
        CommandHandler("where", where_command),
        CallbackQueryHandler(where_callback, pattern=r"^where:\d+$"),
        CallbackQueryHandler(where_tv_callback, pattern=r"^where_tv:\d+$"),
    ]