# Implemented features

Summary of shipped UI and API features for demos and grading.

## Batch A — guided experience & chat ergonomics

### 1. Demo tour (guided first run)

- **What:** Spotlight overlay with four steps (thresholds → ask question → demo sequence → read traces).
- **Where:** `frontend/src/components/DemoTour.jsx`, wired from `Chat.jsx`.
- **Behavior:** Auto-opens on first visit until completed; **Demo tour** button reopens. Completion stored in `localStorage` key `semcachelm_demo_tour_v1`.

### 2. Session export (Markdown)

- **What:** **Export session** downloads a `.md` file with each turn, assistant routing fields (`source`, `agent_action`, similarity, latency, `cache_id`, reason), and thresholds used for that request.
- **Where:** `frontend/src/utils/exportSession.js`, button in chat sidebar. Also available from the command palette (**⌘/Ctrl+K**).

### 3. One-click threshold presets

- **What:** **Conservative**, **Balanced**, **Aggressive** chips with short policy hints; manual slider movement clears the active chip highlight.
- **Where:** `frontend/src/constants/thresholdPresets.js`, `GrayZoneSliders.jsx`.

### 4. Live savings ticker

- **What:** Panel beside latency bars showing estimated tokens saved, cache hits + hit rate, illustrative USD (labeled), and LLM call count; polls analytics every ~2.5s.
- **Where:** `frontend/src/components/SavingsTicker.jsx`.

### 5. Last routing decision panel

- **What:** Below the message list: two-column card for the latest assistant reply—embedding band vs current thresholds, source/action, whether any LLM was invoked, validator line.
- **Where:** `frontend/src/components/LastDecisionPanel.jsx`; each reply stores `requestMeta: { hitThreshold, grayLow }` at request time.

---

## Batch B — architecture, ops surface, analytics tools

### 6. Architecture & data-flow modal

- **What:** SVG diagram (browser → FastAPI → Qdrant / Redis / Ollama → response) plus bullet list of each service’s role.
- **Where:** `frontend/src/components/ArchitectureModal.jsx`. Open via **Architecture** in the header or the command palette.

### 7. Version / environment strip

- **What:** Footer with API base URL, backend version, health status, optional `VITE_GIT_SHA`, and model/collection names from **`GET /api/v1/health`**.
- **Where:** `frontend/src/components/EnvironmentStrip.jsx`, `frontend/src/App.jsx`. Backend: `HealthStatus` extended in `backend/shared/models/schemas.py` and `backend/services/gateway/app/api/v1/health.py`.

### 8. Stress-the-cache micro-benchmark

- **What:** Runs a fixed sequence of queries against a throwaway session; shows hit rate, p50/p95 server latency, and a per-query bar chart (green = cache/validated path, blue = LLM path).
- **Where:** `frontend/src/components/CacheStressBench.jsx` on the **Analytics** page.

### 9. Quality & feedback snapshot

- **What:** Promoted / demoted / low-quality counts and a simple quality-score bucket bar chart from cache entries; eviction hint copy.
- **Where:** `frontend/src/components/QualityFeedbackSlice.jsx` on **Analytics**.

### 10. Command palette & shortcuts

- **What:** **⌘/Ctrl+K** toggles palette; **`/`** opens it when focus is not in an input/textarea. Commands navigate (Chat, Cache, Analytics, Settings), open tour, export session, focus chat input, open architecture modal, clear chat, clear chat+cache.
- **Where:** `frontend/src/components/CommandPalette.jsx`, `frontend/src/store/commandRegistry.js`; Chat registers runtime handlers on mount.

---

## Assistant message collapse (long answers)

- **What:** Assistant replies longer than ~2 lines or ~220 chars show **Expand answer** / **Collapse answer** (2-line clamp when collapsed). Sending a **new user message** auto-collapses the **latest** assistant reply to keep scrolling light.
- **Where:** `frontend/src/components/ResponseCard.jsx`, `frontend/src/store/sessionStore.js` (`collapseLastAssistant`, `toggleMessageBodyCollapsed`), `Chat.jsx` (`collapseLastAssistant()` at start of `sendQuery`).

---

_Configuration: optional `VITE_GIT_SHA` documented in `frontend/.env.example`._
