import { useHealthQuery, useSummaryQuery } from "../hooks/useLiveStats.js";

const SERVICE_LABELS = {
  redis: "Redis",
  ai_service: "AI Service",
  cache_service: "Cache Service",
  rag_service: "RAG Service",
  analytics_service: "Analytics Service",
  orchestrator_service: "Orchestrator Service",
};

function Dot({ ok }) {
  return (
    <span
      className={`inline-block w-2.5 h-2.5 rounded-full ${
        ok ? "bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.8)]" : "bg-rose-500"
      }`}
    />
  );
}

export default function SystemMonitorPanel() {
  const summary = useSummaryQuery();
  const health = useHealthQuery();

  const s = summary.data;
  const h = health.data;
  const services = h?.services || {};
  const serviceRows = Object.entries(services);

  return (
    <aside className="glass rounded-xl p-4 w-72 flex-shrink-0 self-start sticky top-4">
      <div className="text-[11px] uppercase tracking-widest text-slate-500 mb-3">
        System Monitor
      </div>

      <div className="space-y-2 text-sm">
        <Row label="Cache Entries" value={s?.cache_entries ?? "—"} />
        <Row
          label="Hit Rate"
          value={s ? `${(s.hit_rate * 100).toFixed(1)}%` : "—"}
        />
        <Row label="Cache Hits" value={s?.cache_hits ?? "—"} />
        <Row label="LLM Calls" value={s?.llm_calls ?? "—"} />
        <Row label="False Hits" value={s?.false_hits ?? "—"} />
      </div>

      <div className="mt-4 border-t border-slate-800 pt-3">
        <div className="text-[11px] uppercase tracking-widest text-slate-500 mb-2">
          Last Decision
        </div>
        {s?.last_decision ? (
          <div className="text-xs space-y-1">
            <div className="code">{s.last_decision.agent_action}</div>
            <div className="text-slate-400">
              sim {(s.last_decision.similarity_score * 100).toFixed(1)}% ·{" "}
              {s.last_decision.latency_ms.toFixed(0)} ms
            </div>
            <div className="text-slate-500 italic truncate">
              "{s.last_decision.query_preview}"
            </div>
          </div>
        ) : (
          <div className="text-xs text-slate-500">No queries yet</div>
        )}
      </div>

      <div className="mt-4 border-t border-slate-800 pt-3 space-y-2 text-xs">
        {serviceRows.length > 0 ? (
          serviceRows.map(([name, ok]) => (
            <div className="flex items-center justify-between" key={name}>
              <span className="text-slate-400">{SERVICE_LABELS[name] || name}</span>
              <Dot ok={Boolean(ok)} />
            </div>
          ))
        ) : (
          <div className="text-slate-500">No service health reported</div>
        )}
      </div>

      {h?.status === "degraded" && (
        <div className="mt-3 px-2 py-1.5 rounded bg-rose-500/15 border border-rose-500/40 text-rose-300 text-xs">
          ⚠ One or more services are unreachable.
        </div>
      )}
    </aside>
  );
}

function Row({ label, value }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-slate-400">{label}</span>
      <span className="code text-slate-100">{value}</span>
    </div>
  );
}
