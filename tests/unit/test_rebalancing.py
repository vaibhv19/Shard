from engine.sharding.consistent_hash import ConsistentHashRing


def test_consistent_hash_rebalancing_minimalism():
    """
    Verifies that when a node is added to a ring of N nodes,
    no more than approximately 1/(N+1) of the keys migrate to the new node.
    """
    N = 3
    nodes = [f"Node-{i}" for i in range(N)]
    
    # 1. Initialize ring with N nodes (150 virtual nodes each)
    ring = ConsistentHashRing(default_virtual_nodes=150)
    for node in nodes:
        ring.add_node(node)
        
    # 2. Map 50,000 keys to their initial target nodes
    total_keys = 50000
    initial_mappings = {}
    for i in range(total_keys):
        key = f"key_{i}"
        initial_mappings[key] = ring.get_node(key)
        
    # 3. Add a new node (Node-New) to the ring (making it N + 1 nodes)
    new_node = "Node-New"
    ring.add_node(new_node)
    
    # 4. Re-map keys and measure migration
    migrated_keys = 0
    new_node_keys = 0
    
    for i in range(total_keys):
        key = f"key_{i}"
        new_node_mapped = ring.get_node(key)
        if new_node_mapped != initial_mappings[key]:
            migrated_keys += 1
            # The migrated keys MUST have migrated to Node-New (consistent hashing invariant)
            assert new_node_mapped == new_node
            new_node_keys += 1
            
    migration_rate = migrated_keys / total_keys
    theoretical_limit = 1 / (N + 1)
    
    print(f"Total keys: {total_keys}")
    print(f"Migrated keys: {migrated_keys}")
    print(f"Actual migration rate: {migration_rate:.4f}")
    print(f"Theoretical 1/(N+1) limit: {theoretical_limit:.4f}")
    
    # Assert that the migration rate is close to 1/(N+1) with a small tolerance (e.g. + 5% for statistical variance)
    assert migration_rate <= theoretical_limit + 0.05, f"Migration rate {migration_rate:.4f} exceeded theoretical bound {theoretical_limit + 0.05:.4f}!"
