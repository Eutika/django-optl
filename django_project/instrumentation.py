import os
import sys
import socket
import logging
import logging.config
import psycopg2
from functools import wraps
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME

def configure_logging():
    """
    Logging configuration for instrumentation
    """
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    # Create formatter
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)

    # Add handler to logger
    logger.addHandler(console_handler)

    return logger

# Set up logger
logger = configure_logging()

class TracedDatabaseConnection:
    def __init__(self, conn_params, tracer):
        self.conn_params = conn_params
        self.tracer = tracer
        self.span = None
        self.connection = None

    def __enter__(self):
        # Create a span for the database connection
        self.span = self.tracer.start_span("db.connection")
        
        try:
            self.connection = psycopg2.connect(**self.conn_params)
            
            # Add connection details to span
            if self.span:
                self.span.set_attributes({
                    "db.system": "postgresql",
                    "db.connection.host": self.conn_params.get('host', 'unknown'),
                    "db.connection.port": str(self.conn_params.get('port', 'unknown')),
                    "db.connection.user": self.conn_params.get('user', 'unknown'),
                })
            
            return self
        except Exception as e:
            # Record exception in the span if connection fails
            if self.span:
                self.span.record_exception(e)
                self.span.set_status(Status(StatusCode.ERROR))
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Close the connection
        if self.connection:
            try:
                self.connection.close()
            except Exception:
                pass
        
        # End the span
        if self.span:
            try:
                if exc_type:
                    self.span.record_exception(exc_val)
                    self.span.set_status(Status(StatusCode.ERROR))
                self.span.end()
            except Exception:
                pass

    def cursor(self):
        return TracedCursor(self.connection.cursor(), self.tracer)

    def commit(self):
        if self.connection:
            self.connection.commit()

    def rollback(self):
        if self.connection:
            self.connection.rollback()

class TracedCursor:
    def __init__(self, cursor, tracer):
        self.cursor = cursor
        self.tracer = tracer
        self.span = None

    def __enter__(self):
        # Create a span when entering the context
        self.span = self.tracer.start_span("database.query")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # End the span when exiting the context
        if self.span:
            if exc_type:
                # Record exception if one occurred
                self.span.record_exception(exc_val)
                self.span.set_status(Status(StatusCode.ERROR))
            
            # Attempt to end the span safely
            try:
                self.span.end()
            except Exception:
                pass

    def execute(self, query, vars=None):
        try:
            # If no span was created via context manager, create one
            if not self.span:
                self.span = self.tracer.start_span("database.query")

            # Comprehensive span attributes
            self.span.set_attributes({
                "db.system": "postgresql",
                "db.statement": query,
                "db.operation": query.split()[0].upper(),
                "db.sql.table": self._extract_table_name(query)
            })
            
            # Execute the query
            if vars:
                result = self.cursor.execute(query, vars)
            else:
                result = self.cursor.execute(query)
            
            # Add query execution details
            self.span.set_attributes({
                "db.row_count": self.cursor.rowcount
            })
            
            return result
        except Exception as e:
            # Record exception details in the span
            if self.span:
                self.span.record_exception(e)
                self.span.set_status(Status(StatusCode.ERROR))
            raise
        finally:
            # Safely end the span
            if self.span:
                try:
                    self.span.end()
                    self.span = None
                except Exception:
                    pass

    def _extract_table_name(self, query):
        """
        Basic method to extract table name from simple queries
        """
        try:
            query_lower = query.lower().strip()
            if query_lower.startswith('select'):
                parts = query_lower.split('from')
                if len(parts) > 1:
                    table = parts[1].strip().split()[0]
                    return table
            elif query_lower.startswith('insert'):
                parts = query_lower.split('into')
                if len(parts) > 1:
                    table = parts[1].strip().split()[0]
                    return table
            elif query_lower.startswith('update'):
                parts = query_lower.split('update')
                if len(parts) > 1:
                    table = parts[1].strip().split()[0]
                    return table
            return "unknown"
        except Exception:
            return "unknown"

    # Delegate other cursor methods
    def __getattr__(self, name):
        return getattr(self.cursor, name)

    # Add methods to support cursor-like behavior
    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()

    def close(self):
        return self.cursor.close()

def validate_conn_params(conn_params):
    """
    Validate database connection parameters
    """
    required_keys = ['host', 'dbname', 'user', 'port']
    for key in required_keys:
        if key not in conn_params or not conn_params[key]:
            logger.warning(f"Missing or empty connection parameter: {key}")
    return conn_params

def log_environment_variables():
    """
    Log relevant environment variables for debugging
    """
    env_vars = [
        'OTEL_SERVICE_NAME',
        'OTEL_EXPORTER_OTLP_ENDPOINT',
        'DEPLOYMENT_ENV',
        'DB_HOST',
        'DB_NAME',
        'DB_USER'
    ]
    
    for var in env_vars:
        value = os.environ.get(var)
        if value:
            logger.info(f"ENV {var}: {value}")
        else:
            logger.warning(f"ENV {var}: Not set")

