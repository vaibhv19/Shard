import cache_app
from cache_app.apps import CacheAppConfig
from cache_app.singleton import hash_ring, router


def test_bootstrap_populates_ring(settings):
    # Setup mock configuration in settings
    settings.SHARD_NODE_ID = "Node-Test"
    settings.SHARD_VIRTUAL_NODES = 10
    settings.SHARD_CLUSTER_NODES = {
        "Node-Test": "http://127.0.0.1:9000",
        "Node-Other": "http://127.0.0.1:9001"
    }
    
    # Run the AppConfig.ready() bootstrap sequence
    config = CacheAppConfig('cache_app', cache_app)
    config.ready()
    
    # Assert hash_ring has been populated (10 virtual nodes per physical node * 2 nodes = 20 hashes)
    assert len(hash_ring.ring) == 20
    assert hash_ring.get_node("some_key") in ["Node-Test", "Node-Other"]
    
    # Assert router has been configured
    assert router.self_node_id == "Node-Test"
    assert router.cluster_nodes == settings.SHARD_CLUSTER_NODES
