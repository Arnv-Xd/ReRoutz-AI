"""
app_integrated.py
===================
ReRoutz AI — Unified FastAPI backend with non-blocking reentrant locks,
runtime live incident persistence, graph routing, and static dataset analytics.
"""

import os
import time
import math
import threading
from datetime import datetime
from typing import List, Optional

import numpy as np
import osmnx as ox
import networkx as nx
import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

import deployment_service
from audit_logger import audit_logger

# ─── Path Configurations ───
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_valid_path(filename: str) -> str:
    parent_path = os.path.abspath(os.path.join(BASE_DIR, "..", "Data", filename))
    curr_path = os.path.abspath(os.path.join(BASE_DIR, "Data", filename))
    if os.path.exists(parent_path):
        return parent_path
    elif os.path.exists(curr_path):
        return curr_path
    data_dir = os.path.abspath(os.path.join(BASE_DIR, "..", "Data"))
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, filename)

DATA_PATH = get_valid_path("Dataset.csv")
LIVE_DATA_PATH = get_valid_path("Live_Incidents.csv")
PROCESSED_DATA_PATH = os.path.join(BASE_DIR, "processed_data.csv")

print(f"📁 Historical Dataset (Training/Similarity): {DATA_PATH}")
print(f"📁 Live Incidents Dataset (Runtime): {LIVE_DATA_PATH}")

_csv_lock = threading.RLock()
CSV_HEADER = "id,event_type,latitude,longitude,endlatitude,endlongitude,address,end_address,event_cause,requires_road_closure,start_datetime,end_datetime,status,authenticated,modified_datetime,description,veh_type,corridor,priority,zone,junction,resolved_datetime\n"

def safe_load_live_df() -> pd.DataFrame:
    with _csv_lock:
        try:
            if not os.path.exists(LIVE_DATA_PATH) or os.path.getsize(LIVE_DATA_PATH) < len(CSV_HEADER.strip()):
                with open(LIVE_DATA_PATH, "w", encoding="utf-8") as f:
                    f.write(CSV_HEADER)
                return pd.DataFrame(columns=CSV_HEADER.strip().split(","))

            df = pd.read_csv(LIVE_DATA_PATH, low_memory=False)
            if df.empty or "latitude" not in df.columns:
                with open(LIVE_DATA_PATH, "w", encoding="utf-8") as f:
                    f.write(CSV_HEADER)
                return pd.DataFrame(columns=CSV_HEADER.strip().split(","))
            return df
        except Exception:
            with open(LIVE_DATA_PATH, "w", encoding="utf-8") as f:
                f.write(CSV_HEADER)
            return pd.DataFrame(columns=CSV_HEADER.strip().split(","))

safe_load_live_df()

# ==========================================
# DATA MODELS
# ==========================================

class Point(BaseModel):
    lat: float
    lon: float

class ClusterRequest(BaseModel):
    target: Point
    active_cluster: List[Point]

class RouteDiversionRequest(BaseModel):
    start: Point
    end: Point
    blocking_incidents: List[Point]

class PatrolPoint(BaseModel):
    incident_id: str = "unknown"
    lat: float
    lon: float

class PatrolRouteRequest(BaseModel):
    start_point: Optional[PatrolPoint] = None
    active_cluster: List[PatrolPoint]

class CreateIncidentRequest(BaseModel):
    lat: float
    lon: float
    event_type: Optional[str] = "unplanned"
    event_cause: Optional[str] = "traffic_jam"
    priority: Optional[str] = "medium"
    veh_type: Optional[str] = "unknown"
    requires_road_closure: Optional[bool] = False
    corridor: Optional[str] = "unknown"
    junction: Optional[str] = "unknown"
    zone: Optional[str] = "unknown"
    description: Optional[str] = ""

