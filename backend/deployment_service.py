"""
deployment_service.py
=======================
EventFlow AI — Stage 2d: FastAPI router for manpower/barricade predictions.

Mount this into your existing app.py (see app_integrated.py for a full
example) so the diversion engine and the deployment model share one process
and one set of model artifacts loaded once at startup.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import time
import joblib
import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from audit_logger import audit_logger
from inference_features import DeploymentFeatureBuilder

router = APIRouter()

# ─── Robust Absolute Paths ───
BASE_DIR = Path(__file__).resolve().parent
ARTIFACTS_DIR = BASE_DIR / "model_artifacts"
FEATURE_METADATA_PATH = BASE_DIR / "feature_metadata.json"

_builder: Optional[DeploymentFeatureBuilder] = None
_personnel_model = None
_barricade_model = None
_tier_model = None
_tier_encoder = None

_historical_rows = []
_historical_tfidf = None


class DeploymentRequest(BaseModel):
    incident_id: str = Field(default="unknown", description="Unique ID for the incident")
    lat: float
    lon: float
    event_type: str = Field(default="unplanned", description="'planned' or 'unplanned'")
    event_cause: str = Field(default="others")
    priority: str = Field(default="unknown")
    veh_type: str = Field(default="others")
    requires_road_closure: bool = False
    corridor: str = "unknown"
    junction: str = "unknown"
    zone: str = "unknown"
    description: str = ""
    start_datetime: Optional[str] = None
    expected_duration_minutes: float = 60.0


class DeploymentResponse(BaseModel):
    recommended_personnel: int
    recommended_barricades: int
    deployment_tier: str
    severity_encoded: int
    affected_radius_km: float
    is_major_corridor: bool
    location_cluster: int
    explanation: List[str]
    label_basis: str = (
        "Model estimate trained on weak-supervision proxy labels "
        "(no historical ground-truth deployment records exist yet). "
        "Treat as a starting recommendation, not a measured fact."
    )


class ClusterAreaResponse(BaseModel):
    personnel_total: int
    barricades_total: int
    tier_max: str
    incident_count: int
    radius_km: float
    label_basis: str
    included_incident_ids: List[str]


class ClusterDeploymentRequest(BaseModel):
    target: DeploymentRequest
    active_cluster: List[DeploymentRequest]
    radius_km: float


class ClusterDeploymentResponse(BaseModel):
    single_point: DeploymentResponse
    cluster_area: ClusterAreaResponse


class SimilarityRequest(BaseModel):
    description: str = ""
    event_cause: str = "unknown"
    event_type: str = "unplanned"
    lat: float
    lon: float


class SimilarIncidentMatch(BaseModel):
    incident_id: str
    date: str
    description: str
    similarity_score: float
    event_type: str
    location: str
    recommended_personnel: int
    recommended_barricades: int
    deployment_tier: str


class SimilarityResponse(BaseModel):
    matches: List[SimilarIncidentMatch]


class PlanEventRequest(BaseModel):
    event_type: str = "planned"
    lat: float
    lon: float
    corridor: str = "unknown"
    junction: str = "unknown"
    zone: str = "unknown"
    planned_date_time: str
    expected_duration_hours: float
    description: str = ""


class PlanEventResponse(BaseModel):
    pre_event_risk_index: float
    recommended_personnel: int
    recommended_barricades: int
    deployment_tier: str
    deployment_lead_time_hours: float


def load_models() -> None:
    """Call once at app startup to load trained models and feature metadata."""
    global _builder, _personnel_model, _barricade_model, _tier_model, _tier_encoder
    global _historical_rows, _historical_tfidf

    print(f"Loading deployment models from {ARTIFACTS_DIR} ...")
    try:
        _builder = DeploymentFeatureBuilder(ARTIFACTS_DIR, FEATURE_METADATA_PATH)
        _personnel_model = joblib.load(ARTIFACTS_DIR / "personnel_model.joblib")
        _barricade_model = joblib.load(ARTIFACTS_DIR / "barricade_model.joblib")
        _tier_model = joblib.load(ARTIFACTS_DIR / "tier_model.joblib")
        _tier_encoder = joblib.load(ARTIFACTS_DIR / "tier_label_encoder.joblib")
        print("✅ RandomForest Deployment models loaded successfully.")
    except Exception as e:
        print(f"❌ Error loading ML model artifacts: {e}")
        return

    print("Precomputing TF-IDF vectors for historical incidents (Similarity Search)...")
    try:
        csv_path = BASE_DIR / "processed_data.csv"
        if not csv_path.is_file():
            csv_path = ARTIFACTS_DIR / "deployment_dataset.csv"
        if not csv_path.is_file():
            csv_path = BASE_DIR / "Data" / "Dataset.csv"
        if not csv_path.is_file():
            csv_path = BASE_DIR.parent / "Data" / "Dataset.csv"

        if csv_path.is_file():
            df = pd.read_csv(csv_path)
            if "latitude" in df.columns and "lat" not in df.columns:
                df["lat"] = df["latitude"]
            if "longitude" in df.columns and "lon" not in df.columns:
                df["lon"] = df["longitude"]

            df["description"] = df.get("description", pd.Series([""] * len(df))).fillna("")
            df["event_cause"] = df.get("event_cause", pd.Series([""] * len(df))).fillna("")

            combined_texts = (df["description"].astype(str) + " " + df["event_cause"].astype(str)).str.lower().tolist()
            _historical_tfidf = _builder.tfidf_vectorizer.transform(combined_texts)
            _historical_rows = df.to_dict("records")
            print(f"Cached {_historical_tfidf.shape[0]} historical incidents for similarity search (from {csv_path}).")
        else:
            print("⚠️ Warning: Historical dataset not found for similarity search caching.")
    except Exception as e:
        print(f"⚠️ Warning: Failed to precompute similarity vectors: {e}")


@router.post("/predict-deployment", response_model=DeploymentResponse)
def predict_deployment(req: DeploymentRequest) -> DeploymentResponse:
    if _builder is None or _personnel_model is None:
        raise HTTPException(status_code=503, detail="Deployment models not loaded yet. Call load_models() at startup.")

    t0 = time.monotonic()
    try:
        frame, extras = _builder.build(req.model_dump())
        
        # Base ML predictions from trained RandomForest models
        personnel = float(_personnel_model.predict(frame)[0])
        barricades = float(_barricade_model.predict(frame)[0])
        tier_idx = _tier_model.predict(frame)[0]
        tier = str(_tier_encoder.inverse_transform([tier_idx])[0])

        # Feature sensitivity scaling for priority and closures
        priority = (req.priority or "medium").lower()
        if priority in ("critical", "p0", "severe", "very_high"):
            personnel = max(personnel * 1.8, 14.0)
            barricades = max(barricades * 1.8, 12.0)
            tier = "Critical"
        elif priority in ("high", "p1"):
            personnel = max(personnel * 1.4, 9.0)
            barricades = max(barricades * 1.4, 7.0)
            if tier in ("Low", "Medium"):
                tier = "High"
        elif priority in ("low", "p3", "minor"):
            personnel = min(personnel * 0.7, 4.0)
            barricades = min(barricades * 0.7, 3.0)
            tier = "Low"

        if req.requires_road_closure:
            personnel += 6.0
            barricades += 8.0
            if tier == "Low":
                tier = "Medium"
            elif tier == "Medium":
                tier = "High"
            elif tier == "High":
                tier = "Critical"

    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {exc}") from exc
        
    elapsed_ms = round((time.monotonic() - t0) * 1000)

    recommended_personnel = max(2, round(personnel))
    recommended_barricades = max(2, round(barricades))
    explanation = build_explanation(req, extras, recommended_personnel, recommended_barricades)

    # ── Immutable audit record ──
    audit_logger.log("deployment_prediction", {
        "incident_id": req.incident_id,
        "lat": req.lat,
        "lon": req.lon,
        "event_type": req.event_type,
        "event_cause": req.event_cause,
        "priority": req.priority,
        "veh_type": req.veh_type,
        "requires_road_closure": req.requires_road_closure,
        "corridor": req.corridor,
        "junction": req.junction,
        "zone": req.zone,
        "description": req.description,
        "start_datetime": req.start_datetime,
        "recommended_personnel": recommended_personnel,
        "recommended_barricades": recommended_barricades,
        "deployment_tier": tier,
        "severity_encoded": extras["severity_encoded"],
        "affected_radius_km": extras["affected_radius"],
        "is_major_corridor": bool(extras["is_major_corridor"]),
        "location_cluster": extras["location_cluster"],
        "explanation": explanation,
        "response_time_ms": elapsed_ms,
    })

    return DeploymentResponse(
        recommended_personnel=recommended_personnel,
        recommended_barricades=recommended_barricades,
        deployment_tier=tier,
        severity_encoded=extras["severity_encoded"],
        affected_radius_km=extras["affected_radius"],
        is_major_corridor=bool(extras["is_major_corridor"]),
        location_cluster=extras["location_cluster"],
        explanation=explanation,
    )


@router.post("/predict-deployment-cluster", response_model=ClusterDeploymentResponse)
def predict_deployment_cluster(req: ClusterDeploymentRequest) -> ClusterDeploymentResponse:
    if _builder is None:
        raise HTTPException(status_code=503, detail="Deployment models not loaded yet. Call load_models() at startup.")

    single_point_resp = predict_deployment(req.target)

    cluster_responses = []
    included_ids = []

    try:
        tier_hierarchy = {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}
        total_personnel = 0
        total_barricades = 0
        max_tier_val = 1
        max_tier_str = "Low"

        for inc in req.active_cluster:
            resp = predict_deployment(inc)
            cluster_responses.append(resp)
            included_ids.append(inc.incident_id)

            total_personnel += resp.recommended_personnel
            total_barricades += resp.recommended_barricades

            t_val = tier_hierarchy.get(resp.deployment_tier, 1)
            if t_val > max_tier_val:
                max_tier_val = t_val
                max_tier_str = resp.deployment_tier

        if not cluster_responses:
            cluster_area_resp = ClusterAreaResponse(
                personnel_total=single_point_resp.recommended_personnel,
                barricades_total=single_point_resp.recommended_barricades,
                tier_max=single_point_resp.deployment_tier,
                incident_count=1,
                radius_km=req.radius_km,
                label_basis=single_point_resp.label_basis,
                included_incident_ids=[req.target.incident_id]
            )
        else:
            cluster_area_resp = ClusterAreaResponse(
                personnel_total=total_personnel,
                barricades_total=total_barricades,
                tier_max=max_tier_str,
                incident_count=len(req.active_cluster),
                radius_km=req.radius_km,
                label_basis=single_point_resp.label_basis,
                included_incident_ids=included_ids
            )

        return ClusterDeploymentResponse(
            single_point=single_point_resp,
            cluster_area=cluster_area_resp
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Cluster prediction failed: {exc}") from exc


def build_explanation(req: DeploymentRequest, extras: dict, personnel: int, barricades: int) -> list[str]:
    reasons = [
        (
            f"The estimated {extras['affected_radius']:.2f} km impact radius is a primary sizing signal; "
            "larger affected areas require more coverage points and staff."
        )
    ]

    if req.requires_road_closure:
        reasons.append("A road closure increases both traffic-control staffing and barricade requirements.")
    if extras["is_major_corridor"]:
        reasons.append("The incident is on a major corridor, increasing control points and diversion complexity.")
    if req.priority.lower() in ("high", "critical", "p0", "p1", "severe"):
        reasons.append("High priority raises the inferred severity and the recommended response capacity.")

    text = f"{req.event_cause} {req.description}".lower()
    if any(token in text for token in ("rally", "protest", "procession", "crowd")):
        reasons.append("Crowd or procession language adds perimeter-control and public-safety demand.")
    if any(token in text for token in ("accident", "crash", "collision")):
        reasons.append("Accident language adds scene protection and traffic separation requirements.")

    if len(reasons) == 1:
        reasons.append(
            "No road closure, major-corridor, high-priority, crowd, or accident signal was supplied, "
            "so the recommendation remains near the model's lower operating range."
        )

    reasons.append(
        f"Combined model severity is {extras['severity_encoded']} on the encoded 0-2 scale; "
        f"learned interactions across these inputs and historical location patterns produced "
        f"{personnel} personnel and {barricades} barricades."
    )
    return reasons


@router.post("/similar-incidents", response_model=SimilarityResponse)
def similar_incidents(req: SimilarityRequest) -> SimilarityResponse:
    if _builder is None or _historical_tfidf is None or not _historical_rows:
        raise HTTPException(status_code=503, detail="Similarity engine not initialized.")

    combined_text = f"{req.description} {req.event_cause}".lower()
    query_vec = _builder.tfidf_vectorizer.transform([combined_text])

    sim_scores = cosine_similarity(query_vec, _historical_tfidf).flatten()

    req_cluster = _builder._assign_cluster(req.lat, req.lon)

    for i, row in enumerate(_historical_rows):
        if str(row.get("event_type", "")).lower() == req.event_type.lower():
            sim_scores[i] += 0.05
        if row.get("location_cluster") == req_cluster and req_cluster != -1:
            sim_scores[i] += 0.05

    top_indices = sim_scores.argsort()[-5:][::-1]

    matches = []
    for idx in top_indices:
        score = float(sim_scores[idx])
        row = _historical_rows[idx]

        sim_req_dict = {
            "lat": float(row.get("lat", 0.0)),
            "lon": float(row.get("lon", 0.0)),
            "event_type": str(row.get("event_type", "unplanned")),
            "event_cause": str(row.get("event_cause", "others")),
            "priority": str(row.get("priority", "unknown")),
            "veh_type": str(row.get("veh_type", "others")),
            "requires_road_closure": bool(row.get("requires_road_closure", False)),
            "corridor": str(row.get("corridor", "unknown")),
            "junction": str(row.get("junction", "unknown")),
            "zone": str(row.get("zone", "unknown")),
            "description": str(row.get("description", "")),
            "start_datetime": str(row.get("start_datetime", "")),
            "expected_duration_minutes": float(row.get("expected_duration_minutes", 60.0))
        }

        try:
            frame, _ = _builder.build(sim_req_dict)
            personnel = max(2, round(float(_personnel_model.predict(frame)[0])))
            barricades = max(2, round(float(_barricade_model.predict(frame)[0])))
            tier_idx = _tier_model.predict(frame)[0]
            tier = str(_tier_encoder.inverse_transform([tier_idx])[0])
        except Exception:
            personnel = 2
            barricades = 2
            tier = "Low"

        desc = str(row.get("description", ""))
        if len(desc) > 60:
            desc = desc[:57] + "..."

        corridor = str(row.get("corridor", ""))
        junction = str(row.get("junction", ""))
        if junction and junction != "unknown":
            loc_label = junction
        elif corridor and corridor != "unknown":
            loc_label = corridor
        else:
            loc_label = "Unknown Location"

        date_str = str(row.get("start_datetime", ""))[:10] if str(row.get("start_datetime", "")) else "Unknown"

        matches.append(SimilarIncidentMatch(
            incident_id=str(row.get("id", "unknown")),
            date=date_str,
            description=desc,
            similarity_score=score,
            event_type=str(row.get("event_type", "unknown")),
            location=loc_label,
            recommended_personnel=personnel,
            recommended_barricades=barricades,
            deployment_tier=tier
        ))

    return SimilarityResponse(matches=matches)


@router.post("/plan-event", response_model=PlanEventResponse)
def plan_event(req: PlanEventRequest) -> PlanEventResponse:
    if _builder is None or _personnel_model is None:
        raise HTTPException(status_code=503, detail="Models not loaded yet.")

    t0 = time.monotonic()

    sim_req_dict = {
        "lat": req.lat,
        "lon": req.lon,
        "event_type": req.event_type,
        "event_cause": "planned_event",
        "priority": "high",
        "veh_type": "others",
        "requires_road_closure": True,
        "corridor": req.corridor,
        "junction": req.junction,
        "zone": req.zone,
        "description": req.description,
        "start_datetime": req.planned_date_time,
        "expected_duration_minutes": req.expected_duration_hours * 60.0
    }

    frame, extras = _builder.build(sim_req_dict)

    personnel = max(2, round(float(_personnel_model.predict(frame)[0])))
    barricades = max(2, round(float(_barricade_model.predict(frame)[0])))
    tier_idx = _tier_model.predict(frame)[0]
    tier = str(_tier_encoder.inverse_transform([tier_idx])[0])

    tier_scores = {"Low": 20, "Medium": 50, "High": 75, "Critical": 90}
    base_risk = tier_scores.get(tier, 20)

    peak_flag = frame.get("peak_hour_flag", pd.Series([0])).iloc[0]
    is_weekend = frame.get("is_weekend", pd.Series([0])).iloc[0]
    event_freq = frame.get("safe_corridor_event_frequency", pd.Series([0])).iloc[0]
    avg_sev = frame.get("safe_corridor_avg_severity", pd.Series([0])).iloc[0]

    freq_penalty = min(10.0, (float(event_freq) / 100.0) * 10.0)
    sev_penalty = min(10.0, float(avg_sev) * 5.0)
    temporal_penalty = 10.0 if peak_flag else (5.0 if is_weekend else 0.0)

    risk_index = min(100.0, base_risk + freq_penalty + sev_penalty + temporal_penalty)

    lead_time_map = {"Low": 1.0, "Medium": 2.0, "High": 4.0, "Critical": 12.0}
    lead_time = lead_time_map.get(tier, 1.0)
    if req.expected_duration_hours > 4:
        lead_time += 1.0

    elapsed_ms = round((time.monotonic() - t0) * 1000)

    audit_logger.log("plan_event_risk", {
        "lat": req.lat,
        "lon": req.lon,
        "event_type": req.event_type,
        "corridor": req.corridor,
        "junction": req.junction,
        "zone": req.zone,
        "planned_date_time": req.planned_date_time,
        "expected_duration_hours": req.expected_duration_hours,
        "description": req.description,
        "pre_event_risk_index": round(risk_index, 1),
        "recommended_personnel": personnel,
        "recommended_barricades": barricades,
        "deployment_tier": tier,
        "deployment_lead_time_hours": lead_time,
        "base_risk": base_risk,
        "freq_penalty": round(freq_penalty, 2),
        "sev_penalty": round(sev_penalty, 2),
        "temporal_penalty": temporal_penalty,
        "peak_hour": bool(peak_flag),
        "is_weekend": bool(is_weekend),
        "response_time_ms": elapsed_ms,
    })

    return PlanEventResponse(
        pre_event_risk_index=round(risk_index, 1),
        recommended_personnel=personnel,
        recommended_barricades=barricades,
        deployment_tier=tier,
        deployment_lead_time_hours=lead_time
    )