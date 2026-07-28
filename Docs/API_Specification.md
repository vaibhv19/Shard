# Synod API Specification

This document defines the API contracts for **Synod**. The REST layer provides room and workflow management, while the WebSocket layer carries real-time turn updates, streaming events, and orchestration state changes.

---

## Part A: Public REST API (Django DRF → React)

### 1. Global Conventions
- **Base URL:** `http://localhost:8000/api`
- **Auth Scheme:** JWT using SimpleJWT via `Authorization: Bearer <token>`
- **Format:** All requests and responses are `application/json`.
- **Data Model:** Synod uses **DRF Serializers** to validate request bodies and shape nested room and role-mapping data.

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
| `/` | `POST` | Create room + assign roles/providers | `RoomDetailSerializer` |
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
    {"role": "Lead Architect", "model": "Gemini (Live)"},
    {"role": "Reviewer", "model": "Claude (Mocked)"}
  ]
}
```

---

## Part B: Real-time WebSocket Contract (Django Channels)

Synod uses **Raw WebSockets** with a custom JSON dispatch pattern over the **Daphne** ASGI server.

### 1. Consumer Context
- **Consumer Class:** `ChatConsumer(AsyncJsonConsumer)`
- **Route:** `ws/room/{room_id}/`
- **Group Naming:** `room_{room_id}` (Stored in Redis Channel Layer)

### 2. Client-to-Server Actions
The client sends a JSON object with an `action` key.

| Action | Payload | Trigger |
| :--- | :--- | :--- |
| `send_message` | `{"text": "...", "is_mention": true}` | User sends a chat or @-mentions a model. |
| `pause_pipeline` | `{}` | User pauses an automated sequence. |
| `resume_pipeline` | `{}` | User resumes a paused sequence. |
| `system_intervention` | `{"text": "..."}` | User injects manual context or a correction. |

### 3. Server-to-Client Broadcasts (The `group_send` Model)
When the backend processes a turn, it broadcasts a dictionary to the group. The consumer’s handler method (e.g., `room_message`) then pushes it to the WebSocket.

**Message Schema:**
```json
{
  "type": "turn_update | status_change | stream_start | stream_chunk | stream_end",
  "data": {
    "message_id": "UUID",
    "sender": "Lead Architect (Gemini (Live))",
    "content": "string",
    "workflow_update": { "current_draft": "string", "review_comments": ["string"] },
    "is_complete": true,
    "chunk_index": 3,
    "is_final": false
  }
}
```

### 4. Event Semantics
- `stream_start`: Signals the beginning of a streamed response for a specific role.
- `stream_chunk`: Carries incremental content for the UI to render progressively.
- `stream_end`: Marks the completion of the streamed response and finalizes the turn.

---

## Part C: Internal Adapter Contract

While not exposed to the frontend, the **Provider Adapter** uses a consistent internal interface to transform data for the AI engines.

| Model | Adapter Strategy | Context Divergence |
| :--- | :--- | :--- |
| **Gemini (Live)** | `GeminiAdapterSerializer` | Maps history to `user/model` turns for the real Python SDK call. |
| **OpenAI (Mocked)** | `OpenAIAdapterSerializer` | Maps history to `user/assistant/system` for the mocked provider. |
| **Claude (Mocked)** | `ClaudeAdapterSerializer` | Extracts `SYSTEM` roles into the top-level parameter for the mocked provider. |

**Success Criterion:** Any `CanonicalMessage` stored in the Django ORM must pass through these serializers to produce a provider-compliant JSON payload without manual string manipulation.