import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Command, CornerDownLeft, Search } from "lucide-react";
import { useCommandRegistry } from "../store/commandRegistry.js";

export default function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const navigate = useNavigate();
  const run = useCommandRegistry((s) => s.run);

  const items = useMemo(() => {
    const nav = (to) => () => {
      navigate(to);
      setOpen(false);
      setQ("");
    };
    return [
      { id: "nav-chat", label: "Chat", hint: "Home", keywords: "chat home", action: nav("/") },
      { id: "nav-cache", label: "Cache Explorer", hint: "", keywords: "cache qdrant", action: nav("/cache") },
      { id: "nav-analytics", label: "Analytics", hint: "", keywords: "metrics charts", action: nav("/analytics") },
      { id: "nav-settings", label: "Settings", hint: "", keywords: "config health", action: nav("/settings") },
      {
        id: "tour",
        label: "Open demo tour",
        hint: "Chat",
        keywords: "guide help",
        action: () => {
          run("openTour");
          setOpen(false);
          setQ("");
        },
      },
      {
        id: "export",
        label: "Export chat session (Markdown)",
        hint: "Chat",
        keywords: "download md",
        action: () => {
          run("exportSession");
          setOpen(false);
          setQ("");
        },
      },
      {
        id: "focus",
        label: "Focus chat input",
        hint: "Chat",
        keywords: "type ask",
        action: () => {
          run("focusChatInput");
          setOpen(false);
          setQ("");
        },
      },
      {
        id: "arch",
        label: "Open architecture diagram",
        hint: "Global",
        keywords: "diagram design",
        action: () => {
          run("openArchitecture");
          setOpen(false);
          setQ("");
        },
      },
      {
        id: "clear-chat",
        label: "Clear chat (UI only)",
        hint: "Chat",
        keywords: "erase",
        action: () => {
          run("clearChat");
          setOpen(false);
          setQ("");
        },
      },
      {
        id: "clear-all",
        label: "Clear chat & server cache…",
        hint: "Confirm",
        keywords: "wipe reset",
        action: () => {
          run("clearChatAndCache");
          setOpen(false);
          setQ("");
        },
      },
    ];
  }, [navigate, run]);

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return items;
    return items.filter(
      (it) =>
        it.label.toLowerCase().includes(s) ||
        it.keywords.toLowerCase().includes(s) ||
        it.hint.toLowerCase().includes(s)
    );
  }, [items, q]);

  useEffect(() => {
    const onKey = (e) => {
      const isMetaK = (e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k";
      if (isMetaK) {
        e.preventDefault();
        setOpen((o) => !o);
        return;
      }
      if (e.key === "Escape") setOpen(false);
      if (e.key === "/" && !open) {
        const tag = document.activeElement?.tagName;
        const editable =
          document.activeElement?.isContentEditable ||
          tag === "TEXTAREA" ||
          tag === "INPUT";
        if (!editable) {
          e.preventDefault();
          setOpen(true);
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[280] flex items-start justify-center pt-[12vh] px-4 bg-black/55 backdrop-blur-[2px]"
      onClick={() => setOpen(false)}
    >
      <div
        className="glass w-full max-w-lg rounded-xl border border-slate-700 shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 px-3 py-2 border-b border-slate-800 bg-slate-900/80">
          <Search size={16} className="text-slate-500 shrink-0" />
          <input
            autoFocus
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search commands…"
            className="flex-1 bg-transparent text-sm text-slate-100 placeholder:text-slate-600 focus:outline-none"
          />
          <span className="hidden sm:flex items-center gap-0.5 text-[10px] text-slate-600 shrink-0">
            <kbd className="px-1 py-0.5 rounded bg-slate-800">⌘</kbd>
            <kbd className="px-1 py-0.5 rounded bg-slate-800">K</kbd>
          </span>
        </div>
        <ul className="max-h-[min(50vh,320px)] overflow-y-auto py-1">
          {filtered.length === 0 ? (
            <li className="px-4 py-6 text-sm text-slate-500 text-center">No matches</li>
          ) : (
            filtered.map((it) => (
              <li key={it.id}>
                <button
                  type="button"
                  className="w-full flex items-center gap-3 px-3 py-2.5 text-left text-sm hover:bg-slate-800/80 text-slate-200"
                  onClick={() => it.action()}
                >
                  <Command size={14} className="text-slate-500 shrink-0" />
                  <span className="flex-1">{it.label}</span>
                  {it.hint ? <span className="text-[10px] text-slate-600">{it.hint}</span> : null}
                  <CornerDownLeft size={12} className="text-slate-600 opacity-0 sm:opacity-100" />
                </button>
              </li>
            ))
          )}
        </ul>
        <div className="px-3 py-2 border-t border-slate-800 text-[10px] text-slate-600 flex justify-between">
          <span>/ to open · Esc close</span>
          <span>SemCacheLM command palette</span>
        </div>
      </div>
    </div>
  );
}
