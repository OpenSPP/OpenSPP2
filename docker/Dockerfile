# syntax=docker/dockerfile:1
# OpenSPP Docker - Optimized Multi-Stage Build
# Based on Odoo 19.0 (OCB) with OpenSPP modules
#
# Build: docker build -f docker/Dockerfile -t openspp .
# Build with dev tools: docker build --build-arg INSTALL_DEV=1 -f docker/Dockerfile -t openspp:dev .

ARG PYTHON_VERSION=3.13

# =============================================================================
# Stage 1: Builder - Install all Python packages with build dependencies
# =============================================================================
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

ARG ODOO_SOURCE=OCA/OCB
ARG ODOO_VERSION=19.0

# Install ALL build dependencies once
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        git \
        libcairo2-dev \
        libffi-dev \
        libfreetype6-dev \
        libfribidi-dev \
        libgeos-dev \
        libghc-zlib-dev \
        libharfbuzz-dev \
        libjpeg-dev \
        liblcms2-dev \
        libldap2-dev \
        libopenjp2-7-dev \
        libpq-dev \
        libproj-dev \
        libsasl2-dev \
        libssl-dev \
        libtiff5-dev \
        libwebp-dev \
        libxml2-dev \
        libxslt-dev \
        tcl-dev \
        tk-dev \
        zlib1g-dev

# Create virtual environment for cleaner copying
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install uv for fast dependency management (standalone installer is faster than pip)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    mv /root/.local/bin/uv /opt/venv/bin/

# Stage the local requirements files
COPY requirements.txt /tmp/manifest-requirements.txt
COPY docker/requirements.txt /tmp/openspp-requirements.txt

# Download the remote file and install everything in one go
# Use BuildKit cache mount for uv's download cache (persists between builds)
RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked \
    --mount=type=cache,target=/tmp/downloads,sharing=locked \
    set -eux; \
    ODOO_REQS="/tmp/downloads/odoo-${ODOO_VERSION}-requirements.txt"; \
    if [ ! -s "$ODOO_REQS" ]; then \
        rm -f "$ODOO_REQS"; \
        curl -sSL -o "$ODOO_REQS" \
            "https://raw.githubusercontent.com/${ODOO_SOURCE}/${ODOO_VERSION}/requirements.txt"; \
    fi; \
    uv pip install \
    --override /tmp/openspp-requirements.txt \
    -r "$ODOO_REQS" \
    -r /tmp/manifest-requirements.txt \
    -r /tmp/openspp-requirements.txt

# Download and install Odoo (cache the tarball to avoid re-downloading)
RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked \
    --mount=type=cache,target=/tmp/downloads,sharing=locked \
    set -eux; \
    ODOO_TARBALL="/tmp/downloads/odoo-${ODOO_VERSION}.tar.gz"; \
    if [ ! -f "$ODOO_TARBALL" ] || ! gzip -t "$ODOO_TARBALL" 2>/dev/null; then \
        rm -f "$ODOO_TARBALL"; \
        curl -sSL -o "$ODOO_TARBALL" \
            "https://github.com/${ODOO_SOURCE}/archive/refs/heads/${ODOO_VERSION}.tar.gz"; \
    fi; \
    mkdir -p /opt/odoo; \
    tar -xzf "$ODOO_TARBALL" -C /opt/odoo --strip-components=1; \
    mv /opt/odoo /opt/odoo-src; \
    mkdir -p /opt/odoo; \
    mv /opt/odoo-src /opt/odoo/odoo; \
    uv pip install -e /opt/odoo/odoo

