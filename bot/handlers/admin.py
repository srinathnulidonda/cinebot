# bot/handlers/admin.py
import logging
import io
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from bot.middleware.admin_check import admin_only
from bot.middleware.subscription_check import ensure_user
from bot.middleware.analytics import track_command, get_daily_stats
from bot.services import key_service
from bot.models.engine import get_session
from bot.models.user import UserRepo
from bot.models.database import SubscriptionTier
from bot.utils.formatters import format_key_info, format_user_info
from bot.utils.keyboards import admin_dashboard_kb, pagination_kb
from bot.utils.key_generator import format_key_display, format_keys_file
from bot.utils.validators import validate_key_format, validate_key_type, validate_quantity, validate_batch_name
from bot.utils.constants import E_GEAR, E_KEY, E_CHECK, E_CROSS, E_CHART, E_PERSON, E_SEND, KEY_TYPES
from bot import CineBotError

logger = logging.getLogger(__name__)


@admin_only
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    await track_command(update, context)
    await update.message.reply_text(
        f"{E_GEAR} <b>Admin Dashboard</b>",
        reply_markup=admin_dashboard_kb(),
        parse_mode="HTML",
    )


@admin_only
async def genkey_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    args = context.args or []
    if not args:
        types = " | ".join(KEY_TYPES.keys())
        await update.message.reply_text(
            f"{E_KEY} <b>Generate License Key</b>\n\n"
            f"Usage: <code>/genkey TYPE [batch_name]</code>\n"
            f"Types: {types}\n"
            f"Example: <code>/genkey 1M promo_jan</code>",
            parse_mode="HTML",
        )
        return
    key_type = args[0].upper()
    if not validate_key_type(key_type):
        await update.message.reply_text(f"❌ Invalid type. Use: {' | '.join(KEY_TYPES.keys())}", parse_mode="HTML")
        return
    batch_name = validate_batch_name(args[1]) if len(args) > 1 else None
    try:
        key = await key_service.generate_single_key(update.effective_user.id, key_type, batch_name)
        type_info = KEY_TYPES[key_type]
        await update.message.reply_text(
            f"{E_CHECK} <b>Key Generated</b>\n\n"
            f"Key: {format_key_display(key)}\n"
            f"Type: {type_info['label']} ({type_info['days']} days)\n"
            f"Batch: {batch_name or 'N/A'}",
            parse_mode="HTML",
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}", parse_mode="HTML")


@admin_only
async def genkeys_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    args = context.args or []
    if len(args) < 3:
        await update.message.reply_text(
            f"{E_KEY} <b>Bulk Generate Keys</b>\n\n"
            f"Usage: <code>/genkeys TYPE QUANTITY BATCH_NAME</code>\n"
            f"Example: <code>/genkeys 1M 50 promo_jan</code>",
            parse_mode="HTML",
        )
        return
    key_type = args[0].upper()
    if not validate_key_type(key_type):
        await update.message.reply_text(f"❌ Invalid type.", parse_mode="HTML")
        return
    qty = validate_quantity(args[1])
    if not qty:
        await update.message.reply_text("❌ Quantity must be 1-500.", parse_mode="HTML")
        return
    batch_name = validate_batch_name(args[2])
    if not batch_name:
        await update.message.reply_text("❌ Invalid batch name.", parse_mode="HTML")
        return
    loading = await update.message.reply_text(f"⏳ Generating {qty} keys...", parse_mode="HTML")
    try:
        keys = await key_service.generate_bulk_keys(update.effective_user.id, key_type, qty, batch_name)
        file_content = format_keys_file(keys, key_type, batch_name)
        file_bytes = io.BytesIO(file_content.encode())
        file_bytes.name = f"keys_{batch_name}_{key_type}_{qty}.txt"
        await loading.edit_text(f"{E_CHECK} Generated {qty} keys. Sending file...", parse_mode="HTML")
        await update.message.reply_document(
            document=file_bytes,
            filename=file_bytes.name,
            caption=f"{E_KEY} {qty} keys | Type: {key_type} | Batch: {batch_name}",
        )
    except Exception as e:
        await loading.edit_text(f"❌ Error: {e}", parse_mode="HTML")


