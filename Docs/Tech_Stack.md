# Tech Stack Specification: Synod

This document outlines the technical specifications for **Synod**. The stack is selected to facilitate a direct comparison between Python’s asynchronous ecosystem and the Java/Spring architecture of **Conclave**.

---

## 1. Backend Orchestration (Django)

| Component | Technology | Version | Rationale | Comparison to Conclave |
| :--- | :--- | :--- | :--- | :--- |
| **Language** | **Python** | `3.12` | Native support for `async/await` is critical for non-blocking AI API calls. | Conclave used **Java 21**; Python is used here to test the "dynamic vs. static" developer velocity. |
| **Framework** | **Django** | `5.0` | Provides a "batteries-included" ORM and admin for rapid schema management. | Conclave used **Spring Boot 3.3**; Django is chosen to contrast rapid-prototyping with Java's DI-heavy setup. |
| **API Layer** | **DRF** | `3.15` | Serializers provide a robust way to validate complex, multi-provider JSON payloads. | Conclave used **Jackson/DTOs**; DRF Serializers replace Java's strictly-typed POJOs for schema translation. |
| **Authentication** | **SimpleJWT** | `5.3` | Enables stateless token-based auth to maintain parity with Spring Security. | Conclave used **Spring Security + JWT**; Synod uses SimpleJWT to keep the auth logic identical across ports. |
| **Persistence** | **PostgreSQL**| `16` | Standard relational storage for conversation history and user session metadata. | Conclave used **PostgreSQL 16**; the choice is identical to ensure database performance is a constant variable. |

---

## 2. Real-time Layer (Django Channels)

| Component | Technology | Version | Rationale | Comparison to Conclave |
| :--- | :--- | :--- | :--- | :--- |
| **Async Wrapper**| **Channels** | `4.1` | Bridges Django’s synchronous nature with WebSockets via an event-driven consumer model. | Conclave used **Spring WebSockets/STOMP**; Channels is the core architectural divergence point for Synod. |
| **ASGI Server** | **Daphne** | `4.1` | The reference ASGI server that natively handles the WebSocket protocol handshakes for Channels. | Conclave used **Embedded Tomcat**; Daphne is used here to highlight the Pythonic need for a specialized ASGI server. |
| **Channel Layer** | **Redis** | `5.0` | Acts as the backing store for cross-instance message broadcasting (Pub/Sub). | Conclave used an **In-memory Simple Broker**; Redis is required by Channels, introducing an external dependency Conclave lacks. |
| **Consumer Logic**| **AsyncJsonConsumer**| - | Handles real-time message routing and `@-mention` parsing within the Python event loop. | Conclave used **@MessageMapping**; Synod's consumers are more low-level, requiring manual routing logic. |

---

## 3. Frontend Client (React)

| Component | Technology | Version | Rationale | Comparison to Conclave |
| :--- | :--- | :--- | :--- | :--- |
| **Framework** | **React** | `19` | Enables high-performance rendering of live-streaming AI message chunks. | Identical to Conclave to isolate backend divergence from UI behavior. |
| **Build Tool** | **Vite** | `5.x` | Provides near-instant HMR, essential for debugging real-time WebSocket state. | Identical to Conclave for parity in developer experience. |
| **State Mgmt** | **Zustand** | `4.x` | Minimalist store to manage the "Meeting Room" state without the boilerplate of Redux. | Identical to Conclave to ensure the "Model Registry" logic is comparable on the frontend. |
| **WS Client** | **WebSocket API** | Native | Uses native browser WebSockets with a custom reconnect wrapper for simplicity. | Conclave used **STOMP.js**; Synod moves to raw WebSockets to demonstrate the lack of a default Python STOMP protocol. |

---

## 4. AI Provider Integration

| Component | Technology | Approach | Rationale | Comparison to Conclave |
| :--- | :--- | :--- | :--- | :--- |
| **Live Provider** | **Gemini** | `Google SDK` | Real integration via the `google-generativeai` Python library. | Conclave used **Spring AI Vertex**; Synod uses the native SDK to highlight Python's first-class AI library support. |
| **Mock Providers**| **Unittest.mock** | `Mock Classes` | OpenAI and Claude are implemented as classes with stubbed `async` methods. | Conclave used **Fake ChatClient Beans**; Synod uses Python's dynamic mocking to simplify provider swapping. |
| **Validation** | **DRF Serializers**| `Schema Mapping` | Maps the "Canonical" message model to vendor-specific formats (e.g. OpenAI's `role` vs Gemini's `parts`). | Conclave used **Custom Adapters**; Synod leverages DRF Serializers as the primary engine for this translation. |

---

## 5. Local Infrastructure (Docker Compose)

| Service | Container Image | Port | Context | Comparison to Conclave |
| :--- | :--- | :--- | :--- | :--- |
| **Database** | `postgres:16-alpine` | `5432` | Conversation history and room metadata persistence. | Identical to Conclave. |
| **Cache/Bus** | `redis:7-alpine` | `6379` | **Mandatory** backing for the Django Channels layer. | Conclave **does not** require Redis for local dev; this is a Synod-specific infra requirement. |
| **App Server** | `python:3.12-slim` | `8000` | Runs the Daphne ASGI server for unified HTTP and WS traffic. | Conclave runs as a **JAR** on `8080`; Synod runs as a **Daphne** process on `8000`. |

---

## 6. Architectural Divergence Summary

### 6.1 Daphne vs. Spring's In-memory Broker
Conclave’s use of Spring WebSockets allows for a simple, in-memory message broker that is nearly invisible to the developer. Synod, by choosing Django Channels, must explicitly manage a **Redis** instance and an **ASGI** server (Daphne). This highlights Python's more explicit (and complex) path to real-time scalability.

### 6.2 DRF Serializers vs. Java Jackson
While Conclave uses Jackson to map JSON to POJOs, Synod uses **DRF Serializers** to handle the heavy lifting of the Adapter Pattern. This allows Synod to perform complex schema translations (e.g., merging system prompts for Claude) within the validation layer itself, a more declarative approach than the imperative adapter classes found in the Java implementation.