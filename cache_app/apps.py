import sys
from django.apps import AppConfig

class CacheAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'cache_app'

    def ready(self):
        from django.conf import settings
        from cache_app.singleton import hash_ring, router
        
        # Start active sweeper thread if not in test suite
        if 'test' not in sys.argv and 'pytest' not in sys.modules:
            from cache_app.singleton import active_sweeper
            active_sweeper.start()
            
        # Bootstrap consistent hash ring and router parameters from Django settings
        node_id = getattr(settings, 'SHARD_NODE_ID', 'Node-A')
        cluster_nodes = getattr(settings, 'SHARD_CLUSTER_NODES', {})
        v_nodes = getattr(settings, 'SHARD_VIRTUAL_NODES', 150)
        
        # Clear existing ring structures if any
        hash_ring.ring.clear()
        hash_ring.hash_to_node.clear()
        
        # Populate hashing ring virtual nodes
        for nid in cluster_nodes:
            hash_ring.add_node(nid, v_nodes)
            
        # Update router configuration
        router.self_node_id = node_id
        router.cluster_nodes = cluster_nodes
