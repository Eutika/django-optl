from django.shortcuts import render, redirect, get_object_or_404
from .models import Note
from .forms import NoteForm

# Tracing
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

tracer = trace.get_tracer(__name__)

def note_list(request):
    with tracer.start_as_current_span("note_list") as span:
        with tracer.start_as_current_span("database_query"):
            notes = Note.objects.all()
        
        # Add attributes to the span
        span.set_attribute("http.method", request.method)
        span.set_attribute("notes.count", len(notes))
        
        return render(request, 'note_list.html', {'notes': notes})

def note_create(request):
    with tracer.start_as_current_span("note_create") as span:
        span.set_attribute("http.method", request.method)
        span.set_attribute("form.is_valid", False)  # Will be updated if form is valid
        
        try:
            if request.method == "POST":
                form = NoteForm(request.POST)
                if form.is_valid():
                    span.set_attribute("form.is_valid", True)
                    # Record database operation
                    with tracer.start_as_current_span("note_save"):
                        form.save()
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
        span.set_attribute("http.method", request.method)
        span.set_attribute("note.pk", pk)
        
        try:
            note = get_object_or_404(Note, pk=pk)
            
            if request.method == "POST":
                form = NoteForm(request.POST, instance=note)
                if form.is_valid():
                    with tracer.start_as_current_span("note_update_save"):
                        form.save()
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
        span.set_attribute("http.method", request.method)
        span.set_attribute("note.pk", pk)
        
        try:
            note = get_object_or_404(Note, pk=pk)
            
            if request.method == "POST":
                with tracer.start_as_current_span("note_delete_operation"):
                    note.delete()
                return redirect('note_list')
            
            return render(request, 'note_delete.html', {'note': note})
        
        except Exception as e:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR))
            raise

def note_detail(request, pk):
    with tracer.start_as_current_span("note_detail") as span:
        span.set_attribute("http.method", request.method)
        span.set_attribute("note.pk", pk)
        
        try:
            notes = get_object_or_404(Note, pk=pk)
            return render(request, 'note_detail.html', {'notes': notes})
        
        except Exception as e:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR))
            raise


