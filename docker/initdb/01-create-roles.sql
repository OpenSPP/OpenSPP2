-- OpenSPP initdb roles (Option A - strict)
-- Edit passwords and database name to match your .env.production
-- This file runs only on first initialization when the data directory is empty.

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'odoo') THEN
    CREATE ROLE odoo LOGIN PASSWORD 'CHANGE_ME_STRONG_PASSWORD_HERE' NOSUPERUSER NOCREATEDB;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'openspp_admin') THEN
    CREATE ROLE openspp_admin LOGIN PASSWORD 'CHANGE_ME_ADMIN_PASSWORD_HERE' SUPERUSER;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'openspp') THEN
    CREATE DATABASE openspp OWNER openspp_admin;
  ELSE
    ALTER DATABASE openspp OWNER TO openspp_admin;
  END IF;
END $$;

\connect openspp
CREATE EXTENSION IF NOT EXISTS postgis;
