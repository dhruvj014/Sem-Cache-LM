import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Trash, Ban } from "lucide-react";
import { api } from "../api/client.js";
import CacheTable from "../components/CacheTable.jsx";

export default function CacheExplorer() {
  const qc = useQueryClient();
  const [toast, setToast] = useState(null);
  const [invMode, setInvMode] = useState("source");
  const [invValue, setInvValue] = useState("");
  const [invMessage, setInvMessage] = useState(null);

  const { data, isLoading } = useQuery({
    queryKey: ["cache-entries"],
    queryFn: () => api.listCache(1, 100),
    refetchInterval: 5000,
  });

  const deleteMut = useMutation({
    mutationFn: (id) => api.deleteCache(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["cache-entries"] }),
  });

  const evictMut = useMutation({
    mutationFn: () => api.evict(),
    onSuccess: (res) => {
      setToast(`Evicted ${res.evicted_count} low-quality entries.`);
      qc.invalidateQueries({ queryKey: ["cache-entries"] });
      setTimeout(() => setToast(null), 4000);
    },
  });

  const invalidateMut = useMutation({
    mutationFn: () => {
      const v = invValue.trim();
      if (!v) throw new Error("Enter a chunk_id or source identifier.");
      const body =
        invMode === "chunk_id" ? { chunk_id: v } : { source_identifier: v };
      return api.invalidateCache(body);
    },
    onSuccess: (res) => {
      setInvMessage({
        ok: true,
        text: `Invalidated ${res.cache_invalidated_count} cache entr${res.cache_invalidated_count === 1 ? "y" : "ies"}; RAG removed ${res.rag_deleted_chunk_points} point(s).`,
      });
      qc.invalidateQueries({ queryKey: ["cache-entries"] });
      setTimeout(() => setInvMessage(null), 6000);
    },
    onError: (err) => {
      setInvMessage({ ok: false, text: err.message || "Invalidation failed." });
      setTimeout(() => setInvMessage(null), 8000);
    },
  });

  return (
    <div className="px-6 py-4 space-y-4 overflow-y-auto h-full">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">Cache Explorer</h2>
          <p className="text-sm text-slate-400">
            Browse stored semantic cache entries. Quality scores update from feedback.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => evictMut.mutate()}
            className="flex items-center gap-2 px-3 py-2 rounded-md bg-amber-500/15 border border-amber-500/40 text-amber-200 text-sm hover:bg-amber-500/25"
          >
            <Trash size={14} /> Trigger Eviction
          </button>
        </div>
      </div>

      <div className="glass rounded-lg border border-slate-600/40 p-4 space-y-3">
        <div className="text-sm font-medium text-slate-200">RAG-linked invalidation</div>
        <p className="text-xs text-slate-400">
          Remove cache entries tied to a chunk id or a RAG source path, and delete matching RAG vectors
          (via gateway).
        </p>
        <div className="flex flex-wrap gap-2 items-center">
          <select
            value={invMode}
            onChange={(e) => setInvMode(e.target.value)}
            className="bg-slate-900/80 border border-slate-600 rounded-md px-2 py-1.5 text-sm text-slate-200"
          >
            <option value="source">Source identifier</option>
            <option value="chunk_id">Chunk ID</option>
          </select>
          <input
            type="text"
            value={invValue}
            onChange={(e) => setInvValue(e.target.value)}
            placeholder={invMode === "chunk_id" ? "e.g. Qdrant point id" : "e.g. repo:path from rag_citations"}
            className="flex-1 min-w-[200px] bg-slate-900/80 border border-slate-600 rounded-md px-3 py-1.5 text-sm text-slate-100 placeholder:text-slate-500"
          />
          <button
            type="button"
            disabled={invalidateMut.isPending}
            onClick={() => invalidateMut.mutate()}
            className="flex items-center gap-2 px-3 py-2 rounded-md bg-rose-500/15 border border-rose-500/40 text-rose-200 text-sm hover:bg-rose-500/25 disabled:opacity-50"
          >
            <Ban size={14} /> Invalidate
          </button>
        </div>
        {invMessage && (
          <div
            className={`rounded-md px-3 py-2 text-sm border ${
              invMessage.ok
                ? "text-emerald-300 border-emerald-500/40 bg-emerald-500/10"
                : "text-rose-300 border-rose-500/40 bg-rose-500/10"
            }`}
          >
            {invMessage.text}
          </div>
        )}
      </div>

      {toast && (
        <div className="glass rounded-md px-4 py-2 text-sm text-emerald-300 border border-emerald-500/40">
          {toast}
        </div>
      )}

      {isLoading ? (
        <div className="text-slate-500 text-sm">Loading…</div>
      ) : (
        <CacheTable
          entries={data?.entries || []}
          onDelete={(id) => deleteMut.mutate(id)}
        />
      )}
    </div>
  );
}
