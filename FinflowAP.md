# FinFlow AP

AI invoice processing demo for supplier PDF invoices. The app previews invoices, extracts AP fields with GPT-4o Vision, validates anomalies, creates IFRS-style journal entries, and exports a NetSuite-ready CSV.

## Files

- `finflow-ap.html`: main browser UI.
- `finflow-ap-server.py`: local Python server and OpenAI proxy.
- `finflow.db`: local SQLite audit database created automatically on server start and ignored by git.
- `.env`: local API key file. This file is ignored by git.
- `.env.example`: template for `.env`.
- `.gitignore`: excludes local secrets, generated databases, invoice uploads, caches, and CSV exports.

## What The App Does

1. User uploads supplier PDF invoices.
2. App renders the selected PDF in the center viewer.
3. User processes one invoice or all invoices sequentially.
4. Server sends the rendered first page image to OpenAI GPT-4o.
5. Extracted fields appear in an editable form.
6. Deterministic validation flags anomalies.
7. App generates an IFRS-style journal entry preview.
8. User confirms entries into an export queue.
9. User can remove one confirmed entry or remove all confirmed entries.
10. App exports confirmed entries as a NetSuite journal-entry CSV.

## How To Run

Add your OpenAI key to `.env`:

```env
OPENAI_API_KEY=your-openai-api-key
```

Start the local server:

```powershell
python finflow-ap-server.py
```

Open:

```text
http://127.0.0.1:8787/finflow-ap.html
```

Do not open `finflow-ap.html` directly from disk. If opened through `file://`, the page redirects to the local server URL.

## API Key Handling

The browser does not store or send the OpenAI API key.

The key is read by `finflow-ap-server.py` from `.env`:

```env
OPENAI_API_KEY=...
```

The browser calls the local endpoint:

```text
/api/openai/chat/completions
```

The Python proxy forwards the request to:

```text
https://api.openai.com/v1/chat/completions
```

The app checks server key availability through:

```text
/api/openai/health
```

Expected healthy response:

```json
{"ok": true, "version": "2026-05-10-env-key", "has_api_key": true}
```

If `has_api_key` is false, processing is blocked and the UI shows a toast asking to save `.env` and restart the server.

## Tech Stack

- HTML, CSS, and JavaScript in `finflow-ap.html`
- Local Python standard-library HTTP server in `finflow-ap-server.py`
- Tailwind via CDN for demo styling
- Lucide icons via CDN
- PDF.js via CDN for rendering PDFs
- PapaParse via CDN for CSV export
- OpenAI GPT-4o through local proxy
- SQLite audit logging through Python stdlib `sqlite3`
- No `localStorage`
- No `sessionStorage`
- Browser state is held only in JavaScript memory

## Layout

The app uses a three-column full-height layout:

- Left panel: branding, upload, demo invoices, file list, process button, status counts.
- Center panel: PDF visualizer with zoom controls and single-invoice extraction button.
- Right panel: extracted fields, anomaly flags, journal entry preview, confirmation controls, summary footer, export controls.

Minimum intended width is 1280px.

## Left Panel

The left panel contains:

- FinFlow AP branding.
- Server-key status gear button.
- Logs button.
- PDF upload drop zone.
- `Load demo invoices` link.
- Uploaded file list.
- `Process All` button.
- Upload/done/flagged/pending stats.

### File Statuses

Rows can show:

- `Pending`: invoice uploaded but not processed.
- `Processing`: invoice is currently being extracted.
- `Done`: extraction completed and no active flags.
- `Review`: warning-level flags exist.
- `Blocked`: error-level flags exist.
- `Error`: non-auth processing failure.

Flagged rows always take visual priority over selection:

- Error flags show red border, red left stripe, red icon, and `Blocked`.
- Warning flags show amber border, amber left stripe, amber icon, and `Review`.
- The first flag title is shown under the file metadata. Additional flags are shown as `+N`.

## Center PDF Viewer

When a user selects an uploaded PDF:

- PDF.js loads the file from memory.
- Each page renders to a canvas.
- Pages are stacked vertically.
- Viewer shows page labels.
- Zoom controls adjust by 25% steps.
- Rendering uses device pixel ratio for sharper canvas output.

Demo invoices do not have real PDF files, so the viewer shows a placeholder.

## Right Panel

The right panel contains extracted AP data and the journal entry preview.

### Extracted Fields

Editable fields:

