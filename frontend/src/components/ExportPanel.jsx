import { useState } from "react";
import { Download, Loader2 } from "lucide-react";
import { api } from "../api/client.js";

export default function ExportPanel() {
  const [busy, setBusy] = useState(null);
  const [msg, setMsg] = useState(null);

  const run = async (fmt) => {
    setBusy(fmt);
    setMsg(null);
    try {
      const { blob, filename } = await api.exportAnalytics(fmt);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
      setMsg({ ok: true, text: `Downloaded ${filename}` });
    } catch (e) {
      setMsg({ ok: false, text: e.message || "Export failed" });
    } finally {
      setBusy(null);
      setTimeout(() => setMsg(null), 5000);
    }
  };

  return (
    <div className="glass rounded-xl p-4 space-y-3">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div>
          <div className="text-sm font-semibold text-slate-200">Export analytics</div>
          <div className="text-xs text-slate-500">Hit rates, latency, history — JSON or CSV</div>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={() => run("json")}
            className="flex items-center gap-1.5 px-3 py-2 rounded-md bg-slate-800 border border-slate-600 text-sm text-slate-100 hover:bg-slate-700 disabled:opacity-50"
          >
            {busy === "json" ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
            {busy === "json" ? "Exporting…" : "JSON"}
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => run("csv")}
            className="flex items-center gap-1.5 px-3 py-2 rounded-md bg-slate-800 border border-slate-600 text-sm text-slate-100 hover:bg-slate-700 disabled:opacity-50"
          >
            {busy === "csv" ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
            {busy === "csv" ? "Exporting…" : "CSV"}
          </button>
        </div>
      </div>
      {msg && (
        <div
          className={`text-xs rounded-md px-2 py-1 border ${
            msg.ok ? "text-emerald-300 border-emerald-500/40" : "text-rose-300 border-rose-500/40"
          }`}
        >
          {msg.text}
        </div>
      )}
    </div>
  );
}
