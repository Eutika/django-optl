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
    def __init__(self, connection_params=None):
        self.connection_params = connection_params or {
            'dbname': os.environ.get('DB_NAME', 'django'),
            'user': os.environ.get('DB_USER', 'django'),
            'password': os.environ.get('DB_PASSWORD', '1234'),
            'host': os.environ.get('DB_HOST', 'postgresql'),
            'port': os.environ.get('DB_PORT', '5432')
        }
    
    @contextmanager
    def get_connection(self):
        connection = None
        try:
            with tracer.start_as_current_span("db.connection") as span:
                # Explicit service attribution
                span.set_attribute("service.name", "postgresql")
                span.set_attribute("peer.service", "postgresql")
                span.set_attribute("db.system", "postgresql")
                
                connection = psycopg2.connect(**self.connection_params)
                yield connection
        except Exception as e:
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
    logger = logging.getLogger(__name__)
    
    try:
        # More robust tracer provider check
        current_tracer_provider = trace.get_tracer_provider()
        if not isinstance(current_tracer_provider, TracerProvider):
            # Create resource with service name
            resource = Resource.create({
                SERVICE_NAME: os.environ.get('OTEL_SERVICE_NAME', 'postgresql'),
                "service.version": os.environ.get('SERVICE_VERSION', '1.0.0'),
                "deployment.environment": os.environ.get('DEPLOYMENT_ENV', 'kubernetes'),
                "service.namespace": os.environ.get('SERVICE_NAMESPACE', 'notes-app'),
                "service.instance.id": os.environ.get('HOSTNAME', 'unknown-instance')
            })
            
            # Setup trace provider with resource
            provider = TracerProvider(resource=resource)
            trace.set_tracer_provider(provider)
        else:
            provider = current_tracer_provider
            logger.warning("Using existing tracer provider")

        # More robust OTLP exporter configuration
        otlp_endpoint = os.environ.get(
            'OTEL_EXPORTER_OTLP_ENDPOINT', 
            'http://grafana-k8s-monitoring-alloy.grafana.svc.cluster.local:4317'
        )
        
        otlp_exporter = OTLPSpanExporter(
            endpoint=otlp_endpoint,
            insecure=os.environ.get('OTEL_EXPORTER_INSECURE', 'true').lower() == 'true'
        )
        
        # Add batch processor
        batch_processor = BatchSpanProcessor(otlp_exporter)
        provider.add_span_processor(batch_processor)
        
        # Add database span processor
        provider.add_span_processor(DatabaseSpanProcessor())
        
        # Enhanced Psycopg2 Instrumentation
        try:
            Psycopg2Instrumentor().instrument(
                tracer_provider=provider,
                tags_generator=lambda cursor: {
                    "db.system": "postgresql",
                    "service.name": "postgresql",
                    "peer.service": "notes-web-service",
                    "net.peer.name": os.environ.get('DB_HOST', 'localhost'),
                    "net.peer.port": os.environ.get('DB_PORT', '5432')
                }
            )
            logger.info("Psycopg2 instrumentation successful")
        except Exception as psycopg_err:
            logger.error(f"Psycopg2 instrumentation failed: {psycopg_err}")
        
        # Enhanced Django Instrumentation
        try:
            DjangoInstrumentor().instrument(
                # More comprehensive instrumentation options
                is_sql_commentator_enabled=True,
                tracer_provider=provider,
                get_tracer_provider=provider,
                commenter_options={
                    'comment_prefix': 'django-otel',
                    'db_statement_key': 'db.statement'
                },
                # Ensure link between web and database services
                trace_parent_span_header_name='traceparent'
            )
            logger.info("Django instrumentation successful")
        except Exception as django_err:
            logger.error(f"Django instrumentation failed: {django_err}")
        
        logger.info("OpenTelemetry setup completed successfully")
    
    except Exception as setup_err:
        logger.error(f"OpenTelemetry setup failed: {setup_err}")
        raise

def link_service_spans(parent_span, child_span):
    """
    Explicitly link spans between services
    """
    if parent_span and child_span:
        child_span.set_attribute("service.parent", parent_span.get_span_context().trace_id)
        parent_span.set_attribute("service.child", child_span.get_span_context().trace_id)
