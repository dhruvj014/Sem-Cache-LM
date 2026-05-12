import { useState, useRef } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Flame } from "lucide-react";
import { api } from "../api/client.js";

export default function CacheWarmingPanel() {
  const qc = useQueryClient();
  const fileRef = useRef(null);
  const [text, setText] = useState("");
  const [progress, setProgress] = useState(0);

  const warmMut = useMutation({
    mutationFn: (questions) => api.warmCache({ questions }),
    onMutate: () => setProgress(15),
    onSuccess: () => {
      setProgress(100);
      qc.invalidateQueries({ queryKey: ["cache-entries"] });
      setTimeout(() => setProgress(0), 1200);
    },
    onError: () => setProgress(0),
  });

  const lines = text
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);

  const run = () => {
    if (!lines.length) return;
    setProgress(40);
    warmMut.mutate(lines);
  };

  const onFile = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    const t = await f.text();
    setText(t);
  };

  const r = warmMut.data;

  return (
    <div className="glass rounded-lg border border-slate-600/40 p-4 space-y-3">
      <div className="text-sm font-medium text-slate-200">Cache warming</div>
      <p className="text-xs text-slate-500">
        One question per line. Each line is embedded, checked against the semantic cache, and stored
        if no strong hit exists (may call the LLM — can take a while).
      </p>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={6}
        className="w-full bg-slate-900/80 border border-slate-600 rounded-md px-3 py-2 text-sm font-mono"
        placeholder={"What is a distributed system?\nExplain idempotency."}
      />
      <div className="flex flex-wrap gap-2 items-center">
        <input ref={fileRef} type="file" accept=".txt" className="hidden" onChange={onFile} />
        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          className="text-xs px-3 py-1.5 rounded-md border border-slate-600 text-slate-300 hover:bg-slate-800"
        >
          Upload .txt
        </button>
        <button
          type="button"
          disabled={warmMut.isPending || !lines.length}
          onClick={run}
          className="flex items-center gap-2 px-4 py-2 rounded-md bg-orange-500/15 border border-orange-500/40 text-orange-100 text-sm hover:bg-orange-500/25 disabled:opacity-50"
        >
          <Flame size={16} /> {warmMut.isPending ? "Warming…" : "Warm cache"}
        </button>
      </div>
      {(warmMut.isPending || progress > 0) && (
        <div className="space-y-1">
          <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-orange-500/80 transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="text-xs text-slate-500">Processing…</div>
        </div>
      )}
      {warmMut.isError && (
        <div className="text-sm text-rose-300">{warmMut.error?.message || "Warm failed"}</div>
      )}
      {r && (
        <div className="text-sm text-emerald-300 border border-emerald-500/30 rounded-md px-3 py-2">
          Warmed <span className="code">{r.warmed_count}</span>, skipped{" "}
          <span className="code">{r.skipped_count}</span>, failed{" "}
          <span className="code">{r.failed_count}</span>
        </div>
      )}
    </div>
  );
}
