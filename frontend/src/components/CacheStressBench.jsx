import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Gauge, Play } from "lucide-react";
import { api } from "../api/client.js";

const STRESS_QUERIES = [
  "What is a distributed system?",
  "What is a distributed system?",
  "Can you explain what distributed systems are?",
  "Describe the CAP theorem in plain English.",
  "What does the CAP theorem mean?",
  "What is a distributed system?",
  "Briefly define eventual consistency.",
];

function cacheHitLike(source) {
  return source === "cache" || source === "validated_cache";
}

export default function CacheStressBench() {
  const [running, setRunning] = useState(false);
  const [rows, setRows] = useState([]);
  const [error, setError] = useState(null);

  const runBench = async () => {
    setRunning(true);
    setError(null);
    setRows([]);
    const sid = `stress-${Date.now()}`;
    const out = [];
    try {
      for (let i = 0; i < STRESS_QUERIES.length; i++) {
        const q = STRESS_QUERIES[i];
        const payload = await api.query(q, sid);
        out.push({
          i: i + 1,
          ms: Math.round(payload.latency_ms),
          source: payload.source,
          hit: cacheHitLike(payload.source),
        });
      }
      setRows(out);
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setRunning(false);
    }
  };

  const hitRate =
    rows.length > 0
      ? ((rows.filter((r) => r.hit).length / rows.length) * 100).toFixed(0)
      : "—";
  const sorted = [...rows].map((r) => r.ms).sort((a, b) => a - b);
  const p50 = sorted.length ? sorted[Math.floor(sorted.length * 0.5)] : 0;
  const p95 = sorted.length ? sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * 0.95))] : 0;

  const chartData = rows.map((r) => ({
    q: `#${r.i}`,
    ms: r.ms,
    fill: r.hit ? "#34d399" : "#60a5fa",
  }));

  return (
    <div className="glass rounded-xl p-4 border border-slate-800/80">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
        <div className="flex items-center gap-2">
          <Gauge className="text-fuchsia-400" size={20} />
          <div>
            <h3 className="text-sm font-semibold text-slate-200">Stress the cache</h3>
            <p className="text-[11px] text-slate-500 mt-0.5">
              Runs {STRESS_QUERIES.length} sequential queries (same session) to warm hits ·
              pollutes shared cache
            </p>
          </div>
        </div>
        <button
          type="button"
          disabled={running}
          onClick={runBench}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-fuchsia-500/20 border border-fuchsia-500/50 text-fuchsia-200 text-sm font-medium hover:bg-fuchsia-500/30 disabled:opacity-50"
        >
          <Play size={16} />
          {running ? "Running…" : "Run micro-benchmark"}
        </button>
      </div>

      {error && (
        <div className="mb-3 text-sm text-rose-400 px-2">{error}</div>
      )}

      {rows.length > 0 && (
        <>
          <div className="grid grid-cols-3 gap-2 mb-4 text-center text-xs">
            <div className="rounded-lg bg-slate-900/70 border border-slate-800 py-2">
              <div className="text-slate-500">Hit rate</div>
              <div className="text-lg font-semibold text-emerald-300">{hitRate}%</div>
            </div>
            <div className="rounded-lg bg-slate-900/70 border border-slate-800 py-2">
              <div className="text-slate-500">p50 latency</div>
              <div className="text-lg font-semibold text-slate-200 code">{p50} ms</div>
            </div>
            <div className="rounded-lg bg-slate-900/70 border border-slate-800 py-2">
              <div className="text-slate-500">p95 latency</div>
              <div className="text-lg font-semibold text-slate-200 code">{p95} ms</div>
            </div>
          </div>
          <div className="h-48 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="q" tick={{ fontSize: 10, fill: "#94a3b8" }} />
                <YAxis
                  tick={{ fontSize: 10, fill: "#94a3b8" }}
                  label={{ value: "ms", angle: -90, position: "insideLeft", fill: "#64748b", fontSize: 10 }}
                />
                <Tooltip
                  contentStyle={{ background: "#0f172a", border: "1px solid #334155", borderRadius: "8px" }}
                  labelStyle={{ color: "#94a3b8" }}
                  formatter={(v, _n, p) => [
                    `${v} ms (${p.payload.fill === "#34d399" ? "cache path" : "LLM path"})`,
                    "latency",
                  ]}
                />
                <Bar dataKey="ms" radius={[4, 4, 0, 0]}>
                  {chartData.map((_, index) => (
                    <Cell key={`c-${index}`} fill={chartData[index].fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-2 flex gap-4 text-[10px] text-slate-500 justify-center">
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 rounded bg-emerald-400/80" /> cache / validated
            </span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 rounded bg-blue-400/80" /> LLM / fallback
            </span>
          </div>
        </>
      )}
    </div>
  );
}
