import React from "react";

const fieldClass =
  "w-full rounded-xl bg-slate-50 border border-slate-200 px-3.5 py-2.5 text-xs text-slate-800 outline-none transition-all focus:bg-white focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500";

const labelClass = "block space-y-1.5 text-[11px] font-bold uppercase tracking-wider text-slate-500";

export default function PlanEventForm({ open, onToggle, form, onChange, onSubmit, mapPoint, submitting }) {
  return (
    <section className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center justify-between p-4 text-left transition-colors hover:bg-slate-50"
      >
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-amber-500"></span>
          <span className="text-xs font-bold text-slate-900 uppercase tracking-wider">Planned Event Profiler</span>
        </div>
        <span className={`text-slate-400 transition-transform duration-200 ${open ? "rotate-180" : ""}`}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="6 9 12 15 18 9"/>
          </svg>
        </span>
      </button>

      {open && (
        <form className="space-y-3.5 px-4 pb-4 border-t border-slate-100 pt-3" onSubmit={onSubmit}>
          {mapPoint && (
            <div className="flex items-center gap-2 rounded-xl bg-amber-50 border border-amber-200 p-2.5">
              <span className="h-1.5 w-1.5 rounded-full bg-amber-500 animate-ping"></span>
              <span className="text-[11px] font-mono font-bold text-amber-900">
                Selected: {mapPoint.lat.toFixed(5)}, {mapPoint.lon.toFixed(5)}
              </span>
            </div>
          )}

          <div className="grid grid-cols-2 gap-2.5">
            <label className={labelClass}>
              Latitude
              <input className={fieldClass} name="lat" value={form.lat} onChange={onChange} placeholder="12.9716" required />
            </label>
            <label className={labelClass}>
              Longitude
              <input className={fieldClass} name="lon" value={form.lon} onChange={onChange} placeholder="77.5946" required />
            </label>
          </div>

          <div className="grid grid-cols-2 gap-2.5">
            <label className={labelClass}>
              Event Type
              <select className={fieldClass} name="event_type" value={form.event_type} onChange={onChange}>
                <option value="festival">Festival</option>
                <option value="rally">Rally / Procession</option>
                <option value="match">Sports Match</option>
                <option value="marathon">Marathon</option>
                <option value="planned">General Gathering</option>
              </select>
            </label>
            <label className={labelClass}>
              Duration (Hours)
              <input type="number" step="0.5" className={fieldClass} name="expected_duration_hours" value={form.expected_duration_hours} onChange={onChange} required />
            </label>
          </div>

          <label className={labelClass}>
            Planned Date & Time
            <input type="datetime-local" className={fieldClass} name="planned_date_time" value={form.planned_date_time} onChange={onChange} />
          </label>

          <div className="grid grid-cols-3 gap-2">
            <label className={labelClass}>
              Corridor
              <input className={fieldClass} name="corridor" value={form.corridor} onChange={onChange} placeholder="MG Road" />
            </label>
            <label className={labelClass}>
              Junction
              <input className={fieldClass} name="junction" value={form.junction} onChange={onChange} placeholder="Trinity Circle" />
            </label>
            <label className={labelClass}>
              Zone
              <input className={fieldClass} name="zone" value={form.zone} onChange={onChange} placeholder="Central" />
            </label>
          </div>

          <label className={labelClass}>
            Event Description
            <textarea
              className={`${fieldClass} min-h-[60px] resize-none`}
              name="description"
              value={form.description}
              onChange={onChange}
              placeholder="e.g. Major cultural procession expected to draw 15,000+ attendees."
              required
            />
          </label>

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-xl bg-amber-600 hover:bg-amber-700 active:scale-[0.99] text-white py-2.5 text-xs font-bold shadow-sm transition-all disabled:opacity-50"
          >
            {submitting ? "Evaluating Risk Index..." : "Assess Risk & Lead Time"}
          </button>
        </form>
      )}
    </section>
  );
}