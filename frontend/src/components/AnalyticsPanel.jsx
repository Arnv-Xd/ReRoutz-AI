import React, { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Cell,
} from "recharts";
import { getAnalyticsSummary } from "../api/client.js";

const CHART_PALETTE = ["#059669", "#d97706", "#e11d48", "#475569", "#10b981", "#b45309"];

const HeatmapGrid = ({ data }) => {
  if (!data || data.length === 0) {
    return <div className="text-xs text-slate-500 font-medium py-4 text-center">No traffic history available</div>;
  }

  const days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
  const hours = Array.from({ length: 24 }, (_, i) => i);
  const maxCount = Math.max(...data.map((d) => d.count), 1);

  const getValue = (day, hour) => {
    const entry = data.find((d) => d.day_of_week === day && d.hour === hour);
    return entry ? entry.count : 0;
  };

  return (
    <div className="w-full overflow-x-auto custom-scrollbar pb-2">
      <div className="min-w-[620px]">
        <div className="flex text-[10px] font-mono text-slate-400 mb-1.5 ml-14">
          {hours.map((h) => (
            <div key={h} className="flex-1 text-center font-semibold">{h}h</div>
          ))}
        </div>
        {days.map((day) => (
          <div key={day} className="flex items-center mb-1">
            <div className="w-14 text-[11px] font-semibold text-slate-500 truncate pr-2 text-right">
              {day.substring(0, 3)}
            </div>
            <div className="flex flex-1 gap-1">
              {hours.map((hour) => {
                const count = getValue(day, hour);
                const intensity = count / maxCount;
                return (
                  <div
                    key={hour}
                    className="flex-1 h-5 rounded-sm transition-all hover:ring-2 hover:ring-emerald-500"
                    style={{
                      backgroundColor: count > 0 ? "#059669" : "#e2e8f0",
                      opacity: count > 0 ? Math.max(0.2, intensity) : 0.4,
                    }}
                    title={`${day} at ${hour}:00 — ${count} Incident(s)`}
                  />
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default function AnalyticsPanel({ startDate, endDate }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await getAnalyticsSummary(startDate, endDate);
        setData(res);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    const timer = setTimeout(fetchData, 250);
    return () => clearTimeout(timer);
  }, [startDate, endDate]);

  if (loading && !data) {
    return (
      <div className="flex h-full items-center justify-center p-12 text-slate-500">
        <div className="flex items-center gap-3">
          <span className="h-4 w-4 border-2 border-emerald-600 border-t-transparent rounded-full animate-spin"></span>
          <p className="text-sm font-semibold">Loading traffic trends...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <div className="bg-rose-50 border border-rose-200 rounded-xl p-5 text-center max-w-md">
          <p className="text-xs font-bold uppercase text-rose-600 tracking-wider">Error Loading Trends</p>
          <p className="text-xs text-slate-700 mt-1">{error}</p>
        </div>
      </div>
    );
  }

  if (!data || data.incident_count_in_window === 0) {
    return (
      <div className="flex h-full items-center justify-center p-8 text-center text-slate-500">
        <div className="bg-white border border-slate-200 rounded-2xl p-8 shadow-sm max-w-sm">
          <h2 className="text-base font-bold text-slate-800">No Incidents Found</h2>
          <p className="text-xs text-slate-500 mt-1">No traffic incidents occurred in this time frame.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto custom-scrollbar space-y-6 max-w-7xl mx-auto">
      <div className="bg-white border border-slate-200 rounded-2xl p-5 flex items-center justify-between shadow-sm">
        <div>
          <h2 className="text-lg font-bold text-slate-900 tracking-tight">Traffic Overview & Trends</h2>
          <p className="text-xs text-slate-500 mt-0.5">Traffic patterns and incident statistics across the city</p>
        </div>
        <div className="bg-emerald-50 border border-emerald-200 px-4 py-2 rounded-xl text-emerald-800 text-xs font-mono font-bold">
          Total Incidents: {data.incident_count_in_window}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Incident Volume over Time */}
        <section className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800 mb-4">Daily Incidents Over Time</h3>
          <div className="h-60 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.incident_volume_timeseries} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#64748b" }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 10, fill: "#64748b" }} axisLine={false} tickLine={false} />
                <Tooltip
                  cursor={{ fill: "#f8fafc" }}
                  contentStyle={{ borderRadius: "8px", border: "1px solid #e2e8f0", fontSize: "11px", boxShadow: "0 4px 12px rgba(0,0,0,0.05)" }}
                />
                <Bar dataKey="count" name="Incidents" fill="#059669" radius={[4, 4, 0, 0]} maxBarSize={36} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>

        {/* Resources Trend */}
        <section className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800 mb-4">Required Police & Barricades Trend</h3>
          <div className="h-60 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data.avg_personnel_barricades_trend} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#64748b" }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 10, fill: "#64748b" }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ borderRadius: "8px", border: "1px solid #e2e8f0", fontSize: "11px" }} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: "11px" }} />
                <Line type="monotone" dataKey="recommended_personnel" name="Police" stroke="#059669" strokeWidth={2.5} dot={{ r: 3 }} activeDot={{ r: 5 }} />
                <Line type="monotone" dataKey="recommended_barricades" name="Barricades" stroke="#d97706" strokeWidth={2.5} dot={{ r: 3 }} activeDot={{ r: 5 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>

        {/* Severity */}
        <section className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800 mb-4">Incident Priority Breakdown</h3>
          <div className="h-60 w-full flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={data.severity_tier_distribution}
                  dataKey="count"
                  nameKey="deployment_tier"
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={85}
                  paddingAngle={3}
                >
                  {data.severity_tier_distribution.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={CHART_PALETTE[index % CHART_PALETTE.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ borderRadius: "8px", border: "1px solid #e2e8f0", fontSize: "11px" }} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: "11px" }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </section>

        {/* Causes */}
        <section className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800 mb-4">Top Incident Causes</h3>
          <div className="h-60 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.incident_type_breakdown} layout="vertical" margin={{ top: 0, right: 20, left: 10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f1f5f9" />
                <XAxis type="number" tick={{ fontSize: 10, fill: "#64748b" }} axisLine={false} tickLine={false} />
                <YAxis dataKey="event_cause" type="category" width={90} tick={{ fontSize: 10, fill: "#64748b" }} axisLine={false} tickLine={false} />
                <Tooltip cursor={{ fill: "#f8fafc" }} contentStyle={{ borderRadius: "8px", border: "1px solid #e2e8f0", fontSize: "11px" }} />
                <Bar dataKey="count" name="Incidents" radius={[0, 4, 4, 0]} maxBarSize={20}>
                  {data.incident_type_breakdown.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={CHART_PALETTE[index % CHART_PALETTE.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>

        {/* Hotspot Roads */}
        <section className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm lg:col-span-2">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800 mb-4">Most Congested Roads</h3>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.top_hotspot_corridors} layout="vertical" margin={{ top: 0, right: 20, left: 100, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f1f5f9" />
                <XAxis type="number" tick={{ fontSize: 10, fill: "#64748b" }} axisLine={false} tickLine={false} />
                <YAxis dataKey="corridor" type="category" tick={{ fontSize: 10, fill: "#334155" }} axisLine={false} tickLine={false} width={130} />
                <Tooltip cursor={{ fill: "#f8fafc" }} contentStyle={{ borderRadius: "8px", border: "1px solid #e2e8f0", fontSize: "11px" }} />
                <Bar dataKey="count" name="Incidents" fill="#e11d48" radius={[0, 4, 4, 0]} maxBarSize={18} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>

        {/* Weekly Heatmap */}
        <section className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm lg:col-span-2">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800 mb-4">Weekly Traffic Heatmap (Day vs Hour)</h3>
          <HeatmapGrid data={data.temporal_pattern_heatmap} />
        </section>
      </div>
    </div>
  );
}