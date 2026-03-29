import logging
import io
from math import ceil
from telegram import Update, Contact
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from bot.middleware.admin_check import admin_only
from bot.middleware.subscription_check import ensure_user
from bot.middleware.analytics import track_command, get_daily_stats
from bot.services import key_service
from bot.services import ai_service
from bot.services import backend_health
from bot.models.engine import get_session
from bot.models.user import UserRepo
from bot.models.database import SubscriptionTier
from bot.utils.formatters import (
    format_key_info, format_user_info, format_admin_stats, format_backend_status,
    progress_bar, section,
)
from bot.utils.keyboards import admin_dashboard_kb, pagination_kb
from bot.utils.key_generator import format_key_display, format_keys_file
from bot.utils.validators import validate_key_format, validate_key_type, validate_quantity, validate_batch_name, sanitize_html
from bot.utils.constants import (
    E_SHIELD, E_KEY, E_CHECK, E_CROSS, E_CHART, E_PERSON, E_SEND,
    E_ROBOT, E_CROWN, E_SERVER, KEY_TYPES, LINE, LINE_LIGHT, BADGE_PRO,
)
from bot import CineBotError

logger = logging.getLogger(__name__)


@admin_only
async def adduser_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    args = context.args or []

    if len(args) < 2:
        await update.message.reply_text(
            f"👤 <b>ADD USER</b>\n"
            f"{LINE}\n\n"
            f"Usage:\n"
            f"<code>/adduser TELEGRAM_ID DisplayName</code>\n"
            f"<code>/adduser TELEGRAM_ID DisplayName admin</code>\n\n"
            f"💡 Examples:\n"
            f"<code>/adduser 123456789 John</code>\n"
            f"<code>/adduser 123456789 John admin</code>\n\n"
            f"📌 All users are added as <b>FREE</b> plan\n"
            f"📌 Add <code>admin</code> at end to make admin",
            parse_mode="HTML",
        )
        return

    try:
        telegram_id = int(args[0])
    except ValueError:
        await update.message.reply_text(
            f"{E_CROSS} Invalid Telegram ID. Must be a number.",
            parse_mode="HTML",
        )
        return

    is_admin = args[-1].lower() == "admin"
    
    if is_admin:
        display_name = " ".join(args[1:-1]) or f"User_{telegram_id}"
    else:
        display_name = " ".join(args[1:]) or f"User_{telegram_id}"

    display_name = display_name.strip()
    if len(display_name) > 200:
        display_name = display_name[:200]

    async with get_session() as session:
        existing = await UserRepo.get_by_telegram_id(session, telegram_id)

    if existing:
        admin_badge = " 👑" if existing.is_admin else ""
        await update.message.reply_text(
            f"ℹ️ <b>User already exists</b>\n"
            f"{LINE}\n\n"
            f"🆔 <code>{telegram_id}</code>\n"
            f"👤 {sanitize_html(existing.display_name)}{admin_badge}\n"
            f"📋 Plan: <b>{existing.subscription_tier.value}</b>\n\n"
            f"💡 Use /userlookup {telegram_id} for full info",
            parse_mode="HTML",
        )
        return

    try:
        async with get_session() as session:
            from bot.models.database import User
            new_user = User(
                telegram_id=telegram_id,
                display_name=display_name,
                username=None,
                subscription_tier=SubscriptionTier.FREE,
                subscription_expires_at=None,
                is_admin=is_admin,
                onboarding_completed=True,
            )
            session.add(new_user)

        admin_badge = " 👑 Admin" if is_admin else ""
        await update.message.reply_text(
            f"{E_CHECK} <b>USER ADDED</b>\n"
            f"{LINE}\n\n"
            f"🆔 <code>{telegram_id}</code>\n"
            f"👤 {sanitize_html(display_name)}{admin_badge}\n"
            f"📋 Plan: <b>FREE</b>\n"
            f"🔒 No subscription\n\n"
            f"✅ User can now use /start to begin!",
            parse_mode="HTML",
        )
        logger.info(f"Admin {update.effective_user.id} added user {telegram_id} ({display_name})")

    except Exception as e:
        logger.error(f"Failed to add user {telegram_id}: {e}")
        await update.message.reply_text(
            f"{E_CROSS} Failed to add user: {e}",
            parse_mode="HTML",
        )