# Download OCA dependencies in builder (cache tarballs to avoid re-downloading)
RUN --mount=type=cache,target=/tmp/downloads,sharing=locked \
    set -eux; \
    download_module() { \
        local repo=$1; \
        local dest=$2; \
        local branch=${3:-19.0}; \
        local tarball="/tmp/downloads/${dest}-${branch}.tar.gz"; \
        if [ ! -f "$tarball" ] || ! gzip -t "$tarball" 2>/dev/null; then \
            rm -f "$tarball"; \
            curl -sSL -o "$tarball" \
                "https://github.com/${repo}/archive/refs/heads/${branch}.tar.gz"; \
        fi; \
        mkdir -p /opt/extra-addons/${dest}; \
        tar -xzf "$tarball" -C /opt/extra-addons/${dest} --strip-components=1; \
    }; \
    download_module "OCA/server-ux" "server-ux"; \
    download_module "OCA/server-tools" "server-tools"; \
    download_module "OCA/queue" "queue"; \
    download_module "OpenSPP/odoo-job-worker" "odoo-job-worker"; \
    download_module "OCA/server-backend" "server-backend"; \
    download_module "OCA/rest-framework" "rest-framework"; \
    download_module "muk-it/odoo-modules" "muk-it"

# Precompile Python files (ignore errors from Python 2 syntax in some packages)
RUN python -m compileall -q /opt/venv/lib/ || true

# =============================================================================
# Stage 2: Runtime - Minimal image with only runtime dependencies
# =============================================================================
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

ARG TARGETARCH
ARG WKHTMLTOPDF_VERSION=0.12.6.1
ARG WKHTMLTOPDF_AMD64_CHECKSUM='98ba0d157b50d36f23bd0dedf4c0aa28c7b0c50fcdcdc54aa5b6bbba81a3941d'
ARG WKHTMLTOPDF_ARM64_CHECKSUM='b6606157b27c13e044d0abbe670301f88de4e1782afca4f9c06a5817f3e03a9c'
ARG GEOIP_UPDATER_VERSION=6.0.0
ARG ODOO_VERSION=19.0
ARG UID=1000
ARG GID=1000
ARG PG_VERSION=18

EXPOSE 8069 8072

# Environment variables
ENV ODOO_VERSION="${ODOO_VERSION}" \
    ODOO_RC=/etc/odoo/odoo.conf \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8 \
    PATH="/opt/venv/bin:/home/odoo/.local/bin:$PATH" \
    VIRTUAL_ENV=/opt/venv \
    PYTHONUNBUFFERED=1 \
    DB_FILTER=.* \
    LIST_DB=false \
    UNACCENT=true \
    PROXY_MODE=true \
    WITHOUT_DEMO=all

# Install runtime dependencies only (no build tools!)
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        # System utilities
        curl \
        ca-certificates \
        gnupg2 \
        gettext-base \
        # Fonts for PDF generation (including wkhtmltopdf dependencies)
        fontconfig \
        fonts-liberation2 \
        fonts-dejavu-core \
        fonts-freefont-ttf \
        xfonts-75dpi \
        xfonts-base \
        # Runtime libraries (no -dev packages!)
        libcairo2 \
        libfreetype6 \
        libfribidi0 \
        libgeos-c1v5 \
        libjpeg62-turbo \
        liblcms2-2 \
        libldap-2.5-0 \
        libopenjp2-7 \
        libpq5 \
        libproj25 \
        libsasl2-2 \
        libtiff6 \
        libwebp7 \
        libxml2 \
        libxslt1.1 \
        proj-data \
        proj-bin \
    ; \
    # Install PostgreSQL client
    echo 'deb https://apt.postgresql.org/pub/repos/apt/ bookworm-pgdg main' > /etc/apt/sources.list.d/postgresql.list; \
    curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /etc/apt/trusted.gpg.d/postgresql.gpg; \
    apt-get update; \
    apt-get install -y --no-install-recommends postgresql-client-${PG_VERSION}; \
    # Patch OpenSSL to fix CVE-2025-15467 and CVE-2025-69419 (RCE)
    apt-get upgrade -y libssl3 openssl

