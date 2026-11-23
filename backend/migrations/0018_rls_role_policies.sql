-- 0018_rls_role_policies
-- Row Level Security por rol para single-tenant (sin entidad tenant).
-- toscana_app es un rol LOGIN que no es owner de las tablas: RLS lo restringe.
-- Superusuarios y roles BYPASSRLS siempre lo evaden, así que hasta que
-- DATABASE_URL apunte a toscana_app las policies quedan dormidas.
-- Contexto por sesión, seteado por la API en cada request:
--   app.current_user_id  id del usuario autenticado (JWT sub)
--   app.current_role     admin | customer | negocio
--   app.webhook_order_id pedido del webhook de pagos (firma verificada)
-- GUC sin setear o vacía no matchea ninguna policy: deny por defecto.
-- Alcance: tablas con datos privados de cliente (superficie de IDOR).
-- users, refresh_tokens y google_nonces quedan fuera a propósito: login y
-- refresh las leen antes de que exista contexto autenticado.
-- Se aplica a mano en producción como superuser, después del esquema.
-- La password es un placeholder: cambiarla y apuntar DATABASE_URL a toscana_app.

-- Upgrade
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'toscana_app') THEN
        CREATE ROLE toscana_app WITH LOGIN PASSWORD 'toscana_app_password'
            NOCREATEDB NOCREATEROLE;
    END IF;
END
$$;

GRANT CONNECT ON DATABASE toscana_db TO toscana_app;
GRANT USAGE, CREATE ON SCHEMA public TO toscana_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO toscana_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO toscana_app;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO toscana_app;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO toscana_app;

ALTER TABLE cart ENABLE ROW LEVEL SECURITY;
ALTER TABLE cart FORCE ROW LEVEL SECURITY;
ALTER TABLE cart_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE cart_items FORCE ROW LEVEL SECURITY;
ALTER TABLE customer_addresses ENABLE ROW LEVEL SECURITY;
ALTER TABLE customer_addresses FORCE ROW LEVEL SECURITY;
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders FORCE ROW LEVEL SECURITY;
ALTER TABLE order_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE order_items FORCE ROW LEVEL SECURITY;
ALTER TABLE order_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE order_events FORCE ROW LEVEL SECURITY;
ALTER TABLE order_idempotency_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE order_idempotency_keys FORCE ROW LEVEL SECURITY;

CREATE POLICY policy_owner_cart ON cart TO toscana_app
    USING (
        current_setting('app.current_role', true) = 'admin'
        OR (
            current_setting('app.current_role', true) IN ('customer', 'negocio')
            AND user_id = current_setting('app.current_user_id', true)
        )
    )
    WITH CHECK (
        current_setting('app.current_role', true) = 'admin'
        OR (
            current_setting('app.current_role', true) IN ('customer', 'negocio')
            AND user_id = current_setting('app.current_user_id', true)
        )
    );

CREATE POLICY policy_owner_cart_items ON cart_items TO toscana_app
    USING (
        current_setting('app.current_role', true) = 'admin'
        OR (
            current_setting('app.current_role', true) IN ('customer', 'negocio')
            AND user_id = current_setting('app.current_user_id', true)
        )
    )
    WITH CHECK (
        current_setting('app.current_role', true) = 'admin'
        OR (
            current_setting('app.current_role', true) IN ('customer', 'negocio')
            AND user_id = current_setting('app.current_user_id', true)
        )
    );

CREATE POLICY policy_owner_customer_addresses ON customer_addresses TO toscana_app
    USING (
        current_setting('app.current_role', true) = 'admin'
        OR (
            current_setting('app.current_role', true) IN ('customer', 'negocio')
            AND user_id = current_setting('app.current_user_id', true)
        )
    )
    WITH CHECK (
        current_setting('app.current_role', true) = 'admin'
        OR (
            current_setting('app.current_role', true) IN ('customer', 'negocio')
            AND user_id = current_setting('app.current_user_id', true)
        )
    );

