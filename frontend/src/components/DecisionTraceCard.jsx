import SourceBadge from "./SourceBadge.jsx";
import FeedbackButtons from "./FeedbackButtons.jsx";

export default function DecisionTraceCard({ payload }) {
  if (!payload) return null;
  const {
    source,
    similarity_score,
    latency_ms,
    agent_action,
    decision_reason,
    matched_query,
    matched_cache_id,
    cache_id,
    hit_count,
    quality_score,
    validation_confidence,
  } = payload;

  return (
    <div className="glass rounded-xl mt-3 overflow-hidden">
      <div className="px-4 py-3 flex flex-wrap items-center justify-between gap-x-3 gap-y-2 border-b border-slate-800">
        <SourceBadge source={source} size="lg" />
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-400">
          <span>
            Similarity{" "}
            <span className="code text-slate-200">
              {(similarity_score * 100).toFixed(1)}%
            </span>
          </span>
          <span className="text-slate-600 select-none" aria-hidden>
            ·
          </span>
          <span>{latency_ms.toFixed(0)} ms</span>
        </div>
      </div>
      <div className="px-4 py-3 grid grid-cols-2 gap-y-2 text-sm">
        <div className="text-slate-400">Agent Decision</div>
        <div className="code">{agent_action}</div>
        <div className="text-slate-400">Reason</div>
        <div className="text-slate-200">{decision_reason}</div>
        {matched_query && (
          <>
            <div className="text-slate-400">Matched Query</div>
            <div className="text-slate-200 italic">"{matched_query}"</div>
          </>
        )}
        {matched_cache_id && matched_cache_id !== cache_id && (
          <>
            <div className="text-slate-400">Rejected cache entry</div>
            <div className="code text-xs break-all">{matched_cache_id}</div>
          </>
        )}
        {cache_id && (
          <>
            <div className="text-slate-400">
              {matched_cache_id && matched_cache_id !== cache_id
                ? "New answer cache id"
                : "Cache Entry ID"}
            </div>
            <div className="code text-xs break-all">{cache_id}</div>
          </>
        )}
        {hit_count != null && (
          <>
            <div className="text-slate-400">Hit Count</div>
            <div className="code">{hit_count}</div>
          </>
        )}
        {quality_score != null && (
          <>
            <div className="text-slate-400">Quality Score</div>
            <div className="code">{quality_score.toFixed(3)}</div>
          </>
        )}
        {validation_confidence != null && (
          <>
            <div className="text-slate-400">Judge confidence</div>
            <div className="space-y-0.5">
              <div className="code">{validation_confidence.toFixed(2)}</div>
              <div className="text-[10px] text-slate-500 leading-tight">
                How sure the validator is of its YES/NO verdict — not the same as
                embedding similarity above.
              </div>
            </div>
          </>
        )}
      </div>
      <div className="px-4 py-3 border-t border-slate-800 flex items-center justify-between">
        <span className="text-xs text-slate-500">Was this response helpful?</span>
        <FeedbackButtons cacheId={cache_id} />
      </div>
    </div>
  );
}
