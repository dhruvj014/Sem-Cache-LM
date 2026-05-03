import { Box, Cpu, Database, HardDrive, Orbit, X } from "lucide-react";

export default function ArchitectureModal({ open, onClose }) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[300] flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="arch-modal-title"
    >
      <div className="glass max-w-3xl w-full max-h-[90vh] overflow-y-auto rounded-2xl border border-slate-700 shadow-2xl">
        <div className="sticky top-0 flex items-center justify-between px-5 py-4 border-b border-slate-800 bg-slate-900/90">
          <div className="flex items-center gap-2">
            <Orbit className="text-cyan-400" size={22} />
            <h2 id="arch-modal-title" className="text-lg font-semibold text-white">
              Architecture &amp; data flow
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-2 rounded-lg text-slate-400 hover:bg-slate-800 hover:text-white"
            aria-label="Close"
          >
            <X size={20} />
          </button>
        </div>

        <div className="p-5 space-y-6">
          <div className="rounded-xl bg-slate-950/80 border border-slate-800 p-4 overflow-x-auto">
            <svg viewBox="0 0 720 200" className="w-full min-w-[560px] h-44 text-slate-300">
              <defs>
                <marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
                  <path d="M0,0 L8,4 L0,8 Z" fill="currentColor" className="text-slate-500" />
                </marker>
              </defs>
              <rect x="20" y="70" width="100" height="56" rx="10" fill="rgba(16,185,129,0.15)" stroke="rgba(52,211,153,0.5)" />
              <text x="70" y="102" textAnchor="middle" fill="#a7f3d0" fontSize="12" fontFamily="system-ui">
                Browser
              </text>
              <line x1="120" y1="98" x2="175" y2="98" stroke="#64748b" strokeWidth="2" markerEnd="url(#arrow)" />
              <rect x="180" y="50" width="130" height="96" rx="12" fill="rgba(56,189,248,0.12)" stroke="rgba(56,189,248,0.45)" />
              <text x="245" y="78" textAnchor="middle" fill="#7dd3fc" fontSize="11" fontFamily="system-ui" fontWeight="600">
                FastAPI
              </text>
              <text x="245" y="96" textAnchor="middle" fill="#94a3b8" fontSize="10" fontFamily="system-ui">
                Query · Agent ·
              </text>
              <text x="245" y="112" textAnchor="middle" fill="#94a3b8" fontSize="10" fontFamily="system-ui">
                Validator orchestration
              </text>
              <text x="245" y="132" textAnchor="middle" fill="#64748b" fontSize="9" fontFamily="system-ui">
                /api/v1/*
              </text>
              <line x1="310" y1="70" x2="370" y2="40" stroke="#64748b" strokeWidth="2" markerEnd="url(#arrow)" />
              <line x1="310" y1="98" x2="370" y2="98" stroke="#64748b" strokeWidth="2" markerEnd="url(#arrow)" />
              <line x1="310" y1="126" x2="370" y2="156" stroke="#64748b" strokeWidth="2" markerEnd="url(#arrow)" />
              <rect x="375" y="18" width="120" height="52" rx="10" fill="rgba(244,63,94,0.12)" stroke="rgba(251,113,133,0.45)" />
              <text x="435" y="40" textAnchor="middle" fill="#fda4af" fontSize="10" fontFamily="system-ui" fontWeight="600">
                Qdrant HNSW
              </text>
              <text x="435" y="56" textAnchor="middle" fill="#94a3b8" fontSize="9" fontFamily="system-ui">
                Vectors + payload
              </text>
              <rect x="375" y="78" width="120" height="52" rx="10" fill="rgba(234,179,8,0.12)" stroke="rgba(250,204,21,0.45)" />
              <text x="435" y="100" textAnchor="middle" fill="#fde047" fontSize="10" fontFamily="system-ui" fontWeight="600">
                Redis
              </text>
              <text x="435" y="116" textAnchor="middle" fill="#94a3b8" fontSize="9" fontFamily="system-ui">
                Analytics · quality
              </text>
              <rect x="375" y="138" width="120" height="52" rx="10" fill="rgba(167,139,250,0.12)" stroke="rgba(196,181,253,0.45)" />
              <text x="435" y="160" textAnchor="middle" fill="#ddd6fe" fontSize="10" fontFamily="system-ui" fontWeight="600">
                Ollama
              </text>
              <text x="435" y="176" textAnchor="middle" fill="#94a3b8" fontSize="9" fontFamily="system-ui">
                Embed + LLM
              </text>
              <line x1="495" y1="98" x2="555" y2="98" stroke="#64748b" strokeWidth="2" markerEnd="url(#arrow)" />
              <rect x="560" y="70" width="140" height="56" rx="10" fill="rgba(148,163,184,0.1)" stroke="rgba(148,163,184,0.35)" />
              <text x="630" y="102" textAnchor="middle" fill="#cbd5e1" fontSize="11" fontFamily="system-ui">
                User response
              </text>
            </svg>
          </div>

          <ul className="grid sm:grid-cols-2 gap-3 text-sm text-slate-300">
            <li className="flex gap-2 items-start">
              <Database size={16} className="text-rose-300 shrink-0 mt-0.5" />
              <span>
                <strong className="text-slate-100">Qdrant</strong> stores query embeddings and
                cached answer payloads for semantic retrieval.
              </span>
            </li>
            <li className="flex gap-2 items-start">
              <HardDrive size={16} className="text-amber-300 shrink-0 mt-0.5" />
              <span>
                <strong className="text-slate-100">Redis</strong> tracks per-entry quality/hits,
                aggregate analytics, and recent history.
              </span>
            </li>
            <li className="flex gap-2 items-start">
              <Cpu size={16} className="text-violet-300 shrink-0 mt-0.5" />
              <span>
                <strong className="text-slate-100">Ollama</strong> serves embedding and chat
                models; the validator reuses the LLM for gray-zone checks.
              </span>
            </li>
            <li className="flex gap-2 items-start">
              <Box size={16} className="text-cyan-300 shrink-0 mt-0.5" />
              <span>
                <strong className="text-slate-100">FastAPI</strong> composes embed → search →
                decision → optional validate → respond → analytics.
              </span>
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
}
