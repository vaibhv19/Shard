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
        Samples a batch of keys under the engine's lock and purges expired entries.
        Returns the ratio of expired keys in the sample (0.0 to 1.0).
        """
        with self.engine.lock:
            keys = list(self.engine.cache_dict.keys())
            if not keys:
                return 0.0
                
            # Sample up to batch_size keys
            sample_size = min(self.batch_size, len(keys))
            sample_keys = random.sample(keys, sample_size)
            
            expired_count = 0
            for key in sample_keys:
                # _check_expiry_under_lock deletes the entry, notifies eviction, and increments ttl_evictions
                if self.engine._check_expiry_under_lock(key):
                    expired_count += 1
                    
            return expired_count / sample_size
