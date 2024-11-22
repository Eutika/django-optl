# Django Notes App with Distributed Tracing

## Overview
This is a Django-based Notes application deployed on Kubernetes with distributed tracing using OpenTelemetry and Grafana.

## Architecture
- Django Web Application
- PostgreSQL Database
- Kubernetes Deployment
- OpenTelemetry Instrumentation
- Grafana Tempo for Distributed Tracing

## Prerequisites
- Kubernetes Cluster
- kubectl
- Helm (optional)
- Docker

## Components
- `notes-app`: Django web application
- `postgresql`: Database for storing notes

## Configuration
### Environment Variables
- `DB_NAME`: Database name (default: `notes`)
- `DB_USER`: Database user (default: `django`)
- `DB_PASSWORD`: Database password
- `OTEL_EXPORTER_OTLP_ENDPOINT`: OpenTelemetry collector endpoint

## Deployment
```bash
kubectl apply -f deployment.yaml
```

### Database Migrations
After deploying, execute database migrations:

```bash
# Find the correct pod name
kubectl get pods

# Run makemigrations
kubectl exec <notes-app-pod-name> -- python manage.py makemigrations

# Apply migrations
kubectl exec <notes-app-pod-name> -- python manage.py migrate
```

Example:
```bash
kubectl exec notes-app-64887b67d6-86w86 -- python manage.py makemigrations
kubectl exec notes-app-64887b67d6-86w86 -- python manage.py migrate
```

#### Migration Output
When you run migrations, you'll see:
- Creation of initial migrations for `notes_app`
- Application of Django default migrations (contenttypes, auth, admin, sessions)

⚠️ Always run migrations after initial deployment or when changing models.``

## Distributed Tracing

### Database Tracing Configuration
- Uses OpenTelemetry Django and Psycopg2 instrumentations
- Traces include:
  - Database connection details
  - Query performance
  - Distributed tracing context

### Tracing Packages
- `opentelemetry-instrumentation-django`
- `opentelemetry-instrumentation-psycopg2`
- `opentelemetry-exporter-otlp`

### Tracing Features
- Comprehensive OpenTelemetry instrumentation
- Spans for each view method
- Error tracking and status reporting
- Detailed attributes:
  - HTTP methods
  - Note primary keys
  - Form validation status

### Traced Operations
- List notes
- Create notes
- Update notes
- Delete notes
- View note details

### Tracing Attributes
- `http.method`: HTTP request method
- `notes.count`: Number of notes
- `note.pk`: Primary key of specific notes
- `form.is_valid`: Form validation status
### Debugging Tracing
- Verify OpenTelemetry packages are installed
- Check OTLP exporter configuration
- Ensure tracing is enabled in Django settings

## Troubleshooting Tracing
- Verify OTLP exporter endpoint
- Check Grafana Alloy configuration
- Ensure network connectivity between services and tracing backend

### Tracing Endpoint
`http://grafana-k8s-monitoring-alloy.grafana.svc.cluster.local:4317`

## Development
1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Run locally: `python manage.py runserver`

## Docker Build
```bash
docker build -t dalareo/notes-app:latest .
```

## Monitoring
Traces can be viewed in the Grafana Tempo dashboard.

## Security Considerations
⚠️ Update default database credentials in production!
