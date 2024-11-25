FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PIP_NO_CACHE_DIR 1

# Create a non-root user
RUN addgroup --system django && \
    adduser --system --ingroup django django

# Set working directory
WORKDIR /app

# Install system dependencies for PostgreSQL and OpenTelemetry
RUN apt-get update && apt-get install -y \
    postgresql-client \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY --chown=django:django . .

# Upgrade pip and install dependencies with comprehensive OpenTelemetry support
RUN pip install --upgrade pip && \
    pip install --no-cache-dir \
    psycopg2-binary \
    opentelemetry-api \
    opentelemetry-sdk \
    opentelemetry-exporter-otlp-proto-grpc \
    opentelemetry-instrumentation-django \
    opentelemetry-instrumentation-psycopg2 \
    opentelemetry-instrumentation-sqlalchemy \
    opentelemetry-instrumentation-logging \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install gunicorn

# Create static files directory with correct permissions
RUN mkdir -p /app/staticfiles && \
    chown -R django:django /app/staticfiles

# Expose port
EXPOSE 8000

# Comprehensive OpenTelemetry environment variables
ENV DJANGO_SETTINGS_MODULE=django_project.settings
ENV STATIC_ROOT=/app/staticfiles
ENV OTEL_SERVICE_NAME=notes-web-service
ENV OTEL_EXPORTER_OTLP_ENDPOINT=http://grafana-k8s-monitoring-alloy.grafana.svc.cluster.local:4317
ENV OTEL_TRACES_EXPORTER=otlp
ENV OTEL_METRICS_EXPORTER=otlp
ENV OTEL_LOGS_EXPORTER=otlp
ENV OTEL_TRACE_SAMPLING_RATE=1.0
ENV OTEL_PYTHON_LOG_CORRELATION=true
ENV OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED=true

# Logging and debugging configuration
ENV PYTHONWARNINGS=always
ENV PYTHONDEVMODE=1

# Entrypoint script to set up OpenTelemetry and run Django
COPY --chown=root:root entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Switch to non-root user
USER django

# Use entrypoint script
CMD ["/app/entrypoint.sh"]
