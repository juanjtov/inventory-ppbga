-- Premier Padel BGA — Migration 006
-- Atomic stock mutation RPC functions. Replace the read-then-write patterns
-- scattered across the backend (sale creation, sale void, inventory entry,
-- internal use, fiado item removal, stock adjustment) with a single
-- conditional UPDATE that is safe under concurrent writes.
--
-- Services must call these via supabase.rpc(...) rather than SELECT + UPDATE.
--
-- DEPENDS ON: 001 (products)

-- ============================================================
-- decrement_stock(product_id, qty) -> new stock
-- Raises 'insufficient_stock' if stock would go negative.
-- ============================================================
CREATE OR REPLACE FUNCTION decrement_stock(p_product_id UUID, p_qty INTEGER)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    new_stock INTEGER;
BEGIN
    IF p_qty <= 0 THEN
        RAISE EXCEPTION 'qty_must_be_positive';
    END IF;

    UPDATE products
       SET stock = stock - p_qty
     WHERE id = p_product_id
       AND stock IS NOT NULL
       AND stock >= p_qty
     RETURNING stock INTO new_stock;

    IF new_stock IS NULL THEN
        -- Either the product doesn't exist, isn't stock-tracked (NULL stock),
        -- or the stock would have gone negative.
        RAISE EXCEPTION 'insufficient_stock';
    END IF;

    RETURN new_stock;
END;
$$;

-- ============================================================
-- increment_stock(product_id, qty) -> new stock
-- Used by restock flows (sale void, fiado item removal, inventory entry).
-- Treats NULL stock as 0 so services without a tracked stock column
-- (legacy rows) become tracked after their first increment.
-- ============================================================
CREATE OR REPLACE FUNCTION increment_stock(p_product_id UUID, p_qty INTEGER)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    new_stock INTEGER;
BEGIN
    IF p_qty <= 0 THEN
        RAISE EXCEPTION 'qty_must_be_positive';
    END IF;

    UPDATE products
       SET stock = COALESCE(stock, 0) + p_qty
     WHERE id = p_product_id
     RETURNING stock INTO new_stock;

    IF new_stock IS NULL THEN
        RAISE EXCEPTION 'product_not_found';
    END IF;

    RETURN new_stock;
END;
$$;

-- ============================================================
-- set_stock(product_id, new_value) -> old stock
-- Used by the physical-count adjustment flow. Locks the row, captures the
-- pre-adjustment value, sets the new value, returns the old value so the
-- service can record both on the stock_adjustments row atomically.
-- ============================================================
CREATE OR REPLACE FUNCTION set_stock(p_product_id UUID, p_new_value INTEGER)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    old_stock INTEGER;
    found_row BOOLEAN;
BEGIN
    IF p_new_value < 0 THEN
        RAISE EXCEPTION 'value_must_be_non_negative';
    END IF;

    -- Lock the row, then read-and-update. Row-level lock means concurrent
    -- callers serialize on this product.
    SELECT stock INTO old_stock
      FROM products
     WHERE id = p_product_id
     FOR UPDATE;

    GET DIAGNOSTICS found_row = ROW_COUNT;
    IF NOT found_row THEN
        RAISE EXCEPTION 'product_not_found';
    END IF;

    UPDATE products
       SET stock = p_new_value
     WHERE id = p_product_id;

    RETURN COALESCE(old_stock, 0);
END;
$$;