@admin_only
async def keyinfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    args = context.args or []
    if not args:
        await update.message.reply_text("Usage: <code>/keyinfo CINE-XXXX-XXXX-XXXX-XXXX</code>", parse_mode="HTML")
        return
    key_str = args[0].upper().strip()
    try:
        info = await key_service.get_key_info(key_str)
        if not info:
            await update.message.reply_text("❌ Key not found.", parse_mode="HTML")
            return
        lines = [
            f"{E_KEY} <b>Key Info</b>\n",
            f"Key: <code>{info['key']}</code>",
            f"Type: <b>{info['key_type']}</b> ({info['duration_days']} days)",
            f"Status: <b>{info['status']}</b>",
            f"Batch: {info['batch_name'] or 'N/A'}",
            f"Created: {info['created_at']}",
        ]
        if info.get("redeemed_at"):
            lines.append(f"Redeemed by: {info.get('redeemed_by_name', 'N/A')} ({info.get('redeemed_by_telegram_id', 'N/A')})")
            lines.append(f"Redeemed at: {info['redeemed_at']}")
        await update.message.reply_text("\n".join(lines), parse_mode="HTML")
    except CineBotError as e:
        await update.message.reply_text(e.user_message, parse_mode="HTML")


@admin_only
async def revokekey_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    args = context.args or []
    if not args:
        await update.message.reply_text("Usage: <code>/revokekey CINE-XXXX-XXXX-XXXX-XXXX</code>", parse_mode="HTML")
        return
    key_str = args[0].upper().strip()
    try:
        result = await key_service.revoke_key(update.effective_user.id, key_str)
        text = f"{E_CHECK} <b>Key Revoked</b>\n\nKey: <code>{result['key']}</code>"
        if result.get("downgraded_user"):
            text += f"\n⬇️ User <b>{result['downgraded_user']}</b> downgraded to FREE."
        await update.message.reply_text(text, parse_mode="HTML")
    except CineBotError as e:
        await update.message.reply_text(e.user_message, parse_mode="HTML")


@admin_only
async def listkeys_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    args = context.args or []
    status_filter = args[0].upper() if args else None
    page = int(args[1]) if len(args) > 1 else 1
    try:
        keys, total = await key_service.list_keys(status_filter, page=page, per_page=10)
        if not keys:
            await update.message.reply_text("No keys found.", parse_mode="HTML")
            return
        lines = [f"{E_KEY} <b>License Keys</b> ({total} total)\n"]
        for k in keys:
            status_emoji = {"UNUSED": "🟢", "USED": "🔵", "EXPIRED": "🟡", "REVOKED": "🔴"}.get(k.status.value, "⚪")
            lines.append(f"  {status_emoji} <code>{k.key}</code> | {k.key_type} | {k.status.value}")
        from math import ceil
        total_pages = max(1, ceil(total / 10))
        lines.append(f"\nPage {page}/{total_pages}")
        await update.message.reply_text("\n".join(lines), parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}", parse_mode="HTML")


@admin_only
async def userlookup_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    args = context.args or []
    if not args:
        await update.message.reply_text("Usage: <code>/userlookup TELEGRAM_ID</code>", parse_mode="HTML")
        return
    try:
        telegram_id = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid telegram ID.", parse_mode="HTML")
        return
    async with get_session() as session:
        user = await UserRepo.get_by_telegram_id(session, telegram_id)
    if not user:
        await update.message.reply_text("❌ User not found.", parse_mode="HTML")
        return
    text = format_user_info(user)
    await update.message.reply_text(text, parse_mode="HTML")


@admin_only
async def giftkey_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text(
            "Usage: <code>/giftkey TELEGRAM_ID TYPE</code>\n"
            "Example: <code>/giftkey 123456789 1M</code>",
            parse_mode="HTML",
        )
        return
    try:
        target_id = int(args[0])
        key_type = args[1].upper()
        result = await key_service.gift_key(update.effective_user.id, target_id, key_type)
        text = (
            f"🎁 <b>Key Gifted!</b>\n\n"
            f"Key: <code>{result['key']}</code>\n"
            f"Duration: {result['duration']}\n"
            f"User: {result['user']} ({result['telegram_id']})\n\n"
            f"The user has been auto-upgraded to Pro!"
        )
        await update.message.reply_text(text, parse_mode="HTML")
        try:
            await context.bot.send_message(
                target_id,
                f"🎁 <b>You've been gifted Pro!</b>\n\n"
                f"Duration: {result['duration']}\n"
                f"Enjoy unlimited access! ✨",
                parse_mode="HTML",
            )
        except Exception:
            pass
    except ValueError as e:
        await update.message.reply_text(f"❌ {e}", parse_mode="HTML")
    except CineBotError as e:
        await update.message.reply_text(e.user_message, parse_mode="HTML")


