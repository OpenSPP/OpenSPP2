#!/usr/bin/env bash
# Run coverage for a single OpenSPP module against the docker stack.
# Mirrors the CI recipe in .github/workflows/ci.yml so local numbers
# match what gets reported in CI.
#
# Usage: ./scripts/coverage_single_module.sh <module_name>

set -e

MODULE_NAME="${1:?usage: $0 <module_name>}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

DB_NAME="cov_${MODULE_NAME}_$$"
COV_FILE="/tmp/.coverage.${MODULE_NAME}.$$"
LOG_FILE="/tmp/openspp-test-logs/${MODULE_NAME}_coverage_$(date +%Y%m%d_%H%M%S).log"
mkdir -p "$(dirname "$LOG_FILE")"

# Ensure DB container is up.
if ! docker compose ps db --status running --quiet >/dev/null 2>&1; then
    docker compose up -d db >/dev/null 2>&1
    until docker compose exec -T db pg_isready -U odoo -d postgres >/dev/null 2>&1; do
        sleep 1
    done
fi

# Fresh database per run.
docker compose exec -T db psql -U odoo -d postgres -c "DROP DATABASE IF EXISTS $DB_NAME;" >/dev/null 2>&1
docker compose exec -T db psql -U odoo -d postgres -c "CREATE DATABASE $DB_NAME;" >/dev/null 2>&1

echo "Running coverage for $MODULE_NAME (log: $LOG_FILE)..."

set +e
docker compose run --rm \
    -e DB_NAME="$DB_NAME" \
    -e COVERAGE_FILE="$COV_FILE" \
    --entrypoint "" \
    test \
    bash -c "
        coverage run --branch --source=/mnt/extra-addons/openspp/${MODULE_NAME} \
            /opt/odoo/odoo/odoo-bin \
            --addons-path=/opt/odoo/odoo/addons,/opt/odoo/odoo/odoo/addons,/mnt/extra-addons/openspp,/mnt/extra-addons/server-ux,/mnt/extra-addons/server-tools,/mnt/extra-addons/odoo-job-worker,/mnt/extra-addons/server-backend,/mnt/extra-addons/rest-framework,/mnt/extra-addons/muk-it \
            -d $DB_NAME \
            --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
            --stop-after-init --no-http \
            --data-dir /tmp/odoo-data \
            -i ${MODULE_NAME} \
            --test-tags /${MODULE_NAME} \
            --log-level=test 2>&1 | tee /tmp/test_output_${MODULE_NAME}.log
        echo '===COVERAGE REPORT==='
        coverage report --skip-empty --skip-covered --omit='*/tests/*,*/migrations/*' || true
        echo '===COVERAGE TOTAL==='
        coverage report --omit='*/tests/*,*/migrations/*' | tail -2 || true
    " > "$LOG_FILE" 2>&1
EXIT=$?
set -e

docker compose exec -T db psql -U odoo -d postgres -c "DROP DATABASE IF EXISTS $DB_NAME;" >/dev/null 2>&1

echo "=== $MODULE_NAME coverage ==="
sed -n '/===COVERAGE TOTAL===/,$p' "$LOG_FILE" | tail -3
echo "(full log: $LOG_FILE)"
exit $EXIT
