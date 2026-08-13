import random
import time
from concurrent.futures import ThreadPoolExecutor

from engine.cache_engine import CacheEngine
from engine.expire.active_expiry import ActiveExpirySweeper
from tests.concurrency.test_concurrent_engine import (
    verify_lru_integrity,
)


def test_concurrent_expiry_race():
    """
    Test passive expiry (via concurrent GETs) and the active sweeper thread
    running simultaneously against overlapping keys.
    Asserts no exceptions, no double-removal races, and correct tracking layouts.
    """
    # Max size 100, LRU policy
    engine = CacheEngine(max_size=100, eviction_policy="lru")
    
    # Pre-populate keys with a mixture of permanent, far-expiring, and near-expiring TTLs
    num_keys = 80
    for i in range(num_keys):
        key = f"key_{i}"
        # 1/3 expire in 0.03 seconds, 1/3 expire in 10 seconds, 1/3 have no TTL
        rand = i % 3
        if rand == 0:
            engine.set(key, f"val_{i}", ttl=0.03)
        elif rand == 1:
            engine.set(key, f"val_{i}", ttl=10.0)
        else:
            engine.set(key, f"val_{i}")
            
    # Start active sweeper with short sweep interval (0.01s) and batch size 20
    sweeper = ActiveExpirySweeper(engine, interval=0.01, batch_size=20)
    sweeper.start()
    
    # Sleep 0.05 seconds to guarantee the 0.03s TTL keys are expired
    time.sleep(0.05)
    
    num_threads = 20
    num_ops_per_thread = 150
    
    def worker(thread_idx):
        random.seed(thread_idx)
        for _ in range(num_ops_per_thread):
            # Target overlapping keys
            key = f"key_{random.randint(0, num_keys - 1)}"
            op = random.choice(["get", "exists", "set"])
            
            if op == "get":
                engine.get(key)
            elif op == "exists":
                engine.exists(key)
            elif op == "set":
                # Writes with very short TTL
                engine.set(key, "new_val", ttl=0.01)

    try:
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker, i) for i in range(num_threads)]
            for fut in futures:
                fut.result()  # Ensure no exceptions were raised
    finally:
        # Stop and join sweeper thread
        sweeper.stop()
        sweeper.join(timeout=1.0)
        
    # Verify the doubly linked list integrity and keys consistency
    verify_lru_integrity(engine)
    
    # Assert that some TTL evictions occurred and were recorded
    assert engine.ttl_evictions > 0, "No TTL evictions occurred during the concurrent run!"
