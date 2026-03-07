# bot/main.py
import logging
import sys
from datetime import time, timezone
from telegram import Update, BotCommand, LinkPreviewOptions
from telegram.ext import (
    Application, ApplicationBuilder, CommandHandler,
    CallbackQueryHandler, MessageHandler, filters, Defaults,
)
from bot.config import get_settings
from bot.models.engine import init_db, close_db
from bot.handlers import (
    start, search, recommend, watchlist, watched,
    where, compare, explain, stats, alerts,
    random as random_handler, mood, inline, redeem, admin, callbacks, contact,
)
from bot.jobs.daily_suggestion import daily_suggestion_job
from bot.jobs.release_alerts import release_alerts_job
from bot.jobs.subscription_expiry import subscription_expiry_job
from bot.middleware.subscription_check import ensure_user
from bot.middleware.rate_limiter import check_global_rate_limit
from bot.middleware.analytics import track_command
from bot.utils.constants import LINE
from bot import CineBotError

logger = logging.getLogger(__name__)
_s = get_settings()

BOT_COMMANDS = [
    BotCommand("start", "Start the bot"),
    BotCommand("help", "Show help message"),
    BotCommand("search", "Search for a movie"),
    BotCommand("recommend", "Get AI recommendations"),
    BotCommand("watchlist", "Manage your watchlist"),
    BotCommand("watched", "Log watched movies"),
    BotCommand("where", "Find where to stream"),
    BotCommand("compare", "Compare two movies"),
    BotCommand("explain", "AI movie explanations"),
    BotCommand("stats", "Your watching statistics"),
    BotCommand("alerts", "Release notifications"),
    BotCommand("random", "Random movie suggestion"),
    BotCommand("mood", "Mood-based picks"),
    BotCommand("redeem", "Redeem a Pro key"),
    BotCommand("pro", "View your plan"),
    BotCommand("contact", "Contact admin support"),
]


async def error_handler(update: object, context) -> None:
    error = context.error
    if isinstance(error, CineBotError):
        if isinstance(update, Update):
            if update.callback_query:
                try:
                    await update.callback_query.answer(error.user_message, show_alert=True)
                except Exception:
                    pass
            elif update.effective_message:
                try:
                    from bot.utils.keyboards import rate_limit_kb
                    from bot import RateLimitExceededError, SubscriptionRequiredError
                    kb = None
                    if isinstance(error, (RateLimitExceededError, SubscriptionRequiredError)):
                        kb = rate_limit_kb()
                    await update.effective_message.reply_text(
                        error.user_message, parse_mode="HTML", reply_markup=kb,
                    )
                except Exception:
                    pass
        return
    logger.error(f"Unhandled exception: {error}", exc_info=context.error)
    if isinstance(update, Update):
        try:
            if update.callback_query:
                await update.callback_query.answer("⚠️ Something went wrong.", show_alert=True)
            elif update.effective_message:
                from bot.utils.keyboards import rate_limit_kb
                await update.effective_message.reply_text(
                    "⚠️ <b>Unexpected Error</b>\n\n"
                    "Something went wrong. Try again shortly.\n\n"
                    "📞 /contact if this persists",
                    parse_mode="HTML",
                    reply_markup=rate_limit_kb(),
                )
        except Exception:
            pass


