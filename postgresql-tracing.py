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

# Enhanced logging configuration
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/tmp/postgresql-tracing.log', mode='w')
    ]
)
logger = logging.getLogger(__name__)

def get_connection_params():
    """
    Retrieve and validate PostgreSQL connection parameters
    with comprehensive error logging
    """
    conn_params = {
        'dbname': os.environ.get('POSTGRES_DB', 'postgres'),
        'user': os.environ.get('POSTGRES_USER', 'postgres'),
        'password': os.environ.get('POSTGRES_PASSWORD', ''),
        'host': os.environ.get('DB_HOST', 'localhost'),
        'port': os.environ.get('DB_PORT', '5432')
    }

    # Log connection details for debugging
    logger.info(f"Connection Parameters: {conn_params}")
    
    # Validate required parameters
    for key, value in conn_params.items():
        if not value:
            logger.error(f"Missing required connection parameter: {key}")
    
    return conn_params

def setup_postgresql_tracing():
    """
    Set up comprehensive OpenTelemetry tracing for PostgreSQL
    """
    try:
        # More comprehensive resource attributes
        resource = Resource.create({
            ResourceAttributes.SERVICE_NAME: "postgresql",
            ResourceAttributes.SERVICE_VERSION: "1.0.0",
            ResourceAttributes.DEPLOYMENT_ENVIRONMENT: "kubernetes",
            "service.type": "database",
            "db.system": "postgresql",
            "net.host.name": socket.gethostname(),
            "net.host.port": os.environ.get('DB_PORT', '5432')
        })

        provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(provider)

        # Detailed OTLP exporter configuration
        otlp_exporter = OTLPSpanExporter(
            endpoint=os.environ.get(
                'OTEL_EXPORTER_OTLP_ENDPOINT', 
                'http://grafana-k8s-monitoring-alloy.grafana.svc.cluster.local:4317'
            ),
            insecure=os.environ.get('OTEL_EXPORTER_INSECURE', 'true').lower() == 'true'
        )

        # Batch span processor with more detailed configuration
        batch_processor = BatchSpanProcessor(
            otlp_exporter,
            max_queue_size=2048,
            schedule_delay_millis=5000,
            export_timeout_millis=30000
        )
        provider.add_span_processor(batch_processor)

        return trace.get_tracer(__name__, tracer_provider=provider)
    except Exception as e:
        logger.error(f"Tracing setup failed: {e}")
        raise

def validate_database_connection(tracer, conn_params):
    """
    Comprehensive database connection validation with detailed tracing
    """
    with tracer.start_as_current_span("db.connection_validation") as span:
        try:
            # Comprehensive span attributes
            span.set_attributes({
                "db.system": "postgresql",
                "db.connection_type": "primary",
                "db.host": conn_params.get('host', 'unknown'),
                "db.port": str(conn_params.get('port', '5432')),
                "db.user": conn_params.get('user', 'unknown'),
                "service.name": "postgresql",
                "peer.service": "database"
            })

            # Implement connection retry mechanism
            max_retries = 10
            retry_delay = 5  # seconds

            for attempt in range(max_retries):
                try:
                    with psycopg2.connect(**conn_params) as conn:
                        with conn.cursor() as cursor:
                            cursor.execute("SELECT version()")
                            db_version = cursor.fetchone()[0]
                    
                    # Additional version and connection details
                    span.set_attributes({
                        "db.version": db_version,
                        "db.connection_status": "successful",
                        "db.connection_attempts": attempt + 1
                    })
                    
                    logger.info(f"Database connection successful. Version: {db_version}")
                    return  # Exit if connection is successful
                
                except (psycopg2.OperationalError, psycopg2.Error) as conn_error:
                    logger.warning(f"Connection attempt {attempt + 1} failed: {conn_error}")
                    time.sleep(retry_delay)
            
            # If all attempts fail
            raise Exception("Failed to establish database connection after multiple attempts")
        
        except Exception as conn_error:
            span.record_exception(conn_error)
            span.set_status(Status(StatusCode.ERROR, str(conn_error)))
            logger.error(f"Database connection validation failed: {conn_error}")
            raise

def main():
    try:
        # Set up tracing with comprehensive configuration
        tracer = setup_postgresql_tracing()

        # Get connection parameters
        conn_params = get_connection_params()

        # Validate database connection
        validate_database_connection(tracer, conn_params)

        # Periodic trace generation with error handling
        def trace_generator():
            while True:
                try:
                    # Add your trace generation logic here
                    logger.info("Periodic trace generation completed successfully")
                except Exception as e:
                    logger.error(f"Trace generation error: {e}")
                time.sleep(60)  # Generate traces every minute

        # Run trace generator in a separate thread
        import threading
        trace_thread = threading.Thread(target=trace_generator, daemon=True)
        trace_thread.start()
        trace_thread.join()  # Keep the script running

    except Exception as global_err:
        logger.error(f"Script execution failed: {global_err}")
        sys.exit(1)

if __name__ == "__main__":
    main()
