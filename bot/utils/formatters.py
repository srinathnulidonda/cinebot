# bot/utils/formatters.py
from datetime import datetime
from bot.utils.constants import (
    E_MOVIE, E_STAR, E_CLOCK, E_GLOBE, E_TROPHY, E_CHECK, E_CHART,
    E_CALENDAR, E_PIN, E_CROWN, E_SPARKLE, E_FIRE, E_FILM, E_TV,
    E_HEART, E_LIST, E_BELL, E_PERSON, E_PEOPLE, E_KEY, E_INFO,
    E_BRAIN, TMDB_GENRES, MILESTONES,
)
from bot.utils.validators import sanitize_html

def format_movie_card(movie: dict) -> str:
    title = sanitize_html(movie.get("title", "Unknown"))
    year = movie.get("release_date", "")[:4] or "N/A"
    rating = movie.get("vote_average", 0)
    votes = movie.get("vote_count", 0)
    overview = sanitize_html(movie.get("overview", "No overview available."))
    if len(overview) > 400:
        overview = overview[:397] + "..."
    genres = ", ".join(TMDB_GENRES.get(g, "?") for g in (movie.get("genre_ids") or []))
    if not genres and movie.get("genres"):
        genres = ", ".join(g["name"] for g in movie["genres"])
    runtime = movie.get("runtime")
    runtime_str = f"\n{E_CLOCK} <b>Runtime:</b> {runtime} min" if runtime else ""
    lang = movie.get("original_language", "").upper()
    popularity = movie.get("popularity", 0)
    stars = "⭐" * min(int(rating / 2), 5)
    return (
        f"{E_MOVIE} <b>{title}</b> ({year})\n\n"
        f"{stars} <b>{rating:.1f}</b>/10 ({votes:,} votes)\n"
        f"{E_FIRE} Popularity: {popularity:,.0f}\n"
        f"🎭 <b>Genres:</b> {genres or 'N/A'}"
        f"{runtime_str}\n"
        f"{E_GLOBE} <b>Language:</b> {lang}\n\n"
        f"📝 <b>Overview:</b>\n{overview}"
    )


def format_movie_short(movie: dict) -> str:
    title = sanitize_html(movie.get("title", "Unknown"))
    year = movie.get("release_date", "")[:4] or "?"
    rating = movie.get("vote_average", 0)
    return f"{E_MOVIE} <b>{title}</b> ({year}) — ⭐ {rating:.1f}"


def format_movie_credits(credits: dict) -> str:
    cast = credits.get("cast", [])[:6]
    directors = [c for c in credits.get("crew", []) if c.get("job") == "Director"]
    lines = []
    if directors:
        names = ", ".join(sanitize_html(d["name"]) for d in directors[:2])
        lines.append(f"🎥 <b>Director:</b> {names}")
    if cast:
        names = ", ".join(sanitize_html(a["name"]) for a in cast)
        lines.append(f"🌟 <b>Cast:</b> {names}")
    return "\n".join(lines)


def format_comparison(a: dict, b: dict) -> str:
    def score(m: dict) -> float:
        return m.get("vote_average", 0) * 0.6 + min(m.get("popularity", 0) / 100, 40) * 0.4

    sa, sb = score(a), score(b)
    winner = a if sa >= sb else b
    wt = sanitize_html(winner.get("title", ""))

    def side(m: dict, emoji: str) -> str:
        t = sanitize_html(m.get("title", "Unknown"))
        y = m.get("release_date", "")[:4] or "?"
        r = m.get("vote_average", 0)
        v = m.get("vote_count", 0)
        p = m.get("popularity", 0)
        rt = m.get("runtime", "?")
        return (
            f"{emoji} <b>{t}</b> ({y})\n"
            f"   ⭐ {r:.1f}/10 ({v:,} votes)\n"
            f"   {E_FIRE} Popularity: {p:,.0f}\n"
            f"   {E_CLOCK} Runtime: {rt} min"
        )

    return (
        f"{E_TROPHY} <b>Movie Comparison</b>\n\n"
        f"{side(a, '🔵')}\n\n"
        f"          ⚔️ VS ⚔️\n\n"
        f"{side(b, '🔴')}\n\n"
        f"{'━' * 28}\n"
        f"{E_TROPHY} <b>Winner: {wt}</b> {E_SPARKLE}"
    )


def format_watchlist_item(item, idx: int) -> str:
    pri_emoji = {"HIGH": "🔴", "MED": "🟡", "LOW": "🟢"}.get(item.priority.value, "⚪")
    return f"{idx}. {pri_emoji} <b>{sanitize_html(item.movie_title)}</b> (ID: {item.tmdb_movie_id})"


