import { useLayoutEffect, useRef, useState } from "react";
import { Sparkles, X } from "lucide-react";

const STORAGE_KEY = "semcachelm_demo_tour_v1";

const STEPS = [
  {
    title: "Similarity thresholds",
    body: "Adjust the lower and upper bounds. Below the floor the router calls the LLM; in the middle it validates; at or above the top it can reuse cache directly.",
    selector: '[data-tour="thresholds"]',
  },
  {
    title: "Ask a question",
    body: "Type anything in the input and press Send. The first answer usually comes from the LLM and is stored in the semantic cache.",
    selector: '[data-tour="chat-input"]',
  },
  {
    title: "Hit the cache",
    body: "Ask the exact same question again—or use Run Demo Sequence for a scripted path. Watch latency drop and the source badge switch to cache.",
    selector: '[data-tour="demo-row"]',
  },
  {
    title: "Read the traces",
    body: "Each assistant reply shows a source badge (cache vs LLM) and an expandable decision card with similarity, latency, and validator details.",
    selector: '[data-tour="messages"]',
  },
];

export function isDemoTourCompleted() {
  try {
    return localStorage.getItem(STORAGE_KEY) === "done";
  } catch {
    return true;
  }
}

export function markDemoTourCompleted() {
  try {
    localStorage.setItem(STORAGE_KEY, "done");
  } catch {
    /* ignore */
  }
}

export default function DemoTour({ open, onClose }) {
  const [step, setStep] = useState(0);
  const [rect, setRect] = useState(null);
  const prevOpen = useRef(false);

  useLayoutEffect(() => {
    if (open && !prevOpen.current) setStep(0);
    prevOpen.current = open;
  }, [open]);

  useLayoutEffect(() => {
    if (!open) return;
    const sel = STEPS[step]?.selector;
    if (!sel) {
      setRect(null);
      return;
    }
    const update = () => {
      const el = document.querySelector(sel);
      setRect(el ? el.getBoundingClientRect() : null);
    };
    update();
    window.addEventListener("scroll", update, true);
    window.addEventListener("resize", update);
    const t = window.setInterval(update, 400);
    return () => {
      window.removeEventListener("scroll", update, true);
      window.removeEventListener("resize", update);
      window.clearInterval(t);
    };
  }, [step, open]);

  if (!open) return null;

  const isLast = step >= STEPS.length - 1;
  const pad = 8;

  const spotlight =
    rect && rect.width > 0 && rect.height > 0 ? (
      <div
        className="pointer-events-none fixed z-[240] rounded-xl border-2 border-emerald-400/90 shadow-[0_0_0_9999px_rgba(0,0,0,0.62)] transition-all duration-200"
        style={{
          left: rect.left - pad,
          top: rect.top - pad,
          width: rect.width + pad * 2,
          height: rect.height + pad * 2,
        }}
      />
    ) : (
      <div className="fixed inset-0 z-[230] bg-black/65" />
    );

  let popStyle = {
    left: "50%",
    top: "50%",
    transform: "translate(-50%, -50%)",
  };
  if (rect && rect.width > 0) {
    const top = Math.min(window.innerHeight - 220, rect.bottom + 16);
    const left = Math.min(window.innerWidth - 340, Math.max(16, rect.left + rect.width / 2));
    popStyle = {
      left,
      top,
      transform: "translateX(-50%)",
    };
  }

  return (
    <div className="fixed inset-0 z-[230]">
      {spotlight}
      <div
        className="fixed z-[250] w-[min(100vw-2rem,22rem)] rounded-2xl border border-emerald-500/30 bg-slate-900/95 shadow-2xl shadow-emerald-900/20 p-4 backdrop-blur-md"
        style={popStyle}
      >
        <div className="flex items-start justify-between gap-2 mb-2">
          <div className="flex items-center gap-2 text-emerald-400">
            <Sparkles size={18} />
            <span className="text-[10px] uppercase tracking-widest text-slate-500">
              Demo tour · {step + 1}/{STEPS.length}
            </span>
          </div>
          <button
            type="button"
            onClick={() => {
              markDemoTourCompleted();
              onClose();
            }}
            className="p-1 rounded-md text-slate-500 hover:bg-slate-800 hover:text-slate-300"
            aria-label="Close tour"
          >
            <X size={18} />
          </button>
        </div>
        <h4 className="text-sm font-semibold text-white mb-1">{STEPS[step].title}</h4>
        <p className="text-xs text-slate-400 leading-relaxed mb-4">{STEPS[step].body}</p>
        <div className="flex justify-between gap-2">
          <button
            type="button"
            className="text-xs text-slate-500 hover:text-slate-300 px-2 py-1.5"
            onClick={() => {
              markDemoTourCompleted();
              onClose();
            }}
          >
            Skip tour
          </button>
          <div className="flex gap-2">
            {step > 0 && (
              <button
                type="button"
                className="text-xs px-3 py-1.5 rounded-lg border border-slate-700 text-slate-300 hover:bg-slate-800"
                onClick={() => setStep((s) => s - 1)}
              >
                Back
              </button>
            )}
            <button
              type="button"
              className="text-xs px-3 py-1.5 rounded-lg bg-emerald-500 text-slate-950 font-semibold hover:bg-emerald-400"
              onClick={() => {
                if (isLast) {
                  markDemoTourCompleted();
                  onClose();
                } else {
                  setStep((s) => s + 1);
                }
              }}
            >
              {isLast ? "Finish" : "Next"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export function resetDemoTourLocal() {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
}
