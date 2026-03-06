# bot/utils/constants.py

E_MOVIE = "🎬"
E_STAR = "⭐"
E_FIRE = "🔥"
E_HEART = "❤️"
E_CLOCK = "⏱"
E_GLOBE = "🌍"
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
E_ARROW_R = "▶️"
E_ARROW_L = "◀️"
E_UP = "⬆️"
E_DOWN = "⬇️"
E_REFRESH = "🔄"
E_SEND = "📤"
E_PERSON = "👤"
E_PEOPLE = "👥"
E_GEAR = "⚙️"
E_ROBOT = "🤖"

TMDB_GENRES = {
    28: "Action", 12: "Adventure", 16: "Animation", 35: "Comedy",
    80: "Crime", 99: "Documentary", 18: "Drama", 10751: "Family",
    14: "Fantasy", 36: "History", 27: "Horror", 10402: "Music",
    9648: "Mystery", 10749: "Romance", 878: "Sci-Fi", 10770: "TV Movie",
    53: "Thriller", 10752: "War", 37: "Western",
}

MOOD_MAP = {
    "😊 Happy": [35, 10751, 16, 10402],
    "😢 Sad": [18, 10749],
    "😱 Scared": [27, 53],
    "🤔 Thoughtful": [99, 36, 18],
    "🚀 Adventurous": [28, 12, 878, 14],
    "😂 Funny": [35, 16],
    "❤️ Romantic": [10749, 18, 35],
    "😎 Cool": [28, 80, 53],
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
    f"{E_MOVIE} <b>Welcome to CineBot!</b> {E_POPCORN}\n\n"
    "Your personal AI movie companion. Here's what I can do:\n\n"
    f"{E_SEARCH} /search — Find any movie with rich details\n"
    f"{E_BRAIN} /recommend — AI-powered personalized picks\n"
    f"{E_LIST} /watchlist — Manage your want-to-watch list\n"
    f"{E_CHECK} /watched — Log & rate movies you've seen\n"
    f"{E_TV} /where — Find where to stream any movie\n"
    f"{E_TROPHY} /compare — Compare two movies head-to-head\n"
    f"{E_ROBOT} /explain — AI plot & ending explanations\n"
    f"{E_CHART} /stats — Your watching statistics\n"
    f"{E_BELL} /alerts — Release date notifications\n"
    f"{E_DICE} /random — Surprise movie pick\n"
    f"😊 /mood — Mood-based recommendations\n"
    f"{E_KEY} /redeem — Activate Pro subscription\n"
    f"{E_CROWN} /pro — View your plan & usage\n\n"
    f"Just type a movie name to search, or use inline mode: <code>@CineBot movie name</code>"
)

MSG_HELP = (
    f"{E_INFO} <b>CineBot Help</b>\n\n"
    f"<b>Search & Discovery</b>\n"
    f"  /search <code>movie name</code> — Detailed movie card\n"
    f"  /recommend — Get AI recommendations\n"
    f"  /random — Random movie suggestion\n"
    f"  /mood — Pick by your mood\n\n"
    f"<b>Your Library</b>\n"
    f"  /watchlist — Your watch-later list\n"
    f"  /watched — Your movie diary\n"
    f"  /stats — Viewing statistics\n\n"
    f"<b>Movie Info</b>\n"
    f"  /where <code>movie name</code> — Streaming availability\n"
    f"  /compare <code>movie A</code> vs <code>movie B</code> — Side-by-side\n"
    f"  /explain <code>movie name</code> — AI analysis\n\n"
    f"<b>Subscription</b>\n"
    f"  /redeem <code>KEY</code> — Activate Pro\n"
    f"  /pro — Plan details & usage\n"
    f"  /alerts — Release notifications\n\n"
    f"<b>Inline Mode</b>\n"
    f"  Type <code>@CineBot query</code> in any chat"
)

MSG_ONBOARDING_GENRES = (
    f"{E_MOVIE} <b>Let's personalize your experience!</b>\n\n"
    "Pick your favorite genres (select at least 2):"
)

MSG_RATE_LIMITED = f"{E_CLOCK} You're going too fast! Please wait a moment."

MSG_PRO_REQUIRED = (
    f"{E_LOCK} This is a <b>Pro</b> feature.\n\n"
    f"Upgrade to Pro to unlock:\n"
    f"  {E_SPARKLE} Unlimited searches & recommendations\n"
    f"  {E_SPARKLE} Unlimited explains & watchlist\n"
    f"  {E_SPARKLE} Advanced statistics\n"
    f"  {E_SPARKLE} Priority support\n\n"
    f"Contact an admin or use /redeem with a license key!"
)

MSG_PRO_STATUS = (
    f"{E_CROWN} <b>Your Pro Status</b>\n\n"
    "Plan: <b>{tier}</b>\n"
    "Expires: <b>{expires}</b>\n"
    "Days left: <b>{days_left}</b>\n\n"
    "<b>Today's Usage:</b>\n"
    f"  {E_SEARCH} Searches: {{searches}}\n"
    f"  {E_BRAIN} Recommends: {{recommends}}\n"
    f"  {E_ROBOT} Explains: {{explains}}\n"
    f"  {E_LIST} Watchlist: {{watchlist}}"
)

MSG_KEY_REDEEMED = (
    f"{E_PARTY} <b>Key Redeemed Successfully!</b>\n\n"
    f"{E_CROWN} Plan: <b>Pro</b>\n"
    f"{E_CALENDAR} Duration: <b>{{duration}}</b>\n"
    f"{E_CLOCK} Expires: <b>{{expires}}</b>\n\n"
    f"Enjoy unlimited access to all features! {E_SPARKLE}"
)

MSG_EXPIRY_WARNING = (
    f"{E_WARN} <b>Subscription Expiring Soon</b>\n\n"
    "Your Pro subscription expires in <b>{days} days</b> ({date}).\n"
    "Contact an admin to renew!"
)

MSG_EXPIRED = (
    f"{E_INFO} Your Pro subscription has expired.\n"
    "You've been downgraded to the Free plan.\n"
    "Use /redeem with a new key to reactivate Pro!"
)

MSG_NO_RESULTS = f"{E_SEARCH} No results found. Try a different search term."
MSG_WATCHLIST_EMPTY = f"{E_LIST} Your watchlist is empty. Use /search to find movies to add!"
MSG_WATCHED_EMPTY = f"{E_FILM} You haven't logged any movies yet. Use /watched after watching a film!"
MSG_MILESTONE = f"{E_PARTY} <b>Milestone!</b> You've watched <b>{{count}}</b> movies! {E_CLAP}"