def format_watched_item(item, idx: int) -> str:
    rating_str = f"⭐ {item.user_rating}/10" if item.user_rating else "Not rated"
    date_str = item.watched_at.strftime("%b %d, %Y") if item.watched_at else ""
    return f"{idx}. {E_FILM} <b>{sanitize_html(item.movie_title)}</b> — {rating_str} ({date_str})"


def format_stats(stats: dict) -> str:
    total = stats.get("total_watched", 0)
    avg = stats.get("avg_rating", 0)
    genre_bars = stats.get("genre_bars", "")
    return (
        f"{E_CHART} <b>Your Movie Stats</b>\n\n"
        f"{E_FILM} Total watched: <b>{total}</b>\n"
        f"{E_STAR} Average rating: <b>{avg:.1f}/10</b>\n"
        f"{E_CROWN} Highest rated: <b>{sanitize_html(stats.get('best', 'N/A'))}</b>\n"
        f"{E_CALENDAR} Most active: <b>{stats.get('active_month', 'N/A')}</b>\n\n"
        f"🎭 <b>Genre Breakdown:</b>\n{genre_bars}"
    )


def build_genre_bars(genre_counts: dict[str, int], top_n: int = 8) -> str:
    if not genre_counts:
        return "No data yet."
    sorted_genres = sorted(genre_counts.items(), key=lambda x: x[1], reverse=True)[:top_n]
    max_count = sorted_genres[0][1] if sorted_genres else 1
    lines = []
    for gid, count in sorted_genres:
        name = TMDB_GENRES.get(int(gid), f"Genre {gid}")
        bar_len = int((count / max_count) * 10)
        bar = "█" * bar_len + "░" * (10 - bar_len)
        lines.append(f"  {name}: {bar} {count}")
    return "\n".join(lines)


def format_streaming(data: dict, country: str = "US") -> str:
    if not data:
        return f"{E_TV} No streaming info available for this movie."
    lines = [f"{E_TV} <b>Where to Watch</b> ({country})\n"]
    for stype, emoji in [("flatrate", "📺 Stream"), ("rent", "💲 Rent"), ("buy", "🛒 Buy")]:
        providers = data.get(stype, [])
        if providers:
            names = ", ".join(p.get("provider_name", "?") for p in providers[:5])
            lines.append(f"  {emoji}: {names}")
    if len(lines) == 1:
        lines.append("  No options found for this region.")
    return "\n".join(lines)


def format_recommendation_list(movies: list[dict], title: str = "Recommendations") -> str:
    lines = [f"{E_BRAIN} <b>{title}</b>\n"]
    for i, m in enumerate(movies, 1):
        t = sanitize_html(m.get("title", "Unknown"))
        y = m.get("release_date", "")[:4] or "?"
        r = m.get("vote_average", 0)
        confidence = m.get("confidence", "")
        conf_str = f" — {confidence}% match" if confidence else ""
        lines.append(f"{i}. {E_MOVIE} <b>{t}</b> ({y}) ⭐ {r:.1f}{conf_str}")
    return "\n".join(lines)


def format_key_info(key) -> str:
    return (
        f"{E_KEY} <b>Key Info</b>\n\n"
        f"Key: <code>{key.key}</code>\n"
        f"Type: <b>{key.key_type}</b> ({key.duration_days} days)\n"
        f"Status: <b>{key.status.value}</b>\n"
        f"Batch: {key.batch_name or 'N/A'}\n"
        f"Created: {key.created_at.strftime('%Y-%m-%d %H:%M') if key.created_at else 'N/A'}\n"
        f"Redeemed by: {key.redeemed_by_user_id or 'N/A'}\n"
        f"Redeemed at: {key.redeemed_at.strftime('%Y-%m-%d %H:%M') if key.redeemed_at else 'N/A'}"
    )


def format_user_info(user) -> str:
    return (
        f"{E_PERSON} <b>User Info</b>\n\n"
        f"ID: <code>{user.telegram_id}</code>\n"
        f"Name: {sanitize_html(user.display_name)}\n"
        f"Username: @{user.username or 'N/A'}\n"
        f"Plan: <b>{user.subscription_tier.value}</b>\n"
        f"Expires: {user.subscription_expires_at.strftime('%Y-%m-%d') if user.subscription_expires_at else 'N/A'}\n"
        f"Admin: {'Yes' if user.is_admin else 'No'}\n"
        f"Joined: {user.created_at.strftime('%Y-%m-%d') if user.created_at else 'N/A'}"
    )


def check_milestone(count: int) -> str | None:
    if count in MILESTONES:
        return f"🎉 <b>Milestone!</b> You've watched <b>{count}</b> movies! 👏"
    return None