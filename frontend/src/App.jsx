import { useEffect, useMemo, useState } from "react";
import {
  calculateClusterDiversion,
  calculateRouteDiversion,
  getDataset,
  predictDeploymentCluster,
  findSimilarIncidents,
  planEvent,
  optimizePatrolRoute,
} from "./api/client.js";
import DiversionResultsPanel from "./components/DiversionResultsPanel.jsx";
import IncidentForm from "./components/IncidentForm.jsx";
import PlanEventForm from "./components/PlanEventForm.jsx";
import MapView from "./components/MapView.jsx";
import RadiusSlider from "./components/RadiusSlider.jsx";
import RoutePlannerPanel from "./components/RoutePlannerPanel.jsx";
import TimelineScrubber from "./components/TimelineScrubber.jsx";
import AnalyticsPanel from "./components/AnalyticsPanel.jsx";
import AuditDashboard from "./components/AuditDashboard.jsx";

const defaultForm = {
  lat: "",
  lon: "",
  event_type: "unplanned",
  event_cause: "traffic_jam",
  priority: "medium",
  veh_type: "unknown",
  requires_road_closure: false,
  corridor: "unknown",
  junction: "unknown",
  zone: "unknown",
  description: "",
};

const defaultPlanEventForm = {
  lat: "",
  lon: "",
  event_type: "festival",
  expected_duration_hours: "4",
  planned_date_time: "",
  corridor: "unknown",
  junction: "unknown",
  zone: "unknown",
  description: "",
};

function normalizeDataset(data) {
  let minTime = Infinity;
  let maxTime = -Infinity;

  const incidents = data
    .map((incident, index) => {
      const rawStart =
        incident.start_datetime ||
        incident.start_time ||
        incident.created_at ||
        incident.datetime;

      const parsedStart = rawStart ? new Date(rawStart).getTime() : NaN;
      if (Number.isNaN(parsedStart)) return null;

      // Extract explicit end time or calculate from duration_minutes
      const rawEnd =
        incident.end_datetime ||
        incident.resolved_datetime ||
        incident.closed_datetime;

      let parsedEnd = rawEnd ? new Date(rawEnd).getTime() : NaN;

      if (Number.isNaN(parsedEnd)) {
        const durationMinutes =
          Number(incident.duration_minutes) ||
          Number(incident.expected_duration_minutes) ||
          180; // 3-hour realistic active window
        parsedEnd = parsedStart + durationMinutes * 60 * 1000;
      }

      minTime = Math.min(minTime, parsedStart);
      maxTime = Math.max(maxTime, parsedEnd);

      const lat = Number(incident.latitude ?? incident.lat);
      const lon = Number(incident.longitude ?? incident.lon);
      if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;

      return {
        ...incident,
        latitude: lat,
        longitude: lon,
        parsedStart,
        parsedEnd,
        stableKey: `${String(incident.id || incident.event_id || "inc")}-${index}`,
      };
    })
    .filter(Boolean);

  return {
    incidents,
    minTime: Number.isFinite(minTime) ? minTime : Date.now() - 86400000 * 30,
    maxTime: Number.isFinite(maxTime) ? maxTime : Date.now(),
  };
}

function getDistance(lat1, lon1, lat2, lon2) {
  const radius = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  return radius * (2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a)));
}

function getPaddedBoundingBox(a, b, paddingRatio = 0.3, minPaddingKm = 0.5) {
  const minLat = Math.min(a.lat, b.lat);
  const maxLat = Math.max(a.lat, b.lat);
  const minLon = Math.min(a.lon, b.lon);
  const maxLon = Math.max(a.lon, b.lon);

  const latSpan = maxLat - minLat;
  const lonSpan = maxLon - minLon;

  const avgLat = (minLat + maxLat) / 2;
  const kmPerDegLat = 111.0;
  const kmPerDegLon = 111.0 * Math.cos((avgLat * Math.PI) / 180);

  const latPadding = Math.max(latSpan * paddingRatio, minPaddingKm / kmPerDegLat);
  const lonPadding = Math.max(lonSpan * paddingRatio, minPaddingKm / kmPerDegLon);

  return {
    minLat: minLat - latPadding,
    maxLat: maxLat + latPadding,
    minLon: minLon - lonPadding,
    maxLon: maxLon + lonPadding,
  };
}

function readString(incident, keys, fallback = "unknown") {
  for (const key of keys) {
    const value = incident[key];
    if (value !== undefined && value !== null && String(value).trim() !== "") return String(value).trim();
  }
  return fallback;
}

