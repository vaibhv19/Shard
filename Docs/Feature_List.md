# Synod — Feature List

**PROJECT NAME:** Synod (Python/Django variant of Conclave)
**Stack:** Python / Django
**Core Differentiator:** Multi-Provider Context Unification — Django implementation

## Same core concept and features as Conclave

- Unified message schema + per-provider adapters (Claude/GPT/Gemini)
- Shared conversation history across all models
- @-mention turn-taking, chat room UI
- Auth + user accounts

## What's actually different — the point of building it twice

- Django Channels + Redis for the real-time chat room, instead of Spring's more native WebSocket handling — worth naming explicitly since it's a real architectural divergence, not just "same thing, different syntax"
- DRF serializers/validation patterns vs. Spring's DTO/validation approach for the adapter layer
- Built specifically to compare how Java vs. Python diverge on the same real-time, multi-integration problem — the value of this project is the comparison itself, not just having "a Python version"
