from engine.cache_engine import CacheEngine
from engine.expire.active_expiry import ActiveExpirySweeper
from engine.sharding.consistent_hash import ConsistentHashRing
from engine.sharding.router import NodeRouter

cache_engine = CacheEngine()
active_sweeper = ActiveExpirySweeper(cache_engine)

hash_ring = ConsistentHashRing()
router = NodeRouter(hash_ring, "Node-A", {})
