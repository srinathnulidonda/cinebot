# bot/jobs/status.py
from __future__ import annotations
import logging
import os
import platform
import threading
import time
import asyncio
import json
import traceback
import urllib.request
from datetime import datetime, timezone

import psutil
from flask import Flask, Response, jsonify, request
from flask_cors import CORS

logger = logging.getLogger(__name__)

PORT: int = int(os.environ.get("PORT", 10000))
PING_INTERVAL: int = int(os.environ.get("PING_INTERVAL", 300))
ENVIRONMENT: str = os.environ.get("ENVIRONMENT", "production")
STATUS_SECRET: str = os.environ.get("STATUS_SECRET", "")
FRONTEND_URL: str = os.environ.get("FRONTEND_URL", "https://cinebrainplayer.vercel.app")
VIDEASY_BASE: str = os.environ.get("VIDEASY_BASE_URL", "https://player.videasy.net")
VIDKING_BASE: str = os.environ.get("VIDKING_BASE_URL", "https://www.vidking.net")

START_TIME: float = time.time()

_lock = threading.Lock()
_bot_state: dict = {"running": False, "mode": "polling"}


def _run_async(coro, timeout: float = 20.0):
    from bot.models.engine import get_bot_loop
    loop = get_bot_loop()
    if loop is None or loop.is_closed():
        raise RuntimeError("Bot event loop not available")
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    try:
        return future.result(timeout=timeout)
    except asyncio.TimeoutError:
        future.cancel()
        raise TimeoutError("Async operation timed out")


def set_bot_running(running: bool, mode: str = "polling") -> None:
    with _lock:
        _bot_state["running"] = running
        _bot_state["mode"] = mode


def _uptime() -> tuple[str, int]:
    total = int(time.time() - START_TIME)
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}h {minutes}m {seconds}s", total


