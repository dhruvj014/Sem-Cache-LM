import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client.js";

const SERVICE_LABELS = {
  redis: "Redis",
  ai_service: "AI Service",
  cache_service: "Cache Service",
  rag_service: "RAG Service",
  analytics_service: "Analytics Service",
  orchestrator_service: "Orchestrator Service",
};

function emptyDraft() {
  return {
    similarity_hit_threshold: 0.85,
    similarity_gray_zone_low: 0.55,
    quality_ema_alpha: 0.2,
    quality_eviction_threshold: 0.35,
  };
}

export default function Settings() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["health"], queryFn: () => api.health() });
  const thrQ = useQuery({ queryKey: ["thresholds"], queryFn: () => api.getThresholds() });
  const [draft, setDraft] = useState(emptyDraft);
  const [localErr, setLocalErr] = useState(null);

  useEffect(() => {
    if (thrQ.data) {
      setDraft({
        similarity_hit_threshold: thrQ.data.similarity_hit_threshold,
        similarity_gray_zone_low: thrQ.data.similarity_gray_zone_low,
        quality_ema_alpha: thrQ.data.quality_ema_alpha,
        quality_eviction_threshold: thrQ.data.quality_eviction_threshold,
      });
    }
  }, [thrQ.data]);

  const [savedBanner, setSavedBanner] = useState(false);

  const saveMut = useMutation({
    mutationFn: () =>
      api.updateThresholds({
        similarity_hit_threshold: draft.similarity_hit_threshold,
        similarity_gray_zone_low: draft.similarity_gray_zone_low,
        quality_ema_alpha: draft.quality_ema_alpha,
        quality_eviction_threshold: draft.quality_eviction_threshold,
      }),
    onSuccess: () => {
      setLocalErr(null);
      setSavedBanner(true);
      setTimeout(() => setSavedBanner(false), 3500);
      qc.invalidateQueries({ queryKey: ["thresholds"] });
    },
  });

  const apiUrl = import.meta.env.VITE_API_URL || "http://localhost:8000";

  const onSave = () => {
    if (draft.similarity_gray_zone_low >= draft.similarity_hit_threshold) {
      setLocalErr("SIMILARITY_GRAY_ZONE_LOW must be strictly less than SIMILARITY_HIT_THRESHOLD.");
      return;
    }
    setLocalErr(null);
    saveMut.mutate();
  };

  return (
    <div className="px-6 py-4 max-w-2xl space-y-4 overflow-y-auto h-full">
      <div>
        <h2 className="text-xl font-semibold">Settings</h2>
        <p className="text-sm text-slate-400">
          Service health is read-only. Similarity and quality tuning knobs can be updated live on the
          gateway (in-memory until restart for fields not persisted elsewhere).
        </p>
      </div>

      <div className="glass rounded-xl p-4 space-y-2 text-sm">
        <div className="flex justify-between">
          <span className="text-slate-400">API Base URL</span>
          <span className="code">{apiUrl}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-400">Backend Version</span>
          <span className="code">{data?.version ?? "—"}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-400">Status</span>
          <span className={`code ${data?.status === "ok" ? "text-emerald-300" : "text-rose-300"}`}>
            {data?.status ?? "—"}
          </span>
        </div>
      </div>

      <div className="glass rounded-xl p-4 space-y-2 text-sm">
        <div className="text-[11px] uppercase tracking-widest text-slate-500 mb-2">
          Service Health
        </div>
        {data?.services
          ? Object.entries(data.services).map(([k, v]) => (
              <div className="flex justify-between" key={k}>
                <span className="text-slate-400">{SERVICE_LABELS[k] || k}</span>
                <span className={`code ${v ? "text-emerald-300" : "text-rose-300"}`}>
                  {v ? "online" : "offline"}
                </span>
              </div>
            ))
          : null}
      </div>

      <div className="glass rounded-xl p-4 space-y-4 text-sm">
        <div className="text-[11px] uppercase tracking-widest text-slate-500">
          Runtime thresholds
        </div>
        {thrQ.isLoading && <div className="text-slate-500 text-sm">Loading thresholds…</div>}
        {thrQ.isError && (
          <div className="text-rose-300 text-sm">{thrQ.error?.message || "Failed to load thresholds"}</div>
        )}
        {!thrQ.isLoading && !thrQ.isError && (
          <>
            <div>
              <div className="flex justify-between text-xs text-slate-500 mb-1">
                <span>SIMILARITY_HIT_THRESHOLD</span>
                <span className="code">{draft.similarity_hit_threshold.toFixed(2)}</span>
              </div>
              <input
                type="range"
                min={0}
                max={1}
                step={0.01}
                value={draft.similarity_hit_threshold}
                onChange={(e) =>
                  setDraft((d) => ({ ...d, similarity_hit_threshold: Number(e.target.value) }))
                }
                className="w-full"
              />
            </div>
            <div>
              <div className="flex justify-between text-xs text-slate-500 mb-1">
                <span>SIMILARITY_GRAY_ZONE_LOW</span>
                <span className="code">{draft.similarity_gray_zone_low.toFixed(2)}</span>
              </div>
              <input
                type="range"
                min={0}
                max={1}
                step={0.01}
                value={draft.similarity_gray_zone_low}
                onChange={(e) =>
                  setDraft((d) => ({ ...d, similarity_gray_zone_low: Number(e.target.value) }))
                }
                className="w-full"
              />
            </div>
            <div>
              <div className="flex justify-between text-xs text-slate-500 mb-1">
                <span>QUALITY_EMA_ALPHA</span>
                <span className="code">{draft.quality_ema_alpha.toFixed(2)}</span>
              </div>
              <input
                type="range"
                min={0}
                max={1}
                step={0.01}
                value={draft.quality_ema_alpha}
                onChange={(e) =>
                  setDraft((d) => ({ ...d, quality_ema_alpha: Number(e.target.value) }))
                }
                className="w-full"
              />
            </div>
            <div>
              <div className="flex justify-between text-xs text-slate-500 mb-1">
                <span>QUALITY_EVICTION_THRESHOLD</span>
                <span className="code">{draft.quality_eviction_threshold.toFixed(2)}</span>
              </div>
              <input
                type="range"
                min={0}
                max={1}
                step={0.01}
                value={draft.quality_eviction_threshold}
                onChange={(e) =>
                  setDraft((d) => ({ ...d, quality_eviction_threshold: Number(e.target.value) }))
                }
                className="w-full"
              />
            </div>
            {localErr && (
              <div className="text-xs text-rose-300 border border-rose-500/40 rounded-md px-2 py-1">
                {localErr}
              </div>
            )}
            {saveMut.isError && (
              <div className="text-xs text-rose-300 border border-rose-500/40 rounded-md px-2 py-1">
                {saveMut.error?.message || "Save failed"}
              </div>
            )}
            {savedBanner && (
              <div className="text-xs text-emerald-300 border border-emerald-500/40 rounded-md px-2 py-1">
                Thresholds updated.
              </div>
            )}
            <button
              type="button"
              disabled={saveMut.isPending}
              onClick={onSave}
              className="px-4 py-2 rounded-md bg-emerald-600/20 border border-emerald-500/50 text-emerald-100 text-sm hover:bg-emerald-600/30 disabled:opacity-50"
            >
              {saveMut.isPending ? "Saving…" : "Save thresholds"}
            </button>
          </>
        )}
      </div>

      <div className="glass rounded-xl p-4 text-sm text-slate-400">
        Gemini model IDs and other secrets remain in the backend <span className="code">.env</span>{" "}
        file.
      </div>
    </div>
  );
}
