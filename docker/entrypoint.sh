#!/bin/bash
# OpenSPP Odoo Entrypoint - Updated 2025-12-05
set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Parse DATABASE_URL if provided
# Format: postgres://user:password@host:port/dbname
# Uses Python for robust URL parsing (handles special chars, URL encoding, IPv6)
if [ -n "${DATABASE_URL:-}" ]; then
    log_info "Parsing DATABASE_URL..."

    # Use Python for robust URL parsing
    DB_PARSE_RESULT=$(python3 -c "
import urllib.parse
import sys

try:
    url = urllib.parse.urlparse('$DATABASE_URL')
    # URL-decode username and password (handles special chars like @, :, etc.)
    username = urllib.parse.unquote(url.username or '')
    password = urllib.parse.unquote(url.password or '')
    hostname = url.hostname or 'localhost'
    port = url.port or 5432
    # Remove leading slash and any query params from path
    dbname = (url.path.lstrip('/').split('?')[0]) if url.path else ''

    # Output export statements for each variable
    print(f'export DB_USER=\"{username}\"')
    print(f'export DB_PASSWORD=\"{password}\"')
    print(f'export DB_HOST=\"{hostname}\"')
    print(f'export DB_PORT=\"{port}\"')
    print(f'export DB_NAME=\"{dbname}\"')
except Exception as e:
    print(f'PARSE_ERROR={e}', file=sys.stderr)
    sys.exit(1)
" 2>&1)

    if [ $? -ne 0 ]; then
        log_error "Failed to parse DATABASE_URL: $DB_PARSE_RESULT"
        exit 1
    fi

    # Export the parsed values (each line is now a separate export statement)
    eval "$DB_PARSE_RESULT"

    # Validate required fields
    if [ -z "${DB_HOST:-}" ]; then
        log_error "DATABASE_URL parsing failed: no host found"
        exit 1
    fi

    # Ensure DB_PORT is a valid integer
    [[ -z "$DB_PORT" || ! "$DB_PORT" =~ ^[0-9]+$ ]] && export DB_PORT="5432"

    log_info "Database configuration parsed:"
    log_info "  Host: $DB_HOST"
    log_info "  Port: $DB_PORT"
    log_info "  User: $DB_USER"
    log_info "  Database: ${DB_NAME:-not set}"
else
    log_warn "DATABASE_URL not set, using individual DB_* environment variables"
    # Set defaults for individual DB vars
    export DB_PORT="${DB_PORT:-5432}"
    [[ ! "$DB_PORT" =~ ^[0-9]+$ ]] && export DB_PORT="5432"
fi

# If DB_NAME is still not set, try ODOO_DB_NAME
if [ -z "${DB_NAME:-}" ] && [ -n "${ODOO_DB_NAME:-}" ]; then
    export DB_NAME="$ODOO_DB_NAME"
    log_info "Using ODOO_DB_NAME: $DB_NAME"
fi

# Parse REDIS_URL if provided (from dokku-redis)
# Format: redis://user:password@host:port or redis://host:port
if [ -n "${REDIS_URL:-}" ]; then
    log_info "Parsing REDIS_URL..."

    # Remove the redis:// prefix
    REDIS_URL_PARSED="${REDIS_URL#redis://}"

    # Check if there's authentication (contains @)
    if [[ "$REDIS_URL_PARSED" == *"@"* ]]; then
        # Extract password (user is usually empty for Redis)
        REDIS_AUTH="${REDIS_URL_PARSED%%@*}"
        export REDIS_PASSWORD="${REDIS_AUTH#*:}"
        REDIS_HOSTPORT="${REDIS_URL_PARSED#*@}"
    else
        export REDIS_PASSWORD=""
        REDIS_HOSTPORT="$REDIS_URL_PARSED"
    fi

    # Extract host and port
    export REDIS_HOST="${REDIS_HOSTPORT%%:*}"
    REDIS_PORT_TEMP="${REDIS_HOSTPORT#*:}"

    # Handle case where port might not be in the URL
    if [ "$REDIS_PORT_TEMP" = "$REDIS_HOST" ]; then
        export REDIS_PORT="6379"
    else
        export REDIS_PORT="${REDIS_PORT_TEMP%%/*}"
    fi

    export SESSION_REDIS="True"
    export REDIS_PREFIX="${ODOO_DB_NAME:-odoo}"
    export REDIS_EXPIRATION="${REDIS_EXPIRATION:-604800}"

    log_info "Redis configuration parsed:"
    log_info "  Host: $REDIS_HOST"
    log_info "  Port: $REDIS_PORT"
    log_info "  Session store: enabled"
else
    log_info "REDIS_URL not set, sessions will use filesystem"
    export SESSION_REDIS="False"
    export REDIS_HOST=""
    export REDIS_PORT="6379"
    export REDIS_PASSWORD=""
    export REDIS_PREFIX=""
    export REDIS_EXPIRATION=""
fi

# Validate required environment variables
REQUIRED_VARS=("DB_HOST" "DB_PORT" "DB_USER" "DB_PASSWORD" "DB_NAME" "ODOO_ADMIN_PASSWD")
MISSING_VARS=()

for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var:-}" ]; then
        MISSING_VARS+=("$var")
    fi
