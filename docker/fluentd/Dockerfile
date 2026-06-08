# Fluentd image with output plugins for S3, GCS, Azure, and MinIO.
#
# Only needed for cloud storage backends. For local filesystem / NFS output,
# use the official fluentd image directly (no build required).
#
# Build with:
#   docker compose -f docker/docker-compose.nginx.yml build fluentd
#
# The base image uses Debian with jemalloc to mitigate memory fragmentation.
# Plugins are installed at build time so the container starts read-only.

FROM fluent/fluentd:v1.19-2

USER root

# Install output plugins for all supported backends.
# - fluent-plugin-s3: AWS S3 and MinIO (S3-compatible)
# - fluent-plugin-gcs: Google Cloud Storage
# - fluent-plugin-azure-storage-append-blob: Azure Blob Storage
RUN gem install --no-document \
        fluent-plugin-s3 \
        fluent-plugin-gcs \
        fluent-plugin-azure-storage-append-blob \
    && gem cleanup

USER fluent
