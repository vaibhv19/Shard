# mypy: ignore-errors
import os

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-shard-cache-secret-key')
DEBUG = True
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'rest_framework',
    'cache_app.apps.CacheAppConfig',
]

MIDDLEWARE = [
    'django.middleware.common.CommonMiddleware',
]

ROOT_URLCONF = 'shard_project.urls'
WSGI_APPLICATION = 'shard_project.wsgi.application'

# Strictly in-memory, no database ORM
DATABASES = {}

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = False
USE_TZ = True

# Disable append slash to match API contracts exactly
APPEND_SLASH = False

# Shard Cache Engine Configurations
SHARD_CACHE_MAX_SIZE = 1000
SHARD_EVICTION_POLICY = 'lru'
SHARD_ACTIVE_EXPIRY_INTERVAL = 5.0
SHARD_ACTIVE_EXPIRY_BATCH_SIZE = 20

# Django REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [],
    'DEFAULT_PERMISSION_CLASSES': [],
    'UNAUTHENTICATED_USER': None,
    'UNAUTHENTICATED_TOKEN': None,
    'EXCEPTION_HANDLER': 'cache_app.exceptions.custom_exception_handler',
}

# Static Cluster Sharding Configurations
SHARD_NODE_ID = os.getenv('SHARD_NODE_ID', 'Node-A')
SHARD_VIRTUAL_NODES = 150
SHARD_CLUSTER_NODES = {
    "Node-A": "http://127.0.0.1:8000",
    "Node-B": "http://127.0.0.1:8001",
    "Node-C": "http://127.0.0.1:8002",
}