- Vendor Name
- Bill To Company
- Vendor VAT Number
- Invoice Number
- Invoice Date
- Due Date
- Currency
- Subtotal
- VAT %
- VAT Amount
- Total Amount

Each field has a status indicator:

- `ok`: value exists and has no relevant anomaly.
- `warn`: field is tied to a warning-level anomaly.
- `error`: field is tied to an error-level anomaly.

Relevant fields also receive red or amber input borders when flagged.

If the user edits a field:

- The invoice is removed from the confirmed export queue.
- The field receives an `edited` badge.
- Validation reruns immediately.
- Journal entry totals update.

### Line Items

Line items are shown in a collapsible table:

- Description
- Quantity
- Unit Price
- Amount

## Extraction Flow

For each real PDF:

1. PDF.js renders page 1 at high scale.
2. The canvas is converted to JPEG base64.
3. Browser sends the OpenAI request body to the local server.
4. Local server adds the `.env` OpenAI key and forwards to OpenAI.
5. GPT-4o returns strict JSON.
6. App parses JSON and validates it.

Only page 1 is sent to GPT-4o in the current implementation.

The prompt asks for:

```json
{
  "vendor_name": "string",
  "vendor_vat": "string or null",
  "invoice_number": "string",
  "invoice_date": "YYYY-MM-DD or null",
  "due_date": "YYYY-MM-DD or null",
  "currency": "EUR",
  "line_items": [
    {"description": "string", "quantity": 0, "unit_price": 0, "amount": 0}
  ],
  "subtotal": 0,
  "vat_percentage": 21,
  "vat_amount": 0,
  "total_amount": 0,
  "payment_reference": "string or null",
  "bill_to_company": "string or null"
}
```

Prompt rules include:

- Return JSON only.
- Use plain numeric amounts.
- Use `YYYY-MM-DD` dates.
- Do not invent data.
- `vendor_vat` means supplier/seller VAT only.
- Do not copy buyer or bill-to VAT into `vendor_vat`.
- If supplier VAT is `NOT PROVIDED`, `N/A`, missing, or similar, return `null`.
- `bill_to_company` must be the exact legal company name from the invoice billing block.

## Processing Behavior

Processing is sequential, not parallel.

`Process All`:

- Takes pending/error invoices.
- Processes one invoice at a time.
- Updates progress text and progress bar.
- Waits briefly between invoices.
- Stops if an auth/configuration error occurs.

`Extract this invoice` processes only the currently selected invoice.

## Anomaly Detection

Validation is deterministic JavaScript. It does not rely on a second AI call.

### Error-Level Flags

These block bulk add and mark the invoice as `Blocked`:

- Missing required field.
- Missing supplier VAT number.
- Total mismatch: subtotal plus VAT does not match total.
- Wrong VAT rate.
- Wrong entity.

### Warning-Level Flags

These mark the invoice as `Review`:

- Same invoice number already exists in the session.
- Same vendor and same total amount already exist in the session.
- Invoice date is more than 90 days old.
- Due date has already passed.
- Line items do not match subtotal.

### Missing VAT Logic

The VAT number is treated as missing if it is empty or a placeholder:

- `null`
- `none`
- `n/a`
- `not applicable`
- `not available`
- `not provided`
- `missing`
- `unknown`
- `undefined`
- `-`

When detected, `vendor_vat` is normalized to `null`.

### Wrong VAT Rate Logic

Current automatic-posting rule:

- `21%` is valid.
- `0%` is valid only for known zero-VAT suppliers such as Stripe/payment processing.
- `9%` is flagged as `Wrong VAT Rate`.
- Any other rate is flagged as `Wrong VAT Rate`.
- VAT amount must match `subtotal * vat_percentage` within tolerance.

Unknown vendor with `0%` VAT is blocked as wrong VAT rate.

### Wrong Entity Logic

Expected bill-to company:

```text
Demo Company B.V.
```

If extracted `bill_to_company` is present and differs from `Demo Company B.V.`, the invoice is blocked.

Example:

```text
Demo Company International Holdings
```

This triggers `Wrong Entity`.

### Duplicate Logic

Two duplicate checks exist:

- Same invoice number in the current browser session.
- Same vendor name plus same total amount in the current browser session.

These are session-only checks. They do not query NetSuite or any database.

## Journal Entry Generation

Journal entries are generated deterministically from extracted data.

Rows:

- Debit expense account for subtotal.
- Debit VAT Receivable if VAT amount is greater than zero.
- Credit Trade Payables for total amount.

The journal preview shows:

