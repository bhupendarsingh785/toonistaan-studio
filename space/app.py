"""astra-audio — AppSail par chalne wala chhota server (sirf Python stdlib).

Port: X_ZOHO_CATALYST_LISTEN_PORT -> PORT -> 9000 (AppSail ka default).
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(os.environ.get("X_ZOHO_CATALYST_LISTEN_PORT")
           or os.environ.get("PORT")
           or 7860)


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        b = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path.startswith("/health"):
            return self._send(200, json.dumps({"ok": True, "service": "astra-audio"}))
        if self.path == "/" or self.path.startswith("/index"):
            html = ("<!doctype html><meta name=viewport content='width=device-width,initial-scale=1'>"
                    "<body style='font-family:system-ui;background:#0b1020;color:#e8ecf8;padding:24px'>"
                    "<h2>astra-audio chal raha hai</h2>"
                    "<p>/health theek hai. Engine jodne par /render chalega.</p></body>")
            return self._send(200, html, "text/html; charset=utf-8")
        return self._send(404, json.dumps({"error": "path nahi mila"}))

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            body = {}
        if self.path.startswith("/render"):
            return self._send(501, json.dumps({"error": "engine abhi juda nahi", "mila": bool(body)}))
        return self._send(404, json.dumps({"error": "path nahi mila"}))

    def log_message(self, fmt, *a):
        sys.stderr.write("astra: %s - %s\n" % (self.address_string(), fmt % a))


if __name__ == "__main__":
    print("astra-audio server shuru, port %d" % PORT, flush=True)
    srv = HTTPServer(("0.0.0.0", PORT), H)
    print("astra-audio listening on 0.0.0.0:%d" % PORT, flush=True)
    srv.serve_forever()
