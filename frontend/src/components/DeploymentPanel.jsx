import React from "react";

const tierStyle = {
  Low: "bg-emerald-50 text-emerald-700 border-emerald-200",
  Medium: "bg-amber-50 text-amber-700 border-amber-200",
  High: "bg-amber-100 text-amber-800 border-amber-300",
  Critical: "bg-rose-50 text-rose-700 border-rose-200",
};

export default function DeploymentPanel({
  recommendation,
  patrolRouteResult,
  isGeneratingPatrol,
  onGeneratePatrolRoute,
  onClear,
  onClearPatrolRoute,
}) {
  if (!recommendation) return null;

  const single = recommendation.single_point || recommendation;
  const cluster = recommendation.cluster_area;
  const tierClass = tierStyle[single.deployment_tier] || tierStyle.Low;

  return (
    <article className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm p-4 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-100 pb-3">
        <div>
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-900">Required Resources</h3>
          <p className="text-[11px] text-slate-500">
            Affected Area: <span className="font-bold text-slate-800">{Number(single.affected_radius_km || 0).toFixed(1)} km</span>
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold border ${tierClass}`}>
            {single.deployment_tier} Priority
          </span>
          {onClear && (
            <button onClick={onClear} className="text-slate-400 hover:text-slate-700 text-xs px-1" title="Clear">
              ✕
            </button>
          )}
        </div>
      </div>

      {/* Single Incident Counts */}
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-emerald-50/60 border border-emerald-200/80 rounded-xl p-3 text-center">
          <div className="text-2xl font-mono font-black text-emerald-700">{single.recommended_personnel}</div>
          <div className="text-[10px] uppercase font-bold text-emerald-800 mt-0.5">Police Officers</div>
        </div>
        <div className="bg-amber-50/60 border border-amber-200/80 rounded-xl p-3 text-center">
          <div className="text-2xl font-mono font-black text-amber-700">{single.recommended_barricades}</div>
          <div className="text-[10px] uppercase font-bold text-amber-800 mt-0.5">Barricades</div>
        </div>
      </div>

      {/* Area Totals */}
      {cluster && (
        <div className="bg-slate-50 border border-slate-200 rounded-xl p-3 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-[10px] uppercase font-bold text-slate-600">Total for Area ({cluster.incident_count} Incidents)</span>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-200">
              {cluster.tier_max}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-2 text-center">
            <div className="bg-white border border-slate-200 rounded-lg p-2">
              <span className="text-lg font-mono font-bold text-emerald-600">{cluster.personnel_total}</span>
              <div className="text-[9px] text-slate-500 uppercase">Total Police</div>
            </div>
            <div className="bg-white border border-slate-200 rounded-lg p-2">
              <span className="text-lg font-mono font-bold text-amber-600">{cluster.barricades_total}</span>
              <div className="text-[9px] text-slate-500 uppercase">Total Barricades</div>
            </div>
          </div>

          {/* Patrol Route Button */}
          {cluster.incident_count > 1 ? (
            <button
              onClick={onGeneratePatrolRoute}
              disabled={isGeneratingPatrol}
              className="w-full py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition flex items-center justify-center gap-2 shadow-sm disabled:opacity-50"
            >
              {isGeneratingPatrol ? "Finding Shortest Route..." : "Plan Officer Patrol Route"}
            </button>
          ) : (
            <div className="text-[10px] text-slate-400 text-center">Only 1 incident — no patrol route needed</div>
          )}

          {patrolRouteResult?.status === "success" && (
            <div className="bg-white border border-emerald-200 rounded-lg p-2.5 space-y-1 text-xs">
              <div className="flex justify-between">
                <span className="text-slate-500">Patrol Distance:</span>
                <span className="font-bold text-slate-800 font-mono">{(patrolRouteResult.total_distance_m / 1000).toFixed(1)} km</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Estimated Drive Time:</span>
                <span className="font-bold text-emerald-600 font-mono">{Math.ceil(patrolRouteResult.total_travel_time_s / 60)} Mins</span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* AI Reasons */}
      {Array.isArray(single.explanation) && single.explanation.length > 0 && (
        <div className="border-t border-slate-100 pt-3 space-y-1.5">
          <span className="text-[10px] uppercase text-slate-400 font-bold">Why this was recommended:</span>
          <ul className="space-y-1">
            {single.explanation.map((item, idx) => (
              <li key={idx} className="text-[11px] text-slate-600 bg-slate-50 rounded-md px-2.5 py-1.5 border border-slate-100">
                {item}
              </li>
            ))}
          </ul>
        </div>
      )}
    </article>
  );
}