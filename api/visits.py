import json
import os
import sys
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from http.server import BaseHTTPRequestHandler
from _firestore import get_access_token, add_doc, list_docs, decode_doc, encode_value

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
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            payload = {}

        try:
            token = get_access_token()
            fields = {
                "ip": encode_value(str(payload.get("ip", "unknown"))[:64]),
                "ua": encode_value(str(payload.get("ua", ""))[:256]),
                "path": encode_value(str(payload.get("path", ""))[:128]),
                "ts": encode_value(int(time.time() * 1000))
            }
            add_doc("store_visits", token, fields)
            self._send(200, {"ok": True})
        except Exception as e:
            self._send(500, {"ok": False, "error": str(e)})

    def do_GET(self):
        admin_token = os.environ.get("ADMIN_TOKEN", "")
        provided = self.headers.get("x-admin-token", "")
        if not admin_token or provided != admin_token:
            self._send(401, {"ok": False, "error": "unauthorized"})
            return

        try:
            token = get_access_token()
            docs = list_docs("store_visits", token)
            ip_count = {}
            for doc in docs:
                data = decode_doc(doc)
                ip = str(data.get("ip") or "unknown").strip() or "unknown"
                ip_count[ip] = ip_count.get(ip, 0) + 1

            total = len(docs)
            ips = list(ip_count.keys())
            top_ips = sorted(
                [{"ip": ip, "count": c} for ip, c in ip_count.items()],
                key=lambda x: x["count"], reverse=True
            )[:8]

            self._send(200, {
                "ok": True,
                "stats": {
                    "total": total,
                    "uniqueIps": len(ips),
                    "repeatVisits": max(total - len(ips), 0),
                    "topIps": top_ips
                }
            })
        except Exception as e:
            self._send(500, {"ok": False, "error": str(e)})
