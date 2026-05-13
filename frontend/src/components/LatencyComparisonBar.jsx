import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client.js";

export default function LatencyComparisonBar() {
  const { data } = useQuery({
    queryKey: ["summary"],
    queryFn: () => api.summary(),
    refetchInterval: 3000,
  });

  const cache = data?.avg_cache_latency_ms || 0;
  const llm = data?.avg_llm_latency_ms || 0;
  const max = Math.max(cache, llm, 1);

  return (
    <div className="glass rounded-xl p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[11px] uppercase tracking-widest text-slate-500">
          Live Latency Comparison
        </span>
        <span className="text-xs text-slate-500">
          {data?.total_queries ?? 0} queries · {data?.cache_hits ?? 0} cache hits
        </span>
      </div>
      <Row label="Cache avg" value={cache} max={max} color="bg-emerald-400" />
      <Row label="LLM avg"   value={llm}   max={max} color="bg-blue-400" />
    </div>
  );
}

function Row({ label, value, max, color }) {
  const pct = max > 0 ? (value / max) * 100 : 0;
  return (
    <div className="flex items-center gap-3 mb-1.5 last:mb-0">
      <span className="w-20 text-xs text-slate-400">{label}</span>
      <div className="flex-1 h-3 bg-slate-800 rounded-md overflow-hidden">
        <div className={`${color} h-full`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-20 text-right code text-xs">{value.toFixed(0)} ms</span>
    </div>
  );
}
