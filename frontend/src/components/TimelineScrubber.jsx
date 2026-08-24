import React from "react";

export default function TimelineScrubber({ minTime, maxTime, value, disabled, onChange }) {
  const hasRange = Number.isFinite(minTime) && Number.isFinite(maxTime) && minTime < maxTime;
  
  // Safe display formatting
  const display = Number.isFinite(value)
    ? new Date(value).toLocaleString("en-IN", { 
        month: "short", 
        day: "numeric", 
        hour: "2-digit", 
        minute: "2-digit", 
        hour12: true 
      })
    : "Live Timeline";

  const startLabel = hasRange 
    ? new Date(minTime).toLocaleDateString("en-IN", { month: "short", day: "numeric" })
    : "Start";

  const endLabel = hasRange 
    ? new Date(maxTime).toLocaleDateString("en-IN", { month: "short", day: "numeric" })
    : "Now";

  return (
    <section className="bg-white border border-slate-200 rounded-2xl p-4 shadow-sm space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-emerald-500"></span>
            <h2 className="text-xs font-bold text-slate-900 uppercase tracking-wider">Time Filter</h2>
          </div>
          <p className="text-[11px] text-slate-500 mt-0.5">Filter incidents across simulation history</p>
        </div>
        <span className="shrink-0 rounded-lg bg-emerald-50 border border-emerald-200 px-2.5 py-1 font-mono text-[11px] font-bold text-emerald-800">
          {display}
        </span>
      </div>

      <div className="space-y-1.5 pt-1">
        <input
          type="range"
          min={hasRange ? minTime : 0}
          max={hasRange ? maxTime : 100}
          value={Number.isFinite(value) ? value : hasRange ? maxTime : 100}
          disabled={disabled || !hasRange}
          onChange={(event) => onChange(Number(event.target.value))}
          className="w-full h-1.5 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-emerald-600 disabled:opacity-40 disabled:cursor-not-allowed"
        />

        <div className="flex items-center justify-between text-[10px] font-mono font-semibold text-slate-400">
          <span>{startLabel}</span>
          <span className="text-[9px] uppercase tracking-wider text-slate-400">Scrub History</span>
          <span>{endLabel}</span>
        </div>
      </div>
    </section>
  );
}