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
The application is configured to send traces to Grafana Tempo via the Alloy collector.

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
