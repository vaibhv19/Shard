import time

import pytest

from engine.cache_engine import CacheEngine, EvictionFailedException
from engine.cache_entry import CacheEntry


def test_cache_entry_defaults():
    entry = CacheEntry(value="test_value")
    assert entry.value == "test_value"
    assert entry.expiry_time == float('inf')
    assert abs(entry.created_time - time.time()) < 1.0

def test_cache_engine_basic_ops():
    engine = CacheEngine(max_size=10, eviction_policy="lru")
    
    # 1. Test set & exists
    assert not engine.exists("key1")
    is_new = engine.set("key1", "val1")
    assert is_new is True
    assert engine.exists("key1")
    
    # 2. Test get
    assert engine.get("key1") == "val1"
    assert engine.get("key2") is None
    
    # 3. Test overwrite
    is_new = engine.set("key1", "val2")
    assert is_new is False
    assert engine.get("key1") == "val2"
    
    # 4. Test delete
    deleted = engine.delete("key1")
    assert deleted is True
    assert not engine.exists("key1")
    assert engine.get("key1") is None
    
    # 5. Delete absent key
    deleted = engine.delete("key1")
    assert deleted is False

def test_exists_no_side_effects():
    engine = CacheEngine(max_size=10, eviction_policy="lru")
    engine.set("key1", "val1")
    engine.set("key2", "val2")
    
    # LRU order: key1 is least recently used (at tail), key2 is most recently used (at head)
    assert engine.eviction_strategy.tail.prev.key == "key1"
    
    # exists() check should not promote key1 to head
    assert engine.exists("key1") is True
    assert engine.eviction_strategy.tail.prev.key == "key1"

def test_cache_engine_lru_eviction():
    # Cache size 3, LRU policy
    engine = CacheEngine(max_size=3, eviction_policy="lru")
    
    engine.set("k1", "v1")
    engine.set("k2", "v2")
    engine.set("k3", "v3")
    
    # Access k1 to make it most recently used
    # Order: k1 (most recent) -> k3 -> k2 (least recent)
    engine.get("k1")
    
    # Add k4, which should trigger eviction of k2 (least recent)
    engine.set("k4", "v4")
    
    assert not engine.exists("k2")
    assert engine.exists("k1")
    assert engine.exists("k3")
    assert engine.exists("k4")
    assert engine.policy_evictions == 1

def test_cache_engine_lfu_eviction():
    # Cache size 3, LFU policy
    engine = CacheEngine(max_size=3, eviction_policy="lfu")
    
    engine.set("k1", "v1")
    engine.set("k2", "v2")
    engine.set("k3", "v3")
    
    # Access k2 and k3
    # Freq: k2: 2, k3: 2, k1: 1
    engine.get("k2")
    engine.get("k3")
    
    # Add k4, which should trigger eviction of k1 (lowest frequency)
    engine.set("k4", "v4")
    
    assert not engine.exists("k1")
    assert engine.exists("k2")
    assert engine.exists("k3")
    assert engine.exists("k4")
    assert engine.policy_evictions == 1

def test_eviction_failed_exception():
    # Cache size 0, should raise EvictionFailedException immediately
    engine = CacheEngine(max_size=0, eviction_policy="lru")
    with pytest.raises(EvictionFailedException):
        engine.set("k1", "v1")

def test_settings_swap(settings):
    # Test setting integration swap
    settings.SHARD_CACHE_MAX_SIZE = 5
    settings.SHARD_EVICTION_POLICY = "lfu"
    
    engine = CacheEngine()
    assert engine.max_size == 5
    assert engine.policy_name == "lfu"
