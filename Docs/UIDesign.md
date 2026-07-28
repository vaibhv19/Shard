This document defines the visual design system for **Synod**. The frontend identity is designed to emphasize clarity, provenance, and multi-agent orchestration rather than decorative complexity.

---

## 1. Design Philosophy

Synod’s UI exists to make the invisible visible: the transformation of context through the Adapter Pattern.

- **Provenance First:** The user must never wonder whether a response came from a real provider or a mocked provider.
- **Role > Model:** The UI emphasizes the *Persona* (for example, Lead Architect) while keeping the *Provider* as secondary technical metadata.
- **State as a Sidebar:** The "Memory" (WorkflowState) is a living document, not just a hidden backend variable.
- **Intervention Clarity:** When the system is paused for a manual intervention, the UI must feel locked to prevent state collisions.

---

## 2. Finalized Palette

### The Laboratory (Neutral / Cold-Professional)
- **Background:** Cool Gray (`#F1F5F9`)
- **Primary Accent:** Cyan-600 (`#0891B2`)
- **Secondary Accent:** Emerald-600 (`#059669`)
- **Rationale:** Clean, clinical, and objective. This palette reduces visual fatigue during long multi-model debates while keeping the distinction between live and mocked providers clear.

---

## 3. Layout & Density

### 3.1 The "Message Matrix" (Center)
- **Bubbles:** Offset based on role. User messages are right-aligned; AI messages are left-aligned but grouped by role-color.
- **Provenance Indicator:** A small "Mocked" or "Live" badge sits top-right of every AI message bubble.
- **Turn Indicators:** A "Thinking..." pulse appears only on the active model's role badge.

### 3.2 The "Context Sidebar" (Right)
- **Pinned WorkflowState:** A persistent, collapsible panel showing the `Current Draft` in Markdown and a bulleted list of `Review Comments`.
- **Sync Status:** A small pulse (Green/Amber) indicating the WebSocket connection health to the Django Channels backend.

---

## 4. Key Screens & Transitions

### 4.1 Room Setup (The "Drafting Table")
- **Layout:** A split view. Left side: Room name/Objective. Right side: A "Model Bench" where users select providers for each role through dropdown menus.
- **Constraint Feedback:** The UI prevents starting the room until at least one live provider and one reviewer role are assigned.

### 4.2 The Intervention State (The "Lock")
- **Visual Treatment:** When the user clicks "Pause," the chat input becomes a high-contrast "System Intervention" field with a strong border and accent treatment.
- **Behavior:** All @-mention buttons are disabled. The "Shared Context" panel highlights the specific section being manually edited.

---

## 5. Component Patterns

### 5.1 Model/Role Badges
- **Format:** `[ ROLE ] ↳ { PROVIDER }`
- **Logic:** The `ROLE` uses a semi-opaque background of the role’s assigned color. The `PROVIDER` is displayed in a monospace font to emphasize its technical nature.

### 5.2 Real-time "Pulse"
- **Mocked Pulse:** A fast, 500ms fade-in (simulating the near-instant stubbed response).
- **Live (Gemini) Pulse:** A slower, undulating "wave" animation (representing the real provider latency).

### 5.3 Turn-Taking Controls
- **The "Command Strip":** Below the chat input, a horizontal scroll of @-mention chips (for example, `@Architect`, `@Critic`).
- **Action:** Clicking a chip auto-fills the input and triggers the sequential mode toggle if applicable.

---

## 6. Design Note
This palette is intended to feel professional and technical while remaining readable during long collaborative drafting sessions.