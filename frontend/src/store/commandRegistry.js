import { create } from "zustand";

/** Commands invoked from the global palette (registered from Chat / pages). */
export const useCommandRegistry = create((set, get) => ({
  handlers: {},
  register: (id, fn) =>
    set((s) => ({ handlers: { ...s.handlers, [id]: fn } })),
  unregister: (id) =>
    set((s) => {
      const next = { ...s.handlers };
      delete next[id];
      return { handlers: next };
    }),
  run: (id) => {
    const fn = get().handlers[id];
    if (typeof fn === "function") fn();
  },
}));
