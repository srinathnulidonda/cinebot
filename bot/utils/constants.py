# bot/utils/constants.py

E_MOVIE = "🎬"
E_STAR = "⭐"
E_FIRE = "🔥"
E_HEART = "❤️"
E_CLOCK = "🕐"
E_GLOBE = "🌐"
E_TROPHY = "🏆"
E_LOCK = "🔒"
E_KEY = "🔑"
E_CHECK = "✅"
E_CROSS = "❌"
E_WARN = "⚠️"
E_INFO = "ℹ️"
E_SEARCH = "🔍"
E_LIST = "📋"
E_CHART = "📊"
E_BELL = "🔔"
E_DICE = "🎲"
E_BRAIN = "🧠"
E_POPCORN = "🍿"
E_CLAP = "👏"
E_PARTY = "🎉"
E_CROWN = "👑"
E_SPARKLE = "✨"
E_FILM = "🎞"
E_TV = "📺"
E_MONEY = "💰"
E_CALENDAR = "📅"
E_PIN = "📌"
E_ARROW_R = "→"
E_ARROW_L = "←"
E_UP = "⬆️"
E_DOWN = "⬇️"
E_REFRESH = "🔄"
E_SEND = "📤"
E_PERSON = "👤"
E_PEOPLE = "👥"
E_GEAR = "⚙️"
E_ROBOT = "🤖"
E_GEM = "💎"
E_BOLT = "⚡"
E_PHONE = "📞"
E_SHIELD = "🛡️"
E_WAIT = "⏳"
E_DB = "🗄️"
E_SERVER = "🖥️"
E_PING = "📡"
E_GREEN = "🟢"
E_YELLOW = "🟡"
E_RED = "🔴"

# Mobile-friendly separators
LINE = "─ ─ ─ ─ ─ ─ ─ ─"
LINE_LIGHT = "· · · · · · · ·"

BADGE_PRO = "👑"
BADGE_HOT = "🔥"
BADGE_NEW = "✨"
BADGE_TOP = "⭐"

TMDB_GENRES = {
    28: "Action", 12: "Adventure", 16: "Animation", 35: "Comedy",
    80: "Crime", 99: "Documentary", 18: "Drama", 10751: "Family",
    14: "Fantasy", 36: "History", 27: "Horror", 10402: "Music",
    9648: "Mystery", 10749: "Romance", 878: "Sci-Fi", 10770: "TV Movie",
    53: "Thriller", 10752: "War", 37: "Western",
}

MOOD_MAP = {
    "😄 Happy": [35, 10751, 16, 10402],
    "😢 Sad": [18, 10749],
    "😱 Scared": [27, 53],
    "🤔 Think": [99, 36, 9648],
    "💑 Love": [10749, 18, 35],
    "😂 Funny": [35, 16],
}

FREE_LIMITS = {
    "search": 10,
    "explain": 3,
    "recommend": 5,
    "watchlist": 20,
}

PRO_LIMITS = {
    "search": 999999,
    "explain": 999999,
    "recommend": 999999,
    "watchlist": 999999,
}

KEY_TYPES = {
    "1M": {"label": "1 Month", "days": 30},
    "2M": {"label": "2 Months", "days": 60},
    "3M": {"label": "3 Months", "days": 90},
    "6M": {"label": "6 Months", "days": 180},
    "1Y": {"label": "1 Year", "days": 365},
}

MILESTONES = [1, 5, 10, 25, 50, 100, 250, 500, 1000]

MSG_WELCOME = (
    f"{E_MOVIE} <b>CINEBOT</b> {E_POPCORN}\n"
    f"{LINE}\n\n"
    f"<b>◆ Discover</b>\n"
    f"{E_SEARCH} /search - Find movies\n"
    f"{E_BRAIN} /recommend - AI picks\n"
    f"{E_DICE} /random - Surprise me\n"
    f"😊 /mood - Match vibe\n\n"
    f"<b>◆ Library</b>\n"
    f"{E_LIST} /watchlist - Save later\n"
    f"{E_CHECK} /watched - Diary\n"
    f"{E_CHART} /stats - Stats\n\n"
    f"<b>◆ Explore</b>\n"
    f"{E_TV} /where - Streaming\n"
    f"{E_TROPHY} /compare - Head2Head\n"
    f"{E_BRAIN} /explain - AI dive\n"
    f"{E_BELL} /alerts - Releases\n\n"
    f"<b>◆ Account</b>\n"
    f"{E_KEY} /redeem - Pro key\n"
    f"{E_CROWN} /pro - Plan\n"
    f"{E_PHONE} /contact - Support\n\n"
    f"{LINE_LIGHT}\n"
    f"💡 Type movie name to search"
)

