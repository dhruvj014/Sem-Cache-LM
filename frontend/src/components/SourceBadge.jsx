const STYLES = {
  cache:               { label: "⚡ CACHE HIT",          cls: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40" },
  llm:                 { label: "🤖 LLM RESPONSE",       cls: "bg-blue-500/20 text-blue-300 border-blue-500/40" },
  validated_cache:     { label: "✅ VALIDATED CACHE",    cls: "bg-teal-500/20 text-teal-300 border-teal-500/40" },
  false_hit_fallback:  { label: "🔍 FALSE HIT FALLBACK", cls: "bg-amber-500/20 text-amber-300 border-amber-500/40" },
};

export default function SourceBadge({ source, size = "lg" }) {
  const cfg = STYLES[source] || STYLES.llm;
  const padding = size === "lg" ? "px-3 py-1.5 text-sm" : "px-2 py-0.5 text-xs";
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md border font-semibold tracking-wide ${cfg.cls} ${padding}`}
    >
      {cfg.label}
    </span>
  );
}
