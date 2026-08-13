from concurrent.futures import ThreadPoolExecutor

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from cache_app.singleton import cache_engine


@pytest.fixture(autouse=True)
def clear_cache(settings):
    """
    Clears cache dict, resets stats, and ensures single-node config before each test.
    """
    settings.SHARD_NODE_ID = "Node-A"
    settings.SHARD_CLUSTER_NODES = {
        "Node-A": "http://127.0.0.1:8000"
    }
    import cache_app
    from cache_app.apps import CacheAppConfig
    config = CacheAppConfig('cache_app', cache_app)
    config.ready()

    with cache_engine.lock:
        cache_engine.cache_dict.clear()
        cache_engine.hits = 0
        cache_engine.misses = 0
        cache_engine.policy_evictions = 0
        cache_engine.ttl_evictions = 0


def test_concurrent_api_post_expiry_race():
    """
    Verifies that concurrent POST write requests and DELETE requests
    on the same key do not result in a 'null' expiry string in POST responses.
    """
    client = APIClient()
    
    # Pre-populate the key
    client.post("/api/v1/cache", {"key": "con_race_key", "value": "initial", "ttl": 100}, format="json")
    
    def writer():
        c = APIClient()
        res = c.post("/api/v1/cache", {"key": "con_race_key", "value": "new_val", "ttl": 100}, format="json")
        if res.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]:
            assert res.data["expiry"] is not None

    def deleter():
        c = APIClient()
        c.delete("/api/v1/cache/con_race_key")

    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = []
        for _ in range(100):
            futures.append(executor.submit(writer))
            futures.append(executor.submit(deleter))
            
        for fut in futures:
            fut.result()


def test_concurrent_api_get_ttl_race():
    """
    Verifies that concurrent GET and DELETE/expiration do not raise a 404
    after the value has already been successfully retrieved.
    """
    def reader():
        c = APIClient()
        res = c.get("/api/v1/cache/con_get_race_key")
        if res.status_code == status.HTTP_200_OK:
            assert res.data["value"] is not None
            assert "ttl_remaining" in res.data

    def modifier():
        c = APIClient()
        # Constantly write and delete the key
        c.post("/api/v1/cache", {"key": "con_get_race_key", "value": "val", "ttl": 50}, format="json")
        c.delete("/api/v1/cache/con_get_race_key")

    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = []
        for _ in range(100):
            futures.append(executor.submit(reader))
            futures.append(executor.submit(modifier))
            
        for fut in futures:
            fut.result()
