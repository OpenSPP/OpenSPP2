#!/bin/sh
# certbot-init.sh — Bootstrap SSL certificates for a fresh deployment
#
# This script:
#   1. Starts Nginx in HTTP-only mode (self-signed temp cert)
#   2. Runs Certbot to obtain real certificates via webroot challenge
#   3. Reloads Nginx with the real certificates
#
# Usage:
#   cd /path/to/project
#   ./docker/nginx/certbot-init.sh
#
# Prerequisites:
#   - docker/.env.production is configured (DOMAIN and ACME_EMAIL set)
#   - Ports 80 and 443 are reachable from the internet
#   - DNS A record for DOMAIN points to this server

set -eu

COMPOSE_FILE="docker/docker-compose.nginx.yml"
ENV_FILE="docker/.env.production"

if [ ! -f "$ENV_FILE" ]; then
    echo "Error: $ENV_FILE not found. Copy from .env.production.example first."
    exit 1
fi

# shellcheck disable=SC1090
. "$ENV_FILE"

if [ -z "${DOMAIN:-}" ] || [ -z "${ACME_EMAIL:-}" ]; then
    echo "Error: DOMAIN and ACME_EMAIL must be set in $ENV_FILE"
    exit 1
fi

echo "==> Creating temporary self-signed certificate for $DOMAIN ..."
docker compose -f "$COMPOSE_FILE" run --rm --entrypoint sh nginx -c "
    mkdir -p /etc/letsencrypt/live/$DOMAIN &&
    openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
        -keyout /etc/letsencrypt/live/$DOMAIN/privkey.pem \
        -out /etc/letsencrypt/live/$DOMAIN/fullchain.pem \
        -subj '/CN=localhost'
"

echo "==> Starting Nginx (temporary certificate) ..."
docker compose -f "$COMPOSE_FILE" up -d nginx

echo "==> Requesting certificate from Let's Encrypt for $DOMAIN ..."
docker compose -f "$COMPOSE_FILE" --profile certbot run --rm certbot \
    certonly --webroot -w /var/www/certbot \
    --email "$ACME_EMAIL" -d "$DOMAIN" \
    --agree-tos --non-interactive --force-renewal

echo "==> Reloading Nginx with real certificate ..."
docker compose -f "$COMPOSE_FILE" exec nginx nginx -s reload

echo "==> Done! SSL certificate obtained for $DOMAIN"
echo ""
echo "To start all services:"
echo "  docker compose -f $COMPOSE_FILE up -d"
echo ""
echo "To renew certificates (schedule via cron every 3 months):"
echo "  docker compose -f $COMPOSE_FILE --profile certbot run --rm certbot renew"
echo "  docker compose -f $COMPOSE_FILE exec nginx nginx -s reload"
