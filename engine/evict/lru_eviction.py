

class LruNode:
    __slots__ = ('key', 'next', 'prev')
    
    def __init__(self, key: str):
        self.key = key
        self.prev = None
        self.next = None

class LruEvictionPolicy:
    """
    Least Recently Used (LRU) eviction strategy.
    
    Not thread-safe on its own — callers must hold CacheEngine's lock before invoking any method here.
    """
    def __init__(self):
        self.node_map = {}
        # Dummy head and tail nodes to simplify list boundaries
        self.head = LruNode("")
        self.tail = LruNode("")
        self.head.next = self.tail
        self.tail.prev = self.head

    def _add_first(self, node: LruNode) -> None:
        """
        Inserts the node right after the head (most recently used).
        """
        node.next = self.head.next
        node.prev = self.head
        self.head.next.prev = node
        self.head.next = node

    def _remove(self, node: LruNode) -> None:
        """
        Removes the node from the list.
        """
        if node.prev is not None and node.next is not None:
            node.prev.next = node.next
            node.next.prev = node.prev

    def _promote(self, node: LruNode) -> None:
        """
        Promotes the node to the head of the list.
        """
        self._remove(node)
        self._add_first(node)

    def on_access(self, key: str) -> None:
        """
        Updates the key's position to mark it as most recently accessed.
        """
        node = self.node_map.get(key)
        if node is not None:
            self._promote(node)

    def on_insert(self, key: str) -> None:
        """
        Adds a new key to the head of the LRU list.
        """
        node = LruNode(key)
        self.node_map[key] = node
        self._add_first(node)

    def on_remove(self, key: str) -> None:
        """
        Explicitly removes a key from tracking.
        """
        node = self.node_map.pop(key, None)
        if node is not None:
            self._remove(node)

    def evict_victim(self) -> str | None:
        """
        Evicts the least recently used key (node right before the dummy tail).
        Returns the key of the evicted victim, or None if the list is empty.
        """
        if self.head.next is self.tail:
            return None
        
        victim_node = self.tail.prev
        self._remove(victim_node)
        self.node_map.pop(victim_node.key, None)
        return victim_node.key
