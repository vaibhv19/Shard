# Product Requirements Document (PRD): Synod

**Project Name:** Synod — Multi-Provider Context Unification (Python/Django Port)  
**Status:** Planning / Architecture Phase  
**Document Version:** 1.0  

---

## 1. Problem Statement
The primary engineering challenge in multi-model AI orchestration is **Context Fragmentation**. Different LLM providers (Google, OpenAI, Anthropic) require disparate API schemas, making it difficult to maintain a single, coherent conversation history across vendors without manual copy-pasting.

**Synod** is a deliberate technical port of the **Conclave** (Spring Boot) architecture into the Python/Django ecosystem. The goal is not to solve a new product need, but to perform a direct architectural comparison. Specifically, Synod examines how a unified message schema and provider-adapter pattern diverge when implemented using:
*   **Django Channels & Redis** (Asynchronous/Event-driven) instead of Spring's native STOMP/Message-Broker implementation.
*   **DRF Serializers** for payload validation instead of Java’s strictly-typed POJO/DTO patterns.
*   **Python’s Asyncio/ASGI runtime** for handling long-polling LLM requests vs. Spring’s multi-threaded approach.

---

## 2. Target Persona & Use Case
*   **Target Persona:** Technical Reviewers and Engineering Leads.
*   **Core Use Case:** Demonstrating cross-stack architectural fluency. The project serves as a portfolio centerpiece that allows a reviewer to see how the same high-level system design (Shared Context + Adapter Pattern) is adapted to the idiomatic strengths and constraints of Python.
*   **User Action:** A user initiates a session where multiple AI models (one live Gemini, two mocked) collaborate on a single task. The system handles the real-time synchronization of state across these providers while exposing the "reasoning" of the adapter layer.

---

## 3. Functional Requirements (In-Scope)

### 3.1 Django Backend (Orchestration & Persistence)
*   **Unified Canonical Schema:** Implementation of a single database model for messages that normalizes the differing role/content structures of various AI vendors.
*   **Provider Adapter Layer:** A set of translation services using DRF Serializers to map the internal schema to Google Gemini, OpenAI, and Anthropic Claude formats.
*   **Model Registry:** A dynamic lookup service that resolves @-mentions to specific model configurations and their corresponding adapter logic.
*   **Workflow State Persistence:** Management of a summarized "WorkflowState" object (Current Draft, Review Comments, Task) to minimize token consumption across turns.
*   **Authentication:** Stateless session management using JWT or standard Django session auth for developer-level access.

### 3.2 Channels Layer (Real-time Communication)
*   **ASGI Integration:** Use of Daphne/Uvicorn to support asynchronous WebSocket connections alongside standard HTTP traffic.
*   **Redis Channel Layer:** Multi-client broadcast system to push model "typing" states, incremental chunks, and turn-completion events.
*   **Turn Broadcasting:** A STOMP-like behavior implemented via Channels to notify the UI of model transitions.

### 3.3 Frontend Client (React)
*   **Multi-Agent Thread:** A conversational UI visually differentiating models by role and provider.
*   **Moderated Turn-Taking:** UI support for @-mentioning specific models to trigger the next response in the sequence.
*   **Pause & Intervene:** Controls to halt an automated turn sequence, allowing the user to inject manual context or corrections.

---

## 4. Explicit Non-Goals
*   **No Feature Drift:** Synod will not include features absent in Conclave (e.g., RAG, PDF ingestion). It is a faithful 1:1 architectural port.
*   **No Multi-Vendor Live Costs:** To maintain parity with Conclave, only Google Gemini will be "Live." OpenAI and Claude will use mocked responses to demonstrate the adapter logic without incurring costs.
*   **No Production Deployment:** This is a local-first repository designed for technical review; automated cloud scaling is out of scope.
*   **No OAuth2/Complex RBAC:** Simple user identification is sufficient for the demo environment.

---

## 5. Success Criteria
*   **Parity Verification:** Synod must successfully execute the same "Lead Writer → Critic" workflow as Conclave using the same state-passing logic.
*   **Adapter Integrity:** Unit tests must prove that a single message in the Django database can be correctly serialized into three distinct, vendor-compliant JSON payloads.
*   **Comparison Documentation:** The project is considered successful only if it includes a "Comparison Log" identifying at least three concrete friction points, such as:
    1.  The complexity of configuring **ASGI/Redis** vs. Spring's **native WebSocket** support.
    2.  The flexibility vs. risk of **Python’s duck-typing** in the adapter layer compared to **Java’s interfaces**.
    3.  Differences in handling **long-running AI requests** (Asyncio tasks vs. Spring thread pools).

---

## 6. Key Risks & Open Questions
*   **Parity Drift:** If the Conclave (Java) architecture changes during the build, Synod risks becoming a port of an obsolete version.
*   **Channels Configuration:** The "hidden" complexity of the Redis Channel Layer and Daphne configuration often exceeds the boilerplate required for Spring WebSockets.
*   **Serialization Performance:** Evaluating if DRF’s serialization overhead for deep message histories becomes a bottleneck compared to Java’s Jackson-based serialization.
*   **Global Interpreter Lock (GIL):** Monitoring if high-concurrency WebSocket traffic interacts poorly with the CPU-bound tasks of message summarization.