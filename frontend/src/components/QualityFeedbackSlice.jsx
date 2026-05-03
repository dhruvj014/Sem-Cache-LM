import { ThumbsUp, AlertTriangle, Flag, Layers } from "lucide-react";

const BUCKETS = [
  { min: 0, max: 0.3, label: "0.0–0.3", color: "bg-rose-500/60" },
  { min: 0.3, max: 0.6, label: "0.3–0.6", color: "bg-amber-500/60" },
  { min: 0.6, max: 0.9, label: "0.6–0.9", color: "bg-cyan-500/60" },
  { min: 0.9, max: 1.01, label: "0.9–1.0", color: "bg-emerald-500/60" },
];

export default function QualityFeedbackSlice({ entries }) {
  const list = entries || [];
  const n = list.length;
  const promoted = list.filter((e) => e.promoted).length;
  const demoted = list.filter((e) => e.demoted).length;
  const risky = list.filter((e) => e.quality_score < 0.35).length;

  const bucketCounts = BUCKETS.map((b) => ({
    ...b,
    count: list.filter((e) => e.quality_score >= b.min && e.quality_score < b.max).length,
  }));
  const maxC = Math.max(...bucketCounts.map((b) => b.count), 1);

  const lastEvictionNote =
    risky > 0
      ? `${risky} entr${risky === 1 ? "y" : "ies"} under ~0.35 quality (candidates for eviction)`
      : "No low-quality rows in this sample";

  return (
    <div className="glass rounded-xl p-4 border border-slate-800/80">
      <div className="flex items-center gap-2 mb-3">
        <Layers className="text-amber-400" size={18} />
        <h3 className="text-sm font-semibold text-slate-200">Quality &amp; feedback snapshot</h3>
        <span className="text-[10px] text-slate-500 ml-auto code">{n} entries</span>
      </div>

      <div className="grid grid-cols-3 gap-2 mb-4 text-center text-xs">
        <div className="rounded-lg bg-slate-900/60 border border-slate-800 py-2 px-1">
          <div className="flex items-center justify-center gap-1 text-slate-500 mb-0.5">
            <ThumbsUp size={12} /> Promoted
          </div>
          <div className="text-lg font-semibold text-emerald-300">{promoted}</div>
        </div>
        <div className="rounded-lg bg-slate-900/60 border border-slate-800 py-2 px-1">
          <div className="flex items-center justify-center gap-1 text-slate-500 mb-0.5">
            <Flag size={12} /> Demoted
          </div>
          <div className="text-lg font-semibold text-amber-300">{demoted}</div>
        </div>
        <div className="rounded-lg bg-slate-900/60 border border-slate-800 py-2 px-1">
          <div className="flex items-center justify-center gap-1 text-slate-500 mb-0.5">
            <AlertTriangle size={12} /> Low Q
          </div>
          <div className="text-lg font-semibold text-rose-300">{risky}</div>
        </div>
      </div>

      <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-2">Quality distribution</div>
      <div className="space-y-2">
        {bucketCounts.map((b) => (
          <div key={b.label} className="flex items-center gap-2 text-xs">
            <span className="w-16 text-slate-500 shrink-0">{b.label}</span>
            <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full ${b.color}`}
                style={{ width: `${(b.count / maxC) * 100}%` }}
              />
            </div>
            <span className="w-6 text-right code text-slate-400">{b.count}</span>
          </div>
        ))}
      </div>

      <p className="mt-3 text-[11px] text-slate-500 leading-snug border-t border-slate-800/80 pt-3">
        <strong className="text-slate-400">Eviction hint:</strong> {lastEvictionNote}. Use{" "}
        <span className="code text-slate-400">POST /cache/evict</span> on the API or evict from
        Cache Explorer for low-quality rows.
      </p>
    </div>
  );
}
