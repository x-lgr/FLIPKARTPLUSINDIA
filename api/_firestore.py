import json
import os
import time
import urllib.request
from google.oauth2 import service_account
from google.auth.transport.requests import Request

SCOPES = ["https://www.googleapis.com/auth/datastore"]
_cache = {"token": None, "expiry": 0}


def get_access_token():
    now = time.time()
    if _cache["token"] and now < _cache["expiry"] - 60:
        return _cache["token"]

    sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON", "")
    if not sa_json:
        raise RuntimeError("FIREBASE_SERVICE_ACCOUNT_JSON not set")

    info = json.loads(sa_json)
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    creds.refresh(Request())
    _cache["token"] = creds.token
    _cache["expiry"] = creds.expiry.timestamp() if creds.expiry else now + 3000
    return creds.token


def base_url():
    project_id = os.environ.get("FIREBASE_PROJECT_ID", "")
    return "https://firestore.googleapis.com/v1/projects/%s/databases/(default)/documents" % project_id


def encode_value(value):
    if value is None:
        return {"nullValue": None}
    if isinstance(value, bool):
        return {"booleanValue": value}
    if isinstance(value, int):
        return {"integerValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    if isinstance(value, str):
        return {"stringValue": value}
    if isinstance(value, list):
        return {"arrayValue": {"values": [encode_value(v) for v in value]}}
    if isinstance(value, dict):
        return {"mapValue": {"fields": {k: encode_value(v) for k, v in value.items()}}}
    return {"stringValue": str(value)}


def decode_value(value):
    if "stringValue" in value:
        return value["stringValue"]
    if "integerValue" in value:
        return int(value["integerValue"])
    if "doubleValue" in value:
        return value["doubleValue"]
    if "booleanValue" in value:
        return value["booleanValue"]
    if "nullValue" in value:
        return None
    if "timestampValue" in value:
        return value["timestampValue"]
    if "mapValue" in value:
        fields = value["mapValue"].get("fields", {})
        return {k: decode_value(v) for k, v in fields.items()}
    if "arrayValue" in value:
        values = value["arrayValue"].get("values", [])
        return [decode_value(v) for v in values]
    return None


def decode_doc(doc):
    fields = doc.get("fields", {})
    return {k: decode_value(v) for k, v in fields.items()}


def _request(method, url, token, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Authorization": "Bearer %s" % token}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=8) as resp:
        raw = resp.read()
        return json.loads(raw.decode("utf-8")) if raw else {}


def get_doc(path, token):
    try:
        return _request("GET", "%s/%s" % (base_url(), path), token)
    except Exception:
        return None


def put_doc(path, token, fields):
    return _request("PATCH", "%s/%s" % (base_url(), path), token, {"fields": fields})


def add_doc(path, token, fields):
    return _request("POST", "%s/%s" % (base_url(), path), token, {"fields": fields})


def list_docs(path, token):
    try:
        data = _request("GET", "%s/%s" % (base_url(), path), token)
        return data.get("documents", [])
    except Exception:
        return []


def delete_doc_url(name, token):
    try:
        _request("DELETE", "https://firestore.googleapis.com/v1/%s" % name, token)
    except Exception:
        pass
