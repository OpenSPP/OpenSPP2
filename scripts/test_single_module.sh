#!/bin/bash
# Test a single OpenSPP module for Odoo 19 compatibility
# Optimized for AI agents - minimal output, full details in log file
#
# Supports two modes:
#   - Docker mode (default): Uses docker compose to run tests
#   - Local mode: When CLAUDE_CODE_REMOTE=true, uses local venv
#
# Usage: ./scripts/test_single_module.sh <module_name> [options]
#
# Options:
#   --docker         Force Docker mode
#   --local          Force local mode (requires CLAUDE_CODE_REMOTE environment)
#   --test-tags=...  Override test tags (passed to Odoo)
#   --log-level=...  Override log level (passed to Odoo)
#
# Prerequisites:
#   - Docker mode: Docker with compose plugin
#   - Local mode: Run ./scripts/setup_test_env.sh first

set -e

# Project root directory (where docker-compose.yml is)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Parse arguments
MODULE_NAME=""
FORCE_DOCKER=false
FORCE_LOCAL=false
EXTRA_ARGS=""

for arg in "$@"; do
    case "$arg" in
        --docker) FORCE_DOCKER=true ;;
        --local) FORCE_LOCAL=true ;;
        --test-tags=*|--log-level=*) EXTRA_ARGS="$EXTRA_ARGS $arg" ;;
        -*) EXTRA_ARGS="$EXTRA_ARGS $arg" ;;
        *) [ -z "$MODULE_NAME" ] && MODULE_NAME="$arg" ;;
    esac
done

if [ -z "$MODULE_NAME" ]; then
    echo "Usage: $0 <module_name> [options]"
    echo ""
    echo "Options:"
    echo "  --docker         Force Docker mode (default when not in Claude Code remote)"
    echo "  --local          Force local mode (requires CLAUDE_CODE_REMOTE=true)"
    echo "  --test-tags=...  Override test tags (e.g., --test-tags=post_install)"
    echo "  --log-level=...  Override log level"
    echo ""
    echo "Examples:"
    echo "  $0 spp_base                           # Run all tests"
    echo "  $0 spp_base --test-tags=post_install  # Run only post_install tests"
    echo "  $0 spp_base --docker                  # Force Docker mode"
    exit 1
fi

# Configuration - shared
LOG_DIR="/tmp/openspp-test-logs"
mkdir -p "$LOG_DIR"
DB_NAME="test_${MODULE_NAME}_$(shuf -i 1000000-9999999 -n 1)"
LOG_FILE="$LOG_DIR/${MODULE_NAME}_unittest_$(date +%Y%m%d_%H%M%S).log"
BUILD_LOG_FILE="$LOG_DIR/${MODULE_NAME}_build_$(date +%Y%m%d_%H%M%S).log"

# Note: COMPOSE_PROJECT_NAME is NOT set here - we use the default (directory name)
# This ensures test and dev share the same images/containers within a clone
# Different clones/worktrees naturally get different project names from their directory

# Configuration - local mode
ODOO_DIR="/tmp/odoo-19"
VENV_DIR="/tmp/odoo19-venv"
CONF_FILE="/tmp/odoo19-test.conf"
ADDONS_DIR="/tmp/odoo19-addons"

# Determine test tags and log level
TEST_TAGS="/$MODULE_NAME"
LOG_LEVEL="test"
for arg in $EXTRA_ARGS; do
    case "$arg" in
        --test-tags=*) TEST_TAGS="${arg#--test-tags=}" ;;
        --log-level=*) LOG_LEVEL="${arg#--log-level=}" ;;
    esac
done

#==============================================================================
# DOCKER MODE FUNCTIONS
#==============================================================================

