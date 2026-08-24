import { Circle, MapContainer, Marker, Polyline, Popup, TileLayer, useMap, useMapEvents } from "react-leaflet";
import L from "leaflet";
import { Fragment, useEffect } from "react";

const vectorColors = ["#059669", "#d97706", "#e11d48", "#475569", "#10b981", "#b45309"];

const activeGreenIcon = L.divIcon({
  html: `<div style="width:20px;height:20px;background:#10b981;border:3px solid #ffffff;border-radius:50%;box-shadow:0 0 10px rgba(16,185,129,0.9), 0 2px 6px rgba(0,0,0,0.3);"></div>`,
  className: "",
  iconSize: [20, 20],
  iconAnchor: [10, 10],
});

const pastRedIcon = L.divIcon({
  html: `<div style="width:16px;height:16px;background:#e11d48;border:2px solid #ffffff;border-radius:50%;box-shadow:0 2px 6px rgba(0,0,0,0.3);"></div>`,
  className: "",
  iconSize: [16, 16],
  iconAnchor: [8, 8],
});

const plannedEventIcon = L.divIcon({
  html: `<div style="width:20px;height:20px;background:#d97706;border:3px dashed #ffffff;border-radius:50%;box-shadow:0 2px 8px rgba(217,119,6,0.5);"></div>`,
  className: "",
  iconSize: [20, 20],
  iconAnchor: [10, 10],
});

function makePointIcon(label, color) {
  return L.divIcon({
    html: `<div style="background:${color};color:white;width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:12px;border:2px solid white;box-shadow:0 3px 10px rgba(0,0,0,0.2);">${label}</div>`,
    className: "",
    iconSize: [28, 28],
    iconAnchor: [14, 14],
  });
}

