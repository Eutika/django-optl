from django.apps import AppConfig

class NotesAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'notes_app'

    def ready(self):
        if self.apps.is_installed('notes_app'):
            import os
            if os.environ.get('OPENTELEMETRY_ENABLED', 'True') == 'True':
                try:
                    from django_project.instrumentation import setup_opentelemetry
                    setup_opentelemetry()
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to initialize OpenTelemetry: {e}")
