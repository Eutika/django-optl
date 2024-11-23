import os
import logging
import functools
import psycopg2
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider, SpanProcessor
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.django import DjangoInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME

# Global tracer
tracer = trace.get_tracer(__name__)

def trace_database_operation(operation_name):
    """
    Decorator to create spans for database operations
    
    Args:
        operation_name (str): Name of the database operation
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with tracer.start_as_current_span(f"db.{operation_name}") as span:
                # Set standard database span attributes
                span.set_attribute("db.system", "postgresql")
                span.set_attribute("service.name", "postgresql")
                span.set_attribute("peer.service", "postgresql")
                
                try:
                    # Execute the database operation
                    result = func(*args, **kwargs)
                    
                    # Mark span as successful
                    span.set_status(trace.Status(trace.StatusCode.OK))
                    return result
                
                except Exception as e:
                    # Record exception details in the span
                    span.record_exception(e)
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    raise
        return wrapper
    return decorator

class DatabaseTracer:
    """
    Wrapper class for database operations with OpenTelemetry tracing
    """
    def __init__(self, connection_params=None):
        # Use environment variables or default connection parameters
        self.connection_params = connection_params or {
            'dbname': os.environ.get('DB_NAME', 'django'),
            'user': os.environ.get('DB_USER', 'django'),
            'password': os.environ.get('DB_PASSWORD', '1234'),
            'host': os.environ.get('DB_HOST', 'postgresql'),
            'port': os.environ.get('DB_PORT', '5432')
        }
    
    @contextmanager
    def get_connection(self):
        """
        Context manager for database connections with tracing
        """
        connection = None
        try:
            with tracer.start_as_current_span("db.connection"):
                connection = psycopg2.connect(**self.connection_params)
                yield connection
        except Exception as e:
            # Trace connection errors
            active_span = trace.get_current_span()
            active_span.record_exception(e)
            active_span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            raise
        finally:
            if connection:
                connection.close()
    
    @trace_database_operation("query")
    def execute_query(self, query, params=None):
        """
        Execute a database query with comprehensive tracing
        
        Args:
            query (str): SQL query to execute
            params (tuple, optional): Query parameters
        
        Returns:
            List of query results
        """
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                # Add query-specific attributes
                active_span = trace.get_current_span()
                active_span.set_attribute("db.statement", query)
                
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                
                return cursor.fetchall()
    
    @trace_database_operation("transaction")
    def execute_transaction(self, operations):
        """
        Execute a database transaction with tracing
        
        Args:
            operations (callable): Function containing database operations
        """
        with self.get_connection() as conn:
            try:
                with tracer.start_as_current_span("db.transaction"):
                    # Execute the transaction
                    operations(conn)
                    conn.commit()
            except Exception as e:
                # Rollback on error and trace
                conn.rollback()
                active_span = trace.get_current_span()
                active_span.record_exception(e)
                active_span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                raise

def get_db_attributes():
    """
    Generate database connection attributes
    """
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
    """
    Set up OpenTelemetry tracing for the application
    """
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
