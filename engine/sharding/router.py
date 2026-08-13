import httpx

from engine.sharding.consistent_hash import ConsistentHashRing


class NodeRouter:
    """
    HTTP Proxy router. Hashes cache keys to physical nodes on the ConsistentHashRing
    and proxies calls to remote nodes using an HTTP client with connection pooling.
    """
    def __init__(self, ring: ConsistentHashRing, self_node_id: str, cluster_nodes: dict[str, str]):
        self.ring = ring
        self.self_node_id = self_node_id
        self.cluster_nodes = cluster_nodes  # Dict mapping node_id -> base_url (e.g. "http://127.0.0.1:8000")
        # Instantiate a single Client to enable connection pooling
        self.client = httpx.Client(timeout=5.0)

    def should_proxy(self, key: str) -> bool:
        """
        Returns True if the key hashes to a node other than the current node.
        """
        try:
            target_node = self.ring.get_node(key)
            return target_node != self.self_node_id
        except ValueError:
            # If ring is empty, do not proxy (fallback to local engine)
            return False

    def forward(self, key: str, method: str, path_suffix: str, json_data: dict | None = None) -> httpx.Response:
        """
        Proxies the HTTP request to the resolved target node for the given key.
        """
        target_node = self.ring.get_node(key)
        base_url = self.cluster_nodes.get(target_node)
        if not base_url:
            raise ValueError(f"No configured address for target node: {target_node}")
            
        url = f"{base_url}/api/v1/cache{path_suffix}"
        
        # Proxy request using the pooled httpx client
        response = self.client.request(
            method=method,
            url=url,
            json=json_data,
            headers={"Content-Type": "application/json"}
        )
        return response

    def close(self) -> None:
        """
        Closes the underlying HTTP client.
        """
        self.client.close()
