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

| File                            | Description                                       |
| ------------------------------- | ------------------------------------------------- |
| `Dockerfile`                    | Multi-stage build for OpenSPP                     |
| `docker-compose.production.yml` | Production stack (Traefik + Odoo + Queue Worker)  |
| `.env.production.example`       | Production configuration template                 |
| `entrypoint.sh`                 | Container entrypoint with database initialization |
| `odoo.conf.template`            | Odoo configuration template                       |
| `requirements.txt`              | Python dependencies beyond module manifests       |
| `requirements-dev.txt`          | Development-only dependencies                     |

## Production Deployment

### Architecture

```
Internet -> Traefik (SSL) -> Odoo (workers) -> PostgreSQL
                          -> Queue Worker
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
docker compose -f docker/docker-compose.production.yml up -d
```

4. **View logs:**

```bash
docker compose -f docker/docker-compose.production.yml logs -f odoo
```

### Using External Database (RDS/Cloud SQL)

1. Set `DATABASE_URL` in `.env.production`:

```bash
DATABASE_URL=postgres://user:password@hostname:5432/openspp?sslmode=require
```

2. Comment out or remove the `db` service in `docker-compose.production.yml`

3. Update `depends_on` in `odoo` and `queue-worker` services

### Backups

The production stack includes automated PostgreSQL backups:

- **Schedule:** Daily at 2am (configurable via `BACKUP_SCHEDULE`)
- **Retention:** 7 daily, 4 weekly, 6 monthly
- **Location:** `backup_data` Docker volume

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
# Start with ClamAV profile
docker compose -f docker/docker-compose.production.yml --profile clamav up -d
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

| Variable                  | Default    | Description                           |
| ------------------------- | ---------- | ------------------------------------- |
| `ODOO_WORKERS`            | 2          | Number of worker processes            |
| `ODOO_CRON_THREADS`       | 1          | Number of cron threads                |
| `ODOO_MEMORY_SOFT`        | 2147483648 | Soft memory limit per worker (bytes)  |
| `ODOO_MEMORY_HARD`        | 2684354560 | Hard memory limit per worker (bytes)  |
| `ODOO_TIME_CPU`           | 600        | CPU time limit per request (seconds)  |
| `ODOO_TIME_REAL`          | 1200       | Real time limit per request (seconds) |
| `ODOO_QUEUE_JOB_CHANNELS` | root:2     | Concurrent background jobs            |

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
