import os
import logging
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExportResult
from opentelemetry.instrumentation.django import DjangoInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_NAMESPACE

# Global flag to prevent multiple instrumentations
_is_instrumented = False

def setup_opentelemetry():
    global _is_instrumented
    
    # Check if already instrumented
    if _is_instrumented:
        print("OpenTelemetry already instrumented. Skipping.")
        return
    
    print("Starting OpenTelemetry setup")
    try:
        # Create resources for notes and database services
        notes_resource = Resource(attributes={
            SERVICE_NAME: "notes",
            SERVICE_NAMESPACE: "application",
            "service.version": "1.0.0",
            "deployment.environment": "kubernetes"
        })
        
        db_resource = Resource(attributes={
            SERVICE_NAME: "notes-db",
            SERVICE_NAMESPACE: "database",
            "service.version": "1.0.0",
            "deployment.environment": "kubernetes"
        })
        
        # Set up trace providers with resources
        notes_provider = TracerProvider(resource=notes_resource)
        db_provider = TracerProvider(resource=db_resource)
        
        trace.set_tracer_provider(notes_provider)
        
        # Create OTLP exporter
        otlp_exporter = OTLPSpanExporter(
            endpoint=os.environ.get(
                'OTEL_EXPORTER_OTLP_ENDPOINT', 
                'http://grafana-k8s-monitoring-alloy.grafana.svc.cluster.local:4317'
            ),
            insecure=True
        )
        
        # Add batch processors
        notes_provider.add_span_processor(
            BatchSpanProcessor(otlp_exporter)
        )
        db_provider.add_span_processor(
            BatchSpanProcessor(otlp_exporter)
        )
        
        # Instrument only if not already instrumented
        if not _is_instrumented:
            DjangoInstrumentor().instrument()
            Psycopg2Instrumentor().instrument()
            _is_instrumented = True
        
        print("OpenTelemetry setup completed successfully")
    except Exception as e:
        print(f"OpenTelemetry setup error: {e}")
        raise
