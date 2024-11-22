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

# Install system dependencies for PostgreSQL
RUN apt-get update && apt-get install -y \
    postgresql-client \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY --chown=django:django . .

# Upgrade pip and install requirements
RUN pip install --upgrade pip && \
    pip install --no-cache-dir psycopg2-binary && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install gunicorn

# Create static files directory with correct permissions
RUN mkdir -p /app/staticfiles && \
    chown -R django:django /app/staticfiles

# Switch to non-root user
USER django

# Expose port
EXPOSE 8000

# Default environment variables
ENV DJANGO_SETTINGS_MODULE=django_project.settings
ENV STATIC_ROOT=/app/staticfiles

# Default OpenTelemetry environment variables
ENV OTEL_SERVICE_NAME=notes-web-service
ENV OTEL_EXPORTER_OTLP_ENDPOINT=http://grafana-k8s-monitoring-alloy.grafana.svc.cluster.local:4317
ENV OTEL_TRACES_EXPORTER=otlp
ENV OTEL_METRICS_EXPORTER=otlp
ENV OTEL_LOGS_EXPORTER=otlp

# Use gunicorn for production
CMD ["gunicorn", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "django_project.wsgi:application"]
