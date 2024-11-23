#!/usr/bin/env python3
import os
import logging
from opentelemetry import trace
from opentelemetry.trace import SpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor

class DatabaseSpanProcessor(SpanProcessor):
    def on_start(self, span, parent_context):
        if "db." in span.name or "sql" in span.name.lower():
            span.set_attribute("service.name", "postgresql")
            span.set_attribute("peer.service", "postgresql")
    
    def on_end(self, span):
        pass

def setup_opentelemetry():
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    try:
        # Create resource with detailed service information
        resource = Resource.create({
            SERVICE_NAME: os.environ.get('OTEL_SERVICE_NAME', 'notes-db-service'),
            "service.version": os.environ.get('SERVICE_VERSION', '1.0.0'),
            "deployment.environment": os.environ.get('DEPLOYMENT_ENV', 'kubernetes'),
            "service.namespace": os.environ.get('SERVICE_NAMESPACE', 'notes-app'),
            "service.instance.id": os.environ.get('HOSTNAME', 'unknown-instance')
        })
        
        # Set up trace provider with resource
        provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(provider)
        
        # Create OTLP exporter
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
            BatchSpanProcessor(otlp_exporter),
            DatabaseSpanProcessor()
        )
        
        # Instrument SQLAlchemy (generic SQL instrumentation)
        Psycopg2Instrumentor().instrument(
            service_name=resource.attributes[SERVICE_NAME]
        )
        
        logger.info(f"OpenTelemetry setup completed for {resource.attributes[SERVICE_NAME]}")
    
    except Exception as setup_err:
        logger.error(f"OpenTelemetry setup failed: {setup_err}")
        raise

if __name__ == "__main__":
    setup_opentelemetry()
