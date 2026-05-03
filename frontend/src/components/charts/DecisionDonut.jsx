import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from "recharts";

const COLORS = {
  CACHE_HIT: "#34d399",
  VALIDATE: "#14b8a6",
  LLM_FALLBACK: "#60a5fa",
  FALSE_HIT: "#f59e0b",
};

export default function DecisionDonut({ summary, history }) {
  const counts = { CACHE_HIT: 0, VALIDATE: 0, LLM_FALLBACK: 0, FALSE_HIT: 0 };
  for (const h of history || []) {
    if (h.source === "false_hit_fallback") counts.FALSE_HIT += 1;
    else if (h.agent_action === "CACHE_HIT") counts.CACHE_HIT += 1;
    else if (h.agent_action === "VALIDATE") counts.VALIDATE += 1;
    else if (h.agent_action === "LLM_FALLBACK") counts.LLM_FALLBACK += 1;
  }
  const data = Object.entries(counts).map(([name, value]) => ({ name, value }));
  return (
    <div className="glass rounded-xl p-4">
      <div className="text-sm font-semibold mb-3">Decision Breakdown</div>
      <ResponsiveContainer width="100%" height={220}>
        <PieChart>
          <Pie
            data={data}
            innerRadius={50}
            outerRadius={80}
            dataKey="value"
            nameKey="name"
            label
          >
            {data.map((d) => (
              <Cell key={d.name} fill={COLORS[d.name]} />
            ))}
          </Pie>
          <Legend />
          <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #334155" }} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
