import { useState } from "react";
import { Play } from "lucide-react";

const DEMO_QUERIES = [
  "What is a distributed system?",
  "What is a distributed system?",
  "Can you explain what distributed systems are?",
  "Describe the CAP theorem in plain English.",
  "What does the CAP theorem mean?",
];

export default function DemoSequenceButton({ onSendQuery, disabled }) {
  const [running, setRunning] = useState(false);
  const [step, setStep] = useState(0);

  const run = async () => {
    setRunning(true);
    for (let i = 0; i < DEMO_QUERIES.length; i++) {
      setStep(i + 1);
      try {
        await onSendQuery(DEMO_QUERIES[i]);
      } catch (e) {
        console.error("demo failed", e);
        break;
      }
      await new Promise((r) => setTimeout(r, 2000));
    }
    setRunning(false);
    setStep(0);
  };

  return (
    <button
      disabled={disabled || running}
      onClick={run}
      className="flex items-center gap-2 px-3 py-2 rounded-md bg-gradient-to-br from-fuchsia-500/20 to-cyan-500/20 border border-fuchsia-400/40 text-fuchsia-200 text-sm hover:brightness-110 disabled:opacity-50"
    >
      <Play size={14} />
      {running ? `Running… (${step}/${DEMO_QUERIES.length})` : "🎬 Run Demo Sequence"}
    </button>
  );
}
