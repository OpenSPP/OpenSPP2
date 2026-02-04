#!/bin/sh
# Backup container entrypoint
#
# Sets up cron schedule and runs crond in foreground.
# Also supports running a one-off backup via: docker compose exec backup /backup.sh

set -e

BACKUP_SCHEDULE="${BACKUP_SCHEDULE:-0 2 * * *}"

echo "[$(date -Iseconds)] Setting up backup schedule: ${BACKUP_SCHEDULE}"

# Create crontab with environment variables
cat > /etc/crontabs/root << EOF
# OpenSPP Database Backup
# Schedule: ${BACKUP_SCHEDULE}
${BACKUP_SCHEDULE} /backup.sh >> /var/log/backup.log 2>&1
EOF

# Export PostgreSQL environment for cron
cat > /etc/profile.d/pg_env.sh << EOF
export PGHOST="${PGHOST:-db}"
export PGPORT="${PGPORT:-5432}"
export PGUSER="${PGUSER:-odoo}"
export PGPASSWORD="${PGPASSWORD}"
export PGDATABASE="${PGDATABASE:-openspp}"
export BACKUP_DIR="${BACKUP_DIR:-/backups}"
export BACKUP_KEEP_DAYS="${BACKUP_KEEP_DAYS:-7}"
export BACKUP_KEEP_WEEKS="${BACKUP_KEEP_WEEKS:-4}"
export BACKUP_KEEP_MONTHS="${BACKUP_KEEP_MONTHS:-6}"
EOF

# Source env for current shell
. /etc/profile.d/pg_env.sh

# Create log file
touch /var/log/backup.log

echo "[$(date -Iseconds)] Waiting for database to be ready..."
until pg_isready -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" -q; do
    sleep 2
done
echo "[$(date -Iseconds)] Database is ready"

echo "[$(date -Iseconds)] Starting crond..."
exec crond -f -l 2
