-- Premier Padel BGA — Migration 002
-- Capture payment method when fiado (por cobrar) sales are settled, and
-- redefine cash-closing aggregation to track money flow per day.

-- ============================================================
-- 1. SALES: track how & when a fiado was settled
-- ============================================================
ALTER TABLE sales
    ADD COLUMN IF NOT EXISTS paid_payment_method payment_method,
    ADD COLUMN IF NOT EXISTS paid_at TIMESTAMPTZ;

-- Index to make "fiado paid today" queries fast in the cash closing
CREATE INDEX IF NOT EXISTS idx_sales_paid_at ON sales(paid_at) WHERE paid_at IS NOT NULL;

-- Only fiado sales should ever have paid_payment_method set. Non-fiado
-- sales settle instantly at creation; their payment_method is the truth.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'paid_method_only_for_fiado'
    ) THEN
        ALTER TABLE sales
            ADD CONSTRAINT paid_method_only_for_fiado CHECK (
                paid_payment_method IS NULL OR payment_method = 'fiado'
            );
    END IF;
END $$;

-- A paid_payment_method is never 'fiado' itself — fiado is only valid
-- as the *original* payment intent, never as a settlement channel.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'paid_method_not_fiado'
    ) THEN
        ALTER TABLE sales
            ADD CONSTRAINT paid_method_not_fiado CHECK (
                paid_payment_method IS NULL OR paid_payment_method != 'fiado'
            );
    END IF;
END $$;

-- ============================================================
-- 2. CASH CLOSINGS: extend with credit-flow totals
-- ============================================================
-- New fields capture the *credit lifecycle* on a given day:
--   total_credit_issued    = sum of fiado created that day (regardless of paid status)
--   total_credit_collected = sum of fiado paid that day (regardless of when created)
--   total_credit_outstanding = snapshot of all pending fiado at the time of closing
--
-- Existing columns (total_cash, total_transfer, total_datafono) retain their
-- numeric value for historical closings but now mean "money received today via
-- this channel" for closings created after this migration. The legacy
-- total_fiado field is preserved for historical readability.
ALTER TABLE cash_closings
    ADD COLUMN IF NOT EXISTS total_credit_issued INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS total_credit_collected INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS total_credit_outstanding INTEGER NOT NULL DEFAULT 0;
