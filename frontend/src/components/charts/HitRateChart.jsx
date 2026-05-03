import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";

export default function HitRateChart({ history }) {
  // Transform history (most recent first) into rolling hit-rate.
  const reversed = [...(history || [])].reverse();
  let total = 0;
  let hits = 0;
  const data = reversed.map((h, i) => {
    total += 1;
    if (h.source === "cache" || h.source === "validated_cache") hits += 1;
    return { i: i + 1, hitRate: total > 0 ? (hits / total) * 100 : 0 };
  });
  return (
    <div className="glass rounded-xl p-4">
      <div className="text-sm font-semibold mb-3">Hit Rate Over Time</div>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={data}>
          <CartesianGrid stroke="#1e293b" />
          <XAxis dataKey="i" stroke="#475569" />
          <YAxis domain={[0, 100]} stroke="#475569" unit="%" />
          <Tooltip
            contentStyle={{ background: "#0f172a", border: "1px solid #334155" }}
          />
          <Line type="monotone" dataKey="hitRate" stroke="#34d399" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