ensure_docker() {
    if ! command -v docker &>/dev/null; then
        echo "ERROR: Docker is not installed or not in PATH"
        echo "       Install Docker: https://docs.docker.com/get-docker/"
        exit 1
    fi

    if ! docker info &>/dev/null; then
        echo "ERROR: Docker daemon is not running or you don't have permission"
        echo "       Try: sudo usermod -aG docker \$USER && newgrp docker"
        exit 1
    fi

    if ! docker compose version &>/dev/null; then
        echo "ERROR: Docker Compose plugin not found"
        echo "       Install: https://docs.docker.com/compose/install/"
        exit 1
    fi
}

ensure_db_container() {
    cd "$PROJECT_ROOT"

    # Check if db container is running (match "-db-" to avoid matching "wdb" etc.)
    if docker compose ps --status running 2>/dev/null | grep -qE "\-db-[0-9]+"; then
        return 0
    fi

    echo "Starting PostgreSQL container..."
    docker compose up -d db

    # Wait for health check
    echo "Waiting for PostgreSQL to be ready..."
    for i in {1..30}; do
        if docker compose exec -T db pg_isready -U odoo -d postgres &>/dev/null; then
            echo "PostgreSQL ready"
            return 0
        fi
        sleep 1
    done

    echo "ERROR: PostgreSQL failed to start"
    docker compose logs db
    exit 1
}

build_test_image() {
    cd "$PROJECT_ROOT"

    # Get build hash from spp CLI (single source of truth)
    local build_hash
    build_hash=$("$PROJECT_ROOT/spp" _get_build_hash 2>/dev/null || echo "unknown")

    # Use same marker file format as spp CLI (profile=dev since test uses same image)
    local marker_file="/tmp/.openspp-build-dev-${build_hash}"

    # Check if we need to rebuild
    if [ -f "$marker_file" ]; then
        # Check if openspp-dev image exists (shared by odoo, odoo-dev, and test services)
        if docker images openspp-dev --format "{{.Repository}}" 2>/dev/null | grep -q "openspp-dev"; then
            return 0
        fi
    fi

    # Build via openspp service (test service uses same openspp-dev image, no separate build)
    echo "Building openspp-dev image... (log: $BUILD_LOG_FILE)"
    if ! docker compose build openspp > "$BUILD_LOG_FILE" 2>&1; then
        echo "Build failed. Last 30 lines:"
        tail -30 "$BUILD_LOG_FILE"
        exit 1
    fi
    echo "Build complete"

    # Mark as built (same marker as spp uses)
    touch "$marker_file"
}

run_tests_docker() {
    cd "$PROJECT_ROOT"

    # Check module exists
    if [ ! -d "$PROJECT_ROOT/$MODULE_NAME" ]; then
        echo "ERROR: Module '$MODULE_NAME' not found in $PROJECT_ROOT"
        echo "       Available modules: $(ls -d spp_* 2>/dev/null | head -5 | tr '\n' ' ')..."
        exit 1
    fi

    echo "Testing module: $MODULE_NAME (Docker mode)"
    echo "Log file: $LOG_FILE"

    ensure_docker
    ensure_db_container
    build_test_image

    echo "Creating test database..."
    docker compose exec -T db psql -U odoo -d postgres -c "CREATE DATABASE $DB_NAME;" >/dev/null 2>&1 || {
        echo "ERROR: Failed to create test database"
        exit 1
    }

    echo "Running tests (this may take a few minutes)..."

    # Run tests in container
    set +e
    docker compose run --rm \
        -e DB_NAME="$DB_NAME" \
        --entrypoint "" \
        test \
        /opt/odoo/odoo/odoo-bin \
        --addons-path=/opt/odoo/odoo/addons,/opt/odoo/odoo/odoo/addons,/mnt/extra-addons/openspp,/mnt/extra-addons/server-ux,/mnt/extra-addons/server-tools,/mnt/extra-addons/queue,/mnt/extra-addons/odoo-job-worker,/mnt/extra-addons/server-backend,/mnt/extra-addons/rest-framework,/mnt/extra-addons/muk-it \
        -d "$DB_NAME" \
        --db_host=db \
        --db_port=5432 \
        --db_user=odoo \
        --db_password=odoo \
        --stop-after-init \
        --no-http \
        -i "$MODULE_NAME" \
        --test-tags "$TEST_TAGS" \
        --log-level="$LOG_LEVEL" \
        > "$LOG_FILE" 2>&1
    TEST_EXIT_CODE=$?
    set -e

    # Cleanup database
    docker compose exec -T db psql -U odoo -d postgres -c "DROP DATABASE IF EXISTS $DB_NAME;" >/dev/null 2>&1

    return $TEST_EXIT_CODE
}