done

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
    log_error "Missing required environment variables: ${MISSING_VARS[*]}"
    exit 1
fi

# Set default values for optional variables
# Database defaults
export DB_SSLMODE="${DB_SSLMODE:-prefer}"
export DB_FILTER="${DB_FILTER:-.*}"
export LIST_DB="${LIST_DB:-False}"

# Proxy mode (required for Dokku reverse proxy)
export PROXY_MODE="${PROXY_MODE:-True}"

# Performance tuning - ensure integer values are never empty
export ODOO_WORKERS="${ODOO_WORKERS:-2}"
[[ -z "$ODOO_WORKERS" || ! "$ODOO_WORKERS" =~ ^[0-9]+$ ]] && export ODOO_WORKERS="2"
export ODOO_CRON_THREADS="${ODOO_CRON_THREADS:-1}"
[[ -z "$ODOO_CRON_THREADS" || ! "$ODOO_CRON_THREADS" =~ ^[0-9]+$ ]] && export ODOO_CRON_THREADS="1"
export ODOO_MEMORY_HARD="${ODOO_MEMORY_HARD:-2684354560}"
[[ -z "$ODOO_MEMORY_HARD" || ! "$ODOO_MEMORY_HARD" =~ ^[0-9]+$ ]] && export ODOO_MEMORY_HARD="2684354560"
export ODOO_MEMORY_SOFT="${ODOO_MEMORY_SOFT:-2147483648}"
[[ -z "$ODOO_MEMORY_SOFT" || ! "$ODOO_MEMORY_SOFT" =~ ^[0-9]+$ ]] && export ODOO_MEMORY_SOFT="2147483648"
export ODOO_DB_MAXCONN="${ODOO_DB_MAXCONN:-128}"
[[ -z "$ODOO_DB_MAXCONN" || ! "$ODOO_DB_MAXCONN" =~ ^[0-9]+$ ]] && export ODOO_DB_MAXCONN="128"
export ODOO_TIME_CPU="${ODOO_TIME_CPU:-600}"
[[ -z "$ODOO_TIME_CPU" || ! "$ODOO_TIME_CPU" =~ ^[0-9]+$ ]] && export ODOO_TIME_CPU="600"
export ODOO_TIME_REAL="${ODOO_TIME_REAL:-1200}"
[[ -z "$ODOO_TIME_REAL" || ! "$ODOO_TIME_REAL" =~ ^[0-9]+$ ]] && export ODOO_TIME_REAL="1200"
export ODOO_LIMIT_REQUEST="${ODOO_LIMIT_REQUEST:-8192}"
[[ -z "$ODOO_LIMIT_REQUEST" || ! "$ODOO_LIMIT_REQUEST" =~ ^[0-9]+$ ]] && export ODOO_LIMIT_REQUEST="8192"

# Logging
export LOG_LEVEL="${LOG_LEVEL:-info}"
export LOG_HANDLER="${LOG_HANDLER:-:INFO}"
# Logfile must not be empty string if set - remove if empty
export LOGFILE="${LOGFILE:-}"
[[ -z "$LOGFILE" ]] && unset LOGFILE

# Server settings - http_interface can be empty (means all interfaces)
export HTTP_INTERFACE="${HTTP_INTERFACE:-}"

# Email configuration
export SMTP_SERVER="${SMTP_SERVER:-localhost}"
export SMTP_PORT="${SMTP_PORT:-25}"
[[ -z "$SMTP_PORT" || ! "$SMTP_PORT" =~ ^[0-9]+$ ]] && export SMTP_PORT="25"
export SMTP_SSL="${SMTP_SSL:-False}"
export EMAIL_FROM="${EMAIL_FROM:-}"

# Internationalization
export UNACCENT="${UNACCENT:-True}"

# Generate odoo.conf from template using envsubst
log_info "Generating Odoo configuration file..."
if [ ! -f /etc/odoo/odoo.conf.template ]; then
    log_error "Template file /etc/odoo/odoo.conf.template not found!"
    exit 1
fi

if envsubst < /etc/odoo/odoo.conf.template > /etc/odoo/odoo.conf; then
    log_info "Configuration file generated successfully at /etc/odoo/odoo.conf"
    # Show generated config only in dev mode (contains sensitive values)
    if [ "${ODOO_DEV_MODE:-}" = "true" ]; then
        log_info "Generated config (dev mode):"
        cat /etc/odoo/odoo.conf
    fi
