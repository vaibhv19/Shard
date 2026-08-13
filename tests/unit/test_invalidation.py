import pytest
from rest_framework import status
from rest_framework.test import APIClient

from cache_app.singleton import cache_engine


@pytest.fixture(autouse=True)
def clear_cache():
    with cache_engine.lock:
        cache_engine.cache_dict.clear()

def test_pattern_invalidation_exact():
    # Insert keys
    cache_engine.set("key1", "val1")
    cache_engine.set("key2", "val2")
    
    client = APIClient()
    response = client.post("/api/v1/cache/invalidate", {"pattern": "key1"}, format="json")
    
    assert response.status_code == status.HTTP_200_OK
    assert response.data["status"] == "success"
    assert response.data["invalidatedKeysCount"] == 1
    
    assert cache_engine.exists("key1") is False
    assert cache_engine.exists("key2") is True

def test_pattern_invalidation_wildcard():
    # Insert keys
    cache_engine.set("user:session:123", "val1")
    cache_engine.set("user:session:456", "val2")
    cache_engine.set("user:profile:123", "val3")
    cache_engine.set("other:key", "val4")
    
    client = APIClient()
    response = client.post("/api/v1/cache/invalidate", {"pattern": "user:session:*"}, format="json")
    
    assert response.status_code == status.HTTP_200_OK
    assert response.data["invalidatedKeysCount"] == 2
    
    assert cache_engine.exists("user:session:123") is False
    assert cache_engine.exists("user:session:456") is False
    assert cache_engine.exists("user:profile:123") is True
    assert cache_engine.exists("other:key") is True

def test_pattern_invalidation_flush():
    cache_engine.set("k1", "v1")
    cache_engine.set("k2", "v2")
    
    client = APIClient()
    response = client.post("/api/v1/cache/invalidate", {"pattern": "*"}, format="json")
    
    assert response.status_code == status.HTTP_200_OK
    assert response.data["invalidatedKeysCount"] == 2
    
    assert len(cache_engine.cache_dict) == 0
