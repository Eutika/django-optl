from django.db import models
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

tracer = trace.get_tracer(__name__)

class Note(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        with tracer.start_as_current_span("note.save") as span:
            try:
                span.set_attribute("service.name", "postgresql")
                span.set_attribute("peer.service", "postgresql")
                span.set_attribute("db.system", "postgresql")
                span.set_attribute("db.operation", "save")
                
                result = super().save(*args, **kwargs)
                
                span.set_attribute("note.id", self.id)
                span.set_attribute("note.title", self.title)
                span.set_status(Status(StatusCode.OK))
                
                return result
            except Exception as e:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR))
                raise
