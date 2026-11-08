ALTER TABLE business_settings
    ADD COLUMN IF NOT EXISTS consumer_markup_pct VARCHAR NOT NULL DEFAULT '40';

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

    IF old_type IS NOT NULL AND old_type NOT IN ('varchar', 'text') THEN
        BEGIN
            EXECUTE format('DROP TYPE IF EXISTS %I', old_type);
        EXCEPTION WHEN dependent_objects_still_exist THEN
            RAISE NOTICE 'enum type % still in use, left in place', old_type;
        END;
    END IF;
END $$;
