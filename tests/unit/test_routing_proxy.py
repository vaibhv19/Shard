import httpx
import respx

from engine.sharding.consistent_hash import ConsistentHashRing
from engine.sharding.router import NodeRouter


@respx.mock
def test_router_should_proxy():
    ring = ConsistentHashRing(default_virtual_nodes=5)
    ring.add_node("Node-A")
    ring.add_node("Node-B")
    
    cluster_nodes = {
        "Node-A": "http://127.0.0.1:8000",
        "Node-B": "http://127.0.0.1:8001"
    }
    
    router = NodeRouter(ring, "Node-A", cluster_nodes)
    
    # Find keys mapping to Node-A and Node-B
    key_a = "key_for_a"
    while ring.get_node(key_a) != "Node-A":
        key_a += "a"
        
    key_b = "key_for_b"
    while ring.get_node(key_b) != "Node-B":
        key_b += "b"
        
    assert router.should_proxy(key_a) is False
    assert router.should_proxy(key_b) is True
    
    # Clean up router connection pool
    router.close()

@respx.mock
def test_router_forward_crud():
    ring = ConsistentHashRing(default_virtual_nodes=5)
    ring.add_node("Node-A")
    ring.add_node("Node-B")
    
    cluster_nodes = {
        "Node-A": "http://127.0.0.1:8000",
        "Node-B": "http://127.0.0.1:8001"
    }
    
    router = NodeRouter(ring, "Node-A", cluster_nodes)
    
    # Target Node-B
    key = "target_key"
    while ring.get_node(key) != "Node-B":
        key += "x"
        
    # Mock various CRUD endpoints on Node-B
    post_route = respx.post("http://127.0.0.1:8001/api/v1/cache").mock(
        return_value=httpx.Response(201, json={"status": "success", "key": key})
    )
    get_route = respx.get(f"http://127.0.0.1:8001/api/v1/cache/{key}").mock(
        return_value=httpx.Response(200, json={"key": key, "value": "test_val", "ttl_remaining": -1})
    )
    delete_route = respx.delete(f"http://127.0.0.1:8001/api/v1/cache/{key}").mock(
        return_value=httpx.Response(204)
    )
    
    # Test POST proxying
    res_post = router.forward(key, "POST", "", {"key": key, "value": "test_val"})
    assert post_route.called
    assert res_post.status_code == 201
    assert res_post.json()["key"] == key
    
    # Test GET proxying
    res_get = router.forward(key, "GET", f"/{key}")
    assert get_route.called
    assert res_get.status_code == 200
    assert res_get.json()["value"] == "test_val"
    
    # Test DELETE proxying
    res_del = router.forward(key, "DELETE", f"/{key}")
    assert delete_route.called
    assert res_del.status_code == 204
    
    router.close()
