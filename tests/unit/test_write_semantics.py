import time

import pytest

from engine.cache_engine import CacheEngine


def test_write_through_success():
    engine = CacheEngine(max_size=10)
    engine.db.clear()
    
    # Write through
    is_new = engine.write_through("key_wt", "val_wt", ttl=300)
    assert is_new is True
    
    # Assert written to both cache and database
    assert engine.get("key_wt") == "val_wt"
    assert engine.db.get("key_wt") == "val_wt"

def test_write_through_failure_propagation():
    engine = CacheEngine(max_size=10)
    engine.db.clear()
    
    # A failure in the database write should propagate to the caller
    with pytest.raises(RuntimeError) as exc_info:
        engine.write_through("simulate_db_failure", "val")
    assert "Database write error" in str(exc_info.value)
    
    # Verify that the value was still written to cache (since cache write is done first)
    assert engine.get("simulate_db_failure") == "val"

def test_write_back_success():
    engine = CacheEngine(max_size=10)
    engine.db.clear()
    
    # Write back returns immediately
    is_new = engine.write_back("key_wb", "val_wb")
    assert is_new is True
    
    # Cache has it immediately
    assert engine.get("key_wb") == "val_wb"
    
    # Database might not have it immediately (asynchronous write)
    # Wait for the background worker thread to process the queue
    for _ in range(20):
        if engine.db.get("key_wb") == "val_wb":
            break
        time.sleep(0.05)
        
    assert engine.db.get("key_wb") == "val_wb"

def test_write_back_high_concurrency():
    import concurrent.futures
    engine = CacheEngine(max_size=1000)
    engine.db.clear()
    
    num_writes = 500
    
    # Concurrently write back keys
    def perform_write(i):
        engine.write_back(f"con_key_{i}", f"val_{i}")
        
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        executor.map(perform_write, range(num_writes))
        
    # All keys should be present in the cache immediately
    for i in range(num_writes):
        assert engine.get(f"con_key_{i}") == f"val_{i}"
        
    # Wait for background queue to drain completely
    for _ in range(50):
        if len(engine.db._db) == num_writes:
            break
        time.sleep(0.1)
        
    # Verify all records have eventually landed in the mock database
    assert len(engine.db._db) == num_writes
    for i in range(num_writes):
        assert engine.db.get(f"con_key_{i}") == f"val_{i}"
