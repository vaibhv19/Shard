import datetime
import time

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from cache_app.exceptions import KeyNotFoundException
from cache_app.serializers import CacheEntrySerializer, ExpireSerializer, InvalidateSerializer
from cache_app.singleton import cache_engine, router

BOOT_TIME = time.time()

class CacheView(APIView):
    """
    Handles POST /api/v1/cache to insert or update keys.
    Proxies request if key hashes to a remote node.
    """
    def post(self, request):
        serializer = CacheEntrySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        key = serializer.validated_data['key']
        value = serializer.validated_data['value']
        ttl = serializer.validated_data.get('ttl')
        
        # Proxy check
        if router.should_proxy(key):
            res = router.forward(key, "POST", "", request.data)
            return Response(res.json(), status=res.status_code)
            
        # Local execution
        is_inserted = cache_engine.set(key, value, ttl)
        
        # Retrieve the exact expiry timestamp to return in response
        with cache_engine.lock:
            entry = cache_engine.cache_dict.get(key)
            if entry is not None and entry.expiry_time != float('inf'):
                expiry_dt = datetime.datetime.fromtimestamp(entry.expiry_time, tz=datetime.UTC)
                expiry_str = expiry_dt.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
            else:
                expiry_str = None
                
        if is_inserted:
            return Response({
                "status": "success",
                "message": "Key created successfully",
                "key": key,
                "expiry": expiry_str
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                "status": "success",
                "message": "Key updated successfully",
                "key": key,
                "expiry": expiry_str
            }, status=status.HTTP_200_OK)


class CacheDetailView(APIView):
    """
    Handles GET /api/v1/cache/{key} and DELETE /api/v1/cache/{key}.
    Proxies request if key hashes to a remote node.
    """
    def get(self, request, key):
        if router.should_proxy(key):
            res = router.forward(key, "GET", f"/{key}")
            return Response(res.json(), status=res.status_code)
            
        val = cache_engine.get(key)
        if val is None:
            raise KeyNotFoundException("Requested key does not exist or has expired.")
            
        ttl_rem = cache_engine.ttl(key)
        if ttl_rem is None:
            raise KeyNotFoundException("Requested key does not exist or has expired.")
            
        return Response({
            "key": key,
            "value": val,
            "ttl_remaining": int(ttl_rem) if ttl_rem != -1.0 else -1
        }, status=status.HTTP_200_OK)

    def delete(self, request, key):
        if router.should_proxy(key):
            res = router.forward(key, "DELETE", f"/{key}")
            data = res.json() if res.status_code != 204 else None
            return Response(data, status=res.status_code)
            
        success = cache_engine.delete(key)
        if not success:
            raise KeyNotFoundException("Cannot delete key: key does not exist.")
        return Response(status=status.HTTP_204_NO_CONTENT)


class CacheExistsView(APIView):
    """
    Handles GET /api/v1/cache/{key}/exists.
    Proxies request if key hashes to a remote node.
    """
    def get(self, request, key):
        if router.should_proxy(key):
            res = router.forward(key, "GET", f"/{key}/exists")
            return Response(res.json(), status=res.status_code)
            
        exists = cache_engine.exists(key)
        return Response({
            "key": key,
            "exists": exists
        }, status=status.HTTP_200_OK)


class CacheExpireView(APIView):
    """
    Handles POST /api/v1/cache/{key}/expire.
    Proxies request if key hashes to a remote node.
    """
    def post(self, request, key):
        serializer = ExpireSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ttl = serializer.validated_data['ttl']
        
        if router.should_proxy(key):
            res = router.forward(key, "POST", f"/{key}/expire", request.data)
            return Response(res.json(), status=res.status_code)
            
        success = cache_engine.expire(key, ttl)
        if not success:
            raise KeyNotFoundException("Requested key does not exist or has expired.")
            
        return Response({
            "key": key,
            "ttl_updated": ttl
        }, status=status.HTTP_200_OK)


class CacheTtlView(APIView):
    """
    Handles GET /api/v1/cache/{key}/ttl.
    Proxies request if key hashes to a remote node.
    """
    def get(self, request, key):
        if router.should_proxy(key):
            res = router.forward(key, "GET", f"/{key}/ttl")
            return Response(res.json(), status=res.status_code)
            
        ttl_rem = cache_engine.ttl(key)
        if ttl_rem is None:
            raise KeyNotFoundException("Requested key does not exist or has expired.")
            
        return Response({
            "key": key,
            "ttl_remaining": int(ttl_rem) if ttl_rem != -1.0 else -1
        }, status=status.HTTP_200_OK)


class CacheClusterHealthView(APIView):
    """
    Handles GET /api/v1/cluster/health.
    """
    def get(self, request):
        node_id = getattr(settings, 'SHARD_NODE_ID', 'Node-A')
        uptime = int(time.time() - BOOT_TIME)
        with cache_engine.lock:
            active_keys = len(cache_engine.cache_dict)
            capacity = cache_engine.max_size
            
        return Response({
            "nodeId": node_id,
            "status": "healthy",
            "activeKeys": active_keys,
            "capacity": capacity,
            "uptime_seconds": uptime
        }, status=status.HTTP_200_OK)


class CacheClusterRingView(APIView):
    """
    Handles GET /api/v1/cluster/ring.
    """
    def get(self, request):
        node_list = []
        for node_id, base_url in router.cluster_nodes.items():
            node_list.append({
                "nodeId": node_id,
                "address": base_url,
                "status": "healthy"  # Static health status for config output
            })
            
        v_nodes = getattr(settings, 'SHARD_VIRTUAL_NODES', 150)
        return Response({
            "hashFunction": "Murmur3_32",
            "virtualNodesPerPhysicalNode": v_nodes,
            "nodes": node_list
        }, status=status.HTTP_200_OK)


class CacheInvalidateView(APIView):
    """
    Handles POST /api/v1/cache/invalidate.
    Invalidates keys matching a wildcard pattern (e.g. 'user:*').
    Broadcasts the invalidation to all nodes in the cluster.
    """
    def post(self, request):
        serializer = InvalidateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        pattern = serializer.validated_data['pattern']
        
        # Check if this is an internal broadcast request
        is_broadcast = request.headers.get('X-Shard-Broadcast', 'false').lower() == 'true'
        
        # Invalidate locally
        local_count = cache_engine.invalidate_by_pattern(pattern)
        total_invalidated = local_count
        
        # If not a broadcast, propagate to all other nodes in the cluster
        if not is_broadcast:
            for node_id, base_url in router.cluster_nodes.items():
                if node_id == router.self_node_id:
                    continue
                try:
                    url = f"{base_url}/api/v1/cache/invalidate"
                    res = router.client.post(
                        url,
                        json={"pattern": pattern},
                        headers={"X-Shard-Broadcast": "true", "Content-Type": "application/json"},
                        timeout=2.0
                    )
                    if res.status_code == 200:
                        total_invalidated += res.json().get("invalidatedKeysCount", 0)
                except Exception as e:
                    # Log or print and recover gracefully if node is unreachable
                    print(f"Failed to broadcast invalidation to node {node_id}: {e}")
                    
        return Response({
            "status": "success",
            "invalidatedKeysCount": total_invalidated
        }, status=status.HTTP_200_OK)