async def text_message_handler(update: Update, context) -> None:
    if not update.message or not update.message.text:
        return

    replying_ticket = context.user_data.get("replying_ticket")
    if replying_ticket:
        from bot.handlers.contact import admin_reply_handler
        await admin_reply_handler(update, context)
        return

    awaiting_review = context.user_data.get("awaiting_review_for")
    if awaiting_review:
        from bot.handlers.watched import review_text_handler
        await review_text_handler(update, context)
        return

    awaiting_similar = context.user_data.get("awaiting_similar_movie")
    if awaiting_similar:
        context.user_data.pop("awaiting_similar_movie", None)
        await ensure_user(update, context)
        query = update.message.text.strip()
        if not query:
            return
        from bot.services import tmdb_service
        from bot.services import recommendation_engine
        from bot.utils.formatters import format_recommendation_list
        from bot.utils.keyboards import search_results_kb
        from bot.utils.constants import E_BRAIN
        loading = await update.message.reply_text(
            f"{E_BRAIN} Finding similar movies...\n⏳ This may take a moment",
            parse_mode="HTML",
        )
        try:
            search_data = await tmdb_service.search_movies(query)
            results = search_data.get("results", [])
            if not results:
                from bot.utils.formatters import format_no_results
                from bot.utils.keyboards import no_results_kb
                await loading.edit_text(
                    format_no_results(query), reply_markup=no_results_kb(), parse_mode="HTML",
                )
                return
            source_movie = results[0]
            user_db_id = context.user_data.get("db_user_id", 0)
            movies = await recommendation_engine.recommend_similar(user_db_id, source_movie["id"])
            from bot.middleware.rate_limiter import increment_usage
            await increment_usage(update.effective_user.id, "recommend")
            if not movies:
                await loading.edit_text(
                    "😕 No similar movies found. Try another title! 🎬", parse_mode="HTML",
                )
                return
            source_title = source_movie.get("title", "?")
            text = format_recommendation_list(movies, f"🎬 Similar to '{source_title}'")
            kb = search_results_kb(movies)
            await loading.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except CineBotError as e:
            await loading.edit_text(e.user_message, parse_mode="HTML")
        return

    text = update.message.text.strip()
    if text and not text.startswith("/") and len(text) >= 2:
        allowed = await check_global_rate_limit(update.effective_user.id)
        if not allowed:
            return
        await ensure_user(update, context)
        from bot.services import tmdb_service
        from bot.utils.keyboards import search_results_kb
        try:
            data = await tmdb_service.search_movies(text)
            results = data.get("results", [])[:6]
            if results:
                await update.message.reply_text(
                    f"🔍 <b>Quick results:</b>\n{LINE}",
                    reply_markup=search_results_kb(results),
                    parse_mode="HTML",
                )
        except Exception:
            pass


async def post_init(application: Application) -> None:
    await init_db()
    from bot.services import ai_service
    ai_service._init_providers()
    await application.bot.set_my_commands(BOT_COMMANDS)
    logger.info("Bot initialized, database ready, commands set")


async def post_shutdown(application: Application) -> None:
    from bot.services import tmdb_service, youtube_service, streaming_service, ai_service
    await tmdb_service.close()
    await youtube_service.close()
    await streaming_service.close()
    await ai_service.close()
    await close_db()
    logger.info("Bot shutdown complete")


def _register_handlers(app: Application) -> None:
    handler_modules = [
        start, search, recommend, watchlist, watched,
        where, compare, explain, stats, alerts,
        random_handler, mood, inline, redeem, admin, contact, callbacks,
    ]
    for module in handler_modules:
        for handler in module.get_handlers():
            app.add_handler(handler)

    app.add_handler(
        CallbackQueryHandler(callbacks.unknown_callback),
        group=99,
    )

    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler),
        group=1,
    )


def _register_jobs(app: Application) -> None:
    jq = app.job_queue
    if not jq:
        logger.warning("Job queue not available")
        return

    jq.run_daily(
        daily_suggestion_job,
        time=time(hour=9, minute=0, tzinfo=timezone.utc),
        name="daily_suggestion",
    )

    jq.run_repeating(
        release_alerts_job,
        interval=3600 * 6,
        first=60,
        name="release_alerts",
    )

    jq.run_daily(
        subscription_expiry_job,
        time=time(hour=0, minute=30, tzinfo=timezone.utc),
        name="subscription_expiry",
    )

    logger.info("Scheduled jobs registered")


def build_application() -> Application:
    logging.basicConfig(
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        level=logging.INFO,
        stream=sys.stdout,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)

    defaults = Defaults(
        parse_mode="HTML",
        link_preview_options=LinkPreviewOptions(is_disabled=True)
    )

    builder = (
        ApplicationBuilder()
        .token(_s.BOT_TOKEN)
        .defaults(defaults)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .concurrent_updates(True)
        .connect_timeout(30.0)
        .read_timeout(30.0)
        .write_timeout(30.0)
        .pool_timeout(30.0)
    )

    app = builder.build()
    _register_handlers(app)
    _register_jobs(app)
    app.add_error_handler(error_handler)

    return app


def run_polling() -> None:
    app = build_application()
    logger.info("Starting CineBot in polling mode")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
        close_loop=False,
    )


def run_webhook() -> None:
    app = build_application()
    logger.info(f"Starting CineBot in webhook mode: {_s.webhook_full_url}")
    app.run_webhook(
        listen="0.0.0.0",
        port=_s.WEBHOOK_PORT,
        url_path=_s.WEBHOOK_PATH,
        webhook_url=_s.webhook_full_url,
        secret_token=_s.WEBHOOK_SECRET,
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
        close_loop=False,
    )