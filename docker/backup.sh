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
#   BACKUP_FILESTORE (default: false) — set true to archive Odoo filestore
#   FILESTORE_SRC (default: /odoo_data/filestore/$PGDATABASE)
#   BACKUP_FILESTORE_COMPRESS (default: false) — gzip filestore archives
#   BACKUP_KEEP_DAYS (default: 7)
#   BACKUP_KEEP_WEEKS (default: 4)
#   BACKUP_KEEP_MONTHS (default: 6)
#   BACKUP_FILESTORE_KEEP_DAYS / _WEEKS / _MONTHS (default: same as BACKUP_KEEP_*)

set -e

# Configuration with defaults
BACKUP_DIR="${BACKUP_DIR:-/backups}"
BACKUP_KEEP_DAYS="${BACKUP_KEEP_DAYS:-7}"
BACKUP_KEEP_WEEKS="${BACKUP_KEEP_WEEKS:-4}"
BACKUP_KEEP_MONTHS="${BACKUP_KEEP_MONTHS:-6}"
BACKUP_FILESTORE="${BACKUP_FILESTORE:-false}"
BACKUP_FILESTORE_COMPRESS="${BACKUP_FILESTORE_COMPRESS:-false}"
BACKUP_FILESTORE_KEEP_DAYS="${BACKUP_FILESTORE_KEEP_DAYS:-${BACKUP_KEEP_DAYS}}"
BACKUP_FILESTORE_KEEP_WEEKS="${BACKUP_FILESTORE_KEEP_WEEKS:-${BACKUP_KEEP_WEEKS}}"
BACKUP_FILESTORE_KEEP_MONTHS="${BACKUP_FILESTORE_KEEP_MONTHS:-${BACKUP_KEEP_MONTHS}}"

# Directories
DAILY_DIR="${BACKUP_DIR}/daily"
WEEKLY_DIR="${BACKUP_DIR}/weekly"
MONTHLY_DIR="${BACKUP_DIR}/monthly"

# Create directories
mkdir -p "${DAILY_DIR}" "${WEEKLY_DIR}" "${MONTHLY_DIR}"

# Skip overlapping runs (filestore archives can outlast the cron interval)
exec 9>"${BACKUP_DIR}/.backup.lock"
flock -n 9 || { echo "[$(date -Iseconds)] Backup already running; skipping"; exit 0; }

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

# Filestore backup (attachments, documents) — opt-in.
# Dump runs before the archive on purpose: an attachment written between dump and
# tar leaves an orphan file that Odoo's filestore GC reaps; the reverse order
# produces a DB row whose file was never captured (FileNotFoundError on restore).
# The pair is crash-consistent, not a true point-in-time snapshot.
FILESTORE_SRC="${FILESTORE_SRC:-/odoo_data/filestore/${PGDATABASE:-openspp}}"
FILESTORE_SRC="${FILESTORE_SRC%/}"
if [ "${BACKUP_FILESTORE_COMPRESS}" = "true" ]; then
    FILESTORE_EXT="tar.gz"
    FILESTORE_TAR_FLAGS="-czf"
else
    FILESTORE_EXT="tar"
    FILESTORE_TAR_FLAGS="-cf"
fi
FILESTORE_BACKUP_FILE="${PGDATABASE:-openspp}_filestore_${TIMESTAMP}.${FILESTORE_EXT}"
FILESTORE_BACKUP_CREATED=0

if [ "${BACKUP_FILESTORE}" != "true" ]; then
    echo "[$(date -Iseconds)] Filestore backup disabled (BACKUP_FILESTORE=${BACKUP_FILESTORE})"
elif [ ! -d "${FILESTORE_SRC}" ]; then
    echo "[$(date -Iseconds)] Filestore not found at ${FILESTORE_SRC}; skipping filestore backup"
