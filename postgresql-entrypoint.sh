#!/bin/bash
set -e

# Run OpenTelemetry instrumentation in background
python3 /usr/local/bin/postgresql-otel-instrumentation.py &

# Run the original PostgreSQL entrypoint
docker-entrypoint.sh "$@"
