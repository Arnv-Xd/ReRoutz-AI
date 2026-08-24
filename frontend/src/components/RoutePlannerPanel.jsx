import React from "react";

export default function RoutePlannerPanel({
  routeMode,
  routeStart,
  routeEnd,
  routeStatus,
  calculating,
  onToggle,
  onClear,
}) {
  function toggleLabel() {
    if (calculating) return "Finding Route...";
    if (!routeMode && !routeStart) return "Find New Route";
    if (routeMode && !routeStart) return "Pick Point A on Map";
    if (routeMode && routeStart && !routeEnd) return "Pick Point B on Map";
    return "Find New Route";
  }

  const isActive = routeMode || calculating;

  return (
    <section className="bg-white border border-slate-200 rounded-2xl p-4 shadow-sm space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-900">Point-to-Point Route</h2>
          <p className="text-[11px] text-slate-500">Find a route between two points</p>
        </div>
        <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
          isActive 
            ? "bg-amber-50 text-amber-700 border-amber-200" 
            : "bg-slate-50 text-slate-500 border-slate-200"
        }`}>
          {isActive ? "ACTIVE" : "IDLE"}
        </span>
      </div>

      <div className="flex gap-2">
        <button
          type="button"
          onClick={onToggle}
          disabled={calculating}
          className={`flex-1 py-2.5 px-3 rounded-xl text-xs font-bold transition flex items-center justify-center gap-2 shadow-sm disabled:opacity-50 ${
            isActive
              ? "bg-amber-600 hover:bg-amber-500 text-white"
              : "bg-emerald-600 hover:bg-emerald-500 text-white"
          }`}
        >
          {calculating && (
            <span className="h-3 w-3 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
          )}
          {toggleLabel()}
        </button>

        <button
          type="button"
          onClick={onClear}
          disabled={calculating}
          className="py-2.5 px-3 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold transition border border-slate-200 disabled:opacity-50"
        >
          Reset
        </button>
      </div>

      {routeStatus && (
        <div className="bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-[11px] text-slate-600 leading-snug">
          {routeStatus}
        </div>
      )}
    </section>
  );
}