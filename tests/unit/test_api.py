import pytest
from rest_framework import status
from rest_framework.test import APIClient

from cache_app.singleton import cache_engine


@pytest.fixture(autouse=True)
def clear_cache():
    """
    Clears cache dict and resets stats before each test.
    """
    with cache_engine.lock:
        cache_engine.cache_dict.clear()
        cache_engine.hits = 0
        cache_engine.misses = 0
        cache_engine.policy_evictions = 0
        cache_engine.ttl_evictions = 0

def test_api_set_and_get():
    client = APIClient()
    
    # 1. New insert
    payload = {"key": "session:1", "value": "user_123", "ttl": 300}
    response = client.post("/api/v1/cache", payload, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["status"] == "success"
    assert response.data["key"] == "session:1"
    assert response.data["expiry"] is not None
    
    # 2. Retrieve key
    response = client.get("/api/v1/cache/session:1")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["key"] == "session:1"
    assert response.data["value"] == "user_123"
    assert response.data["ttl_remaining"] > 0
    
    # 3. Update existing key
    payload = {"key": "session:1", "value": "user_456"}
    response = client.post("/api/v1/cache", payload, format="json")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["status"] == "success"
    assert response.data["expiry"] is None  # Since no TTL was provided, it is now permanent
    
    response = client.get("/api/v1/cache/session:1")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["value"] == "user_456"
    assert response.data["ttl_remaining"] == -1

def test_api_validation_errors():
    client = APIClient()
    
    # Blank key
    payload = {"key": "", "value": "val"}
    response = client.post("/api/v1/cache", payload, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["errorCode"] == "VALIDATION_FAILED"
    assert "key" in response.data["message"]
    
    # Key too long
    payload = {"key": "a" * 251, "value": "val"}
    response = client.post("/api/v1/cache", payload, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["errorCode"] == "VALIDATION_FAILED"
    assert "key" in response.data["message"]
    
    # Value size too large (cap at 1MB, test with > 1MB)
    payload = {"key": "k", "value": "a" * 1048577}
    response = client.post("/api/v1/cache", payload, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["errorCode"] == "VALIDATION_FAILED"
    assert "value" in response.data["message"]
    
    # Negative TTL
    payload = {"key": "k", "value": "v", "ttl": -5}
    response = client.post("/api/v1/cache", payload, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["errorCode"] == "VALIDATION_FAILED"
    assert "ttl" in response.data["message"]

def test_api_get_miss():
    client = APIClient()
    response = client.get("/api/v1/cache/absent_key")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.data["errorCode"] == "KEY_NOT_FOUND"
    assert response.data["status"] == "error"

def test_api_delete():
    client = APIClient()
    
    # Delete absent
    response = client.delete("/api/v1/cache/absent_key")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.data["errorCode"] == "KEY_NOT_FOUND"
    
    # Set and delete
    client.post("/api/v1/cache", {"key": "k", "value": "v"}, format="json")
    response = client.delete("/api/v1/cache/k")
    assert response.status_code == status.HTTP_204_NO_CONTENT

def test_api_exists():
    client = APIClient()
    
    response = client.get("/api/v1/cache/k/exists")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["exists"] is False
    
    client.post("/api/v1/cache", {"key": "k", "value": "v"}, format="json")
    response = client.get("/api/v1/cache/k/exists")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["exists"] is True

def test_api_expire_and_ttl():
    client = APIClient()
    
    # Expire absent
    response = client.post("/api/v1/cache/absent/expire", {"ttl": 10}, format="json")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    
    # Set permanent and check TTL
    client.post("/api/v1/cache", {"key": "k", "value": "v"}, format="json")
    response = client.get("/api/v1/cache/k/ttl")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["ttl_remaining"] == -1
    
    # Expire and check TTL
    response = client.post("/api/v1/cache/k/expire", {"ttl": 50}, format="json")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["ttl_updated"] == 50
    
    response = client.get("/api/v1/cache/k/ttl")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["ttl_remaining"] > 0
    assert response.data["ttl_remaining"] <= 50

def test_api_eviction_failed(settings):
    settings.SHARD_CACHE_MAX_SIZE = 0
    with cache_engine.lock:
        cache_engine.max_size = 0  # Dynamic override for test
        
    client = APIClient()
    response = client.post("/api/v1/cache", {"key": "k", "value": "v"}, format="json")
    assert response.status_code == status.HTTP_507_INSUFFICIENT_STORAGE
    assert response.data["errorCode"] == "EVICTION_FAILED"
    
    # Restore max_size
    with cache_engine.lock:
        cache_engine.max_size = 1000
