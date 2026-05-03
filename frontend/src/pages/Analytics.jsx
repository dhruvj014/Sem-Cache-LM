import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client.js";
import HitRateChart from "../components/charts/HitRateChart.jsx";
import LatencyBarChart from "../components/charts/LatencyBarChart.jsx";
import DecisionDonut from "../components/charts/DecisionDonut.jsx";
import QualityHistogram from "../components/charts/QualityHistogram.jsx";
import CacheStressBench from "../components/CacheStressBench.jsx";
import QualityFeedbackSlice from "../components/QualityFeedbackSlice.jsx";

function StatCard({ label, value, hint }) {
  return (
    <div className="glass rounded-xl p-4">
      <div className="text-[11px] uppercase tracking-widest text-slate-500">{label}</div>
      <div className="text-2xl font-semibold mt-1 code">{value}</div>
      {hint && <div className="text-xs text-slate-400 mt-1">{hint}</div>}
    </div>
  );
}

export default function Analytics() {
  const summary = useQuery({
    queryKey: ["summary"],
    queryFn: () => api.summary(),
    refetchInterval: 4000,
  });
  const history = useQuery({
    queryKey: ["history"],
    queryFn: () => api.history(50),
    refetchInterval: 4000,
  });
  const cache = useQuery({
    queryKey: ["cache-entries-analytics"],
    queryFn: () => api.listCache(1, 200),
    refetchInterval: 6000,
  });

  const s = summary.data;
  const h = history.data?.entries || [];
  const entries = cache.data?.entries || [];

  return (
    <div className="px-6 py-4 space-y-4 overflow-y-auto h-full">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">Analytics Dashboard</h2>
          <p className="text-sm text-slate-400">
            Live system metrics — refreshing every few seconds.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <CacheStressBench />
        <QualityFeedbackSlice entries={entries} />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard label="Total Queries" value={s?.total_queries ?? 0} />
        <StatCard
          label="Hit Rate"
          value={s ? `${(s.hit_rate * 100).toFixed(1)}%` : "—"}
          hint={`${s?.cache_hits ?? 0} cache · ${s?.llm_calls ?? 0} llm`}
        />
        <StatCard
          label="Avg Cache Latency"
          value={s ? `${s.avg_cache_latency_ms.toFixed(0)} ms` : "—"}
        />
        <StatCard
          label="Avg LLM Latency"
          value={s ? `${s.avg_llm_latency_ms.toFixed(0)} ms` : "—"}
        />
      </div>

      <div className="glass rounded-xl px-4 py-3 flex items-center justify-between">
        <div>
          <div className="text-[11px] uppercase tracking-widest text-slate-500">
            Estimated Savings
          </div>
          <div className="text-sm mt-1">
            Tokens saved:{" "}
            <span className="code text-emerald-300">
              {(s?.estimated_tokens_saved ?? 0).toLocaleString()}
            </span>{" "}
            · Time saved:{" "}
            <span className="code text-emerald-300">
              {((s?.estimated_time_saved_ms ?? 0) / 1000).toFixed(1)}s
            </span>
          </div>
        </div>
        <div className="text-xs text-slate-500">
          False hits detected:{" "}
          <span className="code text-amber-300">{s?.false_hits ?? 0}</span> · Validate
          decisions:{" "}
          <span className="code text-teal-300">{s?.validate_decisions ?? 0}</span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <HitRateChart history={h} />
        <LatencyBarChart history={h} />
        <DecisionDonut summary={s} history={h} />
        <QualityHistogram entries={entries} />
      </div>

      <div className="glass rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-800 text-sm font-semibold">
          Recent Query Log
        </div>
        <table className="w-full text-xs">
          <thead className="bg-slate-900/60 text-slate-500 uppercase tracking-wider">
            <tr>
              <th className="text-left px-3 py-2">Time</th>
              <th className="text-left px-3 py-2">Query</th>
              <th className="text-left px-3 py-2">Source</th>
              <th className="text-left px-3 py-2">Action</th>
              <th className="text-right px-3 py-2">Sim</th>
              <th className="text-right px-3 py-2">Latency</th>
            </tr>
          </thead>
          <tbody>
            {h.slice(0, 20).map((e, i) => (
              <tr key={i} className="border-t border-slate-800/60">
                <td className="px-3 py-2 text-slate-500">
                  {e.timestamp?.slice(11, 19)}
                </td>
                <td className="px-3 py-2 truncate max-w-md">{e.query}</td>
                <td className="px-3 py-2 code">{e.source}</td>
                <td className="px-3 py-2 code">{e.agent_action}</td>
                <td className="px-3 py-2 text-right code">
                  {(e.similarity_score * 100).toFixed(1)}%
                </td>
                <td className="px-3 py-2 text-right code">
                  {e.latency_ms.toFixed(0)} ms
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
