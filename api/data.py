import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from http.server import BaseHTTPRequestHandler
from _firestore import get_access_token, get_doc, list_docs, decode_doc


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        result = {
            "products": [],
            "upi": {"upiId": "", "name": "Store", "note": "Order Payment"},
            "banners": []
        }

        try:
            token = get_access_token()

            products_doc = get_doc("store/products", token)
            if products_doc and "fields" in products_doc:
                val = decode_doc(products_doc).get("value")
                if isinstance(val, list):
                    result["products"] = val

            upi_doc = get_doc("store/upi", token)
            if upi_doc and "fields" in upi_doc:
                val = decode_doc(upi_doc).get("value")
                if isinstance(val, dict):
                    result["upi"] = val

            banner_docs = list_docs("store_banners", token)
            items = []
            for doc in banner_docs:
                decoded = decode_doc(doc)
                v = decoded.get("value")
                if isinstance(v, str) and v.strip():
                    items.append((decoded.get("idx", 0), v))
            items.sort(key=lambda x: x[0])
            result["banners"] = [v for _, v in items]
        except Exception as e:
            print("data.py error:", e)

        body = json.dumps({"ok": True, "data": result}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "public, s-maxage=300, stale-while-revalidate=60")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
