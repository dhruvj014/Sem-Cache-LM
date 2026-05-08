import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client.js";

const SERVICE_LABELS = {
  redis: "Redis",
  ai_service: "AI Service",
  cache_service: "Cache Service",
  rag_service: "RAG Service",
  analytics_service: "Analytics Service",
  orchestrator_service: "Orchestrator Service",
};

export default function Settings() {
  const { data } = useQuery({ queryKey: ["health"], queryFn: () => api.health() });
  const apiUrl = import.meta.env.VITE_API_URL || "http://localhost:8000";

  return (
    <div className="px-6 py-4 max-w-2xl space-y-4 overflow-y-auto h-full">
      <div>
        <h2 className="text-xl font-semibold">Settings</h2>
        <p className="text-sm text-slate-400">
          Read-only system configuration — runtime values come from the backend.
        </p>
      </div>

      <div className="glass rounded-xl p-4 space-y-2 text-sm">
        <div className="flex justify-between">
          <span className="text-slate-400">API Base URL</span>
          <span className="code">{apiUrl}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-400">Backend Version</span>
          <span className="code">{data?.version ?? "—"}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-400">Status</span>
          <span className={`code ${data?.status === "ok" ? "text-emerald-300" : "text-rose-300"}`}>
            {data?.status ?? "—"}
          </span>
        </div>
      </div>

      <div className="glass rounded-xl p-4 space-y-2 text-sm">
        <div className="text-[11px] uppercase tracking-widest text-slate-500 mb-2">
          Service Health
        </div>
        {data?.services
          ? Object.entries(data.services).map(([k, v]) => (
              <div className="flex justify-between" key={k}>
                <span className="text-slate-400">{SERVICE_LABELS[k] || k}</span>
                <span className={`code ${v ? "text-emerald-300" : "text-rose-300"}`}>
                  {v ? "online" : "offline"}
                </span>
              </div>
            ))
          : null}
      </div>

      <div className="glass rounded-xl p-4 text-sm text-slate-400">
        Decision thresholds and Ollama model names are configured server-side via the
        backend <span className="code">.env</span> file.
      </div>
    </div>
  );
}