@admin_only
async def addusers_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)

    if not context.args:
        await update.message.reply_text(
            f"👥 <b>BULK ADD USERS</b>\n"
            f"{LINE}\n\n"
            f"Usage:\n"
            f"<code>/addusers\n"
            f"123456789 John\n"
            f"987654321 Jane\n"
            f"555555555 Alex admin</code>\n\n"
            f"📌 One user per line: <code>ID Name</code>\n"
            f"📌 Add <code>admin</code> at end for admin\n"
            f"📌 All added as <b>FREE</b> plan",
            parse_mode="HTML",
        )
        return

    full_text = update.message.text
    lines_text = full_text.split("\n")

    users_to_add = []
    first_line_args = " ".join(context.args)

    if first_line_args.strip():
        lines_text[0] = first_line_args

    for line in lines_text:
        line = line.strip()
        if not line or line.startswith("/"):
            continue

        parts = line.split()
        if len(parts) < 2:
            continue

        try:
            tid = int(parts[0])
        except ValueError:
            continue

        is_admin = parts[-1].lower() == "admin"
        if is_admin:
            name = " ".join(parts[1:-1]) or f"User_{tid}"
        else:
            name = " ".join(parts[1:]) or f"User_{tid}"

        users_to_add.append({
            "telegram_id": tid,
            "display_name": name.strip()[:200],
            "is_admin": is_admin,
        })

    if not users_to_add:
        await update.message.reply_text(
            f"{E_CROSS} No valid users found.\n\n"
            f"Format: <code>TELEGRAM_ID DisplayName</code>",
            parse_mode="HTML",
        )
        return

    loading = await update.message.reply_text(
        f"⏳ Adding {len(users_to_add)} users...",
        parse_mode="HTML",
    )

    added, skipped, failed = 0, 0, 0
    results = []

    for user_data in users_to_add:
        tid = user_data["telegram_id"]
        name = user_data["display_name"]
        is_admin = user_data["is_admin"]

        try:
            async with get_session() as session:
                existing = await UserRepo.get_by_telegram_id(session, tid)

            if existing:
                results.append(f"  ⏭️ {tid} — {sanitize_html(name)} (exists)")
                skipped += 1
                continue

            async with get_session() as session:
                from bot.models.database import User
                new_user = User(
                    telegram_id=tid,
                    display_name=name,
                    username=None,
                    subscription_tier=SubscriptionTier.FREE,
                    subscription_expires_at=None,
                    is_admin=is_admin,
                    onboarding_completed=True,
                )
                session.add(new_user)

            badge = " 👑" if is_admin else ""
            results.append(f"  ✅ {tid} — {sanitize_html(name)}{badge}")
            added += 1

        except Exception as e:
            results.append(f"  ❌ {tid} — {sanitize_html(name)} ({e})")
            failed += 1

    result_text = "\n".join(results)
    await loading.edit_text(
        f"👥 <b>BULK ADD RESULTS</b>\n"
        f"{LINE}\n\n"
        f"{result_text}\n\n"
        f"{LINE_LIGHT}\n"
        f"✅ Added: {added}\n"
        f"⏭️ Skipped: {skipped}\n"
        f"❌ Failed: {failed}",
        parse_mode="HTML",
    )
    logger.info(f"Admin {update.effective_user.id} bulk added users: {added} added, {skipped} skipped, {failed} failed")


@admin_only
async def addcontact_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    context.user_data["collecting_contacts"] = True
    context.user_data["collected_contacts"] = []

    await update.message.reply_text(
        f"📱 <b>ADD USERS FROM CONTACTS</b>\n"
        f"{LINE}\n\n"
        f"Now share contacts from your phone:\n\n"
        f"📎 Tap the attachment icon\n"
        f"👤 Select <b>Contact</b>\n"
        f"📤 Send one or more contacts\n\n"
        f"When done, send /donecontacts to add them all.\n"
        f"Send /cancelcontacts to cancel.\n\n"
        f"📌 All contacts will be added as <b>FREE</b> plan\n"
        f"⚠️ Only contacts with Telegram IDs can be added",
        parse_mode="HTML",
    )


