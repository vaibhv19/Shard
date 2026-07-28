# Synod — Feature List

**PROJECT NAME:** Synod
**Stack:** Python / Django
**Purpose:** This document is the single source of truth for the capabilities described across the Synod planning documents.

## Core Capabilities

- **Authentication:** JWT-based sign-in and token refresh using SimpleJWT.
- **User Accounts:** Registration and account management for room owners and participants.
- **Room Management:** Creation and lifecycle management of collaborative AI rooms.
- **Workflow State:** Persistent draft, review-comment, and summary state for each room.
- **Provider Registry:** Lookup and configuration of available AI providers for each role.
- **Provider Adapter:** Translation layer that converts canonical messages into provider-specific payloads.
- **Canonical Message Schema:** A normalized message structure shared across all providers.
- **Conversation History:** Persistent message history for all turns and interventions.
- **Role Mapping:** Assignment of providers to specific personas such as Lead Architect or Reviewer.
- **Token Streaming:** Progressive delivery of provider output chunks for live UI rendering.
- **Pause Pipeline:** Ability to halt a running workflow sequence.
- **Resume Pipeline:** Ability to continue a paused workflow sequence.
- **Manual Intervention:** User-supplied correction or direction inserted into the workflow.
- **Presence:** Awareness of connected users in the room.
- **Typing Indicators:** Visual feedback when a model or user is actively composing.
- **Workflow Summary:** A compact summary of the current draft and outstanding review items.
- **Token Usage Logging:** Recording of prompt and completion token usage for live and mocked providers.
- **WebSocket Broadcast:** Real-time propagation of room events and model updates.
- **Shared Context:** Unified room context visible to all participants.
- **Live Provider:** Gemini (Live) for real provider execution.
- **Mock Providers:** OpenAI (Mocked) and Claude (Mocked) for adapter and workflow demonstration.
- **Developer Comparison:** The project also serves as a comparison point for Django/Channels implementation choices.
