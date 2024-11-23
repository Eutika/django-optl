# In your project directory, create entrypoint.sh
#!/bin/bash
set -e

# Print OpenTelemetry configuration
echo "OTEL_SERVICE_NAME: $OTEL_SERVICE_NAME"
echo "OTEL_EXPORTER_OTLP_ENDPOINT: $OTEL_EXPORTER_OTLP_ENDPOINT"

# Apply database migrations
python manage.py migrate

# Optional: Create superuser if not exists
python -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'adminpass')
"

# Run with OpenTelemetry instrumentation
exec opentelemetry-instrument gunicorn \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    django_project.wsgi:application