async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.contact:
        return

    user_id = update.effective_user.id
    from bot.config import get_settings
    _s = get_settings()

    if user_id not in _s.ADMIN_IDS:
        return

    if not context.user_data.get("collecting_contacts"):
        return

    contact: Contact = update.message.contact
    telegram_id = contact.user_id
    first_name = contact.first_name or ""
    last_name = contact.last_name or ""
    phone = contact.phone_number or ""
    display_name = f"{first_name} {last_name}".strip() or f"User_{telegram_id or phone}"

    if not telegram_id:
        await update.message.reply_text(
            f"⚠️ <b>{sanitize_html(display_name)}</b> ({phone})\n"
            f"No Telegram ID found — skipped.\n\n"
            f"💡 This contact may not have Telegram.",
            parse_mode="HTML",
        )
        return

    collected = context.user_data.get("collected_contacts", [])

    if any(c["telegram_id"] == telegram_id for c in collected):
        await update.message.reply_text(
            f"⏭️ <b>{sanitize_html(display_name)}</b> already in queue.",
            parse_mode="HTML",
        )
        return

    collected.append({
        "telegram_id": telegram_id,
        "display_name": display_name,
        "phone": phone,
    })
    context.user_data["collected_contacts"] = collected

    await update.message.reply_text(
        f"✅ <b>Contact #{len(collected)}</b>\n"
        f"👤 {sanitize_html(display_name)}\n"
        f"🆔 <code>{telegram_id}</code>\n"
        f"📱 {phone}\n\n"
        f"📥 {len(collected)} contact{'s' if len(collected) > 1 else ''} queued\n"
        f"Send more or /donecontacts to add them all.",
        parse_mode="HTML",
    )


@admin_only
async def done_contacts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)

    if not context.user_data.get("collecting_contacts"):
        await update.message.reply_text(
            f"❌ No contact collection in progress.\n\n"
            f"Use /addcontact to start.",
            parse_mode="HTML",
        )
        return

    collected = context.user_data.get("collected_contacts", [])

    context.user_data.pop("collecting_contacts", None)
    context.user_data.pop("collected_contacts", None)

    if not collected:
        await update.message.reply_text(
            f"❌ No contacts to add.\n\n"
            f"Use /addcontact and share contacts first.",
            parse_mode="HTML",
        )
        return

    loading = await update.message.reply_text(
        f"⏳ Adding {len(collected)} contacts...",
        parse_mode="HTML",
    )

    added, skipped, failed = 0, 0, 0
    results = []

    for contact_data in collected:
        tid = contact_data["telegram_id"]
        name = contact_data["display_name"]
        phone = contact_data["phone"]

        try:
            async with get_session() as session:
                existing = await UserRepo.get_by_telegram_id(session, tid)

            if existing:
                results.append(f"  ⏭️ {sanitize_html(name)} — already exists")
                skipped += 1
                continue

            async with get_session() as session:
                from bot.models.database import User
                new_user = User(
                    telegram_id=tid,
                    display_name=name,
                    username=None,
                    subscription_tier=SubscriptionTier.FREE,
                    subscription_expires_at=None,
                    is_admin=False,
                    onboarding_completed=True,
                )
                session.add(new_user)

            results.append(f"  ✅ {sanitize_html(name)} ({tid})")
            added += 1

        except Exception as e:
            results.append(f"  ❌ {sanitize_html(name)} — {e}")
            failed += 1

    result_text = "\n".join(results)
    await loading.edit_text(
        f"📱 <b>CONTACTS ADDED</b>\n"
        f"{LINE}\n\n"
        f"{result_text}\n\n"
        f"{LINE_LIGHT}\n"
        f"✅ Added: {added}\n"
        f"⏭️ Already existed: {skipped}\n"
        f"❌ Failed: {failed}\n\n"
        f"📌 All added as FREE plan",
        parse_mode="HTML",
    )
    logger.info(
        f"Admin {update.effective_user.id} added {added} users from contacts "
        f"(skipped={skipped}, failed={failed})"
    )


@admin_only
async def cancel_contacts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)

    collected = len(context.user_data.get("collected_contacts", []))
    context.user_data.pop("collecting_contacts", None)
    context.user_data.pop("collected_contacts", None)

    await update.message.reply_text(
        f"❌ <b>Contact collection cancelled.</b>\n\n"
        f"🗑️ {collected} queued contact{'s' if collected != 1 else ''} discarded.",
        parse_mode="HTML",
    )


