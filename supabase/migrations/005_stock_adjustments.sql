-- Premier Padel BGA — Migration 005
-- Physical stock count feature. Owners can record a counted quantity per
-- product; the system captures the before/after and delta as a dedicated row
-- in stock_adjustments. Used by the reconciliation report to surface real
-- discrepancies between system and physical stock.
--
-- DEPENDS ON: 001 (products, users, audit_log)

CREATE TABLE IF NOT EXISTS stock_adjustments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id UUID NOT NULL REFERENCES products(id),
    counted_quantity INTEGER NOT NULL CHECK (counted_quantity >= 0),
    system_quantity INTEGER NOT NULL,
    difference INTEGER NOT NULL,
    reason TEXT,
    adjusted_by UUID NOT NULL REFERENCES users(id),
    adjusted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT difference_matches CHECK (difference = counted_quantity - system_quantity)
);

CREATE INDEX IF NOT EXISTS idx_stock_adjustments_product
    ON stock_adjustments(product_id, adjusted_at DESC);
CREATE INDEX IF NOT EXISTS idx_stock_adjustments_adjusted_at
    ON stock_adjustments(adjusted_at DESC);

ALTER TABLE stock_adjustments ENABLE ROW LEVEL SECURITY;
