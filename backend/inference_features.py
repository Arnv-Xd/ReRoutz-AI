"""
inference_features.py
=======================
ReRoutz AI — Stage 2c: real-time feature builder for ONE incoming event.

`preprocess.py` engineers features over a whole CSV batch: it fits a
DBSCAN clustering, fits a TF-IDF vectorizer, and computes groupby
aggregates across the entire file. None of that works for "a new incident
just got reported, score it now" -- there's no batch, and you can't refit
DBSCAN/TF-IDF on a single row.

This module reconstructs the same feature space for a single new event by
reusing the artifacts `prepare_deployment_dataset.py` already saved:

  - label_metadata.json's recommended_feature_columns -> exact column order
  - feature_metadata.json's label_encoders             -> category -> code
  - tfidf_vectorizer.joblib                            -> fitted TF-IDF (transform, not fit)
  - spatial_reference.json                             -> corridor/junction
                                                           representative points
                                                           + DBSCAN cluster centroids,
                                                           for nearest-neighbor lookups
  - entity_lookup.json                                 -> latest known
                                                           point-in-time historical
                                                           stats per corridor/junction/
                                                           cluster (falls back to
                                                           global stats for unseen ones)

Nothing here is fit on the fly -- everything is a lookup/transform against
artifacts produced once, offline, by the training pipeline. That's what
makes this safe to call inside an API request.
"""

from __future__ import annotations

import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import joblib
import numpy as np
import pandas as pd

PEAK_MORNING_HOURS = set(range(7, 12))
PEAK_EVENING_HOURS = set(range(17, 22))
KEYWORDS = {
    "contains_water": ["water", "waterlogging", "water_logging", "rain", "flood"],
    "contains_tree": ["tree", "branch"],
    "contains_accident": ["accident", "crash", "collision", "hit"],
    "contains_rally": ["rally", "protest", "procession", "public event", "public_event"],
    "contains_breakdown": ["breakdown", "vehicle_breakdown", "stalled"],
    "contains_pothole": ["pothole", "pot hole", "pot_hole", "pot_holes"],
    "contains_closure": ["closure", "closed", "blocked", "block"],
}
MAJOR_CORRIDOR_TOKENS = ["ring_road", "outer_ring", "tumkur", "hosur", "airport", "mysore", "bannerghatta"]