@admin_only
async def removeuser_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    args = context.args or []

    if not args:
        await update.message.reply_text(
            f"🗑️ <b>REMOVE USER</b>\n"
            f"{LINE}\n\n"
            f"Usage: <code>/removeuser TELEGRAM_ID</code>\n\n"
            f"⚠️ This deletes user and all their data!",
            parse_mode="HTML",
        )
        return

    try:
        telegram_id = int(args[0])
    except ValueError:
        await update.message.reply_text(
            f"{E_CROSS} Invalid Telegram ID.",
            parse_mode="HTML",
        )
        return

    if telegram_id == update.effective_user.id:
        await update.message.reply_text(
            f"{E_CROSS} <b>You cannot delete yourself!</b>\n\n"
            f"🛡️ Self-deletion is blocked for safety.",
            parse_mode="HTML",
        )
        return

    from bot.config import get_settings
    _s = get_settings()
    if telegram_id in _s.ADMIN_IDS:
        await update.message.reply_text(
            f"{E_CROSS} <b>Cannot delete an admin!</b>\n\n"
            f"🛡️ Remove them from ADMIN_IDS first.",
            parse_mode="HTML",
        )
        return

    async with get_session() as session:
        user = await UserRepo.get_by_telegram_id(session, telegram_id)
        if not user:
            await update.message.reply_text(
                f"{E_CROSS} User <code>{telegram_id}</code> not found.",
                parse_mode="HTML",
            )
            return

        if user.is_admin:
            await update.message.reply_text(
                f"{E_CROSS} <b>Cannot delete admin user!</b>\n\n"
                f"👤 {sanitize_html(user.display_name)}\n"
                f"🛡️ Revoke admin access first.",
                parse_mode="HTML",
            )
            return

        display_name = sanitize_html(user.display_name)

        try:
            from sqlalchemy import text as sa_text
            await session.execute(
                sa_text("DELETE FROM watchlist WHERE user_id = :uid"),
                {"uid": user.id},
            )
            await session.execute(
                sa_text("DELETE FROM watched_movies WHERE user_id = :uid"),
                {"uid": user.id},
            )
            await session.execute(
                sa_text("DELETE FROM release_alerts WHERE user_id = :uid"),
                {"uid": user.id},
            )
            await session.execute(
                sa_text("DELETE FROM user_preferences WHERE user_id = :uid"),
                {"uid": user.id},
            )
            await session.delete(user)
        except Exception:
            await session.delete(user)

    await update.message.reply_text(
        f"🗑️ <b>USER REMOVED</b>\n"
        f"{LINE}\n\n"
        f"🆔 <code>{telegram_id}</code>\n"
        f"👤 {display_name}\n\n"
        f"✅ User and all data deleted.",
        parse_mode="HTML",
    )
    logger.info(f"Admin {update.effective_user.id} removed user {telegram_id}")


@admin_only
async def allusers_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    await track_command(update, context)

    page = int(context.args[0]) if context.args else 1
    per_page = 15

    async with get_session() as session:
        total = await UserRepo.get_user_count(session)
        from sqlalchemy import select, func
        from bot.models.database import User

        offset = (page - 1) * per_page
        result = await session.execute(
            select(User)
            .order_by(User.created_at.desc())
            .offset(offset)
            .limit(per_page)
        )
        users = result.scalars().all()

    if not users:
        await update.message.reply_text(
            f"👥 <b>No users found</b>",
            parse_mode="HTML",
        )
        return

    total_pages = max(1, ceil(total / per_page))
    lines = [
        f"👥 <b>ALL USERS</b> ({total})",
        LINE,
        "",
    ]

    for u in users:
        admin_badge = "👑" if u.is_admin else "  "
        tier = "PRO" if u.subscription_tier.value == "PRO" else "FREE"
        tier_dot = "🟢" if tier == "PRO" else "⚪"
        name = sanitize_html(u.display_name)[:20]
        username = f"@{u.username}" if u.username else ""

        lines.append(
            f"  {admin_badge} {tier_dot} <code>{u.telegram_id}</code> · "
            f"{name} {username}"
        )

    lines.append(f"\n📄 Page {page}/{total_pages}")

    if page < total_pages:
        lines.append(f"\n💡 <code>/allusers {page + 1}</code> for next page")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


@admin_only
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    await track_command(update, context)
    await update.message.reply_text(
        f"{E_SHIELD} <b>ADMIN DASHBOARD</b>\n"
        f"{LINE}",
        reply_markup=admin_dashboard_kb(),
        parse_mode="HTML",
    )


