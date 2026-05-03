import { useEffect, useState } from "react";
import { Link, Route, Routes, useLocation } from "react-router-dom";
import ArchitectureModal from "./components/ArchitectureModal.jsx";
import CommandPalette from "./components/CommandPalette.jsx";
import EnvironmentStrip from "./components/EnvironmentStrip.jsx";
import Chat from "./pages/Chat.jsx";
import CacheExplorer from "./pages/CacheExplorer.jsx";
import Analytics from "./pages/Analytics.jsx";
import Settings from "./pages/Settings.jsx";
import { useCommandRegistry } from "./store/commandRegistry.js";

const NAV = [
  { to: "/", label: "Chat" },
  { to: "/cache", label: "Cache Explorer" },
  { to: "/analytics", label: "Analytics" },
  { to: "/settings", label: "Settings" },
];

export default function App() {
  const { pathname } = useLocation();
  const [archOpen, setArchOpen] = useState(false);
  const register = useCommandRegistry((s) => s.register);
  const unregister = useCommandRegistry((s) => s.unregister);

  useEffect(() => {
    const open = () => setArchOpen(true);
    register("openArchitecture", open);
    return () => unregister("openArchitecture");
  }, [register, unregister]);

  return (
    <div className="min-h-screen flex flex-col">
      <ArchitectureModal open={archOpen} onClose={() => setArchOpen(false)} />
      <CommandPalette />

      <header className="px-6 py-4 border-b border-slate-800 bg-slate-900/70 flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-emerald-400 to-cyan-500" />
          <h1 className="text-lg font-semibold tracking-tight">SemCacheLM</h1>
          <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 ml-1 hidden sm:inline">
            Quality-Aware Semantic Cache · CMPE 273
          </span>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <button
            type="button"
            onClick={() => setArchOpen(true)}
            className="text-xs px-3 py-1.5 rounded-md border border-slate-700 text-slate-300 hover:bg-slate-800/80 hover:text-white transition"
          >
            Architecture
          </button>
          <nav className="flex gap-1">
            {NAV.map((n) => (
              <Link
                key={n.to}
                to={n.to}
                className={`px-3 py-1.5 rounded-md text-sm transition ${
                  pathname === n.to
                    ? "bg-slate-800 text-white"
                    : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-100"
                }`}
              >
                {n.label}
              </Link>
            ))}
          </nav>
        </div>
      </header>

      <main className="flex-1 overflow-hidden min-h-0">
        <Routes>
          <Route path="/" element={<Chat />} />
          <Route path="/cache" element={<CacheExplorer />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>

      <EnvironmentStrip />
    </div>
  );
}