else
    echo "[$(date -Iseconds)] Starting filestore backup from ${FILESTORE_SRC}..."
    # tar exits 1 when Odoo's filestore GC unlinks a file mid-archive. Running it
    # as an `if` condition keeps `set -e` from skipping the retention pass below.
    if tar ${FILESTORE_TAR_FLAGS} "${DAILY_DIR}/${FILESTORE_BACKUP_FILE}.part" \
           -C "$(dirname "${FILESTORE_SRC}")" "$(basename "${FILESTORE_SRC}")"; then
        mv "${DAILY_DIR}/${FILESTORE_BACKUP_FILE}.part" "${DAILY_DIR}/${FILESTORE_BACKUP_FILE}"
        ln -sf "${FILESTORE_BACKUP_FILE}" "${DAILY_DIR}/${PGDATABASE:-openspp}_filestore_latest.${FILESTORE_EXT}"
        FILESTORE_BACKUP_CREATED=1
        echo "[$(date -Iseconds)] Filestore backup complete: ${FILESTORE_BACKUP_FILE}"
    else
        rm -f "${DAILY_DIR}/${FILESTORE_BACKUP_FILE}.part"
        echo "[$(date -Iseconds)] WARNING: filestore backup failed; database dump kept"
    fi
fi

# Weekly backup (Sunday)
if [ "${DAY_OF_WEEK}" = "7" ]; then
    cp "${DAILY_DIR}/${BACKUP_FILE}" "${WEEKLY_DIR}/"
    if [ "${FILESTORE_BACKUP_CREATED}" = "1" ] && [ -f "${DAILY_DIR}/${FILESTORE_BACKUP_FILE}" ]; then
        cp "${DAILY_DIR}/${FILESTORE_BACKUP_FILE}" "${WEEKLY_DIR}/"
    fi
    echo "[$(date -Iseconds)] Weekly backup saved"
fi

# Monthly backup (1st of month)
if [ "${DAY_OF_MONTH}" = "01" ]; then
    cp "${DAILY_DIR}/${BACKUP_FILE}" "${MONTHLY_DIR}/"
    if [ "${FILESTORE_BACKUP_CREATED}" = "1" ] && [ -f "${DAILY_DIR}/${FILESTORE_BACKUP_FILE}" ]; then
        cp "${DAILY_DIR}/${FILESTORE_BACKUP_FILE}" "${MONTHLY_DIR}/"
    fi
    echo "[$(date -Iseconds)] Monthly backup saved"
fi

# Cleanup old backups
echo "[$(date -Iseconds)] Cleaning up old backups..."

# Remove daily backups older than BACKUP_KEEP_DAYS
find "${DAILY_DIR}" -name "*.dump" -type f -mtime +${BACKUP_KEEP_DAYS} -delete 2>/dev/null || true

# Remove weekly backups older than BACKUP_KEEP_WEEKS weeks
find "${WEEKLY_DIR}" -name "*.dump" -type f -mtime +$((BACKUP_KEEP_WEEKS * 7)) -delete 2>/dev/null || true

# Remove monthly backups older than BACKUP_KEEP_MONTHS months (approximate: 30 days per month)
find "${MONTHLY_DIR}" -name "*.dump" -type f -mtime +$((BACKUP_KEEP_MONTHS * 30)) -delete 2>/dev/null || true

# Filestore retention stays outside the BACKUP_FILESTORE guard so archives age out
# even after the feature is turned back off.
find "${DAILY_DIR}" -name "*_filestore_*.tar*" -type f -mtime +${BACKUP_FILESTORE_KEEP_DAYS} -delete 2>/dev/null || true
find "${WEEKLY_DIR}" -name "*_filestore_*.tar*" -type f -mtime +$((BACKUP_FILESTORE_KEEP_WEEKS * 7)) -delete 2>/dev/null || true
find "${MONTHLY_DIR}" -name "*_filestore_*.tar*" -type f -mtime +$((BACKUP_FILESTORE_KEEP_MONTHS * 30)) -delete 2>/dev/null || true

# Report disk usage
echo "[$(date -Iseconds)] Backup sizes:"
du -sh "${DAILY_DIR}" "${WEEKLY_DIR}" "${MONTHLY_DIR}" 2>/dev/null || true

echo "[$(date -Iseconds)] Backup complete"
