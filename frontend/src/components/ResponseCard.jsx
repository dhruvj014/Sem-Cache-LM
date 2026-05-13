import { motion } from "framer-motion";
import { Check, ChevronDown, ChevronUp, Copy, RotateCcw } from "lucide-react";
import { useState } from "react";
import DecisionTraceCard from "./DecisionTraceCard.jsx";
import SourceBadge from "./SourceBadge.jsx";
import { useSessionStore } from "../store/sessionStore.js";

function assistantBodyIsLong(text) {
  if (!text) return false;
  return text.split("\n").length > 2 || text.length > 220;
}

export default function ResponseCard({ message, onRegenerate, busy }) {
  const toggleBody = useSessionStore((s) => s.toggleMessageBodyCollapsed);
  const [showAllCitations, setShowAllCitations] = useState(false);
  const [copied, setCopied] = useState(false);
  const isUser = message.role === "user";
  const long = !isUser && assistantBodyIsLong(message.content);

  const copyResponse = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    } catch {
      // TODO
      // Ignoring clipboard failures silently
    }
  };

  if (isUser) {
    return (
      <div className="flex justify-end">
        <motion.div
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          className="max-w-2xl bg-blue-600/20 border border-blue-500/40 rounded-xl px-4 py-2 text-sm"
        >
          {message.content}
        </motion.div>
      </div>
    );
  }

  const { payload } = message;
  const collapsed = message.bodyCollapsed === true;
  const citations = payload?.citations ?? [];
  const visibleCitations = showAllCitations ? citations : citations.slice(0, 3);

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      className="max-w-3xl"
    >
      <div className="glass rounded-xl px-4 py-3">
        <div className="mb-2 flex justify-end">
          <button
            type="button"
            onClick={copyResponse}
            className="flex items-center gap-1 rounded-md border border-slate-700/80 px-2 py-1 text-[11px] text-slate-400 hover:border-emerald-500/60 hover:text-emerald-300"
            title="Copy response"
          >
            {copied ? <Check size={13} /> : <Copy size={13} />}
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
        <div
          className={`text-sm whitespace-pre-wrap leading-relaxed text-slate-100 ${
            long && collapsed ? "line-clamp-2" : ""
          }`}
        >
          {message.content}
        </div>
        {long && (
          <button
            type="button"
            onClick={() => toggleBody(message.id)}
            className="mt-2 flex items-center gap-1 text-[11px] font-medium text-emerald-400/90 hover:text-emerald-300"
          >
            {collapsed ? (
              <>
                <ChevronDown size={14} /> Expand answer
              </>
            ) : (
              <>
                <ChevronUp size={14} /> Collapse answer
              </>
            )}
          </button>
        )}
        {onRegenerate && (
          <button
            type="button"
            onClick={onRegenerate}
            disabled={busy}
            className="mt-2 ml-3 inline-flex items-center gap-1 text-[11px] font-medium text-slate-400 hover:text-emerald-300 disabled:opacity-50"
            title="Regenerate response"
          >
            <RotateCcw size={13} />
            Regenerate
          </button>
        )}
        {payload && (
          <div className="mt-2 flex items-center gap-2 text-[11px] text-slate-500">
            <SourceBadge source={payload.source} size="sm" />
            <span>•</span>
            <span>sim {(payload.similarity_score * 100).toFixed(1)}%</span>
            <span>•</span>
            <span>{payload.latency_ms.toFixed(0)} ms</span>
            <span>•</span>
            <span className="code">{payload.agent_action}</span>
          </div>
        )}
        {citations.length > 0 && (
          <div className="mt-3 rounded-lg border border-slate-700/80 bg-slate-900/40 p-3">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
              Sources
            </div>
            <div className="mt-2 space-y-2">
              {visibleCitations.map((c, idx) => (
                <div key={`${c.file_path}-${idx}`} className="rounded-md border border-slate-800/90 p-2">
                  <div className="flex items-center justify-between gap-2 text-[11px]">
                    <span className="truncate text-slate-300">{c.file_path}</span>
                    <span className="shrink-0 text-slate-500">
                      relevance {(c.score * 100).toFixed(1)}%
                    </span>
                  </div>
                  <pre className="mt-1 whitespace-pre-wrap break-words rounded bg-slate-950/80 p-2 text-[11px] text-slate-400">
                    {c.snippet}
                  </pre>
                </div>
              ))}
            </div>
            {citations.length > 3 && (
              <button
                type="button"
                onClick={() => setShowAllCitations((v) => !v)}
                className="mt-2 text-[11px] font-medium text-emerald-400/90 hover:text-emerald-300"
              >
                {showAllCitations ? "Show fewer sources" : `Show ${citations.length - 3} more sources`}
              </button>
            )}
          </div>
        )}
      </div>
      {payload && <DecisionTraceCard payload={payload} />}
    </motion.div>
  );
}
