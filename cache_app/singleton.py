from engine.cache_engine import CacheEngine
from engine.expire.active_expiry import ActiveExpirySweeper

cache_engine = CacheEngine()
active_sweeper = ActiveExpirySweeper(cache_engine)
