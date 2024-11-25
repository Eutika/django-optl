import os
import sys
import logging
import logging.config
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
import socket

# Simplified logging configuration
def configure_logging():
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),  # Ensure logs go to container stdout
            logging.StreamHandler(sys.stderr)
        ]
    )
    return logging.getLogger(__name__)

# Logger for instrumentation
logger = configure_logging()

def setup_opentelemetry():
    try:
        logger.info("Starting OpenTelemetry Instrumentation Setup")
        
        # Create resource with comprehensive attributes
        resource = Resource.create({
            SERVICE_NAME: os.environ.get('OTEL_SERVICE_NAME', 'notes-web-service'),
            "service.version": os.environ.get('SERVICE_VERSION', '1.0.0'),
            "deployment.environment": os.environ.get('DEPLOYMENT_ENV', 'kubernetes'),
            "service.namespace": os.environ.get('SERVICE_NAMESPACE', 'notes-app'),
            "service.instance.id": os.environ.get('HOSTNAME', socket.gethostname()),
            "net.host.name": socket.gethostname()
        })
        
        # Setup trace provider with resource
        provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(provider)

        # More robust OTLP exporter configuration
        otlp_endpoint = os.environ.get(
            'OTEL_EXPORTER_OTLP_ENDPOINT', 
            'http://grafana-k8s-monitoring-alloy.grafana.svc.cluster.local:4317'
        )
        
        otlp_exporter = OTLPSpanExporter(
            endpoint=otlp_endpoint,
            insecure=os.environ.get('OTEL_EXPORTER_INSECURE', 'true').lower() == 'true'
        )
        
        # Batch processor with more detailed configuration
        batch_processor = BatchSpanProcessor(
            otlp_exporter,
            max_queue_size=2048,
            schedule_delay_millis=5000,
            export_timeout_millis=30000
        )
        provider.add_span_processor(batch_processor)
        
        # Enhanced Psycopg2 Instrumentation
        try:
            from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
            Psycopg2Instrumentor().instrument(
                tracer_provider=provider,
                tags_generator=lambda cursor: {
                    "db.system": "postgresql",
                    "db.name": os.environ.get('DB_NAME', 'notes'),
                    "db.user": os.environ.get('DB_USER', 'django'),
                    "net.peer.name": os.environ.get('DB_HOST', 'localhost'),
                    "net.peer.port": os.environ.get('DB_PORT', '5432'),
                    "net.transport": "ip_tcp",
                    "service.name": "notes-web-service",
                    "server.address": os.environ.get('DB_HOST', 'localhost'),
                    "server.port": os.environ.get('DB_PORT', '5432'),
                    "peer.service": "postgresql",
                }
            )
            logger.info("Psycopg2 instrumentation successful")
        except Exception as psycopg_err:
            logger.error(f"Psycopg2 instrumentation failed: {psycopg_err}")
        
        # Enhanced Django Instrumentation
        try:
            from opentelemetry.instrumentation.django import DjangoInstrumentor
            DjangoInstrumentor().instrument(
                is_sql_commentator_enabled=True,
                tracer_provider=provider,
                get_tracer_provider=provider,
                commenter_options={
                    'comment_prefix': 'django-otel',
                    'db_statement_key': 'db.statement'
                },
                trace_parent_span_header_name='traceparent'
            )
            logger.info("Django instrumentation successful")
        except Exception as django_err:
            logger.error(f"Django instrumentation failed: {django_err}")
        
        logger.info("OpenTelemetry setup completed successfully")
    
    except Exception as setup_err:
        logger.error(f"OpenTelemetry setup failed: {setup_err}")
        raise

# Ensure instrumentation runs when module is imported
setup_opentelemetry()
