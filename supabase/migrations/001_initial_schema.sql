-- Premier Padel BGA — Initial Schema
-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Custom types
CREATE TYPE user_role AS ENUM ('owner', 'admin', 'worker');
CREATE TYPE product_type AS ENUM ('product', 'service');
CREATE TYPE payment_method AS ENUM ('efectivo', 'transferencia', 'datafono', 'fiado');
CREATE TYPE sale_status AS ENUM ('completed', 'pending', 'voided');

-- ============================================================
-- USERS (synced with Supabase Auth)
-- ============================================================
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    auth_id UUID UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role user_role NOT NULL DEFAULT 'worker',
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- CATEGORIES
-- ============================================================
CREATE TABLE categories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- SUPPLIERS
-- ============================================================
CREATE TABLE suppliers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- PRODUCTS
-- ============================================================
CREATE TABLE products (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    category_id UUID NOT NULL REFERENCES categories(id),
    supplier_id UUID NOT NULL REFERENCES suppliers(id),
    sale_price INTEGER NOT NULL CHECK (sale_price >= 0),
    purchase_price INTEGER NOT NULL DEFAULT 0 CHECK (purchase_price >= 0),
    stock INTEGER,
    min_stock_alert INTEGER NOT NULL DEFAULT 5,
    type product_type NOT NULL DEFAULT 'product',
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(name, supplier_id)
);

-- ============================================================
-- SALES
-- ============================================================
CREATE TABLE sales (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id),
    total INTEGER NOT NULL CHECK (total >= 0),
    payment_method payment_method NOT NULL,
    status sale_status NOT NULL DEFAULT 'completed',
    client_name VARCHAR(255),
    notes TEXT,
    voided_by UUID REFERENCES users(id),
    void_reason VARCHAR(500),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    voided_at TIMESTAMPTZ,
    CONSTRAINT fiado_requires_client CHECK (
        payment_method != 'fiado' OR client_name IS NOT NULL
    )
);

-- ============================================================
-- SALE ITEMS
-- ============================================================
CREATE TABLE sale_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sale_id UUID NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price INTEGER NOT NULL CHECK (unit_price >= 0),
    subtotal INTEGER NOT NULL CHECK (subtotal >= 0)
);

-- ============================================================
-- INVENTORY ENTRIES (restocking)
-- ============================================================
CREATE TABLE inventory_entries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id UUID NOT NULL REFERENCES products(id),
    user_id UUID NOT NULL REFERENCES users(id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    supplier_id UUID NOT NULL REFERENCES suppliers(id),
    expected_price INTEGER NOT NULL CHECK (expected_price >= 0),
    actual_price INTEGER NOT NULL CHECK (actual_price >= 0),
    price_confirmed BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- INTERNAL USE (non-sale stock deductions)
-- ============================================================
CREATE TABLE internal_use (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id UUID NOT NULL REFERENCES products(id),
    user_id UUID NOT NULL REFERENCES users(id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    reason VARCHAR(500) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- CASH CLOSINGS (corte de caja)
-- ============================================================
CREATE TABLE cash_closings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id),
    closing_date DATE NOT NULL,
    total_sales INTEGER NOT NULL DEFAULT 0,
    total_cash INTEGER NOT NULL DEFAULT 0,
    total_transfer INTEGER NOT NULL DEFAULT 0,
    total_datafono INTEGER NOT NULL DEFAULT 0,
    total_fiado INTEGER NOT NULL DEFAULT 0,
    total_voided INTEGER NOT NULL DEFAULT 0,
    total_internal_use INTEGER NOT NULL DEFAULT 0,
    physical_cash INTEGER NOT NULL DEFAULT 0,
    difference INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(closing_date)
);

-- ============================================================
-- AUDIT LOG (extra feature)
-- ============================================================
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id UUID NOT NULL,
    old_values JSONB,
    new_values JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- INDEXES
-- ============================================================
CREATE INDEX idx_products_category ON products(category_id);
CREATE INDEX idx_products_supplier ON products(supplier_id);
CREATE INDEX idx_products_active ON products(is_active) WHERE is_active = true;
CREATE INDEX idx_products_low_stock ON products(stock, min_stock_alert) WHERE type = 'product';
CREATE INDEX idx_sales_created ON sales(created_at);
CREATE INDEX idx_sales_status ON sales(status);
CREATE INDEX idx_sales_payment ON sales(payment_method);
CREATE INDEX idx_sales_user ON sales(user_id);
CREATE INDEX idx_sale_items_sale ON sale_items(sale_id);
CREATE INDEX idx_sale_items_product ON sale_items(product_id);
CREATE INDEX idx_inventory_entries_product ON inventory_entries(product_id);
CREATE INDEX idx_internal_use_product ON internal_use(product_id);
CREATE INDEX idx_audit_log_entity ON audit_log(entity_type, entity_id);
CREATE INDEX idx_audit_log_created ON audit_log(created_at);

-- ============================================================
-- UPDATED_AT TRIGGER
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_users_updated_at
    BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trigger_products_updated_at
    BEFORE UPDATE ON products FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- REALTIME (enable for products table so stock updates are live)
-- ============================================================
ALTER PUBLICATION supabase_realtime ADD TABLE products;

-- ============================================================
-- ROW LEVEL SECURITY
-- ============================================================
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE products ENABLE ROW LEVEL SECURITY;
ALTER TABLE sales ENABLE ROW LEVEL SECURITY;
ALTER TABLE sale_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventory_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE internal_use ENABLE ROW LEVEL SECURITY;
ALTER TABLE cash_closings ENABLE ROW LEVEL SECURITY;
ALTER TABLE categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE suppliers ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;

-- Service role bypasses RLS; API uses service_role_key
-- Frontend direct access uses anon key with these policies:
CREATE POLICY "Authenticated users can read products" ON products
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "Authenticated users can read categories" ON categories
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "Authenticated users can read suppliers" ON suppliers
    FOR SELECT USING (auth.role() = 'authenticated');
