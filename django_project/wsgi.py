"""
WSGI config for django_project project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""

import os
import logging
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult, BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter  # Updated import
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.instrumentation.wsgi import OpenTelemetryMiddleware
from django.core.wsgi import get_wsgi_application

from django.core.wsgi import get_wsgi_application

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_project.settings')

# Configure logging at the beginning
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LoggingSpanExporter(SpanExporter):
    def __init__(self, exporter):
        self._exporter = exporter
        self._logger = logger

    def export(self, spans):
        result = self._exporter.export(spans)
        if result == SpanExportResult.SUCCESS:
            self._logger.info(f"Successfully exported {len(spans)} spans.")
        else:
            self._logger.error(f"Failed to export {len(spans)} spans.")
        return result

    def shutdown(self):
        self._exporter.shutdown()

# Initialize the WSGI application
application = get_wsgi_application()
application = OpenTelemetryMiddleware(application)

# Set up the resource for the TracerProvider
resource = Resource(attributes={
    SERVICE_NAME: "django-notes-app"
})

# Initialize the OTLP exporter
otlp_exporter = OTLPSpanExporter(endpoint=os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://opentelemetry-collector:4317"), insecure=True)

# Wrap the OTLP exporter with the LoggingSpanExporter
logging_exporter = LoggingSpanExporter(otlp_exporter)

# Set up the TracerProvider with the custom resource
provider = TracerProvider(resource=resource)

# Add the LoggingSpanExporter wrapped BatchSpanProcessor to the TracerProvider
provider.add_span_processor(BatchSpanProcessor(logging_exporter))

# Set the TracerProvider as the global tracer provider
trace.set_tracer_provider(provider)




