from engine.evict.lfu_eviction import LfuEvictionPolicy


def test_lfu_basic_eviction():
    policy = LfuEvictionPolicy()
    
    # Insert 3 keys
    policy.on_insert("k1")
    policy.on_insert("k2")
    policy.on_insert("k3")
    
    # All start at frequency 1. k1 was inserted first, so it is the oldest at min_frequency=1.
    assert policy.evict_victim() == "k1"
    assert policy.evict_victim() == "k2"
    assert policy.evict_victim() == "k3"
    assert policy.evict_victim() is None

def test_lfu_frequency_promotion():
    policy = LfuEvictionPolicy()
    
    policy.on_insert("k1")
    policy.on_insert("k2")
    policy.on_insert("k3")
    
    # Access k2 and k3 to increment their frequency to 2.
    policy.on_access("k2")
    policy.on_access("k3")
    
    # k1 is still at frequency 1. It should be evicted first.
    assert policy.evict_victim() == "k1"
    
    # k2 and k3 are at frequency 2. k2 was accessed first (making it older in bucket 2).
    assert policy.evict_victim() == "k2"
    assert policy.evict_victim() == "k3"
    assert policy.evict_victim() is None

def test_lfu_removal():
    policy = LfuEvictionPolicy()
    
    policy.on_insert("k1")
    policy.on_insert("k2")
    policy.on_insert("k3")
    
    policy.on_access("k1")
    policy.on_access("k2")
    
    # k3 is at frequency 1. Remove it explicitly.
    policy.on_remove("k3")
    
    # k1 and k2 are at frequency 2. k1 was accessed first, so it is the oldest at min_frequency=2.
    assert policy.min_frequency == 2
    assert policy.evict_victim() == "k1"
    assert policy.evict_victim() == "k2"
    assert policy.evict_victim() is None

def test_lfu_empty_behavior():
    policy = LfuEvictionPolicy()
    assert policy.evict_victim() is None
    
    policy.on_access("absent_key") # should not raise error
    policy.on_remove("absent_key") # should not raise error
