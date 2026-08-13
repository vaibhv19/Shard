import datetime

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from cache_app.exceptions import KeyNotFoundException
from cache_app.serializers import CacheEntrySerializer, ExpireSerializer
from cache_app.singleton import cache_engine


class CacheView(APIView):
    """
    Handles GET /api/v1/cache (not requested/defined, but we keep strictly to defined endpoints)
    and POST /api/v1/cache to insert or update keys.
    """
    def post(self, request):
        serializer = CacheEntrySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        key = serializer.validated_data['key']
        value = serializer.validated_data['value']
        ttl = serializer.validated_data.get('ttl')
        
        # set returns True if a new key was inserted, False if updated
        is_inserted = cache_engine.set(key, value, ttl)
        
        # Retrieve the exact expiry timestamp to return in response
        with cache_engine.lock:
            entry = cache_engine.cache_dict.get(key)
            if entry is not None and entry.expiry_time != float('inf'):
                expiry_dt = datetime.datetime.fromtimestamp(entry.expiry_time, tz=datetime.UTC)
                # ISO format ending in 'Z'
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
    """
    def get(self, request, key):
        val = cache_engine.get(key)
        if val is None:
            raise KeyNotFoundException("Requested key does not exist or has expired.")
            
        ttl_rem = cache_engine.ttl(key)
        if ttl_rem is None:
            # Race condition check (expired between GET and TTL check)
            raise KeyNotFoundException("Requested key does not exist or has expired.")
            
        return Response({
            "key": key,
            "value": val,
            "ttl_remaining": int(ttl_rem) if ttl_rem != -1.0 else -1
        }, status=status.HTTP_200_OK)

    def delete(self, request, key):
        success = cache_engine.delete(key)
        if not success:
            raise KeyNotFoundException("Cannot delete key: key does not exist.")
        return Response(status=status.HTTP_204_NO_CONTENT)


class CacheExistsView(APIView):
    """
    Handles GET /api/v1/cache/{key}/exists.
    """
    def get(self, request, key):
        exists = cache_engine.exists(key)
        return Response({
            "key": key,
            "exists": exists
        }, status=status.HTTP_200_OK)


class CacheExpireView(APIView):
    """
    Handles POST /api/v1/cache/{key}/expire.
    """
    def post(self, request, key):
        serializer = ExpireSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ttl = serializer.validated_data['ttl']
        
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
    """
    def get(self, request, key):
        ttl_rem = cache_engine.ttl(key)
        if ttl_rem is None:
            raise KeyNotFoundException("Requested key does not exist or has expired.")
            
        return Response({
            "key": key,
            "ttl_remaining": int(ttl_rem) if ttl_rem != -1.0 else -1
        }, status=status.HTTP_200_OK)
