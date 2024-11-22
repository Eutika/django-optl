import os

# Ensure OpenTelemetry is initialized when the project starts
if os.environ.get('OPENTELEMETRY_ENABLED', 'True') == 'True':
    try:
        from .instrumentation import setup_opentelemetry
        setup_opentelemetry()
    except ImportError:
        print("Could not import OpenTelemetry instrumentation")
    except Exception as e:
        print(f"OpenTelemetry initialization failed: {e}")
