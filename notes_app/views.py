import logging
from django.shortcuts import render, redirect, get_object_or_404
from .models import Note
from .forms import NoteForm

# Tracing
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from opentelemetry.propagate import inject

logger = logging.getLogger(__name__)

# Create a tracer
tracer = trace.get_tracer(__name__)

def create_db_span_attributes(operation, table=None, statement=None, row_count=None):
    return {
        "db.system": "postgresql",
        "db.name": "notes",
        "db.user": "django",
        "db.operation": operation.upper(),
        "db.sql.table": table,
        "db.statement": statement,
        "db.row_count": row_count,
        "server.address": os.environ.get('DB_HOST', 'postgresql'),
        "server.port": os.environ.get('DB_PORT', '5432'),
        "network.transport": "tcp",
        "service.name": "postgresql",
        "peer.service": "notes-web-service"
    }

def note_list(request):
    with tracer.start_as_current_span("note_list") as span:
        # Prepare context for downstream services
        context = {}
        inject(context)
        
        # Add HTTP request details to span
        span.set_attribute("http.method", request.method)
        span.set_attribute("http.route", "/notes")
        
        try:
            # Create a nested span for database query with explicit PostgreSQL service attribution
            with tracer.start_as_current_span("db.query") as db_span:
                # Set attributes immediately within the span context
                db_span.set_attributes({
                    # PostgreSQL Semantic Conventions
                    "db.system": "postgresql",
                    "db.name": "notes",  # Hardcoded or from settings
                    "db.user": "django",  # From database settings
                    "db.operation": "SELECT",
                    "db.sql.table": "notes_app_note",
                    
                    # Network and Service Attributes
                    "server.address": os.environ.get('DB_HOST', 'postgresql'),
                    "server.port": os.environ.get('DB_PORT', '5432'),
                    "network.transport": "tcp",
                    
                    # Detailed Attributes
                    "db.statement": "SELECT * FROM notes_app_note",
                    
                    # Service Attribution
                    "service.name": "postgresql",
                    "peer.service": "notes-web-service"
                })

                # Fetch notes
                notes = Note.objects.all()
                
                # Add row count after query
                db_span.set_attribute("db.row_count", len(notes))

            current_span = trace.get_current_span()
            logger.info(f"Trace ID: {current_span.get_span_context().trace_id}")
            logger.info(f"Span ID: {current_span.get_span_context().span_id}")
            
            return render(request, 'note_list.html', {'notes': notes})
        
        except Exception as e:
            # Record exception in the span
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR))
            raise

def note_create(request):
    with tracer.start_as_current_span("note_create") as span:
        # Add HTTP request details to span
        span.set_attribute("http.method", request.method)
        span.set_attribute("http.route", "/notes/create")
        
        try:
            if request.method == "POST":
                form = NoteForm(request.POST)
                
                if form.is_valid():
                    # Create a nested span for database save with PostgreSQL service attribution
                    with tracer.start_as_current_span("db.save") as db_span:
                        db_span.set_attribute("db.system", "postgresql")
                        db_span.set_attribute("service.name", "postgresql")
                        db_span.set_attribute("peer.service", "notes-web-service")
                        
                        # Save the note
                        note = form.save()
                        
                        # Add save operation details to span
                        db_span.set_attribute("db.operation", "insert")
                        db_span.set_attribute("db.table", "notes_app_note")
                        db_span.set_attribute("note.id", note.id)
                    
                    return redirect('note_list')
            else:
                form = NoteForm()
            
            return render(request, 'note_create.html', {'form': form})
        
        except Exception as e:
            # Record exception in the span
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR))
            raise

def note_update(request, pk):
    with tracer.start_as_current_span("note_update") as span:
        # Add HTTP request details to span
        span.set_attribute("http.method", request.method)
        span.set_attribute("http.route", f"/notes/{pk}/update")
        span.set_attribute("note.pk", pk)
        
        try:
            # Fetch note with tracing
            with tracer.start_as_current_span("db.fetch") as db_span:
                db_span.set_attribute("db.system", "postgresql")
                db_span.set_attribute("service.name", "postgresql")
                db_span.set_attribute("peer.service", "notes-web-service")
                
                note = get_object_or_404(Note, pk=pk)
                
                db_span.set_attribute("db.operation", "select")
                db_span.set_attribute("note.id", note.id)
            
            if request.method == "POST":
                form = NoteForm(request.POST, instance=note)
                
                if form.is_valid():
                    # Update with tracing
                    with tracer.start_as_current_span("db.update") as db_span:
                        db_span.set_attribute("db.system", "postgresql")
                        db_span.set_attribute("service.name", "postgresql")
                        db_span.set_attribute("peer.service", "notes-web-service")
                        
                        updated_note = form.save()
                        
                        db_span.set_attribute("db.operation", "update")
                        db_span.set_attribute("note.id", updated_note.id)
                    
                    return redirect('note_list')
            else:
                form = NoteForm(instance=note)
            
            return render(request, 'note_update.html', {'form': form})
        
        except Exception as e:
            # Record exception in the span
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR))
            raise

def note_delete(request, pk):
    with tracer.start_as_current_span("note_delete") as span:
        # Add HTTP request details to span
        span.set_attribute("http.method", request.method)
        span.set_attribute("http.route", f"/notes/{pk}/delete")
        span.set_attribute("note.pk", pk)
        
        try:
            # Fetch note with tracing
            with tracer.start_as_current_span("db.fetch") as db_span:
                db_span.set_attribute("db.system", "postgresql")
                db_span.set_attribute("service.name", "postgresql")
                db_span.set_attribute("peer.service", "notes-web-service")
                
                note = get_object_or_404(Note, pk=pk)
                
                db_span.set_attribute("db.operation", "select")
                db_span.set_attribute("note.id", note.id)
            
            if request.method == "POST":
                # Delete with tracing
                with tracer.start_as_current_span("db.delete") as db_span:
                    db_span.set_attribute("db.system", "postgresql")
                    db_span.set_attribute("service.name", "postgresql")
                    db_span.set_attribute("peer.service", "notes-web-service")
                    
                    note_id = note.id
                    note.delete()
                    
                    db_span.set_attribute("db.operation", "delete")
                    db_span.set_attribute("note.id", note_id)
                
                return redirect('note_list')
            
            return render(request, 'note_delete.html', {'note': note})
        
        except Exception as e:
            # Record exception in the span
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR))
            raise

def note_detail(request, pk):
    with tracer.start_as_current_span("note_detail") as span:
        # Add HTTP request details to span
        span.set_attribute("http.method", request.method)
        span.set_attribute("http.route", f"/notes/{pk}")
        span.set_attribute("note.pk", pk)
        
        try:
            # Fetch note with tracing
            with tracer.start_as_current_span("db.fetch") as db_span:
                db_span.set_attribute("db.system", "postgresql")
                db_span.set_attribute("service.name", "postgresql")
                db_span.set_attribute("peer.service", "notes-web-service")
                
                note = get_object_or_404(Note, pk=pk)
                
                db_span.set_attribute("db.operation", "select")
                db_span.set_attribute("note.id", note.id)
            
            return render(request, 'note_detail.html', {'note': note})
        
        except Exception as e:
            # Record exception in the span
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR))
            raise
