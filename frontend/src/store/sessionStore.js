import { create } from "zustand";

function newSessionId() {
  return "sess-" + Math.random().toString(36).slice(2, 10);
}

export const useSessionStore = create((set, get) => ({
  sessionId: newSessionId(),
  messages: [],
  flowState: { embed: "idle", search: "idle", agent: "idle", validate: "hidden", result: "idle" },

  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),

  /** Reset conversation UI only (does not touch backend cache). */
  clearChat: () =>
    set({
      messages: [],
      flowState: {
        embed: "idle",
        search: "idle",
        agent: "idle",
        validate: "hidden",
        result: "idle",
      },
    }),

  /** Collapse the most recent assistant reply (before sending a new user message). */
  collapseLastAssistant: () =>
    set((s) => {
      for (let i = s.messages.length - 1; i >= 0; i--) {
        if (s.messages[i].role === "assistant") {
          const idx = i;
          return {
            messages: s.messages.map((m, j) =>
              j === idx ? { ...m, bodyCollapsed: true } : m
            ),
          };
        }
      }
      return s;
    }),

  toggleMessageBodyCollapsed: (id) =>
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === id && m.role === "assistant"
          ? { ...m, bodyCollapsed: !m.bodyCollapsed }
          : m
      ),
    })),

  setFlow: (state) => set({ flowState: state }),
  resetFlow: () =>
    set({
      flowState: {
        embed: "idle",
        search: "idle",
        agent: "idle",
        validate: "hidden",
        result: "idle",
      },
    }),
}));
