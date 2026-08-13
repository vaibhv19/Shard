# Shard — Feature List

**Project Name:** Shard (Distributed Cache Service — Python/Django build)  
**Stack:** Python + Django + Django REST Framework + threading/asyncio (concurrency model TBD during scoping)  
**Core Differentiator:** Custom in-memory cache engine built from scratch (no wrapping Redis) — pluggable eviction policies, consistent-hashing based sharding, and safe concurrent access reasoned about explicitly under Python's threading/GIL model.

---

## MVP (Build First)

*   **In-Memory Key-Value Store Core** — A thread-safe hash map supporting `SET`/`GET`/`DELETE`/`EXISTS` (single-node only, no persistence).
*   **Pluggable Eviction Policies** — LRU and LFU implemented as swappable strategies (interface/duck-typed policy object), selectable per cache instance.
*   **TTL Expiry** — Per-key expiration set at write time; both passive expiry (checked on access) and active expiry (background sweep thread/task).
*   **Concurrency Safety** — Correct simultaneous reads/writes from multiple clients hitting the same node; explicit reasoning about the GIL's effect on true parallelism (thread-based locking vs. an async event-loop-per-node model — decide and document the tradeoff rather than assuming naive thread safety is "free").
*   **Client-Facing API** — `SET`/`GET`/`DELETE`/`EXISTS`/`EXPIRE`/`TTL` exposed over HTTP via Django views/DRF.
*   **Core Engineering** — Eviction and expiry logic must stay correct under concurrent access; no silently corrupting cache state, and no evicting or expiring the wrong key due to a race condition.

---

## Phase 2 — Sharding & Distribution
*Scoped honestly, not a full Redis Cluster reimplementation*

*   **Consistent Hashing Ring** — Routes keys deterministically to one of several cache-node processes.
*   **Routing Layer** — A thin proxy or client-side hashing library that resolves which node owns a given key.
*   **Static Node Membership** — Node list comes from config; explicitly scoped as "consistent-hashing based static sharding, not dynamic cluster membership or a gossip protocol."
*   **Rebalancing Behavior** — Documented (and at minimum partially implemented) behavior for what happens to key ownership when a node is added or removed.

---

## Phase 3 — Invalidation Strategies & Metrics Dashboard

*   **Cache Invalidation Strategies** — Explicit invalidate command, write-through vs. write-back semantics, TTL-based passive invalidation.
*   **Metrics Collection** — Hit/miss ratio, eviction count, per-node memory usage, latency percentiles.
*   **Metrics Dashboard** — Aggregates across nodes; useful for comparing eviction-policy configurations against each other (e.g. "does LFU reduce miss rate vs LRU for this access pattern?").
