import threading
import time

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from engine.cache_entry import CacheEntry
from engine.evict.strategy import EvictionStrategy


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
        with self.lock:
            if key not in self.cache_dict:
                self.misses += 1
                return None
            if self._check_expiry_under_lock(key):
                self.misses += 1
                return None
                
            entry = self.cache_dict[key]
            entry.last_access_time = time.time()
            entry.access_frequency += 1
            
            # Promote key in the active eviction policy
            self.eviction_strategy.on_access(key)
            self.hits += 1
            return entry.value

    def delete(self, key: str) -> bool:
        """
        Deletes key under the lock and notifies eviction policy.
        """
        with self.lock:
            if key in self.cache_dict:
                # Remove from cache and notify eviction policy
                del self.cache_dict[key]
                self.eviction_strategy.on_remove(key)
                return True
            return False

    def set(self, key: str, value: str, ttl: float | None = None) -> bool:
        """
        Writes key and value to cache under the lock, enforcing capacity constraints and
        performing LRU/LFU promotions.
        Returns True if a new key was inserted, False if an existing key was updated.
        """
        with self.lock:
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
        with self.lock:
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
            return True
        return False
