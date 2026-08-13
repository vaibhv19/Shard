# Implementation Roadmap — Shard (Distributed Cache Service)

## Document Control
* **Document Version:** 0.1.0
* **Status:** Draft
* **Authors:** Portfolio Owner / Technical Architect
* **Milestone Reference:** v0.5.0 (Roadmap Complete)
* **Twin Project Reference:** [Cairn Roadmap](file:///d:/Coding/Projects----For%20Resume/Cairn/Docs/Roadmap.md)

---

## 1. Git Workflow & Branching Strategy

To maintain a clean and reliable milestone progression, all code additions must adhere to the following git workflow:

```
[main]          <------------------------------ (Milestone Merges Only)
  ^
  | (milestone references: v0.1.0, v0.5.0, v1.0.0)
[test]          <------------------ (RC testing & manual verification)
  ^
  | (successful integration & stress tests)
[develop]       <------ (Local feature branch integration)
  ^
  |
[feature/*]     (Function-level tasks)
```

### Git Transition Gates:
1. **`feature/*` to `develop`:** Triggered when a developer finishes a function-level task. Requires the module to import/run cleanly and $100\%$ success of Phase-specific **Standard Unit Tests**.
2. **`develop` to `test`:** Triggered at phase completion. Requires $100\%$ success of **Concurrency Stress Tests** (under high thread contention) to guarantee no race conditions or lock deadlocks.
3. **`test` to `main`:** Triggered at Milestone Completion. Requires final code audit, static analysis checks (e.g. `ruff`/`mypy`), and up-to-date documentation.

---

## 2. Phase 1: MVP — Single-Node Engine & Core API

### 2.1 Task Dependency Graph
```
[1.1: Core Storage Engine] ---> [1.2: LRU Strategy] ---> [1.4: Eviction Integration] ---> [1.6: REST API]
                            ---> [1.3: LFU Strategy] ---> [1.5: TTL Expiration]       ---> [1.7: Test Suites]
```

### 2.2 Function-Level Code Tasks
1. **Task 1.1: Core Storage Engine & Records**
   * Implement `engine/cache_entry.py` dataclass with attributes `value (str)`, `created_time (float)`, `expiry_time (float)`, `last_access_time (float)`, and `access_frequency (int)`.
   * Implement `engine/cache_engine.py` containing the main index store (a standard Python `dict` protected by a `threading.Lock` or `threading.RLock`).
   * Implement `CacheEngine.exists(key)` returning a fast boolean lookup under the lock.
   * Implement base `CacheEngine.get(key)` and `CacheEngine.delete(key)` operations (excluding eviction/expiry).
2. **Task 1.2: Eviction Strategy Interface & LRU Implementation**
   * Define `engine/evict/strategy.py` Protocol/duck-typed interface with methods `on_access(key)`, `on_insert(key)`, `on_remove(key)`, and `evict_victim()`.
   * Implement `engine/evict/lru_eviction.py` containing a custom doubly-linked list node `LruNode` (attributes: `key`, `prev`, `next`) and the class `LruEvictionPolicy`.
   * Implement internal node list manipulation methods: `_promote(node)`, `_remove(node)`, and `_add_first(node)`.
3. **Task 1.3: LFU Eviction Policy Implementation**
   * Implement `engine/evict/lfu_eviction.py` containing the class `LfuEvictionPolicy` using a frequency-bucket list index.
   * Implement frequency promotion methods: update frequency counter and move keys between frequency lists (`OrderedDict` buckets).
   * Implement minimum frequency tracker pointer (`min_frequency`) to find LFU victim keys in $O(1)$ time.
4. **Task 1.4: Swappable Eviction Strategy Integration**
   * Wire `LruEvictionPolicy` and `LfuEvictionPolicy` as swappable strategies using Django settings (`SHARD_EVICTION_POLICY`) bootstrapped inside the `CacheEngine.__init__` factory loader.
   * Integrate capacity checks inside `CacheEngine.set(key, value)`. If the index size exceeds the maximum key limit (`SHARD_CACHE_MAX_SIZE`), call `evict_victim()`, remove the victim key from the dict and the eviction policy lists, and write the new entry.
5. **Task 1.5: Passive Expiration & Active Sweeper**
   * Integrate passive expiration logic within `CacheEngine.get()` and `CacheEngine.exists()`.
   * Create `engine/expire/active_expiry.py` executing background sweeps on a dedicated `threading.Thread` daemon worker.
   * Implement probabilistic sweep method `sweep_batch()` that samples random sub-arrays of keys under the lock and loops recursively if the expired percentage exceeds $25\%$ of the sample.
6. **Task 1.6: REST API Layer**
   * Implement API views in `cache_app/views.py` with routes `POST /api/v1/cache`, `GET /api/v1/cache/{key}`, `DELETE /api/v1/cache/{key}`, `GET /api/v1/cache/{key}/exists`, `POST /api/v1/cache/{key}/expire`, and `GET /api/v1/cache/{key}/ttl`.
   * Implement input serializers in `cache_app/serializers.py` to enforce key length, value size limits, and positive TTL validations.
   * Create custom DRF exception handlers in `cache_app/exceptions.py` to transform internal exceptions into standard HTTP error payloads from `APIContracts.md`.

### 2.3 Verification Tasks (Standard vs. Concurrency)
7. **Task 1.7: Verification & Testing**
   * **Standard Unit Tests (Category A):** Validate correctness of LRU doubly-linked list insertion/promotion, LFU frequency bucket boundaries, and passive/active TTL expiries inside `tests/unit/`.
   * **Concurrency Stress Tests (Category B):** Spawn parallel threads (e.g., 100 threads using `concurrent.futures.ThreadPoolExecutor`) writing and reading keys simultaneously under Gunicorn configurations with a capacity of 1,000 keys. Verify that eviction and sweeps never corrupt doubly-linked list pointers, drop writes, or raise exceptions.

### 2.4 Manual Setup Required
* Initialize standard Poetry environment and install virtualenv dependencies.
* Configure cache capacity settings and default eviction policies (`SHARD_CACHE_MAX_SIZE`, `SHARD_EVICTION_POLICY`) in `shard_project/settings.py`.

---

## 3. Phase 2: Consistent Hashing & Static Sharding

### 3.1 Task Dependency Graph
```
[Phase 1 Complete] ---> [2.1: Consistent Hashing Ring] ---> [2.2: Routing Layer] ---> [2.4: Route API]
                                                       ---> [2.3: Configuration]  ---> [2.5: Test Suites]
```

### 3.2 Function-Level Code Tasks
1. **Task 2.1: Hashing Ring Data Structure**
   * Implement Murmur3-32 hashing algorithm wrapper.
   * Implement `engine/sharding/consistent_hash.py` with an internal list representation of sorted hashes representing the ring.
   * Implement `ConsistentHashRing.add_node(node_id, virtual_node_count)` generating virtual node hashes on the ring and sorting them.
   * Implement `ConsistentHashRing.get_node(key)` returning the nearest virtual node IP from the ring utilizing binary search (`bisect.bisect_right`).
2. **Task 2.2: Routing Proxy Layer**
   * Implement `engine/sharding/router.py` to act as an HTTP request proxy.
   * Configure asynchronous/synchronous HTTP caller (e.g., using Gunicorn connection pooling or `httpx` client) in `NodeRouter` to forward CRUD actions to target node endpoints.
3. **Task 2.3: Static Configuration Bootstrap**
   * Parse list of static IP endpoints and virtual node allocations from Django settings (`SHARD_CLUSTER_NODES`).
   * Implement a Django app initializer or middleware startup hook to populate the local `ConsistentHashRing` during application boot.
4. **Task 2.4: Cluster Monitoring API**
   * Create routing views with route `GET /api/v1/cluster/health` returning node statuses, and `GET /api/v1/cluster/ring` mapping the ring distribution.

### 3.3 Verification Tasks (Standard vs. Concurrency)
5. **Task 2.5: Verification & Testing**
   * **Standard Unit Tests (Category A):** Validate node hash distributions. Assert that key hashing maps deterministically, and node addition/removal recalculates maps correctly.
   * **Concurrency Stress Tests (Category B):** Launch concurrent API writes across a multi-node setup, verifying proxy connection pools remain stable under load.
   * **Rebalancing Tests (Category C):** Programmatically alter static configurations and measure that the key migration rate matches the expected $1/(N+1)$ formula.

### 3.4 Manual Setup Required
* Define static cluster addresses (`SHARD_CLUSTER_NODES`) in `shard_project/settings.py`.
* Setup local test running environment: write shell/PowerShell scripts to boot 3 concurrent Django/Gunicorn instances on local ports `8000`, `8001`, and `8002`.

---

## 4. Phase 3: Invalidation Strategies & Observability

### 4.1 Task Dependency Graph
```
[Phase 2 Complete] ---> [3.1: Invalidation API]       ---> [3.3: Metrics Engine] ---> [3.5: Grafana UI]
                       ---> [3.2: Write Semantics]    ---> [3.4: Prometheus Hook] ---> [3.6: Test Suites]
```

### 4.2 Function-Level Code Tasks
1. **Task 3.1: Cache Invalidation Methods**
   * Implement invalidation methods inside the cache engine.
   * Implement wildcard evaluation method `invalidate_by_pattern(pattern)` (scanning key dictionary keys to match regex patterns like `user:*`).
   * Expose route `POST /api/v1/cache/invalidate` in `cache_app/views.py`.
2. **Task 3.2: Write-Through & Write-Back Pipelines**
   * Create a simulated external datasource interface (`engine/mock_database.py`).
   * Implement synchronous write pipeline `write_through(key, value)` updating both local cache dict and mock database under the lock.
   * Implement asynchronous pipeline `write_back(key, value)` queueing writes to a thread-safe `queue.Queue` drained by dedicated background worker daemon threads.
3. **Task 3.3: Non-Blocking Metrics Aggregation**
   * Implement `engine/metrics/collector.py` utilizing thread-safe metrics or locked counters for hits, misses, policy evictions, and expiry counts via `prometheus_client`.
   * Implement operational latency percentile timers ($p50$, $p95$, $p99$) using decay reservoirs.
4. **Task 3.4: Prometheus Metrics Mapping**
   * Register Shard metrics with the `prometheus_client` registry.
   * Expose endpoints `/metrics` returning standard Prometheus plaintext metrics, and `/api/v1/metrics/latency` returning JSON latency percentiles.
5. **Task 3.5: Dashboard Visualization**
   * Design dashboard UI layouts and construct Prometheus scrape configurations.
   * Compile Grafana Dashboard JSON templates displaying cluster health cards and hit ratio gauges.

### 4.3 Verification Tasks (Standard vs. Concurrency)
6. **Task 3.6: Verification & Testing**
   * **Standard Unit Tests (Category A):** Verify pattern matches on invalidation, correct write-through sync sequences, and write-back queue drainage checks.
   * **Concurrency Stress Tests (Category B):** Run high-volume write-back loads concurrently with wild-card purges. Verify that queue contention does not block live GET threads, and that Prometheus metrics update accurately without causing synchronization delays.

### 4.4 Manual Setup Required
* Register the `/metrics` path in `cache_app/urls.py` to expose metrics.
* Spin up local Prometheus and Grafana Docker instances to verify metric scrapes and render dashboard visualizations.
