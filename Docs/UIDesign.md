This document defines the visual design system for **Synod**. While Synod is a technical port of Conclave, the frontend identity is designed to emphasize its role as a "Collaborative AI Laboratory," focusing on the provenance of information (Real vs. Mocked) and the clarity of multi-agent orchestration.

---

## 1. Design Philosophy

Synod’s UI exists to make the invisible visible: the transformation of context through the Adapter Pattern. 

- **Provenance First:** The user must never wonder if a response was a real API call or a stub. 
- **Role > Model:** The UI emphasizes the *Persona* (e.g., Lead Architect) while keeping the *Provider* (e.g., Gemini) as secondary technical metadata.
- **State as a Sidebar:** The "Memory" (WorkflowState) is a living document, not just a hidden backend variable.
- **Intervention Clarity:** When the system is paused for a manual intervention, the UI must feel "locked" to prevent state collisions.

---

## 2. Palette Options (Selection Required)

Please select one of the following palettes to anchor the Synod identity:

### Option A: "The Terminal" (High-Contrast / Technical)
- **Background:** Deep Charcoal (`#121212`)
- **Primary Accent:** Electric Violet (`#8B5CF6`)
- **Secondary Accent:** Safety Orange (`#F97316`)
- **Rationale:** Mimics an IDE or Terminal environment. High contrast makes provider-specific colors (e.g., Gemini Blue vs. Claude Rust) pop. Best for demonstrating the "Engineering" nature of the project.

### Option B: "The Newsroom" (Editorial / Structured)
- **Background:** Off-White (`#F8FAFC`) / Slate Text (`#0F172A`)
- **Primary Accent:** Navy Blue (`#1E293B`)
- **Secondary Accent:** Terracotta (`#C2410C`)
- **Rationale:** Focuses on readability and the "Drafting" aspect of the WorkflowState. Feels like a collaborative document editor (Notion/Google Docs style).

### Option C: "The Laboratory" (Neutral / Cold-Professional)
- **Background:** Cool Gray (`#F1F5F9`)
- **Primary Accent:** Cyan-600 (`#0891B2`)
- **Secondary Accent:** Emerald-600 (`#059669`)
- **Rationale:** Clean, clinical, and objective. Uses a "Cool" palette to reduce visual fatigue during long multi-model debates. Emphasizes the "comparison" aspect through subtle gray-scale variations.

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
- **Layout:** A split view. Left side: Room name/Objective. Right side: A "Model Bench" where users drag-and-drop roles onto specific AI providers.
- **Constraint Feedback:** The UI prevents starting the room until at least one "Live" model and one "Reviewer" role are assigned.

### 4.2 The Intervention State (The "Lock")
- **Visual Treatment:** When the user clicks "Pause," the chat input becomes a high-contrast "System Intervention" field (e.g., bright Yellow or Red border).
- **Behavior:** All @-mention buttons are disabled. The "Shared Context" panel highlights the specific section being manually edited.

---

## 5. Component Patterns

### 5.1 Model/Role Badges
- **Format:** `[ ROLE ] ↳ { PROVIDER }`
- **Logic:** The `ROLE` uses a semi-opaque background of the role’s assigned color. The `PROVIDER` is displayed in a monospace font to emphasize its technical nature.

### 5.2 Real-time "Pulse"
- **Mocked Pulse:** A fast, 500ms fade-in (simulating the near-instant Python stub).
- **Real (Gemini) Pulse:** A slower, undulating "wave" animation (representing the 2-5 second latency of the real Vertex AI/Gemini API call).

### 5.3 Turn-Taking Controls
- **The "Command Strip":** Below the chat input, a horizontal scroll of @-mention chips (e.g., `@Architect`, `@Critic`). 
- **Action:** Clicking a chip auto-fills the input and triggers the "Sequential Mode" toggle if applicable.

---

## 6. Comparison Note (Synod vs. Conclave)
*Note: If Conclave's frontend is already established, Synod should intentionally diverge in Palette to make it clear which stack the user is currently viewing. I will wait for confirmation on Conclave's UI status before finalizing the typography choices.*