def standardize_text(value: Any) -> str:
    """Mirrors preprocess.py's standardize_text (English-only path -- run
    Kannada inputs through preprocess.py's normalize_kannada_text first if
    needed before calling this API)."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "unknown"
    text = str(value).strip().lower()
    if not text or text in {"null", "none", "nan"}:
        return "unknown"
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "unknown"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371.0088 * 2 * math.asin(math.sqrt(a))


class DeploymentFeatureBuilder:
    """Loads artifacts once at startup; call `.build(event)` per request."""

    def __init__(self, artifacts_dir: Path, feature_metadata_path: Path):
        artifacts_dir = Path(artifacts_dir)
        with open(artifacts_dir / "label_metadata.json", "r", encoding="utf-8") as f:
            self.label_metadata = json.load(f)
        with open(artifacts_dir / "spatial_reference.json", "r", encoding="utf-8") as f:
            self.spatial_reference = json.load(f)
        with open(artifacts_dir / "entity_lookup.json", "r", encoding="utf-8") as f:
            self.entity_lookup = json.load(f)
        with open(feature_metadata_path, "r", encoding="utf-8") as f:
            self.feature_metadata = json.load(f)
        with open(artifacts_dir / "feature_columns.json", "r", encoding="utf-8") as f:
            self.feature_columns: list[str] = json.load(f)

        self.tfidf_vectorizer = joblib.load(artifacts_dir / "tfidf_vectorizer.joblib")
        self.label_encoders: dict[str, dict[str, int]] = self.feature_metadata["label_encoders"]

        self.cluster_centroids = self.spatial_reference.get("location_cluster_centroids", [])
        self.cluster_eps_km = self.spatial_reference.get("location_cluster_eps_km", 1.6)
        self.corridor_points = self.spatial_reference.get("corridor", [])
        self.junction_points = self.spatial_reference.get("junction", [])
        self.major_corridor_set = self._major_corridor_lookup()

    def _major_corridor_lookup(self) -> set[str]:
        corridor_enc = self.label_encoders.get("corridor", {})
        majors = set()
        for corridor_name in corridor_enc:
            if any(token in corridor_name for token in MAJOR_CORRIDOR_TOKENS):
                majors.add(corridor_name)
        return majors

    # -- helpers -----------------------------------------------------------

    def _encode_category(self, column: str, raw_value: str) -> int:
        encoder = self.label_encoders.get(column, {})
        value = standardize_text(raw_value)
        if value in encoder:
            return encoder[value]
        if "unknown" in encoder:
            return encoder["unknown"]
        return 0

    def _nearest_distance(self, lat: float, lon: float, points: list[dict]) -> float:
        if not points:
            return 0.0
        return min(haversine_km(lat, lon, p["latitude"], p["longitude"]) for p in points)

    def _assign_cluster(self, lat: float, lon: float) -> int:
        if not self.cluster_centroids:
            return -1
        best_cluster, best_distance = -1, float("inf")
        for c in self.cluster_centroids:
            d = haversine_km(lat, lon, c["latitude"], c["longitude"])
            if d < best_distance:
                best_distance, best_cluster = d, int(c["location_cluster"])
        return best_cluster if best_distance <= self.cluster_eps_km else -1

    def _entity_stats(self, group_column: str, entity_value: Any) -> dict[str, float]:
        table = self.entity_lookup.get(group_column, {})
        key = str(entity_value)
        return table.get(key, self.entity_lookup["global_fallback"])

    # -- main entry point ----------------------------------------------------

    def build(self, event: dict[str, Any]) -> pd.DataFrame:
        """`event` keys (raw, human-entered values are fine):
        lat, lon, event_type, event_cause, priority, veh_type,
        requires_road_closure (bool/0/1), corridor, junction, zone,
        description (free text), start_datetime (ISO string, optional -> now)
        """
        lat = float(event["lat"])
        lon = float(event["lon"])
        start_dt = pd.to_datetime(event.get("start_datetime") or datetime.utcnow(), utc=True)

        corridor = standardize_text(event.get("corridor", "unknown"))
        junction = standardize_text(event.get("junction", "unknown"))
        zone = standardize_text(event.get("zone", "unknown"))
        event_type = standardize_text(event.get("event_type", "unplanned"))
        event_cause = standardize_text(event.get("event_cause", "others"))
        priority = standardize_text(event.get("priority", "unknown"))
        veh_type = standardize_text(event.get("veh_type", "others"))
        requires_closure = int(bool(event.get("requires_road_closure", 0)))
        description = str(event.get("description", "") or "")

        hour = start_dt.hour
        day_of_week = start_dt.dayofweek
        is_weekend = int(day_of_week in (5, 6))
        month = start_dt.month
        peak_hour_flag = int(hour in PEAK_MORNING_HOURS or hour in PEAK_EVENING_HOURS)
        is_night = int(hour in set(range(0, 6)) | {22, 23})
        is_holiday = int(event.get("is_holiday", 0))

        if hour <= 5 or hour == 24:
            event_window_code = 0
        elif hour <= 11:
            event_window_code = 1
        elif hour <= 16:
            event_window_code = 2
        elif hour <= 21:
            event_window_code = 3
        else:
            event_window_code = 4

        location_cluster = self._assign_cluster(lat, lon)
        dist_junction = self._nearest_distance(lat, lon, self.junction_points)
        dist_corridor = self._nearest_distance(lat, lon, self.corridor_points)
        is_major_corridor = int(corridor in self.major_corridor_set or any(t in corridor for t in MAJOR_CORRIDOR_TOKENS))
        event_path_distance_km = float(event.get("event_path_distance_km", 0.0))

        combined_text = f"{description} {event_cause}".lower()
        keyword_flags = {
            name: int(any(term in combined_text for term in terms))
            for name, terms in KEYWORDS.items()
        }

        # severity_encoded & affected_radius are themselves features the
        # personnel/barricade model trains on (see prepare_deployment_dataset.py) --
        # at inference time we re-derive them with the SAME formula preprocess.py
        # used, since the real outcome (actual duration) is not known yet for a
        # brand-new event.
        duration_estimate = float(event.get("expected_duration_minutes", 60.0))
        priority_high = int(priority == "high")
        duration_component = 2 if duration_estimate >= 180 else (1 if duration_estimate >= 60 else 0)
        severity_score = priority_high * 2 + requires_closure * 2 + duration_component + peak_hour_flag
        severity_encoded = 0 if severity_score <= 1 else (1 if severity_score <= 3 else 2)
        affected_radius = float(np.clip(
            0.25 + severity_encoded * 0.35 + requires_closure * 0.5 + is_major_corridor * 0.3
            + min(event_path_distance_km, 2.0) * 0.2,
            0.25, 5.0,
        ))

        row: dict[str, Any] = {
            "hour": hour, "day_of_week": day_of_week, "is_weekend": is_weekend, "month": month,
            "peak_hour_flag": peak_hour_flag, "is_night": is_night, "is_holiday": is_holiday,
            "event_window_code": event_window_code,
            "distance_to_nearest_junction_km": dist_junction,
            "distance_to_nearest_corridor_km": dist_corridor,
            "is_major_corridor": is_major_corridor,
            "event_path_distance_km": event_path_distance_km,
            "requires_road_closure": requires_closure,
            "severity_encoded": severity_encoded,
            "affected_radius": affected_radius,
            **keyword_flags,
            "event_type_encoded": self._encode_category("event_type", event_type),
            "event_cause_encoded": self._encode_category("event_cause", event_cause),
            "priority_encoded": self._encode_category("priority", priority),
            "veh_type_encoded": self._encode_category("veh_type", veh_type),
            "corridor_encoded": self._encode_category("corridor", corridor),
            "junction_encoded": self._encode_category("junction", junction),
            "zone_encoded": self._encode_category("zone", zone),
        }

        for group_column, entity_value in [("corridor", corridor), ("junction", junction), ("location_cluster", location_cluster)]:
            stats = self._entity_stats(group_column, entity_value)
            row[f"safe_{group_column}_avg_duration"] = stats["avg_duration"]
            row[f"safe_{group_column}_avg_severity"] = stats["avg_severity"]
            row[f"safe_{group_column}_avg_impact"] = stats["avg_impact"]
            row[f"safe_{group_column}_event_frequency"] = stats["event_frequency"]
            row[f"safe_{group_column}_rolling_impact_30d"] = stats["rolling_impact_30d"]

        tfidf_matrix = self.tfidf_vectorizer.transform([combined_text]).toarray()[0]
        tfidf_names = [f"tfidf_safe_{n.replace(' ', '_')}" for n in self.tfidf_vectorizer.get_feature_names_out()]
        for name, value in zip(tfidf_names, tfidf_matrix):
            row[name] = float(value)

        frame = pd.DataFrame([row])
        for col in self.feature_columns:
            if col not in frame.columns:
                frame[col] = 0.0
        return frame[self.feature_columns], {
            "location_cluster": location_cluster,
            "severity_encoded": severity_encoded,
            "affected_radius": round(affected_radius, 3),
            "is_major_corridor": is_major_corridor,
        }
