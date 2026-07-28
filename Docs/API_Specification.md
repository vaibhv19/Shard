# Synod API Specification

This document defines the API contracts for **Synod**. As a port of Conclave, Synod maintains functional parity in its REST endpoints but introduces a significantly different WebSocket contract due to the shift from Spring STOMP to **Django Channels**.

---

## Part A: Public REST API (Django DRF → React)

### 1. Global Conventions
- **Base URL:** `http://localhost:8000/api`
- **Auth Scheme:** JWT (JSON Web Token) via `Authorization: Bearer <token>`
- **Format:** All requests and responses are `application/json`.
- **Divergence Note:** Unlike Conclave's Spring Boot DTOs, Synod uses **DRF Serializers**, which handle both validation and the nested relationship between Rooms and Role Mappings in a single pass.

### 2. Authentication (`/auth/`)
| Path | Method | Description | Request Body | Status |
| :--- | :--- | :--- | :--- | :--- |
| `/token/` | `POST` | Get JWT access/refresh pair | `{ "username", "password" }` | 200/401 |
| `/token/refresh/` | `POST` | Refresh expired access token | `{ "refresh" }` | 200/401 |
| `/register/` | `POST` | Create new account | `{ "username", "password", "email" }` | 201/400 |

### 3. Room & Workflow Management (`/rooms/`)
| Path | Method | Description | Response |
| :--- | :--- | :--- | :--- |
| `/` | `GET` | List user's active meeting rooms | `List<RoomSummarySerializer>` |
| `/` | `POST` | Create room + assign roles/models | `RoomDetailSerializer` |
| `/{id}/` | `GET` | Get full room state + WorkflowState | `RoomDetailSerializer` |
| `/{id}/messages/` | `GET` | Fetch canonical history (paginated) | `List<MessageSerializer>` |

**Key DTO Shape (`RoomDetailSerializer`):**
```json
{
  "id": "UUID",
  "name": "string",
  "objective": "string",
  "status": "INITIALIZED|ACTIVE|PAUSED",
  "workflow_state": {
    "current_draft": "string (Markdown)",
    "review_comments": ["string"],
    "last_updated": "ISO-8601"
  },
  "role_mappings": [
    {"role": "Lead Architect", "model": "GEMINI_PRO"},
    {"role": "Reviewer", "model": "CLAUDE_MOCKED"}
  ]
}
```

---

## Part B: Real-time WebSocket Contract (Django Channels)

This is Synod's most architecturally distinct surface. While Conclave uses the STOMP sub-protocol (with built-in `SUBSCRIBE` and `SEND` frames), Synod uses **Raw WebSockets** with a custom JSON dispatch pattern.

### 1. Consumer Context
- **Consumer Class:** `ChatConsumer(AsyncJsonConsumer)`
- **Route:** `ws/room/{room_id}/`
- **Group Naming:** `room_{room_id}` (Stored in Redis Channel Layer)

### 2. Client-to-Server Actions
The client sends a JSON object with an `action` key.

| Action | Payload | Trigger |
| :--- | :--- | :--- |
| `send_message` | `{"text": "...", "is_mention": true}` | User sends a chat or @-mentions a model. |
| `pause_pipeline` | `{}` | User halts an automated sequence. |

### 3. Server-to-Client Broadcasts (The `group_send` Model)
When the backend processes a turn, it broadcasts a dictionary to the group. The consumer’s handler method (e.g., `room_message`) then pushes it to the WebSocket.

**Message Schema:**
```json
{
  "type": "turn_update | status_change | chunk",
  "data": {
    "message_id": "UUID",
    "sender": "Lead Architect (Gemini)",
    "content": "string",
    "workflow_update": { ... },
    "is_complete": true
  }
}
```

### 4. Comparison: Channels vs. STOMP
- **Protocol Overhead:** Synod’s contract is "lighter" but requires the developer to manually define event types (`type`). Conclave leverages STOMP's native headers to route messages to specific `@MessageMapping` controllers.
- **State Presence:** In Synod, `connect()` explicitly adds the user to the Redis Group. In Conclave, the broker handles subscriptions transparently.
- **Broadcast Trigger:** Synod requires an explicit `self.channel_layer.group_send` call from the consumer or a signal, whereas Conclave uses `@SendTo` or `SimpMessagingTemplate`.

---

## Part C: Internal Adapter Contract

While not exposed to the frontend, the **Provider Adapter** (DRF-based) uses a consistent internal interface to transform data for the AI engines.

| Model | Adapter Strategy | Context Divergence |
| :--- | :--- | :--- |
| **Gemini** | `GeminiAdapterSerializer` | Maps history to `user/model` turns for the real Python SDK call. |
| **OpenAI** | `OpenAIAdapterSerializer` | Maps history to `user/assistant/system` for the Mocked provider. |
| **Claude** | `ClaudeAdapterSerializer` | Extracts `SYSTEM` roles into the top-level parameter for the Mocked provider. |

**Success Criterion:** Any `CanonicalMessage` stored in the Django ORM must pass through these serializers to produce a provider-compliant JSON payload without manual string manipulation.