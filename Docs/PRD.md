# Product Requirements Document (PRD): Synod

**Project Name:** Synod — Multi-Provider Context Unification  
**Status:** Planning / Architecture Phase  
**Document Version:** 1.0  

---

## 1. Problem Statement
The primary engineering challenge in multi-model AI orchestration is **Context Fragmentation**. Different LLM providers require disparate API schemas, making it difficult to maintain a single coherent conversation history across vendors without manual copy-pasting.

**Synod** is a Python/Django implementation of a multi-provider orchestration workspace. The goal is to demonstrate how a unified message schema and provider-adapter pattern can be applied in a real-time, asynchronous environment using Django Channels and DRF.

---

## 2. Target Persona & Use Case
*   **Target Persona:** Technical Reviewers and Engineering Leads.
*   **Core Use Case:** Demonstrating how a shared workflow can coordinate multiple AI providers while preserving room context and provider-specific translation logic.
*   **User Action:** A user initiates a session where one live provider and one or more mocked providers collaborate on a single task. The system handles real-time synchronization of state across these providers while exposing the adapter layer’s reasoning and summary state.

---

## 3. Functional Requirements (In-Scope)

### 3.1 Django Backend (Orchestration & Persistence)
*   **Unified Canonical Schema:** Implementation of a single database model for messages that normalizes the differing role/content structures of various AI vendors.
*   **Provider Adapter Layer:** A set of translation services using DRF Serializers to map the internal schema to Gemini (Live), OpenAI (Mocked), and Claude (Mocked) formats.
*   **Model Registry:** A dynamic lookup service that resolves @-mentions to specific model configurations and their corresponding adapter logic.
*   **Workflow State Persistence:** Management of a summarized `WorkflowState` object (Current Draft, Review Comments, Task) to minimize token consumption across turns.
*   **Authentication:** JWT-based sign-in and token refresh using SimpleJWT.

### 3.2 Channels Layer (Real-time Communication)
*   **ASGI Integration:** Use of Daphne to support asynchronous WebSocket connections alongside standard HTTP traffic.
*   **Redis Channel Layer:** Multi-client broadcast system to push model typing states, incremental chunks, turn-completion events, and pause/resume signals.
*   **Turn Broadcasting:** Event-driven behavior implemented via Channels to notify the UI of model transitions and streaming updates.

### 3.3 Frontend Client (React)
*   **Multi-Agent Thread:** A conversational UI visually differentiating models by role and provider.
*   **Moderated Turn-Taking:** UI support for @-mentioning specific models to trigger the next response in the sequence.
*   **Pause & Intervene:** Controls to halt an automated turn sequence, allowing the user to inject manual context or corrections.
*   **Room Setup:** Dropdown-based role-to-provider selection during room creation.

---

## 4. Explicit Non-Goals
*   **No Feature Drift:** Synod will not include features absent from the documented workflow (for example, RAG or PDF ingestion).
*   **No Multi-Vendor Live Costs:** Only Gemini (Live) will perform a real provider call; OpenAI (Mocked) and Claude (Mocked) will use mocked responses for demonstration and adapter validation.
*   **No Production Deployment:** This is a local-first repository designed for technical review; automated cloud scaling is out of scope.
*   **No OAuth2/Complex RBAC:** Simple user identification is sufficient for the demo environment.

---

## 5. Success Criteria
*   **Workflow Verification:** Synod must successfully execute the same room workflow using pause, resume, manual intervention, and streaming events.
*   **Adapter Integrity:** Unit tests must prove that a single message in the Django database can be correctly serialized into three distinct, provider-compliant JSON payloads.
*   **Usage Logging:** The project should capture token usage and cost-related metadata for both live and mocked provider calls.

---

## 6. Key Risks & Open Questions
*   **Channels Configuration:** The complexity of the Redis Channel Layer and Daphne runtime can exceed the boilerplate commonly associated with simpler chat systems.
*   **Serialization Performance:** Evaluating whether DRF serialization overhead for deep message histories becomes a bottleneck during large room histories.
*   **Global Interpreter Lock (GIL):** Monitoring whether high-concurrency WebSocket traffic interacts poorly with CPU-bound tasks such as message summarization.