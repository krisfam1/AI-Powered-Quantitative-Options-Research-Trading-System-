"""Minimal HTTP kill switch for the live trading loop.

Runs as a daemon thread alongside run_live_trading_loop() in main.py.
All three endpoints work from any phone browser — bookmark the /status URL.

Endpoints (all require ?token=YOUR_TOKEN):
  GET  /status?token=…   HTML status page with Stop / Resume buttons
  GET  /stop?token=…     Create STOP_TRADING, redirect to status
  GET  /resume?token=…   Remove STOP_TRADING, redirect to status

Set KILL_SERVER_TOKEN as a Replit Secret before publishing.

Security note: this is a simple bearer-token check suitable for personal use.
The token is visible in your browser's URL bar, so keep it private and avoid
sharing screenshots of the address bar while trading.
"""

import os
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

STOP_FILE = Path("STOP_TRADING")
DEFAULT_PORT = 8080
ET = ZoneInfo("America/New_York")

# ── HTML template ─────────────────────────────────────────────────────────────
_HTML = """\
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Trading Kill Switch</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #0f1117; color: #e2e8f0;
      display: flex; align-items: center; justify-content: center;
      min-height: 100vh; padding: 24px;
    }}
    .card {{
      background: #1a1f2e; border: 1px solid #2d3448;
      border-radius: 12px; padding: 32px 28px; max-width: 420px; width: 100%;
    }}
    h1 {{ font-size: 1.2rem; font-weight: 700; margin-bottom: 4px; }}
    .sub {{ font-size: 0.8rem; color: #64748b; margin-bottom: 24px; }}
    .status-badge {{
      display: inline-flex; align-items: center; gap: 8px;
      padding: 10px 16px; border-radius: 8px;
      font-size: 0.95rem; font-weight: 600; margin-bottom: 28px;
      width: 100%;
    }}
    .running  {{ background: #052e16; color: #4ade80; border: 1px solid #166534; }}
    .paused   {{ background: #450a0a; color: #f87171; border: 1px solid #991b1b; }}
    .dot {{ width: 10px; height: 10px; border-radius: 50%; }}
    .dot-run {{ background: #4ade80; }}
    .dot-pause {{ background: #f87171; }}
    .info {{ font-size: 0.82rem; color: #94a3b8; margin-bottom: 24px; line-height: 1.6; }}
    .info span {{ color: #e2e8f0; }}
    .actions {{ display: flex; gap: 12px; flex-direction: column; }}
    a.btn {{
      display: block; text-align: center; padding: 14px;
      border-radius: 8px; font-size: 0.95rem; font-weight: 600;
      text-decoration: none; transition: opacity .15s;
    }}
    a.btn:hover {{ opacity: .85; }}
    .btn-stop   {{ background: #dc2626; color: #fff; }}
    .btn-resume {{ background: #16a34a; color: #fff; }}
    .btn-refresh {{ background: #1e293b; color: #94a3b8;
                    border: 1px solid #334155; font-size: 0.85rem; padding: 10px; }}
    .footer {{ margin-top: 20px; font-size: 0.75rem; color: #475569; text-align: center; }}
  </style>
</head>
<body>
<div class="card">
  <h1>&#9889; Trading Kill Switch</h1>
  <p class="sub">Paper account — AAPL / TSLA / NVDA / AMD / SMCI / MSTR</p>

  {status_badge}

  <div class="info">
    <div>Time (ET): <span>{time_et}</span></div>
    <div>Market:    <span>{market_status}</span></div>
    <div>Last check: <span>{last_check}</span></div>
  </div>

  <div class="actions">
    {action_button}
    <a class="btn btn-refresh" href="/status?token={token}">&#8635; Refresh status</a>
  </div>

  <p class="footer">
    All actions logged to signal_log.db &bull; Changes take effect on the next 5-min cycle
  </p>
</div>
</body>
</html>
"""


def _render_status(token: str) -> str:
    paused = STOP_FILE.exists()
    now_et = datetime.now(ET)
    time_str = now_et.strftime("%A %b %#d, %H:%M ET")

    # Market status string
    wd = now_et.weekday()
    t  = now_et.time()
    from datetime import time as dtime
    if wd >= 5:
        market = "Weekend — closed"
    elif t < dtime(9, 30):
        market = "Pre-market"
    elif t < dtime(16, 0):
        market = "Open ✓"
    else:
        market = "After-hours — closed"

    # Last signal-log entry
    last_check = "—"
    try:
        import sqlite3, live_trader
        with sqlite3.connect(live_trader.SIGNAL_LOG_DB) as con:
            row = con.execute(
                "SELECT checked_at, ticker, signal_fired FROM signal_log "
                "WHERE ticker NOT LIKE '[%]' "
                "ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if row:
                checked_at, ticker, fired = row
                label = "✓ order" if fired else "– no signal"
                ts = checked_at[:16].replace("T", " ") + " UTC"
                last_check = f"{ticker} ({label}) at {ts}"
    except Exception:
        pass

    if paused:
        badge = (
            '<div class="status-badge paused">'
            '<div class="dot dot-pause"></div>PAUSED — kill switch active</div>'
        )
        action = (
            f'<a class="btn btn-resume" href="/resume?token={token}">'
            "&#9654; Resume trading</a>"
        )
    else:
        badge = (
            '<div class="status-badge running">'
            '<div class="dot dot-run"></div>ACTIVE — loop is running</div>'
        )
        action = (
            f'<a class="btn btn-stop" href="/stop?token={token}">'
            "&#9632; Stop trading</a>"
        )

    return _HTML.format(
        status_badge=badge,
        time_et=time_str,
        market_status=market,
        last_check=last_check,
        action_button=action,
        token=token,
    )


# ── HTTP handler ──────────────────────────────────────────────────────────────
class _Handler(BaseHTTPRequestHandler):
    def _token(self) -> str:
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        return (params.get("token") or [""])[0]

    def _token_ok(self) -> bool:
        expected = os.environ.get("KILL_SERVER_TOKEN", "")
        if not expected:
            return False  # deny all if secret is not configured
        return self._token() == expected

    def _html(self, code: int, body: str) -> None:
        encoded = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _redirect(self, location: str) -> None:
        self.send_response(302)
        self.send_header("Location", location)
        self.end_headers()

    def _plain(self, code: int, body: str) -> None:
        encoded = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        parsed = urlparse(self.path)
        path   = parsed.path

        if not self._token_ok():
            self._plain(403, "403 Forbidden — missing or wrong token.\n"
                            "Add ?token=YOUR_TOKEN to the URL.\n")
            return

        token = self._token()

        if path in ("/", "/status"):
            self._html(200, _render_status(token))

        elif path == "/stop":
            STOP_FILE.touch()
            self._redirect(f"/status?token={token}")

        elif path == "/resume":
            STOP_FILE.unlink(missing_ok=True)
            self._redirect(f"/status?token={token}")

        else:
            self._plain(404, "Not found. Try /status, /stop, or /resume.\n")

    def log_message(self, fmt, *args):
        # Suppress default per-request stdout noise; errors still print
        pass


# ── Public API ────────────────────────────────────────────────────────────────
def start(port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    """Start the kill server in a background daemon thread.

    Returns the server object.  Stops automatically when the process exits
    because the thread is a daemon.
    """
    server = ThreadingHTTPServer(("0.0.0.0", port), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True, name="kill-server")
    thread.start()
    print(f"  Control panel : :{port}  →  GET /status?token=… | /stop | /resume")
    return server
