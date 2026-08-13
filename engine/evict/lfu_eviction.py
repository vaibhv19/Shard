from collections import OrderedDict


class LfuNode:
    __slots__ = ('frequency', 'key')
    
    def __init__(self, key: str, frequency: int = 1):
        self.key = key
        self.frequency = frequency

class LfuEvictionPolicy:
    """
    Least Frequently Used (LFU) eviction strategy.
    
    Not thread-safe on its own — callers must hold CacheEngine's lock before invoking any method here.
    """
    def __init__(self):
        self.node_map = {}  # dict[str, LfuNode]
        self.freq_map = {}  # dict[int, OrderedDict[str, bool]]
        self.min_frequency = 0

    def on_access(self, key: str) -> None:
        """
        Increments the key's access frequency and moves it to the appropriate frequency bucket.
        """
        node = self.node_map.get(key)
        if node is None:
            return
            
        old_freq = node.frequency
        new_freq = old_freq + 1
        node.frequency = new_freq
        
        # Remove key from the old frequency bucket
        if old_freq in self.freq_map:
            self.freq_map[old_freq].pop(key, None)
            if not self.freq_map[old_freq]:
                del self.freq_map[old_freq]
                # If the old frequency bucket is empty and was the min_frequency, update min_frequency
                if self.min_frequency == old_freq:
                    self.min_frequency = new_freq
                    
        # Add key to the new frequency bucket
        if new_freq not in self.freq_map:
            self.freq_map[new_freq] = OrderedDict()
        self.freq_map[new_freq][key] = True

    def on_insert(self, key: str) -> None:
        """
        Inserts a new key, starting with an access frequency of 1.
        """
        node = LfuNode(key, frequency=1)
        self.node_map[key] = node
        
        if 1 not in self.freq_map:
            self.freq_map[1] = OrderedDict()
        self.freq_map[1][key] = True
        
        self.min_frequency = 1

    def on_remove(self, key: str) -> None:
        """
        Explicitly removes a key from tracking.
        """
        node = self.node_map.pop(key, None)
        if node is not None:
            freq = node.frequency
            if freq in self.freq_map:
                self.freq_map[freq].pop(key, None)
                if not self.freq_map[freq]:
                    del self.freq_map[freq]
                    # If this was the min_frequency bucket, update it
                    if self.min_frequency == freq:
                        if self.freq_map:
                            self.min_frequency = min(self.freq_map.keys())
                        else:
                            self.min_frequency = 0

    def evict_victim(self) -> str | None:
        """
        Evicts the oldest key in the min_frequency bucket.
        Returns the key of the evicted victim, or None if the cache is empty.
        """
        if not self.node_map:
            return None
            
        bucket = self.freq_map.get(self.min_frequency)
        if not bucket:
            # Fallback in case of tracking mismatch
            if self.freq_map:
                self.min_frequency = min(self.freq_map.keys())
                bucket = self.freq_map[self.min_frequency]
            else:
                return None
                
        # Evict the oldest item in the minimum frequency bucket (FIFO)
        victim_key, _ = bucket.popitem(last=False)
        self.node_map.pop(victim_key, None)
        
        if not bucket:
            del self.freq_map[self.min_frequency]
            if self.freq_map:
                self.min_frequency = min(self.freq_map.keys())
            else:
                self.min_frequency = 0
                
        return victim_key
