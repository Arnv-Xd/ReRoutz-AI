import { Circle, MapContainer, Marker, Polyline, Popup, TileLayer, useMap, useMapEvents } from "react-leaflet";
import L from "leaflet";
import { Fragment, useEffect, useMemo } from "react";

const vectorColors = ["#059669", "#d97706", "#e11d48", "#475569", "#10b981", "#b45309"];

const hazardIcon = L.divIcon({
  html: `<div style="position:relative;width:14px;height:14px;">
    <div style="position:absolute;inset:0;background:#e11d48;border-radius:50%;border:2px solid #ffffff;box-shadow:0 2px 6px rgba(225,29,72,0.4);"></div>
    <div class="marker-ring-crimson"></div>
  </div>`,
  className: "",
  iconSize: [14, 14],
  iconAnchor: [7, 7],
});

const tempIcon = L.divIcon({
  html: `<div style="position:relative;width:16px;height:16px;">
    <div style="background:#059669;width:16px;height:16px;border-radius:50%;border:2px solid #ffffff;box-shadow:0 2px 8px rgba(5,150,105,0.4);"></div>
    <div class="marker-ring-emerald"></div>
  </div>`,
  className: "",
  iconSize: [16, 16],
  iconAnchor: [8, 8],
});

const plannedEventIcon = L.divIcon({
  html: `<div style="position:relative;width:18px;height:18px;">
    <div style="background:#d97706;width:18px;height:18px;border-radius:50%;border:2px dashed #ffffff;box-shadow:0 2px 8px rgba(217,119,6,0.4);"></div>
  </div>`,
  className: "",
  iconSize: [18, 18],
  iconAnchor: [9, 9],
});

function makePointIcon(label, color) {
  return L.divIcon({
    html: `<div style="background:${color};color:white;width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:12px;border:2px solid white;box-shadow:0 3px 10px rgba(0,0,0,0.15);">${label}</div>`,
    className: "",
    iconSize: [28, 28],
    iconAnchor: [14, 14],
  });
}

function makePatrolStopIcon(number) {
  return L.divIcon({
    html: `<div style="background:#059669;color:white;width:22px;height:22px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:900;font-size:11px;border:2px solid white;box-shadow:0 3px 8px rgba(5,150,105,0.4); z-index: 1000;">${number}</div>`,
    className: "",
    iconSize: [22, 22],
    iconAnchor: [11, 11],
  });
}

const pointAIcon = makePointIcon("A", "#059669");
const pointBIcon = makePointIcon("B", "#d97706");

function MapClickHandler({ enabled, onMapClick }) {
  useMapEvents({
    click(e) {
      if (enabled) {
        onMapClick({ lat: e.latlng.lat, lon: e.latlng.lng });
      }
    },
  });
  return null;
}

function RoutePlanClickHandler({ enabled, onRoutePlanClick }) {
  useMapEvents({
    click(e) {
      if (enabled) {
        onRoutePlanClick(e.latlng);
      }
    },
  });
  return null;
}

function CursorController({ routeMode }) {
  const map = useMap();
  useEffect(() => {
    const container = map.getContainer();
    container.style.cursor = routeMode ? "crosshair" : "";
    return () => {
      container.style.cursor = "";
    };
  }, [map, routeMode]);
  return null;
}

function FitDiversions({ target, diversions, radiusKm }) {
  const map = useMap();

  useEffect(() => {
    if (!target || !Number.isFinite(target.lat) || !Number.isFinite(target.lon)) return;

    const group = L.featureGroup([L.marker([target.lat, target.lon])]);
    diversions
      .filter((d) => d.status === "success" && Array.isArray(d.coordinates))
      .forEach((d) => group.addLayer(L.polyline(d.coordinates)));

    const bounds = group.getBounds();
    const circleBounds = L.latLng(target.lat, target.lon).toBounds(radiusKm * 1000);
    bounds.extend(circleBounds);

    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [50, 50], maxZoom: 15 });
    }
  }, [map, target, diversions, radiusKm]);

  return null;
}

