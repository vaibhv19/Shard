import queue
import threading
import time

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from engine.cache_entry import CacheEntry
from engine.evict.strategy import EvictionStrategy
from engine.mock_database import MockDatabase
from engine.metrics.collector import metrics_collector


class EvictionFailedException(Exception):
    """
    Raised when the cache is full and the active eviction strategy fails to free up space.
    """

class CacheEngine:
    """
    Coordinates the standard Python dict cache store and eviction strategies under a global lock.
    """
    def __init__(self, max_size: int | None = None, eviction_policy: str | None = None):
        self.lock = threading.Lock()
        self.cache_dict: dict[str, CacheEntry] = {}
        self.eviction_strategy: EvictionStrategy
        
        # Load configuration with fallback to Django settings or default values
        try:
            self.max_size = max_size if max_size is not None else getattr(settings, 'SHARD_CACHE_MAX_SIZE', 1000)
            policy = eviction_policy if eviction_policy is not None else getattr(settings, 'SHARD_EVICTION_POLICY', 'lru')
        except (ImproperlyConfigured, RuntimeError, AttributeError):
            # Fallbacks when django settings are not configured (e.g. raw unit tests)
            self.max_size = max_size if max_size is not None else 1000
            policy = eviction_policy if eviction_policy is not None else 'lru'
            
        self.policy_name = policy.lower()
        
        # Operational counters
        self.hits = 0
        self.misses = 0
        self.policy_evictions = 0
        self.ttl_evictions = 0
        
        # Initialize selected eviction strategy
        if self.policy_name == 'lru':
            from engine.evict.lru_eviction import LruEvictionPolicy
            self.eviction_strategy = LruEvictionPolicy()
        elif self.policy_name == 'lfu':
            from engine.evict.lfu_eviction import LfuEvictionPolicy
            self.eviction_strategy = LfuEvictionPolicy()
        else:
            raise ValueError(f"Unknown eviction policy: {policy}")

        # Initialize mock database and write-back queue/thread
        self.db = MockDatabase()
        self.write_back_queue: queue.Queue = queue.Queue()
        self.write_back_thread = threading.Thread(target=self._write_back_worker, daemon=True)
        self.write_back_thread.start()

    def exists(self, key: str) -> bool:
        """
        Checks presence under the lock without triggering LRU/LFU promotion.
        """
        with self.lock:
            if key not in self.cache_dict:
                return False
            return not self._check_expiry_under_lock(key)

    def get(self, key: str) -> str | None:
        """
        Retrieves cache value under the lock and triggers eviction policy promotion.
        """
        start_time = time.perf_counter()
        with self.lock:
            try:
                if key not in self.cache_dict:
                    self.misses += 1
                    metrics_collector.record_miss()
                    return None
                if self._check_expiry_under_lock(key):
                    self.misses += 1
                    metrics_collector.record_miss()
                    return None
                    
                entry = self.cache_dict[key]
                entry.last_access_time = time.time()
                entry.access_frequency += 1
                
                # Promote key in the active eviction policy
                self.eviction_strategy.on_access(key)
                self.hits += 1
                metrics_collector.record_hit(self.policy_name)
                return entry.value
            finally:
                metrics_collector.set_keys_count(len(self.cache_dict))
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                metrics_collector.record_latency("GET", duration_ms)

    def delete(self, key: str) -> bool:
        """
        Deletes key under the lock and notifies eviction policy.
        """
        start_time = time.perf_counter()
        with self.lock:
            try:
                if key in self.cache_dict:
                    # Remove from cache and notify eviction policy
                    del self.cache_dict[key]
                    self.eviction_strategy.on_remove(key)
                    return True
                return False
            finally:
                metrics_collector.set_keys_count(len(self.cache_dict))
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                metrics_collector.record_latency("DELETE", duration_ms)

    def set(self, key: str, value: str, ttl: float | None = None) -> bool:
        """
        Inserts or updates a key in the cache.
        """
        start_time = time.perf_counter()
        with self.lock:
            try:
                return self._set_under_lock(key, value, ttl)
            finally:
                metrics_collector.set_keys_count(len(self.cache_dict))
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                metrics_collector.record_latency("SET", duration_ms)

    def _set_under_lock(self, key: str, value: str, ttl: float | None = None) -> bool:
        expiry_time = time.time() + ttl if ttl is not None else float('inf')
        
        # Passive expiration check on write
        if key in self.cache_dict and self._check_expiry_under_lock(key):
            # The key was expired and deleted; it is now a new insertion
            pass
            
        is_new = key not in self.cache_dict
        
        if is_new:
            # Enforce capacity constraints
            if len(self.cache_dict) >= self.max_size:
                victim = self.eviction_strategy.evict_victim()
                if victim is None or victim not in self.cache_dict:
                    raise EvictionFailedException("Cache capacity reached and eviction was unable to free memory.")
                del self.cache_dict[victim]
                self.policy_evictions += 1
                metrics_collector.record_eviction("policy")
            
            # Insert entry
            entry = CacheEntry(
                value=value,
                created_time=time.time(),
                expiry_time=expiry_time,
                last_access_time=time.time(),
                access_frequency=1
            )
            self.cache_dict[key] = entry
            self.eviction_strategy.on_insert(key)
        else:
            # Update existing entry
            entry = self.cache_dict[key]
            entry.value = value
            entry.expiry_time = expiry_time
            entry.last_access_time = time.time()
            entry.access_frequency += 1
            self.eviction_strategy.on_access(key)
            
        return is_new

    def write_through(self, key: str, value: str, ttl: float | None = None) -> bool:
        """
        Writes to the local cache and then synchronously blocks until the mock database write completes.
        """
        start_time = time.perf_counter()
        with self.lock:
            try:
                is_new = self._set_under_lock(key, value, ttl)
                self.db.set(key, value)
                return is_new
            finally:
                metrics_collector.set_keys_count(len(self.cache_dict))
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                metrics_collector.record_latency("SET", duration_ms)

    def write_back(self, key: str, value: str, ttl: float | None = None) -> bool:
        """
        Writes to the local cache, appends a write event to the queue, and returns immediately.
        """
        start_time = time.perf_counter()
        with self.lock:
            try:
                is_new = self._set_under_lock(key, value, ttl)
                self.write_back_queue.put((key, value))
                return is_new
            finally:
                metrics_collector.set_keys_count(len(self.cache_dict))
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                metrics_collector.record_latency("SET", duration_ms)

    def _write_back_worker(self) -> None:
        """
        Asynchronously drains the write-back queue and updates the mock database.
        """
        while True:
            try:
                key, value = self.write_back_queue.get()
                self.db.set(key, value)
                self.write_back_queue.task_done()
            except Exception:
                # Silently catch database write failures (e.g. key == "simulate_db_failure") to keep thread alive
                pass

    def ttl(self, key: str) -> float | None:
        """
        Returns remaining TTL for a key.
        """
        with self.lock:
            if key not in self.cache_dict:
                return None
            if self._check_expiry_under_lock(key):
                return None
            entry = self.cache_dict[key]
            if entry.expiry_time == float('inf'):
                return -1.0
            return max(0.0, entry.expiry_time - time.time())

    def expire(self, key: str, ttl: float) -> bool:
        """
        Updates the expiry time for a key.
        """
        with self.lock:
            if key not in self.cache_dict:
                return False
            if self._check_expiry_under_lock(key):
                return False
            entry = self.cache_dict[key]
            entry.expiry_time = time.time() + ttl
            return True

    def invalidate_by_pattern(self, pattern: str) -> int:
        """
        Invalidates keys matching a wildcard pattern (e.g., 'user:*').
        Supports '*' for full cache flush.
        Runs under the engine's global lock.
        """
        import fnmatch
        start_time = time.perf_counter()
        with self.lock:
            try:
                keys_to_remove = []
                
                # Prune expired keys first and find matches
                for key in list(self.cache_dict.keys()):
                    self._check_expiry_under_lock(key)
                    if key in self.cache_dict and fnmatch.fnmatchcase(key, pattern):
                        keys_to_remove.append(key)
                        
                # Remove keys
                for key in keys_to_remove:
                    del self.cache_dict[key]
                    self.eviction_strategy.on_remove(key)
                    
                return len(keys_to_remove)
            finally:
                metrics_collector.set_keys_count(len(self.cache_dict))
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                metrics_collector.record_latency("INVALIDATE", duration_ms)

    def _check_expiry_under_lock(self, key: str) -> bool:
        """
        Checks if a key is expired. If expired, removes it from cache and eviction policy.
        Must be called under the lock.
        Returns True if the key was expired and deleted, False otherwise.
        """
        entry = self.cache_dict.get(key)
        if entry is not None and time.time() > entry.expiry_time:
            del self.cache_dict[key]
            self.eviction_strategy.on_remove(key)
            self.ttl_evictions += 1
            metrics_collector.record_eviction("ttl")
            return True
        return False
