import pytest
from rest_framework.test import APIClient
from rest_framework import status
from cache_app.singleton import cache_engine

@pytest.fixture(autouse=True)
def clear_cache():
    with cache_engine.lock:
        cache_engine.cache_dict.clear()

def test_prometheus_plaintext_endpoint():
    # Make some cache hits/misses to record values
    cache_engine.set("key1", "val1")
    cache_engine.get("key1")
    cache_engine.get("missing_key")
    
    client = APIClient()
    response = client.get("/metrics")
    
    assert response.status_code == status.HTTP_200_OK
    assert response.headers["Content-Type"].startswith("text/plain")
    
    content = response.content.decode("utf-8")
    assert "shard_cache_keys_total" in content
    assert "shard_cache_hits_total" in content
    assert "shard_cache_misses_total" in content
    assert "shard_cache_latency_milliseconds" in content

def test_json_latency_endpoint():
    # Record some latency values
    cache_engine.set("key1", "val1")
    cache_engine.get("key1")
    
    client = APIClient()
    response = client.get("/api/v1/metrics/latency")
    
    assert response.status_code == status.HTTP_200_OK
    assert response.data["name"] == "shard.cache.latency"
    assert response.data["baseUnit"] == "milliseconds"
    
    measurements = response.data["measurements"]
    assert len(measurements) == 4
    
    stats = {m["statistic"]: m["value"] for m in measurements}
    assert "MAX" in stats
    assert "P50" in stats
    assert "P95" in stats
    assert "P99" in stats
    
    # Assert values are numeric and >= 0
    for value in stats.values():
        assert isinstance(value, float)
        assert value >= 0.0
