import { THRESHOLD_PRESETS } from "../constants/thresholdPresets.js";

/** Live controls for similarity lower/upper bounds (gray zone vs auto cache hit). */
export default function GrayZoneSliders({
  grayLow,
  hitThreshold,
  onGrayLowChange,
  onHitThresholdChange,
  activePresetId,
  onSelectPreset,
  onManualAdjust,
}) {
  return (
    <div className="glass rounded-xl px-4 py-3 text-xs space-y-3 border border-slate-800/80">
      <div className="font-semibold text-slate-300 text-sm tracking-tight">
        Similarity thresholds
      </div>

      <div className="flex flex-wrap gap-2">
        {THRESHOLD_PRESETS.map((p) => {
          const on = activePresetId === p.id;
          return (
            <button
              key={p.id}
              type="button"
              onClick={() => onSelectPreset(p)}
              className={`px-2.5 py-1.5 rounded-lg text-[11px] font-medium border transition ${
                on
                  ? "bg-emerald-500/20 border-emerald-500/50 text-emerald-200"
                  : "bg-slate-800/50 border-slate-700 text-slate-400 hover:border-slate-600 hover:text-slate-300"
              }`}
              title={p.hint}
            >
              {p.label}
            </button>
          );
        })}
      </div>
      {activePresetId && (
        <p className="text-[11px] text-slate-500 italic leading-snug">
          {THRESHOLD_PRESETS.find((x) => x.id === activePresetId)?.hint}
        </p>
      )}

      <p className="text-slate-500 leading-snug">
        Below the lower bound the router calls the LLM. Between the two: validate. At or
        above the upper bound: cache hit (unless quality is very low).
      </p>
      <label className="flex flex-col gap-1.5">
        <span className="text-slate-400 flex justify-between">
          Lower bound (gray zone floor)
          <span className="code text-emerald-300/90">{(grayLow * 100).toFixed(0)}%</span>
        </span>
        <input
          type="range"
          min={0}
          max={0.99}
          step={0.01}
          value={grayLow}
          onChange={(e) => {
            onManualAdjust?.();
            const v = Number(e.target.value);
            const maxGray = hitThreshold - 0.02;
            onGrayLowChange(Math.min(v, maxGray));
          }}
          className="w-full accent-emerald-500"
        />
      </label>
      <label className="flex flex-col gap-1.5">
        <span className="text-slate-400 flex justify-between">
          Upper bound (auto cache hit)
          <span className="code text-cyan-300/90">{(hitThreshold * 100).toFixed(0)}%</span>
        </span>
        <input
          type="range"
          min={0.55}
          max={1}
          step={0.01}
          value={hitThreshold}
          onChange={(e) => {
            onManualAdjust?.();
            const v = Number(e.target.value);
            onHitThresholdChange(v);
            if (grayLow >= v - 0.02) {
              onGrayLowChange(Math.max(0, v - 0.02));
            }
          }}
          className="w-full accent-cyan-500"
        />
      </label>
    </div>
  );
}
