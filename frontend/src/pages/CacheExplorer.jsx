import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Trash } from "lucide-react";
import { api } from "../api/client.js";
import CacheTable from "../components/CacheTable.jsx";

export default function CacheExplorer() {
  const qc = useQueryClient();
  const [toast, setToast] = useState(null);

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

  return (
    <div className="px-6 py-4 space-y-4 overflow-y-auto h-full">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">Cache Explorer</h2>
          <p className="text-sm text-slate-400">
            Browse stored semantic cache entries. Quality scores update from feedback.
          </p>
        </div>
        <button
          onClick={() => evictMut.mutate()}
          className="flex items-center gap-2 px-3 py-2 rounded-md bg-amber-500/15 border border-amber-500/40 text-amber-200 text-sm hover:bg-amber-500/25"
        >
          <Trash size={14} /> Trigger Eviction
        </button>
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