@admin_only
async def genkey_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    args = context.args or []
    if not args:
        types = " · ".join(KEY_TYPES.keys())
        await update.message.reply_text(
            f"{E_KEY} <b>GENERATE KEY</b>\n"
            f"{LINE}\n\n"
            f"Usage: <code>/genkey TYPE [batch]</code>\n"
            f"Types: {types}\n\n"
            f"💡 <code>/genkey 1M promo_jan</code>",
            parse_mode="HTML",
        )
        return
    key_type = args[0].upper()
    if not validate_key_type(key_type):
        await update.message.reply_text(
            f"❌ Invalid type. Use: {' · '.join(KEY_TYPES.keys())}", parse_mode="HTML",
        )
        return
    batch_name = validate_batch_name(args[1]) if len(args) > 1 else None
    try:
        key = await key_service.generate_single_key(update.effective_user.id, key_type, batch_name)
        type_info = KEY_TYPES[key_type]
        await update.message.reply_text(
            f"{E_CHECK} <b>KEY GENERATED</b>\n"
            f"{LINE}\n\n"
            f"Key: {format_key_display(key)}\n"
            f"Type: <b>{type_info['label']}</b> ({type_info['days']}d)\n"
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
            f"{E_KEY} <b>BULK GENERATE</b>\n"
            f"{LINE}\n\n"
            f"Usage: <code>/genkeys TYPE QTY BATCH</code>\n\n"
            f"💡 <code>/genkeys 1M 50 promo_jan</code>",
            parse_mode="HTML",
        )
        return
    key_type = args[0].upper()
    if not validate_key_type(key_type):
        await update.message.reply_text("❌ Invalid type.", parse_mode="HTML")
        return
    qty = validate_quantity(args[1])
    if not qty:
        await update.message.reply_text("❌ Quantity: 1–500", parse_mode="HTML")
        return
    batch_name = validate_batch_name(args[2])
    if not batch_name:
        await update.message.reply_text("❌ Invalid batch name.", parse_mode="HTML")
        return
    loading = await update.message.reply_text(
        f"⏳ Generating {qty} keys...", parse_mode="HTML",
    )
    try:
        keys = await key_service.generate_bulk_keys(update.effective_user.id, key_type, qty, batch_name)
        file_content = format_keys_file(keys, key_type, batch_name)
        file_bytes = io.BytesIO(file_content.encode())
        file_bytes.name = f"keys_{batch_name}_{key_type}_{qty}.txt"
        await loading.edit_text(
            f"{E_CHECK} <b>{qty} keys generated!</b>", parse_mode="HTML",
        )
        await update.message.reply_document(
            document=file_bytes,
            filename=file_bytes.name,
            caption=f"{E_KEY} {qty} keys · {key_type} · {batch_name}",
        )
    except Exception as e:
        await loading.edit_text(f"❌ Error: {e}", parse_mode="HTML")


@admin_only
async def keyinfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    args = context.args or []
    if not args:
        await update.message.reply_text(
            f"Usage: <code>/keyinfo CINE-XXXX-XXXX-XXXX-XXXX</code>", parse_mode="HTML",
        )
        return
    key_str = args[0].upper().strip()
    try:
        info = await key_service.get_key_info(key_str)
        if not info:
            await update.message.reply_text("❌ Key not found 🙈", parse_mode="HTML")
            return
        status_dot = {
            "UNUSED": "🟢", "USED": "🔵", "EXPIRED": "🟡", "REVOKED": "🔴",
        }.get(info["status"], "⚪")
        lines = [
            f"{E_KEY} <b>KEY INFO</b>",
            LINE,
            "",
            f"Key: <code>{info['key']}</code>",
            f"Type: <b>{info['key_type']}</b> ({info['duration_days']}d)",
            f"Status: {status_dot} <b>{info['status']}</b>",
            f"Batch: {info['batch_name'] or 'N/A'}",
            f"Created: {info['created_at']}",
        ]
        if info.get("redeemed_at"):
            lines.append(LINE_LIGHT)
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
        await update.message.reply_text(
            f"Usage: <code>/revokekey CINE-XXXX-XXXX-XXXX-XXXX</code>", parse_mode="HTML",
        )
        return
    key_str = args[0].upper().strip()
    try:
        result = await key_service.revoke_key(update.effective_user.id, key_str)
        text = (
            f"{E_CHECK} <b>KEY REVOKED</b>\n"
            f"{LINE}\n\n"
            f"Key: <code>{result['key']}</code>"
        )
        if result.get("downgraded_user"):
            text += f"\n⬇️ <b>{result['downgraded_user']}</b> → FREE"
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
        lines = [
            f"{E_KEY} <b>LICENSE KEYS</b> ({total})",
            LINE,
            "",
        ]
        for k in keys:
            dot = {"UNUSED": "🟢", "USED": "🔵", "EXPIRED": "🟡", "REVOKED": "🔴"}.get(k.status.value, "⚪")
            lines.append(f"  {dot} <code>{k.key}</code> · {k.key_type} · {k.status.value}")
        total_pages = max(1, ceil(total / 10))
        lines.append(f"\n📄 Page {page}/{total_pages}")
        await update.message.reply_text("\n".join(lines), parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}", parse_mode="HTML")