# ==========================================
# 1. ADVANCED LOCAL GRAPH ENGINE
# ==========================================
class LocalDiversionEngine:
    def __init__(self, lat: float, lon: float, dist: int = 12000):
        print(f"🤖 Booting Advanced Cluster Graph Engine (Radius: {dist}m)...")
        print("⏳ Processing OSM graph into RAM...")
        self.G = ox.graph_from_point((lat, lon), dist=dist, network_type='drive')
        self.G = ox.add_edge_speeds(self.G)
        self.G = ox.add_edge_travel_times(self.G)
        self.original_G = self.G.copy()
        print(f"✅ Computational Engine Online: {len(self.G.nodes)} nodes, {len(self.G.edges)} edges.")

    def _sever_incident_point(self, lat: float, lon: float) -> int:
        severed = 0
        try:
            node = ox.nearest_nodes(self.G, lon, lat)
            touching = list(self.G.out_edges(node, keys=True)) + list(self.G.in_edges(node, keys=True))
            for u, v, k in touching:
                if self.G.has_edge(u, v, k):
                    self.G.remove_edge(u, v, k)
                    severed += 1
        except Exception:
            pass

        try:
            u, v, _ = ox.nearest_edges(self.G, lon, lat)
            for a, b in [(u, v), (v, u)]:
                edge_data = self.G.get_edge_data(a, b)
                if edge_data:
                    for k in list(edge_data.keys()):
                        if self.G.has_edge(a, b, k):
                            self.G.remove_edge(a, b, k)
                            severed += 1
        except Exception:
            pass

        return severed

    def calculate_cluster_diversions(self, target_lat: float, target_lon: float, active_cluster_coords: List[Point]):
        self.G = self.original_G.copy()
        for pt in active_cluster_coords:
            self._sever_incident_point(pt.lat, pt.lon)

        try:
            u_target, v_target, _ = ox.nearest_edges(self.original_G, target_lon, target_lat)
            approaching_edges = self.original_G.in_edges(u_target, data=True)
            diversion_manifest = []

            for source_node, _, data in approaching_edges:
                if source_node == v_target:
                    continue
                raw_name = data.get('name', 'Local Street')
                incoming_road = raw_name[0] if isinstance(raw_name, list) else raw_name
                bypass_path = None

                for depth in range(6):
                    if bypass_path:
                        break
                    target_pool = list(nx.ego_graph(self.original_G, v_target, radius=depth).nodes)
                    for potential_target in target_pool:
                        try:
                            bypass_path = nx.shortest_path(self.G, source=source_node, target=potential_target, weight='travel_time')
                            break
                        except nx.NetworkXNoPath:
                            continue

                if bypass_path:
                    coords = [[self.G.nodes[n]['y'], self.G.nodes[n]['x']] for n in bypass_path]
                    diversion_manifest.append({"from_road": incoming_road, "coordinates": coords, "status": "success"})
                else:
                    diversion_manifest.append({"from_road": incoming_road, "status": "gridlock"})

            return diversion_manifest
        except Exception as e:
            return [{"from_road": "System", "status": f"Graph Error: {str(e)}"}]

    def calculate_point_to_point_route(self, start_lat: float, start_lon: float, end_lat: float, end_lon: float, blocking_points: List[Point]):
        self.G = self.original_G.copy()
        severed_count = 0
        for pt in blocking_points:
            severed_count += self._sever_incident_point(pt.lat, pt.lon)

        try:
            start_node = ox.nearest_nodes(self.G, start_lon, start_lat)
            end_node = ox.nearest_nodes(self.G, end_lon, end_lat)
        except Exception as e:
            return {"status": "error", "message": f"Could not snap points to road network: {str(e)}"}

        try:
            path = nx.shortest_path(self.G, source=start_node, target=end_node, weight='travel_time')
            coords = [[self.G.nodes[n]['y'], self.G.nodes[n]['x']] for n in path]
            return {"status": "success", "coordinates": coords, "severed_edges": severed_count}
        except nx.NetworkXNoPath:
            return {"status": "gridlock", "message": "No path exists between these points avoiding active blockages.", "severed_edges": severed_count}
        except nx.NodeNotFound as e:
            return {"status": "error", "message": f"Node not found in graph: {str(e)}"}

