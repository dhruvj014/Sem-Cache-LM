import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Download, Eraser, HelpCircle, Send, Sparkles, Trash2 } from "lucide-react";
import { api } from "../api/client.js";
import { useSessionStore } from "../store/sessionStore.js";
import { useCommandRegistry } from "../store/commandRegistry.js";
import ResponseCard from "../components/ResponseCard.jsx";
import QueryFlowVisualizer from "../components/QueryFlowVisualizer.jsx";
import SystemMonitorPanel from "../components/SystemMonitorPanel.jsx";
import LatencyComparisonBar from "../components/LatencyComparisonBar.jsx";
import DemoSequenceButton from "../components/DemoSequenceButton.jsx";
import GrayZoneSliders from "../components/GrayZoneSliders.jsx";
import DemoTour, { isDemoTourCompleted } from "../components/DemoTour.jsx";
import SavingsTicker from "../components/SavingsTicker.jsx";
import LastDecisionPanel from "../components/LastDecisionPanel.jsx";
import { buildSessionMarkdown, downloadMarkdown } from "../utils/exportSession.js";
import { THRESHOLD_PRESETS } from "../constants/thresholdPresets.js";

export default function Chat() {
  const {
    sessionId,
    messages,
    addMessage,
    clearChat,
    collapseLastAssistant,
    flowState,
    setFlow,
    resetFlow,
  } = useSessionStore();
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [hitThreshold, setHitThreshold] = useState(0.92);
  const [grayLow, setGrayLow] = useState(0.7);
  const [thresholdsReady, setThresholdsReady] = useState(false);
  const [activePresetId, setActivePresetId] = useState(null);
  const [tourOpen, setTourOpen] = useState(false);
  const scrollRef = useRef(null);
  const inputRef = useRef(null);
  const register = useCommandRegistry((s) => s.register);
  const unregister = useCommandRegistry((s) => s.unregister);

  const lastAssistantMessage = useMemo(
    () => [...messages].reverse().find((m) => m.role === "assistant"),
    [messages]
  );

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    try {
      if (!isDemoTourCompleted()) setTourOpen(true);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    api
      .getDecisionThresholds()
      .then((d) => {
        if (cancelled) return;
        setHitThreshold(d.similarity_hit_threshold);
        setGrayLow(d.similarity_gray_zone_low);
        const match = THRESHOLD_PRESETS.find(
          (p) =>
            Math.abs(p.similarity_hit_threshold - d.similarity_hit_threshold) < 0.006 &&
            Math.abs(p.similarity_gray_zone_low - d.similarity_gray_zone_low) < 0.006
        );
        setActivePresetId(match?.id ?? null);
        setThresholdsReady(true);
      })
      .catch(() => {
        if (!cancelled) setThresholdsReady(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!thresholdsReady) return;
    const t = setTimeout(() => {
      api.updateDecisionThresholds(hitThreshold, grayLow).catch(() => {});
    }, 450);
    return () => clearTimeout(t);
  }, [hitThreshold, grayLow, thresholdsReady]);

  const handleClearChatOnly = useCallback(() => {
    setError(null);
    clearChat();
  }, [clearChat]);

  const handleClearChatAndCache = useCallback(async () => {
    if (!window.confirm("Clear chat and wipe server cache and analytics?")) return;
    setError(null);
    try {
      await api.clearAllCache();
      clearChat();
    } catch (e) {
      setError(e.message);
    }
  }, [clearChat]);

  const exportSession = useCallback(() => {
    const { sessionId: sid, messages: msgs } = useSessionStore.getState();
    if (!msgs.length) return;
    downloadMarkdown(
      `semcachelm-session-${sid}.md`,
      buildSessionMarkdown(sid, msgs)
    );
  }, []);

  useEffect(() => {
    register("openTour", () => setTourOpen(true));
    register("exportSession", exportSession);
    register("focusChatInput", () => inputRef.current?.focus());
    register("clearChat", handleClearChatOnly);
    register("clearChatAndCache", () => {
      void handleClearChatAndCache();
    });
    return () => {
      unregister("openTour");
      unregister("exportSession");
      unregister("focusChatInput");
      unregister("clearChat");
      unregister("clearChatAndCache");
    };
  }, [
    register,
    unregister,
    exportSession,
    handleClearChatOnly,
    handleClearChatAndCache,
  ]);

  const applyPreset = (p) => {
    setActivePresetId(p.id);
    setHitThreshold(p.similarity_hit_threshold);
    setGrayLow(p.similarity_gray_zone_low);
  };

  const sendQuery = async (q) => {
    if (!q?.trim() || busy) return;
    setError(null);
    setBusy(true);

    collapseLastAssistant();

    addMessage({ id: Date.now(), role: "user", content: q });

    setFlow({ embed: "active", search: "idle", agent: "idle", validate: "hidden", result: "idle" });
    setTimeout(() => setFlow({ embed: "done", search: "active", agent: "idle", validate: "hidden", result: "idle" }), 200);
    setTimeout(() => setFlow({ embed: "done", search: "done", agent: "active", validate: "hidden", result: "idle" }), 450);

    const snapHit = hitThreshold;
    const snapGray = grayLow;

    try {
      const payload = await api.query(q, sessionId, {
        similarity_hit_threshold: snapHit,
        similarity_gray_zone_low: snapGray,
      });
      const validateUsed = payload.agent_action === "VALIDATE" || payload.source === "false_hit_fallback";
      const fallback = payload.source === "false_hit_fallback";
      setFlow({
        embed: "done",
        search: "done",
        agent: "done",
        validate: validateUsed ? (fallback ? "fallback" : "done") : "hidden",
        result: fallback ? "fallback" : "done",
      });
      addMessage({
        id: Date.now() + 1,
        role: "assistant",
        content: payload.response,
        payload,
        requestMeta: { hitThreshold: snapHit, grayLow: snapGray },
      });
    } catch (e) {
      setError(e.message);
      setFlow({ ...flowState, result: "fallback" });
    } finally {
      setBusy(false);
      setTimeout(resetFlow, 2500);
    }
  };

  const regenerateLastResponse = async () => {
    const lastUserMessage = [...messages]
      .reverse()
      .find((m) => m.role === "user");
  
    if (!lastUserMessage) return;
  
    await sendQuery(lastUserMessage.content);
  };

  const onSubmit = async (e) => {
    e.preventDefault();
    const q = input;
    setInput("");
    await sendQuery(q);
  };

  return (
    <div className="h-full flex gap-4 px-6 py-4 overflow-hidden">
      <DemoTour open={tourOpen} onClose={() => setTourOpen(false)} />

      <div className="flex-1 flex flex-col gap-3 min-w-0">
        <div className="grid md:grid-cols-2 gap-3">
          <LatencyComparisonBar />
          <SavingsTicker />
        </div>

        <div className="flex flex-col sm:flex-row gap-3 items-stretch">
          <div className="flex-1 min-w-0" data-tour="thresholds">
            <GrayZoneSliders
              grayLow={grayLow}
              hitThreshold={hitThreshold}
              onGrayLowChange={setGrayLow}
              onHitThresholdChange={setHitThreshold}
              activePresetId={activePresetId}
              onSelectPreset={applyPreset}
              onManualAdjust={() => setActivePresetId(null)}
            />
          </div>
          <div className="flex flex-col gap-2 sm:w-48 shrink-0">
            <button
              type="button"
              onClick={() => setTourOpen(true)}
              className="flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-violet-500/15 border border-violet-500/45 text-violet-200 text-sm hover:bg-violet-500/25"
            >
              <HelpCircle size={16} /> Demo tour
            </button>
            <button
              type="button"
              onClick={exportSession}
              disabled={!messages.length}
              className="flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-slate-800 border border-slate-600 text-slate-200 text-sm hover:bg-slate-700/80 disabled:opacity-40"
            >
              <Download size={16} /> Export session
            </button>
            <div className="flex items-center gap-1.5 px-1 text-[10px] text-slate-500">
              <Sparkles size={12} className="text-slate-600 shrink-0" />
              Markdown download · includes routing metadata
            </div>
            <button
              type="button"
              onClick={handleClearChatOnly}
              disabled={busy}
              className="flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-slate-200 text-sm hover:bg-slate-700/80 disabled:opacity-50"
            >
              <Eraser size={16} /> Clear chat
            </button>
            <button
              type="button"
              onClick={handleClearChatAndCache}
              disabled={busy}
              className="flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-rose-500/15 border border-rose-500/50 text-rose-200 text-sm hover:bg-rose-500/25 disabled:opacity-50"
            >
              <Trash2 size={16} /> Clear chat &amp; cache
            </button>
          </div>
        </div>

        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto space-y-4 pr-2"
          data-tour="messages"
        >
          {messages.length === 0 && (
            <div className="glass rounded-xl p-6 text-center text-slate-400">
              <div className="text-lg font-semibold mb-1">SemCacheLM Chat</div>
              <div className="text-sm">
                Ask any question. Watch the cache, agent, and false-hit detector decide
                what to do — every step is shown live.
              </div>
            </div>
          )}
          {messages.map((m) => (
            <ResponseCard key={m.id} message={m} onRegenerate={regenerateLastResponse} busy={busy} />
          ))}
        </div>

        <LastDecisionPanel lastAssistantMessage={lastAssistantMessage} />

        <QueryFlowVisualizer flow={flowState} />

        {error && (
          <div className="px-3 py-2 rounded-lg bg-rose-500/15 border border-rose-500/40 text-rose-300 text-sm">
            {error}
          </div>
        )}

        <form onSubmit={onSubmit} className="flex items-center gap-2 flex-wrap" data-tour="chat-input">
          <input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask anything…"
            disabled={busy}
            className="flex-1 min-w-[12rem] px-4 py-2.5 rounded-lg bg-slate-900 border border-slate-800 focus:border-emerald-500 focus:outline-none text-sm disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={busy || !input.trim()}
            className="px-4 py-2.5 rounded-lg bg-emerald-500 text-slate-950 font-semibold flex items-center gap-2 disabled:opacity-50"
          >
            <Send size={14} /> Send
          </button>
          <div data-tour="demo-row">
            <DemoSequenceButton onSendQuery={sendQuery} disabled={busy} />
          </div>
        </form>
      </div>

      <SystemMonitorPanel />
    </div>
  );
}
