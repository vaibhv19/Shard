from engine.sharding.consistent_hash import ConsistentHashRing


def test_hashing_ring_determinism():
    ring = ConsistentHashRing()
    ring.add_node("Node-A")
    ring.add_node("Node-B")
    ring.add_node("Node-C")
    
    # Same key should always resolve to the same node
    for i in range(100):
        key = f"user:session:{i}"
        node1 = ring.get_node(key)
        node2 = ring.get_node(key)
        assert node1 == node2

def test_hashing_ring_wraparound():
    ring = ConsistentHashRing(default_virtual_nodes=1)
    # Clear and manually add one node with a low hash value, and one with a high hash value
    # We want to force key hashes that exceed all node hashes, to verify wraparound
    ring.add_node("Node-Low", virtual_node_count=1)
    
    # Ensure there is at least one node
    assert len(ring.ring) == 1
    
    # A key should always resolve to the single node regardless of hash value
    assert ring.get_node("key_high_hash_value") == "Node-Low"
    assert ring.get_node("key_low_hash_value") == "Node-Low"

def test_hashing_ring_uniformity():
    # Setup 3 nodes, 150 virtual nodes each
    ring = ConsistentHashRing(default_virtual_nodes=150)
    nodes = ["Node-A", "Node-B", "Node-C"]
    for node in nodes:
        ring.add_node(node)
        
    # Allocate 100,000 keys and measure counts per node
    counts = {node: 0 for node in nodes}
    total_keys = 100000
    
    for i in range(total_keys):
        key = f"key_{i}"
        node = ring.get_node(key)
        counts[node] += 1
        
    # Expected keys per node: 100000 / 3 = 33333.33
    expected_mean = total_keys / len(nodes)
    
    # Calculate max relative deviation: max(|count - mean| / mean)
    # The requirement is that node allocation variance < 15% (i.e. < 0.15)
    max_deviation = 0.0
    for node, count in counts.items():
        deviation = abs(count - expected_mean) / expected_mean
        max_deviation = max(max_deviation, deviation)
        print(f"{node}: count={count}, deviation={deviation:.4f}")
        
    assert max_deviation < 0.15, f"Hashing uniformity exceeded 15%! Max deviation was {max_deviation:.4f}"

def test_ring_remove_node():
    ring = ConsistentHashRing()
    ring.add_node("Node-A")
    ring.add_node("Node-B")
    
    # Check that keys map to both nodes
    nodes_seen = set()
    for i in range(200):
        nodes_seen.add(ring.get_node(f"k{i}"))
    assert len(nodes_seen) == 2
    
    # Remove Node-B and check all keys map to Node-A
    ring.remove_node("Node-B")
    nodes_seen_after = set()
    for i in range(200):
        nodes_seen_after.add(ring.get_node(f"k{i}"))
    assert len(nodes_seen_after) == 1
    assert "Node-A" in nodes_seen_after