@admin_only
async def userlookup_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    args = context.args or []
    if not args:
        await update.message.reply_text(
            f"Usage: <code>/userlookup TELEGRAM_ID</code>", parse_mode="HTML",
        )
        return
    try:
        telegram_id = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid ID.", parse_mode="HTML")
        return
    async with get_session() as session:
        user = await UserRepo.get_by_telegram_id(session, telegram_id)
    if not user:
        await update.message.reply_text("❌ User not found 🙈", parse_mode="HTML")
        return
    await update.message.reply_text(format_user_info(user), parse_mode="HTML")


@admin_only
async def giftkey_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text(
            f"🎁 <b>GIFT PRO</b>\n"
            f"{LINE}\n\n"
            f"Usage: <code>/giftkey TELEGRAM_ID TYPE</code>\n\n"
            f"💡 <code>/giftkey 123456789 1M</code>",
            parse_mode="HTML",
        )
        return
    try:
        target_id = int(args[0])
        key_type = args[1].upper()
        result = await key_service.gift_key(update.effective_user.id, target_id, key_type)
        text = (
            f"🎁 <b>PRO GIFTED!</b>\n"
            f"{LINE}\n\n"
            f"Key: <code>{result['key']}</code>\n"
            f"Duration: <b>{result['duration']}</b>\n"
            f"User: {result['user']} ({result['telegram_id']})\n\n"
            f"{E_CHECK} Auto-upgraded to Pro!"
        )
        await update.message.reply_text(text, parse_mode="HTML")
        try:
            await context.bot.send_message(
                target_id,
                f"🎁 <b>You've been gifted Pro!</b>\n"
                f"{LINE}\n\n"
                f"Duration: <b>{result['duration']}</b>\n"
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
            f"{E_SEND} <b>BROADCAST</b>\n"
            f"{LINE}\n\n"
            f"Usage: <code>/broadcast [all|pro] message</code>\n\n"
            f"💡 <code>/broadcast all 🎉 New features!</code>",
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
        f"{E_CHECK} <b>BROADCAST COMPLETE</b>\n"
        f"{LINE}\n\n"
        f"Target: <b>{target}</b>\n"
        f"✅ Sent: {sent}\n"
        f"❌ Failed: {failed}",
        parse_mode="HTML",
    )


@admin_only
async def aistatus_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    await track_command(update, context)
    status = await ai_service.get_status()
    lines = [
        f"{E_ROBOT} <b>AI STATUS</b>",
        LINE,
        "",
    ]
    for name, info in status.items():
        if name == "_total":
            continue
        usage = info["usage"]
        limit = info["limit"]
        remaining = info["remaining"]
        bar = progress_bar(remaining, limit, 8)
        if info["exhausted"]:
            dot = "🔴"
        elif remaining < limit * 0.1:
            dot = "🟡"
        else:
            dot = "🟢"
        lines.append(f"  {dot} <b>{name}</b>")
        lines.append(f"     {bar} {usage}/{limit}")
    total = status.get("_total", {})
    pct = (total.get("remaining", 0) / max(total.get("limit", 1), 1)) * 100
    lines.append("")
    lines.append(LINE_LIGHT)
    lines.append(f"⚡ Capacity: {progress_bar(int(pct), 100, 10)} {pct:.0f}%")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


@admin_only
async def backend_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user(update, context)
    await track_command(update, context)
    loading = await update.message.reply_text(f"{E_SERVER} Checking backend services...", parse_mode="HTML")
    try:
        health = await backend_health.get_full_health()
        text = format_backend_status(health)
        await loading.edit_text(text, parse_mode="HTML")
    except Exception as e:
        await loading.edit_text(f"❌ Error: {e}", parse_mode="HTML")