function FitRoute({ routeStart, routeEnd, routeResult }) {
  const map = useMap();

  useEffect(() => {
    if (!routeStart || !routeEnd) return;
    if (routeResult?.status !== "success" || !Array.isArray(routeResult.coordinates)) return;

    const group = L.featureGroup([
      L.marker([routeStart.lat, routeStart.lon]),
      L.marker([routeEnd.lat, routeEnd.lon]),
      L.polyline(routeResult.coordinates),
    ]);

    if (group.getBounds().isValid()) {
      map.fitBounds(group.getBounds(), { padding: [50, 50], maxZoom: 15 });
    }
  }, [map, routeStart, routeEnd, routeResult]);

  return null;
}

function getIncidentTitle(incident) {
  if (incident.corridor && incident.corridor !== "unknown") return incident.corridor;
  if (incident.junction && incident.junction !== "unknown") return incident.junction;
  if (incident.zone && incident.zone !== "unknown") return incident.zone;
  return "Traffic Incident";
}

function IncidentMarker({
  incident,
  temporary,
  lat,
  lon,
  onCalculateDiversion,
  onRecommendDeployment,
  onFindSimilarEvents,
}) {
  const map = useMap();

  function runAfterClosingPopup(action) {
    map.closePopup();
    window.requestAnimationFrame(() => action(incident));
  }

  const title = temporary ? "Manual Incident Entry" : getIncidentTitle(incident);
  const cause = String(incident.event_cause || "Traffic Jam").replaceAll("_", " ");

  return (
    <Marker position={[lat, lon]} icon={temporary ? tempIcon : hazardIcon}>
      <Popup>
        <div className="min-w-[220px] space-y-2.5 p-1">
          <div>
            <h3 className="m-0 text-xs font-bold text-slate-900 capitalize leading-tight">
              {title}
            </h3>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-[10px] font-bold uppercase text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200">
                {cause}
              </span>
              {incident.id && (
                <span className="text-[9px] font-mono text-slate-400">
                  ID: {incident.id}
                </span>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-1.5 pt-1">
            <button
              type="button"
              onClick={() => runAfterClosingPopup(onCalculateDiversion)}
              className="py-1.5 px-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-[10px] transition"
            >
              Find Diversions
            </button>
            <button
              type="button"
              onClick={() => runAfterClosingPopup(onRecommendDeployment)}
              className="py-1.5 px-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-800 font-bold text-[10px] transition border border-slate-200"
            >
              Staff Needed
            </button>
          </div>

          <button
            type="button"
            onClick={() => runAfterClosingPopup(onFindSimilarEvents)}
            className="w-full py-1.5 rounded-lg bg-slate-50 hover:bg-slate-100 text-slate-700 font-semibold text-[10px] transition border border-slate-200"
          >
            Past Similar Incidents
          </button>
        </div>
      </Popup>
    </Marker>
  );
}

export default function MapView({
  incidents,
  temporaryIncident,
  plannedEventTarget,
  selectedTarget,
  radiusKm,
  diversionResult,
  formOpen,
  onMapClick,
  onCalculateDiversion,
  onRecommendDeployment,
  onFindSimilarEvents,
  routeMode,
  routeStart,
  routeEnd,
  routeResult,
  patrolRouteResult,
  onRoutePlanClick,
  selectedPathIndex,
}) {
  const successfulDiversions =
    diversionResult?.diversions?.filter(
      (d) => d.status === "success" && Array.isArray(d.coordinates) && d.coordinates.length >= 2,
    ) || [];

  const markers = useMemo(() => {
    const rows = incidents.map((incident) => ({ incident, temporary: false }));
    if (temporaryIncident) rows.push({ incident: temporaryIncident, temporary: true });
    return rows;
  }, [incidents, temporaryIncident]);

  return (
    <MapContainer center={[12.9716, 77.5946]} zoom={12} className="h-full w-full">
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      <MapClickHandler enabled={formOpen} onMapClick={onMapClick} />
      <RoutePlanClickHandler enabled={routeMode} onRoutePlanClick={onRoutePlanClick} />
      <CursorController routeMode={routeMode} />

      {markers.map(({ incident, temporary }) => {
        const lat = Number(incident.latitude ?? incident.lat);
        const lon = Number(incident.longitude ?? incident.lon);
        if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;

        return (
          <IncidentMarker
            key={`${temporary ? "temp" : "incident"}-${incident.stableKey || incident.id || `${lat}-${lon}`}`}
            incident={incident}
            temporary={temporary}
            lat={lat}
            lon={lon}
            onCalculateDiversion={onCalculateDiversion}
            onRecommendDeployment={onRecommendDeployment}
            onFindSimilarEvents={onFindSimilarEvents}
          />
        );
      })}

      {plannedEventTarget && (
        <Marker position={[plannedEventTarget.lat, plannedEventTarget.lon]} icon={plannedEventIcon} />
      )}

      {selectedTarget && (
        <Circle
          center={[selectedTarget.lat, selectedTarget.lon]}
          radius={radiusKm * 1000}
          pathOptions={{ color: "#d97706", fillColor: "#d97706", fillOpacity: 0.08, dashArray: "5 5", weight: 1.5 }}
        />
      )}

      {(() => {
        const anySelected = selectedPathIndex !== null && selectedPathIndex < successfulDiversions.length;
        const order = successfulDiversions.map((_, i) => i).filter((i) => i !== selectedPathIndex);
        if (anySelected) order.push(selectedPathIndex);

        return order.map((index) => {
          const diversion = successfulDiversions[index];
          const isSelected = index === selectedPathIndex;
          const lineOpacity = anySelected ? (isSelected ? 1 : 0.2) : 0.85;

          return (
            <Fragment key={`${diversion.from_road}-${index}`}>
              <Polyline
                positions={diversion.coordinates}
                pathOptions={{
                  color: "#ffffff",
                  weight: isSelected ? 10 : 8,
                  opacity: 0.9,
                }}
              />
              <Polyline
                positions={diversion.coordinates}
                pathOptions={{
                  color: vectorColors[index % vectorColors.length],
                  weight: isSelected ? 6 : 4,
                  opacity: lineOpacity,
                  lineCap: "round",
                  lineJoin: "round",
                }}
              />
            </Fragment>
          );
        });
      })()}

      <FitDiversions target={selectedTarget} diversions={successfulDiversions} radiusKm={radiusKm} />

      {routeStart && <Marker position={[routeStart.lat, routeStart.lon]} icon={pointAIcon} />}
      {routeEnd && <Marker position={[routeEnd.lat, routeEnd.lon]} icon={pointBIcon} />}

      {routeResult?.status === "success" && (
        <Polyline
          positions={routeResult.coordinates}
          pathOptions={{ color: "#059669", weight: 5, opacity: 0.95, lineJoin: "round" }}
        />
      )}

      {patrolRouteResult?.status === "success" && (
        <>
          <Polyline
            positions={patrolRouteResult.route_coordinates}
            pathOptions={{ color: "#059669", weight: 4, opacity: 0.8, dashArray: "8, 8", lineJoin: "round" }}
          />
          {patrolRouteResult.ordered_incident_ids.map((id, index) => {
            const incident = incidents.find((i) => i.id === id) || (selectedTarget?.id === id ? selectedTarget : null);
            if (!incident) return null;
            return (
              <Marker
                key={`patrol-stop-${id}-${index}`}
                position={[incident.latitude, incident.longitude]}
                icon={makePatrolStopIcon(index + 1)}
                zIndexOffset={1000}
              />
            );
          })}
        </>
      )}

      <FitRoute routeStart={routeStart} routeEnd={routeEnd} routeResult={routeResult} />
    </MapContainer>
  );
}