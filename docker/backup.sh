#!/bin/sh
# OpenSPP PostgreSQL/PostGIS Backup Script
#
# Performs daily backups with retention policy:
#   - 7 daily backups
#   - 4 weekly backups (Sundays)
#   - 6 monthly backups (1st of month)
#
# Usage: Run via cron or manually: /backup.sh
#
# Environment variables:
#   PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE (standard PostgreSQL vars)
#   BACKUP_DIR (default: /backups)
#   FILESTORE_SRC (default: /odoo_data/filestore/$PGDATABASE)
#   BACKUP_KEEP_DAYS (default: 7)
#   BACKUP_KEEP_WEEKS (default: 4)
#   BACKUP_KEEP_MONTHS (default: 6)

set -e

# Configuration with defaults
BACKUP_DIR="${BACKUP_DIR:-/backups}"
BACKUP_KEEP_DAYS="${BACKUP_KEEP_DAYS:-7}"
BACKUP_KEEP_WEEKS="${BACKUP_KEEP_WEEKS:-4}"
BACKUP_KEEP_MONTHS="${BACKUP_KEEP_MONTHS:-6}"

# Directories
DAILY_DIR="${BACKUP_DIR}/daily"
WEEKLY_DIR="${BACKUP_DIR}/weekly"
MONTHLY_DIR="${BACKUP_DIR}/monthly"

# Create directories
mkdir -p "${DAILY_DIR}" "${WEEKLY_DIR}" "${MONTHLY_DIR}"

# Timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DATE=$(date +%Y%m%d)
DAY_OF_WEEK=$(date +%u)  # 1=Monday, 7=Sunday
DAY_OF_MONTH=$(date +%d)

# Backup filename
BACKUP_FILE="${PGDATABASE:-openspp}_${TIMESTAMP}.dump"

echo "[$(date -Iseconds)] Starting backup of ${PGDATABASE:-openspp}..."

# Perform backup using pg_dump with custom format (supports PostGIS)
# -Fc = custom format (compressed, supports parallel restore)
# -Z6 = compression level 6
pg_dump -Fc -Z6 -f "${DAILY_DIR}/${BACKUP_FILE}"

# Update latest symlink
ln -sf "${BACKUP_FILE}" "${DAILY_DIR}/${PGDATABASE:-openspp}_latest.dump"

echo "[$(date -Iseconds)] Daily backup complete: ${BACKUP_FILE}"

# Filestore backup (attachments, documents) when odoo data volume is mounted
FILESTORE_SRC="${FILESTORE_SRC:-/odoo_data/filestore/${PGDATABASE:-openspp}}"
FILESTORE_BACKUP_FILE="${PGDATABASE:-openspp}_filestore_${TIMESTAMP}.tar.gz"
if [ -d "${FILESTORE_SRC}" ]; then
    echo "[$(date -Iseconds)] Starting filestore backup from ${FILESTORE_SRC}..."
    tar -czf "${DAILY_DIR}/${FILESTORE_BACKUP_FILE}" -C "$(dirname "${FILESTORE_SRC}")" "$(basename "${FILESTORE_SRC}")"
    ln -sf "${FILESTORE_BACKUP_FILE}" "${DAILY_DIR}/${PGDATABASE:-openspp}_filestore_latest.tar.gz"
    echo "[$(date -Iseconds)] Filestore backup complete: ${FILESTORE_BACKUP_FILE}"
else
    echo "[$(date -Iseconds)] Filestore not found at ${FILESTORE_SRC}; skipping filestore backup"
fi

# Weekly backup (Sunday)
if [ "${DAY_OF_WEEK}" = "7" ]; then
    cp "${DAILY_DIR}/${BACKUP_FILE}" "${WEEKLY_DIR}/"
    if [ -f "${DAILY_DIR}/${FILESTORE_BACKUP_FILE}" ]; then
        cp "${DAILY_DIR}/${FILESTORE_BACKUP_FILE}" "${WEEKLY_DIR}/"
    fi
    echo "[$(date -Iseconds)] Weekly backup saved"
fi

# Monthly backup (1st of month)
if [ "${DAY_OF_MONTH}" = "01" ]; then
    cp "${DAILY_DIR}/${BACKUP_FILE}" "${MONTHLY_DIR}/"
    if [ -f "${DAILY_DIR}/${FILESTORE_BACKUP_FILE}" ]; then
        cp "${DAILY_DIR}/${FILESTORE_BACKUP_FILE}" "${MONTHLY_DIR}/"
    fi
    echo "[$(date -Iseconds)] Monthly backup saved"
fi

# Cleanup old backups
echo "[$(date -Iseconds)] Cleaning up old backups..."

# Remove daily backups older than BACKUP_KEEP_DAYS
find "${DAILY_DIR}" -name "*.dump" -type f -mtime +${BACKUP_KEEP_DAYS} -delete 2>/dev/null || true
find "${DAILY_DIR}" -name "*_filestore_*.tar.gz" -type f -mtime +${BACKUP_KEEP_DAYS} -delete 2>/dev/null || true

# Remove weekly backups older than BACKUP_KEEP_WEEKS weeks
find "${WEEKLY_DIR}" -name "*.dump" -type f -mtime +$((BACKUP_KEEP_WEEKS * 7)) -delete 2>/dev/null || true
find "${WEEKLY_DIR}" -name "*_filestore_*.tar.gz" -type f -mtime +$((BACKUP_KEEP_WEEKS * 7)) -delete 2>/dev/null || true

# Remove monthly backups older than BACKUP_KEEP_MONTHS months (approximate: 30 days per month)
find "${MONTHLY_DIR}" -name "*.dump" -type f -mtime +$((BACKUP_KEEP_MONTHS * 30)) -delete 2>/dev/null || true
find "${MONTHLY_DIR}" -name "*_filestore_*.tar.gz" -type f -mtime +$((BACKUP_KEEP_MONTHS * 30)) -delete 2>/dev/null || true

# Report disk usage
echo "[$(date -Iseconds)] Backup sizes:"
du -sh "${DAILY_DIR}" "${WEEKLY_DIR}" "${MONTHLY_DIR}" 2>/dev/null || true

echo "[$(date -Iseconds)] Backup complete"
