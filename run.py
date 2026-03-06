# run.py
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import os


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"CineBot is running!")

    def log_message(self, format, *args):
        pass


def start_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    print(f"Health server running on port {port}")
    server.serve_forever()


def main():
    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()

    from bot.config import get_settings
    settings = get_settings()
    if settings.USE_WEBHOOK:
        from bot.main import run_webhook
        run_webhook()
    else:
        from bot.main import run_polling
        run_polling()


if __name__ == "__main__":
    main()