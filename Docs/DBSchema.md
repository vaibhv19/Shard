# Data Model & Schema Document — Shard (Distributed Cache Service)

## Document Control
* **Document Version:** 0.1.0
* **Status:** Draft
* **Authors:** Portfolio Owner / Technical Architect
* **Milestone Reference:** v0.1.0 (Docs Complete)
* **Twin Project Reference:** [Cairn DB Schema](file:///d:/Coding/Projects----For%20Resume/Cairn/Docs/DBSchema.md)

---

## 1. Database Non-Goals & In-Memory Scope

Shard is built strictly as a transient, high-speed, in-memory cache engine.

> [!IMPORTANT]
> **No Database / Persistence Layer:** Shard does not connect to any SQL or NoSQL database (such as SQLite, PostgreSQL, or MongoDB) for core caching, nor does it write backup files to local disk storage (like Redis RDB snapshots or Append-Only Files). All cache entries are held in volatile Python process memory space. A restart of the Django server process clears the cache completely.

---

## 2. In-Memory Data Structures

Data is stored in-memory inside the `CacheEngine` utilizing standard Python structures. Below is the definition of the storage schema.

### 2.1 The Key-Value Map Registry
* **Collection:** Standard Python `dict`
* **Primary Key:** `str` (The cache key)
* **Value Record:** `CacheEntry` (An object encapsulating the payload and policy tracking metadata)

---

### 2.2 CacheEntry Structure
The `CacheEntry` class defines the structural "schema" of every cached record in memory.

```
+-------------------------------------------------------+
|                      CacheEntry                       |
+-------------------------------------------------------+
| - value: str (Payload)                                |
| - created_time: float (Epoch seconds)                 |
| - expiry_time: float (Epoch seconds)                  |
+-------------------------------------------------------+
```

| Field Name | Python Data Type | Nullability | Purpose / Usage |
| :--- | :--- | :--- | :--- |
| **`value`** | `str` | Non-Null | The actual cached value payload. Serialized JSON format is recommended for complex structures. |
| **`created_time`** | `float` | Non-Null | Epoch timestamp in seconds (from `time.time()`) indicating when the key was written to the cache. |
| **`expiry_time`** | `float` | Non-Null | Epoch timestamp in seconds when the key is considered stale. If no TTL is set, this is configured to `float('inf')`. |

*(Note: Prior versions included `last_access_time` and `access_frequency` fields on `CacheEntry`. These were removed as redundant, since LRU/LFU eviction strategies manage their own metadata indexing and mapping structures independently.)*

---

## 3. Eviction Metadata Structures

To perform $O(1)$ evictions without iterating over the entire dictionary, the swappable eviction policies maintain dedicated internal pointer index schemas.

### 3.1 LRU (Least Recently Used) Schema
The LRU eviction strategy tracks access recency using a custom doubly-linked list.

```
Head (Most Recent) <---> Node <---> Node <---> Tail (Least Recent / Victim)
```

* **Node Record Map:** `dict[str, LruNode]` (Holds pointers to list nodes for $O(1)$ lookups)
* **LruNode Structure:**
  * `key`: `str` (Referencing the cache key)
  * `prev`: `LruNode` pointer (or `None`)
  * `next`: `LruNode` pointer (or `None`)

---

### 3.2 LFU (Least Frequently Used) Schema
The LFU eviction strategy tracks access frequency using a frequency-bucket list.

```
Freq [1] Bucket <---> Freq [2] Bucket <---> Freq [N] Bucket
     |                     |                     |
  Keys [k1, k2]         Keys [k3]             Keys [k4, k5]
```

* **Node Map:** `dict[str, LfuNode]`
* **Frequency Table:** `dict[int, OrderedDict[str, bool]]` (Maps access frequency to an `OrderedDict` representing a linked set of keys, preserving LRU order within the same frequency bucket)
* **Min Frequency Index:** `int min_frequency` (Maintains a pointer to the lowest frequency list containing keys, ensuring $O(1)$ extraction of the eviction victim)

---

## 4. Open Questions / Future Considerations (Phase 3 Metrics)

During Phase 3, metrics dashboards aggregate hit/miss ratios and memory statistics.
* **Problem Statement:** If the cache server crashes or restarts, historical operational metrics are lost, preventing long-term performance comparisons between policy configurations.
* **Proposed Future Database Addition:** If persistent metrics are requested, the system will hook into an in-memory SQL database (such as **SQLite**) to log metrics snapshots:
  
  ```sql
  CREATE TABLE cache_metrics_snapshot (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      snapshot_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
      node_identifier VARCHAR(100) NOT NULL,
      policy_type VARCHAR(10) NOT NULL, -- 'LRU' or 'LFU'
      total_keys INT NOT NULL,
      hit_ratio REAL NOT NULL,
      total_evictions INT NOT NULL,
      memory_bytes INTEGER NOT NULL
  );
  ```
* **Status:** This persistence layer remains **unimplemented** and serves only as a design reference for Phase 3 metrics aggregation extensions.
