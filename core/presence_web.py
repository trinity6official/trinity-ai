"""Localhost-only web presence for Trinity."""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Any

from core.presence import PresenceEngine


_LOOPBACKS = {"127.0.0.1", "localhost", "::1"}


_PRESENCE_HTML = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Trinity</title><style>
:root{color-scheme:dark;font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display",Inter,system-ui,sans-serif}
*{box-sizing:border-box}body{margin:0;min-height:100vh;background:#05070a;color:#f5f7fa;display:grid;place-items:center;overflow:hidden}
.wrap{text-align:center;width:min(680px,92vw)}
.orb{width:220px;height:220px;margin:0 auto 42px;border-radius:50%;position:relative;background:radial-gradient(circle at 38% 30%,#fff 0 1%,#79d7ff 5%,#2468ff 28%,#0a1738 62%,#02040a 75%);box-shadow:0 0 28px rgba(74,150,255,.36),0 0 110px rgba(36,104,255,.18);transition:.35s ease}
.orb:after{content:"";position:absolute;inset:-12px;border-radius:inherit;border:1px solid rgba(130,205,255,.22);animation:pulse 2.5s infinite ease-in-out}
body[data-state="listening"] .orb{transform:scale(1.04);box-shadow:0 0 45px rgba(87,214,255,.55),0 0 140px rgba(43,155,255,.28)}
body[data-state="thinking"] .orb,body[data-state="searching"] .orb,body[data-state="using_tool"] .orb{animation:think 2s infinite ease-in-out}
body[data-state="executing"] .orb{box-shadow:0 0 48px rgba(172,110,255,.5),0 0 140px rgba(123,72,255,.25)}
body[data-state="speaking"] .orb{animation:speak .8s infinite alternate ease-in-out}
body[data-state="done"] .orb{transform:scale(1.02);filter:brightness(1.16)}
body[data-state="error"] .orb{filter:hue-rotate(125deg);box-shadow:0 0 50px rgba(255,70,70,.5)}
.name{font-size:42px;font-weight:600;letter-spacing:.22em;margin-right:-.22em}.state{margin-top:14px;font-size:17px;color:#9fb0c4;letter-spacing:.08em;text-transform:uppercase}.detail{height:28px;margin-top:10px;color:#d7e1ee;font-size:15px}.meta{margin-top:34px;color:#65768a;font-size:13px;line-height:1.7}.dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:#5ee398;margin-right:8px;box-shadow:0 0 10px rgba(94,227,152,.6)}
@keyframes pulse{50%{transform:scale(1.08);opacity:.35}}@keyframes think{50%{transform:scale(.96);filter:hue-rotate(20deg)}}@keyframes speak{to{transform:scale(1.06);filter:brightness(1.22)}}
</style></head><body data-state="idle"><main class="wrap"><div class="orb"></div><div class="name">TRINITY</div><div id="state" class="state">IDLE</div><div id="detail" class="detail">Ready</div><div class="meta"><span class="dot"></span>Local runtime<br><span id="app"></span></div></main>
<script>
async function refresh(){try{const r=await fetch('/api/presence',{cache:'no-store'});const d=await r.json();document.body.dataset.state=d.state;document.getElementById('state').textContent=d.state.replace('_',' ');document.getElementById('detail').textContent=d.detail||'';document.getElementById('app').textContent=d.frontmost_app?'Active: '+d.frontmost_app:''}catch(e){document.getElementById('detail').textContent='Local runtime unavailable'}}
refresh();setInterval(refresh,500);
</script></body></html>'''


class PresenceServer:
    """Tiny read-only HTTP server bound to localhost by default."""

    def __init__(
        self,
        presence: PresenceEngine,
        *,
        awareness: Any = None,
        host: str = "127.0.0.1",
        port: int = 8765,
    ) -> None:
        self.presence = presence
        self.awareness = awareness
        self.host = host
        self.port = port
        self._server: ThreadingHTTPServer | None = None
        self._thread: Thread | None = None

    def payload(self) -> dict:
        data = self.presence.snapshot().to_dict()
        if self.awareness is not None:
            data["frontmost_app"] = self.awareness.snapshot().frontmost_app
        else:
            data["frontmost_app"] = None
        return data

    def _handler(self):
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                if self.path == "/api/presence":
                    body = json.dumps(owner.payload()).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers(); self.wfile.write(body); return
                if self.path in {"/", "/index.html"}:
                    body = _PRESENCE_HTML.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers(); self.wfile.write(body); return
                self.send_error(404)

            def log_message(self, fmt, *args):
                return

        return Handler

    def start(self) -> bool:
        if self._server is not None:
            return True
        if self.host.strip().lower() not in _LOOPBACKS:
            return False
        try:
            self._server = ThreadingHTTPServer((self.host, self.port), self._handler())
        except OSError:
            self._server = None
            return False
        self.port = self._server.server_address[1]
        self._thread = Thread(target=self._server.serve_forever, name="trinity-presence", daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        server, thread = self._server, self._thread
        self._server = None; self._thread = None
        if server is not None:
            server.shutdown(); server.server_close()
        if thread is not None:
            thread.join(timeout=2)