def trace_django_request(view_func):
    """
    Decorator to trace Django HTTP requests with comprehensive attributes
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span(
            f"{request.method} {request.path}", 
            kind=trace.SpanKind.SERVER
        ) as span:
            # Capture detailed request metadata
            span.set_attributes({
                "http.method": request.method,
                "http.url": request.build_absolute_uri(),
                "http.host": request.get_host(),
                "http.scheme": request.scheme,
                "http.user_agent": request.META.get('HTTP_USER_AGENT', 'unknown'),
                "http.client_ip": request.META.get('REMOTE_ADDR', 'unknown')
            })

            try:
                response = view_func(request, *args, **kwargs)
                span.set_attributes({"http.status_code": response.status_code})
                return response
            except Exception as e:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR))
                raise

    return wrapper

def trace_database_query(query, conn_params):
    """
    Create a database query span with comprehensive attributes
    """
    current_span = trace.get_current_span()
    tracer = trace.get_tracer(__name__)
    
    with tracer.start_span(
        "database.query", 
        context=trace.set_span_in_context(current_span),
        kind=trace.SpanKind.CLIENT
    ) as span:
        span.set_attributes({
            "db.system": "postgresql",
            "db.statement": query,
            "db.operation": query.split()[0].upper(),
            "db.sql.table": _extract_table_name(query),
            "db.connection.host": conn_params.get('host', 'unknown'),
            "db.connection.user": conn_params.get('user', 'unknown')
        })

def _extract_table_name(query):
    """
    Extract table name from SQL query
    """
    try:
        query_lower = query.lower().strip()
        if query_lower.startswith('select'):
            parts = query_lower.split('from')
            if len(parts) > 1:
                return parts[1].strip().split()[0]
        elif query_lower.startswith('insert'):
            parts = query_lower.split('into')
            if len(parts) > 1:
                return parts[1].strip().split()[0]
        elif query_lower.startswith('update'):
            parts = query_lower.split('update')
            if len(parts) > 1:
                return parts[1].strip().split()[0]
        return "unknown"
    except Exception:
        return "unknown"

def setup_opentelemetry():
    try:
        logger.info("Starting OpenTelemetry Instrumentation Setup")
        logger.info(f"Python Version: {sys.version}")
    
        log_environment_variables()
        # Database connection parameters
        conn_params = {
            'host': os.environ.get('DB_HOST', 'localhost'),
            'dbname': os.environ.get('DB_NAME', 'notes'),
            'user': os.environ.get('DB_USER', 'django'),
            'password': os.environ.get('DB_PASSWORD', ''),
            'port': os.environ.get('DB_PORT', '5432')
        }
        
        # Remove any None or empty string values
        conn_params = validate_conn_params(conn_params)
        
        logger.info(f"Database Connection Params: {conn_params}")

        # Resource creation
        resource = Resource.create({
            "service.name": "postgresql",
            "service.version": os.environ.get('SERVICE_VERSION', '1.0.0'),
            "deployment.environment": os.environ.get('DEPLOYMENT_ENV', 'development'),
            "service.namespace": os.environ.get('SERVICE_NAMESPACE', 'notes-app'),
            "service.instance.id": os.environ.get('HOSTNAME', socket.gethostname()),
            "net.host.name": socket.gethostname()
        })

        # Provider setup
        provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(provider)

        # Exporters list
        exporters = []

        # Console exporter as a guaranteed fallback
        console_exporter = ConsoleSpanExporter()
        exporters.append(console_exporter)

        # Attempt OTLP HTTP Exporter if available
        if OTLPSpanExporter:
            try:
                otlp_endpoint = os.environ.get(
                    'OTEL_EXPORTER_OTLP_ENDPOINT', 
                    'http://grafana-k8s-monitoring-alloy.grafana.svc.cluster.local:4317'
                )
                
                # Create OTLP exporter
                otlp_exporter = OTLPSpanExporter(
                    endpoint=otlp_endpoint
                )
                exporters.append(otlp_exporter)
                logger.info(f"OTLP exporter configured with endpoint: {otlp_endpoint}")
            
            except Exception as otlp_err:
                logger.warning(f"OTLP exporter configuration failed: {otlp_err}")

        # Add batch processors for each exporter
        for exporter in exporters:
            batch_processor = BatchSpanProcessor(
                exporter,
                max_queue_size=2048,
                schedule_delay_millis=5000,
                export_timeout_millis=30000
            )
            provider.add_span_processor(batch_processor)

        # Get the tracer
        tracer = provider.get_tracer(__name__)

        # Enhanced Psycopg2 Instrumentation
        try:
            from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
            Psycopg2Instrumentor().instrument(
                tracer_provider=provider,
                tags_generator=lambda cursor: {
                    "db.system": "postgresql",
                    "db.name": conn_params.get('dbname', 'unknown'),
                    "db.user": conn_params.get('user', 'unknown'),
                    "net.peer.name": conn_params.get('host', 'localhost'),
                    "net.peer.port": conn_params.get('port', '5432'),
                    "net.transport": "ip_tcp",
                    "service.name": "postgresql",
                    "server.address": conn_params.get('host', 'localhost'),
                    "server.port": conn_params.get('port', '5432'),
                    "peer.service": "notes-web-service",
                }
            )
            logger.info("Psycopg2 instrumentation successful")
        except Exception as psycopg_err:
            logger.error(f"Psycopg2 instrumentation failed: {psycopg_err}")
        
        return {
            'tracer': tracer,
            'conn_params': conn_params,
            'provider': provider,
        }
    
    except Exception as setup_err:
        logger.error(f"OpenTelemetry setup failed: {setup_err}")
        # Provide a fallback tracer
        fallback_tracer = trace.get_tracer(__name__)
        return {
            'tracer': fallback_tracer,
            'conn_params': {},
            'provider': None,
        }

# Ensure single initialization
if 'otel_config' not in globals():
    otel_config = setup_opentelemetry()
