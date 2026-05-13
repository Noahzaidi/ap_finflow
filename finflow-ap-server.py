from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import request, error
from datetime import datetime, timezone
import json
import os
import sqlite3


HOST = "127.0.0.1"
PORT = 8787
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "finflow.db"
SERVER_VERSION = "2026-05-12-error-detail"


def load_env_file():
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().lstrip("\ufeff")
        value = value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


def normalize_api_key(value):
    raw = str(value or "").strip()
    if raw.lower().startswith("bearer "):
        raw = raw[7:]
    raw = raw.strip().strip("\"'").replace(" ", "").replace("\r", "").replace("\n", "").replace("\t", "")
    if raw in {"your-openai-api-key", "your-api-key-here"}:
        return ""
    return raw if raw.startswith("sk-") else ""


load_env_file()


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS invoice_log (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              logged_at TEXT,
              invoice_number TEXT,
              vendor_name TEXT,
              bill_to_company TEXT,
              invoice_date TEXT,
              due_date TEXT,
              currency TEXT,
              subtotal REAL,
              vat_percentage REAL,
              vat_amount REAL,
              total_amount REAL,
              flags TEXT,
              status TEXT,
              exported INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              logged_at TEXT,
              invoice_number TEXT,
              vendor_name TEXT,
              action TEXT,
              actor TEXT DEFAULT 'system',
              detail TEXT
            )
        """)


def rows_as_dicts(cursor):
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


init_db()


class FinFlowHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1:8787")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, OPTIONS")
        super().end_headers()

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/finflow-ap"):
            self.path = "/finflow-ap.html"
        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        if path == "/api/openai/health":
            self.send_json(200, {
                "ok": True,
                "version": SERVER_VERSION,
                "has_api_key": bool(self.server_api_key()),
            })
            return
        if path == "/api/log/invoices":
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.execute("SELECT * FROM invoice_log ORDER BY logged_at DESC, id DESC")
                self.send_json(200, rows_as_dicts(cursor))
            return
        if path == "/api/log/audit":
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.execute("SELECT * FROM audit_log ORDER BY logged_at DESC, id DESC")
                self.send_json(200, rows_as_dicts(cursor))
            return
        super().do_GET()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/log/invoice":
            self.handle_invoice_log()
            return
        if path == "/api/log/audit":
            self.handle_audit_log()
            return
        if path != "/api/openai/chat/completions":
            self.send_error(404, "Not found")
            return

        api_key = self.normalize_auth_header(self.headers.get("Authorization", "")) or self.server_api_key()
        if not api_key:
            self.send_json(401, {"error": "Missing OpenAI API key"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            upstream = request.Request(
                OPENAI_URL,
                data=body,
                method="POST",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            with request.urlopen(upstream, timeout=120) as response:
                payload = response.read()
                self.send_response(response.status)
                self.send_header("Content-Type", response.headers.get("Content-Type", "application/json"))
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
        except error.HTTPError as exc:
            payload = exc.read() or json.dumps({"error": str(exc)}).encode("utf-8")
            self.send_response(exc.code)
            self.send_header("Content-Type", exc.headers.get("Content-Type", "application/json"))
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except Exception as exc:
            self.send_json(500, {"error": str(exc)})

    def do_PATCH(self):
        path = self.path.split("?", 1)[0]
        if path != "/api/log/invoices/mark-exported":
            self.send_error(404, "Not found")
            return
        payload = self.read_json_body()
        ids = payload.get("ids") if isinstance(payload, dict) else None
        if not isinstance(ids, list):
            self.send_json(400, {"ok": False, "error": "ids must be an array"})
            return
        clean_ids = [int(item) for item in ids if isinstance(item, int) or str(item).isdigit()]
        if clean_ids:
            placeholders = ",".join("?" for _ in clean_ids)
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute(f"UPDATE invoice_log SET exported = 1 WHERE id IN ({placeholders})", clean_ids)
        self.send_json(200, {"ok": True})

    def handle_invoice_log(self):
        payload = self.read_json_body()
        flags = payload.get("flags")
        if not isinstance(flags, str):
            flags = json.dumps(flags or [])
        values = {
            "logged_at": utc_now(),
            "invoice_number": payload.get("invoice_number"),
            "vendor_name": payload.get("vendor_name"),
            "bill_to_company": payload.get("bill_to_company"),
            "invoice_date": payload.get("invoice_date"),
            "due_date": payload.get("due_date"),
            "currency": payload.get("currency"),
            "subtotal": payload.get("subtotal"),
            "vat_percentage": payload.get("vat_percentage"),
            "vat_amount": payload.get("vat_amount"),
            "total_amount": payload.get("total_amount"),
            "flags": flags,
            "status": payload.get("status"),
            "exported": 1 if payload.get("exported") else 0,
        }
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute("""
                INSERT INTO invoice_log (
                  logged_at, invoice_number, vendor_name, bill_to_company, invoice_date, due_date,
                  currency, subtotal, vat_percentage, vat_amount, total_amount, flags, status, exported
                ) VALUES (
                  :logged_at, :invoice_number, :vendor_name, :bill_to_company, :invoice_date, :due_date,
                  :currency, :subtotal, :vat_percentage, :vat_amount, :total_amount, :flags, :status, :exported
                )
            """, values)
            log_id = cursor.lastrowid
        self.send_json(200, {"ok": True, "id": log_id})

    def handle_audit_log(self):
        payload = self.read_json_body()
        actor = payload.get("actor") or "system"
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                INSERT INTO audit_log (
                  logged_at, invoice_number, vendor_name, action, actor, detail
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                utc_now(),
                payload.get("invoice_number"),
                payload.get("vendor_name"),
                payload.get("action"),
                actor,
                payload.get("detail"),
            ))
        self.send_json(200, {"ok": True})

    def read_json_body(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            if not body:
                return {}
            return json.loads(body.decode("utf-8"))
        except Exception:
            return {}

    def send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    @staticmethod
    def normalize_auth_header(value):
        return normalize_api_key(value)

    @staticmethod
    def server_api_key():
        return normalize_api_key(os.environ.get("OPENAI_API_KEY", ""))


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), FinFlowHandler)
    print(f"FinFlow AP running at http://{HOST}:{PORT}/finflow-ap.html")
    print("Keep this terminal open while using the app.")
    server.serve_forever()
