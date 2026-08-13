from django.urls import include, path

from cache_app.views import (
    CacheClusterHealthView,
    CacheClusterRingView,
    CacheLatencyMetricsView,
    PrometheusMetricsView,
)

urlpatterns = [
    path('api/v1/cache', include('cache_app.urls')),
    path('api/v1/cluster/health', CacheClusterHealthView.as_view(), name='cluster-health'),
    path('api/v1/cluster/ring', CacheClusterRingView.as_view(), name='cluster-ring'),
    path('metrics', PrometheusMetricsView.as_view(), name='prometheus-metrics'),
    path('api/v1/metrics/latency', CacheLatencyMetricsView.as_view(), name='metrics-latency'),
]
