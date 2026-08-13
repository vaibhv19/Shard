import random
from concurrent.futures import ThreadPoolExecutor

from engine.cache_engine import CacheEngine


def verify_lru_integrity(engine: CacheEngine):
    """
    Performs a deep structural audit of the LRU policy to ensure no cycles, no orphaned nodes,
    and matching node_map size.
    """
    from engine.evict.lru_eviction import LruEvictionPolicy
    strategy = engine.eviction_strategy
    if not isinstance(strategy, LruEvictionPolicy) or engine.policy_name != 'lru':
        return
        
    node_map = strategy.node_map
    head = strategy.head
    tail = strategy.tail
    
    # Traverse forward
    forward_keys = []
    curr = head.next
    visited = set()
    
    while curr is not tail:
        assert curr not in visited, "LRU linked list has a cycle!"
        visited.add(curr)
        forward_keys.append(curr.key)
        
        # Verify backward pointer link integrity
        assert curr.next.prev is curr, f"LRU link broken: node {curr.key}.next.prev is not node itself!"
        assert curr.prev.next is curr, f"LRU link broken: node {curr.key}.prev.next is not node itself!"
        curr = curr.next
        
    assert len(visited) == len(node_map), "LRU traversed nodes count does not match node_map size!"
    
    # Verify cache_dict and node_map have matching keys
    assert set(engine.cache_dict.keys()) == set(node_map.keys()), "cache_dict keys and node_map keys do not match!"
    assert len(engine.cache_dict) <= engine.max_size, f"Cache size {len(engine.cache_dict)} exceeds max capacity {engine.max_size}!"


def verify_lfu_integrity(engine: CacheEngine):
    """
    Performs a deep structural audit of the LFU policy to ensure frequency bucket mapping is correct,
    and min_frequency points to a valid non-empty bucket.
    """
    from engine.evict.lfu_eviction import LfuEvictionPolicy
    strategy = engine.eviction_strategy
    if not isinstance(strategy, LfuEvictionPolicy) or engine.policy_name != 'lfu':
        return
        
    node_map = strategy.node_map
    freq_map = strategy.freq_map
    min_freq = strategy.min_frequency
    
    # Count keys in all frequency buckets
    bucket_keys_count = 0
    all_bucket_keys = set()
    
    for freq, bucket in freq_map.items():
        assert len(bucket) > 0, f"LFU frequency bucket {freq} is empty but still exists in freq_map!"
        bucket_keys_count += len(bucket)
        for key in bucket:
            all_bucket_keys.add(key)
            # Verify node maps to correct frequency
            assert node_map[key].frequency == freq, f"LFU key {key} in bucket {freq} but node has frequency {node_map[key].frequency}!"
            
    assert bucket_keys_count == len(node_map), "LFU total keys in buckets does not match node_map size!"
    assert all_bucket_keys == set(node_map.keys()), "LFU keys in buckets do not match node_map keys!"
    assert set(engine.cache_dict.keys()) == set(node_map.keys()), "cache_dict keys and LFU node_map keys do not match!"
    assert len(engine.cache_dict) <= engine.max_size, f"Cache size {len(engine.cache_dict)} exceeds max capacity {engine.max_size}!"
    
    if node_map:
        assert min_freq in freq_map, f"LFU min_frequency {min_freq} is not present in freq_map!"
        assert len(freq_map[min_freq]) > 0, f"LFU min_frequency bucket {min_freq} is empty!"
    else:
        assert min_freq == 0, f"LFU cache is empty but min_frequency is {min_freq} (expected 0)!"


def run_concurrent_workload(engine: CacheEngine):
    """
    Runs a highly concurrent read, write, and delete workload on overlapping keys.
    """
    num_threads = 50
    num_ops_per_thread = 200
    keys = [f"key_{i}" for i in range(150)]  # 150 keys to cause evictions (capacity is 100)
    
    def worker(thread_idx):
        random.seed(thread_idx)
        for _ in range(num_ops_per_thread):
            op = random.choice(["get", "set", "delete", "exists"])
            key = random.choice(keys)
            
            if op == "get":
                engine.get(key)
            elif op == "set":
                val = f"val_{random.randint(1, 1000)}"
                engine.set(key, val)
            elif op == "delete":
                engine.delete(key)
            elif op == "exists":
                engine.exists(key)

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker, i) for i in range(num_threads)]
        for fut in futures:
            fut.result()  # Raise exceptions if any thread failed


def test_concurrent_lru_correctness():
    # Max size 100 to force frequent evictions
    engine = CacheEngine(max_size=100, eviction_policy="lru")
    
    # Run heavy concurrent workload
    run_concurrent_workload(engine)
    
    # Audit structure
    verify_lru_integrity(engine)


def test_concurrent_lfu_correctness():
    # Max size 100 to force frequent evictions
    engine = CacheEngine(max_size=100, eviction_policy="lfu")
    
    # Run heavy concurrent workload
    run_concurrent_workload(engine)
    
    # Audit structure
    verify_lfu_integrity(engine)
