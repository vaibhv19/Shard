from typing import Protocol


class EvictionStrategy(Protocol):
    """
    Protocol defining the eviction strategy interface.
    All eviction strategies (LRU, LFU, etc.) must implement this interface.
    """
    def on_access(self, key: str) -> None:
        """
        Called when a key is read or updated in the cache.
        """
        ...

    def on_insert(self, key: str) -> None:
        """
        Called when a new key is inserted into the cache.
        """
        ...

    def on_remove(self, key: str) -> None:
        """
        Called when a key is explicitly deleted or expired.
        """
        ...

    def evict_victim(self) -> str | None:
        """
        Picks and returns the key of the victim item to evict based on the policy,
        and removes it from internal eviction tracking structures.
        Returns None if the cache is empty.
        """
        ...