- Account
- Debit
- Credit
- Total debit
- Total credit
- Balanced/imbalanced badge

## IFRS Account Mapping

Vendor name is matched against keyword rules. First match wins.

Accounts:

- `6100 - IFRS OPEX: Cloud Infrastructure`
- `6200 - IFRS OPEX: Software & Subscriptions`
- `6300 - IFRS OPEX: Short-term Lease & Office Rent`
- `6500 - IFRS OPEX: Professional Services`
- `6510 - IFRS OPEX: Audit & Accounting Fees`
- `6600 - IFRS OPEX: Equipment & Office Supplies`
- `6700 - IFRS OPEX: Payment Processing Fees`
- `6800 - IFRS OPEX: Employee Benefits Expense`
- `6900 - IFRS OPEX: General Administrative Expenses`
- `1500 - IFRS Current Asset: VAT Receivable`
- `2000 - IFRS Current Liability: Trade Payables`

## Confirmation And Removal

### Confirm Selected Invoice

The Journal Entry section includes:

- `Confirm & Add to Export` for clean invoices.
- `Force Add With Warning` for invoices with blocking flags.

Force add asks for browser confirmation before adding the invoice to the export queue.

### Remove Selected Invoice

Once selected invoice is confirmed, the Journal Entry section shows:

- `Added`
- `Remove`

Clicking `Remove` removes only that invoice from the export queue.

### Add All Clean Entries

The sticky summary footer includes:

```text
Add All Clean Entries (N)
```

This adds all processed invoices that:

- Have extracted data.
- Are not already confirmed.
- Have no error-level flags.

Warning-only invoices can be added by bulk add. Error-level invoices are not bulk-added.

### Remove All Confirmed

The sticky summary footer includes:

```text
Remove All Confirmed (N)
```

This removes every confirmed invoice from the export queue and recalculates all totals.

## Summary Footer

The sticky right footer shows totals across confirmed invoices:

- Total invoices confirmed
- Total amount
- Total VAT
- Total net
- Flagged not exported

It also includes:

- `Add All Clean Entries`
- `Export to NetSuite CSV`
- `Remove All Confirmed`

All values recalculate immediately after:

- Confirm selected invoice.
- Remove selected invoice.
- Add all clean entries.
- Remove all confirmed entries.
- Edit an extracted field.

## NetSuite CSV Export

Only confirmed invoices are exported.

CSV columns:

```csv
External ID,*Journal Date,*Subsidiary,Currency,Memo,*Account,Debit,Credit
```

Rules:

- External ID is sequential per invoice: `JE-001`, `JE-002`, etc.
- Journal date format is `DD/MM/YYYY`.
- Subsidiary is always `Demo Company B.V.`
- Memo is `invoice_number | vendor_name`.
- Subtotal is debit to expense account.
- VAT amount is debit to `1500 - IFRS Current Asset: VAT Receivable`.
- Total amount is credit to `2000 - IFRS Current Liability: Trade Payables`.
- If VAT is zero, the VAT row is skipped.

Output filename:

```text
finflow_journal_entries_YYYYMMDD.csv
```

If confirmed invoices contain warning/error flags, the app shows an export warning modal:

```text
N confirmed invoices have warnings. Export anyway?
```

## Demo Mode

`Load demo invoices` loads five prebuilt invoice objects:

- AWS Europe BV
- Office Depot Netherlands
- Prologis Netherlands BV
- Stripe Payments Europe Ltd
- TechSupplies NL BV

Demo invoices:

- Skip the OpenAI API.
- Are marked `done`.
- Show extracted data immediately.
- Show a placeholder in the PDF viewer because no real PDF file exists.

## Error Handling

### Missing `.env` Key

If the server cannot see `OPENAI_API_KEY`, processing is disabled and a toast says:

```text
Server cannot see OPENAI_API_KEY in .env. Save .env and restart the server.
```

### OpenAI Auth Failure

If OpenAI returns auth failure:

- Server key state is marked unavailable.
- Invoice remains pending.
- Batch processing stops.
- Toast shows a sanitized error.

### OpenAI Rate Limit Or Server Error

Non-auth OpenAI errors:

- Mark the invoice as `Error`.
- Show a sanitized toast.
- Do not expose API-key-looking strings.

## SQLite Audit Logging

`finflow-ap-server.py` creates `finflow.db` on startup with two tables:

- `invoice_log`: invoice snapshots.
- `audit_log`: action and decision events.

Timestamps are set server-side as UTC ISO strings.

### Invoice Log Table

