import { useCallback, useEffect, useRef, useState } from "react";
import { getAuditLogs, getAuditStats } from "../api/client.js";

const EVENT_META = {
  diversion_query: {
    label: "Detour Route",
    color: "#059669",
    bg: "#ecfdf5",
    border: "#a7f3d0",
    description: "Alternative route searches",
  },
  route_query: {
    label: "Custom Route",
    color: "#475569",
    bg: "#f1f5f9",
    border: "#cbd5e1",
    description: "Point A to Point B searches",
  },
  deployment_prediction: {
    label: "Staff Prediction",
    color: "#d97706",
    bg: "#fffbeb",
    border: "#fde68a",
    description: "Police and barricade estimates",
  },
  plan_event_risk: {
    label: "Event Risk Check",
    color: "#e11d48",
    bg: "#fff1f2",
    border: "#fecdd3",
    description: "Pre-event traffic risk checks",
  },
};

const EVENT_TYPES = Object.keys(EVENT_META);

function formatTime(isoStr) {
  if (!isoStr) return "—";
  const d = new Date(isoStr);
  return d.toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  });
}

function msLabel(ms) {
  if (!ms && ms !== 0) return "—";
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`;
  return `${ms}ms`;
}

function Badge({ color, bg, border, children }) {
  return (
    <span
      className="px-2 py-0.5 rounded-md text-[10px] font-bold"
      style={{ color, backgroundColor: bg, border: `1px solid ${border}` }}
    >
      {children}
    </span>
  );
}

function RiskBar({ value }) {
  const pct = Math.min(100, Math.max(0, value));
  const color = pct >= 75 ? "#e11d48" : pct >= 50 ? "#d97706" : "#059669";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 rounded-full bg-slate-100 overflow-hidden">
        <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
      <span className="text-xs font-mono font-bold" style={{ color }}>{pct.toFixed(1)}</span>
    </div>
  );
}

function Field({ label, value, accent, mono }) {
  return (
    <div>
      <div className="text-[10px] uppercase text-slate-400 font-semibold mb-0.5">{label}</div>
      <div className={`text-xs font-semibold ${mono ? "font-mono" : ""}`} style={{ color: accent || "#0f172a" }}>
        {value ?? "—"}
      </div>
    </div>
  );
}

function PayloadDetail({ row }) {
  const meta = EVENT_META[row.event_type] || EVENT_META.diversion_query;
  const payload = typeof row.payload === "string" ? JSON.parse(row.payload) : row.payload;

  return (
    <div className="p-4 bg-slate-50 border-t border-slate-200 space-y-3">
      <div className="text-[10px] uppercase text-slate-500 font-bold">
        Log Details · Recorded: {formatTime(row.created_at)}
      </div>

      {row.event_type === "diversion_query" && (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          <Field label="Location" value={`${payload.target_lat?.toFixed(4)}, ${payload.target_lon?.toFixed(4)}`} />
          <Field label="Nearby Incidents" value={payload.cluster_size} />
          <Field label="Detours Found" value={payload.total_diversions_found} accent="#059669" />
          <Field label="Blocked Roads" value={payload.gridlock_count} accent={payload.gridlock_count > 0 ? "#e11d48" : undefined} />
          <Field label="Speed" value={msLabel(payload.response_time_ms)} />
          <Field label="Log ID" value={payload.audit_id} mono />
        </div>
      )}

      {row.event_type === "route_query" && (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          <Field label="Start (Point A)" value={`${payload.start_lat?.toFixed(4)}, ${payload.start_lon?.toFixed(4)}`} />
          <Field label="End (Point B)" value={`${payload.end_lat?.toFixed(4)}, ${payload.end_lon?.toFixed(4)}`} />
          <Field label="Status" value={payload.route_status} accent={payload.route_status === "success" ? "#059669" : "#e11d48"} />
          <Field label="Incidents Avoided" value={payload.blocking_incidents_count} />
          <Field label="Speed" value={msLabel(payload.response_time_ms)} />
        </div>
      )}

      {row.event_type === "deployment_prediction" && (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          <Field label="Incident ID" value={payload.incident_id} mono />
          <Field label="Police Recommended" value={payload.recommended_personnel} accent="#059669" />
          <Field label="Barricades Recommended" value={payload.recommended_barricades} accent="#d97706" />
          <Field label="Priority Level" value={payload.deployment_tier} accent={payload.deployment_tier === "Critical" ? "#e11d48" : "#d97706"} />
          <Field label="Road Type" value={payload.is_major_corridor ? "Main Road" : "Side Road"} />
          <Field label="Speed" value={msLabel(payload.response_time_ms)} />
        </div>
      )}

      {row.event_type === "plan_event_risk" && (
        <div className="space-y-2">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <Field label="Event Type" value={payload.event_type} />
            <Field label="Preparation Lead Time" value={`${payload.deployment_lead_time_hours || 0} Hours`} accent="#059669" />
            <Field label="Police Needed" value={payload.recommended_personnel} />
            <Field label="Barricades Needed" value={payload.recommended_barricades} />
          </div>
          <div className="pt-2">
            <span className="text-[10px] text-slate-400 uppercase font-semibold">Traffic Risk Score</span>
            <RiskBar value={payload.pre_event_risk_index} />
          </div>
        </div>
      )}
    </div>
  );
}

function LogRow({ row, expanded, onToggle }) {
  const meta = EVENT_META[row.event_type] || { label: row.event_type, color: "#64748b", bg: "#f1f5f9", border: "#e2e8f0" };
  const payload = typeof row.payload === "string" ? JSON.parse(row.payload) : row.payload;

  return (
    <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm transition">
      <button
        onClick={onToggle}
        className="w-full px-4 py-3 text-left flex items-center justify-between gap-4 hover:bg-slate-50 transition"
      >
        <div className="flex items-center gap-3">
          <Badge color={meta.color} bg={meta.bg} border={meta.border}>{meta.label}</Badge>
          <span className="text-xs text-slate-400">{formatTime(row.created_at)}</span>
        </div>

        <div className="flex items-center gap-3">
          {payload?.response_time_ms != null && (
            <span className="text-[10px] font-mono font-bold text-slate-600 bg-slate-100 px-2 py-0.5 rounded border border-slate-200">
              {msLabel(payload.response_time_ms)}
            </span>
          )}
          <span className="text-slate-400 text-xs font-mono">{expanded ? "▲" : "▼"}</span>
        </div>
      </button>

      {expanded && <PayloadDetail row={row} />}
    </div>
  );
}

export default function AuditDashboard() {
  const [stats, setStats] = useState(null);
  const [logs, setLogs] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState(null);
  const [page, setPage] = useState(0);
  const [expandedId, setExpandedId] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const refreshRef = useRef(null);
  const PAGE_SIZE = 20;

  const fetchStats = useCallback(async () => {
    try {
      const s = await getAuditStats();
      setStats(s);
    } catch (e) {
      console.error(e);
    }
  }, []);

  const fetchLogs = useCallback(async (f, p) => {
    setLoading(true);
    try {
      const res = await getAuditLogs({ eventType: f, limit: PAGE_SIZE, offset: p * PAGE_SIZE });
      setLogs(res.data || []);
      setTotal(res.total || 0);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchStats(); }, [fetchStats]);
  useEffect(() => { fetchLogs(filter, page); }, [filter, page, fetchLogs]);

  useEffect(() => {
    if (autoRefresh) {
      refreshRef.current = setInterval(() => {
        fetchStats();
        fetchLogs(filter, page);
      }, 10000);
    }
    return () => clearInterval(refreshRef.current);
  }, [autoRefresh, filter, page, fetchStats, fetchLogs]);

  const pages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="h-full flex flex-col space-y-4 max-w-7xl mx-auto overflow-hidden">
      {/* Header */}
      <div className="bg-white border border-slate-200 rounded-2xl p-5 flex items-center justify-between shadow-sm shrink-0">
        <div>
          <h2 className="text-lg font-bold text-slate-900 tracking-tight">System Activity Log</h2>
          <p className="text-xs text-slate-500 mt-0.5">Records every route calculation and resource prediction</p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`px-3 py-1.5 rounded-xl text-xs font-semibold border transition ${
              autoRefresh ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"
            }`}
          >
            {autoRefresh ? "Auto-refreshing" : "Paused"}
          </button>
          <button
            onClick={() => { fetchStats(); fetchLogs(filter, page); }}
            className="px-3 py-1.5 rounded-xl text-xs font-semibold bg-emerald-600 text-white hover:bg-emerald-500 transition shadow-sm"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 shrink-0">
        {EVENT_TYPES.map((et) => {
          const meta = EVENT_META[et];
          const count = stats?.counts?.[et] ?? 0;
          const avg = stats?.avg_response_ms?.[et];
          const isActive = filter === et;

          return (
            <button
              key={et}
              onClick={() => { setFilter(isActive ? null : et); setPage(0); setExpandedId(null); }}
              className={`p-3.5 rounded-2xl border text-left transition ${
                isActive
                  ? "bg-white border-emerald-500 ring-2 ring-emerald-500/20 shadow-sm"
                  : "bg-white border-slate-200 hover:border-slate-300 shadow-sm"
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold text-slate-700">{meta.label}</span>
                <span className="text-lg font-mono font-bold" style={{ color: meta.color }}>{count}</span>
              </div>
              <div className="text-[10px] text-slate-400 mt-1">Avg Speed: {msLabel(avg)}</div>
            </button>
          );
        })}
      </div>

      {/* Log Feed */}
      <div className="flex-1 overflow-y-auto custom-scrollbar space-y-2 pr-1">
        {loading ? (
          <div className="p-12 text-center text-xs font-semibold text-slate-400">Loading activity history...</div>
        ) : logs.length === 0 ? (
          <div className="bg-white border border-slate-200 rounded-2xl p-8 text-center text-xs text-slate-500">
            No activity records found for this filter.
          </div>
        ) : (
          logs.map((row) => (
            <LogRow
              key={row.id}
              row={row}
              expanded={expandedId === row.id}
              onToggle={() => setExpandedId(expandedId === row.id ? null : row.id)}
            />
          ))
        )}
      </div>

      {/* Pagination */}
      {pages > 1 && (
        <div className="flex items-center justify-center gap-3 pt-2 shrink-0">
          <button
            disabled={page === 0}
            onClick={() => setPage((p) => p - 1)}
            className="px-3 py-1 rounded-lg text-xs font-semibold bg-white border border-slate-200 disabled:opacity-40"
          >
            Previous
          </button>
          <span className="text-xs text-slate-500">Page {page + 1} of {pages}</span>
          <button
            disabled={page >= pages - 1}
            onClick={() => setPage((p) => p + 1)}
            className="px-3 py-1 rounded-lg text-xs font-semibold bg-white border border-slate-200 disabled:opacity-40"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}