function readBool(incident, keys) {
  for (const key of keys) {
    const value = incident[key];
    if (typeof value === "boolean") return value;
    if (typeof value === "number") return value > 0;
    if (typeof value === "string" && value.trim() !== "") {
      return ["true", "yes", "1", "y", "closed", "closure"].includes(value.trim().toLowerCase());
    }
  }
  return false;
}

function deploymentPayloadFromIncident(incident) {
  const lat = Number(incident.latitude ?? incident.lat);
  const lon = Number(incident.longitude ?? incident.lon);
  const eventCause = readString(incident, ["event_cause", "cause", "eventcause"], "unknown");
  const description = readString(incident, ["description", "event_description", "details", "remarks"], eventCause);

  return {
    incident_id: String(incident.id || incident.stableKey || "unknown"),
    lat,
    lon,
    event_type: readString(incident, ["event_type", "type"], "unplanned").toLowerCase().includes("planned")
      ? "planned"
      : "unplanned",
    event_cause: eventCause,
    priority: readString(incident, ["priority", "event_priority", "severity"], "medium").toLowerCase(),
    veh_type: readString(incident, ["veh_type", "vehicle_type", "vehicle", "involved_vehicle"], "unknown"),
    requires_road_closure: readBool(incident, ["requires_road_closure", "road_closure", "is_road_closed", "road_closed"]),
    corridor: readString(incident, ["corridor", "road_name", "road", "street"], "unknown"),
    junction: readString(incident, ["junction", "junction_name", "intersection"], "unknown"),
    zone: readString(incident, ["zone", "police_zone", "area"], "unknown"),
    description,
    start_datetime: readString(incident, ["start_datetime"], "") || null,
    expected_duration_minutes: 60,
  };
}

function normalizeDiversionResult(result) {
  const diversions = Array.isArray(result?.diversions)
    ? result.diversions.map((diversion) => {
        const coordinates = Array.isArray(diversion.coordinates)
          ? diversion.coordinates
              .map((point) => [Number(point?.[0]), Number(point?.[1])])
              .filter(([lat, lon]) => Number.isFinite(lat) && Number.isFinite(lon))
          : [];

        return {
          ...diversion,
          coordinates,
          status: diversion.status === "success" && coordinates.length >= 2 ? "success" : diversion.status || "gridlock",
        };
      })
    : [];

  return {
    ...result,
    diversions,
    total_diversions: diversions.filter((diversion) => diversion.status === "success").length,
  };
}

