from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseBadRequest
from .models import Note
from .forms import NoteForm

# Tracing
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

tracer = trace.get_tracer(__name__)

def note_list(request):
    with tracer.start_as_current_span("note_list") as span:
        try:
            # Add more context to the span
            span.set_attribute("http.method", request.method)
            span.set_attribute("http.route", "note_list")
            
            with tracer.start_as_current_span("database_query"):
                notes = Note.objects.all()
                span.set_attribute("database.query", "SELECT * FROM notes_app_note")
                span.set_attribute("notes.count", len(notes))
            
            return render(request, 'note_list.html', {'notes': notes})
        except Exception as e:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR))
            raise

def note_create(request):
    with tracer.start_as_current_span("note_create") as span:
        try:
            span.set_attribute("http.method", request.method)
            span.set_attribute("form.is_valid", False)  # Will be updated if form is valid
            
            if request.method == "POST":
                form = NoteForm(request.POST)
                
                if form.is_valid():
                    span.set_attribute("form.is_valid", True)
                    
                    # Record database operation
                    with tracer.start_as_current_span("note_save"):
                        note = form.save()
                        span.set_attribute("note.id", note.id)
                        span.set_attribute("note.title", note.title)
                    
                    return redirect('note_list')
            else:
                form = NoteForm()
            
            return render(request, 'note_create.html', {'form': form})
        
        except Exception as e:
            # Record error in tracing
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR))
            # Optionally re-raise or handle the error
            raise

def note_update(request, pk):
    with tracer.start_as_current_span("note_update") as span:
        try:
            span.set_attribute("http.method", request.method)
            span.set_attribute("note.pk", pk)
            
            note = get_object_or_404(Note, pk=pk)
            
            if request.method == "POST":
                form = NoteForm(request.POST, instance=note)
                
                if form.is_valid():
                    with tracer.start_as_current_span("note_update_save"):
                        updated_note = form.save()
                        span.set_attribute("note.id", updated_note.id)
                        span.set_attribute("note.title", updated_note.title)
                    
                    return redirect('note_list')
            else:
                form = NoteForm(instance=note)
            
            return render(request, 'note_update.html', {'form': form})
        
        except Exception as e:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR))
            raise

def note_delete(request, pk):
    with tracer.start_as_current_span("note_delete") as span:
        try:
            span.set_attribute("http.method", request.method)
            span.set_attribute("note.pk", pk)
            
            note = get_object_or_404(Note, pk=pk)
            
            if request.method == "POST":
                with tracer.start_as_current_span("note_delete_operation"):
                    note_id = note.id
                    note_title = note.title
                    note.delete()
                    
                    span.set_attribute("deleted_note.id", note_id)
                    span.set_attribute("deleted_note.title", note_title)
                
                return redirect('note_list')
            
            return render(request, 'note_delete.html', {'note': note})
        
        except Exception as e:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR))
            raise

def note_detail(request, pk):
    with tracer.start_as_current_span("note_detail") as span:
        try:
            span.set_attribute("http.method", request.method)
            span.set_attribute("note.pk", pk)
            
            note = get_object_or_404(Note, pk=pk)
            
            span.set_attribute("note.title", note.title)
            
            return render(request, 'note_detail.html', {'note': note})
        
        except Exception as e:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR))
            raise