@admin_only
async def admin_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    async with get_session() as session:
        total_users = await UserRepo.get_user_count(session)
        pro_users = await UserRepo.get_pro_user_count(session)
    key_stats = await key_service.get_key_stats()
    daily = await get_daily_stats()
    ai_status = await ai_service.get_status()
    backend = await backend_health.get_full_health()
    text = format_admin_stats(total_users, pro_users, key_stats, daily, ai_status, backend)
    await query.edit_message_text(text, reply_markup=admin_dashboard_kb(), parse_mode="HTML")


async def admin_dashboard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data = query.data
    await query.answer()

    if data == "adm:stats":
        await admin_stats_callback(update, context)
    elif data == "adm:genkey":
        await query.edit_message_text(
            f"{E_KEY} <b>GENERATE KEY</b>\n{LINE}\n\n"
            f"<code>/genkey TYPE [batch]</code>\n\nTypes: {' · '.join(KEY_TYPES.keys())}",
            parse_mode="HTML",
        )
    elif data == "adm:bulkkeys":
        await query.edit_message_text(
            f"{E_KEY} <b>BULK GENERATE</b>\n{LINE}\n\n"
            f"<code>/genkeys TYPE QTY BATCH</code>",
            parse_mode="HTML",
        )
    elif data == "adm:keyinfo":
        await query.edit_message_text(
            f"{E_KEY} <b>KEY LOOKUP</b>\n{LINE}\n\n"
            f"<code>/keyinfo CINE-XXXX-XXXX-XXXX-XXXX</code>",
            parse_mode="HTML",
        )
    elif data == "adm:userlookup":
        await query.edit_message_text(
            f"{E_PERSON} <b>USER LOOKUP</b>\n{LINE}\n\n"
            f"<code>/userlookup TELEGRAM_ID</code>",
            parse_mode="HTML",
        )
    elif data == "adm:broadcast":
        await query.edit_message_text(
            f"{E_SEND} <b>BROADCAST</b>\n{LINE}\n\n"
            f"<code>/broadcast [all|pro] message</code>",
            parse_mode="HTML",
        )
    elif data == "adm:revoke":
        await query.edit_message_text(
            f"{E_KEY} <b>REVOKE KEY</b>\n{LINE}\n\n"
            f"<code>/revokekey CINE-XXXX-XXXX-XXXX-XXXX</code>",
            parse_mode="HTML",
        )
    elif data.startswith("adm:listkeys"):
        await query.edit_message_text(
            f"{E_KEY} <b>LIST KEYS</b>\n{LINE}\n\n"
            f"<code>/listkeys [UNUSED|USED|EXPIRED|REVOKED] [page]</code>",
            parse_mode="HTML",
        )
    elif data == "adm:aistatus":
        await query.edit_message_text(
            f"{E_ROBOT} <b>AI STATUS</b>\n{LINE}\n\n"
            f"Use <code>/aistatus</code> for full report",
            parse_mode="HTML",
        )
    elif data == "adm:backend":
        await query.edit_message_text(
            f"{E_SERVER} <b>BACKEND STATUS</b>\n{LINE}\n\n"
            f"Use <code>/backend</code> for full report",
            parse_mode="HTML",
        )


def get_handlers() -> list:
    return [
        CommandHandler("admin", admin_command),
        CommandHandler("adduser", adduser_command),
        CommandHandler("addusers", addusers_command),
        CommandHandler("addcontact", addcontact_command),
        CommandHandler("donecontacts", done_contacts_command),
        CommandHandler("cancelcontacts", cancel_contacts_command),
        CommandHandler("removeuser", removeuser_command),
        CommandHandler("allusers", allusers_command),
        CommandHandler("genkey", genkey_command),
        CommandHandler("genkeys", genkeys_command),
        CommandHandler("keyinfo", keyinfo_command),
        CommandHandler("revokekey", revokekey_command),
        CommandHandler("listkeys", listkeys_command),
        CommandHandler("userlookup", userlookup_command),
        CommandHandler("giftkey", giftkey_command),
        CommandHandler("broadcast", broadcast_command),
        CommandHandler("aistatus", aistatus_command),
        CommandHandler("backend", backend_command),
        CallbackQueryHandler(admin_dashboard_callback, pattern=r"^adm:"),
        MessageHandler(filters.CONTACT, contact_handler),
    ]