@admin_only
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    args = context.args or []
    if not args:
        await update.message.reply_text(
            f"{E_SEND} <b>Broadcast Message</b>\n\n"
            f"Usage: <code>/broadcast [all|pro] Your message here</code>\n"
            f"Example: <code>/broadcast all 🎉 New features available!</code>",
            parse_mode="HTML",
        )
        return
    target = args[0].lower()
    if target not in ("all", "pro"):
        message_text = " ".join(args)
        target = "all"
    else:
        message_text = " ".join(args[1:])
    if not message_text:
        await update.message.reply_text("❌ No message provided.", parse_mode="HTML")
        return
    loading = await update.message.reply_text("📡 Broadcasting...", parse_mode="HTML")
    async with get_session() as session:
        if target == "pro":
            user_ids = await UserRepo.get_pro_user_ids(session)
        else:
            user_ids = await UserRepo.get_all_user_ids(session)
    sent, failed = 0, 0
    for uid in user_ids:
        try:
            await context.bot.send_message(uid, message_text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1
    await loading.edit_text(
        f"{E_CHECK} <b>Broadcast Complete</b>\n\n"
        f"Target: {target}\n"
        f"Sent: {sent}\nFailed: {failed}",
        parse_mode="HTML",
    )


@admin_only
async def admin_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    async with get_session() as session:
        total_users = await UserRepo.get_user_count(session)
        pro_users = await UserRepo.get_pro_user_count(session)
    key_stats = await key_service.get_key_stats()
    daily = await get_daily_stats()
    text = (
        f"{E_CHART} <b>Admin Stats</b>\n\n"
        f"<b>Users:</b>\n"
        f"  👥 Total: {total_users}\n"
        f"  👑 Pro: {pro_users}\n\n"
        f"<b>Keys:</b>\n"
        f"  🟢 Unused: {key_stats.get('UNUSED', 0)}\n"
        f"  🔵 Used: {key_stats.get('USED', 0)}\n"
        f"  🟡 Expired: {key_stats.get('EXPIRED', 0)}\n"
        f"  🔴 Revoked: {key_stats.get('REVOKED', 0)}\n"
        f"  📊 Total: {key_stats.get('TOTAL', 0)}\n\n"
        f"<b>Today:</b>\n"
        f"  📨 Commands: {daily.get('total_commands', 0)}\n"
        f"  👤 Active users: {daily.get('unique_users', 0)}"
    )
    await query.edit_message_text(text, reply_markup=admin_dashboard_kb(), parse_mode="HTML")


async def admin_dashboard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data = query.data
    await query.answer()

    if data == "adm:stats":
        await admin_stats_callback(update, context)
    elif data == "adm:genkey":
        await query.edit_message_text(
            f"{E_KEY} Use command:\n<code>/genkey TYPE [batch_name]</code>\n\nTypes: {' | '.join(KEY_TYPES.keys())}",
            parse_mode="HTML",
        )
    elif data == "adm:bulkkeys":
        await query.edit_message_text(
            f"{E_KEY} Use command:\n<code>/genkeys TYPE QUANTITY BATCH_NAME</code>",
            parse_mode="HTML",
        )
    elif data == "adm:keyinfo":
        await query.edit_message_text(
            f"{E_KEY} Use command:\n<code>/keyinfo CINE-XXXX-XXXX-XXXX-XXXX</code>",
            parse_mode="HTML",
        )
    elif data == "adm:userlookup":
        await query.edit_message_text(
            f"{E_PERSON} Use command:\n<code>/userlookup TELEGRAM_ID</code>",
            parse_mode="HTML",
        )
    elif data == "adm:broadcast":
        await query.edit_message_text(
            f"{E_SEND} Use command:\n<code>/broadcast [all|pro] message</code>",
            parse_mode="HTML",
        )
    elif data == "adm:revoke":
        await query.edit_message_text(
            f"{E_KEY} Use command:\n<code>/revokekey CINE-XXXX-XXXX-XXXX-XXXX</code>",
            parse_mode="HTML",
        )
    elif data.startswith("adm:listkeys"):
        await query.edit_message_text(
            f"{E_KEY} Use command:\n<code>/listkeys [UNUSED|USED|EXPIRED|REVOKED] [page]</code>",
            parse_mode="HTML",
        )


def get_handlers() -> list:
    return [
        CommandHandler("admin", admin_command),
        CommandHandler("genkey", genkey_command),
        CommandHandler("genkeys", genkeys_command),
        CommandHandler("keyinfo", keyinfo_command),
        CommandHandler("revokekey", revokekey_command),
        CommandHandler("listkeys", listkeys_command),
        CommandHandler("userlookup", userlookup_command),
        CommandHandler("giftkey", giftkey_command),
        CommandHandler("broadcast", broadcast_command),
        CallbackQueryHandler(admin_dashboard_callback, pattern=r"^adm:"),
    ]