# Install wkhtmltopdf and geoipupdate (cache the downloads)
RUN --mount=type=cache,target=/tmp/downloads,sharing=locked \
    set -eux; \
    # wkhtmltopdf
    if [ "$TARGETARCH" = "arm64" ]; then \
        WKHTMLTOPDF_CHECKSUM=$WKHTMLTOPDF_ARM64_CHECKSUM; \
    elif [ "$TARGETARCH" = "amd64" ]; then \
        WKHTMLTOPDF_CHECKSUM=$WKHTMLTOPDF_AMD64_CHECKSUM; \
    else \
        echo "Unsupported architecture: $TARGETARCH" >&2; \
        exit 1; \
    fi; \
    WKHTMLTOPDF_DEB="/tmp/downloads/wkhtmltox_${WKHTMLTOPDF_VERSION}_${TARGETARCH}.deb"; \
    if [ ! -f "$WKHTMLTOPDF_DEB" ] || ! echo "${WKHTMLTOPDF_CHECKSUM} ${WKHTMLTOPDF_DEB}" | sha256sum -c - >/dev/null 2>&1; then \
        rm -f "$WKHTMLTOPDF_DEB"; \
        curl -sSL -o "$WKHTMLTOPDF_DEB" \
            "https://github.com/wkhtmltopdf/packaging/releases/download/${WKHTMLTOPDF_VERSION}-3/wkhtmltox_${WKHTMLTOPDF_VERSION}-3.bookworm_${TARGETARCH}.deb"; \
        echo "${WKHTMLTOPDF_CHECKSUM} ${WKHTMLTOPDF_DEB}" | sha256sum -c -; \
    fi; \
    apt-get install -y --no-install-recommends "$WKHTMLTOPDF_DEB"; \
    # geoipupdate
    GEOIP_DEB="/tmp/downloads/geoipupdate_${GEOIP_UPDATER_VERSION}_${TARGETARCH}.deb"; \
    if [ ! -f "$GEOIP_DEB" ] || ! dpkg --info "$GEOIP_DEB" >/dev/null 2>&1; then \
        rm -f "$GEOIP_DEB"; \
        curl -sSL -o "$GEOIP_DEB" \
            "https://github.com/maxmind/geoipupdate/releases/download/v${GEOIP_UPDATER_VERSION}/geoipupdate_${GEOIP_UPDATER_VERSION}_linux_${TARGETARCH}.deb"; \
    fi; \
    dpkg -i "$GEOIP_DEB"

# Create odoo user and directories
RUN set -eux; \
    groupadd -g ${GID} odoo; \
    useradd -l -m -d /home/odoo -s /bin/bash -u ${UID} -g ${GID} odoo; \
    mkdir -p /var/lib/odoo /mnt/extra-addons /etc/odoo; \
    chown -R odoo:odoo /var/lib/odoo /mnt/extra-addons /etc/odoo

# Copy virtual environment from builder (includes all pip packages)
COPY --from=builder /opt/venv /opt/venv

# Copy Odoo installation from builder
COPY --from=builder /opt/odoo /opt/odoo

# Copy OCA dependencies from builder
COPY --from=builder --chown=odoo:odoo /opt/extra-addons /mnt/extra-addons

# Configuration files
COPY docker/odoo.conf.template /etc/odoo/odoo.conf.template
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh; \
    chown odoo:odoo /etc/odoo/odoo.conf.template /entrypoint.sh

# Final configuration
WORKDIR /var/lib/odoo
VOLUME ["/var/lib/odoo"]
USER odoo

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=5 \
    CMD curl -f http://localhost:8069/web/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["odoo"]

# =============================================================================
# Stage 3: Dev - For local development (openspp via volume mount)
# =============================================================================
# Use this target for dev/test: code comes from volume mount, always fresh
FROM runtime AS dev
# OpenSPP modules come from volume mount - NOT copied into image
# This ensures dev/test always use live code from the host
# All other setup (OCA deps, config, user) inherited from runtime stage

# =============================================================================
# Stage 4: Production - Standalone image with all code baked in
# =============================================================================
# Use this target for CI/production: fully self-contained image
FROM runtime AS production
# Need root to copy files, then switch back to odoo
USER root
COPY --chown=odoo:odoo . /mnt/extra-addons/openspp
USER odoo
