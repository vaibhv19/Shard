from django.urls import include, path

urlpatterns = [
    path('api/v1/cache', include('cache_app.urls')),
]
