import bisect

import mmh3


class ConsistentHashRing:
    """
    Consistent Hash Ring implementation using Murmur3-32 hashing.
    Supports virtual nodes to ensure uniform key distribution.
    """
    def __init__(self, default_virtual_nodes: int = 150):
        self.default_virtual_nodes = default_virtual_nodes
        self.ring: list[int] = []  # Sorted list of virtual node hash values (int)
        self.hash_to_node: dict[int, str] = {}  # dict[int, str] mapping hash -> node_id

    def add_node(self, node_id: str, virtual_node_count: int | None = None) -> None:
        """
        Hashes virtual node configurations and inserts them into the sorted ring space.
        """
        v_count = virtual_node_count if virtual_node_count is not None else self.default_virtual_nodes
        for i in range(v_count):
            v_node_name = f"{node_id}#{i}"
            # Use unsigned 32-bit hash space
            v_hash = mmh3.hash(v_node_name) & 0xffffffff
            
            # Avoid duplicate hashes
            idx = bisect.bisect_left(self.ring, v_hash)
            if idx < len(self.ring) and self.ring[idx] == v_hash:
                continue
            self.ring.insert(idx, v_hash)
            self.hash_to_node[v_hash] = node_id

    def remove_node(self, node_id: str, virtual_node_count: int | None = None) -> None:
        """
        Removes virtual node hashes for a node from the ring.
        """
        v_count = virtual_node_count if virtual_node_count is not None else self.default_virtual_nodes
        for i in range(v_count):
            v_node_name = f"{node_id}#{i}"
            v_hash = mmh3.hash(v_node_name) & 0xffffffff
            idx = bisect.bisect_left(self.ring, v_hash)
            if idx < len(self.ring) and self.ring[idx] == v_hash:
                self.ring.pop(idx)
                self.hash_to_node.pop(v_hash, None)

    def get_node(self, key: str) -> str:
        """
        Hashes a cache key and retrieves the target physical node ID clockwise.
        """
        if not self.ring:
            raise ValueError("Consistent hash ring is empty. Cannot resolve node.")
            
        key_hash = mmh3.hash(key) & 0xffffffff
        
        # bisect.bisect_right finds the first virtual node clockwise (hash >= key_hash)
        idx = bisect.bisect_right(self.ring, key_hash)
        
        # Wraparound if key_hash is greater than the largest virtual node hash
        if idx == len(self.ring):
            idx = 0
            
        return self.hash_to_node[self.ring[idx]]
