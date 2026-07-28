# App Flow & Execution Lifecycles: Synod

This document outlines the user journeys and data state transitions for **Synod**. It highlights the operational divergence between Django Channels' event-driven architecture and Conclave’s Spring-based message handling.

---

## 1. Room Setup & Identity Flow
This flow establishes the "meeting room" and assigns AI personas before the first message is sent.

1.  User enters room metadata and the high-level task objective (Frontend).
2.  User maps available models (Gemini, OpenAI-Mock, Claude-Mock) to specific roles (Frontend).
3.  Frontend sends configuration to the `POST /api/rooms/` endpoint (DRF Backend).
4.  Backend validates provider availability via the Model Registry (Django Backend).
5.  Backend persists the `Room`, `RoleMapping`, and an initial `WorkflowState` in PostgreSQL (Django Backend).
6.  Frontend receives the room ID and initiates a WebSocket handshake with `/ws/room/{room_id}/` (Frontend -> Daphne ASGI).
7.  **Divergence Point:** The `ChatConsumer` validates the session and adds the specific user channel to a Redis-backed group named `room_{id}` (Django Channels). *Unlike Conclave's native STOMP topics, Synod requires explicit management of the Redis channel layer group.*

---

## 2. @-Mention Turn-Taking Flow
This is the core execution loop where a user triggers a response from a specific AI model.

1.  User inputs a message containing an @-mention (e.g., "@Claude, review the draft") (Frontend).
2.  Frontend dispatches the message as a JSON frame over the existing WebSocket connection (Frontend -> Channels Consumer).
3.  Consumer receives the frame and parses the @-mention to identify the target model (Django Backend).
4.  Backend retrieves the canonical history and passes it to the corresponding Provider Adapter (Django Backend).
5.  The Adapter (a DRF Serializer) translates the internal schema into the vendor-specific JSON shape (Django Backend).
6.  The AI call is executed:
    *   **Gemini:** Dispatched via `asyncio` using the real Google Generative AI SDK (Real Provider).
    *   **OpenAI/Claude:** Dispatched to an `async` mock class returning a stubbed response (Mocked Provider).
7.  The raw response is normalized back into a `CanonicalMessage` object (Django Backend).
8.  Backend saves the new message to the database and updates the `WorkflowState` summary (Django Backend).
9.  **Divergence Point:** The Consumer uses `self.channel_layer.group_send` to broadcast the completion event to the Redis backplane (Django Channels). *In Conclave, this is handled by Spring’s internal SimpleBroker; Synod requires the message to transit through Redis.*
10. The `room_message` handler in each consumer instance pushes the final JSON payload to every connected client (Django Channels).

---

## 3. Shared Context & Real-time Sync
This flow ensures that all users in the room see the same state, even if they aren't the one who prompted the model.

1.  The UI maintains a subscription to the WebSocket group via a persistent ASGI connection (Frontend).
2.  **Divergence Point:** When a model starts "thinking," the backend broadcasts a `TURN_STARTED` signal. *In Channels, this is a distinct event type sent through the consumer, whereas Conclave uses separate STOMP headers/destinations.*
3.  The Consumer pushes a JSON frame containing the event type and data (Django Backend).
4.  The Frontend receives the frame and updates the Zustand store's `messages` array and `workflowState` object (Frontend).
5.  React triggers a re-render of the "Message Matrix" based on the store update (Frontend).
6.  If a user joins late, they fetch the full history via `GET /api/rooms/{id}/messages/` to hydrate the store (Frontend -> Django Backend).

---

## 4. Pause & Intervene Flow
This logic allows the user to break a sequential model chain to prevent hallucinations or context drift.

1.  User clicks the "Pause" button while a sequential model pipeline is active (Frontend).
2.  Frontend sends a `PAUSE_SIGNAL` JSON frame over the WebSocket (Frontend -> Channels Consumer).
3.  Backend updates the Room status to `PAUSED` in the database to lock the turn queue (Django Backend).
4.  Backend utilizes an `asyncio.Task` cancellation if a mocked turn was currently pending (Django Backend).
5.  User sends a correction or manual instruction (Frontend).
6.  Backend persists this as a `SYSTEM_INTERVENTION` message in the canonical history (Django Backend).
7.  User clicks "Resume" (Frontend).
8.  Backend triggers the next model in the sequence, which now receives the updated history including the manual intervention (Django Backend).