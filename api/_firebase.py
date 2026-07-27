import json
import os
import time
from urllib import error, parse, request as urlrequest

from google.auth.transport.requests import Request
from google.oauth2 import service_account


SERVICE_ACCOUNT_JSON = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
SERVICE_ACCOUNT_INFO = json.loads(SERVICE_ACCOUNT_JSON) if SERVICE_ACCOUNT_JSON else {}
PROJECT_ID = (os.environ.get("FIREBASE_PROJECT_ID", "").strip() or SERVICE_ACCOUNT_INFO.get("project_id", "").strip())
API_KEY = os.environ.get("FIREBASE_API_KEY", "").strip()
DATABASE_URL = os.environ.get("FIREBASE_DATABASE_URL", "").strip().rstrip("/")
BASE_URL = "https://firestore.googleapis.com/v1"
SCOPES = ["https://www.googleapis.com/auth/datastore"]
_CREDENTIALS = None


class FirebaseConfigError(RuntimeError):
    pass


def _require_config():
    if not PROJECT_ID:
        raise FirebaseConfigError("Set FIREBASE_PROJECT_ID or FIREBASE_SERVICE_ACCOUNT_JSON in Vercel environment variables.")
    if not SERVICE_ACCOUNT_INFO and not DATABASE_URL and not API_KEY:
        raise FirebaseConfigError("Set FIREBASE_DATABASE_URL or FIREBASE_SERVICE_ACCOUNT_JSON for backend sync.")


def _credentials():
    global _CREDENTIALS
    if not SERVICE_ACCOUNT_INFO:
        return None
    if _CREDENTIALS is None:
        _CREDENTIALS = service_account.Credentials.from_service_account_info(
            SERVICE_ACCOUNT_INFO,
            scopes=SCOPES
        )
    if not _CREDENTIALS.valid:
        _CREDENTIALS.refresh(Request())
    return _CREDENTIALS


def _headers():
    headers = {"Content-Type": "application/json"}
    creds = _credentials()
    if creds:
        headers["Authorization"] = f"Bearer {creds.token}"
    return headers


def _query():
    return parse.urlencode({"key": API_KEY}) if API_KEY and not SERVICE_ACCOUNT_INFO else ""


def _url(path):
    _require_config()
    safe_path = path.lstrip("/")
    query = _query()
    suffix = f"?{query}" if query else ""
    return f"{BASE_URL}/projects/{PROJECT_ID}/databases/(default)/documents/{safe_path}{suffix}"


def _run_query_url():
    _require_config()
    query = _query()
    suffix = f"?{query}" if query else ""
    return f"{BASE_URL}/projects/{PROJECT_ID}/databases/(default)/documents:runQuery{suffix}"


def _request(method, url, payload=None):
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = urlrequest.Request(url, data=data, method=method, headers=_headers())
    try:
        with urlrequest.urlopen(req, timeout=12) as res:
            raw = res.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Firestore HTTP {exc.code}: {body[:240]}")


def _rtdb_url(path):
    if not DATABASE_URL:
        raise FirebaseConfigError("Set FIREBASE_DATABASE_URL in Vercel environment variables.")
    return f"{DATABASE_URL}/{path.strip('/')}.json"


def _rtdb_request(method, path, payload=None):
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = urlrequest.Request(_rtdb_url(path), data=data, method=method, headers=headers)
    try:
        with urlrequest.urlopen(req, timeout=12) as res:
            raw = res.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Realtime Database HTTP {exc.code}: {body[:240]}")


def encode_value(value):
    if value is None:
        return {"nullValue": None}
    if isinstance(value, bool):
        return {"booleanValue": value}
    if isinstance(value, int) and not isinstance(value, bool):
        return {"integerValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    if isinstance(value, str):
        return {"stringValue": value}
    if isinstance(value, list):
        if not value:
            return {"arrayValue": {}}
        return {"arrayValue": {"values": [encode_value(item) for item in value]}}
    if isinstance(value, dict):
        return {"mapValue": {"fields": {str(k): encode_value(v) for k, v in value.items()}}}
    return {"stringValue": str(value)}


def decode_value(field):
    if not isinstance(field, dict):
        return None
    if "nullValue" in field:
        return None
    if "booleanValue" in field:
        return field["booleanValue"]
    if "integerValue" in field:
        return int(field["integerValue"])
    if "doubleValue" in field:
        return field["doubleValue"]
    if "stringValue" in field:
        return field["stringValue"]
    if "arrayValue" in field:
        values = field.get("arrayValue", {}).get("values", [])
        return [decode_value(item) for item in values]
    if "mapValue" in field:
        fields = field.get("mapValue", {}).get("fields", {})
        return {key: decode_value(value) for key, value in fields.items()}
    if "timestampValue" in field:
        return field["timestampValue"]
    return None


def get_store_value(key):
    if DATABASE_URL and not SERVICE_ACCOUNT_INFO:
        doc = _rtdb_request("GET", f"store/{key}")
        if isinstance(doc, dict) and "value" in doc:
            return doc.get("value")
        return doc

    try:
        doc = _request("GET", _url(f"store/{parse.quote(key)}"))
    except RuntimeError as exc:
        if "HTTP 404" in str(exc):
            if key == "banners":
                return list_banner_values()
            return None
        raise
    return decode_value(doc.get("fields", {}).get("value"))


def set_store_value(key, value):
    if DATABASE_URL and not SERVICE_ACCOUNT_INFO:
        payload = {"value": value, "updatedAt": int(time.time() * 1000)}
        return _rtdb_request("PUT", f"store/{key}", payload)

    payload = {"fields": {"value": encode_value(value), "updatedAt": encode_value(int(time.time() * 1000))}}
    return _request("PATCH", _url(f"store/{parse.quote(key)}"), payload)


def create_visit(payload):
    if DATABASE_URL and not SERVICE_ACCOUNT_INFO:
        return _rtdb_request("POST", "store_visits", payload)

    doc = {"fields": {key: encode_value(value) for key, value in payload.items()}}
    return _request("POST", _url("store_visits"), doc)


def list_banner_values():
    payload = {
        "structuredQuery": {
            "from": [{"collectionId": "store_banners"}],
            "orderBy": [{"field": {"fieldPath": "idx"}, "direction": "ASCENDING"}]
        }
    }
    rows = _request("POST", _run_query_url(), payload)
    values = []
    for row in rows:
        doc = row.get("document") or {}
        if not doc:
            continue
        value = decode_value(doc.get("fields", {}).get("value"))
        if isinstance(value, str) and value.strip():
            values.append(value)
    return values


def list_visits(limit):
    if DATABASE_URL and not SERVICE_ACCOUNT_INFO:
        rows = _rtdb_request("GET", "store_visits") or {}
        visits = list(rows.values()) if isinstance(rows, dict) else []
        return sorted(visits, key=lambda item: int(item.get("ts") or 0), reverse=True)[:min(max(int(limit or 5000), 1), 5000)]

    payload = {
        "structuredQuery": {
            "from": [{"collectionId": "store_visits"}],
            "orderBy": [{"field": {"fieldPath": "ts"}, "direction": "DESCENDING"}],
            "limit": min(max(int(limit or 5000), 1), 5000)
        }
    }
    rows = _request("POST", _run_query_url(), payload)
    visits = []
    for row in rows:
        doc = row.get("document") or {}
        if not doc:
            continue
        fields = doc.get("fields") or {}
        visits.append({key: decode_value(value) for key, value in fields.items()})
    return visits
