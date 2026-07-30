import json
import os
import sys
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from http.server import BaseHTTPRequestHandler
from _firestore import get_access_token, put_doc, list_docs, delete_doc_url, encode_value


class handler(BaseHTTPRequestHandler):
    def _send(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        admin_token = os.environ.get("ADMIN_TOKEN", "")
        provided = self.headers.get("x-admin-token", "")
        if not admin_token or provided != admin_token:
            self._send(401, {"ok": False, "error": "unauthorized"})
            return

        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            self._send(400, {"ok": False, "error": "invalid json"})
            return

        action = payload.get("action")
        value = payload.get("value")

        try:
            token = get_access_token()

            if action in ("products", "upi"):
                fields = {
                    "value": encode_value(value),
                    "updatedAt": encode_value(int(time.time() * 1000))
                }
                put_doc("store/%s" % action, token, fields)
                self._send(200, {"ok": True})
                return

            if action == "banners":
                old_docs = list_docs("store_banners", token)
                for doc in old_docs:
                    name = doc.get("name", "")
                    if name:
                        delete_doc_url(name, token)

                items = [v for v in (value or []) if isinstance(v, str) and v.strip()]
                for idx, v in enumerate(items):
                    doc_id = "b_" + str(idx).zfill(3)
                    fields = {
                        "idx": encode_value(idx),
                        "value": encode_value(v),
                        "updatedAt": encode_value(int(time.time() * 1000))
                    }
                    put_doc("store_banners/%s" % doc_id, token, fields)

                self._send(200, {"ok": True, "count": len(items)})
                return

            self._send(400, {"ok": False, "error": "unknown action"})
        except Exception as e:
            self._send(500, {"ok": False, "error": str(e)})
