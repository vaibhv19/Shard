# App Flow Document — Shard (Distributed Cache Service)

## Document Control
* **Document Version:** 0.1.0
* **Status:** Draft
* **Authors:** Portfolio Owner / Technical Architect
* **Milestone Reference:** v0.1.0 (Docs Complete)
* **Twin Project Reference:** [Cairn App Flow](file:///d:/Coding/Projects----For%20Resume/Cairn/Docs/AppFlow.md)

---

## 1. MVP Single-Node Core Request Lifecycles

All client requests enter via Django WSGI handlers. Below are the sequential steps executed inside the Python interpreter for each core cache operation under **Option A: Thread-based Locking**.

### 1.1 GET Request Flow
1. **HTTP Ingest:** The client calls `GET /api/v1/cache/{key}`. The WSGI server (e.g., Gunicorn) allocates an OS thread to process the request.
2. **Lock Acquisition:** The thread acquires the cache instance's global `threading.Lock` to guarantee structural isolation.
3. **Registry Lookup:** The engine queries the standard Python dictionary: `dict.get(key)`.
4. **Existence Check:**
   * **If Key Absent:** The engine increments the `misses` counter, releases the global lock, and returns a `404 Not Found` REST response.
   * **If Key Present:** The engine extracts the cache entry containing the payload and metadata (expiry timestamp, access frequency, access timestamp).
5. **TTL Expiration Check (Passive Expiry):**
   * The thread compares the current epoch timestamp `time.time()` against the entry's `expiryTime`.
   * **If Expired:**
     * The thread deletes the entry from the primary dictionary.
     * It removes the key metadata from the eviction strategy strategy object (e.g., deletes its node from the LRU doubly-linked list).
     * It increments the `misses` and `ttl_evictions` counters.
     * It releases the global lock and returns a `404 Not Found` REST response.
6. **Eviction Metadata Update (Promotion):**
   * **If Valid (Not Expired):** The thread updates the key's access tracking stats:
     * **LRU:** Relocates the key's node to the head of the doubly-linked list.
     * **LFU:** Increments the reference frequency count and moves the key to its corresponding frequency list/node.
7. **HTTP Response:** The engine increments the `hits` counter, releases the global lock, and returns the cached value with `200 OK`.

---

### 1.2 SET Request Flow
1. **HTTP Ingest:** The client calls `POST /api/v1/cache` with `{ "key": "k", "value": "v", "ttl": 60 }`.
2. **Lock Acquisition:** The thread acquires the cache instance's global `threading.Lock`.
3. **Lookup & Update:** The engine checks if the key already exists in the primary dictionary.
   * **If Existing:**
     * The thread overwrites the value, updates the expiration time (`time.time() + ttl`), and resets/updates access statistics in the eviction strategy object.
     * The thread releases the global lock, increments write metrics, and returns `200 OK`.
   * **If New:**
     * The thread proceeds to the **Capacity Check**.
4. **Capacity Check & Eviction:**
   * The engine checks if `len(cache_dictionary) >= maxCapacity`.
   * **If Over Capacity:**
     * The engine requests the eviction strategy object (LRU/LFU) to select the victim key (the tail of the LRU list, or the head of the lowest LFU frequency list).
     * The engine deletes the selected victim key from the primary dictionary and eviction strategy tracking.
     * Increments the `policy_evictions` counter.
5. **Insert Entry:**
   * The thread creates the cache entry object and inserts it into the primary dictionary.
   * It inserts the key metadata node into the eviction strategy tracking (head of LRU list, or frequency 1 list of LFU).
6. **HTTP Response:** The thread releases the global lock and returns `201 Created` with the key metadata.

---

### 1.3 DELETE Request Flow
1. **HTTP Ingest:** The client calls `DELETE /api/v1/cache/{key}`.
2. **Engine Execution:**
   * The thread acquires the cache instance's global `threading.Lock`.
   * **If Key Not Found:** Releases the global lock and returns `404 Not Found`.
   * **If Key Found:**
     * Removes the key from the primary dictionary.
     * Removes the key's metadata node from the eviction strategy list.
     * Deletes active TTL configurations.
3. **HTTP Response:** The thread releases the global lock and returns `204 No Content`.

---

### 1.4 EXISTS / EXPIRE / TTL Request Flows
* **EXISTS (`GET /api/v1/cache/{key}/exists`):**
  1. Acquires the global lock and executes the passive-expiry check.
  2. If valid, releases the lock and returns `200 OK` with `{ "exists": true }`. Does *not* trigger LRU/LFU promotions, ensuring audit checks do not poison access patterns.
  3. If absent, releases the lock and returns `200 OK` with `{ "exists": false }`.
* **EXPIRE (`POST /api/v1/cache/{key}/expire`):**
  1. Acquires the global lock and checks dictionary presence.
  2. If present, updates the expiration timestamp (`time.time() + requested_ttl`). Releases the lock and returns `200 OK`.
  3. If absent, releases the lock and returns `404 Not Found`.
* **TTL (`GET /api/v1/cache/{key}/ttl`):**
  1. Acquires the global lock and runs the passive-expiry check.
  2. If valid, calculates remaining seconds (`expiryTime - time.time()`) and returns `{ "ttl_remaining": seconds }` with `200 OK`. If the key has no expiry, returns `{ "ttl_remaining": -1 }`. Releases the lock.
  3. If absent, releases the lock and returns `404 Not Found`.

---

## 2. Concurrency Contention Paths

Under **Option A: Thread-based Locking**, the Python interpreter schedules OS-level threads. Because of the GIL, execution is time-sliced on a single core, and locks serialize critical section access.

### 2.1 Read/Write Contention (Same Key)
```
Thread 1 (SET Key "User1")                  Thread 2 (GET Key "User1")
       |                                           |
       v                                           v
Acquire global threading.Lock               Try to acquire global Lock
Modifies cache dictionary                   - (Blocked, waiting for lock release)
Updates LRU list                            - 
Release global threading.Lock               - 
       |                                   Acquires global Lock
       v                                   Runs passive expiry check
(Write Complete)                           Finds key & updates LRU list promotion
                                           Release global threading.Lock
                                           Return value
```

### 2.2 Active Background Expiry Sweep Flow
The active expiration daemon thread runs concurrently alongside WSGI request threads:
1. **Trigger:** The background sweep thread wakes up at configured intervals (e.g., every 5 seconds).
2. **Lock & Sample:** The thread acquires the global `threading.Lock` and pulls a random sample of $N$ keys (e.g., 20 keys) from the dictionary.
3. **Inspection:** For each key in the sample:
   * It checks if `time.time() > expiryTime`.
   * **If Valid:** Skips the key.
   * **If Expired:**
     * Removes the key from the dictionary.
     * Removes the key from the LRU/LFU tracking lists.
     * Increments the `ttl_evictions` metrics counter.
4. **Lock Release & Cycle:** The thread releases the global `threading.Lock`.
5. **Adaptive Loop:** If more than $25\%$ of the sampled keys were expired, it immediately acquires the lock again to run another cycle, protecting memory from sudden expiration spikes. If less than $25\%$ were expired, the thread sleeps. By releasing the lock between cycles, HTTP request threads can execute, preventing lock exhaustion.

---

## 3. Phase 2 Distributed Hashing Flows

### 3.1 Distributed Key Routing Flow
```
Client Request -> [Routing Proxy] 
                       |
                       v
             Hash Key (Murmur3) -> Hash Value H
                       |
                       v
          bisect_right(H) Ring Search
                       |
                       v
         Retrieve target Physical Node IP
                       |
                       v
             Proxy Request to Target Node
```

### 3.2 Dynamic Static-Node Modification (Rebalancing Flow)
When the static node configuration in Django settings is updated:
1. **Initialization:** Operator triggers a reload command.
2. **Ring Recalculation:** The routing layer clears the current ring, reads the new list of nodes, hashes the new virtual nodes, and populates the ring.
3. **Request Distribution Change:**
   * Future GET/SET requests map via the new ring.
   * Keys whose virtual mappings didn't shift continue to hit their previous node (cache hits).
   * Shifted keys yield cache misses on the new node, triggering client-side write-backs that migrate key ownership naturally.

---

## 4. Phase 3 Invalidation & Metrics Flows

### 4.1 Write-Through vs. Write-Back Operations
* **Write-Through Flow:**
  1. Client sends write command to API.
  2. Cache thread acquires the lock and writes to the local cache dictionary.
  3. Cache thread synchronously executes an HTTP write call to the mock database.
  4. Once both write calls complete, the thread releases the lock and returns `201 Created`.
* **Write-Back (Write-Behind) Flow:**
  1. Client sends write command to API.
  2. Cache thread acquires the lock, writes to the local cache dictionary, and appends the write event to a thread-safe `queue.Queue`.
  3. Thread releases the lock and immediately returns `201 Created`.
  4. An independent background worker thread continually drains `queue.Queue` and pushes updates to the mock database asynchronously.

### 4.2 Metrics Collection Pipeline
1. An event occurs in the cache engine (e.g., Cache Hit).
2. The engine calls `metrics_collector.record_hit()`.
3. The metrics collector increments the counter inside the Prometheus client registry. Since simple numeric updates in Python are executed within atomic C-bytecode steps, metrics aggregation introduces minimal latency.
4. Every 10 seconds, the Prometheus server scrapes the `/metrics` endpoint, which translates internal telemetry to standard text formats.
