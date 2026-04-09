-- Premier Padel BGA — Migration 003b
-- Introduce the sale_payments table as the single source of truth for all
-- money received per sale, with per-method attribution. This enables split
-- payments at checkout (one sale, multiple paid methods) and at fiado
-- settlement (one open account, multiple paid methods).
--
-- The existing sales.payment_method column is preserved as the "intent"
-- column (efectivo / datafono / transferencia / fiado / mixto). The new
-- 'mixto' enum value (added in 003a) signals that the sale's per-method
-- breakdown lives in sale_payments.
--
-- DEPENDS ON: 003a (mixto enum value must already exist)

-- ============================================================
-- 1. SALE_PAYMENTS table
-- ============================================================
CREATE TABLE IF NOT EXISTS sale_payments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sale_id UUID NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
    payment_method payment_method NOT NULL,
    amount INTEGER NOT NULL CHECK (amount > 0),
    paid_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Splits and single-method settlements are always paid channels.
    -- 'fiado' and 'mixto' are sale-level intents and can never appear here.
    CONSTRAINT sale_payments_method_is_paid CHECK (
        payment_method IN ('efectivo','datafono','transferencia')
    )
);

CREATE INDEX IF NOT EXISTS idx_sale_payments_sale ON sale_payments(sale_id);
CREATE INDEX IF NOT EXISTS idx_sale_payments_paid_at ON sale_payments(paid_at);
CREATE INDEX IF NOT EXISTS idx_sale_payments_method ON sale_payments(payment_method);

-- ============================================================
-- 2. BACKFILL existing settled sales
-- ============================================================
-- Every previously-settled sale gets a corresponding sale_payments row so
-- the new aggregation queries (cash closing, daily summary) return the
-- same totals they did before this migration.

-- Non-fiado completed sales: one row, paid_at = sale creation time
INSERT INTO sale_payments (sale_id, payment_method, amount, paid_at, created_at)
SELECT id, payment_method, total, created_at, created_at
FROM sales
WHERE status = 'completed'
  AND payment_method IN ('efectivo','datafono','transferencia');

-- Paid fiado with a known settlement method (post-migration-002 data)
INSERT INTO sale_payments (sale_id, payment_method, amount, paid_at, created_at)
SELECT id, paid_payment_method, total, paid_at, paid_at
FROM sales
WHERE status = 'completed'
  AND payment_method = 'fiado'
  AND paid_payment_method IS NOT NULL
  AND paid_at IS NOT NULL;

-- Pre-migration-002 paid fiado (NULL paid_payment_method) is intentionally
-- skipped: report_service handles them via a legacy fallback query so the
-- existing semantics are preserved.

-- ============================================================
-- 3. ROW LEVEL SECURITY
-- ============================================================
ALTER TABLE sale_payments ENABLE ROW LEVEL SECURITY;
