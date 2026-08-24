import React from "react";

export default function TimelineScrubber({ minTime, maxTime, value, disabled, onChange }) {
  const hasRange = Number.isFinite(minTime) && Number.isFinite(maxTime) && maxTime > minTime;

  const display =
    hasRange && Number.isFinite(value)
      ? new Date(value).toLocaleString("en-IN", {
          dateStyle: "medium",
          timeStyle: "short",
        })
      : "Loading timeline...";

  return (
    <section className="bg-white border border-slate-200 rounded-2xl p-4 shadow-sm space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-900">Time Filter</h2>
          <p className="text-[11px] text-slate-500">Filter incidents by time</p>
        </div>
        <span className="text-[11px] font-bold px-2.5 py-1 rounded-lg bg-emerald-50 text-emerald-800 border border-emerald-200 max-w-[170px] truncate">
          {display}
        </span>
      </div>

      <div className="flex items-center gap-3">
        <span className="text-[10px] uppercase font-bold text-slate-400">Start</span>
        <input
          type="range"
          min={hasRange ? minTime : 0}
          max={hasRange ? maxTime : 100}
          step={hasRange ? Math.max(60000, Math.floor((maxTime - minTime) / 200)) : 1}
          value={hasRange && Number.isFinite(value) ? value : hasRange ? maxTime : 100}
          disabled={disabled || !hasRange}
          onChange={(e) => onChange(Number(e.target.value))}
          className="flex-1 cursor-pointer"
        />
        <span className="text-[10px] uppercase font-bold text-slate-400">End</span>
      </div>
    </section>
  );
}