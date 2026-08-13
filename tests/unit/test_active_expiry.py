import time

from engine.cache_engine import CacheEngine
from engine.expire.active_expiry import ActiveExpirySweeper


def test_passive_expiration():
    engine = CacheEngine(max_size=10, eviction_policy="lru")
    
    # 1. TTL-less entry never expires
    engine.set("permanent", "val1")
    # 2. TTL entry set to expire in 0.05 seconds
    engine.set("temporary", "val2", ttl=0.05)
    
    assert engine.exists("permanent") is True
    assert engine.exists("temporary") is True
    
    # Sleep to allow key to expire
    time.sleep(0.06)
    
    # Check passive eviction on exists/get
    assert engine.exists("temporary") is False
    assert engine.get("temporary") is None
    assert engine.exists("permanent") is True
    assert engine.get("permanent") == "val1"
    
    # Verify counter
    assert engine.ttl_evictions == 1

def test_active_sweep_batch():
    engine = CacheEngine(max_size=10, eviction_policy="lru")
    
    # Set 4 keys, 2 expiring immediately (ttl=0.001), 2 persistent
    engine.set("k1", "v1", ttl=0.001)
    engine.set("k2", "v2", ttl=0.001)
    engine.set("k3", "v3")
    engine.set("k4", "v4")
    
    sweeper = ActiveExpirySweeper(engine, batch_size=4)
    
    # Sleep to expire k1 & k2
    time.sleep(0.01)
    
    # Sweep batch should process all 4 keys, evict 2 (k1 and k2)
    ratio = sweeper.sweep_batch()
    
    assert ratio == 0.5  # 2 of 4 keys expired
    assert not engine.exists("k1")
    assert not engine.exists("k2")
    assert engine.exists("k3")
    assert engine.exists("k4")
    assert engine.ttl_evictions == 2

def test_adaptive_loop_logic():
    engine = CacheEngine(max_size=10, eviction_policy="lru")
    
    # We want to test if sweeper loops again if > 25% of keys expire.
    # Set 3 keys, all expiring immediately (100% of batch)
    engine.set("k1", "v1", ttl=0.001)
    engine.set("k2", "v2", ttl=0.001)
    engine.set("k3", "v3", ttl=0.001)
    
    sweeper = ActiveExpirySweeper(engine, interval=0.1, batch_size=3)
    
    time.sleep(0.01)
    
    # Running start/stop to let the thread run one loop or manual sweep
    # Let's run sweep_batch once to check ratio
    ratio = sweeper.sweep_batch()
    assert ratio == 1.0  # 3 of 3 expired