MSG_HELP = (
    f"{E_INFO} <b>HELP</b>\n"
    f"{LINE}\n\n"
    f"<b>◆ Search</b>\n"
    f"{E_SEARCH} /search <code>name</code>\n"
    f"{E_BRAIN} /recommend\n"
    f"{E_DICE} /random\n"
    f"😊 /mood\n\n"
    f"<b>◆ Library</b>\n"
    f"{E_LIST} /watchlist\n"
    f"{E_CHECK} /watched\n"
    f"{E_CHART} /stats\n\n"
    f"<b>◆ Intel</b>\n"
    f"{E_TV} /where <code>name</code>\n"
    f"{E_TROPHY} /compare <code>A vs B</code>\n"
    f"{E_BRAIN} /explain <code>name</code>\n\n"
    f"<b>◆ Account</b>\n"
    f"{E_KEY} /redeem <code>KEY</code>\n"
    f"{E_CROWN} /pro\n"
    f"{E_BELL} /alerts\n"
    f"{E_PHONE} /contact\n\n"
    f"{LINE_LIGHT}\n"
    f"💡 Inline: @YourBot movie"
)

MSG_ONBOARDING_GENRES = (
    f"{E_MOVIE} <b>Personalize!</b>\n"
    f"{LINE}\n\n"
    "Pick favorite genres (2+):"
)

MSG_RATE_LIMITED = (
    f"{E_WAIT} <b>Slow down!</b>\n\n"
    "Try in 10 seconds."
)

MSG_PRO_REQUIRED = (
    f"{E_LOCK} <b>PRO Feature</b>\n"
    f"{LINE}\n\n"
    f"{E_SPARKLE} Unlimited all\n"
    f"{E_SPARKLE} Priority support\n\n"
    f"{E_KEY} /redeem or {E_PHONE} /contact"
)

MSG_KEY_REDEEMED = (
    f"{E_PARTY} <b>REDEEMED!</b>\n"
    f"{LINE}\n\n"
    f"{E_CROWN} Plan: <b>PRO</b>\n"
    f"{E_CALENDAR} Duration: <b>{{duration}}</b>\n"
    f"{E_WAIT} Expires: <b>{{expires}}</b>\n\n"
    f"{E_SPARKLE} Unlimited access! {E_POPCORN}"
)

MSG_EXPIRY_WARNING = (
    f"{E_WARN} <b>EXPIRING</b>\n"
    f"{LINE}\n\n"
    f"{E_WAIT} In <b>{{days}} day(s)</b>\n"
    f"{E_CALENDAR} Date: <b>{{date}}</b>\n\n"
    f"{E_KEY} /redeem to extend"
)

MSG_EXPIRED = (
    f"{E_INFO} <b>Expired</b>\n"
    f"{LINE}\n\n"
    "Pro ended → Free plan\n\n"
    f"{E_KEY} /redeem new key\n"
    f"{E_PHONE} /contact for help"
)

MSG_NO_RESULTS = (
    f"{E_SEARCH} <b>Not Found</b>\n\n"
    "Can't find that 🙈\n\n"
    "💡 Check spelling"
)

MSG_WATCHLIST_EMPTY = (
    f"{E_LIST} <b>Empty</b>\n\n"
    f"Use /search to add movies"
)

MSG_WATCHED_EMPTY = (
    f"{E_FILM} <b>No movies yet</b>\n\n"
    f"Use /search to start {E_POPCORN}"
)

MSG_MILESTONE = (
    f"{E_PARTY} <b>MILESTONE!</b>\n"
    f"{LINE}\n\n"
    f"<b>{{count}}</b> movies! {E_CLAP}\n"
    "Keep going! 🍿"
)