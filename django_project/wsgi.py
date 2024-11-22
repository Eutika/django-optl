import os
from django.core.wsgi import get_wsgi_application
from opentelemetry.instrumentation.wsgi import OpenTelemetryMiddleware

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_project.settings')

# Get basic WSGI application
application = get_wsgi_application()

# Wrap with OpenTelemetry middleware
application = OpenTelemetryMiddleware(application)
