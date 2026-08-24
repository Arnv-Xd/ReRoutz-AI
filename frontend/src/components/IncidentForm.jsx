import React from "react";

const fieldClass =
  "w-full rounded-xl bg-slate-50 border border-slate-200 px-3 py-2 text-xs text-slate-900 outline-none transition focus:border-emerald-500 focus:bg-white";

const labelClass = "block text-[10px] font-mono font-bold uppercase tracking-wider text-slate-500 mb-1";

export default function IncidentForm({ open, onToggle, form, onChange, onSubmit, mapPoint, submitting }) {
  return (
    <section className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm transition">
      <button
        type="button"
        onClick={onToggle}
        className="w-full flex items-center justify-between p-4 text-left hover:bg-slate-50 transition"
      >
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-emerald-500"></span>
          <span className="text-xs font-extrabold uppercase tracking-wider text-slate-900">Manual Incident Entry</span>
        </div>
        <span className="text-xs font-mono text-slate-400">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <form className="p-4 pt-0 space-y-3 border-t border-slate-100" onSubmit={onSubmit}>
          {mapPoint && (
            <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-2.5 flex items-center gap-2 text-xs text-emerald-800 font-mono">
              <span className="h-2 w-2 rounded-full bg-emerald-600 animate-pulse"></span>
              <span>PIN: {mapPoint.lat.toFixed(4)}, {mapPoint.lon.toFixed(4)}</span>
            </div>
          )}

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className={labelClass}>Latitude</label>
              <input className={fieldClass} name="lat" value={form.lat} onChange={onChange} placeholder="12.9716" required />
            </div>
            <div>
              <label className={labelClass}>Longitude</label>
              <input className={fieldClass} name="lon" value={form.lon} onChange={onChange} placeholder="77.5946" required />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className={labelClass}>Event Type</label>
              <select className={fieldClass} name="event_type" value={form.event_type} onChange={onChange}>
                <option value="unplanned">Unplanned Collision</option>
                <option value="planned">Planned Staging</option>
              </select>
            </div>
            <div>
              <label className={labelClass}>Priority</label>
              <select className={fieldClass} name="priority" value={form.priority} onChange={onChange}>
                <option value="unknown">Unknown</option>
                <option value="high">High</option>
                <option value="low">Low</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className={labelClass}>Cause</label>
              <input className={fieldClass} name="event_cause" value={form.event_cause} onChange={onChange} placeholder="Collision" />
            </div>
            <div>
              <label className={labelClass}>Vehicle</label>
              <input className={fieldClass} name="veh_type" value={form.veh_type} onChange={onChange} placeholder="Heavy Commercial" />
            </div>
          </div>

          <label className="flex items-center gap-2.5 bg-slate-50 border border-slate-200 p-2.5 rounded-xl cursor-pointer text-xs text-slate-700">
            <input
              type="checkbox"
              name="requires_road_closure"
              checked={form.requires_road_closure}
              onChange={onChange}
              className="rounded"
            />
            <span className="font-semibold">Requires Road Closure</span>
          </label>

          <div className="grid grid-cols-3 gap-2">
            <div>
              <label className={labelClass}>Corridor</label>
              <input className={fieldClass} name="corridor" value={form.corridor} onChange={onChange} placeholder="MG Road" />
            </div>
            <div>
              <label className={labelClass}>Junction</label>
              <input className={fieldClass} name="junction" value={form.junction} onChange={onChange} placeholder="Trinity" />
            </div>
            <div>
              <label className={labelClass}>Zone</label>
              <input className={fieldClass} name="zone" value={form.zone} onChange={onChange} placeholder="East" />
            </div>
          </div>

          <div>
            <label className={labelClass}>Description & Notes</label>
            <textarea
              className={`${fieldClass} resize-none`}
              rows={2}
              name="description"
              value={form.description}
              onChange={onChange}
              placeholder="Incident context..."
            />
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs transition shadow-sm disabled:opacity-50"
          >
            {submitting ? "Computing Bypass..." : "Submit Incident & Trigger ML"}
          </button>
        </form>
      )}
    </section>
  );
}