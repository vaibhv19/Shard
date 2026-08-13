from engine.evict.lru_eviction import LruEvictionPolicy


def test_lru_basic_eviction():
    policy = LruEvictionPolicy()
    
    # Insert 3 keys
    policy.on_insert("k1")
    policy.on_insert("k2")
    policy.on_insert("k3")
    
    # k3 is most recent (head), k1 is least recent (tail)
    # Evicting should yield k1
    assert policy.evict_victim() == "k1"
    
    # k2 is now tail.
    assert policy.evict_victim() == "k2"
    assert policy.evict_victim() == "k3"
    assert policy.evict_victim() is None

def test_lru_promotion():
    policy = LruEvictionPolicy()
    
    policy.on_insert("k1")
    policy.on_insert("k2")
    policy.on_insert("k3")
    
    # Access k1, making it most recent.
    # Order should now be: k1 (head) -> k3 -> k2 (tail)
    policy.on_access("k1")
    
    assert policy.evict_victim() == "k2"
    assert policy.evict_victim() == "k3"
    assert policy.evict_victim() == "k1"
    assert policy.evict_victim() is None

def test_lru_removal():
    policy = LruEvictionPolicy()
    
    policy.on_insert("k1")
    policy.on_insert("k2")
    policy.on_insert("k3")
    
    # Remove k2. Order should be: k3 -> k1 (tail)
    policy.on_remove("k2")
    
    assert policy.evict_victim() == "k1"
    assert policy.evict_victim() == "k3"
    assert policy.evict_victim() is None

def test_lru_empty_behavior():
    policy = LruEvictionPolicy()
    assert policy.evict_victim() is None
    
    policy.on_access("absent_key") # should not raise error
    policy.on_remove("absent_key") # should not raise error
