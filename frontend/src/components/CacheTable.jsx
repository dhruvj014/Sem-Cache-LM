import { Trash2 } from "lucide-react";

function qualityColor(q) {
  if (q < 0.4) return "bg-rose-500";
  if (q < 0.7) return "bg-amber-400";
  return "bg-emerald-400";
}

export default function CacheTable({ entries, onDelete }) {
  if (!entries?.length) {
    return (
      <div className="glass rounded-xl p-8 text-center text-slate-500 text-sm">
        No cache entries yet. Send a query from the Chat page to populate the cache.
      </div>
    );
  }
  return (
    <div className="glass rounded-xl overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-slate-900/60 text-xs uppercase tracking-wider text-slate-500">
          <tr>
            <th className="text-left px-4 py-2">Query Preview</th>
            <th className="text-left px-4 py-2 w-48">Quality</th>
            <th className="text-left px-4 py-2 w-20">Hits</th>
            <th className="text-left px-4 py-2 w-44">Created</th>
            <th className="text-right px-4 py-2 w-20">Actions</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((e) => (
            <tr key={e.id} className="border-t border-slate-800/60 hover:bg-slate-900/40">
              <td className="px-4 py-3 align-top">
                <div className="text-slate-100 truncate max-w-md">{e.query}</div>
                <div className="text-xs text-slate-500 code mt-0.5">{e.id}</div>
                <div className="flex gap-1 mt-1.5">
                  {e.promoted && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                      PROMOTED
                    </span>
                  )}
                  {e.demoted && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30">
                      DEMOTED
                    </span>
                  )}
                  {e.quality_score < 0.3 && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
                      ⚠ LOW QUALITY
                    </span>
                  )}
                </div>
              </td>
              <td className="px-4 py-3">
                <div className="flex items-center gap-2">
                  <div className="flex-1 h-2 bg-slate-800 rounded overflow-hidden">
                    <div
                      className={`${qualityColor(e.quality_score)} h-full`}
                      style={{ width: `${Math.round(e.quality_score * 100)}%` }}
                    />
                  </div>
                  <span className="code text-xs text-slate-300">
                    {e.quality_score.toFixed(2)}
                  </span>
                </div>
              </td>
              <td className="px-4 py-3 code">{e.hit_count}</td>
              <td className="px-4 py-3 text-xs text-slate-400">
                {e.created_at?.slice(0, 19).replace("T", " ")}
              </td>
              <td className="px-4 py-3 text-right">
                <button
                  onClick={() => onDelete(e.id)}
                  className="p-1.5 rounded-md text-slate-400 hover:text-rose-300 hover:bg-rose-500/10"
                >
                  <Trash2 size={14} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