`invoice_log` stores:

- `logged_at`
- `invoice_number`
- `vendor_name`
- `bill_to_company`
- `invoice_date`
- `due_date`
- `currency`
- `subtotal`
- `vat_percentage`
- `vat_amount`
- `total_amount`
- `flags`
- `status`
- `exported`

Invoice snapshots are logged silently after major state changes such as extraction completion, field edits, confirmation, removal, bulk actions, and export marking.

### Audit Log Table

`audit_log` stores:

- `logged_at`
- `invoice_number`
- `vendor_name`
- `action`
- `actor`
- `detail`

Actors are:

- `system`
- `user`

### Audit Events

System events:

- `INVOICE_UPLOADED`
- `EXTRACTION_STARTED`
- `EXTRACTION_COMPLETED`
- `EXTRACTION_FAILED`
- `ANOMALY_DETECTED`
- `VALIDATION_PASSED`
- `JOURNAL_ENTRY_GENERATED`
- `DUPLICATE_DETECTED`

User events:

- `FIELD_EDITED`
- `INVOICE_CONFIRMED`
- `FORCE_CONFIRMED`
- `INVOICE_REMOVED`
- `BULK_ADD_CLEAN`
- `BULK_REMOVE_ALL`
- `EXPORT_TRIGGERED`
- `EXPORT_WARNING_ACKNOWLEDGED`

All browser logging calls are async, non-blocking, and silent on error. Logging failures never interrupt extraction, validation, confirmation, removal, or export.

### Logs Overlay

The app header includes a `Logs` button. It opens a full-screen overlay with two tabs:

- `Audit Trail`
- `Invoice Log`

The overlay has:

- Search input filtering by invoice number or vendor name.
- Close button in the top-right.
- Automatic refresh every 5 seconds while open.

Audit Trail columns:

- Time
- Invoice
- Vendor
- Actor
- Action
- Detail

Audit row colors:

- `user`: blue
- `system`: gray
- `ANOMALY_DETECTED`: amber
- `FORCE_CONFIRMED`: amber
- `EXTRACTION_FAILED`: red

Invoice Log columns:

- Time
- Invoice #
- Vendor
- Total
- Status
- Flags
- Exported

Exported invoice rows show a green `Exported` badge.

### Audit API

Create invoice snapshot:

```text
POST /api/log/invoice
```

Create audit row:

```text
POST /api/log/audit
```

Read invoice snapshots:

```text
GET /api/log/invoices
```

Read audit rows:

```text
GET /api/log/audit
```

Mark invoice snapshots as exported:

```text
PATCH /api/log/invoices/mark-exported
```

Payload:

```json
{"ids": [1, 2, 3]}
```

## Security Notes

- `.env` is ignored by git.
- The browser does not receive the API key.
- The local server forwards requests to OpenAI.
- Do not paste real API keys into chat, docs, screenshots, or committed files.
- If a key is exposed, rotate it in the OpenAI dashboard.

## Known Limitations

- PDF only.
- GPT extraction currently uses page 1 only.
- No backend database.
- Duplicate detection is session-only.
- No NetSuite API integration; export is CSV only.
- No persistent audit trail after browser refresh.
- Password-protected PDFs are not supported.
- Very blurry, rotated, handwritten, or multi-page invoices may extract poorly.
- Tailwind is loaded from CDN for demo convenience.

## Quick Validation Commands

Check Python server syntax:

```powershell
python -m py_compile finflow-ap-server.py
```

Check page availability:

```powershell
Invoke-WebRequest -Uri "http://127.0.0.1:8787/finflow-ap.html" -UseBasicParsing
```

Check server key health:

```powershell
Invoke-WebRequest -Uri "http://127.0.0.1:8787/api/openai/health" -UseBasicParsing
```

Expected key-loaded health:

```json
{"ok": true, "version": "2026-05-10-env-key", "has_api_key": true}
```

## Demo Talk Track

1. Open the app at `http://127.0.0.1:8787/finflow-ap.html`.
2. Upload supplier PDFs.
3. Select an invoice and show the PDF rendered in the center panel.
4. Click `Process All`.
5. Show sequential processing.
6. Open a blocked invoice and explain the red anomaly.
7. Open a warning invoice and explain the amber review state.
8. Confirm clean entries.
9. Use `Add All Clean Entries` for remaining clean invoices.
10. Remove one confirmed invoice with `Remove`.
11. Remove all confirmed invoices if needed.
12. Export to NetSuite CSV.
