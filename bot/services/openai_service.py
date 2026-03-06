# bot/services/openai_service.py
import logging
import json
from openai import AsyncOpenAI
from bot.config import get_settings
from bot.models.engine import redis_client
from bot import ExternalAPIError

logger = logging.getLogger(__name__)
_s = get_settings()
_client = AsyncOpenAI(api_key=_s.OPENAI_API_KEY)


async def _chat(system: str, user: str, cache_key: str | None = None, ttl: int = 3600) -> str:
    if cache_key:
        cached = await redis_client.get(cache_key)
        if cached:
            return cached
    for attempt in range(3):
        try:
            resp = await _client.chat.completions.create(
                model=_s.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=_s.OPENAI_MAX_TOKENS,
                temperature=0.7,
            )
            text = resp.choices[0].message.content or ""
            if cache_key and ttl and text:
                await redis_client.setex(cache_key, ttl, text)
            return text
        except Exception as e:
            logger.error(f"OpenAI attempt {attempt + 1} failed: {e}")
            if attempt == 2:
                raise ExternalAPIError("OpenAI")
            import asyncio
            await asyncio.sleep(2 ** attempt)
    raise ExternalAPIError("OpenAI")


async def get_recommendations(
    preferences: dict,
    watched_titles: list[str],
    mode: str = "general",
    extra_context: str = "",
) -> list[dict]:
    liked_genres = preferences.get("liked_genres", {})
    genre_str = ", ".join(v.get("name", k) for k, v in list(liked_genres.items())[:8]) if liked_genres else "various"
    watched_str = ", ".join(watched_titles[:20]) if watched_titles else "none yet"

    system = (
        "You are a world-class film recommender. Return exactly 5 movie recommendations as JSON array. "
        "Each object: {\"title\": str, \"year\": int, \"reason\": str (1 sentence why), \"confidence\": int (60-99)}. "
        "Only return valid JSON array, no markdown, no explanation."
    )
    user = (
        f"Mode: {mode}\n"
        f"Favorite genres: {genre_str}\n"
        f"Already watched: {watched_str}\n"
        f"Additional context: {extra_context}\n"
        "Recommend 5 movies they haven't watched. Diverse but matching their taste."
    )
    cache_key = None
    text = await _chat(system, user, cache_key, 0)
    try:
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(text)
    except (json.JSONDecodeError, IndexError):
        logger.error(f"Failed to parse recommendations: {text[:200]}")
        return []


async def explain_movie(
    title: str,
    year: str,
    overview: str,
    explain_type: str = "plot",
) -> str:
    type_prompts = {
        "plot": "Provide a detailed plot summary including major story beats. Spoiler warning included.",
        "ending": "Explain the ending in detail. What happened and why. Include any ambiguous elements.",
        "hidden": "Reveal hidden details, Easter eggs, symbolism, and things most viewers miss.",
        "chars": "Provide deep character analysis for the main characters. Motivations, arcs, development.",
    }
    type_titles = {
        "plot": "📖 Full Plot Summary",
        "ending": "🔚 Ending Explained",
        "hidden": "🔍 Hidden Details & Easter Eggs",
        "chars": "👤 Character Analysis",
    }
    prompt_detail = type_prompts.get(explain_type, type_prompts["plot"])
    title_header = type_titles.get(explain_type, "📖 Analysis")

    system = (
        "You are an expert film critic and analyst. Provide detailed, engaging movie analysis. "
        "Use clear formatting with sections. Be thorough but concise. Always start with a spoiler warning if needed."
    )
    user = (
        f"Movie: {title} ({year})\nOverview: {overview}\n\n"
        f"Task: {prompt_detail}\n\n"
        f"Format your response starting with: {title_header}\n"
        "Keep it under 1200 characters for Telegram."
    )
    cache_key = f"ai:explain:{title.lower()}:{year}:{explain_type}"
    return await _chat(system, user, cache_key, 86400)


async def mood_recommendations(mood: str, preferences: dict, watched_titles: list[str]) -> list[dict]:
    liked_genres = preferences.get("liked_genres", {})
    genre_str = ", ".join(v.get("name", k) for k, v in list(liked_genres.items())[:5]) if liked_genres else "various"
    watched_str = ", ".join(watched_titles[:15]) if watched_titles else "none"

    system = (
        "You are a mood-based movie recommender. Return exactly 5 movies as JSON array. "
        "Each: {\"title\": str, \"year\": int, \"reason\": str, \"confidence\": int (60-99)}. "
        "Only valid JSON array."
    )
    user = (
        f"User mood: {mood}\n"
        f"They like: {genre_str}\n"
        f"Already watched: {watched_str}\n"
        "Recommend 5 perfect movies for this mood. Not already watched."
    )
    text = await _chat(system, user)
    try:
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(text)
    except (json.JSONDecodeError, IndexError):
        logger.error(f"Failed to parse mood recs: {text[:200]}")
        return []


async def compare_movies(movie_a: dict, movie_b: dict) -> str:
    system = (
        "You are a film critic comparing two movies. Be concise, engaging, witty. "
        "Give a brief comparison and declare a winner with reasoning. Under 800 characters."
    )
    user = (
        f"Movie A: {movie_a.get('title')} ({movie_a.get('release_date', '')[:4]})\n"
        f"Rating: {movie_a.get('vote_average')}, Genres: {movie_a.get('genres_text', '')}\n"
        f"Overview: {movie_a.get('overview', '')[:200]}\n\n"
        f"Movie B: {movie_b.get('title')} ({movie_b.get('release_date', '')[:4]})\n"
        f"Rating: {movie_b.get('vote_average')}, Genres: {movie_b.get('genres_text', '')}\n"
        f"Overview: {movie_b.get('overview', '')[:200]}\n\n"
        "Compare them and pick a winner."
    )
    cache_key = f"ai:compare:{movie_a.get('id')}:{movie_b.get('id')}"
    return await _chat(system, user, cache_key, 86400)