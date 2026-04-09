-- Premier Padel BGA — Migration 003a
-- Add 'mixto' to the payment_method enum so a sale can declare that its
-- total was paid via multiple methods. The actual per-method breakdown is
-- recorded in the new sale_payments table (migration 003b).
--
-- NOTE: Postgres requires ALTER TYPE ... ADD VALUE to commit before any
-- subsequent statements can reference the new value. This migration must
-- run on its own before 003b.

ALTER TYPE payment_method ADD VALUE IF NOT EXISTS 'mixto';
