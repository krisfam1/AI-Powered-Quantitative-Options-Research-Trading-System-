from dotenv import load_dotenv
load_dotenv()

"""Status/kill-switch control panel for the options shadow loop.

Shares the same STOP_TRADING file as the stock bot's kill switch -- both
systems pause together. Runs on a separate port (8081 by default) so it
doesn't conflict with the stock bot's control panel on 8080.
"""

import os
import sqlite3
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
STOP_FILE = Path("STOP_TRADING")
DEFAULT_PORT = 8081

_KILL_TOKEN = os.environ.get("KILL_SERVER_TOKEN", "")


def _render_options_status(token: str) -> str:
    from live_options_trader import OPTIONS_SHADOW_MODE
    paused = STOP_FILE.exists()
    now_et = datetime.now(ET)
    time_str = now_et.strftime("%A %b %#d, %H:%M ET")

    last_check = "\u2014"
    try:
        with sqlite3.connect("options_signal_log.db") as con:
            row = con.execute(
                "SELECT checked_at, ticker, signal_fired FROM options_signal_log "
                "ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if row:
                checked_at, ticker, fired = row
                label = "shadow signal" if fired else "no signal"
                ts = checked_at[:16].replace("T", " ") + " UTC"
                last_check = ticker + " (" + label + ") at " + ts
    except Exception:
        pass

    if paused:
        badge = (
            '<div class="status-badge paused">'
            '<div class="dot dot-pause"></div>PAUSED (shared kill switch)</div>'
        )
        action = (
            '<a class="btn btn-resume" href="/resume?token=' + token + '">'
            "&#9654; Resume trading</a>"
        )
    else:
        badge = (
            '<div class="status-badge running">'
            '<div class="dot dot-run"></div>ACTIVE \u2014 ' + ("shadow loop running" if OPTIONS_SHADOW_MODE else "LIVE loop running") + '</div>'
        )
        action = (
            '<a class="btn btn-stop" href="/stop?token=' + token + '">'
            "&#9632; Stop trading</a>"
        )

    html = "<!doctype html><html><head><meta charset='utf-8'>"
    html += "<meta name='viewport' content='width=device-width, initial-scale=1'>"
    html += "<title>Options Shadow Loop</title></head><body style='font-family:sans-serif;background:#0f1117;color:#e2e8f0;padding:24px'>"
    mode_label = "SHADOW MODE -- no real orders" if OPTIONS_SHADOW_MODE else "LIVE -- real orders active"
    html += "<h1>Options Loop (" + mode_label + ")</h1>"
    html += "<p>" + badge + "</p>"
    html += "<p>Time (ET): " + time_str + "</p>"
    html += "<p>Last check: " + last_check + "</p>"
    html += "<p>" + action + "</p>"
    html += "<p><a href='/status?token=" + token + "'>Refresh</a></p>"
    html += "</body></html>"
    return html


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        token = params.get("token", [""])[0]

        if token != _KILL_TOKEN or not _KILL_TOKEN:
            self.send_response(403)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"403 Forbidden -- missing or wrong token.")
            return

        if parsed.path == "/stop":
            STOP_FILE.write_text("stopped")
        elif parsed.path == "/resume":
            if STOP_FILE.exists():
                STOP_FILE.unlink()

        html = _render_options_status(token)
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def log_message(self, format, *args):
        pass


def start(port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("0.0.0.0", port), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True, name="options-kill-server")
    thread.start()
    print("  Options control panel : :" + str(port) + "  ->  GET /status?token=...  | /stop | /resume")
    return server


if __name__ == "__main__":
    start()
    print("Options status server running. Press Ctrl+C to stop.")
    import time
    while True:
        time.sleep(60)