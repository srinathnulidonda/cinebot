# 🎬 CineBot — AI-Powered Telegram Movie Companion

Production-grade Telegram bot for movie discovery, tracking, and AI-powered recommendations.

## Features

- **🔍 Search** — Rich movie cards with ratings, cast, posters
- **🧠 Recommend** — AI-powered personalized picks (mood/genre/similar/surprise)
- **📋 Watchlist** — Priority-based watch-later list
- **✅ Watched** — Movie diary with ratings and reviews
- **📺 Where to Watch** — Streaming availability by region
- **🏆 Compare** — Side-by-side movie comparison with AI analysis
- **🤖 Explain** — AI plot/ending/hidden details analysis
- **📊 Stats** — Visual watching statistics with genre breakdown
- **🔔 Alerts** — Release date notifications
- **🎲 Random** — Surprise movie picks with genre filters
- **😊 Mood** — Mood-based recommendations
- **👑 Pro System** — License key monetization with admin management

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Bot Framework | python-telegram-bot v20+ (async) |
| Language | Python 3.11+ |
| Database | PostgreSQL (async via asyncpg + SQLAlchemy 2.0) |
| Cache | Redis |
| Movie Data | TMDb API v3 |
| AI | OpenAI GPT-4o-mini |
| Trailers | YouTube Data API v3 |
| Streaming | Streaming Availability API + TMDb Providers |

## Setup

### 1. Prerequisites

```bash
# PostgreSQL
sudo apt install postgresql
createdb cinebot

# Redis
sudo apt install redis-server
```

### 2. Install Dependencies

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys
```

Required keys:
- `BOT_TOKEN` — From @BotFather
- `DATABASE_URL` — PostgreSQL connection string
- `TMDB_API_KEY` — From themoviedb.org
- `OPENAI_API_KEY` — From platform.openai.com
- `YOUTUBE_API_KEY` — From Google Cloud Console
- `STREAMING_API_KEY` — From RapidAPI
- `ADMIN_IDS` — JSON array of admin Telegram user IDs

### 4. Run

```bash
# Polling mode (development)
python run.py

# Webhook mode (production)
USE_WEBHOOK=true python run.py
```

## Admin Commands

| Command | Description |
|---------|-------------|
| `/admin` | Admin dashboard |
| `/genkey TYPE` | Generate single license key |
| `/genkeys TYPE QTY BATCH` | Bulk generate keys (sends .txt file) |
| `/keyinfo KEY` | Look up key details |
| `/revokekey KEY` | Revoke key + downgrade user |
| `/listkeys [STATUS]` | List keys with filters |
| `/userlookup TELEGRAM_ID` | Look up user details |
| `/giftkey TELEGRAM_ID TYPE` | Gift Pro to a user |
| `/broadcast [all\|pro] MSG` | Send message to users |

Key types: `1M` (30d), `2M` (60d), `3M` (90d), `6M` (180d), `1Y` (365d)

## Free vs Pro

| Feature | Free | Pro |
|---------|------|-----|
| Searches/day | 10 | Unlimited |
| Recommendations/day | 5 | Unlimited |
| AI Explanations/day | 3 | Unlimited |
| Watchlist items | 20 | Unlimited |
| Daily suggestions | Limited | Full |
| Advanced stats | ❌ | ✅ |

## Architecture

```
cinebot/
├── bot/
│   ├── main.py              # App builder, handler/job registration
│   ├── config.py             # Pydantic settings
│   ├── handlers/             # 16 command/callback handlers
│   ├── services/             # External API integrations
│   ├── models/               # SQLAlchemy models + repositories
│   ├── middleware/            # Rate limiting, auth, analytics
│   ├── utils/                # Formatters, keyboards, validators
│   └── jobs/                 # Scheduled tasks
├── run.py                    # Entry point
└── requirements.txt
```

## Scheduled Jobs

| Job | Schedule | Description |
|-----|----------|-------------|
| Daily Suggestion | 09:00 UTC daily | Personalized movie push |
| Release Alerts | Every 6 hours | Notify upcoming releases |
| Subscription Expiry | 00:30 UTC daily | Warnings + auto-downgrade |

## Production Deployment

```bash
# Using systemd
sudo cp cinebot.service /etc/systemd/system/
sudo systemctl enable cinebot
sudo systemctl start cinebot

# Using Docker
docker-compose up -d
```

### Scaling considerations:
- Connection pooling: 20 base + 30 overflow PostgreSQL connections
- Redis connection pool: 50 max connections
- Concurrent update processing enabled
- 24h movie cache, 6h search cache, 12h streaming cache
- Rate limiting via Redis with midnight TTL reset
- Exponential backoff on all external API calls

## License

MIT
```