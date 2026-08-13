import pytest

from engine.cache_engine import CacheEngine
from engine.metrics.collector import (
    NODE_ID,
    shard_evictions_total,
    shard_hits_total,
    shard_keys_total,
    shard_latency,
    shard_misses_total,
)


@pytest.fixture(autouse=True)
def reset_prometheus_metrics():
    # Reset prometheus metric values where possible (or just read before/after values to check increments)
    pass

def test_metrics_collection_hits_misses():
    engine = CacheEngine(max_size=10)
    
    # Track starting counters
    try:
        start_hits = shard_hits_total.labels(node=NODE_ID, eviction_policy=engine.policy_name)._value.get()
    except KeyError:
        start_hits = 0.0
        
    try:
        start_misses = shard_misses_total.labels(node=NODE_ID)._value.get()
    except KeyError:
        start_misses = 0.0

    # Trigger Miss
    engine.get("missing_key")
    
    # Trigger Hit
    engine.set("key1", "val1")
    engine.get("key1")
    
    # Read updated values
    end_hits = shard_hits_total.labels(node=NODE_ID, eviction_policy=engine.policy_name)._value.get()
    end_misses = shard_misses_total.labels(node=NODE_ID)._value.get()
    
    assert end_misses == start_misses + 1
    assert end_hits == start_hits + 1

def test_metrics_collection_evictions():
    # Setup cache engine with max size 1 to force policy evictions
    engine = CacheEngine(max_size=1)
    
    try:
        start_evictions = shard_evictions_total.labels(node=NODE_ID, reason="policy")._value.get()
    except KeyError:
        start_evictions = 0.0
        
    engine.set("k1", "v1")
    engine.set("k2", "v2")  # Triggers eviction of k1
    
    end_evictions = shard_evictions_total.labels(node=NODE_ID, reason="policy")._value.get()
    assert end_evictions == start_evictions + 1

def test_metrics_collection_keys_count():
    engine = CacheEngine(max_size=10)
    
    engine.set("k1", "v1")
    engine.set("k2", "v2")
    
    current_keys = shard_keys_total.labels(node=NODE_ID)._value.get()
    assert current_keys == 2
    
    engine.delete("k1")
    current_keys_after = shard_keys_total.labels(node=NODE_ID)._value.get()
    assert current_keys_after == 1

def test_metrics_collection_latency():
    engine = CacheEngine(max_size=10)
    
    # Perform operations
    engine.set("k", "v")
    engine.get("k")
    engine.delete("k")
    
    # Check that histogram observations exist
    def get_hist_count(child):
        for sample in child._samples():
            if sample.name == '_count':
                return sample.value
        return 0.0
        
    set_child = shard_latency.labels(node=NODE_ID, operation="SET")
    get_child = shard_latency.labels(node=NODE_ID, operation="GET")
    del_child = shard_latency.labels(node=NODE_ID, operation="DELETE")
    
    assert get_hist_count(set_child) >= 1
    assert get_hist_count(get_child) >= 1
    assert get_hist_count(del_child) >= 1
