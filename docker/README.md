# OpenSPP Docker

Docker configuration for deploying OpenSPP with Odoo 19.0 (OCB).

## Quick Start

### Development

```bash
# From repository root
docker compose --profile ui up -d

# Access at http://localhost:8069 (admin/admin)
```

### Production

See [Production Deployment](#production-deployment) below.

## Files

| File                                 | Description                                       |
| ------------------------------------ | ------------------------------------------------- |
| `Dockerfile`                         | Multi-stage build for OpenSPP                     |
| `docker-compose.production.yml`      | Production stack (Traefik + Odoo + Queue Worker)  |
| `docker-compose.nginx.yml`           | Production stack (Nginx + Certbot + Fluentd)      |
| `.env.production.example`            | Production configuration template                 |
| `entrypoint.sh`                      | Container entrypoint with database initialization |
| `odoo.conf.template`                 | Odoo configuration template                       |
| `nginx/odoo.conf.template`           | Nginx HTTPS reverse proxy config (Odoo docs)      |
| `nginx/odoo-http-only.conf.template` | Nginx HTTP-only reverse proxy config              |
| `nginx/certbot-init.sh`              | Bootstrap script for initial SSL certificate      |
| `fluentd/`                           | Fluentd log collection configs                    |
| `backup.sh`                          | Automated PostgreSQL/PostGIS backup script        |
| `backup-entrypoint.sh`               | Backup container entrypoint with cron scheduling  |
| `requirements.txt`                   | Python dependencies beyond module manifests       |
| `requirements-dev.txt`               | Development-only dependencies                     |

## Production Deployment

Two production compose files are available:

| Compose file                    | Reverse proxy | SSL                       | Logging        |
| ------------------------------- | ------------- | ------------------------- | -------------- |
| `docker-compose.production.yml` | Traefik       | Let's Encrypt (automatic) | Docker default |
| `docker-compose.nginx.yml`      | Nginx         | Certbot (Let's Encrypt)   | Fluentd        |

### Architecture (Traefik)

```
Internet -> Traefik (SSL) -> Odoo (workers) -> PostgreSQL
                          -> Queue Worker
```

### Architecture (Nginx)

```
Internet -> Nginx (SSL) -> Odoo (workers) -> PostgreSQL
                        -> Queue Worker
         Certbot (certificate renewal)
         Fluentd (log collection -> local/NFS, S3, GCS, Azure, MinIO)
         ClamAV (antivirus, optional)
         Backup (daily PostgreSQL dumps)
```

### Requirements

- VPS with Docker and Docker Compose v2
- Domain name pointing to your VPS
- PostgreSQL 16+ (local or managed like RDS)

### Sizing Guide

| Scale              | VPS           | Workers | RAM (Odoo) | RAM (DB) |
| ------------------ | ------------- | ------- | ---------- | -------- |
| 10k beneficiaries  | 4 vCPU / 8GB  | 2       | 4GB        | 3GB      |
| 50k beneficiaries  | 4 vCPU / 16GB | 4       | 8GB        | 6GB      |
| 100k beneficiaries | 8 vCPU / 32GB | 6       | 12GB       | 16GB     |

### Setup

1. **Configure environment:**

```bash
cp docker/.env.production.example docker/.env.production
# Edit docker/.env.production with your settings
```

2. **Required settings in `.env.production`:**

```bash
DOMAIN=openspp.example.org
ACME_EMAIL=admin@example.org
DB_PASSWORD=<strong-random-password>
ODOO_ADMIN_PASSWD=<strong-random-password>
```

3. **Start services:**

```bash
# Traefik stack
docker compose -f docker/docker-compose.production.yml up -d

# Nginx stack (HTTPS)
docker compose -f docker/docker-compose.nginx.yml --profile https up -d
```

4. **View logs:**

```bash
docker compose -f docker/docker-compose.production.yml logs -f odoo
# or
docker compose -f docker/docker-compose.nginx.yml logs -f odoo
```

### Nginx Profiles

The Nginx compose file uses profiles to select the deployment mode:

| Profile  | Services added        | Use case                               |
| -------- | --------------------- | -------------------------------------- |
| `https`  | Nginx (SSL) + Certbot | Production with HTTPS and auto-renewal |
| `http`   | Nginx (HTTP only)     | Dev or isolated on-premises networks   |
| `clamav` | ClamAV antivirus      | File upload scanning (~1GB extra RAM)  |

Profiles can be combined:

```bash
# HTTPS + ClamAV
docker compose -f docker/docker-compose.nginx.yml --profile https --profile clamav up -d

# Or set in .env.production (no --profile flags needed):
COMPOSE_PROFILES=https,clamav
```

HTTP-only mode (no SSL, no Certbot):

```bash
docker compose -f docker/docker-compose.nginx.yml --profile http up -d
```

### Nginx SSL Certificate Setup

1. **Obtain initial certificate** (HTTPS profile only):

```bash
docker compose -f docker/docker-compose.nginx.yml run --rm certbot \
  certonly --webroot -w /var/www/certbot \
  --email ${ACME_EMAIL} -d ${DOMAIN} --agree-tos --non-interactive

# Reload nginx to pick up the new certificate
docker compose -f docker/docker-compose.nginx.yml exec nginx nginx -s reload
```

2. **Schedule renewal** via system cron (certificates expire every 90 days):

```bash
# Add to system crontab (runs monthly)
0 3 1 * * cd /path/to/your/project && docker compose -f docker/docker-compose.nginx.yml run --rm certbot renew && docker compose -f docker/docker-compose.nginx.yml exec nginx nginx -s reload
```

### Nginx Security Hardening

All services in the Nginx compose file include:

- **Capability dropping:** `cap_drop: ALL` with minimal `cap_add` per service
- **No privilege escalation:** `security_opt: no-new-privileges:true`
- **Read-only filesystems:** `read_only: true` with targeted tmpfs mounts (where
  possible)
- **Resource limits:** CPU and memory limits on every service
- **Log rotation:** `json-file` driver with 5MB/3-file rotation (15MB max per service)
- **SELinux compatibility:** `:ro,z` and `:rw,z` volume flags

Nginx adds: rate limiting, security headers (HSTS, CSP, X-Frame-Options), OCSP stapling,
proxy buffering, `/web/database` blocking.

### Centralized Logging with Fluentd (Nginx stack)

The Nginx compose file includes Fluentd for centralized log collection. It uses file
tailing (not Docker's log driver), so `docker compose logs` keeps working and logs are
never lost if Fluentd goes down.

**Default backend:** Local filesystem / NFS (`output-file.conf`)

**Available backends:**

| Backend          | Config file                  | Plugins required                        |
| ---------------- | ---------------------------- | --------------------------------------- |
| Local / NFS      | `output-file.conf` (default) | None (built-in)                         |
| AWS S3           | `output-s3.conf.example`     | fluent-plugin-s3                        |
| Google Cloud GCS | `output-gcs.conf.example`    | fluent-plugin-gcs                       |
| Azure Blob       | `output-azure.conf.example`  | fluent-plugin-azure-storage-append-blob |
| MinIO            | `output-minio.conf.example`  | fluent-plugin-s3                        |

To switch backends:

1. Edit `docker/fluentd/fluent.conf` to `@include` the desired output config
2. For cloud backends, uncomment the `build:` block in the fluentd service to install
   plugins

### Using External Database (RDS/Cloud SQL)

1. Set `DATABASE_URL` in `.env.production`:

```bash
DATABASE_URL=postgres://user:password@hostname:5432/openspp?sslmode=require
```

2. Comment out or remove the `db` service in the compose file

3. Update `depends_on` in `odoo` and `queue-worker` services

### Backups

The production stack includes automated PostgreSQL backups:

- **Schedule:** Daily at 2am (configurable via `BACKUP_SCHEDULE`)
- **Retention:** 7 daily, 4 weekly, 6 monthly
- **Location:** `backup_data` Docker volume
- **Filestore:** When the `odoo_data` volume is mounted on the backup service, attachments under `/odoo_data/filestore/<database>` are archived daily as `*_filestore_*.tar.gz` alongside the database dump

To restore a backup:

```bash
# List backups
docker compose -f docker/docker-compose.production.yml exec backup ls -la /backups

# Restore (stop services first)
docker compose -f docker/docker-compose.production.yml stop odoo queue-worker
docker compose -f docker/docker-compose.production.yml exec db \
  pg_restore -U odoo -d openspp /backups/daily/openspp-YYYYMMDD-HHMMSS.sql.gz
docker compose -f docker/docker-compose.production.yml start odoo queue-worker
```

### Updating

```bash
# Pull latest images
docker compose -f docker/docker-compose.production.yml pull

# Restart with new images
docker compose -f docker/docker-compose.production.yml up -d

# Or rebuild from source
docker compose -f docker/docker-compose.production.yml build --no-cache
docker compose -f docker/docker-compose.production.yml up -d
```

### Antivirus Scanning (Optional)

ClamAV antivirus scanning is available as an optional profile. Enable it when:

- Accepting file uploads from beneficiaries
- Processing documents from external sources
- Compliance requirements mandate antivirus scanning

**Enable ClamAV:**

```bash
# Traefik stack
docker compose -f docker/docker-compose.production.yml --profile clamav up -d

# Nginx stack
docker compose -f docker/docker-compose.nginx.yml --profile https --profile clamav up -d
```

**Configure Odoo:**

1. Install the `spp_attachment_av_scan` module in Odoo
2. Go to Settings > Technical > Antivirus Backends
3. Create a new backend with:
   - **Type:** ClamAV Network
   - **Host:** clamav
   - **Port:** 3310
4. Test the connection and activate the backend

**Resource usage:** ~1GB RAM for virus definitions

**Check ClamAV status:**

```bash
# View ClamAV logs
docker compose -f docker/docker-compose.production.yml logs clamav

# Check virus definition version
docker compose -f docker/docker-compose.production.yml exec clamav clamscan --version
```

## Environment Variables

### Required

| Variable            | Description                           |
| ------------------- | ------------------------------------- |
| `COMPOSE_PROFILES`  | Deployment profile (Nginx stack only) |
| `DB_PASSWORD`       | PostgreSQL password                   |
| `ODOO_ADMIN_PASSWD` | Odoo admin/master password            |
| `DOMAIN`            | Domain name (production only)         |
| `ACME_EMAIL`        | Let's Encrypt email (production only) |

### Database

| Variable       | Default | Description                                          |
| -------------- | ------- | ---------------------------------------------------- |
| `DATABASE_URL` | -       | Full connection URL (alternative to individual vars) |
| `DB_HOST`      | db      | PostgreSQL hostname                                  |
| `DB_PORT`      | 5432    | PostgreSQL port                                      |
| `DB_USER`      | odoo    | Database username                                    |
| `DB_NAME`      | openspp | Database name                                        |
| `DB_SSLMODE`   | prefer  | SSL mode (disable/allow/prefer/require)              |

### Performance

| Variable            | Default    | Description                           |
| ------------------- | ---------- | ------------------------------------- |
| `ODOO_WORKERS`      | 2          | Number of worker processes            |
| `ODOO_CRON_THREADS` | 1          | Number of cron threads                |
| `ODOO_MEMORY_SOFT`  | 2147483648 | Soft memory limit per worker (bytes)  |
| `ODOO_MEMORY_HARD`  | 2684354560 | Hard memory limit per worker (bytes)  |
| `ODOO_TIME_CPU`     | 600        | CPU time limit per request (seconds)  |
| `ODOO_TIME_REAL`    | 1200       | Real time limit per request (seconds) |

### Resource Limits (Nginx stack)

| Variable              | Default | Description               |
| --------------------- | ------- | ------------------------- |
| `ODOO_CPU_LIMIT`      | 2       | Odoo CPU cores            |
| `ODOO_MEMORY_LIMIT`   | 4G      | Odoo memory limit         |
| `DB_CPU_LIMIT`        | 2       | PostgreSQL CPU cores      |
| `DB_MEMORY_LIMIT`     | 4G      | PostgreSQL memory limit   |
| `QUEUE_CPU_LIMIT`     | 1       | Queue worker CPU cores    |
| `QUEUE_MEMORY_LIMIT`  | 2G      | Queue worker memory limit |
| `NGINX_CPU_LIMIT`     | 1       | Nginx CPU cores           |
| `NGINX_MEMORY_LIMIT`  | 256M    | Nginx memory limit        |
| `CLAMAV_MEMORY_LIMIT` | 1536M   | ClamAV memory limit       |

### Logging

| Variable    | Default | Description                       |
| ----------- | ------- | --------------------------------- |
| `LOG_LEVEL` | info    | Log level (debug/info/warn/error) |

## Build

```bash
# Standard build
docker build -f docker/Dockerfile -t openspp .

# With development tools
docker build --build-arg INSTALL_DEV=1 -f docker/Dockerfile -t openspp:dev .
```

## Health Check

The container exposes a health endpoint at `/web/health` on port 8069.

## Ports

- `8069` - HTTP (Odoo web interface)
- `8072` - Longpolling (websocket)
