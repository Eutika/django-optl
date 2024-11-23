#!/bin/bash
set -e

# Print environment variables for debugging
echo "OTEL_SERVICE_NAME: ${OTEL_SERVICE_NAME:-default-postgresql}"
echo "OTEL_EXPORTER_OTLP_ENDPOINT: ${OTEL_EXPORTER_OTLP_ENDPOINT:-default-endpoint}"

# Run OpenTelemetry instrumentation in background
python3 /usr/local/bin/postgresql-tracing.py &

# Execute original postgres entrypoint
exec docker-entrypoint.sh postgres
