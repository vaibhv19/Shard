from django.urls import path, include
from cache_app.views import CacheClusterHealthView, CacheClusterRingView

urlpatterns = [
    path('api/v1/cache', include('cache_app.urls')),
    path('api/v1/cluster/health', CacheClusterHealthView.as_view(), name='cluster-health'),
    path('api/v1/cluster/ring', CacheClusterRingView.as_view(), name='cluster-ring'),
]
