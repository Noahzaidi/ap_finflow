# FinFlow AP

AI invoice processing demo for supplier PDF invoices. It previews PDFs, extracts invoice data with GPT-4o Vision, flags anomalies, generates IFRS-style journal entries, logs every action to SQLite, and exports NetSuite-ready CSV files.

## Requirements

- Python 3.10+
- Internet access for CDN assets and OpenAI API calls
- OpenAI API key

No npm install or build step is required.

## Setup

Create or edit `.env` in this folder:

```env
OPENAI_API_KEY=your-openai-api-key
```

Do not commit `.env`. It is ignored by `.gitignore`.

## Run

Open PowerShell in this folder:

```powershell
python finflow-ap-server.py
```

Keep that PowerShell window open.

Then open the app in your browser:

```text
http://127.0.0.1:8787/finflow-ap.html
```

Do not open `finflow-ap.html` directly from disk. The OpenAI proxy and audit log endpoints only work through the local server.

## Health Check

Check that the server sees your API key:

```powershell
Invoke-WebRequest -Uri "http://127.0.0.1:8787/api/openai/health" -UseBasicParsing
```

Expected response includes:

```json
{"ok": true, "has_api_key": true}
```

If `has_api_key` is `false`, save `.env` and restart `python finflow-ap-server.py`.

## What The App Does

- Upload multiple PDF invoices.
- Preview selected PDFs with PDF.js.
- Process invoices sequentially through GPT-4o Vision.
- Show extracted fields in an editable form.
- Detect anomalies such as missing VAT, duplicate invoices, wrong VAT rate, wrong entity, old submission, overdue due date, and total mismatch.
- Generate IFRS-style journal entry previews.
- Confirm invoices into an export queue.
- Remove selected confirmed invoices or remove all confirmed invoices.
- Export confirmed entries to NetSuite CSV.
- Log invoice snapshots and audit events to SQLite.
- View logs from the in-app `Logs` button.

## Local Files

- `finflow-ap.html`: browser UI
- `finflow-ap-server.py`: local server, OpenAI proxy, SQLite API
- `finflow.db`: generated SQLite database
- `.env`: local OpenAI key
- `.env.example`: key template
- `FinflowAP.md`: detailed technical/product documentation

## Useful Endpoints

```text
GET  /api/openai/health
GET  /api/log/audit
GET  /api/log/invoices
POST /api/log/audit
POST /api/log/invoice
PATCH /api/log/invoices/mark-exported
```
