import React from "react";

export default function RadiusSlider({ value, onChange }) {
  return (
    <section className="bg-white border border-slate-200 rounded-2xl p-4 shadow-sm space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-900">Cluster Radius</h2>
          <p className="text-[11px] text-slate-500">Search circle size</p>
        </div>
        <span className="font-mono text-xs font-bold px-2.5 py-1 rounded-lg bg-emerald-50 text-emerald-800 border border-emerald-200">
          {(Number(value) || 1.5).toFixed(1)} km
        </span>
      </div>

      <div className="flex items-center gap-3">
        <span className="text-[10px] font-mono text-slate-400 font-bold">0.5 km</span>
        <input
          type="range"
          min="0.5"
          max="5.0"
          step="0.1"
          value={Number(value) || 1.5}
          onChange={(e) => onChange(parseFloat(e.target.value))}
          className="flex-1 cursor-pointer"
        />
        <span className="text-[10px] font-mono text-slate-400 font-bold">5.0 km</span>
      </div>
    </section>
  );
}