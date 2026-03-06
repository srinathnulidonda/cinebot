# bot/services/recommendation_engine.py
import logging
import random
from bot.services import tmdb_service, openai_service
from bot.models.engine import get_session
from bot.models.watched import WatchedRepo
from bot.models.preference import PreferenceRepo
from bot.utils.constants import TMDB_GENRES, MOOD_MAP

logger = logging.getLogger(__name__)


async def get_user_context(user_db_id: int) -> tuple[dict, list[str], list[int]]:
    async with get_session() as session:
        prefs = await PreferenceRepo.get_or_create(session, user_db_id)
        recent = await WatchedRepo.get_recent(session, user_db_id, 20)
        watched_ids = await WatchedRepo.get_all_movie_ids(session, user_db_id)
    watched_titles = [w.movie_title for w in recent]
    preferences = {
        "liked_genres": prefs.liked_genres or {},
        "liked_actors": prefs.liked_actors or {},
        "taste_vector": prefs.taste_vector or {},
    }
    return preferences, watched_titles, watched_ids


async def recommend_by_mood(user_db_id: int, mood: str) -> list[dict]:
    preferences, watched_titles, watched_ids = await get_user_context(user_db_id)
    genre_ids = MOOD_MAP.get(mood, [35, 18])
    tmdb_results = []
    try:
        data = await tmdb_service.discover_movies(genres=genre_ids[:2], min_rating=6.5, page=random.randint(1, 5))
        tmdb_results = [m for m in data.get("results", []) if m["id"] not in watched_ids][:10]
    except Exception as e:
        logger.warning(f"TMDb discover failed for mood: {e}")
    ai_results = []
    try:
        ai_results = await openai_service.mood_recommendations(mood, preferences, watched_titles)
    except Exception as e:
        logger.warning(f"AI mood recs failed: {e}")
    return await _merge_results(tmdb_results, ai_results, watched_ids)


async def recommend_by_genre(user_db_id: int, genre_ids: list[int]) -> list[dict]:
    preferences, watched_titles, watched_ids = await get_user_context(user_db_id)
    tmdb_results = []
    try:
        data = await tmdb_service.discover_movies(genres=genre_ids, min_rating=6.0, page=random.randint(1, 5))
        tmdb_results = [m for m in data.get("results", []) if m["id"] not in watched_ids][:10]
    except Exception as e:
        logger.warning(f"TMDb discover failed: {e}")
    genre_names = [TMDB_GENRES.get(g, str(g)) for g in genre_ids]
    ai_results = []
    try:
        ai_results = await openai_service.get_recommendations(
            preferences, watched_titles, "genre",
            f"Focus on genres: {', '.join(genre_names)}",
        )
    except Exception as e:
        logger.warning(f"AI genre recs failed: {e}")
    return await _merge_results(tmdb_results, ai_results, watched_ids)


async def recommend_similar(user_db_id: int, movie_id: int) -> list[dict]:
    _, _, watched_ids = await get_user_context(user_db_id)
    tmdb_results = []
    try:
        data = await tmdb_service.get_similar(movie_id)
        tmdb_results = [m for m in data.get("results", []) if m["id"] not in watched_ids][:10]
    except Exception as e:
        logger.warning(f"TMDb similar failed: {e}")
    try:
        rec_data = await tmdb_service.get_recommendations(movie_id)
        extra = [m for m in rec_data.get("results", []) if m["id"] not in watched_ids and m not in tmdb_results]
        tmdb_results.extend(extra[:5])
    except Exception:
        pass
    for m in tmdb_results:
        m["confidence"] = min(95, int(m.get("vote_average", 5) * 10))
    return tmdb_results[:5] if tmdb_results else []


async def recommend_surprise(user_db_id: int) -> list[dict]:
    preferences, watched_titles, watched_ids = await get_user_context(user_db_id)
    tmdb_results = []
    try:
        source = random.choice(["trending", "discover"])
        if source == "trending":
            data = await tmdb_service.get_trending("week", random.randint(1, 3))
        else:
            data = await tmdb_service.discover_movies(
                sort_by="popularity.desc", min_rating=7.0, page=random.randint(1, 10),
            )
        tmdb_results = [m for m in data.get("results", []) if m["id"] not in watched_ids]
        random.shuffle(tmdb_results)
        tmdb_results = tmdb_results[:10]
    except Exception as e:
        logger.warning(f"TMDb surprise failed: {e}")
    ai_results = []
    try:
        ai_results = await openai_service.get_recommendations(
            preferences, watched_titles, "surprise",
            "Surprise them with unexpected but great picks across different genres and eras.",
        )
    except Exception as e:
        logger.warning(f"AI surprise failed: {e}")
    return await _merge_results(tmdb_results, ai_results, watched_ids)


async def get_random_movie(genre_id: int | None = None) -> dict | None:
    try:
        genres = [genre_id] if genre_id else None
        page = random.randint(1, 20)
        data = await tmdb_service.discover_movies(
            genres=genres, sort_by="popularity.desc", min_rating=5.5, page=page,
        )
        results = data.get("results", [])
        if results:
            return random.choice(results)
    except Exception as e:
        logger.error(f"Random movie failed: {e}")
    return None


async def _merge_results(
    tmdb_results: list[dict],
    ai_results: list[dict],
    watched_ids: list[int],
) -> list[dict]:
    final = []
    seen_ids: set[int] = set()

    for m in tmdb_results[:3]:
        mid = m.get("id")
        if mid and mid not in watched_ids and mid not in seen_ids:
            m["confidence"] = m.get("confidence", min(90, int(m.get("vote_average", 5) * 10)))
            final.append(m)
            seen_ids.add(mid)

    for ai_rec in ai_results:
        if len(final) >= 5:
            break
        title = ai_rec.get("title", "")
        if not title:
            continue
        try:
            search = await tmdb_service.search_movies(f"{title} {ai_rec.get('year', '')}")
            results = search.get("results", [])
            if results:
                tmdb_movie = results[0]
                mid = tmdb_movie["id"]
                if mid not in watched_ids and mid not in seen_ids:
                    tmdb_movie["confidence"] = ai_rec.get("confidence", 75)
                    tmdb_movie["ai_reason"] = ai_rec.get("reason", "")
                    final.append(tmdb_movie)
                    seen_ids.add(mid)
        except Exception:
            continue

    remaining = [m for m in tmdb_results if m.get("id") not in seen_ids and m.get("id") not in watched_ids]
    for m in remaining:
        if len(final) >= 5:
            break
        m["confidence"] = m.get("confidence", min(80, int(m.get("vote_average", 5) * 9)))
        final.append(m)
        seen_ids.add(m["id"])

    return final[:5]