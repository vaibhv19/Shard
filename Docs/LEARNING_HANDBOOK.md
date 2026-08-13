# Learning & Engineering Handbook — Shard

This document compiles the engineering insights, concurrency lessons, and architectural trade-offs discovered during the planning and implementation of Shard. It serves as a technical retrospective for reviewers.

---

## 1. Concurrency Lessons & Lock Granularity

Implementing a thread-safe cache engine in Python requires navigating CPython's execution model, understanding bytecode execution atomicity, and designing synchronization boundaries that respect the runtime environment.

### 1.1 The CPython Global Interpreter Lock (GIL) Reality
Unlike its Java twin Cairn, which executes code in parallel across multiple physical CPU cores, Shard runs on standard CPython threads which are pre-emptively interleaved/time-sliced on a single physical CPU core. 
- **The Misconception:** A common misconception is that CPython's GIL makes code automatically thread-safe, rendering locks unnecessary.
- **The Reality:** While the GIL guarantees that only one thread executes Python bytecode at any single instant, it does *not* make multi-step cache operations atomic. CPython can context-switch threads between any two bytecode instructions.
- **Compound State Transitions:** Operations such as "check if key exists, then update it" or "insert key, promo node, and evict if full" span multiple bytecode instructions. Without explicit synchronization, concurrent threads can interrupt each other mid-operation, resulting in corrupted pointer chains in the LRU/LFU lists, duplicate key entries, or size-tracking discrepancies.

### 1.2 Cache State Synchronization
Shard maintains several mutable, shared data structures that require strict thread-safety:
- **`self.cache_dict`:** The primary hash index mapping keys to `CacheEntry` objects.
- **Eviction Lists:** The LRU doubly-linked list (requiring node unlinking and head promotion) and LFU frequency maps (requiring node unlinking, frequency incrementing, and bucket reallocation).
- **Expiration Schedules:** Expiry timestamps and eviction counters that are accessed and modified by reader threads, writer threads, and the active sweeper thread.
- **Write-Back Queue:** The `queue.Queue` coordinating asynchronous persistence simulation.

