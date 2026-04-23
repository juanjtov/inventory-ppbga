# Premier Padel BGA — Inventory System

## Environments

**Currently, the same Supabase project backs both production and development.**
The connection configured in `backend/.env` and the frontend `.env` IS the
real production DB. Any row written during local work (sales, inventory
entries, adjustments, users) immediately affects real business data. Plan
every test accordingly: snapshot first, use traceable `__test_*__` markers,
hard-delete + verify stock restored afterwards.

The backend prints `Supabase project: <ref>` at startup as a guardrail. That
ref is the prod project. A future split of prod/dev is desirable but not yet
done.

Operational scripts for backups, dev DB refresh, and migrations live in
`scripts/` (see `scripts/README.md`). The DB connection string for `pg_dump`
is stored in macOS Keychain (`inventorypp_prod_db_url`), never in a file.
Run `./scripts/backup_prod_db.sh` BEFORE any batch of tests that writes
rows, and verify row counts / stock values match after cleanup.

## Test Data Cleanup Rule

Because tests touch real data, **cleanup is mandatory**, not best-effort.
Treat every row left behind by a test as an incident.

Dummy-data categories to delete after any test run:

- **Users**: emails matching `*@battery.test`, `*@test.premierpadel.com`, or test patterns
- **Products**: names matching `__test_*__`, `__battery_*__`, `BATTERY_TEST_*`, `__oversell_*__`, `__inv_exceed_*__`, `CSV_TEST_*`
- **Categories**: names matching `__test_*__`, `__csv_test_*__`
- **Suppliers**: names matching `__test_*__`, `__csv_test_*__`
- **Sales, sale_items, inventory_entries, internal_use, sale_payments, stock_adjustments**: any records created during testing
- **Cash closings**: any with test dates (e.g., 2019-01-01, 2020-01-01)
- **Audit log**: entries referencing test entities

Delete in FK-safe order:
`audit_log → stock_adjustments → sale_payments → cash_closings → sale_items → sales → internal_use → inventory_entries → products → categories → suppliers → users`.

After deletion, diff current `products.stock` vs the pre-test snapshot —
every touched product's stock must match.

## Reports semantics

**VentasTab (`/api/v1/reports/daily-summary`) — money-flow view.**
- `total_sales` is accrual: sum of non-voided sales created in the range.
- `by_payment_method.{efectivo,transferencia,datafono}` is cash flow: money
  actually received in the range, sourced from `sale_payments.paid_at`.
  Includes fiado settlements that happened in the range and auto-splits
  mixto sales.
- `by_payment_method.fiado` is "por cobrar": pending fiado created in the
  range (same value as `fiado_pending`).
- `fiado_settled_in_range` is transparency — fiado sales whose `paid_at`
  lies in the range.

`total_sales` (accrual) and `sum(by_payment_method)` (cash flow) are not
expected to match exactly: a fiado created on day D but paid on D+5 appears
in `total_sales` on D and in `efectivo` on D+5.

**Corte de Caja (`/api/v1/reports/cash-closing`) — historical per-date snapshot.**
- `total_credit_outstanding` reflects fiados outstanding AT THE END OF the
  selected date (created ≤ date_end and not paid/voided by date_end). It is
  not a live snapshot; reviewing a past day shows that day's state.
- `total_credit_issued` / `total_credit_collected` are daily-scoped already.
- Cash closings saved before this change store whatever value was live at
  creation time — those rows are frozen.

**Fiado aging (`/api/v1/reports/fiado-aging`)** accepts `as_of=YYYY-MM-DD`.
When provided, buckets reflect the state at end of that date (same semantic
as Corte de Caja's outstanding). Without it, buckets reflect the current
moment.

**Canonical payment source** is `sale_payments`. Never trust
`sales.payment_method` for per-channel attribution of settled fiados — that
column is the sale-level intent, not the settlement channel.

## Stock mutations

All stock changes must go through the atomic RPC functions installed by
migration 006:
- `decrement_stock(product_id, qty)` — used on sale creation, add-items to
  fiado, internal use. Raises `insufficient_stock` (surfaced as HTTP 400)
  if the stock would go negative.
- `increment_stock(product_id, qty)` — used on sale void, fiado item
  removal, inventory entry.
- `set_stock(product_id, new_value)` — used by `stock_adjustments`
  (physical count) to snap stock to a new value.

Never write `supabase.table("products").update({"stock": x})` directly in
service code — doing so bypasses the race-safe path and breaks concurrency
guarantees.

## Audit log

The following mutations leave a row in `audit_log`:
- `sale_created`, `sale_voided`, `fiado_paid`, `fiado_add_items`, `fiado_remove_item`
- `inventory_entry_created`, `internal_use_created`
- `stock_adjustment` (physical count)
- `price_change` (product sale price edits), `purchase_price_change` (implicit via inventory entry with `price_confirmed=false`)

If you add a new mutation path, write an audit row in the same transaction;
the reports and reconciliation flows rely on the log for forensics.
