import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

export default function QualityHistogram({ entries }) {
  const buckets = [
    { range: "0.0-0.2", count: 0 },
    { range: "0.2-0.4", count: 0 },
    { range: "0.4-0.6", count: 0 },
    { range: "0.6-0.8", count: 0 },
    { range: "0.8-1.0", count: 0 },
  ];
  for (const e of entries || []) {
    const q = e.quality_score;
    const idx = Math.min(4, Math.floor(q * 5));
    buckets[idx].count += 1;
  }
  return (
    <div className="glass rounded-xl p-4">
      <div className="text-sm font-semibold mb-3">Quality Score Distribution</div>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={buckets}>
          <CartesianGrid stroke="#1e293b" />
          <XAxis dataKey="range" stroke="#475569" />
          <YAxis stroke="#475569" />
          <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #334155" }} />
          <Bar dataKey="count" fill="#a78bfa" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
