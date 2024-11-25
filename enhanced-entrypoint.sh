#!/bin/bash
set -e

# Enhanced logging and debugging for OpenTelemetry setup
echo "Starting PostgreSQL with OpenTelemetry Instrumentation" >&2

# Print comprehensive environment variables for debugging
echo "Environment Configuration:" >&2
echo "- OTEL_SERVICE_NAME: ${OTEL_SERVICE_NAME:-postgresql}" >&2
echo "- OTEL_EXPORTER_OTLP_ENDPOINT: ${OTEL_EXPORTER_OTLP_ENDPOINT:-http://grafana-k8s-monitoring-alloy.grafana.svc.cluster.local:4317}" >&2
echo "- DB_HOST: ${DB_HOST:-localhost}" >&2
echo "- DB_PORT: ${DB_PORT:-5432}" >&2
echo "- POSTGRES_DB: ${POSTGRES_DB:-postgres}" >&2

# Verify script permissions and existence
TRACING_SCRIPT="/usr/local/bin/postgresql-tracing.py"
if [ ! -f "$TRACING_SCRIPT" ]; then
    echo "Error: Tracing script $TRACING_SCRIPT not found" >&2
    exit 1
fi

if [ ! -x "$TRACING_SCRIPT" ]; then
    echo "Attempting to set executable permissions on $TRACING_SCRIPT" >&2
    chmod 755 "$TRACING_SCRIPT" || {
        echo "Error: Could not set executable permissions on $TRACING_SCRIPT" >&2
        exit 1
    }
fi

# Create a temporary log file in a writable location
TRACE_LOG_FILE=$(mktemp /tmp/postgresql-tracing-XXXXXX.log)
echo "Using temporary log file: $TRACE_LOG_FILE" >&2

# Redirect Python tracing logs to temporary file and stdout/stderr
echo "Starting OpenTelemetry tracing script..." >&2
python3 "$TRACING_SCRIPT" > "$TRACE_LOG_FILE" 2>&1 &
TRACING_PID=$!

# Log the tracing script PID for monitoring
echo "OpenTelemetry Tracing Script PID: $TRACING_PID" >&2

# Function to handle graceful shutdown and log output
cleanup() {
    echo "Received shutdown signal. Cleaning up..." >&2
    if kill -0 $TRACING_PID 2>/dev/null; then
        kill -TERM $TRACING_PID
        wait $TRACING_PID
    fi
    
    # Output log file contents on exit
    echo "Tracing script log contents:" >&2
    cat "$TRACE_LOG_FILE" >&2
    
    exit 0
}

# Trap signals for graceful shutdown
trap cleanup SIGINT SIGTERM

# Verify tracing script is running
sleep 5
if ! kill -0 $TRACING_PID 2>/dev/null; then
    echo "Error: Tracing script failed to start." >&2
    echo "Log file contents:" >&2
    cat "$TRACE_LOG_FILE" >&2
    exit 1
fi

# Execute original postgres entrypoint with verbose logging
echo "Starting PostgreSQL database..." >&2
exec docker-entrypoint.sh postgres