### 1.3 Lock Granularity Decisions
Cairn uses fine-grained lock-striping and reentrant read-write locks to maximize multi-core throughput. Shard, however, implements a single, coarse-grained `self.lock = threading.Lock()` at the `CacheEngine` level.
- **Alternative Considered (Fine-Grained Locking):** We evaluated implementing a custom reader-writer lock or partitioning the cache index into multiple segment locks (similar to Cairn's lock striping).
- **The Trade-off:** Because the CPython GIL serializes all thread execution on a single core anyway, multiple fine-grained locks cannot yield true physical parallelism. Instead, managing multiple locks introduces significant CPU overhead due to repeated lock acquisition/release instructions and increased context-switching latency. 
- **Pragmatic Choice:** A single, coarse-grained engine lock protects all internal dictionaries, eviction lists, and metadata in one atomic block. This is the most performant and correct design for a GIL-bound runtime, as it eliminates lock management overhead and prevents the engine's internal states from diverging.

### 1.4 Eviction and Concurrency
Eviction algorithms (LRU and LFU) introduce a critical concurrency implication: **they transform read operations into concurrent writes**.
- In LRU, a cache `GET` (conceptually a read operation) must promote the key by unlinking it from its current position in the doubly-linked list and inserting it at the head.
- Under high parallel thread load, concurrent `GET` operations will attempt to manipulate the same head and tail pointers simultaneously.
- Without the global engine lock protecting these promotions, pointers will become orphaned, creating cycles in the list or causing memory leaks. Thus, reads and writes must be serialized under the same lock boundary.

### 1.5 TTL / Active Expiration
Shard implements a dual expiration strategy: passive checking on access and active background sweeps.
- **The Sweeper Thread:** The `ActiveExpirySweeper` runs as a background daemon thread, periodically sampling random batches of keys and purging expired entries.
- **Synchronization:** The sweeper must acquire the engine's global lock (`with self.engine.lock:`) during each sweep batch.
- **Race Avoidance:** This prevents a critical race condition where a request worker thread attempts to fetch, update, or promote a key while the active sweeper is unlinking it from the storage dictionary and eviction pointers.

---

## 2. Design Decisions & Trade-offs

### 2.1 Django / DRF Web Boundary
- **Decision:** Python 3.12, Django 5.x, and Django REST Framework 3.15.x.
- **Alternatives Considered:** FastAPI or Flask.
- **Justification:** Shard was built to serve as a direct comparative twin to Cairn (Spring Boot). Django was chosen because its robust settings, WSGI middleware, and request dispatching mirror the enterprise structure of Spring Boot.
- **The Trade-off:** Django introduces higher HTTP request-handling overhead than FastAPI. However, this overhead is isolated to the network/HTTP layer. Bypassing HTTP via concurrent unit tests shows sub-millisecond cache engine execution time, proving the core engine performance is unaffected by the choice of Django.

### 2.2 In-Memory Storage & Custom Engine
- **Decision:** Pure Python `dict` and customized LRU/LFU strategy classes.
- **Alternatives Considered:** Wrapping a local SQLite database or using an external Redis instance.
- **Justification:** The primary engineering value of the project lies in implementing and studying custom eviction algorithms, active/passive sweeper schedules, and thread synchronization from scratch. Wrapping Redis would hide these details.

### 2.3 Consistent Hashing with Virtual Nodes
- **Decision:** Murmur3-32 unsigned hash mapping on a `bisect`-maintained list, registering 150 virtual nodes per physical instance.
- **Alternatives Considered:** Modulo hashing (`hash(key) % N`).
- **Justification:** Modulo hashing causes complete key migration when adding or removing a node. Consistent hashing limits key migrations to approximately $K/(N+1)$ keys, where $K$ is the number of keys and $N$ is the number of nodes. Virtual nodes ensure uniform key distribution across nodes, preventing hotspotting.

### 2.4 Static Cluster Routing & HTTP Forwarding
- **Decision:** Statically configured nodes using `settings.py` and `httpx.Client` for forwarding.
- **The Trade-off:** Peer discovery, Raft consensus, and dynamic replication were excluded from the scope to focus on local consistent hashing routing. HTTP request forwarding via `httpx` introduces connection-pooling overhead, serialization latency, and network failure modes, but matches Cairn's REST-based cluster routing to enable comparable metrics.

### 2.5 Persistence Simulation
- **Decision:** Thread-safe `MockDatabase` with synchronous `write-through` and queue-backed `write-back` workers.
- **Justification:** Demonstrates enterprise persistence patterns. The async `write-back` pipeline uses a thread-safe `queue.Queue` drained by a background daemon thread, decoupling cache writes from simulated database write latencies.

---

## 3. Shard vs. Cairn Comparative Analysis

Shard and Cairn are identical in API contracts and architectural boundaries, but are built on different concurrency runtimes:

| Architectural Metric | Shard (Python/Django) | Cairn (Java/Spring Boot) |
| :--- | :--- | :--- |
| **Concurrency Model** | Interleaved OS Threads under GIL | Native Parallel OS Threads |
| **Synchronization Primitive** | Global `threading.Lock` | `ReentrantReadWriteLock` & `ConcurrentHashMap` |
| **CPU Utilization** | Capped at $100\%$ of a single core | Scales across all available cores |
| **Eviction Pointer Lock** | Protected under the global lock | Isolated eviction policy write-lock |

### Benchmarking Status
The twin architecture was designed to support a controlled comparison, but the repository does not contain a sufficiently controlled benchmark dataset to make a quantitative Shard/Cairn performance claim.

**Required Conditions for Valid Benchmarking:**
- **Workload:** High-concurrency operations (SET/GET mix) with varying key collision rates to evaluate lock contention.
- **Isolation:** Tests must run on the same physical host machine using local loopback interfaces to isolate network latency.
- **Framework Overhead:** The benchmark must differentiate between raw cache engine execution speeds (sub-millisecond in both) and web framework overhead (Django REST Framework vs. Spring Boot WebMVC).

---

## 4. Testing Philosophy

Shard relies on a strict separation of concerns in testing:

### Category A — Unit & Functional Tests
- **Path:** `tests/unit/`
- **Scope:** Fast, deterministic validations targeting isolated components. This includes consistent hashing ring distribution, LRU/LFU eviction accuracy under capacity constraints, passive expiration, mock database pipelines, and Django REST API views.
- **Execution:** `poetry run pytest tests/unit`

### Category B — Concurrency Stress Tests
- **Path:** `tests/concurrency/`
- **Scope:** Heavy, non-deterministic tests using `ThreadPoolExecutor` to execute hundreds of concurrent operations (reads, writes, deletes, and active sweeps) on overlapping keys.
- **Execution:** `poetry run pytest tests/concurrency`
- **Why Isolated:** These tests require spawning multiple threads and sleeping for specific intervals (e.g. to test expiration races). Isolating them ensures the main development test cycles remain fast.

### What the Tests Caught
- **Pointer Safety:** The concurrency tests confirmed that Shard's engine-level lock prevents structural corruption (linked-list cycles, orphaned nodes, out-of-sync size mappings) and double-removal exceptions during concurrent sweeps. No synchronization bugs were caught during implementation because the global lock strategy provides clean isolation.
- **Limits:** These tests provide confidence in pointer integrity and data correctness, but do not guarantee throughput scaling in multi-core hardware environments.

---

## 5. Retrospective: What Would Be Done Differently?

1. **Custom Percentile Metrics Accumulator:**
   Currently, Prometheus client aggregates latencies, but the `/api/v1/metrics/latency` JSON endpoint is tracked in memory using a simple listing. Using a decay-based sliding window accumulator (like a ring-buffer) would provide more accurate real-time percentile metrics under long running workloads.
2. **Lock-Free Read Path via immutable snapshots:**
   Under pure read workloads, acquiring the global engine lock on every `GET` operation limits throughput. If we bypassed promotion (eviction list updates) or used thread-local buffers to queue promotion requests, we could potentially execute read-only GETs concurrently with minimal locking.
3. **Docker Compose for cluster tests:**
   Currently, starting three local nodes requires manual command line executions. Incorporating a pre-configured Docker Compose cluster setup would greatly improve developer experience and test automation.

---

## 6. Key Engineering Lessons

- **State Transition Atomicity:** Thread safety is a property of state transitions, not individual dictionary operations. A Python `dict` operation might be thread-safe at the CPython level, but compound operations require explicit synchronization.
- **GIL & Lock Granularity:** Lock granularity is a correctness/performance trade-off. In a single-core serialized runtime (like CPython with the GIL), fine-grained locking or lock striping degrades performance, making coarse-grained synchronization optimal.
- **Eviction Pointer Mutability:** Eviction algorithms introduce mutable metadata whose pointer consistency is as critical to thread safety as the primary cache index.
- **Controlled Twin Comparisons:** A controlled twin project comparison requires isolating framework-level overhead from engine-level runtime profiles.
- **Stress vs. Unit Testing:** Concurrency stress tests verify structural safety and pointer integrity rather than throughput capacities.
