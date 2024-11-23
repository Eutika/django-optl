#!/usr/bin/env python3
import os
import sys
import logging

# Comprehensive logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/tmp/postgresql-tracing.log', mode='w')
    ]
)
logger = logging.getLogger(__name__)

# Log system and environment details
logger.info(f"Python Executable: {sys.executable}")
logger.info(f"Python Path: {sys.path}")
logger.info(f"Environment Variables:")
for key, value in os.environ.items():
    logger.info(f"{key}: {value}")

# Comprehensive module import check
def check_module_availability():
    modules_to_check = [
        'opentelemetry',
        'opentelemetry.api',
        'opentelemetry.sdk',
        'opentelemetry.exporter.otlp.proto.grpc.trace_exporter'
    ]
    
    for module in modules_to_check:
        try:
            __import__(module)
            logger.info(f"Module {module} is available")
        except ImportError as e:
            logger.error(f"Failed to import {module}: {e}")

# Run module availability check
check_module_availability()

# Full OpenTelemetry import and tracing
try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME

    def setup_comprehensive_tracing():
        try:
            # Create resource with service name
            resource = Resource.create({
                SERVICE_NAME: os.environ.get('OTEL_SERVICE_NAME', 'postgresql')
            })

            # Setup trace provider
            trace_provider = TracerProvider(resource=resource)
            trace.set_tracer_provider(trace_provider)

            # Get endpoint from environment
            otlp_endpoint = os.environ.get(
                'OTEL_EXPORTER_OTLP_ENDPOINT', 
                'http://grafana-k8s-monitoring-alloy.grafana.svc.cluster.local:4317'
            )

            # Create OTLP exporter
            otlp_exporter = OTLPSpanExporter(
                endpoint=otlp_endpoint,
                insecure=True
            )

            # Add batch span processor
            trace_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

            # Create a tracer and generate a startup span
            tracer = trace.get_tracer(__name__)
            with tracer.start_as_current_span("postgresql-startup"):
                logger.info("PostgreSQL tracing initialized successfully")
                print("PostgreSQL tracing initialized")

        except Exception as e:
            logger.error(f"Comprehensive tracing setup failed: {e}", exc_info=True)
            print(f"Comprehensive tracing setup failed: {e}")
            sys.exit(1)

    # Execute tracing setup
    setup_comprehensive_tracing()

except Exception as global_e:
    logger.error(f"Global import or setup error: {global_e}", exc_info=True)
    sys.exit(1)
