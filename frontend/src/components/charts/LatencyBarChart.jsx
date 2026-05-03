import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from "recharts";

export default function LatencyBarChart({ history }) {
  const data = [...(history || [])]
    .reverse()
    .slice(-15)
    .map((h, i) => ({
      i: i + 1,
      cache: ["cache", "validated_cache"].includes(h.source) ? h.latency_ms : 0,
      llm: ["llm", "false_hit_fallback"].includes(h.source) ? h.latency_ms : 0,
    }));
  return (
    <div className="glass rounded-xl p-4">
      <div className="text-sm font-semibold mb-3">Latency Comparison (last 15)</div>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data}>
          <CartesianGrid stroke="#1e293b" />
          <XAxis dataKey="i" stroke="#475569" />
          <YAxis stroke="#475569" unit="ms" />
          <Tooltip
            contentStyle={{ background: "#0f172a", border: "1px solid #334155" }}
          />
          <Legend />
          <Bar dataKey="cache" fill="#34d399" />
          <Bar dataKey="llm" fill="#60a5fa" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
