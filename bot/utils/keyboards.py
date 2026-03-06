# bot/utils/keyboards.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from bot.utils.constants import TMDB_GENRES, MOOD_MAP, KEY_TYPES, E_ARROW_L, E_ARROW_R


def movie_detail_kb(movie_id: int, in_watchlist: bool = False) -> InlineKeyboardMarkup:
    wl_text = "✅ In Watchlist" if in_watchlist else "📋 Add to Watchlist"
    wl_data = f"wl_remove:{movie_id}" if in_watchlist else f"wl_add:{movie_id}"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎥 Trailer", callback_data=f"trailer:{movie_id}"),
            InlineKeyboardButton(wl_text, callback_data=wl_data),
        ],
        [
            InlineKeyboardButton("🔍 Similar", callback_data=f"similar:{movie_id}"),
            InlineKeyboardButton("📺 Where to Watch", callback_data=f"where:{movie_id}"),
        ],
        [
            InlineKeyboardButton("🧠 Explain", callback_data=f"explain_menu:{movie_id}"),
            InlineKeyboardButton("✅ Mark Watched", callback_data=f"watched_add:{movie_id}"),
        ],
        [InlineKeyboardButton("🔔 Alert on Release", callback_data=f"alert_add:{movie_id}")],
    ])


def search_results_kb(movies: list[dict]) -> InlineKeyboardMarkup:
    buttons = []
    for m in movies[:8]:
        mid = m["id"]
        title = m.get("title", "?")[:30]
        year = m.get("release_date", "")[:4]
        label = f"{title} ({year})" if year else title
        buttons.append([InlineKeyboardButton(f"🎬 {label}", callback_data=f"movie:{mid}")])
    return InlineKeyboardMarkup(buttons)


def rating_kb(movie_id: int) -> InlineKeyboardMarkup:
    rows = []
    for start in range(1, 11, 5):
        row = [
            InlineKeyboardButton(f"{'⭐' * i} {i}", callback_data=f"rate:{movie_id}:{i}")
            for i in range(start, min(start + 5, 11))
        ]
        rows.append(row)
    rows.append([InlineKeyboardButton("📝 Add Review", callback_data=f"review:{movie_id}")])
    return InlineKeyboardMarkup(rows)


def confirm_kb(action: str, data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirm", callback_data=f"confirm:{action}:{data}"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
        ]
    ])


def mood_kb() -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(mood, callback_data=f"mood:{mood}")] for mood in MOOD_MAP]
    return InlineKeyboardMarkup(buttons)


def genre_select_kb(selected: set[int] | None = None) -> InlineKeyboardMarkup:
    selected = selected or set()
    buttons = []
    row: list[InlineKeyboardButton] = []
    for gid, name in sorted(TMDB_GENRES.items(), key=lambda x: x[1]):
        prefix = "✅ " if gid in selected else ""
        row.append(InlineKeyboardButton(f"{prefix}{name}", callback_data=f"genre_sel:{gid}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("✅ Done", callback_data="genre_done")])
    return InlineKeyboardMarkup(buttons)


def recommend_type_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("😊 By Mood", callback_data="rec_type:mood")],
        [InlineKeyboardButton("🎭 By Genre", callback_data="rec_type:genre")],
        [InlineKeyboardButton("🎬 Similar to a Movie", callback_data="rec_type:similar")],
        [InlineKeyboardButton("🎲 Surprise Me!", callback_data="rec_type:surprise")],
    ])


def explain_type_kb(movie_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📖 Full Plot", callback_data=f"explain:plot:{movie_id}")],
        [InlineKeyboardButton("🔚 Ending Explained", callback_data=f"explain:ending:{movie_id}")],
        [InlineKeyboardButton("🔍 Hidden Details", callback_data=f"explain:hidden:{movie_id}")],
        [InlineKeyboardButton("👤 Character Analysis", callback_data=f"explain:chars:{movie_id}")],
    ])


def priority_kb(movie_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔴 High", callback_data=f"pri:{movie_id}:HIGH"),
            InlineKeyboardButton("🟡 Medium", callback_data=f"pri:{movie_id}:MED"),
            InlineKeyboardButton("🟢 Low", callback_data=f"pri:{movie_id}:LOW"),
        ]
    ])


def pagination_kb(prefix: str, page: int, total_pages: int) -> InlineKeyboardMarkup:
    buttons = []
    if page > 1:
        buttons.append(InlineKeyboardButton(f"{E_ARROW_L} Prev", callback_data=f"{prefix}:page:{page - 1}"))
    buttons.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        buttons.append(InlineKeyboardButton(f"Next {E_ARROW_R}", callback_data=f"{prefix}:page:{page + 1}"))
    return InlineKeyboardMarkup([buttons]) if buttons else InlineKeyboardMarkup([])


def pro_upgrade_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔑 Redeem a Key", callback_data="redeem_prompt")],
        [InlineKeyboardButton("👑 View Plans", callback_data="view_plans")],
    ])


def admin_dashboard_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Stats", callback_data="adm:stats"),
            InlineKeyboardButton("🔑 Gen Key", callback_data="adm:genkey"),
        ],
        [
            InlineKeyboardButton("📦 Bulk Keys", callback_data="adm:bulkkeys"),
            InlineKeyboardButton("🔍 Key Info", callback_data="adm:keyinfo"),
        ],
        [
            InlineKeyboardButton("👤 User Lookup", callback_data="adm:userlookup"),
            InlineKeyboardButton("📣 Broadcast", callback_data="adm:broadcast"),
        ],
        [
            InlineKeyboardButton("📋 List Keys", callback_data="adm:listkeys:1"),
            InlineKeyboardButton("🚫 Revoke Key", callback_data="adm:revoke"),
        ],
    ])


def random_filter_kb() -> InlineKeyboardMarkup:
    popular_genres = [(28, "Action"), (35, "Comedy"), (18, "Drama"), (27, "Horror"),
                      (878, "Sci-Fi"), (10749, "Romance"), (53, "Thriller"), (16, "Animation")]
    rows = []
    row: list[InlineKeyboardButton] = []
    for gid, name in popular_genres:
        row.append(InlineKeyboardButton(name, callback_data=f"random_genre:{gid}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("🎲 Any Genre", callback_data="random_genre:any")])
    return InlineKeyboardMarkup(rows)


def alert_list_kb(alerts: list, page: int, total_pages: int) -> InlineKeyboardMarkup:
    buttons = []
    for a in alerts:
        buttons.append([InlineKeyboardButton(
            f"❌ {a.movie_title[:30]}", callback_data=f"alert_rm:{a.tmdb_movie_id}"
        )])
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(E_ARROW_L, callback_data=f"alerts:page:{page - 1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton(E_ARROW_R, callback_data=f"alerts:page:{page + 1}"))
    if nav:
        buttons.append(nav)
    return InlineKeyboardMarkup(buttons)


def back_button(callback_data: str = "back_main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data=callback_data)]])