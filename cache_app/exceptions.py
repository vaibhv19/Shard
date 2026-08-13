import datetime

from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler

from engine.cache_engine import EvictionFailedException


class KeyNotFoundException(Exception):
    """
    Raised when a requested key is absent or has expired.
    """

def custom_exception_handler(exc, context):
    """
    Translates internal engine and DRF validation exceptions into standard
    error response shapes outlined in APIContracts.md.
    """
    response = exception_handler(exc, context)
    
    timestamp = datetime.datetime.now(datetime.UTC).isoformat().replace('+00:00', 'Z')
    
    if isinstance(exc, KeyNotFoundException):
        return Response({
            "status": "error",
            "errorCode": "KEY_NOT_FOUND",
            "message": str(exc) or "Requested key does not exist or has expired.",
            "timestamp": timestamp
        }, status=status.HTTP_404_NOT_FOUND)
        
    if isinstance(exc, EvictionFailedException):
        return Response({
            "status": "error",
            "errorCode": "EVICTION_FAILED",
            "message": str(exc) or "Cache capacity reached and eviction was unable to free memory.",
            "timestamp": timestamp
        }, status=status.HTTP_507_INSUFFICIENT_STORAGE)
        
    if isinstance(exc, ValidationError):
        errors = []
        for field, detail in exc.detail.items():
            if isinstance(detail, list):
                detail_str = ", ".join([str(d) for d in detail])
            else:
                detail_str = str(detail)
            errors.append(f"{field}: {detail_str}")
        message = ", ".join(errors)
        
        return Response({
            "status": "error",
            "errorCode": "VALIDATION_FAILED",
            "message": message,
            "timestamp": timestamp
        }, status=status.HTTP_400_BAD_REQUEST)
        
    if response is not None:
        return Response({
            "status": "error",
            "errorCode": "SERVER_ERROR",
            "message": response.data.get('detail', str(exc)),
            "timestamp": timestamp
        }, status=response.status_code)
        
    return None
