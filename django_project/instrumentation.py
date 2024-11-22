import os
import logging

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.django import DjangoInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME

def setup_opentelemetry():
    # Configure logging for OpenTelemetry setup
    logger = logging.getLogger(__name__)
    
    try:
        # Check if a tracer provider is already set
        current_tracer_provider = trace.get_tracer_provider()
        if isinstance(current_tracer_provider, TracerProvider):
            logger.warning("Tracer provider already set. Skipping re-initialization.")
            return
        
        # Determine service name from environment
        service_name = os.environ.get('OTEL_SERVICE_NAME', 'notes-web-service')
        
        # Create resource with detailed service information
        resource = Resource.create({
            SERVICE_NAME: service_name,
            "service.version": os.environ.get('SERVICE_VERSION', '1.0.0'),
            "deployment.environment": os.environ.get('DEPLOYMENT_ENV', 'kubernetes'),
            "service.namespace": os.environ.get('SERVICE_NAMESPACE', 'notes-app'),
            "service.instance.id": os.environ.get('HOSTNAME', 'unknown-instance')
        })
        
        # Set up trace provider with resource
        provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(provider)
        
        # Create OTLP exporter with robust endpoint configuration
        otlp_endpoint = os.environ.get(
            'OTEL_EXPORTER_OTLP_ENDPOINT', 
            'http://grafana-k8s-monitoring-alloy.grafana.svc.cluster.local:4317'
        )
        
        otlp_exporter = OTLPSpanExporter(
            endpoint=otlp_endpoint,
            insecure=os.environ.get('OTEL_EXPORTER_INSECURE', 'true').lower() == 'true'
        )
        
        # Add batch processor
        provider.add_span_processor(
            BatchSpanProcessor(otlp_exporter)
        )
        
        # Instrument Django
        try:
            DjangoInstrumentor().instrument()
            logger.info(f"Django instrumentation successful for {service_name}")
        except Exception as django_err:
            logger.error(f"Django instrumentation failed: {django_err}")
        
        # Instrument Psycopg2
        try:
            Psycopg2Instrumentor().instrument(
                # Add tags to help identify database operations
                tags_generator=lambda cursor: {
                    "db.system": "postgresql",
                    "db.name": os.environ.get('DB_NAME', 'notes'),
                    "db.user": os.environ.get('DB_USER', 'django')
                }
            )
            logger.info("Psycopg2 instrumentation successful")
        except Exception as psycopg_err:
            logger.error(f"Psycopg2 instrumentation failed: {psycopg_err}")
        
        logger.info(f"OpenTelemetry setup completed successfully for {service_name}")
    
    except Exception as setup_err:
        logger.error(f"OpenTelemetry setup failed: {setup_err}")
        raise
