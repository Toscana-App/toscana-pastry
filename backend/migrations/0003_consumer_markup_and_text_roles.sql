-- 0003_consumer_markup_and_text_roles
-- Target: PostgreSQL. Idempotent: safe to run more than once.
-- (Tests run the portable section below against SQLite; see
--  tests/integration/data/test_migration_0003.py.)

-- === upgrade (portable) ===
-- Existing rows get the default '40'. On PostgreSQL, ADD COLUMN IF NOT EXISTS
-- keeps a re-run harmless; SQLite has no IF NOT EXISTS for columns, so the
-- test strips that clause.
ALTER TABLE business_settings
    ADD COLUMN IF NOT EXISTS consumer_markup_pct VARCHAR NOT NULL DEFAULT '40';

-- === upgrade (postgres only) ===
-- users.role: native enum (old labels in uppercase, no 'negocio') -> text,
-- lowercase. USING role::text works for both enum and text columns.
DO $$
DECLARE
    old_type text;
BEGIN
    SELECT udt_name INTO old_type
      FROM information_schema.columns
     WHERE table_name = 'users' AND column_name = 'role'
       AND table_schema = current_schema();

    ALTER TABLE users
        ALTER COLUMN role TYPE VARCHAR(50) USING lower(role::text);
    ALTER TABLE users ALTER COLUMN role SET DEFAULT 'customer';

    -- Drop the orphan enum type only when it was an enum and nothing uses it.
    IF old_type IS NOT NULL AND old_type NOT IN ('varchar', 'text') THEN
        BEGIN
            EXECUTE format('DROP TYPE IF EXISTS %I', old_type);
        EXCEPTION WHEN dependent_objects_still_exist THEN
            RAISE NOTICE 'enum type % still in use, left in place', old_type;
        END;
    END IF;
END $$;

-- === downgrade (commented; data loss for 'negocio' users) ===
-- ALTER TABLE business_settings DROP COLUMN consumer_markup_pct;
-- -- Roles stay as lowercase text; restoring the native enum is not supported.
-- UPDATE users SET role = 'customer' WHERE role = 'negocio';
