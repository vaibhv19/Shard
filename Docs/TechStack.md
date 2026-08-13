# Tech Stack Document — Shard (Distributed Cache Service)

## Document Control
* **Document Version:** 0.1.0
* **Status:** Draft
* **Authors:** Portfolio Owner / Technical Architect
* **Milestone Reference:** v0.1.0 (Docs Complete)
* **Twin Project Reference:** [Cairn Tech Stack](file:///d:/Coding/Projects----For%20Resume/Cairn/Docs/TechStack.md)

---

## 1. Concurrency Model Resolution

The Shard PRD left the core concurrency architecture as an open design decision between **Option A (Thread-based Locking)** and **Option B (Async Event Loop)**. For the Shard implementation, we explicitly resolve this in favor of **Option A: Thread-based Locking**.

### 1.1 Concurrency Model Choice: Thread-Based Locking (Django WSGI + Python `threading` & `threading.Lock`)
This model processes concurrent requests via OS-level threads managed by a WSGI application server (e.g., Gunicorn with threaded workers). Cache operations run synchronously and access shared in-memory structures protected by explicit mutexes.

### 1.2 Justification & Trade-off Analysis

The primary objective of Shard is to serve as a direct comparative twin to Cairn (implemented in Spring Boot/Java). The goal is to study how Python's runtime limitations (the GIL) impact concurrent performance compared to Java's true hardware-parallel execution under identical features and API contracts.

| Dimension | Option A: Thread-Based Locking (Chosen) | Option B: Async Event Loop (Rejected) |
| :--- | :--- | :--- |
| **Architectural Symmetry** | **High.** Directly mirrors Cairn's model of concurrent OS threads accessing shared, lock-protected memory. | **Low.** Changes the architecture to a single-threaded cooperative event loop, departing from Cairn's design. |
| **GIL Exposure** | **Maximum.** Multiple OS threads will actively compete for the GIL, exposing context-switching latency and interpreter bottlenecks under load. | **Low.** The event loop runs on a single thread. The GIL is never contended within the process since execution is cooperative. |
| **Lock Complexity** | **Required.** Must write explicit synchronization blocks (`threading.Lock` / `RLock`) to prevent state corruption across threads. | **Avoided.** No locks are needed for synchronous cache operations because no two tasks execute bytecode at the same instant. |
| **Benchmark Validity** | **True Comparison.** Measures "Python Thread Locking under the GIL vs. Java Thread Locking on the JVM." | **Diluted Comparison.** Measures "Python Cooperative Async vs. Java Pre-emptive Thread Parallelism," introducing an extra variable. |

By choosing **Option A**, we preserve the exact synchronization boundaries found in Cairn. This allows technical reviewers to compare how locking the same critical sections performs under the JVM's multi-core execution versus Python's single-core serialized execution.

---

## 2. Core Language & Framework

```
+-------------------------------------------------------+
|                 Python 3.12+ Interpreter (GIL)        |
|  +-------------------------------------------------+  |
|  |           Django 5.x (WSGI Server)              |  |
|  |  +-------------------------------------------+  |  |
|  |  |      Django REST Framework 3.15.x         |  |  |
|  |  +-------------------------------------------+  |  |
|  +-------------------------------------------------+  |
+-------------------------------------------------------+
```

### 2.1 Language: Python 3.12+
* **Justification:** Python 3.12 introduces key interpreter performance enhancements, improved garbage collection, and clearer error tracebacks.
* **Key Language Features Utilized:**
  * **OS Threads (`threading`):** Utilized to execute concurrent request handlers and run the background active expiry sweeps.
  * **Locks (`threading.Lock`, `threading.RLock`):** Primitives to protect in-memory cache segments and eviction pointers from thread race conditions.
  * **Type Hinting & Protocols (`typing`):** Leveraged to implement the pluggable eviction strategy interface via duck typing/static analysis.

### 2.2 Framework: Django 5.x & Django REST Framework (DRF) 3.15.x
* **Justification:** Django provides a robust configuration system, middleware support, and standard WSGI request dispatching. Django REST Framework provides clean HTTP routing and serialization.
* **Core Modules Used:**
  * **Django WSGI Request Handler:** Dispatches incoming HTTP requests to separate threads inside Gunicorn.
  * **DRF API Views:** Exposes the `SET`, `GET`, `DELETE`, `EXISTS`, `EXPIRE`, and `TTL` endpoints. DRF handles HTTP request parsing and JSON serialization, keeping it strictly decoupled from the core cache engine.
  * **Django Settings System:** Controls cache capacity, eviction strategy selection (`LRU` vs. `LFU`), and TTL background sweep intervals.

---

## 3. Concurrency Primitives & Internal Storage

To implement the caching engine without external database dependencies, Shard uses Python's standard library primitives. The table below maps Shard's synchronization components to their Cairn equivalents:

| Cache Component | Python / Shard Choice | Spring Boot / Cairn Equivalent | Architectural Role / Justification |
| :--- | :--- | :--- | :--- |
| **Primary Index** | Python `dict` + `threading.Lock` | `ConcurrentHashMap<K, V>` | The core dictionary maps keys to values. Because Python's `dict` is not thread-safe for compound operations (e.g. check-and-act), a lock coordinates writes and reads. |
| **Eviction Pointers** | Custom doubly-linked list + `threading.Lock` | `ReentrantReadWriteLock` | Coordinates LRU promotion (updates on read) and LFU bucket shifting. Because python lacks a native `ReadWriteLock`, a standard lock or reader-writer lock wrapper will protect pointer modifications. |
| **Active Expiration** | Background Daemon Thread | `ScheduledExecutorService` | A dedicated background thread executes a loop, sleeping for configured intervals, sampling keys, and purging expired entries. |
| **Operation Counters** | Custom Atomic Counter | `LongAdder` | Tracks hit/miss counts. Implemented via lock-protected variables to avoid value corruption during concurrent increments. |

---

## 4. Build & Dependency Management

### 4.1 Build Tool: Poetry
* **Justification:** Poetry provides deterministic dependency locking (`poetry.lock`) and a clean `pyproject.toml` configuration, mimicking Maven's structured dependency tree and reproducible builds.
* **Key Dependencies:**
  * `django`: Core web framework.
  * `djangorestframework`: REST API exposure.
  * `prometheus-client`: Instrumenting hit/miss ratios, latencies, and active cache keys.
  * `pytest` & `pytest-django`: Unit and concurrent testing framework.

---

## 5. Testing & Verification Stack

To verify safety under concurrent load, the testing stack is divided into distinct suites:

* **Unit Testing:** **`pytest`** for validating functional behavior (e.g., verifying LRU and LFU discard the correct key under capacity limits in isolation).
* **Concurrent Stress Testing:** A custom script utilizing **`concurrent.futures.ThreadPoolExecutor`** to spawn 100+ parallel OS threads hitting the cache core. This suite checks for data race conditions, memory visibility issues, or pointer corruption.
* **API Benchmarking:** **`wrk`** or **`locust`** running locally to push concurrent HTTP requests against the Django REST API, measuring throughput plateaus and tail latencies ($p99$).

---

## 6. Observability & Monitoring

* **`prometheus_client` for Python:** Instruments the cache core. It records cache hits, misses, evictions, latency histograms, and estimated memory footprint.
* **DRF Metrics Endpoint:** A dedicated endpoint `/metrics` exposes these values in the standard Prometheus format, allowing a local Prometheus instance to scrape it and render data in a Grafana dashboard.

---

## 7. Technology Non-Goals
* **No Database/ORM Drivers:** Shard is strictly in-memory. The Django ORM and database configurations (`sqlite`, `postgres`) are completely disabled at runtime.
* **No Redis wrapper:** All cache maps, eviction queues, and expiration logic are written in pure Python.
* **No Distributed Consensus Engine (e.g., Raft):** Nodes in the Phase 2 sharded cluster do not perform dynamic peer-to-peer communication. Topology is defined statically in configurations.

---

## 8. "Why Not" Analysis (Architectural Trade-Offs)

### 8.1 Why not Multiprocessing instead of Multithreading?
* **Rejected Alternative:** Spawning separate Python processes (via `multiprocessing`) to bypass the GIL and leverage multiple CPU cores.
* **Trade-Off Analysis:**
  * *Memory Isolation:* Processes do not share memory space natively. Sharing cache data would require Inter-Process Communication (IPC), Unix sockets, or shared memory managers (`multiprocessing.shared_memory`).
  * *Latency Overhead:* IPC introduces significant serialization and context-switching overhead, inflating latency beyond sub-millisecond bounds.
  * *Purpose Alignment:* Using processes sidesteps the GIL. The fundamental academic purpose of Shard is to show how standard, GIL-limited Python threads execute concurrent memory lookups against Java's concurrent threads. Multiprocessing violates this core comparison.

### 8.2 Why not Asyncio (Option B)?
* **Rejected Alternative:** Implementing an asynchronous cache service using Django's ASGI mode and Python's `asyncio`.
* **Trade-Off Analysis:**
  * *Synchronization Overhead:* An async system runs on a single event-loop thread, eliminating OS thread locks. This removes the synchronization overhead, which is the core engineering challenge of the twin project.
  * *GIL Bottleneck Behavior:* Without thread locking and kernel-level context switching, we cannot measure GIL wait times and scheduler contention, which are the main metrics in our comparative benchmarking with Cairn.