def _system_metrics() -> dict:
    try:
        proc = psutil.Process()
        mem_mb = round(proc.memory_info().rss / (1024 * 1024), 1)
        cpu = psutil.cpu_percent(interval=0.5)
    except (psutil.Error, OSError):
        mem_mb = 0.0
        cpu = 0.0
    return {
        "python_version": platform.python_version(),
        "cpu_percent": cpu,
        "memory_mb": mem_mb,
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _api_response(data=None, error=None, status=200):
    return jsonify({
        "success": error is None,
        "data": data,
        "error": error,
    }), status


def _safe_async(coro, fallback=None):
    try:
        return _run_async(coro)
    except (RuntimeError, TimeoutError) as e:
        logger.warning("Async bridge: %s", e)
        return fallback
    except Exception as e:
        logger.error("Async error: %s\n%s", e, traceback.format_exc())
        return fallback


app = Flask(__name__)
CORS(
    app,
    origins=[
        FRONTEND_URL,
        "http://localhost:3000",
        "http://localhost:5173",
        "https://cinebrainplayer.vercel.app",
    ],
    methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    supports_credentials=True,
    max_age=3600,
)

app.logger.setLevel(logging.ERROR)
logging.getLogger("werkzeug").setLevel(logging.ERROR)


@app.errorhandler(500)
def handle_500(e):
    logger.error(f"Internal server error: {e}")
    return _api_response(error="Internal server error", status=500)


@app.errorhandler(404)
def handle_404(e):
    return _api_response(error="Not found", status=404)


@app.route("/")
def root() -> Response:
    return Response("CineBrainBot is running!", status=200, mimetype="text/plain")


@app.route("/health")
def health():
    return jsonify({"status": "alive"}), 200


@app.route("/bot/services/status")
def detailed_status():
    if STATUS_SECRET:
        header = request.headers.get("Authorization", "")
        if header != f"Bearer {STATUS_SECRET}":
            return jsonify({"error": "unauthorized"}), 401
    human, seconds = _uptime()
    with _lock:
        bot_snapshot = dict(_bot_state)
    try:
        from bot import __version__ as version
    except ImportError:
        version = "1.0.0"
    body = {
        "status": "healthy",
        "service": "CineBrainBot",
        "version": version,
        "environment": ENVIRONMENT,
        "timestamp": _now_iso(),
        "uptime": {"human": human, "seconds": seconds},
        "system": _system_metrics(),
        "bot": bot_snapshot,
    }
    return jsonify(body), 200


@app.route("/embed/movie/<int:tmdb_id>")
def embed_movie(tmdb_id: int):
    from flask import redirect
    server = request.args.get("server", "videasy")
    color = request.args.get("color", "e50914")

    if server == "vidking":
        autoplay = request.args.get("autoPlay", "true")
        url = f"{VIDKING_BASE}/embed/movie/{tmdb_id}?color={color}&autoPlay={autoplay}"
    else:
        overlay = request.args.get("overlay", "true")
        url = f"{VIDEASY_BASE}/movie/{tmdb_id}?color={color}&overlay={overlay}"

    return redirect(url)


@app.route("/embed/tv/<int:tmdb_id>/<int:season>/<int:episode>")
def embed_tv(tmdb_id: int, season: int, episode: int):
    from flask import redirect
    server = request.args.get("server", "videasy")
    color = request.args.get("color", "e50914")

    if server == "vidking":
        autoplay = request.args.get("autoPlay", "true")
        url = (
            f"{VIDKING_BASE}/embed/tv/{tmdb_id}/{season}/{episode}"
            f"?color={color}&autoPlay={autoplay}"
            f"&nextEpisode=true&episodeSelector=true"
        )
    else:
        url = (
            f"{VIDEASY_BASE}/tv/{tmdb_id}/{season}/{episode}"
            f"?color={color}&nextEpisode=true"
            f"&autoplayNextEpisode=true&episodeSelector=true&overlay=true"
        )

    return redirect(url)


@app.route("/api/sources/movie/<int:tmdb_id>")
def api_movie_sources(tmdb_id: int):
    try:
        from bot.services.stream import get_movie_sources
        data = _safe_async(get_movie_sources(tmdb_id))
        if data is None:
            return _api_response(error="Failed to fetch sources", status=502)
        return _api_response(data)
    except Exception as e:
        logger.error(f"API movie sources error: {e}")
        return _api_response(error="Service unavailable", status=503)


@app.route("/api/sources/tv/<int:tmdb_id>/<int:season>/<int:episode>")
def api_tv_sources(tmdb_id: int, season: int, episode: int):
    try:
        from bot.services.stream import get_tv_sources
        data = _safe_async(get_tv_sources(tmdb_id, season, episode))
        if data is None:
            return _api_response(error="Failed to fetch sources", status=502)
        return _api_response(data)
    except Exception as e:
        logger.error(f"API TV sources error: {e}")
        return _api_response(error="Service unavailable", status=503)


@app.route("/api/tv/<int:tmdb_id>/seasons")
def api_tv_seasons(tmdb_id: int):
    try:
        from bot.services.stream import get_tv_seasons
        data = _safe_async(get_tv_seasons(tmdb_id))
        if data is None:
            return _api_response(error="TV show not found", status=404)
        return _api_response(data)
    except Exception as e:
        logger.error(f"API TV seasons error: {e}")
        return _api_response(error="Service unavailable", status=503)


@app.route("/api/movie/<int:tmdb_id>/info")
def api_movie_info(tmdb_id: int):
    try:
        from bot.services.stream import get_movie_info
        data = _safe_async(get_movie_info(tmdb_id))
        if data is None:
            return _api_response(error="Movie not found", status=404)
        return _api_response(data)
    except Exception as e:
        logger.error(f"API movie info error: {e}")
        return _api_response(error="Service unavailable", status=503)


@app.route("/api/tv/<int:tmdb_id>/info")
def api_tv_info(tmdb_id: int):
    try:
        from bot.services.stream import get_tv_info
        data = _safe_async(get_tv_info(tmdb_id))
        if data is None:
            return _api_response(error="TV show not found", status=404)
        return _api_response(data)
    except Exception as e:
        logger.error(f"API TV info error: {e}")
        return _api_response(error="Service unavailable", status=503)


@app.route("/api/progress", methods=["POST"])
def api_save_progress():
    try:
        body = request.get_json(silent=True)
        if not body:
            return _api_response(error="No data provided", status=400)
        required = ["user_id", "media_id", "media_type"]
        for field in required:
            if field not in body:
                return _api_response(error=f"Missing field: {field}", status=400)
        from bot.services.stream import save_progress
        data = _safe_async(save_progress(
            user_id=int(body.get("user_id", 0)),
            media_id=int(body.get("media_id", 0)),
            media_type=str(body.get("media_type", "movie")),
            progress=float(body.get("progress", 0)),
            current_time=float(body.get("current_time", 0)),
            duration=float(body.get("duration", 0)),
            season=body.get("season"),
            episode=body.get("episode"),
        ))
        if data is None:
            return _api_response(error="Failed to save progress", status=502)
        return _api_response(data)
    except (ValueError, TypeError) as e:
        return _api_response(error=f"Invalid data: {e}", status=400)
    except Exception as e:
        logger.error(f"API save progress error: {e}")
        return _api_response(error="Service unavailable", status=503)


@app.route("/api/progress/<int:user_id>/<int:media_id>")
def api_get_progress(user_id: int, media_id: int):
    try:
        media_type = request.args.get("type", "movie")
        season = request.args.get("season", type=int)
        episode = request.args.get("episode", type=int)
        from bot.services.stream import get_progress
        data = _safe_async(get_progress(user_id, media_id, media_type, season, episode))
        return _api_response(data=data or {})
    except Exception as e:
        logger.error(f"API get progress error: {e}")
        return _api_response(error="Service unavailable", status=503)


def start_server() -> threading.Thread:
    def _serve() -> None:
        app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)

    thread = threading.Thread(target=_serve, daemon=True, name="StatusServer")
    thread.start()
    logger.info("🚀 Status server started on 0.0.0.0:%d", PORT)
    return thread


def start_self_ping() -> threading.Thread | None:
    base_url = os.environ.get("RENDER_EXTERNAL_URL") or os.environ.get("STATUS_URL")
    if not base_url:
        logger.warning("⚠️  RENDER_EXTERNAL_URL / STATUS_URL not set — self-ping disabled")
        return None

    ping_url = f"{base_url.rstrip('/')}/health"

    def _loop_fn() -> None:
        time.sleep(30)
        while True:
            try:
                req = urllib.request.Request(ping_url, method="GET")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    logger.info("🏓 Self-ping → %d", resp.status)
            except Exception as exc:
                logger.warning("🏓 Self-ping failed: %s", exc)
            time.sleep(PING_INTERVAL)

    thread = threading.Thread(target=_loop_fn, daemon=True, name="SelfPing")
    thread.start()
    logger.info("🏓 Self-ping target: %s  (every %ds)", ping_url, PING_INTERVAL)
    return thread