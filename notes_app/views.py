from django.shortcuts import render, redirect, get_object_or_404
from .models import Note
from .forms import NoteForm

# OpenTelemetry Tracing
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

# Import the decorator from instrumentation
from django_project.instrumentation import trace_django_request, otel_config

# Tracer
tracer = trace.get_tracer(__name__)

@trace_django_request
def note_list(request):
    with tracer.start_as_current_span("note_list_query") as span:
        try:
            # Capture query details
            notes = Note.objects.all()
            span.set_attributes({
                "db.operation": "SELECT",
                "db.model": "Note",
                "db.row_count": len(notes)
            })
            return render(request, 'note_list.html', {'notes': notes})
        except Exception as e:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR))
            raise

@trace_django_request
def note_create(request):
    with tracer.start_as_current_span("note_create_process") as span:
        try:
            if request.method == "POST":
                form = NoteForm(request.POST)
                if form.is_valid():
                    note = form.save()
                    span.set_attributes({
                        "db.operation": "INSERT",
                        "db.model": "Note",
                        "note.id": note.id
                    })
                    return redirect('note_list')
            else:
                form = NoteForm()
            
            return render(request, 'note_create.html', {'form': form})
        except Exception as e:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR))
            raise

@trace_django_request
def note_update(request, pk):
    with tracer.start_as_current_span("note_update_process") as span:
        try:
            note = get_object_or_404(Note, pk=pk)
            span.set_attributes({
                "note.id": pk,
                "db.operation": "SELECT"
            })

            if request.method == "POST":
                form = NoteForm(request.POST, instance=note)
                if form.is_valid():
                    updated_note = form.save()
                    span.set_attributes({
                        "db.operation": "UPDATE",
                        "note.id": updated_note.id
                    })
                    return redirect('note_list')
            else:
                form = NoteForm(instance=note)
            
            return render(request, 'note_update.html', {'form': form})
        except Exception as e:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR))
            raise

@trace_django_request
def note_delete(request, pk):
    with tracer.start_as_current_span("note_delete_process") as span:
        try:
            note = get_object_or_404(Note, pk=pk)
            span.set_attributes({
                "note.id": pk,
                "db.operation": "SELECT"
            })

            if request.method == "POST":
                note.delete()
                span.set_attributes({
                    "db.operation": "DELETE",
                    "note.id": pk
                })
                return redirect('note_list')
            
            return render(request, 'note_delete.html', {'note': note})
        except Exception as e:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR))
            raise

@trace_django_request
def note_detail(request, pk):
    with tracer.start_as_current_span("note_detail_query") as span:
        try:
            note = get_object_or_404(Note, pk=pk)
            span.set_attributes({
                "note.id": pk,
                "db.operation": "SELECT"
            })
            return render(request, 'note_detail.html', {'note': note})
        except Exception as e:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR))
            raise
