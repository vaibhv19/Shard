# Shard

## 1. Project Overview

**Shard** is an in-memory, distributed, concurrent key-value cache engine implemented in pure Python, Django, and Django REST Framework (DRF). Built from the ground up without third-party caching middleware or external stores (such as Redis or Memcached), Shard implements core cache primitives directly within the Python process memory space.

The system features:
- **In-Memory Key-Value Core:** Bounded dictionary-backed storage protected by thread synchronization primitives.
- **Pluggable $O(1)$ Eviction Engine:** Strategy-pattern implementations of Least Recently Used (LRU) via a doubly-linked list with sentinel nodes, and Least Frequently Used (LFU) via frequency buckets and `OrderedDict` linked sets.
- **Dual Expiration Mechanics:** Passive expiration evaluated lazily upon key access, combined with an active background sweeper daemon thread that executes adaptive probabilistic batch purges.
- **Static Consistent Hashing Ring:** Murmur3-32 unsigned hash ring with 150 virtual nodes per physical instance, utilizing binary search (`bisect`) for deterministic key routing and minimal migration churn.
- **Transparent Cluster Routing Proxy:** Built-in proxy layer utilizing connection-pooled HTTP clients (`httpx`) to transparently forward requests across nodes.
- **Cache Invalidation & Write Semantics:** Prefix wildcard pattern invalidation with cluster-wide broadcast propagation, alongside simulated synchronous write-through and queue-backed asynchronous write-back pipelines.
- **Telemetry & Observability:** Prometheus metric endpoints (`/metrics`) exposing hit/miss counters, active key gauges, latency histograms, and a dedicated JSON latency percentile endpoint (`/api/v1/metrics/latency`) visualized via an included Grafana dashboard configuration.