else
    log_error "Failed to generate configuration file"
    exit 1
fi

# Wait for PostgreSQL to be ready (with timeout)
log_info "Waiting for PostgreSQL to be ready..."
POSTGRES_TIMEOUT=60
POSTGRES_ELAPSED=0
until PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c '\q' 2>/dev/null; do
    if [ $POSTGRES_ELAPSED -ge $POSTGRES_TIMEOUT ]; then
        log_error "PostgreSQL connection timeout after ${POSTGRES_TIMEOUT}s"
        log_error "Please check database configuration and network connectivity"
        exit 1
    fi
    log_warn "PostgreSQL is unavailable - sleeping (${POSTGRES_ELAPSED}s/${POSTGRES_TIMEOUT}s)"
    sleep 2
    POSTGRES_ELAPSED=$((POSTGRES_ELAPSED + 2))
done
log_info "PostgreSQL is ready!"

# Determine if this is a main Odoo process or a custom command
# "odoo" as the only argument means it's the main process (from Dockerfile CMD)
IS_MAIN_PROCESS=false
if [ $# -eq 0 ] || [ "$*" = "odoo" ]; then
    IS_MAIN_PROCESS=true
fi

# Check if database needs initialization (fresh database without Odoo tables)
# Only do this for the main process, not for predeploy/run tasks
if [ "$IS_MAIN_PROCESS" = true ]; then
    if ! [[ "$DB_NAME" =~ ^[a-zA-Z0-9_]+$ ]]; then
        log_error "Invalid database name '$DB_NAME'. Only alphanumeric characters and underscores are allowed."
        exit 1
    fi

    log_info "Checking if database needs initialization..."

    # First, ensure the database exists (connect to 'postgres' db to check/create)
    db_exists() {
        PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres \
            -tAc "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME'" 2>/dev/null | grep -q "1"
    }

    if ! db_exists; then
        log_info "Database '$DB_NAME' does not exist - creating it..."

        # CREATE DATABASE may fail if another container created it first - that's OK
        if PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres \
            -c "CREATE DATABASE \"$DB_NAME\"" 2>/dev/null; then
            log_info "Database '$DB_NAME' created"
        elif db_exists; then
            log_info "Database '$DB_NAME' was created by another process"
        else
            log_error "Failed to create database '$DB_NAME'"
            exit 1
        fi
    fi

    # Now check if database already has Odoo tables
    if PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
        -c "SELECT 1 FROM ir_module_module LIMIT 1" >/dev/null 2>&1; then
        log_info "Database already initialized"
    else
        log_warn "Database '$DB_NAME' is empty - attempting initialization..."

        # Use a table-based lock instead of advisory locks.
        # Advisory locks are session-scoped and released when psql exits,
        # so they don't work for our use case where we need to run odoo commands.

        # Create lock table if it doesn't exist
        PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" \
            -U "$DB_USER" -d "$DB_NAME" \
            -c "CREATE TABLE IF NOT EXISTS _odoo_init_lock (
                id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
                started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                hostname TEXT
            )" 2>/dev/null || true

        # Try to acquire lock by inserting a row (only one can succeed due to PK)
        # Also take over stale locks older than 10 minutes (crashed initializer)
        LOCK_STALE_MINUTES=10
        HOSTNAME=$(hostname 2>/dev/null || echo "unknown")
        lock_acquired=false

        # First, try to clean up stale locks
        PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" \
            -U "$DB_USER" -d "$DB_NAME" \
            -c "DELETE FROM _odoo_init_lock WHERE started_at < NOW() - INTERVAL '${LOCK_STALE_MINUTES} minutes'" 2>/dev/null || true

        # Now try to insert our lock
        if PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" \
            -U "$DB_USER" -d "$DB_NAME" \
            -c "INSERT INTO _odoo_init_lock (id, hostname) VALUES (1, '$HOSTNAME')" 2>/dev/null; then
            lock_acquired=true
            log_info "Acquired initialization lock"
        fi

        if [ "$lock_acquired" = "false" ]; then
            # Another process is initializing - wait with retries
            INIT_TIMEOUT=300  # 5 minutes total timeout
            INIT_ELAPSED=0
            INIT_INTERVAL=5   # Check every 5 seconds

            # Show who holds the lock
            lock_holder=$(PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" \
                -U "$DB_USER" -d "$DB_NAME" -t -A \
                -c "SELECT hostname || ' (started ' || AGE(NOW(), started_at)::TEXT || ' ago)' FROM _odoo_init_lock WHERE id = 1" 2>/dev/null || echo "unknown")
            log_info "Another process is initializing the database: $lock_holder"
            log_info "Waiting up to ${INIT_TIMEOUT}s..."

            while [ $INIT_ELAPSED -lt $INIT_TIMEOUT ]; do
                sleep $INIT_INTERVAL
                INIT_ELAPSED=$((INIT_ELAPSED + INIT_INTERVAL))

                # Check if database is now initialized
                if PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
                    -c "SELECT 1 FROM ir_module_module LIMIT 1" >/dev/null 2>&1; then
                    log_info "Database initialized by another process"
                    break
                fi

                # Try to clean up stale locks and acquire
                PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" \
                    -U "$DB_USER" -d "$DB_NAME" \
                    -c "DELETE FROM _odoo_init_lock WHERE started_at < NOW() - INTERVAL '${LOCK_STALE_MINUTES} minutes'" 2>/dev/null || true

                if PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" \
                    -U "$DB_USER" -d "$DB_NAME" \
                    -c "INSERT INTO _odoo_init_lock (id, hostname) VALUES (1, '$HOSTNAME')" 2>/dev/null; then
                    log_info "Previous initializer timed out or crashed. Taking over initialization..."
                    lock_acquired=true
                    break
                fi

                log_info "Still waiting for database initialization... (${INIT_ELAPSED}s/${INIT_TIMEOUT}s)"
            done

            if [ "$lock_acquired" = "false" ]; then
                # Final check after timeout
                if PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
                    -c "SELECT 1 FROM ir_module_module LIMIT 1" >/dev/null 2>&1; then
                    log_info "Database initialized by another process"
                else
                    log_error "Database still not initialized after waiting ${INIT_TIMEOUT}s"
                    exit 1
                fi
            fi
        fi

        if [ "$lock_acquired" = "true" ]; then
            # We have the lock - initialize the database
            log_info "Initializing database..."
            log_info "This may take a few minutes on first deployment..."

            if odoo -d "$DB_NAME" -i base --stop-after-init --no-http; then
                log_info "Database initialized successfully!"

                # Set admin user password from ODOO_ADMIN_PASSWD
                log_info "Setting admin user password..."
                HASHED_PASSWORD=$(python3 -c "
from passlib.context import CryptContext
ctx = CryptContext(schemes=['pbkdf2_sha512', 'plaintext'], deprecated=['plaintext'])
print(ctx.hash('$ODOO_ADMIN_PASSWD'))
")
                PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" \
                    -U "$DB_USER" -d "$DB_NAME" \
                    -c "UPDATE res_users SET password = '$HASHED_PASSWORD' WHERE login = 'admin'" >/dev/null 2>&1
                log_info "Admin password set"
            else
                log_error "Failed to initialize database"
                # Release lock before exiting
                PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" \
                    -U "$DB_USER" -d "$DB_NAME" \
                    -c "DELETE FROM _odoo_init_lock WHERE id = 1" >/dev/null 2>&1 || true
                exit 1
            fi

            # Release the lock
            PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" \
                -U "$DB_USER" -d "$DB_NAME" \
                -c "DELETE FROM _odoo_init_lock WHERE id = 1" >/dev/null 2>&1 || true
            log_info "Released initialization lock"
        fi
    fi
fi

# Build Odoo command with optional flags
ODOO_CMD="odoo"
ODOO_ARGS=()

# Handle module initialization
if [ -n "${ODOO_INIT_MODULES:-}" ]; then
    log_info "Initializing modules: $ODOO_INIT_MODULES"
    ODOO_ARGS+=("-i" "$ODOO_INIT_MODULES")
fi

# Handle module updates
if [ -n "${ODOO_UPDATE_MODULES:-}" ]; then
    log_info "Updating modules: $ODOO_UPDATE_MODULES"
    ODOO_ARGS+=("-u" "$ODOO_UPDATE_MODULES")
fi

# Add any additional Odoo arguments from environment
# Note: ODOO_EXTRA_ARGS should be a single argument per variable for security
# For multiple args, use ODOO_EXTRA_ARGS_1, ODOO_EXTRA_ARGS_2, etc.
if [ -n "${ODOO_EXTRA_ARGS:-}" ]; then
    log_info "Adding extra Odoo arguments: $ODOO_EXTRA_ARGS"
    # Use read array to safely parse space-separated args
    IFS=' ' read -r -a extra_args <<< "$ODOO_EXTRA_ARGS"
    ODOO_ARGS+=("${extra_args[@]}")
fi

# Execute command
# If this is the main Odoo process (no args or just "odoo"), run with ODOO_ARGS
# Otherwise, execute the passed command directly (for dokku run, predeploy, etc.)
if [ "$IS_MAIN_PROCESS" = true ]; then
    log_info "Starting Odoo..."
    log_info "Command: $ODOO_CMD ${ODOO_ARGS[*]:-}"
    exec "$ODOO_CMD" "${ODOO_ARGS[@]+"${ODOO_ARGS[@]}"}"
else
    log_info "Executing passed command: $*"
    # Use exec to replace the shell process
    exec "$@"
fi