export default function App() {
  const [allIncidents, setAllIncidents] = useState([]);
  const [minTime, setMinTime] = useState(NaN);
  const [maxTime, setMaxTime] = useState(NaN);
  const [selectedTime, setSelectedTime] = useState(NaN);
  const [radiusKm, setRadiusKm] = useState(1.5);
  const [status, setStatus] = useState("Loading incident records...");
  const [error, setError] = useState("");
  const [selectedName, setSelectedName] = useState("");
  const [selectedTarget, setSelectedTarget] = useState(null);
  const [clusterCount, setClusterCount] = useState(0);
  const [diversionResult, setDiversionResult] = useState(null);
  const [deploymentResult, setDeploymentResult] = useState(null);
  const [similarEventsResult, setSimilarEventsResult] = useState(null);
  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState(defaultForm);
  const [temporaryIncident, setTemporaryIncident] = useState(null);
  const [submittingForm, setSubmittingForm] = useState(false);
  const [selectedPathIndex, setSelectedPathIndex] = useState(null);

  const [planEventOpen, setPlanEventOpen] = useState(false);
  const [planEventForm, setPlanEventForm] = useState(defaultPlanEventForm);
  const [plannedEventResult, setPlannedEventResult] = useState(null);
  const [plannedEventTarget, setPlannedEventTarget] = useState(null);
  const [submittingPlanEvent, setSubmittingPlanEvent] = useState(false);

  const [routeMode, setRouteMode] = useState(false);
  const [routeStart, setRouteStart] = useState(null);
  const [routeEnd, setRouteEnd] = useState(null);
  const [routeResult, setRouteResult] = useState(null);
  const [routeCalculating, setRouteCalculating] = useState(false);
  const [routeStatus, setRouteStatus] = useState("Click 'Find New Route', then pick Point A and Point B on the map.");

  const [patrolRouteResult, setPatrolRouteResult] = useState(null);
  const [isGeneratingPatrol, setIsGeneratingPatrol] = useState(false);

  const [currentView, setCurrentView] = useState("map");

  useEffect(() => {
    getDataset()
      .then((result) => {
        if (result.status !== "success") throw new Error(result.message || "Could not load dataset.");
        const normalized = normalizeDataset(result.data);
        setAllIncidents(normalized.incidents);
        setMinTime(normalized.minTime);
        setMaxTime(normalized.maxTime);
        // Default timeline position to max time
        setSelectedTime(normalized.maxTime);
        setStatus(`Loaded ${normalized.incidents.length} total incident records.`);
      })
      .catch((err) => {
        setError(`Backend is offline or dataset missing: ${err.message}`);
        setStatus("");
      });
  }, []);

  // Filter for ACTIVE incidents only (started before/at slider time and not yet resolved)
  const activeIncidents = useMemo(() => {
    if (!allIncidents.length) return [];
    if (!Number.isFinite(selectedTime)) return allIncidents;
    return allIncidents.filter(
      (incident) => selectedTime >= incident.parsedStart && selectedTime <= incident.parsedEnd
    );
  }, [allIncidents, selectedTime]);

  function localClusterFor(lat, lon) {
    const targetLat = Number(lat);
    const targetLon = Number(lon);
    if (!Number.isFinite(targetLat) || !Number.isFinite(targetLon)) return [];

    return activeIncidents.filter((incident) => {
      const incLat = Number(incident.latitude ?? incident.lat);
      const incLon = Number(incident.longitude ?? incident.lon);
      if (!Number.isFinite(incLat) || !Number.isFinite(incLon)) return false;
      return getDistance(targetLat, targetLon, incLat, incLon) <= radiusKm;
    });
  }

  function getBlockingIncidents(a, b) {
    const bbox = getPaddedBoundingBox(a, b);
    return activeIncidents.filter((inc) => {
      const lat = Number(inc.latitude);
      const lon = Number(inc.longitude);
      if (!Number.isFinite(lat) || !Number.isFinite(lon)) return false;
      return lat >= bbox.minLat && lat <= bbox.maxLat && lon >= bbox.minLon && lon <= bbox.maxLon;
    });
  }

  async function runDiversion(incident, clusterOverride) {
    const lat = Number(incident.latitude ?? incident.lat);
    const lon = Number(incident.longitude ?? incident.lon);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) throw new Error("Incident location is invalid.");

    const cluster = clusterOverride ?? localClusterFor(lat, lon);
    const clusterPayload = cluster.map((item) => ({
      lat: Number(item.latitude ?? item.lat),
      lon: Number(item.longitude ?? item.lon),
    }));

    setSelectedTarget({ lat, lon });
    setClusterCount(clusterPayload.length);
    setSelectedPathIndex(null);
    setStatus(`Calculating diversion routes for ${incident.id || "selected point"}...`);

    const response = await calculateClusterDiversion({
      target: { lat, lon },
      active_cluster: clusterPayload,
    });
    const result = normalizeDiversionResult(response);
    setDiversionResult(result);
    setStatus("");
    return result;
  }

  async function runDeployment(incident) {
    setStatus(`Predicting police and barricade requirements for ${incident.id || "selected point"}...`);
    const lat = Number(incident.latitude ?? incident.lat);
    const lon = Number(incident.longitude ?? incident.lon);

    const clusterIncidents = localClusterFor(lat, lon);
    const targetPayload = deploymentPayloadFromIncident(incident);
    const clusterPayloads = clusterIncidents.map(deploymentPayloadFromIncident);

    const result = await predictDeploymentCluster({
      target: targetPayload,
      active_cluster: clusterPayloads.length > 0 ? clusterPayloads : [targetPayload],
      radius_km: radiusKm,
    });

    setDeploymentResult(result);
    setSelectedTarget({ lat, lon });
    setStatus("");
    return result;
  }

  async function handleCalculateDiversion(incident) {
    setError("");
    setSelectedName(incident.id || "New Incident");
    setDeploymentResult(null);
    clearRoute();
    try {
      await runDiversion(incident);
    } catch (err) {
      setError(`Error: ${err.message}`);
      setStatus("");
    }
  }

  async function handleRecommendDeployment(incident) {
    setError("");
    setSelectedName(incident.id || "New Incident");
    try {
      await runDeployment(incident);
    } catch (err) {
      setError(`Could not compute deployment: ${err.message}`);
      setStatus("");
    }
  }

  async function handleFindSimilarEvents(incident) {
    setError("");
    setSelectedName(incident.id || "New Incident");
    setStatus(`Searching historical matches for ${incident.id || "this incident"}...`);
    setSimilarEventsResult(null);
    try {
      const payload = deploymentPayloadFromIncident(incident);
      const result = await findSimilarIncidents({
        description: payload.description,
        event_cause: payload.event_cause,
        event_type: payload.event_type,
        lat: payload.lat,
        lon: payload.lon,
      });
      setSimilarEventsResult(result);
      setStatus("");
    } catch (err) {
      setError(`Could not find similar incidents: ${err.message}`);
      setStatus("");
    }
  }

  function handleMapClick(point) {
    setForm((current) => ({ ...current, lat: point.lat.toFixed(6), lon: point.lon.toFixed(6) }));
    setPlanEventForm((current) => ({ ...current, lat: point.lat.toFixed(6), lon: point.lon.toFixed(6) }));
  }

  function handleFormChange(event) {
    const { name, value, type, checked } = event.target;
    setForm((current) => ({ ...current, [name]: type === "checkbox" ? checked : value }));
  }

  function handlePlanEventFormChange(event) {
    const { name, value } = event.target;
    setPlanEventForm((current) => ({ ...current, [name]: value }));
  }

  async function handleFormSubmit(event) {
    event.preventDefault();
    setError("");
    setSubmittingForm(true);

    const manualIncident = {
      ...form,
      id: "Manual Entry",
      latitude: Number(form.lat),
      longitude: Number(form.lon),
      start_datetime: new Date().toISOString(),
      parsedStart: Date.now() - 60000,
      parsedEnd: Date.now() + 7200000,
    };

    if (!Number.isFinite(manualIncident.latitude) || !Number.isFinite(manualIncident.longitude)) {
      setError("Please enter valid Latitude and Longitude values.");
      setSubmittingForm(false);
      return;
    }

    setTemporaryIncident(manualIncident);
    setSelectedName("Manual Entry");
    try {
      await Promise.all([
        runDiversion(manualIncident, localClusterFor(manualIncident.latitude, manualIncident.longitude)),
        runDeployment(manualIncident),
      ]);
      setForm(defaultForm);
    } catch (err) {
      setError(`Could not add incident: ${err.message}`);
      setStatus("");
    } finally {
      setSubmittingForm(false);
    }
  }

  async function handlePlanEventSubmit(event) {
    event.preventDefault();
    setError("");
    setSubmittingPlanEvent(true);
    setPlannedEventResult(null);
    setPlannedEventTarget(null);

    const lat = Number(planEventForm.lat);
    const lon = Number(planEventForm.lon);

    if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
      setError("Please enter valid Latitude and Longitude.");
      setSubmittingPlanEvent(false);
      return;
    }

    setSelectedName("Planned Event");
    setStatus("Assessing event risk and lead time...");

    try {
      const result = await planEvent({
        ...planEventForm,
        lat,
        lon,
        expected_duration_hours: Number(planEventForm.expected_duration_hours) || 4.0,
      });
      setPlannedEventResult(result);
      setPlannedEventTarget({ lat, lon });
      setPlanEventForm(defaultPlanEventForm);
      setStatus("");
    } catch (err) {
      setError(`Event risk check failed: ${err.message}`);
      setStatus("");
    } finally {
      setSubmittingPlanEvent(false);
    }
  }

  async function handleGeneratePatrolRoute() {
    if (!selectedTarget || !activeIncidents.length) return;
    setIsGeneratingPatrol(true);
    setPatrolRouteResult(null);

    const startLat = Number(selectedTarget.latitude || selectedTarget.lat);
    const startLon = Number(selectedTarget.longitude || selectedTarget.lon);
    const clusterIncidents = localClusterFor(startLat, startLon);

    if (clusterIncidents.length <= 1) {
      setIsGeneratingPatrol(false);
      return;
    }

    const activeCluster = clusterIncidents.map((i) => ({
      incident_id: i.id || i.incident_id || "unknown",
      lat: Number(i.latitude || i.lat),
      lon: Number(i.longitude || i.lon),
    }));

    const startPoint = {
      incident_id: selectedTarget.id || selectedTarget.incident_id || "unknown",
      lat: startLat,
      lon: startLon,
    };

    try {
      const res = await optimizePatrolRoute({ start_point: startPoint, active_cluster: activeCluster });
      if (res.status === "error") {
        setError(`Could not build patrol route: ${res.message}`);
      } else {
        setPatrolRouteResult(res);
      }
    } catch (err) {
      setError(`Patrol route error: ${err.message}`);
    } finally {
      setIsGeneratingPatrol(false);
    }
  }

  function handleClearAll() {
    setDeploymentResult(null);
    setDiversionResult(null);
    setPatrolRouteResult(null);
    setSimilarEventsResult(null);
    setPlannedEventResult(null);
    setRouteResult(null);
    setRouteStart(null);
    setRouteEnd(null);
    setSelectedTarget(null);
    setSelectedName("");
    setTemporaryIncident(null);
    setPlannedEventTarget(null);
    clearRoute();
  }

  function toggleRouteMode() {
    clearRoute();
    setRouteMode(true);
    setRouteStatus("Click Point A (start) on the map.");
  }

  function clearRoute() {
    setRouteMode(false);
    setRouteStart(null);
    setRouteEnd(null);
    setRouteResult(null);
    setRouteCalculating(false);
    setRouteStatus("Click 'Find New Route', then pick Point A and Point B on the map.");
  }

  async function handleRoutePlanClick(latlng) {
    if (!routeMode) return;

    if (!routeStart) {
      setRouteStart({ lat: latlng.lat, lon: latlng.lng });
      setRouteStatus("Point A set. Now click Point B (destination) on the map.");
    } else if (!routeEnd) {
      const end = { lat: latlng.lat, lon: latlng.lng };
      setRouteEnd(end);
      setRouteMode(false);

      setRouteCalculating(true);
      setRouteStatus("Finding clear route avoiding active traffic blockages...");

      const blocking = getBlockingIncidents(routeStart, end);
      const blockingPayload = blocking.map((inc) => ({
        lat: Number(inc.latitude),
        lon: Number(inc.longitude),
      }));

      try {
        const data = await calculateRouteDiversion({
          start: routeStart,
          end,
          blocking_incidents: blockingPayload,
        });
        setRouteResult({ ...data, blockingCount: blockingPayload.length });

        if (data.status === "success") {
          setRouteStatus(`Route found! Avoided ${blockingPayload.length} incident(s).`);
        } else if (data.status === "gridlock") {
          setRouteStatus(`Heavy traffic! No clear route available around ${blockingPayload.length} incidents.`);
        } else {
          setRouteStatus(`Response: ${data.message || "Unknown status."}`);
        }
      } catch (err) {
        setRouteResult({ status: "error", message: err.message });
        setRouteStatus(`Error: ${err.message}`);
      } finally {
        setRouteCalculating(false);
      }
    }
  }

  return (
    <div className="flex h-screen w-screen flex-col bg-[#f8fafc] text-[#0f172a] overflow-hidden antialiased font-sans">
      {/* ─── TOP COMMAND BAR ─── */}
      <header className="h-16 px-6 bg-white border-b border-slate-200 flex items-center justify-between shrink-0 shadow-sm z-20">
        <div className="flex items-center gap-2">
          <h1 className="text-base font-extrabold tracking-tight text-slate-900">
            ReRoutz <span className="text-emerald-600 font-mono">AI</span>
          </h1>
          <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
            Bengaluru City
          </span>
        </div>

        {/* View Switcher */}
        <nav className="flex items-center p-1 rounded-xl bg-slate-100 border border-slate-200">
          {[
            { id: "map", label: "Operations Map" },
            { id: "analytics", label: "Analytics Dashboard" },
            { id: "audit", label: "Audit Registry" },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setCurrentView(tab.id)}
              className={`px-4 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                currentView === tab.id
                  ? "bg-white text-emerald-700 shadow-sm border border-slate-200/80"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        {/* Incident Status Count */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-50 border border-slate-200 text-xs">
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></span>
            <span className="text-slate-500 font-medium">Active Incidents:</span>
            <span className="font-mono font-bold text-slate-900">{activeIncidents.length}</span>
          </div>
          {error && (
            <span className="text-xs font-medium text-rose-600 bg-rose-50 px-3 py-1.5 rounded-xl border border-rose-200 truncate max-w-xs">
              {error}
            </span>
          )}
        </div>
      </header>

      {/* ─── WORKSPACE CONTENT ─── */}
      {currentView === "analytics" ? (
        <main className="flex-1 w-full bg-[#f8fafc] overflow-hidden p-6">
          <AnalyticsPanel startDate={minTime} endDate={selectedTime} />
        </main>
      ) : currentView === "audit" ? (
        <main className="flex-1 w-full bg-[#f8fafc] overflow-hidden p-6">
          <AuditDashboard />
        </main>
      ) : (
        <div className="flex flex-1 min-h-0 w-full overflow-hidden">
          {/* LEFT OPERATOR CONTROLS */}
          <aside className="w-80 bg-white border-r border-slate-200 shrink-0 flex flex-col z-10">
            <div className="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-4">
              <TimelineScrubber
                minTime={minTime}
                maxTime={maxTime}
                value={selectedTime}
                disabled={!allIncidents.length}
                onChange={(value) => {
                  const clamped = Math.max(minTime, Math.min(value, maxTime));
                  setSelectedTime(clamped);
                  handleClearAll();
                }}
              />

              <RadiusSlider value={radiusKm} onChange={setRadiusKm} />

              <RoutePlannerPanel
                routeMode={routeMode}
                routeStart={routeStart}
                routeEnd={routeEnd}
                routeStatus={routeStatus}
                calculating={routeCalculating}
                onToggle={toggleRouteMode}
                onClear={clearRoute}
              />

              <IncidentForm
                open={formOpen}
                onToggle={() => setFormOpen((value) => !value)}
                form={form}
                onChange={handleFormChange}
                onSubmit={handleFormSubmit}
                mapPoint={form.lat && form.lon ? { lat: Number(form.lat), lon: Number(form.lon) } : null}
                submitting={submittingForm}
              />

              <PlanEventForm
                open={planEventOpen}
                onToggle={() => setPlanEventOpen((value) => !value)}
                form={planEventForm}
                onChange={handlePlanEventFormChange}
                onSubmit={handlePlanEventSubmit}
                mapPoint={
                  planEventForm.lat && planEventForm.lon
                    ? { lat: Number(planEventForm.lat), lon: Number(planEventForm.lon) }
                    : null
                }
                submitting={submittingPlanEvent}
              />
            </div>
          </aside>

          {/* CENTER INTERACTIVE LEAFLET MAP */}
          <main className="relative flex-1 min-w-0 h-full bg-slate-100">
            {status && (
              <div className="absolute top-4 left-4 z-[400] bg-white/95 backdrop-blur px-3.5 py-2 rounded-xl border border-slate-200 shadow-sm text-xs text-slate-700 flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-amber-500 animate-ping"></span>
                <span>{status}</span>
              </div>
            )}

            <MapView
              incidents={activeIncidents}
              temporaryIncident={temporaryIncident}
              plannedEventTarget={plannedEventTarget}
              selectedTarget={selectedTarget}
              radiusKm={radiusKm}
              diversionResult={diversionResult}
              formOpen={formOpen}
              onMapClick={handleMapClick}
              onCalculateDiversion={handleCalculateDiversion}
              onRecommendDeployment={handleRecommendDeployment}
              onFindSimilarEvents={handleFindSimilarEvents}
              routeMode={routeMode}
              routeStart={routeStart}
              routeEnd={routeEnd}
              routeResult={routeResult}
              patrolRouteResult={patrolRouteResult}
              onTargetSelect={(incident) => {
                if (!routeMode && !patrolRouteResult) {
                  handleCalculateDiversion(incident);
                  handleRecommendDeployment(incident);
                }
              }}
              onRoutePlanClick={handleRoutePlanClick}
              selectedPathIndex={selectedPathIndex}
            />
          </main>

          {/* RIGHT INTELLIGENCE / RESULTS PANEL */}
          <aside className="w-96 bg-white border-l border-slate-200 shrink-0 flex flex-col z-10">
            <div className="flex-1 overflow-y-auto custom-scrollbar p-4">
              <DiversionResultsPanel
                status={status}
                selectedName={selectedName}
                clusterCount={clusterCount}
                diversionResult={diversionResult}
                deploymentResult={deploymentResult}
                similarEventsResult={similarEventsResult}
                plannedEventResult={plannedEventResult}
                patrolRouteResult={patrolRouteResult}
                isGeneratingPatrol={isGeneratingPatrol}
                onGeneratePatrolRoute={handleGeneratePatrolRoute}
                routeResult={routeResult}
                routeMode={routeMode}
                error={error}
                onClearAll={handleClearAll}
                onClearDeployment={() => setDeploymentResult(null)}
                onClearDiversion={() => setDiversionResult(null)}
                onClearSimilarEvents={() => setSimilarEventsResult(null)}
                onClearPlannedEvent={() => setPlannedEventResult(null)}
                onClearPatrolRoute={() => setPatrolRouteResult(null)}
                onClearPointToPoint={clearRoute}
                selectedPathIndex={selectedPathIndex}
                onSelectPath={setSelectedPathIndex}
              />
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}