CREATE POLICY policy_owner_order_idempotency_keys ON order_idempotency_keys TO toscana_app
    USING (
        current_setting('app.current_role', true) = 'admin'
        OR (
            current_setting('app.current_role', true) IN ('customer', 'negocio')
            AND user_id = current_setting('app.current_user_id', true)
        )
    )
    WITH CHECK (
        current_setting('app.current_role', true) = 'admin'
        OR (
            current_setting('app.current_role', true) IN ('customer', 'negocio')
            AND user_id = current_setting('app.current_user_id', true)
        )
    );

CREATE POLICY policy_owner_orders ON orders TO toscana_app
    USING (
        current_setting('app.current_role', true) = 'admin'
        OR (
            current_setting('app.current_role', true) IN ('customer', 'negocio')
            AND customer_id = current_setting('app.current_user_id', true)
        )
        OR id = current_setting('app.webhook_order_id', true)
    )
    WITH CHECK (
        current_setting('app.current_role', true) = 'admin'
        OR (
            current_setting('app.current_role', true) IN ('customer', 'negocio')
            AND customer_id = current_setting('app.current_user_id', true)
        )
        OR id = current_setting('app.webhook_order_id', true)
    );

CREATE POLICY policy_owner_order_items ON order_items TO toscana_app
    USING (
        current_setting('app.current_role', true) = 'admin'
        OR EXISTS (
            SELECT 1 FROM orders o
            WHERE o.id = order_items.order_id
              AND (
                  o.customer_id = current_setting('app.current_user_id', true)
                  OR o.id = current_setting('app.webhook_order_id', true)
              )
        )
    )
    WITH CHECK (
        current_setting('app.current_role', true) = 'admin'
        OR EXISTS (
            SELECT 1 FROM orders o
            WHERE o.id = order_items.order_id
              AND (
                  o.customer_id = current_setting('app.current_user_id', true)
                  OR o.id = current_setting('app.webhook_order_id', true)
              )
        )
    );

CREATE POLICY policy_owner_order_events ON order_events TO toscana_app
    USING (
        current_setting('app.current_role', true) = 'admin'
        OR EXISTS (
            SELECT 1 FROM orders o
            WHERE o.id = order_events.order_id
              AND (
                  o.customer_id = current_setting('app.current_user_id', true)
                  OR o.id = current_setting('app.webhook_order_id', true)
              )
        )
    )
    WITH CHECK (
        current_setting('app.current_role', true) = 'admin'
        OR EXISTS (
            SELECT 1 FROM orders o
            WHERE o.id = order_events.order_id
              AND (
                  o.customer_id = current_setting('app.current_user_id', true)
                  OR o.id = current_setting('app.webhook_order_id', true)
              )
        )
    );

-- Downgrade
-- DROP POLICY IF EXISTS policy_owner_cart ON cart;
-- DROP POLICY IF EXISTS policy_owner_cart_items ON cart_items;
-- DROP POLICY IF EXISTS policy_owner_customer_addresses ON customer_addresses;
-- DROP POLICY IF EXISTS policy_owner_order_idempotency_keys ON order_idempotency_keys;
-- DROP POLICY IF EXISTS policy_owner_orders ON orders;
-- DROP POLICY IF EXISTS policy_owner_order_items ON order_items;
-- DROP POLICY IF EXISTS policy_owner_order_events ON order_events;
-- ALTER TABLE cart DISABLE ROW LEVEL SECURITY;
-- ALTER TABLE cart_items DISABLE ROW LEVEL SECURITY;
-- ALTER TABLE customer_addresses DISABLE ROW LEVEL SECURITY;
-- ALTER TABLE orders DISABLE ROW LEVEL SECURITY;
-- ALTER TABLE order_items DISABLE ROW LEVEL SECURITY;
-- ALTER TABLE order_events DISABLE ROW LEVEL SECURITY;
-- ALTER TABLE order_idempotency_keys DISABLE ROW LEVEL SECURITY;
-- El rol toscana_app no se borra en el downgrade.
