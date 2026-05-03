import {
  Bot,
  GitBranch,
  Scale,
  ShieldCheck,
  Target,
} from "lucide-react";

function similarityBand(sim, grayLow, hitThreshold) {
  if (sim >= hitThreshold) return { label: "High band", sub: "≥ upper bound → auto cache eligible", tone: "text-cyan-300" };
  if (sim >= grayLow) return { label: "Gray band", sub: "Between lower & upper → validate", tone: "text-amber-300" };
  return { label: "Miss / cold band", sub: "< lower bound → LLM (or empty index)", tone: "text-rose-300" };
}

function llmCalled(source, agentAction) {
  if (source === "cache") return { yes: false, detail: "Served from cache text only" };
  if (source === "llm") return { yes: true, detail: "Full LLM generation (cold / miss path)" };
  if (source === "validated_cache")
    return { yes: true, detail: "Validator LLM ran; answer text from cache" };
  if (source === "false_hit_fallback")
    return {
      yes: true,
      detail: "Validator LLM + answer LLM (rejected cached match)",
    };
  return { yes: agentAction === "VALIDATE", detail: "—" };
}

export default function LastDecisionPanel({ lastAssistantMessage }) {
  const p = lastAssistantMessage?.payload;
  const meta = lastAssistantMessage?.requestMeta;

  if (!p || !meta) {
    return (
      <div className="glass rounded-xl p-4 border border-dashed border-slate-700 text-center text-slate-500 text-sm">
        <GitBranch className="mx-auto mb-2 opacity-50" size={28} />
        <div className="font-medium text-slate-400">Last decision</div>
        <p className="text-xs mt-1 max-w-md mx-auto">
          Send a question to see embedding band, routing, and whether the LLM ran.
        </p>
      </div>
    );
  }

  const sim = p.similarity_score ?? 0;
  const { hitThreshold, grayLow } = meta;
  const band = similarityBand(sim, grayLow, hitThreshold);
  const llm = llmCalled(p.source, p.agent_action);
  const validatorLine =
    p.source === "cache"
      ? "Not used (direct cache hit)"
      : p.agent_action === "VALIDATE" && p.source === "validated_cache"
        ? `Approved (confidence ${p.validation_confidence?.toFixed?.(2) ?? "—"})`
        : p.source === "false_hit_fallback"
          ? `Rejected → new answer (judge conf. ${p.validation_confidence?.toFixed?.(2) ?? "—"})`
          : p.source === "llm"
            ? "Not used (below threshold or empty index)"
            : "—";

  return (
    <div className="glass rounded-xl p-4 border border-slate-800/80">
      <div className="flex items-center gap-2 mb-3">
        <Target className="text-emerald-400" size={18} />
        <h3 className="text-sm font-semibold text-slate-200 tracking-tight">
          Last routing decision
        </h3>
        <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-500 ml-auto code">
          last reply
        </span>
      </div>

      <div className="grid md:grid-cols-2 gap-3">
        <div className="rounded-lg bg-slate-900/60 border border-slate-800 p-3 space-y-2">
          <div className="flex items-center gap-2 text-xs text-slate-400 uppercase tracking-wide">
            <Scale size={14} /> Embedding vs thresholds
          </div>
          <div className={`text-base font-semibold ${band.tone}`}>{band.label}</div>
          <p className="text-[11px] text-slate-500 leading-snug">{band.sub}</p>
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] pt-1 border-t border-slate-800/80">
            <span className="text-slate-500">
              Score{" "}
              <span className="code text-slate-300">{(sim * 100).toFixed(1)}%</span>
            </span>
            <span className="text-slate-500">
              Lower <span className="code text-emerald-400/90">{(grayLow * 100).toFixed(0)}%</span>
            </span>
            <span className="text-slate-500">
              Upper <span className="code text-cyan-400/90">{(hitThreshold * 100).toFixed(0)}%</span>
            </span>
          </div>
        </div>

        <div className="rounded-lg bg-slate-900/60 border border-slate-800 p-3 space-y-2">
          <div className="flex items-center gap-2 text-xs text-slate-400 uppercase tracking-wide">
            <Bot size={14} /> Outcome
          </div>
          <div className="grid grid-cols-1 gap-2 text-sm">
            <div className="flex justify-between gap-2">
              <span className="text-slate-500">Source</span>
              <span className="code text-slate-200 text-right">{p.source}</span>
            </div>
            <div className="flex justify-between gap-2">
              <span className="text-slate-500">Agent action</span>
              <span className="code text-slate-200 text-right">{p.agent_action}</span>
            </div>
            <div className="flex justify-between gap-2 items-start">
              <span className="text-slate-500 shrink-0">LLM invoked?</span>
              <span className={`text-right font-medium ${llm.yes ? "text-amber-300" : "text-emerald-300"}`}>
                {llm.yes ? "Yes" : "No"}
              </span>
            </div>
            <p className="text-[11px] text-slate-500">{llm.detail}</p>
            <div className="flex gap-2 items-start pt-1 border-t border-slate-800/80">
              <ShieldCheck size={16} className="text-slate-500 shrink-0 mt-0.5" />
              <div>
                <div className="text-[10px] uppercase text-slate-500">Validator</div>
                <div className="text-xs text-slate-300">{validatorLine}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
