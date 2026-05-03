import { motion } from "framer-motion";

const STEP_COLORS = {
  idle: "bg-slate-800 border-slate-700 text-slate-500",
  active: "bg-amber-500/20 border-amber-500/60 text-amber-200 animate-pulse",
  done: "bg-emerald-500/20 border-emerald-500/50 text-emerald-200",
  fallback: "bg-rose-500/20 border-rose-500/50 text-rose-200",
};

function Step({ label, state }) {
  return (
    <motion.div
      layout
      className={`px-3 py-2 rounded-lg border text-xs font-semibold tracking-wide ${STEP_COLORS[state] || STEP_COLORS.idle}`}
    >
      {label}
    </motion.div>
  );
}

function Arrow() {
  return <div className="text-slate-600">→</div>;
}

export default function QueryFlowVisualizer({ flow }) {
  const showValidate = flow.validate !== "hidden";
  return (
    <div className="glass rounded-xl px-4 py-3">
      <div className="text-[11px] uppercase tracking-widest text-slate-500 mb-2">
        Query Flow
      </div>
      <div className="flex items-center gap-2 flex-wrap">
        <Step label="Embed Query" state={flow.embed} />
        <Arrow />
        <Step label="Search Cache" state={flow.search} />
        <Arrow />
        <Step label="Agent Decision" state={flow.agent} />
        {showValidate && (
          <>
            <Arrow />
            <Step label="False Hit Check" state={flow.validate} />
          </>
        )}
        <Arrow />
        <Step label="Result" state={flow.result} />
      </div>
    </div>
  );
}
