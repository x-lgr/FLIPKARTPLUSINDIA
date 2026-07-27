import json
from http.server import BaseHTTPRequestHandler
from urllib import parse

from _firebase import FirebaseConfigError, get_store_value, set_store_value


ALLOWED_KEYS = {"products", "upi", "banners"}


class handler(BaseHTTPRequestHandler):
    def _send(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _key(self):
        params = parse.parse_qs(parse.urlparse(self.path).query)
        key = (params.get("key") or [""])[0].strip()
        return key if key in ALLOWED_KEYS else ""

    def do_GET(self):
        key = self._key()
        if not key:
            self._send(400, {"ok": False, "error": "Invalid store key."})
            return

        try:
            self._send(200, {"ok": True, "key": key, "value": get_store_value(key)})
        except FirebaseConfigError as exc:
            self._send(500, {"ok": False, "error": str(exc)})
        except Exception as exc:
            self._send(502, {"ok": False, "error": str(exc)})

    def do_POST(self):
        key = self._key()
        if not key:
            self._send(400, {"ok": False, "error": "Invalid store key."})
            return

        try:
            length = int(self.headers.get("Content-Length") or "0")
            data = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            value = data.get("value")
            set_store_value(key, value)
            self._send(200, {"ok": True, "key": key})
        except FirebaseConfigError as exc:
            self._send(500, {"ok": False, "error": str(exc)})
        except Exception as exc:
            self._send(502, {"ok": False, "error": str(exc)})