#==============================================================================
# LOCAL MODE FUNCTIONS (for Claude Code remote environment)
#==============================================================================

check_local_prerequisites() {
    local errors=0

    if [ ! -d "$VENV_DIR" ] || [ ! -f "$VENV_DIR/bin/activate" ]; then
        echo "ERROR: Virtual environment not found at $VENV_DIR"
        echo "       Run: ./scripts/setup_test_env.sh"
        errors=$((errors + 1))
    fi

    if [ ! -f "$ODOO_DIR/odoo-bin" ]; then
        echo "ERROR: Odoo not found at $ODOO_DIR"
        echo "       Run: ./scripts/setup_test_env.sh"
        errors=$((errors + 1))
    fi

    if [ ! -f "$CONF_FILE" ]; then
        echo "ERROR: Odoo config not found at $CONF_FILE"
        echo "       Run: ./scripts/setup_test_env.sh"
        errors=$((errors + 1))
    fi

    if [ ! -d "$ADDONS_DIR/$MODULE_NAME" ] && [ ! -L "$ADDONS_DIR/$MODULE_NAME" ]; then
        echo "ERROR: Module '$MODULE_NAME' not found in $ADDONS_DIR"
        echo "       Available modules: $(ls $ADDONS_DIR 2>/dev/null | head -10 | tr '\n' ' ')..."
        errors=$((errors + 1))
    fi

    [ $errors -gt 0 ] && return 1
    return 0
}

