import { motion } from "framer-motion";
import { ChevronDown, ChevronUp } from "lucide-react";
import DecisionTraceCard from "./DecisionTraceCard.jsx";
import SourceBadge from "./SourceBadge.jsx";
import { useSessionStore } from "../store/sessionStore.js";

function assistantBodyIsLong(text) {
  if (!text) return false;
  return text.split("\n").length > 2 || text.length > 220;
}

export default function ResponseCard({ message }) {
  const toggleBody = useSessionStore((s) => s.toggleMessageBodyCollapsed);
  const isUser = message.role === "user";
  const long = !isUser && assistantBodyIsLong(message.content);
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

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      className="max-w-3xl"
    >
      <div className="glass rounded-xl px-4 py-3">
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
      </div>
      {payload && <DecisionTraceCard payload={payload} />}
    </motion.div>
  );
}
