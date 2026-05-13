import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { api } from "../api/client.js";

export default function CacheSearchPanel() {
  const [q, setQ] = useState("");
  const [minQ, setMinQ] = useState(0);
  const [maxQ, setMaxQ] = useState(1);
  const [sortBy, setSortBy] = useState("quality");
  const [page, setPage] = useState(1);

  const searchMut = useMutation({
    mutationFn: ({ page: pg = 1 }) =>
      api.searchCache({
        query: q,
        minQuality: minQ,
        maxQuality: maxQ,
        sortBy,
        page: pg,
        pageSize: 15,
      }),
  });

  const data = searchMut.data;

  return (
    <div className="glass rounded-lg border border-slate-600/40 p-4 space-y-4">
      <div className="text-sm font-medium text-slate-200">Search &amp; filter cache</div>
      <div className="flex flex-wrap gap-2 items-end">
        <div className="flex-1 min-w-[200px]">
          <label className="text-xs text-slate-500 block mb-1">Keyword (question / answer)</label>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="w-full bg-slate-900/80 border border-slate-600 rounded-md px-3 py-2 text-sm"
            placeholder="substring match…"
          />
        </div>
        <div>
          <label className="text-xs text-slate-500 block mb-1">Sort</label>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="bg-slate-900/80 border border-slate-600 rounded-md px-2 py-2 text-sm"
          >
            <option value="quality">Quality</option>
            <option value="date">Date</option>
            <option value="similarity">Similarity (uses keyword)</option>
          </select>
        </div>
        <button
          type="button"
          onClick={() => {
            setPage(1);
            searchMut.mutate({ page: 1 });
          }}
          disabled={searchMut.isPending}
          className="flex items-center gap-2 px-4 py-2 rounded-md bg-cyan-600/20 border border-cyan-500/40 text-cyan-100 text-sm hover:bg-cyan-600/30 disabled:opacity-50"
        >
          <Search size={16} /> {searchMut.isPending ? "Searching…" : "Search"}
        </button>
      </div>
      <div className="grid sm:grid-cols-2 gap-4">
        <div>
          <div className="flex justify-between text-xs text-slate-500 mb-1">
            <span>Min quality</span>
            <span className="code">{minQ.toFixed(2)}</span>
          </div>
          <input
            type="range"
            min={0}
            max={1}
            step={0.01}
            value={minQ}
            onChange={(e) => setMinQ(Number(e.target.value))}
            className="w-full"
          />
        </div>
        <div>
          <div className="flex justify-between text-xs text-slate-500 mb-1">
            <span>Max quality</span>
            <span className="code">{maxQ.toFixed(2)}</span>
          </div>
          <input
            type="range"
            min={0}
            max={1}
            step={0.01}
            value={maxQ}
            onChange={(e) => setMaxQ(Number(e.target.value))}
            className="w-full"
          />
        </div>
      </div>

      {searchMut.isError && (
        <div className="text-sm text-rose-300">{searchMut.error?.message || "Search failed"}</div>
      )}

      {data && (
        <div className="space-y-2">
          <div className="text-xs text-slate-500">
            {data.total} match(es) · page {data.page} /{" "}
            {Math.max(1, Math.ceil(data.total / (data.page_size || 15)))}
          </div>
          <ul className="space-y-2 max-h-72 overflow-y-auto">
            {(data.entries || []).map((e) => (
              <li
                key={e.cache_id}
                className="rounded-md border border-slate-700/80 bg-slate-900/40 px-3 py-2 text-sm"
              >
                <div className="flex justify-between gap-2">
                  <span className="text-slate-300 truncate">{e.query_preview}</span>
                  <span className="code text-amber-200 shrink-0">
                    {(e.quality_score ?? 0).toFixed(2)}
                  </span>
                </div>
                <div className="text-[11px] text-slate-500 mt-1 flex justify-between gap-2">
                  <span className="truncate">{e.cache_id}</span>
                  <span className="code shrink-0">{e.source || "—"}</span>
                  <span>{(e.created_at || "").slice(0, 19)}</span>
                </div>
              </li>
            ))}
          </ul>
          <div className="flex gap-2 justify-end">
            <button
              type="button"
              disabled={page <= 1 || searchMut.isPending}
              onClick={() => {
                const np = Math.max(1, page - 1);
                setPage(np);
                searchMut.mutate({ page: np });
              }}
              className="text-xs px-2 py-1 rounded border border-slate-600 disabled:opacity-40"
            >
              Prev
            </button>
            <button
              type="button"
              disabled={!data || page * (data.page_size || 15) >= data.total || searchMut.isPending}
              onClick={() => {
                const np = page + 1;
                setPage(np);
                searchMut.mutate({ page: np });
              }}
              className="text-xs px-2 py-1 rounded border border-slate-600 disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
