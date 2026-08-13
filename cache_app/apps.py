import sys

from django.apps import AppConfig


class CacheAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'cache_app'

    def ready(self):
        # We only want to start the active sweeper if we are in runserver/wsgi/gunicorn,
        # and not in a test session.
        if 'test' not in sys.argv and 'pytest' not in sys.modules:
            from cache_app.singleton import active_sweeper
            active_sweeper.start()
