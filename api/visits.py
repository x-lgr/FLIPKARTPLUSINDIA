import json
import time
from http.server import BaseHTTPRequestHandler
from urllib import parse

from _firebase import FirebaseConfigError, create_visit, list_visits


def _client_ip(headers):
    forwarded = headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return headers.get("x-real-ip", "unknown").strip() or "unknown"


def _stats(visits):
    ip_count = {}
    for visit in visits:
        ip = str(visit.get("ip") or "unknown").strip() or "unknown"
        ip_count[ip] = ip_count.get(ip, 0) + 1

    total = len(visits)
    unique = len(ip_count)
    top_ips = sorted(ip_count.items(), key=lambda item: item[1], reverse=True)[:8]
    return {
        "total": total,
        "uniqueIps": unique,
        "repeatVisits": max(total - unique, 0),
        "topIps": [{"ip": ip, "count": count} for ip, count in top_ips]
    }


class handler(BaseHTTPRequestHandler):
    def _send(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        try:
            params = parse.parse_qs(parse.urlparse(self.path).query)
            limit = int((params.get("limit") or ["5000"])[0])
            self._send(200, {"ok": True, "stats": _stats(list_visits(limit))})
        except FirebaseConfigError as exc:
            self._send(500, {"ok": False, "error": str(exc)})
        except Exception as exc:
            self._send(502, {"ok": False, "error": str(exc)})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length") or "0")
            data = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            payload = {
                "ip": _client_ip(self.headers),
                "ua": str(data.get("ua") or "")[:600],
                "path": str(data.get("path") or "")[:200],
                "ts": int(data.get("ts") or time.time() * 1000)
            }
            create_visit(payload)
            self._send(200, {"ok": True, "ip": payload["ip"]})
        except FirebaseConfigError as exc:
            self._send(500, {"ok": False, "error": str(exc)})
        except Exception as exc:
            self._send(502, {"ok": False, "error": str(exc)})
