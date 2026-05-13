import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client.js";

export default function CacheHealthWidget() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["cache-health-score"],
    queryFn: () => api.getCacheHealthScore(),
    refetchInterval: 10_000,
  });

  if (isLoading) {
    return (
      <div className="glass rounded-xl p-4 text-sm text-slate-400">Loading cache health…</div>
    );
  }
  if (isError || !data) {
    return (
      <div className="glass rounded-xl p-4 text-sm text-rose-300 border border-rose-500/30">
        Could not load cache health score.
      </div>
    );
  }

  const total = Math.max(1, data.total || 0);
  const h = ((data.healthy || 0) / total) * 100;
  const d = ((data.degrading || 0) / total) * 100;
  const c = ((data.critical || 0) / total) * 100;
  const pct = data.overall_health_percent ?? 0;

  return (
    <div className="glass rounded-xl p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-[11px] uppercase tracking-widest text-slate-500">
            Cache health
          </div>
          <div className="text-2xl font-semibold text-emerald-300 mt-1">{pct.toFixed(1)}%</div>
          <div className="text-xs text-slate-400">healthy share · {data.total} entries</div>
        </div>
        <div className="text-right text-xs text-slate-500 space-y-0.5">
          <div>
            <span className="text-emerald-400">●</span> healthy &gt;0.8:{" "}
            <span className="code text-slate-200">{data.healthy}</span>
          </div>
          <div>
            <span className="text-amber-400">●</span> 0.3–0.8:{" "}
            <span className="code text-slate-200">{data.degrading}</span>
          </div>
          <div>
            <span className="text-rose-400">●</span> &lt;0.3:{" "}
            <span className="code text-slate-200">{data.critical}</span>
          </div>
        </div>
      </div>
      <div className="h-3 w-full rounded-full overflow-hidden flex bg-slate-800">
        <div className="h-full bg-emerald-500/90" style={{ width: `${h}%` }} title="healthy" />
        <div className="h-full bg-amber-500/90" style={{ width: `${d}%` }} title="degrading" />
        <div className="h-full bg-rose-600/90" style={{ width: `${c}%` }} title="critical" />
      </div>
    </div>
  );
}
