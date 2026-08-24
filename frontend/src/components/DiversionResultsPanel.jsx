import React from "react";
import DeploymentPanel from "./DeploymentPanel.jsx";

const vectorColors = ["#059669", "#d97706", "#e11d48", "#475569", "#10b981", "#b45309"];

export default function DiversionResultsPanel({
  status,
  selectedName,
  clusterCount,
  diversionResult,
  deploymentResult,
  similarEventsResult,
  plannedEventResult,
  routeResult,
  patrolRouteResult,
  isGeneratingPatrol,
  onGeneratePatrolRoute,
  error,
  selectedPathIndex,
  onSelectPath,
  onClearAll,
  onClearDeployment,
  onClearDiversion,
  onClearSimilarEvents,
  onClearPlannedEvent,
  onClearPatrolRoute,
  onClearPointToPoint,
}) {
  const diversions = diversionResult?.diversions || [];

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-100 pb-3">
        <div>
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-900">Incident Details</h2>
          <p className="text-[11px] text-slate-500 truncate max-w-[240px]">
            {selectedName || "Click any incident on the map"}
          </p>
        </div>
        <button
          onClick={onClearAll}
          className="px-2.5 py-1 rounded-lg text-xs font-semibold text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition border border-slate-200"
        >
          Clear All
        </button>
      </div>

      {/* Status */}
      {status && (
        <div className="bg-amber-50/70 border border-amber-200 rounded-xl p-3 flex items-center gap-2.5 text-xs text-amber-800">
          <span className="h-2 w-2 rounded-full bg-amber-500 animate-ping shrink-0"></span>
          <span className="leading-snug">{status}</span>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-rose-50 border border-rose-200 rounded-xl p-3 text-xs text-rose-700">
          <strong className="block font-bold mb-0.5">Notice</strong>
          {error}
        </div>
      )}

      {/* Staff & Barricade Recommendations */}
      <DeploymentPanel
        recommendation={deploymentResult}
        patrolRouteResult={patrolRouteResult}
        isGeneratingPatrol={isGeneratingPatrol}
        onGeneratePatrolRoute={onGeneratePatrolRoute}
        onClear={onClearDeployment}
        onClearPatrolRoute={onClearPatrolRoute}
      />

      {/* Planned Event Result */}
      {plannedEventResult && (
        <section className="bg-white border border-slate-200 rounded-2xl p-4 shadow-sm space-y-3">
          <div className="flex items-center justify-between border-b border-slate-100 pb-2">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-900">Event Risk & Prep</h3>
            {onClearPlannedEvent && (
              <button onClick={onClearPlannedEvent} className="text-slate-400 hover:text-slate-700 text-xs">✕</button>
            )}
          </div>

          <div className="flex items-center justify-between bg-amber-50/60 border border-amber-200 rounded-xl p-3">
            <div>
              <span className="text-[10px] uppercase text-amber-800 font-semibold block">Risk Score</span>
              <strong className="text-2xl font-mono font-black text-amber-700">
                {Math.round(plannedEventResult.pre_event_risk_index)} / 100
              </strong>
            </div>
            <div className="text-right">
              <span className="text-[10px] uppercase text-slate-500 font-semibold block">Set Up Early</span>
              <span className="text-xs font-bold text-emerald-700 font-mono bg-emerald-50 px-2.5 py-1 rounded border border-emerald-200">
                {plannedEventResult.deployment_lead_time_hours} Hours Before
              </span>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2 text-center text-xs">
            <div className="bg-slate-50 border border-slate-200 rounded-lg p-2">
              <div className="text-lg font-mono font-bold text-slate-800">{plannedEventResult.recommended_personnel}</div>
              <div className="text-[9px] text-slate-500 uppercase">Police Needed</div>
            </div>
            <div className="bg-slate-50 border border-slate-200 rounded-lg p-2">
              <div className="text-lg font-mono font-bold text-slate-800">{plannedEventResult.recommended_barricades}</div>
              <div className="text-[9px] text-slate-500 uppercase">Barricades Needed</div>
            </div>
          </div>
        </section>
      )}

      {/* Point-to-Point Route Result */}
      {routeResult && (
        <section className="bg-white border border-slate-200 rounded-2xl p-4 shadow-sm space-y-2.5">
          <div className="flex items-center justify-between border-b border-slate-100 pb-2">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-900">Custom Route</h3>
            {onClearPointToPoint && (
              <button onClick={onClearPointToPoint} className="text-slate-400 hover:text-slate-700 text-xs">✕</button>
            )}
          </div>

          {routeResult.status === "success" ? (
            <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-3 text-xs text-emerald-800">
              <span className="font-bold block">✓ Clear Route Found</span>
              <span className="text-[11px] text-emerald-700">
                Avoided {routeResult.blockingCount ?? 0} traffic incident(s) along the way.
              </span>
            </div>
          ) : (
            <div className="bg-rose-50 border border-rose-200 rounded-xl p-3 text-xs text-rose-700">
              <span className="font-bold block">⚠ Road Blocked</span>
              <span className="text-[11px]">No clear alternative route without heavy traffic.</span>
            </div>
          )}
        </section>
      )}

      {/* Alternative  Routes */}
      {diversionResult && (
        <section className="bg-white border border-slate-200 rounded-2xl p-4 shadow-sm space-y-3">
          <div className="flex items-center justify-between border-b border-slate-100 pb-2">
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-900">Alternative Routes (s)</h3>
              <p className="text-[10px] text-slate-500">
                {clusterCount} Nearby Incidents · {diversionResult.total_diversions} s Found
              </p>
            </div>
            {onClearDiversion && (
              <button onClick={onClearDiversion} className="text-slate-400 hover:text-slate-700 text-xs">✕</button>
            )}
          </div>

          <div className="space-y-2">
            {diversions.map((diversion, index) => {
              const isSuccess = diversion.status === "success";
              const color = isSuccess ? vectorColors[index % vectorColors.length] : "#e11d48";
              const isSelected = selectedPathIndex === index;

              return (
                <div
                  key={`${diversion.from_road}-${index}`}
                  onClick={() => onSelectPath(isSelected ? null : index)}
                  className={`p-3 rounded-xl border text-xs cursor-pointer transition flex items-center justify-between ${
                    isSelected
                      ? "bg-slate-50 border-emerald-500 ring-2 ring-emerald-500/20"
                      : "bg-white border-slate-200 hover:border-slate-300"
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <span className="h-3 w-3 rounded-full shrink-0" style={{ backgroundColor: color }}></span>
                    <div>
                      <strong className="block text-slate-800">{diversion.from_road || "Local Road"}</strong>
                      <span className="text-[10px]" style={{ color: isSuccess ? "#059669" : "#e11d48" }}>
                        {isSuccess ? " Route Open" : "Road Blocked"}
                      </span>
                    </div>
                  </div>
                  {isSelected && (
                    <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded bg-emerald-100 text-emerald-800">
                      Selected
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* Similar Past Incidents */}
      {similarEventsResult?.matches && (
        <section className="bg-white border border-slate-200 rounded-2xl p-4 shadow-sm space-y-3">
          <div className="flex items-center justify-between border-b border-slate-100 pb-2">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-900">Past Similar Incidents</h3>
            {onClearSimilarEvents && (
              <button onClick={onClearSimilarEvents} className="text-slate-400 hover:text-slate-700 text-xs">✕</button>
            )}
          </div>

          <div className="space-y-2">
            {similarEventsResult.matches.map((match, idx) => (
              <div key={idx} className="p-2.5 rounded-xl bg-slate-50 border border-slate-200 text-xs space-y-1">
                <div className="flex justify-between items-start">
                  <span className="font-bold text-slate-800">{match.event_type}</span>
                  <span className="text-emerald-700 font-bold font-mono">{Math.round(match.similarity_score * 100)}% Match</span>
                </div>
                <p className="text-[11px] text-slate-500 line-clamp-2">{match.description}</p>
                <div className="pt-1 text-[10px] text-slate-600 flex gap-3 border-t border-slate-200 font-medium">
                  <span>👮 {match.recommended_personnel} Officers</span>
                  <span>🚧 {match.recommended_barricades} Barricades</span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}