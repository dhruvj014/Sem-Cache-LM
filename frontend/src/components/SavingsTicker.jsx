import { useQuery } from "@tanstack/react-query";
import { Coins, Sparkles, Zap } from "lucide-react";
import { api } from "../api/client.js";

const ILLUSTRATIVE_USD_PER_1K = 0.002;

export default function SavingsTicker() {
  const { data, isFetching } = useQuery({
    queryKey: ["analytics-summary-ticker"],
    queryFn: () => api.summary(),
    refetchInterval: 2500,
  });

  const tokens = data?.estimated_tokens_saved ?? 0;
  const hits = data?.cache_hits ?? 0;
  const llm = data?.llm_calls ?? 0;
  const illustrativeUsd = (tokens / 1000) * ILLUSTRATIVE_USD_PER_1K;
  const hitRatePct = data?.hit_rate != null ? (data.hit_rate * 100).toFixed(1) : "—";

  return (
    <div className="glass rounded-xl p-3 border border-slate-800/80 h-full min-h-[88px]">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[11px] uppercase tracking-widest text-slate-500 flex items-center gap-1.5">
          <Sparkles size={12} className="text-amber-400/90" />
          Live savings
        </span>
        {isFetching && (
          <span className="text-[10px] text-slate-600 animate-pulse">Updating…</span>
        )}
      </div>
      <div className="grid grid-cols-3 gap-2 text-center">
        <div className="rounded-lg bg-emerald-500/10 border border-emerald-500/25 px-2 py-2">
          <div className="flex items-center justify-center gap-1 text-emerald-400/90 mb-0.5">
            <Zap size={14} />
          </div>
          <div className="text-lg font-bold text-emerald-200 tabular-nums leading-none">
            {tokens.toLocaleString()}
          </div>
          <div className="text-[10px] text-slate-500 mt-1">tokens saved (est.)</div>
        </div>
        <div className="rounded-lg bg-cyan-500/10 border border-cyan-500/25 px-2 py-2">
          <div className="text-lg font-bold text-cyan-200 tabular-nums leading-none">
            {hits}
          </div>
          <div className="text-[10px] text-slate-500 mt-1">cache hits</div>
          <div className="text-[9px] text-slate-600">hit rate {hitRatePct}%</div>
        </div>
        <div className="rounded-lg bg-amber-500/10 border border-amber-500/25 px-2 py-2">
          <div className="flex items-center justify-center gap-1 text-amber-400/90 mb-0.5">
            <Coins size={14} />
          </div>
          <div className="text-lg font-bold text-amber-200 tabular-nums leading-none">
            ~${illustrativeUsd.toFixed(4)}
          </div>
          <div className="text-[10px] text-slate-500 mt-1">illustrative @ ${ILLUSTRATIVE_USD_PER_1K}/1K</div>
        </div>
      </div>
      <div className="mt-2 text-[10px] text-slate-600 text-center">
        LLM generations recorded: <span className="code text-slate-500">{llm}</span>
      </div>
    </div>
  );
}
