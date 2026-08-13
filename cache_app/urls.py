from django.urls import path

from cache_app.views import (
    CacheDetailView,
    CacheExistsView,
    CacheExpireView,
    CacheTtlView,
    CacheView,
    CacheInvalidateView,
)

urlpatterns = [
    path('', CacheView.as_view(), name='cache-base'),
    path('/invalidate', CacheInvalidateView.as_view(), name='cache-invalidate'),
    path('/<str:key>', CacheDetailView.as_view(), name='cache-detail'),
    path('/<str:key>/exists', CacheExistsView.as_view(), name='cache-exists'),
    path('/<str:key>/expire', CacheExpireView.as_view(), name='cache-expire'),
    path('/<str:key>/ttl', CacheTtlView.as_view(), name='cache-ttl'),
]
