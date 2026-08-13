from rest_framework import serializers


class CacheEntrySerializer(serializers.Serializer):
    key = serializers.CharField(
        max_length=250, 
        allow_blank=False, 
        trim_whitespace=False,
        error_messages={
            'blank': 'Key must not be blank.',
            'max_length': 'Key must not exceed 250 characters.'
        }
    )
    value = serializers.CharField(
        max_length=1048576, 
        allow_null=False, 
        allow_blank=True,
        error_messages={
            'null': 'Value must not be null.',
            'max_length': 'Value must not exceed 1MB (1,048,576 characters).'
        }
    )
    ttl = serializers.IntegerField(
        required=False, 
        min_value=1,
        error_messages={
            'min_value': 'TTL must be a positive integer (minimum 1 second).'
        }
    )

class ExpireSerializer(serializers.Serializer):
    ttl = serializers.IntegerField(
        required=True, 
        min_value=1,
        error_messages={
            'min_value': 'TTL must be a positive integer (minimum 1 second).'
        }
    )

class InvalidateSerializer(serializers.Serializer):
    pattern = serializers.CharField(
        required=True,
        allow_blank=False,
        max_length=250,
        error_messages={
            'blank': 'Pattern must not be blank.',
            'required': 'Pattern is required.',
            'max_length': 'Pattern must not exceed 250 characters.'
        }
    )
