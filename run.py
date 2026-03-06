# run.py
from bot.config import get_settings


def main():
    settings = get_settings()
    if settings.USE_WEBHOOK:
        from bot.main import run_webhook
        run_webhook()
    else:
        from bot.main import run_polling
        run_polling()


if __name__ == "__main__":
    main()