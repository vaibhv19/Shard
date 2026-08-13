import pytest
from rest_framework import status
from rest_framework.test import APIClient

import cache_app
from cache_app.apps import CacheAppConfig


@pytest.fixture(autouse=True)
def setup_cluster_settings(settings):
    settings.SHARD_NODE_ID = "Node-A"
    settings.SHARD_VIRTUAL_NODES = 150
    settings.SHARD_CLUSTER_NODES = {
        "Node-A": "http://127.0.0.1:8000",
        "Node-B": "http://127.0.0.1:8001"
    }
    config = CacheAppConfig('cache_app', cache_app)
    config.ready()

def test_cluster_health_endpoint():
    client = APIClient()
    response = client.get("/api/v1/cluster/health")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["nodeId"] == "Node-A"
    assert response.data["status"] == "healthy"
    assert "activeKeys" in response.data
    assert "capacity" in response.data
    assert response.data["uptime_seconds"] >= 0

def test_cluster_ring_endpoint():
    client = APIClient()
    response = client.get("/api/v1/cluster/ring")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["hashFunction"] == "Murmur3_32"
    assert response.data["virtualNodesPerPhysicalNode"] == 150
    assert len(response.data["nodes"]) == 2
    
    # Check node details
    nodes = response.data["nodes"]
    node_ids = [n["nodeId"] for n in nodes]
    assert "Node-A" in node_ids
    assert "Node-B" in node_ids
    
    # Check address and status fields are present
    for node in nodes:
        assert "address" in node
        assert node["status"] == "healthy"
