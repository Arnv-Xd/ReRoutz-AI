import React from "react";

const fieldClass =
  "w-full rounded-xl bg-slate-50 border border-slate-200 px-3 py-2 text-xs text-slate-900 outline-none transition focus:border-amber-500 focus:bg-white";

const labelClass = "block text-[10px] font-mono font-bold uppercase tracking-wider text-slate-500 mb-1";

export default function PlanEventForm({ open, onToggle, form, onChange, onSubmit, mapPoint, submitting }) {
  return (
    <section className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm transition">
      <button
        type="button"
        onClick={onToggle}
        className="w-full flex items-center justify-between p-4 text-left hover:bg-slate-50 transition"
      >
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-amber-500"></span>
          <span className="text-xs font-extrabold uppercase tracking-wider text-slate-900">Planned Event Profiler</span>
        </div>
        <span className="text-xs font-mono text-slate-400">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <form className="p-4 pt-0 space-y-3 border-t border-slate-100" onSubmit={onSubmit}>
          {mapPoint && (
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-2.5 flex items-center gap-2 text-xs text-amber-800 font-mono">
              <span className="h-2 w-2 rounded-full bg-amber-600 animate-pulse"></span>
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
                <option value="festival">Festival / Cultural</option>
                <option value="match">Stadium Match</option>
                <option value="rally">Public Rally</option>
                <option value="marathon">Marathon</option>
                <option value="planned">Other Planned</option>
              </select>
            </div>
            <div>
              <label className={labelClass}>Duration (Hrs)</label>
              <input type="number" step="0.5" className={fieldClass} name="expected_duration_hours" value={form.expected_duration_hours} onChange={onChange} placeholder="4" required />
            </div>
          </div>

          <div>
            <label className={labelClass}>Scheduled Date & Time</label>
            <input type="datetime-local" className={fieldClass} name="planned_date_time" value={form.planned_date_time} onChange={onChange} required />
          </div>

          <div className="grid grid-cols-3 gap-2">
            <div>
              <label className={labelClass}>Corridor</label>
              <input className={fieldClass} name="corridor" value={form.corridor} onChange={onChange} placeholder="MG Road" />
            </div>
            <div>
              <label className={labelClass}>Junction</label>
              <input className={fieldClass} name="junction" value={form.junction} onChange={onChange} placeholder="Brigade Rd" />
            </div>
            <div>
              <label className={labelClass}>Zone</label>
              <input className={fieldClass} name="zone" value={form.zone} onChange={onChange} placeholder="Central" />
            </div>
          </div>

          <div>
            <label className={labelClass}>Event Description</label>
            <textarea
              className={`${fieldClass} resize-none`}
              rows={2}
              name="description"
              value={form.description}
              onChange={onChange}
              placeholder="Anticipated footfall, VIP movements..."
              required
            />
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full py-2.5 rounded-xl bg-amber-600 hover:bg-amber-500 text-white font-bold text-xs transition shadow-sm disabled:opacity-50"
          >
            {submitting ? "Evaluating Risk..." : "Analyze Pre-Event Risk Index"}
          </button>
        </form>
      )}
    </section>
  );
}