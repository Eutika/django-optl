from django.db import models
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

tracer = trace.get_tracer(__name__)

class Note(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title  # Fixed from self.name to self.title

    @classmethod
    def create_note(cls, title, content):
        """
        Class method to create a note with tracing
        """
        with tracer.start_as_current_span("note.create") as span:
            try:
                note = cls.objects.create(title=title, content=content)
                span.set_attribute("note.id", note.id)
                span.set_attribute("note.title", title)
                span.set_status(Status(StatusCode.OK))
                return note
            except Exception as e:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR))
                raise

    def update_note(self, **kwargs):
        """
        Method to update a note with tracing
        """
        with tracer.start_as_current_span("note.update") as span:
            try:
                for key, value in kwargs.items():
                    setattr(self, key, value)
                
                span.set_attribute("note.id", self.id)
                span.set_attribute("updated_fields", list(kwargs.keys()))
                
                self.save()
                span.set_status(Status(StatusCode.OK))
                return self
            except Exception as e:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR))
                raise
