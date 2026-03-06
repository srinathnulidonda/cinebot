# bot/handlers/start.py
import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from bot.models.engine import get_session
from bot.models.user import UserRepo
from bot.middleware.subscription_check import ensure_user
from bot.utils.constants import MSG_WELCOME, MSG_HELP, MSG_ONBOARDING_GENRES, E_CROWN, E_CHECK
from bot.utils.keyboards import genre_select_kb
from bot.middleware.analytics import track_command

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    await track_command(update, context)
    async with get_session() as session:
        user = await UserRepo.get_by_telegram_id(session, update.effective_user.id)
    if user and not user.onboarding_completed:
        context.user_data["selected_genres"] = set()
        await update.message.reply_text(
            MSG_ONBOARDING_GENRES,
            reply_markup=genre_select_kb(),
            parse_mode="HTML",
        )
        return
    await update.message.reply_text(MSG_WELCOME, parse_mode="HTML")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    await track_command(update, context)
    await update.message.reply_text(MSG_HELP, parse_mode="HTML")


async def genre_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data
    selected = context.user_data.get("selected_genres", set())

    if data.startswith("genre_sel:"):
        genre_id = int(data.split(":")[1])
        if genre_id in selected:
            selected.discard(genre_id)
        else:
            selected.add(genre_id)
        context.user_data["selected_genres"] = selected
        await query.edit_message_reply_markup(reply_markup=genre_select_kb(selected))

    elif data == "genre_done":
        if len(selected) < 2:
            await query.answer("Please select at least 2 genres!", show_alert=True)
            return
        genre_names = []
        from bot.utils.constants import TMDB_GENRES
        for gid in selected:
            if gid in TMDB_GENRES:
                genre_names.append(TMDB_GENRES[gid])
        async with get_session() as session:
            await UserRepo.set_preferred_genres(session, update.effective_user.id, genre_names)
            await UserRepo.complete_onboarding(session, update.effective_user.id)
        context.user_data.pop("selected_genres", None)
        await query.edit_message_text(
            f"{E_CHECK} <b>Great choices!</b> Your preferences have been saved.\n\n{MSG_WELCOME}",
            parse_mode="HTML",
        )


async def pro_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    await track_command(update, context)
    async with get_session() as session:
        user = await UserRepo.get_by_telegram_id(session, update.effective_user.id)
    if not user:
        return

    from bot.middleware.rate_limiter import get_all_usage
    from bot.models.watchlist import WatchlistRepo
    usage = await get_all_usage(update.effective_user.id)
    async with get_session() as session:
        wl_count = await WatchlistRepo.count(session, user.id)

    if user.is_pro:
        expires = user.subscription_expires_at.strftime("%Y-%m-%d") if user.subscription_expires_at else "N/A"
        from datetime import datetime, timezone
        days_left = (user.subscription_expires_at - datetime.now(timezone.utc)).days if user.subscription_expires_at else 0
        text = (
            f"{E_CROWN} <b>Pro Subscription Active</b>\n\n"
            f"Plan: <b>PRO</b>\n"
            f"Expires: <b>{expires}</b>\n"
            f"Days left: <b>{max(0, days_left)}</b>\n\n"
            f"<b>Today's Usage:</b>\n"
            f"  🔍 Searches: {usage.get('search', 0)} (unlimited)\n"
            f"  🧠 Recommends: {usage.get('recommend', 0)} (unlimited)\n"
            f"  🤖 Explains: {usage.get('explain', 0)} (unlimited)\n"
            f"  📋 Watchlist: {wl_count} (unlimited)"
        )
    else:
        from bot.utils.constants import FREE_LIMITS
        text = (
            f"📋 <b>Free Plan</b>\n\n"
            f"<b>Today's Usage:</b>\n"
            f"  🔍 Searches: {usage.get('search', 0)}/{FREE_LIMITS['search']}\n"
            f"  🧠 Recommends: {usage.get('recommend', 0)}/{FREE_LIMITS['recommend']}\n"
            f"  🤖 Explains: {usage.get('explain', 0)}/{FREE_LIMITS['explain']}\n"
            f"  📋 Watchlist: {wl_count}/{FREE_LIMITS['watchlist']}\n\n"
            f"🔑 Use /redeem <code>KEY</code> to upgrade to Pro!\n"
            f"Contact an admin to purchase a key."
        )
    from bot.utils.keyboards import pro_upgrade_kb
    kb = None if user.is_pro else pro_upgrade_kb()
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)


def get_handlers() -> list:
    return [
        CommandHandler("start", start_command),
        CommandHandler("help", help_command),
        CommandHandler("pro", pro_command),
        CallbackQueryHandler(genre_select_callback, pattern=r"^genre_(sel|done)"),
    ]