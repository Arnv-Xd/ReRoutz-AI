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

const COLORS = ["#059669", "#2563eb", "#d97706", "#7c3aed", "#0891b2", "#dc2626"];

const HeatmapGrid = ({ data }) => {
  if (!data || data.length === 0) return <div className="text-xs text-slate-500 py-4">No temporal data available</div>;

  const days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
  const hours = Array.from({ length: 24 }, (_, i) => i);
  const maxCount = Math.max(...data.map((d) => d.count), 1);

  const getValue = (day, hour) => {
    const entry = data.find((d) => d.day_of_week === day && d.hour === hour);
    return entry ? entry.count : 0;
  };

  return (
    <div className="w-full overflow-x-auto custom-scrollbar pb-2">
      <div className="min-w-[650px]">
        <div className="flex text-[10px] text-slate-400 font-mono mb-1.5 ml-14">
          {hours.map((h) => (
            <div key={h} className="flex-1 text-center">{h}h</div>
          ))}
        </div>
        {days.map((day) => (
          <div key={day} className="flex items-center mb-1.5">
            <div className="w-14 text-[11px] font-semibold text-slate-600 truncate pr-2 text-right">
              {day.substring(0, 3)}
            </div>
            <div className="flex flex-1 gap-1">
              {hours.map((hour) => {
                const count = getValue(day, hour);
                const intensity = count / maxCount;
                return (
                  <div
                    key={hour}
                    className="flex-1 h-5 rounded-sm transition-all hover:scale-110 cursor-pointer"
                    style={{
                      backgroundColor: count > 0 ? "#059669" : "#f1f5f9",
                      opacity: count > 0 ? Math.max(0.25, intensity) : 1,
                    }}
                    title={`${day} ${hour}:00 — ${count} incident(s)`}
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

export default function AnalyticsPanel() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let isMounted = true;
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await getAnalyticsSummary();
        if (isMounted) setData(res);
      } catch (err) {
        if (isMounted) setError(err.message);
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    fetchData();
    return () => {
      isMounted = false;
    };
  }, []);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center p-8 text-slate-500">
        <div className="flex items-center gap-3">
          <span className="h-4 w-4 rounded-full border-2 border-emerald-600 border-t-transparent animate-spin"></span>
          <span className="text-sm font-medium">Aggregating corridor analytics...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full items-center justify-center p-8 text-rose-600">
        <p className="text-sm font-semibold">Error loading analytics: {error}</p>
      </div>
    );
  }

  if (!data || data.incident_count_in_window === 0) {
    return (
      <div className="flex h-full items-center justify-center p-8 text-slate-500 text-center">
        <div>
          <h2 className="text-base font-bold text-slate-800 mb-1">No Incidents Found</h2>
          <p className="text-xs">No telemetry records available in the dataset.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto custom-scrollbar p-6 space-y-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between pb-4 border-b border-slate-200">
        <div>
          <h2 className="text-xl font-black text-slate-900 tracking-tight">Traffic Operations & Deployment Analytics</h2>
          <p className="text-xs text-slate-500 mt-0.5">Telemetry aggregated across all historical records and active live incidents</p>
        </div>
        <div className="bg-emerald-50 border border-emerald-200 px-4 py-2 rounded-xl text-emerald-800 text-xs font-bold font-mono">
          Total Incidents: {data.incident_count_in_window}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Incident Volume over Time */}
        <section className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm">
          <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider mb-4">Incident Volume over Time</h3>
          <div className="h-[240px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.incident_volume_timeseries} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#64748b" }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 10, fill: "#64748b" }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ borderRadius: "12px", border: "1px solid #e2e8f0", fontSize: "12px" }} />
                <Bar dataKey="count" name="Incidents" fill="#2563eb" radius={[4, 4, 0, 0]} maxBarSize={36} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>

        {/* Personnel & Barricades Trend */}
        <section className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm">
          <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider mb-4">Personnel & Barricade Sizing Trend</h3>
          <div className="h-[240px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data.avg_personnel_barricades_trend} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#64748b" }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 10, fill: "#64748b" }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ borderRadius: "12px", border: "1px solid #e2e8f0", fontSize: "12px" }} />
                <Legend wrapperStyle={{ fontSize: "11px", paddingTop: "8px" }} />
                <Line type="monotone" dataKey="recommended_personnel" name="Personnel" stroke="#7c3aed" strokeWidth={2.5} dot={{ r: 3 }} />
                <Line type="monotone" dataKey="recommended_barricades" name="Barricades" stroke="#d97706" strokeWidth={2.5} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>

        {/* Severity Tier Distribution */}
        <section className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm">
          <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider mb-4">Severity Tier Distribution</h3>
          <div className="h-[240px] w-full flex items-center justify-center">
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
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ borderRadius: "12px", border: "1px solid #e2e8f0", fontSize: "12px" }} />
                <Legend wrapperStyle={{ fontSize: "11px" }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </section>

        {/* Incident Type Breakdown */}
        <section className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm">
          <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider mb-4">Incident Cause Distribution</h3>
          <div className="h-[240px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.incident_type_breakdown} layout="vertical" margin={{ top: 0, right: 20, left: 30, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f1f5f9" />
                <XAxis type="number" tick={{ fontSize: 10, fill: "#64748b" }} axisLine={false} tickLine={false} />
                <YAxis dataKey="event_cause" type="category" tick={{ fontSize: 10, fill: "#64748b" }} axisLine={false} tickLine={false} width={100} />
                <Tooltip contentStyle={{ borderRadius: "12px", border: "1px solid #e2e8f0", fontSize: "12px" }} />
                <Bar dataKey="count" name="Incidents" fill="#059669" radius={[0, 4, 4, 0]} maxBarSize={20} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>

        {/* Top Hotspot Corridors */}
        <section className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm lg:col-span-2">
          <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider mb-4">Top Congestion Hotspots (Corridors)</h3>
          <div className="h-[260px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.top_hotspot_corridors} layout="vertical" margin={{ top: 0, right: 20, left: 60, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f1f5f9" />
                <XAxis type="number" tick={{ fontSize: 10, fill: "#64748b" }} axisLine={false} tickLine={false} />
                <YAxis dataKey="corridor" type="category" tick={{ fontSize: 10, fill: "#64748b" }} axisLine={false} tickLine={false} width={150} />
                <Tooltip contentStyle={{ borderRadius: "12px", border: "1px solid #e2e8f0", fontSize: "12px" }} />
                <Bar dataKey="count" name="Incidents" fill="#dc2626" radius={[0, 4, 4, 0]} maxBarSize={22} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>

        {/* Temporal Pattern Heatmap */}
        <section className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm lg:col-span-2">
          <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider mb-4">Temporal Congestion Pattern (Day vs Hour)</h3>
          <HeatmapGrid data={data.temporal_pattern_heatmap} />
        </section>
      </div>
    </div>
  );
}