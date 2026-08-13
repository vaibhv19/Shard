# Folder Structure Document — Shard (Distributed Cache Service)

## Document Control
* **Document Version:** 0.1.0
* **Status:** Draft
* **Authors:** Portfolio Owner / Technical Architect
* **Milestone Reference:** v0.1.0 (Docs Complete)
* **Twin Project Reference:** [Cairn Folder Structure](file:///d:/Coding/Projects----For%20Resume/Cairn/Docs/FolderStructure.md)

---

## 1. Project Directory Layout

Shard follows a clean Django project directory layout, separating Django REST API handlers (`cache_app/`) from the core cache engine package (`engine/`), and isolating standard tests from concurrent stress tests.

```
shard/
├── .git/
├── Docs/                                # Complete Documentation Suite
│   ├── Shard — Feature List.md
│   ├── PRD.md
│   ├── TechStack.md
│   ├── SystemArchitecture.md
│   ├── AppFlow.md
│   ├── UIDesign.md
│   ├── FolderStructure.md
│   ├── DBSchema.md
│   └── APIContracts.md
├── manage.py                            # Django management script
├── pyproject.toml                       # Poetry package configuration
├── poetry.lock                          # Dependency lockfile
├── shard_project/                       # Django project configuration
│   ├── __init__.py
│   ├── settings.py                      # Global cache limits & sweeps configs
│   ├── urls.py                          # Global URL dispatch registry
│   └── wsgi.py                          # WSGI Gunicorn entry point
├── cache_app/                           # Django App (HTTP REST Layer)
│   ├── __init__.py
│   ├── apps.py
│   ├── urls.py                          # Cache route mappings
│   ├── views.py                         # DRF API controller views
│   ├── serializers.py                   # DRF payload serializers
│   └── exceptions.py                    # API error responders
└── engine/                              # Pure Python Cache Engine Core
    ├── __init__.py
    ├── cache_engine.py                  # Coordinates dict store & eviction Strategy
    ├── cache_entry.py                   # Data class wrapping payload & metadata
    ├── mock_database.py                 # Phase 3 mock backing database
    ├── evict/                           # Eviction Strategy Pattern
    │   ├── __init__.py
    │   ├── strategy.py                  # Base protocol/duck-type class
    │   ├── lru_eviction.py              # LRU doubly-linked list strategy
    │   └── lfu_eviction.py              # LFU frequency-bucket list strategy
    ├── expire/                          # Expiration Sweeper Subsystem
    │   ├── __init__.py
    │   └── active_expiry.py             # Active sweep daemon thread
    ├── sharding/                        # Phase 2 Consistent Hashing Ring
    │   ├── __init__.py
    │   ├── consistent_hash.py           # TreeMap-style ring using bisect
    │   └── router.py                    # Static proxy/client router
    └── metrics/                         # Phase 3 Telemetry
        ├── __init__.py
        └── collector.py                 # prometheus_client metrics wrappers
tests/                                   # Isolation Test Suites
├── __init__.py
├── unit/                                # Standard functional unit tests
│   ├── test_cache_engine.py
│   ├── test_lru_eviction.py
│   ├── test_lfu_eviction.py
│   ├── test_active_expiry.py
│   ├── test_consistent_hash.py
│   └── test_api.py
└── concurrency/                         # High-contention GIL & Lock stress tests
    ├── test_concurrent_engine.py
    ├── test_concurrent_expiry.py
    └── test_lock_contention.py
```

---

## 2. Component Directory Descriptions

### 2.1 Cache Engine & Strategy (`/engine`)
* **`cache_engine.py`**: The core cache engine class coordinating dictionary lookups under a global lock. It calls the swappable eviction strategies when capacity thresholds are crossed.
* **`cache_entry.py`**: Represents the in-memory Python object stored inside the dictionary. Holds the value payload, expiration timestamp, last-access timestamp, and frequency counter.
* **`evict/`**: Implements the Strategy Pattern. Uses Python protocols or static classes to provide swap-in LRU/LFU engines without altering core engine loops.

### 2.2 API Layer (`/cache_app`)
* **`views.py`**: Django REST Framework API views that process incoming requests, authenticate, validate, call the cache engine, and return responses.
* **`serializers.py`**: Serializers that perform input formatting, key/value sizes verification, and positive-integer TTL validation.
* **`exceptions.py`**: Maps errors (e.g. key missing, eviction failures) to exact REST response bodies and status codes.

### 2.3 Expiration & Sweeps (`/engine/expire`)
* Contains tasks and thread workers that run in the background. Operates the active sweep loop using daemon threads that run concurrently alongside WSGI request handlers.

### 2.4 Sharding & Consistent Hashing (`/engine/sharding`)
* Manages virtual node mappings on the hashing ring using Python's `bisect` library to find target physical servers.

### 2.5 Metrics & Invalidation (`/engine/metrics`)
* Integrates `prometheus_client` to record operations stats (hits, misses, tail latencies, sweep counts) and provides manual wildcard invalidation operations.

---

## 3. Test Isolation Directory Design

To verify concurrency safety without slowing down standard local development, the testing directory is split into two independent modules:

1. **Standard Unit Tests (`tests/unit/`):** Contains fast, single-threaded tests that run in milliseconds. Verifies LRU list transitions, LFU bucket shifting, TTL math, and consistent hashing boundaries in isolation.
2. **Concurrency & Stress Tests (`tests/concurrency/`):** Spawns 100+ OS-level threads (via `concurrent.futures.ThreadPoolExecutor`) to execute parallel GET/SET requests on shared keys. These tests stress the `threading.Lock` primitives under the Python GIL to ensure that pointer corruptions, lock-waiting lockouts, or key collisions do not occur, verifying the cache's core concurrency safety.

---

## 4. `/docs` Folder Inventory

The `/Docs` folder contains the complete documentation suite for the Shard project:
* **`PRD.md`**: Core requirements, twin project comparisons (GIL vs. JVM), scope boundaries, and open questions.
* **`TechStack.md`**: Architectural justifications for Python, Django + DRF, Poetry, pytest, and thread-based locking.
* **`SystemArchitecture.md`**: High-level component layouts, synchronization boundaries, sharding ring setup, and a comparison table with Cairn.
* **`AppFlow.md`**: Sequence of operations, thread locks, active sweeps, proxy routing, and metrics counter updates.
* **`UIDesign.md`**: API JSON layouts and Phase 3 operator metrics dashboard design.
* **`FolderStructure.md`**: Django project structure, package layouts, and test directories (this document).
* **`DBSchema.md`**: In-memory data structures, metadata properties, and persistence non-goals.
* **`APIContracts.md`**: URL routes, payload contracts, validation rules, and error return formats.