# ==========================================
# 2. FASTAPI SERVER CONFIGURATION
# ==========================================
app = FastAPI(title="ReRoutz AI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = LocalDiversionEngine(12.9716, 77.5946, dist=12000)

deployment_service.load_models()
app.include_router(deployment_service.router)

# ==========================================
# 3. ROUTE DEFINITIONS
# ==========================================

@app.get("/health")
def health():
    return {"status": "ok", "diversion_engine": "loaded", "deployment_models": "loaded"}

@app.get("/get-dataset")
def get_dataset():
    try:
        df = safe_load_live_df()
        if df.empty:
            return {"status": "success", "data": []}
        df = df.dropna(subset=['latitude', 'longitude']).fillna("")
        return {"status": "success", "data": df.to_dict(orient="records")}
    except Exception:
        return {"status": "success", "data": []}

@app.post("/create-incident")
def create_incident(payload: CreateIncidentRequest):
    try:
        now_utc = datetime.utcnow()
        now_str = now_utc.strftime("%Y-%m-%d %H:%M:%S+00")
        unique_id = f"EVT{int(now_utc.timestamp())}"

        new_row = {
            "id": unique_id,
            "event_type": payload.event_type or "unplanned",
            "latitude": payload.lat,
            "longitude": payload.lon,
            "endlatitude": payload.lat,
            "endlongitude": payload.lon,
            "address": payload.corridor or "Bengaluru Urban",
            "end_address": "",
            "event_cause": payload.event_cause or "traffic_jam",
            "requires_road_closure": bool(payload.requires_road_closure),
            "start_datetime": now_str,
            "end_datetime": "",
            "status": "open",
            "authenticated": "yes",
            "modified_datetime": now_str,
            "description": payload.description or f"{payload.event_cause} at {payload.corridor}",
            "veh_type": payload.veh_type or "unknown",
            "corridor": payload.corridor or "unknown",
            "priority": payload.priority or "medium",
            "zone": payload.zone or "unknown",
            "junction": payload.junction or "unknown",
            "resolved_datetime": "",
        }

        with _csv_lock:
            df = safe_load_live_df()
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            df.to_csv(LIVE_DATA_PATH, index=False)

        print(f"💾 Added incident {unique_id} to {LIVE_DATA_PATH}")
        return {"status": "success", "incident": new_row}
    except Exception as e:
        print(f"❌ Error in /create-incident: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/resolve-incident/{incident_id}")
def resolve_incident(incident_id: str):
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S+00")
    with _csv_lock:
        df = safe_load_live_df()
        match_mask = df["id"].astype(str) == str(incident_id)
        if not match_mask.any():
            return {"status": "error", "message": f"Incident {incident_id} not found."}
        df.loc[match_mask, "status"] = "resolved"
        df.loc[match_mask, "end_datetime"] = now_str
        df.loc[match_mask, "resolved_datetime"] = now_str
        df.to_csv(LIVE_DATA_PATH, index=False)

    print(f"💾 Resolved incident {incident_id} in {LIVE_DATA_PATH}")
    return {"status": "success", "message": f"Incident {incident_id} resolved."}

@app.post("/calculate-cluster-diversion")
def calculate_cluster_diversion(req: ClusterRequest):
    t0 = time.monotonic()
    manifest = engine.calculate_cluster_diversions(req.target.lat, req.target.lon, req.active_cluster)
    elapsed_ms = round((time.monotonic() - t0) * 1000)
    success_count = len([m for m in manifest if m.get("status") == "success"])
    gridlock_count = len([m for m in manifest if m.get("status") == "gridlock"])

    audit_logger.log("diversion_query", {
        "target_lat": req.target.lat,
        "target_lon": req.target.lon,
        "cluster_size": len(req.active_cluster),
        "total_diversions_found": success_count,
        "gridlock_count": gridlock_count,
        "response_time_ms": elapsed_ms,
    })
    return {"total_diversions": success_count, "diversions": manifest}

@app.post("/calculate-route-diversion")
def calculate_route_diversion(req: RouteDiversionRequest):
    t0 = time.monotonic()
    result = engine.calculate_point_to_point_route(req.start.lat, req.start.lon, req.end.lat, req.end.lon, req.blocking_incidents)
    elapsed_ms = round((time.monotonic() - t0) * 1000)

    audit_logger.log("route_query", {
        "start_lat": req.start.lat,
        "start_lon": req.start.lon,
        "end_lat": req.end.lat,
        "end_lon": req.end.lon,
        "blocking_incidents_count": len(req.blocking_incidents),
        "route_status": result.get("status"),
        "response_time_ms": elapsed_ms,
    })
    return result

@app.post("/optimize-patrol-route")
def optimize_patrol_route(req: PatrolRouteRequest):
    if not engine.original_G:
        return {"status": "error", "message": "Graph not loaded."}
        
    t0 = time.monotonic()
    points = list(req.active_cluster)
    if req.start_point:
        existing = [p for p in points if p.incident_id == req.start_point.incident_id and p.lat == req.start_point.lat and p.lon == req.start_point.lon]
        if not existing:
            points.insert(0, req.start_point)
        else:
            points.remove(existing[0])
            points.insert(0, existing[0])
            
    n = len(points)
    if n <= 1:
        return {"status": "success", "route": [{"lat": p.lat, "lon": p.lon, "incident_id": p.incident_id} for p in points], "total_time_min": 0.0, "total_distance_km": 0.0}

    if n > 25:
        return {"status": "error", "message": f"Cluster size {n} is too large for patrol routing."}

    nodes = []
    for p in points:
        try:
            node = ox.nearest_nodes(engine.original_G, p.lon, p.lat)
            nodes.append(node)
        except Exception:
            return {"status": "error", "message": f"Could not snap point {p.incident_id} to road network."}

    matrix = {}
    for i in range(n):
        try:
            lengths, paths = nx.single_source_dijkstra(engine.original_G, source=nodes[i], weight='travel_time')
            for j in range(n):
                if i == j:
                    matrix[(i, j)] = (0.0, 0.0, [])
                else:
                    target = nodes[j]
                    if target in lengths:
                        path = paths[target]
                        tt = lengths[target]
                        dist = sum(min(e.get('length', 0) for e in engine.original_G[path[k]][path[k+1]].values()) for k in range(len(path)-1))
                        matrix[(i, j)] = (tt, dist, path)
                    else:
                        matrix[(i, j)] = (float('inf'), float('inf'), [])
        except Exception:
            for j in range(n):
                matrix[(i, j)] = (0.0, 0.0, []) if i == j else (float('inf'), float('inf'), [])

    visited = [0]
    unvisited = set(range(1, n))
    while unvisited:
        curr = visited[-1]
        next_node = min(unvisited, key=lambda x: matrix[(curr, x)][0])
        visited.append(next_node)
        unvisited.remove(next_node)

    total_time = 0.0
    total_dist = 0.0
    full_path_coords = []
    for k in range(n - 1):
        i, j = visited[k], visited[k+1]
        tt, dist, path = matrix[(i, j)]
        if tt == float('inf'):
            return {"status": "error", "message": "Graph is disconnected."}
        total_time += tt
        total_dist += dist
        coords = [[engine.original_G.nodes[node]['y'], engine.original_G.nodes[node]['x']] for node in path]
        if k > 0 and len(coords) > 0:
            coords = coords[1:]
        full_path_coords.extend(coords)
        
    ordered_ids = [points[i].incident_id for i in visited]
    elapsed_ms = round((time.monotonic() - t0) * 1000)
    
    return {
        "status": "success",
        "ordered_incident_ids": ordered_ids,
        "route_coordinates": full_path_coords,
        "total_distance_m": round(total_dist, 1),
        "total_travel_time_s": round(total_time, 1),
        "response_time_ms": elapsed_ms
    }

# ==========================================
# 4. DIRECT DATASET ANALYTICS ENDPOINT
# ==========================================
def _clean_num(val, default=0.0):
    if val is None or pd.isna(val):
        return default
    if isinstance(val, (float, np.floating)):
        if math.isnan(val) or math.isinf(val):
            return default
        return float(val)
    if isinstance(val, (int, np.integer)):
        return int(val)
    return val

@app.get("/analytics-summary")
def get_analytics_summary():
    try:
        # Load from historical paths directly
        df = pd.DataFrame()
        for candidate_path in [PROCESSED_DATA_PATH, DATA_PATH]:
            if os.path.isfile(candidate_path):
                try:
                    loaded_df = pd.read_csv(candidate_path, low_memory=False)
                    if not loaded_df.empty:
                        df = loaded_df
                        break
                except Exception:
                    continue

        if df.empty:
            return JSONResponse(content={
                "window_start": None,
                "window_end": None,
                "incident_count_in_window": 0,
                "incident_volume_timeseries": [],
                "incident_type_breakdown": [],
                "severity_tier_distribution": [],
                "top_hotspot_corridors": [],
                "avg_personnel_barricades_trend": [],
                "temporal_pattern_heatmap": [],
            })

        # 1. Parse timestamps
        date_col = None
        for col in ["start_datetime", "created_date", "datetime", "date", "timestamp"]:
            if col in df.columns:
                date_col = col
                break

        if date_col:
            df["parsed_start"] = pd.to_datetime(df[date_col], errors="coerce")
        else:
            df["parsed_start"] = pd.Timestamp.now()

        df["parsed_start"] = df["parsed_start"].fillna(pd.Timestamp("2026-01-01"))

        # 2. Volume Timeseries
        df["date_str"] = df["parsed_start"].dt.strftime("%Y-%m-%d").fillna("Overall")
        volume_df = (
            df.groupby("date_str")
            .size()
            .reset_index(name="count")
            .sort_values("date_str")
            .tail(30)
        )
        volume_timeseries = [
            {"date": str(r["date_str"]), "count": int(r["count"])}
            for _, r in volume_df.iterrows()
        ]

        # 3. Cause breakdown
        cause_col = None
        for col in ["event_cause", "cause", "event_type", "type"]:
            if col in df.columns:
                cause_col = col
                break

        if cause_col:
            cause_counts = (
                df[cause_col]
                .fillna("General Incident")
                .astype(str)
                .replace({"nan": "General Incident", "": "General Incident", "None": "General Incident"})
                .value_counts()
                .head(8)
                .reset_index()
            )
            cause_counts.columns = ["event_cause", "count"]
            incident_type_breakdown = [
                {"event_cause": str(r["event_cause"]).replace("_", " ").title(), "count": int(r["count"])}
                for _, r in cause_counts.iterrows()
            ]
        else:
            incident_type_breakdown = [{"event_cause": "Traffic Congestion", "count": int(len(df))}]

        # 4. Severity Distribution
        tier_col = None
        for col in ["deployment_tier", "priority", "severity", "tier"]:
            if col in df.columns:
                tier_col = col
                break

        if tier_col:
            tier_counts = (
                df[tier_col]
                .fillna("Medium")
                .astype(str)
                .replace({"nan": "Medium", "": "Medium", "None": "Medium"})
                .str.capitalize()
                .value_counts()
                .reset_index()
            )
            tier_counts.columns = ["deployment_tier", "count"]
            severity_tier_distribution = [
                {"deployment_tier": str(r["deployment_tier"]), "count": int(r["count"])}
                for _, r in tier_counts.iterrows()
            ]
        else:
            severity_tier_distribution = [
                {"deployment_tier": "Low", "count": int(len(df) * 0.3)},
                {"deployment_tier": "Medium", "count": int(len(df) * 0.5)},
                {"deployment_tier": "High", "count": int(len(df) * 0.2)},
            ]

        # 5. Hotspot Corridors
        corridor_col = None
        for col in ["corridor", "address", "road_name", "location", "junction"]:
            if col in df.columns:
                corridor_col = col
                break

        top_hotspot_corridors = []
        if corridor_col:
            valid_corridors = df[
                ~df[corridor_col].astype(str).str.lower().isin(["unknown", "", "none", "nan", "null"])
            ]
            if not valid_corridors.empty:
                top_c = (
                    valid_corridors[corridor_col]
                    .value_counts()
                    .head(7)
                    .reset_index()
                )
                top_c.columns = ["corridor", "count"]
                top_hotspot_corridors = [
                    {"corridor": str(r["corridor"]).title(), "count": int(r["count"])}
                    for _, r in top_c.iterrows()
                ]

        if not top_hotspot_corridors:
            top_hotspot_corridors = [{"corridor": "Bengaluru Central Arterial", "count": int(len(df))}]

        # 6. Sizing Trend
        avg_pb_trend = []
        has_p = "recommended_personnel" in df.columns
        has_b = "recommended_barricades" in df.columns

        if has_p and has_b:
            df["recommended_personnel"] = pd.to_numeric(df["recommended_personnel"], errors="coerce").fillna(6.0)
            df["recommended_barricades"] = pd.to_numeric(df["recommended_barricades"], errors="coerce").fillna(4.0)

            pb_grouped = (
                df.groupby("date_str")[["recommended_personnel", "recommended_barricades"]]
                .mean()
                .reset_index()
                .tail(20)
            )
            for _, r in pb_grouped.iterrows():
                avg_pb_trend.append({
                    "date": str(r["date_str"]),
                    "recommended_personnel": round(float(_clean_num(r["recommended_personnel"], 6.0)), 1),
                    "recommended_barricades": round(float(_clean_num(r["recommended_barricades"], 4.0)), 1),
                })
        else:
            for item in volume_timeseries[-12:]:
                avg_pb_trend.append({
                    "date": item["date"],
                    "recommended_personnel": 8.0,
                    "recommended_barricades": 6.0,
                })

        # 7. Heatmap
        df["day_of_week"] = df["parsed_start"].dt.day_name().fillna("Monday")
        df["hour"] = df["parsed_start"].dt.hour.fillna(12).astype(int)

        heatmap_df = (
            df.groupby(["day_of_week", "hour"])
            .size()
            .reset_index(name="count")
        )
        temporal_pattern_heatmap = [
            {"day_of_week": str(r["day_of_week"]), "hour": int(r["hour"]), "count": int(r["count"])}
            for _, r in heatmap_df.iterrows()
        ]

        payload = {
            "window_start": None,
            "window_end": None,
            "incident_count_in_window": int(len(df)),
            "incident_volume_timeseries": volume_timeseries,
            "incident_type_breakdown": incident_type_breakdown,
            "severity_tier_distribution": severity_tier_distribution,
            "top_hotspot_corridors": top_hotspot_corridors,
            "avg_personnel_barricades_trend": avg_pb_trend,
            "temporal_pattern_heatmap": temporal_pattern_heatmap,
        }

        return JSONResponse(content=payload)

    except Exception as e:
        print(f"⚠️ Analytics calculation error: {e}")
        return JSONResponse(content={
            "window_start": None,
            "window_end": None,
            "incident_count_in_window": 0,
            "incident_volume_timeseries": [],
            "incident_type_breakdown": [],
            "severity_tier_distribution": [],
            "top_hotspot_corridors": [],
            "avg_personnel_barricades_trend": [],
            "temporal_pattern_heatmap": [],
        })

@app.get("/audit-logs")
def get_audit_logs(event_type: str = None, limit: int = 50, offset: int = 0):
    from audit_logger import _build_client, _SUPABASE_AVAILABLE
    if not _SUPABASE_AVAILABLE:
        return {"status": "error", "message": "Supabase not configured", "data": [], "total": 0}
    client = _build_client()
    if client is None:
        return {"status": "error", "message": "Supabase unavailable", "data": [], "total": 0}
    try:
        query = client.table("audit_logs").select("*", count="exact").order("created_at", desc=True)
        if event_type:
            query = query.eq("event_type", event_type)
        query = query.range(offset, offset + limit - 1)
        response = query.execute()
        return {"status": "success", "data": response.data, "total": response.count if response.count is not None else len(response.data)}
    except Exception as exc:
        return {"status": "error", "message": str(exc), "data": [], "total": 0}

@app.get("/audit-logs/stats")
def get_audit_stats():
    from audit_logger import _build_client, _SUPABASE_AVAILABLE
    if not _SUPABASE_AVAILABLE:
        return {"status": "error", "counts": {}, "avg_response_ms": {}}
    client = _build_client()
    if client is None:
        return {"status": "error", "counts": {}, "avg_response_ms": {}}
    try:
        response = client.table("audit_logs").select("event_type, payload").execute()
        rows = response.data or []
        from collections import defaultdict
        counts = defaultdict(int)
        for row in rows:
            counts[row.get("event_type", "unknown")] += 1
        return {"status": "success", "total": len(rows), "counts": dict(counts), "avg_response_ms": {}}
    except Exception as exc:
        return {"status": "error", "message": str(exc), "counts": {}, "avg_response_ms": {}}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)