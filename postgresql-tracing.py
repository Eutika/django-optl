#!/usr/bin/env python3
import os
import sys
import logging
import time
import socket
import psycopg2
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.trace import Status, StatusCode

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/tmp/postgresql-tracing.log', mode='w')
    ]
)
logger = logging.getLogger(__name__)

def setup_postgresql_tracing():
    resource = Resource.create({
        ResourceAttributes.SERVICE_NAME: "postgresql",
        ResourceAttributes.SERVICE_VERSION: "1.0.0",
        ResourceAttributes.DEPLOYMENT_ENVIRONMENT: "kubernetes"
    })

    provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(provider)

    otlp_exporter = OTLPSpanExporter(
        endpoint=os.environ.get(
            'OTEL_EXPORTER_OTLP_ENDPOINT', 
            'http://grafana-k8s-monitoring-alloy.grafana.svc.cluster.local:4317'
        ),
        insecure=True
    )

    provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    return trace.get_tracer(__name__, tracer_provider=provider)

def validate_database_connection(tracer, conn_params):
    with tracer.start_as_current_span("db.connection_validation") as span:
        try:
            span.set_attribute("db.system", "postgresql")
            span.set_attribute("db.host", conn_params.get('host', 'unknown'))
            span.set_attribute("db.port", str(conn_params.get('port', '5432')))
            span.set_attribute("service.name", "postgresql")

            with psycopg2.connect(**conn_params) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT version()")
                    db_version = cursor.fetchone()[0]
                
                span.set_attribute("db.version", db_version)
                span.set_attribute("db.user", conn_params.get('user', 'unknown'))
                
                logger.info(f"Database connection successful. Version: {db_version}")
            
            span.set_status(Status(StatusCode.OK))
        
        except Exception as conn_error:
            span.record_exception(conn_error)
            span.set_status(Status(StatusCode.ERROR, str(conn_error)))
            logger.error(f"Database connection validation failed: {conn_error}")
            raise

def generate_comprehensive_database_traces(tracer):
    conn_params = {
        'dbname': os.environ.get('POSTGRES_DB', 'postgres'),
        'user': os.environ.get('POSTGRES_USER', 'postgres'),
        'password': os.environ.get('POSTGRES_PASSWORD', ''),
        'host': os.environ.get('DB_HOST', 'localhost'),
        'port': os.environ.get('DB_PORT', '5432')
    }

    with tracer.start_as_current_span("postgresql.diagnostic") as root_span:
        root_span.set_attribute("service.name", "postgresql")
        root_span.set_attribute("db.system", "postgresql")

        diagnostic_operations = [
            ("list_databases", "SELECT datname FROM pg_database LIMIT 10"),
            ("check_extensions", "SELECT * FROM pg_available_extensions LIMIT 10"),
            ("list_schemas", "SELECT schema_name FROM information_schema.schemata LIMIT 20"),
        ]

        for op_name, query in diagnostic_operations:
            with tracer.start_as_current_span(f"postgresql.{op_name}") as span:
                try:
                    span.set_attribute("service.name", "postgresql")
                    span.set_attribute("db.system", "postgresql")
                    span.set_attribute("db.operation", op_name)
                    span.set_attribute("db.statement", query)

                    with psycopg2.connect(**conn_params) as conn:
                        with conn.cursor() as cursor:
                            cursor.execute(query)
                            results = cursor.fetchall()
                            
                            span.set_attribute("db.result_count", len(results))
                            span.set_status(Status(StatusCode.OK))
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    logger.error(f"Diagnostic operation {op_name} failed: {e}")

def main():
    # Set up tracing
    tracer = setup_postgresql_tracing()

    # Connection parameters for validation
    conn_params = {
        'dbname': os.environ.get('POSTGRES_DB', 'postgres'),
        'user': os.environ.get('POSTGRES_USER', 'postgres'),
        'password': os.environ.get('POSTGRES_PASSWORD', ''),
        'host': os.environ.get('DB_HOST', 'localhost'),
        'port': os.environ.get('DB_PORT', '5432')
    }

    # Validate database connection
    validate_database_connection(tracer, conn_params)

    # Periodic trace generation
    def trace_generator():
        while True:
            try:
                generate_comprehensive_database_traces(tracer)
            except Exception as e:
                logger.error(f"Trace generation error: {e}")
            time.sleep(60)  # Generate traces every minute

    try:
        import threading
        trace_thread = threading.Thread(target=trace_generator, daemon=True)
        trace_thread.start()
        trace_thread.join()  # Keep the script running
    except Exception as thread_err:
        logger.error(f"Trace generation thread failed: {thread_err}")

if __name__ == "__main__":
    try:
        main()
    except Exception as global_err:
        logger.error(f"Script execution failed: {global_err}")
        sys.exit(1)