ensure_local_postgres() {
    if pg_isready -q 2>/dev/null; then
        ensure_odoo_user
        return 0
    fi

    echo "PostgreSQL not running, starting..."

    if command -v pg_ctlcluster &>/dev/null; then
        PG_VERSION=$(ls /etc/postgresql/ 2>/dev/null | head -1)
        if [ -n "$PG_VERSION" ]; then
            pg_ctlcluster "$PG_VERSION" main start 2>/dev/null || true
        fi
    fi
    service postgresql start 2>/dev/null || true

    for i in {1..10}; do
        if pg_isready -q 2>/dev/null; then
            break
        fi
        sleep 1
    done

    if ! pg_isready -q 2>/dev/null; then
        echo "ERROR: Failed to start PostgreSQL"
        return 1
    fi

    local pg_hba=$(ls /etc/postgresql/*/main/pg_hba.conf 2>/dev/null | head -1)
    if [ -n "$pg_hba" ]; then
        if grep -q "local.*all.*all.*peer" "$pg_hba" 2>/dev/null; then
            sed -i 's/local\s\+all\s\+all\s\+peer/local   all             all                                     trust/' "$pg_hba" 2>/dev/null || true
            sed -i 's/local\s\+all\s\+postgres\s\+peer/local   all             postgres                                trust/' "$pg_hba" 2>/dev/null || true
            if command -v pg_ctlcluster &>/dev/null; then
                pg_ctlcluster "$PG_VERSION" main reload 2>/dev/null || true
            else
                service postgresql reload 2>/dev/null || true
            fi
            sleep 1
        fi
    fi

    ensure_odoo_user
    echo "PostgreSQL ready"
    return 0
}

ensure_odoo_user() {
    local db_password="odoo_password"
    if [ -f "$CONF_FILE" ]; then
        db_password=$(grep "^db_password" "$CONF_FILE" 2>/dev/null | cut -d'=' -f2 | tr -d ' ' || echo "odoo_password")
    fi

    if ! runuser -u postgres -- psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='odoo'" 2>/dev/null | grep -q 1; then
        echo "Creating PostgreSQL user 'odoo'..."
        runuser -u postgres -- psql -c "CREATE ROLE odoo LOGIN SUPERUSER PASSWORD '$db_password';" 2>/dev/null || true
    else
        runuser -u postgres -- psql -c "ALTER USER odoo WITH PASSWORD '$db_password';" 2>/dev/null || true
    fi
}

check_python_deps() {
    local module_dir="$ADDONS_DIR/$MODULE_NAME"
    local manifest="$module_dir/__manifest__.py"

    [ ! -f "$manifest" ] && return 0

    local python_deps=$(python3 -c "
import ast
try:
    with open('$manifest') as f:
        manifest = ast.literal_eval(f.read())
    deps = manifest.get('external_dependencies', {}).get('python', [])
    print(' '.join(deps))
except:
    pass
" 2>/dev/null)

    [ -z "$python_deps" ] && return 0

    local missing=""
    source "$VENV_DIR/bin/activate"
    for dep in $python_deps; do
        if ! python3 -c "import $dep" 2>/dev/null; then
            if ! pip show "$dep" >/dev/null 2>&1; then
                missing="$missing $dep"
            fi
        fi
    done

    if [ -n "$missing" ]; then
        echo "WARNING: Missing Python dependencies:$missing"
        echo "         Installing..."
        pip install $missing 2>/dev/null || {
            echo "ERROR: Failed to install:$missing"
            return 1
        }
    fi

    return 0
}

run_tests_local() {
    echo "Testing module: $MODULE_NAME (Local mode)"
    echo "Log file: $LOG_FILE"

    if ! check_local_prerequisites; then
        exit 1
    fi

    ensure_local_postgres

    echo "Checking Python dependencies..."
    check_python_deps

    # Check dependencies of module dependencies
    for dep_module in $(python3 -c "
import ast
try:
    with open('$ADDONS_DIR/$MODULE_NAME/__manifest__.py') as f:
        manifest = ast.literal_eval(f.read())
    for dep in manifest.get('depends', []):
        if dep.startswith('spp_'):
            print(dep)
except:
    pass
" 2>/dev/null); do
        if [ -f "$ADDONS_DIR/$dep_module/__manifest__.py" ]; then
            MODULE_NAME_ORIG="$MODULE_NAME"
            MODULE_NAME="$dep_module"
            check_python_deps 2>/dev/null || true
            MODULE_NAME="$MODULE_NAME_ORIG"
        fi
    done

    echo "Creating test database..."
    if ! runuser -u postgres -- psql -c "CREATE DATABASE $DB_NAME TEMPLATE template0;" > /dev/null 2>&1; then
        echo "ERROR: Failed to create test database"
        exit 1
    fi

    source "$VENV_DIR/bin/activate"

    echo "Running tests (this may take a few minutes)..."

    HTTP_PORT=$((8069 + RANDOM % 1000))

    set +e
    python3 "$ODOO_DIR/odoo-bin" \
        -c "$CONF_FILE" \
        -d "$DB_NAME" \
        --stop-after-init \
        --http-port=$HTTP_PORT \
        -i "$MODULE_NAME" \
        --test-tags "$TEST_TAGS" \
        --log-level=$LOG_LEVEL \
        > "$LOG_FILE" 2>&1
    TEST_EXIT_CODE=$?
    set -e

    # Cleanup database
    runuser -u postgres -- psql -c "DROP DATABASE IF EXISTS $DB_NAME;" > /dev/null 2>&1

    return $TEST_EXIT_CODE
}

#==============================================================================
# RESULT PARSING (shared by both modes)
#==============================================================================

parse_and_display_results() {
    echo ""
    echo "========== TEST RESULTS =========="

    RESULT_LINE=$(grep "failed.*error(s).*tests" "$LOG_FILE" 2>/dev/null | tail -1)
    if [ -n "$RESULT_LINE" ]; then
        echo "$RESULT_LINE"
    fi

    if [ -n "$RESULT_LINE" ]; then
        # Use sed instead of grep -P for macOS compatibility
        TOTAL=$(echo "$RESULT_LINE" | sed -E 's/.*[^0-9]([0-9]+) tests.*/\1/' 2>/dev/null || echo "0")
        FAILED=$(echo "$RESULT_LINE" | sed -E 's/.*([0-9]+) failed.*/\1/' 2>/dev/null || echo "0")
        TEST_ERRORS=$(echo "$RESULT_LINE" | sed -E 's/.*([0-9]+) error.*/\1/' 2>/dev/null || echo "0")
        PASSED=$((TOTAL - FAILED - TEST_ERRORS))
    else
        PASSED=0
        FAILED=0
        TEST_ERRORS=0
    fi

    echo "Passed: $PASSED | Failed: $FAILED | Errors: $TEST_ERRORS"

    CRITICAL_ERROR=$(grep -E "CRITICAL|Failed to load registry|MissingDependency|ImportError" "$LOG_FILE" 2>/dev/null | head -1)
    if [ -n "$CRITICAL_ERROR" ]; then
        echo ""
        echo "CRITICAL: $CRITICAL_ERROR"

        if echo "$CRITICAL_ERROR" | grep -q "MissingDependency"; then
            echo ""
            echo "--- Missing Dependency Details ---"
            grep -A 2 "MissingDependency\|External dependency" "$LOG_FILE" 2>/dev/null | head -10
            echo ""
            echo "TIP: Install missing packages with:"
            MISSING_PKG=$(grep "External dependency" "$LOG_FILE" 2>/dev/null | grep -oP "'[^']+'" | head -1 | tr -d "'")
            if [ -n "$MISSING_PKG" ]; then
                echo "     pip install $MISSING_PKG"
            fi
        fi
    fi

    if [ "$FAILED" -gt 0 ] || [ "$TEST_ERRORS" -gt 0 ]; then
        echo ""
        echo "--- Test failures ---"
        grep -E "^FAIL:|^ERROR:|AssertionError" "$LOG_FILE" 2>/dev/null | tail -10
    fi

    if [ "$PASSED" -eq 0 ] && [ "$FAILED" -eq 0 ] && [ "$TEST_ERRORS" -eq 0 ] && [ -z "$CRITICAL_ERROR" ]; then
        echo ""
        echo "NOTE: No tests were executed. Check if:"
        echo "      - Tests are tagged correctly (@tagged('post_install', '-at_install'))"
        echo "      - Test files are in tests/ directory"
        echo "      - Test classes inherit from TransactionCase/HttpCase"
    fi

    echo ""
    echo "Full log: $LOG_FILE"
    echo "=================================="

    if [ "$FAILED" -gt 0 ] || [ "$TEST_ERRORS" -gt 0 ]; then
        return 1
    elif [ -n "$CRITICAL_ERROR" ]; then
        return 2
    fi
    return 0
}

#==============================================================================
# MAIN
#==============================================================================

# Determine which mode to use
if [ "$FORCE_DOCKER" = true ]; then
    MODE="docker"
elif [ "$FORCE_LOCAL" = true ]; then
    if [ "$CLAUDE_CODE_REMOTE" != "true" ]; then
        echo "ERROR: --local requires CLAUDE_CODE_REMOTE=true environment"
        echo "       This mode is for Claude Code remote environments only."
        exit 1
    fi
    MODE="local"
elif [ "$CLAUDE_CODE_REMOTE" = "true" ]; then
    MODE="local"
else
    MODE="docker"
fi

# Run tests
if [ "$MODE" = "docker" ]; then
    run_tests_docker
else
    run_tests_local
fi

# Parse and display results
parse_and_display_results
exit $?
