import time
from dataclasses import dataclass, field


@dataclass(slots=True)
class CacheEntry:
    value: str
    created_time: float = field(default_factory=time.time)
    expiry_time: float = float('inf')
    last_access_time: float = field(default_factory=time.time)
    access_frequency: int = 1
