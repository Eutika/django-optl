import os
import logging

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider, SpanProcessor
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.django import DjangoInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
# Correct import
from opentelemetry.sdk.resources import get_aggregated_resources

# Move the database attributes function to the top level
def get_db_attributes():
    return {
        "db.system": "postgresql",
        "db.name": os.environ.get('DB_NAME', 'notes'),
        "db.user": os.environ.get('DB_USER', 'django'),
        "service.name": "postgresql",
        "peer.service": "postgresql",
        "net.peer.name": os.environ.get('DB_HOST', 'localhost'),
        "net.peer.port": os.environ.get('DB_PORT', '5432'),
        "net.transport": "ip_tcp"
    }

class DatabaseSpanProcessor(SpanProcessor):
    def on_start(self, span, parent_context):
        if "db." in span.name or "sql" in span.name.lower():
            span.set_attribute("service.name", "postgresql")
            span.set_attribute("peer.service", "postgresql")
    
    def on_end(self, span):
        pass

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
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        
        # Add database span processor
        provider.add_span_processor(DatabaseSpanProcessor())
        
        # Instrument Psycopg2 first
        try:
            Psycopg2Instrumentor().instrument(
                tags_generator=lambda cursor: get_db_attributes()
            )
            logger.info("Psycopg2 instrumentation successful")
        except Exception as psycopg_err:
            logger.error(f"Psycopg2 instrumentation failed: {psycopg_err}")
        
        # Instrument Django last
        try:
            DjangoInstrumentor().instrument(
                is_sql_commentator_enabled=True,
                trace_parent_span_header_name='traceparent'
            )
            logger.info(f"Django instrumentation successful for {service_name}")
        except Exception as django_err:
            logger.error(f"Django instrumentation failed: {django_err}")
        
        logger.info(f"OpenTelemetry setup completed successfully for {service_name}")
    
    except Exception as setup_err:
        logger.error(f"OpenTelemetry setup failed: {setup_err}")
        raise