Shard was designed and engineered as the direct functional twin to [Cairn](https://github.com/vaibhv19/Cairn) (a Spring Boot / Java 21 cache engine). Both systems implement identical API contracts, configuration parameters, and architectural boundaries, serving as a controlled comparative study of concurrency synchronization, lock contention, and throughput behavior between CPython's Global Interpreter Lock (GIL) and the JVM's multi-core parallel thread model.

---

## 2. Why I Built It

Most web applications interact with caches as black-box external services (e.g., calling `redis.get()` or `redis.set()`). While this is standard in production engineering, it obscures the internal systems problems that make caching engines work: how eviction pointers are updated under concurrency, how memory is reclaimed without causing request latency spikes, how hash rings route keys without central coordinators, and how runtime execution models shape synchronization design.

I built Shard to:
1. **Implement Core Storage and Eviction Algorithms from Scratch:** Build verified $O(1)$ LRU and LFU algorithms using fundamental data structures (doubly-linked lists and frequency buckets) rather than relying on high-level library abstractions.
2. **Explore Python Concurrency Realities Under the GIL:** Investigate how CPython's Global Interpreter Lock interacts with multithreaded shared-state mutations, examining why bytecode execution interleaving requires explicit locking despite common misconceptions that the GIL provides "free" thread safety.
3. **Conduct a Direct Architectural Twin Study:** Maintain precise functional symmetry with Cairn (Java/Spring Boot) to analyze how the same distributed cache architecture translates between a GIL-bound interpreted runtime and a native multi-core compiled JVM runtime.

---

## 3. Problem / Question

Building an in-memory concurrent cache in Python raises several foundational systems questions:

1. **The Synchronization Myth:** Does Python's GIL protect complex data structures from corruption under concurrent multithreaded access? (No: while single bytecode instructions execute atomically, compound operations—such as reading a value, updating an LRU pointer chain, and checking capacity—span multiple bytecode instructions where CPython can preemptively context-switch threads).
2. **Lock Granularity in a Serialized Runtime:** In a runtime where thread execution is already serialized on a single core by the GIL, what is the optimal lock granularity? Does fine-grained lock-striping (like Java's `ConcurrentHashMap`) provide any benefit, or does it merely introduce lock management overhead?
3. **Read-as-Write Concurrency Contention:** In an LRU or LFU cache, a read operation (`GET`) is not a passive read—it mutates internal pointers to record access recency or increment frequency. How do you protect pointer integrity across concurrent readers and writers without creating catastrophic latency bottlenecks?
4. **Active Expiration vs. Request Contention:** How can a background daemon thread sweep expired keys without holding a global lock long enough to starve user-facing API request threads?
5. **Deterministic Routing Without Central Masters:** How can independent cache nodes partition a global key space statically using consistent hashing, and how do virtual nodes prevent hotspot skew across uneven hash spaces?

---

## 4. What It Actually Does

Shard runs as an HTTP service exposing a REST API for cache operations, cluster routing, and observability:

### Core Caching Operations
- **`POST /api/v1/cache`**: Inserts or updates a key-value pair with an optional time-to-live (`ttl`) in seconds. Validates that keys are non-blank (max 250 chars) and values do not exceed 1MB. Returns `201 Created` for new keys and `200 OK` for updates, with an ISO-8601 UTC expiration timestamp.
- **`GET /api/v1/cache/{key}`**: Retrieves the cached string payload and remaining TTL. Returns `200 OK` with payload on hit, or `404 Not Found` if the key does not exist or has expired.
- **`DELETE /api/v1/cache/{key}`**: Removes the key from the storage dictionary and eviction tracking list, returning `204 No Content`. Returns `404 Not Found` if absent.
- **`GET /api/v1/cache/{key}/exists`**: Checks boolean existence without mutating LRU recency or LFU frequency metadata.
- **`POST /api/v1/cache/{key}/expire`**: Updates or assigns a TTL duration (in seconds) to an existing key.
- **`GET /api/v1/cache/{key}/ttl`**: Returns remaining TTL in seconds (`-1` if the key is persistent and has no expiration).

### Eviction & Expiration
- **Capacity Enforcement:** Bounded by `SHARD_CACHE_MAX_SIZE` (default: 1,000 keys). When an insertion exceeds capacity, the active eviction strategy picks a victim key, unlinks it, and removes it in $O(1)$ time. If eviction fails to free memory, the API returns `507 Insufficient Storage`.
- **Passive Expiration:** Evaluated on every read or write access under lock. If `time.time() > entry.expiry_time`, the key is immediately deleted and treated as a miss.
- **Active Expiration:** A background daemon thread (`ActiveExpirySweeper`) periodically samples a configurable batch of keys (default: 20 keys every 5.0 seconds). If more than 25% of the sampled batch is expired, it immediately loops to run another sweep cycle before sleeping.

### Sharding & Routing Proxy
- **Consistent Hashing:** Each physical node generates 150 virtual node points across an unsigned 32-bit Murmur3 integer ring (`0` to `2^32 - 1`).
- **Transparent Proxying:** If an incoming key hashes to a remote node on the ring, `NodeRouter` proxies the request to the target node using a pooled `httpx.Client` instance and returns the remote response.
- **Cluster Diagnostics:** Exposes `GET /api/v1/cluster/health` (node ID, active keys, capacity, uptime) and `GET /api/v1/cluster/ring` (virtual node allocation and cluster topology).

### Invalidation & Observability
- **Pattern Invalidation (`POST /api/v1/cache/invalidate`)**: Matches keys via wildcard expressions (e.g. `user:*` or `*` for full flush) using `fnmatchcase`. If the request is initiated from a client, the receiving node executes the local purge and broadcasts the invalidation to all other cluster members using the `X-Shard-Broadcast: true` header.
- **Write Semantics:** Synchronous `write_through()` updates both local cache and simulated backing storage; asynchronous `write_back()` updates local cache and enqueues the write to a thread-safe `queue.Queue` drained by a background worker thread.
- **Telemetry:** Exposes standard Prometheus metrics on `GET /metrics` and rolling latency percentiles (Max, P50, P95, P99) in milliseconds on `GET /api/v1/metrics/latency`.

---

## 5. Architecture

```
                                  Client Request
                                        │
                                        ▼
                             ┌─────────────────────┐
                             │  Django WSGI / DRF  │
                             │   (API Controllers) │
                             └──────────┬──────────┘
                                        │
                                        ▼
                             ┌─────────────────────┐
                             │     NodeRouter      │
                             │  (Proxy Evaluator)  │
                             └────┬───────────┬────┘
                                  │           │
           [Remote Node Key]      │           │ [Local Node Key]
                   ┌──────────────┘           └──────────────┐
                   ▼                                         ▼
        ┌─────────────────────┐                   ┌─────────────────────┐
        │    httpx.Client     │                   │     CacheEngine     │
        │ (Forward to Peer)   │                   │ (threading.Lock)    │
        └─────────────────────┘                   └──────────┬──────────┘
                                                             │
                  ┌──────────────────────────────────────────┼──────────────────────────────────────────┐
                  ▼                                          ▼                                          ▼
       ┌─────────────────────┐                    ┌─────────────────────┐                    ┌─────────────────────┐
       │   cache_dict Store  │                    │  EvictionStrategy   │                    │ Expiration Engine   │
       │ dict[str,CacheEntry]│                    │   (LRU / LFU)       │                    │ (Active & Passive)  │
       └─────────────────────┘                    └─────────────────────┘                    └─────────────────────┘
                  │                                          │                                          │
                  └──────────────────────────────────────────┼──────────────────────────────────────────┘
                                                             │
                                                             ▼
                                                  ┌─────────────────────┐
                                                  │  MetricsCollector   │
                                                  │ (Prometheus Gauges) │
                                                  └─────────────────────┘
```

### Module Responsibilities

1. **`cache_app/` (HTTP & Web Boundary):**
   - [`views.py`](file:///d:/Coding/Projects----For%20Resume/Shard/cache_app/views.py): DRF class-based views handling CRUD operations, cluster discovery, invalidation broadcasts, and metric rendering.
   - [`serializers.py`](file:///d:/Coding/Projects----For%20Resume/Shard/cache_app/serializers.py): DRF serializers enforcing payload constraints (key length $\le 250$, value size $\le 1\text{MB}$, positive integer TTL).
   - [`exceptions.py`](file:///d:/Coding/Projects----For%20Resume/Shard/cache_app/exceptions.py): Custom DRF exception handler mapping domain errors (`KeyNotFoundException`, `EvictionFailedException`, `ValidationError`) into standardized JSON error responses.
   - [`singleton.py`](file:///d:/Coding/Projects----For%20Resume/Shard/cache_app/singleton.py): Holds singleton instances of `CacheEngine`, `ActiveExpirySweeper`, `ConsistentHashRing`, and `NodeRouter`.
   - [`apps.py`](file:///d:/Coding/Projects----For%20Resume/Shard/cache_app/apps.py): AppConfig initialization bootstrapping the hash ring, router configuration, and background active sweeper thread on server boot.

2. **`engine/` (Core Storage & Concurrency):**
   - [`cache_engine.py`](file:///d:/Coding/Projects----For%20Resume/Shard/engine/cache_engine.py): Primary orchestrator coordinating the storage dictionary, active eviction strategy, write-through/back pipelines, and thread locking.
   - [`cache_entry.py`](file:///d:/Coding/Projects----For%20Resume/Shard/engine/cache_entry.py): Compact dataclass wrapping the string payload, epoch `created_time`, and epoch `expiry_time`.
   - [`mock_database.py`](file:///d:/Coding/Projects----For%20Resume/Shard/engine/mock_database.py): Thread-safe in-memory database simulation for write-through and write-back tests.

3. **`engine/evict/` (Strategy Pattern Eviction):**
   - [`strategy.py`](file:///d:/Coding/Projects----For%20Resume/Shard/engine/evict/strategy.py): Typing Protocol defining `on_access(key)`, `on_insert(key)`, `on_remove(key)`, and `evict_victim()`.
   - [`lru_eviction.py`](file:///d:/Coding/Projects----For%20Resume/Shard/engine/evict/lru_eviction.py): LRU policy maintaining a doubly-linked list (`LruNode`) with dummy head/tail sentinels and a node lookup map.
   - [`lfu_eviction.py`](file:///d:/Coding/Projects----For%20Resume/Shard/engine/evict/lfu_eviction.py): LFU policy maintaining frequency buckets (`freq_map: dict[int, OrderedDict[str, bool]]`), a key-to-node map, and an active `min_frequency` tracker pointer.

4. **`engine/expire/` (Active Memory Reclamation):**
   - [`active_expiry.py`](file:///d:/Coding/Projects----For%20Resume/Shard/engine/expire/active_expiry.py): `ActiveExpirySweeper` daemon thread running the adaptive probabilistic sweep loop.

5. **`engine/sharding/` (Consistent Hashing & Proxy):**
   - [`consistent_hash.py`](file:///d:/Coding/Projects----For%20Resume/Shard/engine/sharding/consistent_hash.py): `ConsistentHashRing` managing Murmur3-32 virtual node hashes in a sorted list via `bisect`.
   - [`router.py`](file:///d:/Coding/Projects----For%20Resume/Shard/engine/sharding/router.py): `NodeRouter` providing key resolution, proxy decision logic, and pooled HTTP forwarding via `httpx`.

6. **`engine/metrics/` (Telemetry & Observability):**
   - [`collector.py`](file:///d:/Coding/Projects----For%20Resume/Shard/engine/metrics/collector.py): `MetricsCollector` wrapping Prometheus counters, gauges, and histograms, plus a sliding window `deque` for JSON latency percentile calculations.

---

## 6. Important Technical Decisions

### Decision 1: Coarse-Grained Engine Locking over Fine-Grained Lock Striping
- **Context:** Cairn (Java) implements lock-striping across hash buckets using `ConcurrentHashMap` and segmented read-write locks to maximize multi-core parallel throughput.
- **Decision:** In Shard, implement a single, coarse-grained `self.lock = threading.Lock()` at the `CacheEngine` level protecting all dictionary mutations, eviction pointer shifts, and counter updates.
- **Rationale:** Because CPython's GIL serializes all thread bytecode execution onto a single physical CPU core, multiple fine-grained locks cannot provide true hardware parallelism. Instead, managing multiple locks introduces significant CPU overhead from repeated lock acquisition/release cycles and context-switching overhead. A single coarse lock protects internal invariants atomically with lower latency.

### Decision 2: Key-Count Capacity Limits over Memory-Size Byte Limits
- **Context:** Deciding how to define maximum cache capacity (`SHARD_CACHE_MAX_SIZE`).
- **Decision:** Bound the cache by key count (default: 1,000 keys) rather than total memory in bytes.
- **Rationale:** Accurate memory accounting of dynamic Python objects at runtime requires deep object graph traversals (e.g. recursive `sys.getsizeof`), which introduces substantial execution overhead on every write. Furthermore, `sys.getsizeof` does not account for CPython memory allocator fragmentation or PyObject header overhead. Key-count limits provide deterministic, zero-overhead $O(1)$ capacity enforcement.

### Decision 3: Murmur3-32 Consistent Hashing with 150 Virtual Nodes
- **Context:** Mapping arbitrary string keys across a static cluster of cache nodes.
- **Decision:** Use 32-bit unsigned Murmur3 hashes (`mmh3.hash(key) & 0xffffffff`) with 150 virtual nodes per physical instance, maintained in a sorted Python list using `bisect.bisect_right`.
- **Rationale:** Modulo hashing (`hash(key) % N`) causes complete key reshuffling whenever cluster membership changes ($100\%$ migration). Consistent hashing guarantees that adding or removing a node migrates only $\approx 1/(N+1)$ of keys. Virtual nodes ensure uniform distribution across the 32-bit ring space, preventing hot spots.

### Decision 4: Dual-Lock Sweeper Verification for Active Expiration
- **Context:** The background sweeper must sample keys and delete expired ones without holding the engine lock for extended periods.
- **Decision:** Implement a three-stage sweep: (1) acquire lock to take a small random sample of keys, (2) release lock and filter expired keys by comparing timestamps outside the lock, (3) re-acquire lock to delete expired keys, explicitly re-verifying key presence and expiration timestamp under the second lock.
- **Rationale:** Releasing the lock during timestamp evaluation prevents blocking live API request threads. Re-verifying under the lock prevents check-then-act race conditions where a concurrent writer updated or deleted a key between stages 2 and 3.

---

## 7. Interesting Engineering Problems

### Problem 1: Eviction Transforms Reads into Concurrent Writes
- **Symptom:** In a pure key-value store, a `GET` is a read operation that can execute concurrently with other readers. In an LRU cache, however, every `GET` must move the accessed node to the head of the doubly-linked list (`_promote(node)`).
- **Concurrency Danger:** If two concurrent reader threads attempt to promote different nodes simultaneously without synchronization, they will concurrently mutate the same `head.next` and `node.prev` pointers. This causes orphaned nodes, severed list chains, or circular pointer loops that hang eviction traversals.
- **Solution:** Enforce that all `get()` and `get_with_ttl()` calls acquire the engine's `threading.Lock` before calling `eviction_strategy.on_access(key)`, serializing list pointer mutations across all read operations.

### Problem 2: $O(1)$ LFU Bucket Eviction and Min-Frequency Tracking
- **Challenge:** LFU requires evicting the key with the lowest access frequency. Naive implementations scan all entries in $O(N)$ time or use a min-heap in $O(\log N)$ time.
- **Implementation:** Shard implements an $O(1)$ frequency-bucket table:
  - `freq_map: dict[int, OrderedDict[str, bool]]` maps each access count (frequency) to an `OrderedDict` representing keys at that frequency.
  - An `OrderedDict` preserves insertion order, providing LRU tie-breaking within the same frequency bucket.
  - A `self.min_frequency` integer pointer tracks the lowest active frequency. When a key is accessed, it moves from bucket $F$ to $F+1$. If bucket $F$ becomes empty and $F == \text{min\_frequency}$, `min_frequency` increments to $F+1$.
  - Eviction simply pops the oldest item from `freq_map[self.min_frequency]` in $O(1)$ time.

### Problem 3: Cluster Broadcast Loops in Pattern Invalidation
- **Challenge:** When a client calls `POST /api/v1/cache/invalidate` with pattern `user:*`, the receiving node must invalidate its local keys and notify all peer nodes. If peer nodes also broadcast upon receiving the invalidation, an infinite broadcast storm occurs.
- **Solution:** Implement an internal header check: `X-Shard-Broadcast: true`. When a node receives an invalidation from a client, it forwards the request to all peer nodes with `X-Shard-Broadcast: true`. When a node receives a request with this header, it executes the local invalidation but suppresses further outbound forwarding.

---

## 8. Failure Modes / Things That Went Wrong

1. **Check-Then-Act Race in Active Expiration:**
   - *Failure Mode:* During early development, the sweeper sampled keys, identified expired keys outside the lock, and deleted them under a second lock without re-checking. A concurrent request thread updated an expired key with a new value and extended TTL between the sweep stages. The sweeper then deleted the freshly updated key.
   - *Resolution:* Implemented double-checked verification inside the mutation lock: verifying that the key still exists in `cache_dict` and that `time.time() > entry.expiry_time` before calling `del`.

2. **Eviction Failure on Capacity Breach (`507 Insufficient Storage`):**
   - *Failure Mode:* If a cache is initialized with a capacity of 0 or if the eviction tracking list becomes desynchronized from the storage dictionary, `evict_victim()` returns `None`. Without explicit handling, the insertion would proceed, violating capacity limits or raising unexpected exceptions.
   - *Resolution:* Created `EvictionFailedException` which is raised when eviction cannot free space, caught by `custom_exception_handler`, and translated into HTTP `507 Insufficient Storage`.

3. **Remote Peer Outages in Proxy Routing:**
   - *Failure Mode:* In a sharded multi-node cluster, if a target physical node crashes or is unreachable, the proxying node's `httpx` client would raise unhandled connection errors, crashing the request pipeline.
   - *Resolution:* Configured connection timeouts (5.0s on proxy, 2.0s on broadcast) and graceful error handling in `NodeRouter` and `CacheInvalidateView` to prevent peer failures from crashing the local instance.

---

## 9. Verification / Testing

Shard employs a two-tier test strategy separating rapid unit validation from high-contention multithreaded stress testing:

### Test Suites (`tests/`)

1. **Category A: Standard Functional Unit Tests (`tests/unit/` - 14 files):**
   - [`test_cache_engine.py`](file:///d:/Coding/Projects----For%20Resume/Shard/tests/unit/test_cache_engine.py): Tests core CRUD, capacity limits, overwrite semantics, and eviction error handling.
   - [`test_lru_eviction.py`](file:///d:/Coding/Projects----For%20Resume/Shard/tests/unit/test_lru_eviction.py): Tests LRU doubly-linked list ordering, promotion on access, and victim selection.
   - [`test_lfu_eviction.py`](file:///d:/Coding/Projects----For%20Resume/Shard/tests/unit/test_lfu_eviction.py): Tests frequency incrementing, bucket promotion, FIFO tie-breaking, and `min_frequency` tracking.
   - [`test_active_expiry.py`](file:///d:/Coding/Projects----For%20Resume/Shard/tests/unit/test_active_expiry.py): Tests passive expiration on access and active background batch sweep reclamation.
   - [`test_consistent_hash.py`](file:///d:/Coding/Projects----For%20Resume/Shard/tests/unit/test_consistent_hash.py): Validates Murmur3-32 hashing, virtual node distribution, wraparound ring lookups, and node addition/removal.
   - [`test_routing_proxy.py`](file:///d:/Coding/Projects----For%20Resume/Shard/tests/unit/test_routing_proxy.py): Validates `NodeRouter` proxy decisions and HTTP request forwarding using `respx` mock routing.
   - [`test_rebalancing.py`](file:///d:/Coding/Projects----For%20Resume/Shard/tests/unit/test_rebalancing.py): Verifies that adding a node to the hash ring migrates only the expected $\approx 1/(N+1)$ fraction of keys.
   - [`test_invalidation.py`](file:///d:/Coding/Projects----For%20Resume/Shard/tests/unit/test_invalidation.py): Validates exact-key, wildcard prefix (`user:*`), and full flush (`*`) invalidations.
   - [`test_write_semantics.py`](file:///d:/Coding/Projects----For%20Resume/Shard/tests/unit/test_write_semantics.py): Tests synchronous `write_through` and asynchronous `write_back` queue drainage against `MockDatabase`.
   - [`test_api.py`](file:///d:/Coding/Projects----For%20Resume/Shard/tests/unit/test_api.py), [`test_cluster_api.py`](file:///d:/Coding/Projects----For%20Resume/Shard/tests/unit/test_cluster_api.py), [`test_metrics_api.py`](file:///d:/Coding/Projects----For%20Resume/Shard/tests/unit/test_metrics_api.py): Tests all DRF HTTP endpoints, validation error schemas, and status codes.
   - [`test_bootstrap.py`](file:///d:/Coding/Projects----For%20Resume/Shard/tests/unit/test_bootstrap.py): Tests Django `AppConfig.ready()` initialization of hash rings and routers from settings.

2. **Category B: Concurrency Stress Tests (`tests/concurrency/` - 3 files):**
   - [`test_concurrent_engine.py`](file:///d:/Coding/Projects----For%20Resume/Shard/tests/concurrency/test_concurrent_engine.py): Spawns 20–50 parallel threads via `ThreadPoolExecutor` executing 500+ simultaneous read/write/delete operations on shared keys. Asserts zero state corruption, zero missing pointer exceptions, and exact capacity enforcement under high contention.
   - [`test_concurrent_expiry.py`](file:///d:/Coding/Projects----For%20Resume/Shard/tests/concurrency/test_concurrent_expiry.py): Runs concurrent reader/writer threads simultaneously with the background `ActiveExpirySweeper` daemon thread. Validates that active sweeps never corrupt pointers or cause race conditions with live writers.
   - [`test_concurrent_api.py`](file:///d:/Coding/Projects----For%20Resume/Shard/tests/concurrency/test_concurrent_api.py): Executes parallel HTTP requests against DRF views under thread contention to verify view-level synchronization.

### Test Execution Results
- **Pass Rate:** 54 passed in 7.50 seconds.
- **Django Configuration:** `python manage.py check` reports 0 issues.
- **Static Analysis:** `ruff check .` passes with 0 lint errors.

---

## 10. Deployment

### Local Development / Single-Node Mode
Shard runs directly via Django management commands within a Poetry virtual environment:
```bash
poetry install
poetry run python manage.py runserver 127.0.0.1:8000
```

### Static Cluster Mode (3-Node Local Cluster)
To spin up a local 3-node distributed cache cluster, start three instances with configured node identities:
```bash
# Terminal 1 (Node A)
SHARD_NODE_ID=Node-A poetry run python manage.py runserver 127.0.0.1:8000

# Terminal 2 (Node B)
SHARD_NODE_ID=Node-B poetry run python manage.py runserver 127.0.0.1:8001

# Terminal 3 (Node C)
SHARD_NODE_ID=Node-C poetry run python manage.py runserver 127.0.0.1:8002
```

### Production Entry Point
- **WSGI Entry Point:** [`shard_project/wsgi.py`](file:///d:/Coding/Projects----For%20Resume/Shard/shard_project/wsgi.py) exposes the standard `application = get_wsgi_application()` object for deployment behind WSGI application servers (e.g., Gunicorn).

### Observability Stack
- **Prometheus Scraping:** Prometheus scrapes `/metrics` on all running node instances.
- **Grafana Visualization:** Import [`grafana-dashboard.json`](file:///d:/Coding/Projects----For%20Resume/Shard/grafana-dashboard.json) into Grafana to display total cluster keys, healthy node counts, live hit/miss ratio gauges, latency percentile time-series (P50, P95, P99), and eviction breakdowns (Policy vs. TTL).

---

## 11. What I Learned

1. **Python Bytecode Execution vs. Thread Safety:** The CPython GIL guarantees only that one thread executes a bytecode instruction at a time; it does not make compound statements atomic. Operations like `dict` lookups paired with linked list updates can be interrupted between any two bytecode opcodes, making explicit synchronization mandatory for shared mutable state.
2. **Lock Granularity Trade-offs in Interpreted Runtimes:** Architectural patterns from multi-core runtimes (such as Java's lock-striping) do not transfer beneficially to GIL-bound Python. In Python, fine-grained locking adds CPU overhead without enabling true parallelism; a well-placed coarse lock is often both simpler and faster.
3. **Sentinels Drastically Simplify Pointer Mechanics:** Using dummy head and tail sentinel nodes in doubly-linked lists eliminates null-check edge cases during insertion, promotion, and eviction, significantly reducing bug surface area in high-contention code paths.
4. **Adaptive Background Loops Balance Latency and CPU:** Constant background polling wastes CPU cycles, while long fixed sleep intervals allow expired memory to accumulate. An adaptive loop that re-sweeps immediately if $>25\%$ of keys were expired and sleeps otherwise balances memory reclamation with low CPU usage.

---

## 12. What Changed in My Thinking

- **Before:** I assumed the GIL would prevent data corruption for simple in-memory operations, making explicit locking redundant for basic dictionary operations.
  **After:** I realized that even a single conceptual operation (e.g. `CacheEngine.set()`) involves checking capacity, evicting a victim, unlinking pointers, instantiating a dataclass, and updating the dictionary. Context switching during any of these steps causes silent pointer corruption and inconsistent state without strict lock boundaries.
- **Before:** I thought fine-grained locking was always the gold standard for high-performance concurrent software.
  **After:** I learned that synchronization strategy must match the runtime execution model. Fine-grained locking shines in native parallel environments (like Java's JVM), while in GIL-bound environments (like CPython), minimizing lock acquisition count is more critical than segmenting lock domains.
- **Before:** I viewed consistent hashing as a theoretical concept primarily relevant to large multi-terabyte databases.
  **After:** Implementing consistent hashing with virtual nodes from scratch showed how practical it is for static routing proxies, providing deterministic key ownership and bounded key migration with zero central coordination.

---

## 13. Distinctive / Interesting Details

- **Twin Architecture Study:** Shard was deliberately designed alongside Cairn (Java/Spring Boot) with matching API contracts, configuration keys, and error payloads, enabling a direct qualitative and quantitative study of concurrency architectures between Python and Java.
- **Sentinel-Bounded Doubly Linked List:** `LruEvictionPolicy` initializes dummy `head` and `tail` nodes (`self.head.next = self.tail; self.tail.prev = self.head`), ensuring that node insertions and deletions never need special-case handling for empty lists or boundary elements.
- **OrderedDict Frequency Buckets:** `LfuEvictionPolicy` uses `dict[int, OrderedDict[str, bool]]` to achieve $O(1)$ LFU frequency updates while preserving LRU ordering within identical frequency buckets.
- **Self-Routing Proxy Layer:** Every Shard instance can act as both a storage node and a routing proxy. Clients can send any request to any node; if the key belongs to a peer, the node transparently proxies the request and relays the response.
- **Broadcast Invalidation Loop Prevention:** The `X-Shard-Broadcast: true` HTTP header prevents infinite request loops during cluster-wide wildcard cache purges.

---

## 14. Skills Demonstrated

### Engineering Skills
- Concurrency & Thread Synchronization under GIL constraints
- Algorithm & Data Structure Implementation ($O(1)$ LRU & LFU)
- Distributed Systems Routing (Consistent Hashing Ring & Virtual Nodes)
- REST API Design & Error Normalization (Django REST Framework)
- Asynchronous & Background Processing (Daemon threads & thread-safe Queues)
- Concurrency Stress Testing & Verification (`ThreadPoolExecutor`)
- Telemetry & Observability Integration (Prometheus & Grafana)

### Technologies & Tools
- **Language & Runtime:** Python 3.12+, CPython
- **Frameworks:** Django 5.x, Django REST Framework (DRF) 3.15.x
- **Concurrency Primitives:** `threading.Lock`, `threading.Thread`, `queue.Queue`
- **Libraries:** `mmh3` (Murmur3 hashing), `httpx` (HTTP connection pooling), `prometheus-client`
- **Testing & Tooling:** `pytest`, `pytest-django`, `respx`, `ruff`, `mypy`, `Poetry`
- **Monitoring:** Prometheus, Grafana

### Concepts
- Global Interpreter Lock (GIL) execution dynamics
- Doubly-linked lists with sentinel nodes
- Frequency-bucket indexing with secondary recency ordering
- Consistent hashing topology & virtual node distribution
- Passive vs. Active probabilistic expiration sweeps
- Write-Through vs. Write-Back persistence simulation
- Lock contention & tail latency percentile measurement

### Best Skills for LinkedIn
1. **Concurrency & Multithreading (Python)**
2. **Distributed Systems & Consistent Hashing**
3. **Data Structures & Algorithm Design**
4. **Django REST Framework**
5. **Systems Architecture & Performance Analysis**
6. **Prometheus & Observability**
7. **Python (CPython Internal Mechanics)**

---

## 15. Public Content

### LinkedIn Project Description
When building concurrent systems in Python, a common misconception is that the Global Interpreter Lock (GIL) makes multithreaded code automatically thread-safe. While the GIL ensures only one bytecode instruction executes at a time, compound operations—like updating an eviction list while inserting into a dictionary—span multiple opcodes where threads can be preempted, leading to silent state corruption.

To explore this hands-on, I built **Shard**, an in-memory, distributed, concurrent key-value cache engine in Python and Django REST Framework, implemented from scratch without wrapping external stores like Redis.

Key engineering aspects of Shard:
- **$O(1)$ Eviction Strategies:** Implemented pluggable LRU (doubly-linked list with sentinel nodes) and LFU (frequency-bucket maps using OrderedDicts for secondary recency ordering) algorithms.
- **Concurrency & Synchronization:** Analyzed lock granularity under CPython, demonstrating why a single coarse-grained engine lock outperforms fine-grained lock-striping in a GIL-bound runtime by eliminating lock management overhead.
- **Dual Expiration:** Paired lazy passive evaluation on access with an adaptive background sweeper thread that samples batches and re-sweeps when expired key density exceeds 25%.
- **Consistent Hashing & Cluster Routing:** Built an unsigned Murmur3-32 consistent hash ring with 150 virtual nodes per instance, enabling deterministic routing and a self-forwarding HTTP proxy layer across static cluster nodes.
- **Write Pipelines & Telemetry:** Simulated synchronous write-through and asynchronous queue-backed write-back semantics, integrated Prometheus metrics, and compiled Grafana dashboards for latency and eviction tracking.

Shard was developed as the architectural twin to **Cairn** (a Java 21/Spring Boot implementation sharing the same API contracts), providing a direct case study in concurrency design between GIL-bound Python and native multi-core JVM execution.

### LinkedIn Featured Description
*Direct link to technical blog post:*
**Same System, Different Languages: Building a Distributed Cache in Python and Java** — An architectural comparison exploring concurrency models, lock granularity under the Python GIL vs. the JVM, $O(1)$ eviction strategies, and consistent hashing.
[Read the Article](https://vaibhav19.vercel.app/writing/what-i-learned-from-building-the-same-distributed-cache-in-java-and-python)

### Resume Bullets
- Built an in-memory concurrent cache engine in Python/Django from scratch, implementing $O(1)$ LRU (sentinel doubly-linked list) and LFU (frequency buckets with secondary recency ordering) eviction policies under a global thread-synchronization lock.
- Designed a client-side consistent hashing ring using Murmur3-32 and 150 virtual nodes per instance, integrating a transparent HTTP proxy router (`httpx`) to deterministically partition and forward requests across a static multi-node cluster.
- Implemented dual expiration mechanics pairing passive on-access eviction with an adaptive background sweeper thread, alongside Prometheus telemetry and concurrent stress test suites validating zero data corruption under thread contention.

### GitHub Repo One-Liner
GIL-conscious distributed cache in Python/Django with pluggable eviction and consistent hashing.

---

## 16. Claims That Should NOT Be Made

To preserve technical integrity and avoid unsupported statements:
- **DO NOT claim massive production scale or throughput numbers:** Do not claim "processes 100,000 requests/second in production" or "reduced latency by 90% across microservices." Shard is a local architectural project, not deployed to an enterprise production cluster.
- **DO NOT claim dynamic consensus or Raft clustering:** Shard implements static consistent hashing via configuration, not a dynamic gossip protocol (Gossip) or Raft consensus.
- **DO NOT claim zero-GIL free-threading:** Shard runs on standard CPython with the GIL enabled; it coordinates threads using standard `threading.Lock`.
- **DO NOT claim Redis feature parity:** Shard implements a REST API for core key-value operations, not the full Redis RESP protocol, Redis Streams, or disk persistence (RDB/AOF).
- **DO NOT claim quantitative JVM benchmark superiority:** As documented in `LEARNING_HANDBOOK.md`, while the twin architecture enables controlled comparison, the repo does not contain a published multi-node benchmark dataset.

---

## 17. Evidence / Source References

| Key Fact / Feature | Source File in Repository |
| :--- | :--- |
| Core cache engine, lock synchronization, write pipelines | [`engine/cache_engine.py`](file:///d:/Coding/Projects----For%20Resume/Shard/engine/cache_engine.py) |
| $O(1)$ LRU doubly-linked list implementation | [`engine/evict/lru_eviction.py`](file:///d:/Coding/Projects----For%20Resume/Shard/engine/evict/lru_eviction.py) |
| $O(1)$ LFU frequency buckets with `OrderedDict` | [`engine/evict/lfu_eviction.py`](file:///d:/Coding/Projects----For%20Resume/Shard/engine/evict/lfu_eviction.py) |
| Eviction Strategy typing protocol | [`engine/evict/strategy.py`](file:///d:/Coding/Projects----For%20Resume/Shard/engine/evict/strategy.py) |
| Active expiration sweeper thread & adaptive loop | [`engine/expire/active_expiry.py`](file:///d:/Coding/Projects----For%20Resume/Shard/engine/expire/active_expiry.py) |
| Murmur3-32 consistent hash ring with virtual nodes | [`engine/sharding/consistent_hash.py`](file:///d:/Coding/Projects----For%20Resume/Shard/engine/sharding/consistent_hash.py) |
| Proxy routing & pooled HTTP forwarding | [`engine/sharding/router.py`](file:///d:/Coding/Projects----For%20Resume/Shard/engine/sharding/router.py) |
| Prometheus telemetry & latency percentiles | [`engine/metrics/collector.py`](file:///d:/Coding/Projects----For%20Resume/Shard/engine/metrics/collector.py) |
| Mock database for write-through/back semantics | [`engine/mock_database.py`](file:///d:/Coding/Projects----For%20Resume/Shard/engine/mock_database.py) |
| DRF REST API views & broadcast invalidation | [`cache_app/views.py`](file:///d:/Coding/Projects----For%20Resume/Shard/cache_app/views.py) |
| Payload serialization & validation constraints | [`cache_app/serializers.py`](file:///d:/Coding/Projects----For%20Resume/Shard/cache_app/serializers.py) |
| Normalized JSON error responses | [`cache_app/exceptions.py`](file:///d:/Coding/Projects----For%20Resume/Shard/cache_app/exceptions.py) |
| Cluster bootstrapping on application boot | [`cache_app/apps.py`](file:///d:/Coding/Projects----For%20Resume/Shard/cache_app/apps.py) |
| Production WSGI application entry point | [`shard_project/wsgi.py`](file:///d:/Coding/Projects----For%20Resume/Shard/shard_project/wsgi.py) |
| Concurrency stress test suites (threads under load) | [`tests/concurrency/`](file:///d:/Coding/Projects----For%20Resume/Shard/tests/concurrency) |
| Functional & isolation unit test suites | [`tests/unit/`](file:///d:/Coding/Projects----For%20Resume/Shard/tests/unit) |
| Grafana observability dashboard definition | [`grafana-dashboard.json`](file:///d:/Coding/Projects----For%20Resume/Shard/grafana-dashboard.json) |
| Engineering retrospective on GIL & concurrency | [`Docs/LEARNING_HANDBOOK.md`](file:///d:/Coding/Projects----For%20Resume/Shard/Docs/LEARNING_HANDBOOK.md) |
| Product requirements & twin architecture reference | [`Docs/PRD.md`](file:///d:/Coding/Projects----For%20Resume/Shard/Docs/PRD.md) |
| REST API endpoint specifications | [`Docs/APIContracts.md`](file:///d:/Coding/Projects----For%20Resume/Shard/Docs/APIContracts.md) |