function makePatrolStopIcon(number) {
  return L.divIcon({
    html: `<div style="background:#059669;color:white;width:22px;height:22px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:900;font-size:11px;border:2px solid white;box-shadow:0 3px 8px rgba(5,150,105,0.4);">${number}</div>`,
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
    return () => { container.style.cursor = ""; };
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

function IncidentMarker({
  incident,
  lat,
  lon,
  onCalculateDiversion,
  onRecommendDeployment,
  onFindSimilarEvents,
  onResolveIncident,
}) {
  const map = useMap();
  function runAfterClosingPopup(action) {
    map.closePopup();
    window.requestAnimationFrame(() => action(incident));
  }

  const title = incident.corridor || incident.junction || incident.zone || "Traffic Incident";
  const cause = String(incident.event_cause || "Traffic Jam").replaceAll("_", " ");
  const isActive = incident.isActiveAtTime !== false && incident.status !== "resolved";

  return (
    <Marker position={[lat, lon]} icon={isActive ? activeGreenIcon : pastRedIcon} zIndexOffset={isActive ? 500 : 0}>
      <Popup>
        <div className="min-w-[220px] space-y-2.5 p-1">
          <div>
            <div className="flex items-center justify-between gap-1 mb-1">
              <span
                className={`text-[9px] font-bold uppercase px-1.5 py-0.5 rounded border ${
                  isActive
                    ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                    : "bg-rose-50 text-rose-700 border-rose-200"
                }`}
              >
                {isActive ? "● Active Incident" : "Past / Resolved (5 min)"}
              </span>
              {incident.id && <span className="text-[9px] font-mono text-slate-400">{incident.id}</span>}
            </div>
            <h3 className="m-0 text-xs font-bold text-slate-900 capitalize leading-tight">{title}</h3>
            <span className="inline-block text-[10px] font-bold uppercase text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200 mt-1">
              {cause}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-1.5 pt-1">
            <button
              type="button"
              onClick={() => runAfterClosingPopup(onCalculateDiversion)}
              className="py-1.5 px-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-[10px] transition"
            >
              Find Diversion
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

          {isActive && onResolveIncident && (
            <button
              type="button"
              onClick={() => runAfterClosingPopup(onResolveIncident)}
              className="w-full py-1.5 rounded-lg bg-emerald-50 hover:bg-emerald-100 text-emerald-800 font-bold text-[10px] transition border border-emerald-300"
            >
              ✓ Mark as Resolved
            </button>
          )}
        </div>
      </Popup>
    </Marker>
  );
}

export default function MapView({
  incidents = [],
  plannedEventTarget,
  selectedTarget,
  radiusKm,
  diversionResult,
  formOpen,
  onMapClick,
  onCalculateDiversion,
  onRecommendDeployment,
  onFindSimilarEvents,
  onResolveIncident,
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

  return (
    <MapContainer center={[12.9716, 77.5946]} zoom={13} className="h-full w-full">
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      <MapClickHandler enabled={formOpen} onMapClick={onMapClick} />
      <RoutePlanClickHandler enabled={routeMode} onRoutePlanClick={onRoutePlanClick} />
      <CursorController routeMode={routeMode} />

      {incidents.map((incident) => {
        const lat = Number(incident.latitude ?? incident.lat);
        const lon = Number(incident.longitude ?? incident.lon);
        if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;

        return (
          <IncidentMarker
            key={`marker-${incident.id || incident.stableKey || `${lat}-${lon}`}`}
            incident={incident}
            lat={lat}
            lon={lon}
            onCalculateDiversion={onCalculateDiversion}
            onRecommendDeployment={onRecommendDeployment}
            onFindSimilarEvents={onFindSimilarEvents}
            onResolveIncident={onResolveIncident}
          />
        );
      })}

      {selectedTarget && Number.isFinite(Number(selectedTarget.lat)) && (
        <>
          <Marker
            position={[Number(selectedTarget.lat), Number(selectedTarget.lon)]}
            icon={activeGreenIcon}
            zIndexOffset={1000}
          />
          <Circle
            center={[Number(selectedTarget.lat), Number(selectedTarget.lon)]}
            radius={radiusKm * 1000}
            pathOptions={{ color: "#d97706", fillColor: "#d97706", fillOpacity: 0.08, dashArray: "5 5", weight: 2 }}
          />
        </>
      )}

      {plannedEventTarget && (
        <Marker position={[plannedEventTarget.lat, plannedEventTarget.lon]} icon={plannedEventIcon} />
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
              <Polyline positions={diversion.coordinates} pathOptions={{ color: "#ffffff", weight: isSelected ? 10 : 8, opacity: 0.9 }} />
              <Polyline positions={diversion.coordinates} pathOptions={{ color: vectorColors[index % vectorColors.length], weight: isSelected ? 6 : 4, opacity: lineOpacity, lineCap: "round", lineJoin: "round" }} />
            </Fragment>
          );
        });
      })()}

      <FitDiversions target={selectedTarget} diversions={successfulDiversions} radiusKm={radiusKm} />

      {routeStart && <Marker position={[routeStart.lat, routeStart.lon]} icon={pointAIcon} />}
      {routeEnd && <Marker position={[routeEnd.lat, routeEnd.lon]} icon={pointBIcon} />}

      {routeResult?.status === "success" && (
        <Polyline positions={routeResult.coordinates} pathOptions={{ color: "#059669", weight: 5, opacity: 0.95, lineJoin: "round" }} />
      )}

      {patrolRouteResult?.status === "success" && (
        <>
          <Polyline positions={patrolRouteResult.route_coordinates} pathOptions={{ color: "#059669", weight: 4, opacity: 0.8, dashArray: "8, 8", lineJoin: "round" }} />
          {patrolRouteResult.ordered_incident_ids.map((id, index) => {
            const incident = incidents.find((i) => i.id === id) || (selectedTarget?.id === id ? selectedTarget : null);
            if (!incident) return null;
            return (
              <Marker
                key={`patrol-stop-${id}-${index}`}
                position={[Number(incident.latitude ?? incident.lat), Number(incident.longitude ?? incident.lon)]}
                icon={makePatrolStopIcon(index )}
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