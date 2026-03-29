<div align="center">

# CineBrainBot

**Your AI-Powered Movie & TV Companion on Telegram**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Telegram](https://img.shields.io/badge/Telegram-Bot-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)](https://core.telegram.org/bots)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-Welcome-brightgreen?style=for-the-badge)](CONTRIBUTING.md)

<br>

[**Try the Bot →**](https://t.me/cinebrainbot) · [Report Bug](../../issues) · [Request Feature](../../issues)

<br>

<img src="https://raw.githubusercontent.com/srinathnulidonda/cinebrainbot/main/bot/assets/cinebrainbot.png" alt="CineBrainBot Demo" width="400">

</div>

---

## ✨ Features

<table>
<tr>
<td width="50%">

### 🔍 Discovery
- **Smart Search** — Movies & TV shows
- **AI Recommendations** — Personalized picks
- **Mood-Based** — Match your vibe
- **Random Pick** — Surprise me!

### 📺 Watch
- **Instant Streaming** — One-tap watch
- **Episode Browser** — Full season navigation
- **Where to Stream** — Platform availability
- **Trailers** — YouTube integration

</td>
<td width="50%">

### 📚 Library
- **Watchlist** — Save for later
- **Watch History** — Track what you've seen
- **Ratings & Reviews** — Personal diary
- **Statistics** — Viewing insights

### 🧠 AI Features
- **Plot Explanations** — Understand any movie
- **Ending Analysis** — Spoiler-free breakdowns
- **Movie Comparisons** — Head-to-head battles
- **Hidden Details** — Easter eggs revealed

</td>
</tr>
</table>

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Redis 6+
- Telegram Bot Token ([BotFather](https://t.me/BotFather))
- TMDB API Key ([themoviedb.org](https://www.themoviedb.org/settings/api))

### Installation

```bash
# Clone the repository
git clone https://github.com/srinathnulidonda/cinebrainbot.git
cd cinebrainbot

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Run the bot
python run.py
```

---

## ⚙️ Configuration

Create a `.env` file in the root directory:

```env
# Bot
BOT_TOKEN=your_telegram_bot_token

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/cinebot
REDIS_URL=redis://localhost:6379/0

# APIs
TMDB_API_KEY=your_tmdb_api_key
YOUTUBE_API_KEY=your_youtube_api_key
GEMINI_API_KEY=your_gemini_api_key

# Optional
ADMIN_IDS=[123456789]
STREAMING_API_KEY=your_rapidapi_key
```

<details>
<summary><b>📋 Full Configuration Reference</b></summary>

| Variable | Description | Required |
|----------|-------------|:--------:|
| `BOT_TOKEN` | Telegram Bot API token | ✅ |
| `DATABASE_URL` | PostgreSQL connection string | ✅ |
| `REDIS_URL` | Redis connection string | ✅ |
| `TMDB_API_KEY` | TMDB API key for movie data | ✅ |
| `YOUTUBE_API_KEY` | YouTube API for trailers | ✅ |
| `GEMINI_API_KEY` | Google AI for explanations | ❌ |
| `GROQ_API_KEY` | Groq AI (fallback) | ❌ |
| `ADMIN_IDS` | List of admin Telegram IDs | ❌ |
| `STREAMING_API_KEY` | RapidAPI streaming data | ❌ |

</details>

---

## 🤖 Commands

| Command | Description |
|---------|-------------|
| `/start` | Start the bot & onboarding |
| `/search <title>` | Search movies & TV shows |
| `/watch <title>` | Watch movies instantly |
| `/recommend` | Get AI recommendations |
| `/watchlist` | Manage your watchlist |
| `/watched` | Your movie diary |
| `/stats` | Viewing statistics |
| `/explain <title>` | AI movie explanations |
| `/compare A vs B` | Compare two movies |
| `/random` | Random movie suggestion |
| `/mood` | Mood-based picks |
| `/alerts` | Release notifications |
| `/where <title>` | Streaming availability |
| `/pro` | View subscription status |
| `/redeem <KEY>` | Redeem a Pro license |
| `/chat` | Live support chat |

---

## 🏗️ Architecture

```
cinebrainbot/
├── run.py                 # Entry point
├── bot/
│   ├── __init__.py        # Custom exceptions
│   ├── config.py          # Settings (pydantic)
│   ├── main.py            # Application builder
│   ├── handlers/          # Command & callback handlers
│   │   ├── search.py
│   │   ├── watch.py
│   │   ├── recommend.py
│   │   └── ...
│   ├── services/          # Business logic
│   │   ├── tmdb_service.py
│   │   ├── ai_service.py
│   │   ├── stream.py
│   │   └── ...
│   ├── models/            # Database models
│   │   ├── engine.py
│   │   ├── user.py
│   │   └── ...
│   ├── middleware/        # Rate limiting, auth
│   ├── jobs/              # Scheduled tasks
│   └── utils/             # Helpers & formatters
└── tests/
```

---

## 🛠️ Tech Stack

<div align="center">

| Layer | Technology |
|:-----:|:----------:|
| **Bot Framework** | ![python-telegram-bot](https://img.shields.io/badge/python--telegram--bot-20.x-blue?style=flat-square) |
| **Database** | ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14+-336791?style=flat-square&logo=postgresql&logoColor=white) |
| **Cache** | ![Redis](https://img.shields.io/badge/Redis-6+-DC382D?style=flat-square&logo=redis&logoColor=white) |
| **ORM** | ![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-red?style=flat-square) |
| **AI** | ![Gemini](https://img.shields.io/badge/Gemini-1.5-4285F4?style=flat-square&logo=google&logoColor=white) |
| **APIs** | ![TMDB](https://img.shields.io/badge/TMDB-API-01D277?style=flat-square) ![YouTube](https://img.shields.io/badge/YouTube-API-FF0000?style=flat-square&logo=youtube&logoColor=white) |
| **Hosting** | ![Render](https://img.shields.io/badge/Render-46E3B7?style=flat-square&logo=render&logoColor=white) |

</div>

---

## 💎 Pro Features

CineBrainBot offers a **Pro subscription** for power users:

| Feature | Free | Pro |
|---------|:----:|:---:|
| Daily Searches | 10 | ∞ |
| AI Recommendations | 5 | ∞ |
| AI Explanations | 3 | ∞ |
| Watchlist Items | 20 | ∞ |
| Priority Support | ❌ | ✅ |
| Daily Suggestions | ❌ | ✅ |

**License Keys:** `CINE-XXXX-XXXX-XXXX-XXXX`

---

## 📊 Admin Dashboard

Admins have access to powerful management tools:

```
/admin        — Dashboard
/genkey       — Generate license key
/genkeys      — Bulk key generation
/broadcast    — Message all users
/userlookup   — User information
/aistatus     — AI provider status
/backend      — System health
/chats        — Active support chats
```

---

## 🔄 Scheduled Jobs

| Job | Schedule | Description |
|-----|----------|-------------|
| Daily Suggestions | 09:00 UTC | Personalized movie picks |
| Release Alerts | Every 6h | Upcoming release notifications |
| Subscription Check | 00:30 UTC | Expiry warnings & downgrades |

---

## 🚢 Deployment

### Render (Recommended)

1. Connect your GitHub repository
2. Set environment variables
3. Deploy with:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python run.py`

### Docker

```bash
docker build -t cinebrainbot .
docker run -d --env-file .env cinebrainbot
```

### Manual

```bash
# Production
python run.py

# Development (with reload)
python -m bot.main
```

---

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) first.

1. Fork the repository
2. Create your branch (`git checkout -b feature/amazing`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- [TMDB](https://www.themoviedb.org/) — Movie & TV data
- [python-telegram-bot](https://python-telegram-bot.org/) — Bot framework
- [Google Gemini](https://ai.google.dev/) — AI capabilities

---

<div align="center">

**Built with ❤️ for movie lovers**

<br>

[![Telegram](https://img.shields.io/badge/Try%20CineBrainBot-Telegram-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)](https://t.me/cinebrainbot)

<sub>If you found this useful, please ⭐ the repo!</sub>

</div>
```

---

## 📁 Additional Files

### `.env.example`

```env
# ═══════════════════════════════════════════
#          CINEBRAINBOT CONFIGURATION
# ═══════════════════════════════════════════

# ─── Bot ────────────────────────────────────
BOT_TOKEN=

# ─── Database ───────────────────────────────
DATABASE_URL=postgresql://user:password@localhost:5432/cinebot
REDIS_URL=redis://localhost:6379/0

# ─── APIs (Required) ────────────────────────
TMDB_API_KEY=
YOUTUBE_API_KEY=

# ─── AI Providers (At least one) ────────────
GEMINI_API_KEY=
GROQ_API_KEY=
OPENROUTER_API_KEY=

# ─── Streaming ──────────────────────────────
STREAMING_API_KEY=
STREAMING_API_HOST=streaming-availability.p.rapidapi.com

# ─── Admin ──────────────────────────────────
ADMIN_IDS=[123456789]

# ─── URLs ───────────────────────────────────
FRONTEND_URL=https://cinebrainplayer.vercel.app
RENDER_EXTERNAL_URL=

# ─── Limits ─────────────────────────────────
FREE_DAILY_SEARCHES=10
FREE_DAILY_EXPLAINS=3
FREE_DAILY_RECOMMENDS=5
FREE_WATCHLIST_LIMIT=20
```

---

### `LICENSE`

```
MIT License

Copyright (c) 2024 CineBrainBot

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```