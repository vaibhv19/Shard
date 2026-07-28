# Architecture Comparison: Synod (Django) vs. Conclave (Spring Boot)

This document serves as a technical post-mortem and architectural analysis comparing the implementation of the Multi-Provider Context Unification pattern in two disparate ecosystems: **Python/Django** and **Java/Spring Boot**.

The goal of this comparison is to move beyond language preference and identify the concrete engineering trade-offs inherent in the frameworks’ respective approaches to real-time, asynchronous I/O, and state orchestration.

---

## 1. Real-time Layer: Django Channels vs. Spring STOMP

The most significant divergence between the two projects lies in how they handle the lifecycle of a WebSocket connection.

| Feature | Synod (Django Channels) | Conclave (Spring WebSockets) |
| :--- | :--- | :--- |
| **Protocol** | Raw WebSockets with custom JSON dispatch. | STOMP (Simple Text Oriented Messaging Protocol). |
| **Infrastructural Req.** | **Mandatory Redis Backing Store.** Channels requires a separate Channel Layer to broadcast across processes. | **None (Optional).** Uses an in-memory Simple Broker by default for local development. |
| **Entry Point** | `ChatConsumer(AsyncJsonConsumer)`: Low-level event handling. | `@MessageMapping` Controllers: High-level, Spring MVC-style routing. |
| **Server Requirements**| **ASGI (Daphne).** Must bridge the synchronous Django core with an async web server. | **Standard Servlet Container.** (Tomcat/Netty) natively handles the upgrade to WS. |

**Key Insight:** Django Channels is explicit. You must manually manage the Redis backplane and the grouping of channels. Spring is more implicit, providing a higher-level abstraction that feels closer to conventional MVC routing.

---

## 2. Adapter/Validation: DRF Serializers vs. Spring Bean Validation

To implement the **Provider Adapter Pattern**, both systems must validate and transform a canonical message into vendor-specific JSON (Gemini/OpenAI/Claude).

*   **Synod (DRF Serializers):** Utilizes declarative Serializer classes. The transformation logic lives in `to_representation()` and custom `validate()` methods. Python’s dynamic nature allows the serializer to act as a highly flexible transformer that can reshape dictionaries on the fly without strict type definitions.
*   **Conclave (Spring Data DTOs):** Relies on POJOs decorated with JSR-380 annotations (`@NotNull`, `@Valid`). Transformation requires explicit mapping classes or manual builder patterns.

**The Comparison:** DRF Serializers are more powerful for schema-shifting, making them ideal for the Adapter pattern. However, Conclave provides compile-time safety; if a provider API change is reflected in the DTO, the build fails immediately. Synod relies on runtime unit tests to catch the same errors.

---

## 3. Concurrency Model: Asyncio Event Loop vs. Virtual Threads

This section addresses how each system handles the waiting period during long-running LLM API calls.

*   **Synod (Asyncio/ASGI):** Uses a single-threaded event loop. When an LLM call is made, the consumer `awaits` the response, yielding the thread back to the loop to handle other WebSocket frames.
    *   *Risk:* Any CPU-bound task such as heavy message summarization can block the loop, causing latency for every other connected user.
*   **Conclave (Virtual Threads - Java 21):** Uses lightweight threads that map many-to-one onto carrier threads. Blocking I/O looks synchronous in code but the JVM transparently yields the carrier thread.
    *   *Advantage:* Easier to reason about. You can use standard blocking libraries without worrying about saturating an event loop.

---

## 4. Runtime Shape: ASGI vs. JAR

*   **Synod:** Requires an ASGI/WSGI split. Standard Django views are often handled by WSGI, while WebSockets must be handled by ASGI (Daphne). This results in a split runtime where the developer must ensure both servers are configured and potentially sharing a Redis-based session store.
*   **Conclave:** Ships as a single fat JAR. The same embedded server handles both standard REST and the WebSocket upgrade. The runtime is unified, simplifying containerization and local orchestration.

---

## 5. Concrete Friction Points (Implementation Log)

*   **Finding #1: The Sync-to-Async Bridge**
    *   *Issue:* Accessing the Django ORM inside an `async` consumer requires `database_sync_to_async` wrappers.
    *   *Friction:* This adds boilerplate and mental overhead compared to a more conventional thread-based request flow.
*   **Finding #2: Custom JSON Routing**
    *   *Issue:* Because Synod uses raw WebSockets instead of STOMP, I had to build a custom `action` dispatcher in the consumer.
    *   *Friction:* This re-creates some of the routing work that STOMP usually handles for you.
*   **Finding #3: Redis Dependency for Local Dev**
    *   *Issue:* Synod cannot run its real-time features without a Redis container.
    *   *Friction:* This increases the complexity of the local development setup compared with a more self-contained runtime.
*   **Finding #4: Dynamic Adapter Mapping**
    *   *Issue:* Mapping roles to providers was achieved via a Python dictionary acting as a Model Registry.
    *   *Comparison:* This felt more intuitive and less ceremonial than a more explicit dependency-injection-based approach.
*   **Finding #5: Serialization Overhead**
    *   *Issue:* Using DRF Serializers to format 50+ messages in a conversation history showed noticeable latency.
    *   *Optimization:* Had to optimize the ORM query with `select_related` to avoid N+1 issues during serialization.

---
*This document assumes Conclave (Java) is built on Spring Boot 3.3 and Java 21 Virtual Threads. Any divergence in Conclave's actual implementation should be noted as an assumption to verify.*