# Tech Stack Specification: Synod

This document outlines the technical specifications for **Synod**. The stack is selected to support the project’s real-time, multi-provider workflow and to provide a clear implementation baseline for the planning documents.

---

## 1. Backend Orchestration (Django)

| Component | Technology | Version | Rationale | Note |
| :--- | :--- | :--- | :--- | :--- |
| **Language** | **Python** | `3.12` | Native support for `async/await` is critical for non-blocking AI API calls. | Suitable for the event-driven room workflow. |
| **Framework** | **Django** | `5.0` | Provides a batteries-included ORM and admin for rapid schema management. | Keeps the data model and room lifecycle straightforward. |
| **API Layer** | **DRF** | `3.15` | Serializers provide a robust way to validate complex, multi-provider JSON payloads. | Supports the provider-adapter translation layer. |
| **Authentication** | **SimpleJWT** | `5.3` | Enables stateless token-based auth for room access and API calls. | Synod uses JWT using SimpleJWT throughout the documentation. |
| **Persistence** | **PostgreSQL**| `16` | Standard relational storage for conversation history and user session metadata. | Supports the room, message, workflow, and token-usage tables. |

---

## 2. Real-time Layer (Django Channels)

| Component | Technology | Version | Rationale | Note |
| :--- | :--- | :--- | :--- | :--- |
| **Async Wrapper**| **Channels** | `4.1` | Bridges Django’s synchronous nature with WebSockets via an event-driven consumer model. | Supports the room broadcast and turn-taking flow. |
| **ASGI Server** | **Daphne** | `4.1` | The reference ASGI server that handles WebSocket protocol handshakes for Channels. | Standardized as the runtime for Synod. |
| **Channel Layer** | **Redis** | `5.0` | Acts as the backing store for cross-instance message broadcasting (Pub/Sub). | Required for multi-client room updates. |
| **Consumer Logic**| **AsyncJsonConsumer**| - | Handles real-time message routing and `@-mention` parsing within the Python event loop. | Supports turn routing and streaming events. |

---

## 3. Frontend Client (React)

| Component | Technology | Version | Rationale | Note |
| :--- | :--- | :--- | :--- | :--- |
| **Framework** | **React** | `19` | Enables high-performance rendering of live-streaming AI message chunks. | Supports the message matrix and sidebar workflow view. |
| **Build Tool** | **Vite** | `5.x` | Provides near-instant HMR, essential for debugging real-time WebSocket state. | Keeps the local development loop fast. |
| **State Mgmt** | **Zustand** | `4.x` | Minimalist store to manage the meeting-room state without the boilerplate of Redux. | Supports shared context and workflow-state updates. |
| **WS Client** | **WebSocket API** | Native | Uses native browser WebSockets with a custom reconnect wrapper for simplicity. | Supports streaming and room event updates. |

---

## 4. AI Provider Integration

| Component | Technology | Approach | Rationale | Note |
| :--- | :--- | :--- | :--- | :--- |
| **Live Provider** | **Gemini (Live)** | `Google SDK` | Real integration via the `google-generativeai` Python library. | Represents the live path in the workflow. |
| **Mock Providers**| **OpenAI (Mocked), Claude (Mocked)** | `Mock Classes` | OpenAI and Claude are implemented as classes with stubbed `async` methods. | Demonstrates adapter and workflow behavior without live cost. |
| **Validation** | **DRF Serializers**| `Schema Mapping` | Maps the canonical message model to vendor-specific formats. | Keeps provider translation consistent across the stack. |

---

## 5. Local Infrastructure (Docker Compose)

| Service | Container Image | Port | Context | Note |
| :--- | :--- | :--- | :--- | :--- |
| **Database** | `postgres:16-alpine` | `5432` | Conversation history and room metadata persistence. | Stores rooms, messages, workflow state, and token usage logs. |
| **Cache/Bus** | `redis:7-alpine` | `6379` | Mandatory backing for the Django Channels layer. | Required for room broadcasting and presence updates. |
| **App Server** | `python:3.12-slim` | `8000` | Runs the Daphne ASGI server for unified HTTP and WS traffic. | Standardized as the runtime for Synod. |

---

## 6. Architectural Summary

### 6.1 Runtime Model
Synod uses Django, DRF, Channels, and Daphne to support an event-driven room workflow with a shared canonical message model and provider-specific adapters.

### 6.2 Serialization Strategy
DRF Serializers handle the heavy lifting of the Adapter Pattern, allowing Synod to transform canonical messages into provider-compliant payloads while preserving a single shared data model.