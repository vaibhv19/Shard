import random
import threading

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class ActiveExpirySweeper(threading.Thread):
    """
    A background daemon thread that periodically sweeps the CacheEngine dictionary
    to actively reclaim memory from expired keys.
    """
    def __init__(self, cache_engine, interval: float | None = None, batch_size: int | None = None):
        super().__init__(daemon=True, name="ActiveExpirySweeper")
        self.engine = cache_engine
        
        # Load configuration with fallbacks
        try:
            self.interval = interval if interval is not None else getattr(settings, 'SHARD_ACTIVE_EXPIRY_INTERVAL', 5.0)
            self.batch_size = batch_size if batch_size is not None else getattr(settings, 'SHARD_ACTIVE_EXPIRY_BATCH_SIZE', 20)
        except (ImproperlyConfigured, RuntimeError, AttributeError):
            self.interval = interval if interval is not None else 5.0
            self.batch_size = batch_size if batch_size is not None else 20
            
        self._stop_event = threading.Event()

    def stop(self) -> None:
        """
        Signals the background loop to terminate.
        """
        self._stop_event.set()

    def run(self) -> None:
        """
        Background sweep execution loop.
        """
        while not self._stop_event.is_set():
            expired_ratio = self.sweep_batch()
            
            # Adaptive loop: if more than 25% of the batch keys were expired, sweep again immediately
            if expired_ratio > 0.25:
                continue
                
            # Otherwise, wait for the configured interval or stop signal
            self._stop_event.wait(self.interval)

    def sweep_batch(self) -> float:
        """
        Samples a batch of keys under the engine's lock briefly, filters expired candidates
        outside the lock, and purges them under the lock with verification checks.
        Returns the ratio of expired keys in the sample (0.0 to 1.0).
        """
        import time

        from engine.metrics.collector import metrics_collector

        # 1. Sample keys and expiries under the lock briefly
        candidates = []
        with self.engine.lock:
            keys = list(self.engine.cache_dict.keys())
            if not keys:
                return 0.0
                
            sample_size = min(self.batch_size, len(keys))
            sample_keys = random.sample(keys, sample_size)
            
            for key in sample_keys:
                entry = self.engine.cache_dict.get(key)
                if entry is not None:
                    candidates.append((key, entry.expiry_time))
                    
        if not candidates:
            return 0.0
            
        # 2. Filter expired candidates outside the lock
        now = time.time()
        expired_keys = [key for key, expiry_time in candidates if now > expiry_time]
        
        if not expired_keys:
            return 0.0
            
        # 3. Re-acquire lock to perform actual mutations with verification checks
        expired_count = 0
        with self.engine.lock:
            for key in expired_keys:
                # Double check to prevent check-then-act races:
                # The key must still be in cache_dict, and its expiry_time must still be in the past.
                entry = self.engine.cache_dict.get(key)
                if entry is not None and time.time() > entry.expiry_time:
                    del self.engine.cache_dict[key]
                    self.engine.eviction_strategy.on_remove(key)
                    self.engine.ttl_evictions += 1
                    metrics_collector.record_eviction("ttl")
                    expired_count += 1
                    
        return expired_count / len(candidates)
