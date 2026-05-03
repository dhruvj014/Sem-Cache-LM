import { useQuery } from "@tanstack/react-query";
import { Activity, GitBranch, Server } from "lucide-react";
import { api } from "../api/client.js";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const GIT_SHA = import.meta.env.VITE_GIT_SHA || "";

export default function EnvironmentStrip() {
  const { data: h } = useQuery({
    queryKey: ["health-strip"],
    queryFn: () => api.health(),
    refetchInterval: 15000,
  });

  const degrad = h?.status === "degraded";

  return (
    <footer className="border-t border-slate-800 bg-slate-950/80 px-4 py-2 text-[11px] text-slate-500 flex flex-wrap items-center gap-x-4 gap-y-1 justify-between">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <span className="flex items-center gap-1.5 text-slate-400">
          <Server size={12} className="text-slate-600" />
          API{" "}
          <span className="code text-slate-300 max-w-[220px] truncate" title={API_URL}>
            {API_URL}
          </span>
        </span>
        <span className="flex items-center gap-1.5">
          <Activity size={12} className={degrad ? "text-amber-500" : "text-emerald-600"} />
          v<span className="code text-slate-400">{h?.version ?? "—"}</span>
          <span className={degrad ? "text-amber-400/90" : "text-emerald-400/90"}>
            {h?.status ?? "…"}
          </span>
        </span>
        {GIT_SHA ? (
          <span className="flex items-center gap-1.5">
            <GitBranch size={12} className="text-slate-600" />
            <span className="code text-slate-400">{GIT_SHA}</span>
          </span>
        ) : null}
      </div>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-slate-600">
        {h?.llm_model ? (
          <span>
            LLM <span className="code text-slate-400">{h.llm_model}</span>
          </span>
        ) : null}
        {h?.embedding_model ? (
          <span>
            Embed <span className="code text-slate-400">{h.embedding_model}</span>
          </span>
        ) : null}
        {h?.qdrant_collection ? (
          <span>
            Collection <span className="code text-slate-400">{h.qdrant_collection}</span>
          </span>
        ) : null}
      </div>
    </footer>
  );
}
