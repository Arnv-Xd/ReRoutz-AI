"""
prepare_deployment_dataset.py
==============================
ReRoutz AI — Stage 2a: Manpower & Barricading dataset preparation.

WHY THIS FILE EXISTS
---------------------
`preprocess.py` (yours) gives us a rich, well-engineered feature table
(`processed_data.csv`) for *traffic-incident* modeling (severity, congestion
impact, affected radius). It does NOT contain any ground-truth label for
"how many police personnel were deployed" or "how many barricades were used"
-- the raw Astram dataset simply never recorded that. There is no column to
learn from for that target.

So this script does two honest things instead of pretending otherwise:

1.  WEAK-SUPERVISION LABELS
    It derives `recommended_personnel`, `recommended_barricades`, and
    `deployment_tier` from a transparent, documented formula built on real
    incident attributes (severity, road closure, corridor importance, crowd
    keywords, vehicle type, etc.), with injected variance so the label isn't
    a deterministic 1:1 function of the inputs. These are PROXY labels, not
    measured outcomes. `train_deployment_models.py` trains a real ML model
    against them so the model learns interaction patterns in the data
    instead of being a hardcoded lookup -- but the model is only as good as
    these proxy labels until real deployment logs exist.

    ACTION ITEM FOR YOU: if you can get even a rough spreadsheet of past
    events with actual personnel/barricade counts (from post-event police
    reports), replace `recommended_personnel` / `recommended_barricades`
    with that real column and skip the synthesis step. Everything downstream
    (training, serving) stays the same -- see label_metadata.json's
    "how_to_replace_with_real_labels" note.

2.  LEAKAGE-SAFE HISTORICAL FEATURES
    Your `preprocess.py` computes `*_historical_avg_*` and
    `*_rolling_impact_30d` using `groupby().agg()` / `.rolling()` over the
    WHOLE dataset, which includes each row's own future-knowledge (duration,
    impact) when computing "history" for that very row. That's fine for
    offline severity analysis, but it's a leak for a model meant to predict
    BEFORE an event's outcome is known. This script rebuilds those as
    expanding-window features computed strictly from events that happened
    BEFORE the current one (`.shift(1)` after sorting by time), prefixed
    `safe_*`. The deployment model trains on `safe_*` columns, never the
    original leaky ones.

USAGE
-----
    python prepare_deployment_dataset.py \\
        --input processed_data.csv \\
        --metadata feature_metadata.json \\
        --output-dir model_artifacts

Outputs (inside --output-dir):
    deployment_dataset.csv      -- processed_data.csv + safe_* features + targets
    label_metadata.json         -- documents the label formula & feature lists
    tfidf_vectorizer.joblib     -- refit, saved vectorizer (preprocess.py never saved its own)
    spatial_reference.json      -- corridor/junction representative points + cluster centroids
    entity_lookup.json          -- latest known safe-historical stats per corridor/junction/cluster
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

RANDOM_SEED = 42
GROUP_COLUMNS = ["corridor", "junction", "location_cluster"]
ADMIN_ID_COLUMNS = [
    "id", "map_file", "client_id", "created_by_id", "last_modified_by_id",
    "assigned_to_police_id", "citizen_accident_id", "kgid", "closed_by_id",
    "resolved_by_id", "gba_identifier", "veh_no", "resolved_at_address",
    "resolved_at_latitude", "resolved_at_longitude", "age_of_truck",
    "cargo_material", "reason_breakdown", "authenticated", "police_station",
    "direction",
]
HEAVY_VEHICLE_TYPES = {"heavy_vehicle", "ksrtc_bus", "bmtc_bus", "private_bus"}


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_dataset(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    if "start_datetime" not in df.columns:
        raise ValueError("processed_data.csv must contain 'start_datetime' (from preprocess.py).")
    df["start_datetime"] = pd.to_datetime(df["start_datetime"], errors="coerce", utc=True)
    df = df[df["start_datetime"].notna()].copy()
    df = df.sort_values("start_datetime").reset_index(drop=True)
    return df


def load_feature_metadata(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 1. Leakage-safe historical features (point-in-time, expanding + shift(1))
# ---------------------------------------------------------------------------

def add_safe_historical_features(df: pd.DataFrame) -> pd.DataFrame:
    """Rebuild historical aggregates using ONLY strictly-prior events.

    For every group column (corridor / junction / location_cluster), and for
    the dataset as a whole, compute an expanding mean/count that is shifted
    by one row so that the value for row i only reflects rows that happened
    strictly before row i (after sorting by start_datetime). This mirrors
    what would actually be knowable in real time when a new event comes in.
    """
    df = df.copy()
    df["_global_safe_avg_duration"] = (
        df["duration_minutes"].expanding().mean().shift(1)
    )
    df["_global_safe_avg_severity"] = (
        df["severity_encoded"].expanding().mean().shift(1)
    )
    df["_global_safe_avg_impact"] = (
        df["congestion_impact_score"].expanding().mean().shift(1)
    )
    global_fallback_duration = df["duration_minutes"].mean()
    global_fallback_severity = df["severity_encoded"].mean()
    global_fallback_impact = df["congestion_impact_score"].mean()

    df["_global_safe_avg_duration"] = df["_global_safe_avg_duration"].fillna(global_fallback_duration)
    df["_global_safe_avg_severity"] = df["_global_safe_avg_severity"].fillna(global_fallback_severity)
    df["_global_safe_avg_impact"] = df["_global_safe_avg_impact"].fillna(global_fallback_impact)

    for group_column in GROUP_COLUMNS:
        avg_duration_col = f"safe_{group_column}_avg_duration"
        avg_severity_col = f"safe_{group_column}_avg_severity"
        avg_impact_col = f"safe_{group_column}_avg_impact"
        freq_col = f"safe_{group_column}_event_frequency"
        rolling_col = f"safe_{group_column}_rolling_impact_30d"

        df[avg_duration_col] = global_fallback_duration
        df[avg_severity_col] = global_fallback_severity
        df[avg_impact_col] = global_fallback_impact
        df[freq_col] = 0.0
        df[rolling_col] = global_fallback_impact

        for _, group_index in df.groupby(group_column, sort=False).groups.items():
            ordered = df.loc[group_index].sort_values("start_datetime")
            idx = ordered.index

            exp_duration = ordered["duration_minutes"].expanding().mean().shift(1)
            exp_severity = ordered["severity_encoded"].expanding().mean().shift(1)
            exp_impact = ordered["congestion_impact_score"].expanding().mean().shift(1)
            exp_count = ordered["duration_minutes"].expanding().count().shift(1)

            rolling_impact = (
                pd.Series(
                    ordered["congestion_impact_score"].to_numpy(),
                    index=ordered["start_datetime"],
                )
                .shift(1)
                .rolling("30D", min_periods=1)
                .mean()
                .to_numpy()
            )

            df.loc[idx, avg_duration_col] = exp_duration.fillna(df.loc[idx, "_global_safe_avg_duration"]).to_numpy()
            df.loc[idx, avg_severity_col] = exp_severity.fillna(df.loc[idx, "_global_safe_avg_severity"]).to_numpy()
            df.loc[idx, avg_impact_col] = exp_impact.fillna(df.loc[idx, "_global_safe_avg_impact"]).to_numpy()
            df.loc[idx, freq_col] = exp_count.fillna(0).to_numpy()
            df.loc[idx, rolling_col] = pd.Series(rolling_impact, index=idx).fillna(
                df.loc[idx, "_global_safe_avg_impact"]
            ).to_numpy()

    return df.drop(columns=["_global_safe_avg_duration", "_global_safe_avg_severity", "_global_safe_avg_impact"])


# ---------------------------------------------------------------------------
# 2. TF-IDF refit (preprocess.py fit one but never saved it)
# ---------------------------------------------------------------------------

def refit_and_save_tfidf(df: pd.DataFrame, artifacts_dir: Path, max_features: int = 20) -> tuple[pd.DataFrame, list[str]]:
    text = (df.get("description", pd.Series("", index=df.index)).fillna("").astype(str)
            + " " + df.get("event_cause", pd.Series("", index=df.index)).fillna("").astype(str))

    vectorizer = TfidfVectorizer(max_features=max_features, min_df=2, ngram_range=(1, 2))
    matrix = vectorizer.fit_transform(text)
    names = [f"tfidf_safe_{name.replace(' ', '_')}" for name in vectorizer.get_feature_names_out()]
    tfidf_df = pd.DataFrame(matrix.toarray(), columns=names, index=df.index)

    joblib.dump(vectorizer, artifacts_dir / "tfidf_vectorizer.joblib")
    return pd.concat([df, tfidf_df], axis=1), names


# ---------------------------------------------------------------------------
# 3. Weak-supervision targets
# ---------------------------------------------------------------------------

def synthesize_deployment_targets(df: pd.DataFrame) -> pd.DataFrame:
    """Derive proxy manpower / barricade / tier labels.

    This is domain-formula weak supervision, NOT measured ground truth.
    See the module docstring and label_metadata.json for the rationale and
    for how to swap in real labels later.
    """
    df = df.copy()
    rng = np.random.default_rng(RANDOM_SEED)

    is_unplanned = (df.get("event_type", "unplanned") == "unplanned").astype(int)
    closure = df.get("requires_road_closure", 0).astype(int)
    major_corridor = df.get("is_major_corridor", 0).astype(int)
    peak_hour = df.get("peak_hour_flag", 0).astype(int)
    crowd_keyword = df.get("contains_rally", 0).astype(int)
    accident_keyword = df.get("contains_accident", 0).astype(int)
    severity = df.get("severity_encoded", 0).astype(int)
    affected_radius = df.get("affected_radius", 0.5).astype(float)
    is_planned = 1 - is_unplanned
    heavy_vehicle = df.get("veh_type", "").isin(HEAVY_VEHICLE_TYPES).astype(int)

    personnel_signal = (
        2
        + 3 * closure
        + 2 * major_corridor
        + 2 * peak_hour
        + 4 * accident_keyword * is_unplanned
        + 6 * crowd_keyword
        + 3 * heavy_vehicle
        + 2 * np.round(affected_radius)
        + 2 * severity
    )
    personnel_noise = rng.normal(0, 1.2, size=len(df))
    df["recommended_personnel"] = np.clip(
        np.round(personnel_signal + personnel_noise), 2, 40
    ).astype(int)

    barricade_signal = (
        2
        + 4 * np.round(affected_radius)
        + 4 * closure
        + 3 * major_corridor
        + 5 * crowd_keyword
        + 2 * is_planned
    )
    barricade_noise = rng.normal(0, 1.5, size=len(df))
    df["recommended_barricades"] = np.clip(
        np.round(barricade_signal + barricade_noise), 2, 60
    ).astype(int)

    risk_index = (
        2 * severity + 2 * closure + 2 * crowd_keyword + major_corridor + peak_hour
    )
    df["deployment_risk_index"] = risk_index
    try:
        df["deployment_tier"] = pd.qcut(
            risk_index.rank(method="first"), q=4, labels=["Low", "Medium", "High", "Critical"]
        ).astype(str)
    except ValueError:
        df["deployment_tier"] = pd.cut(
            risk_index, bins=[-1, 1, 3, 5, np.inf], labels=["Low", "Medium", "High", "Critical"]
        ).astype(str)

    return df


# ---------------------------------------------------------------------------
# 4. Spatial reference + entity lookup artifacts (used later at inference time)
# ---------------------------------------------------------------------------

def haversine_km(lat1, lon1, lat2, lon2) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371.0088 * 2 * math.asin(math.sqrt(a))


def build_spatial_reference(df: pd.DataFrame, min_events: int = 5) -> dict[str, Any]:
    reference: dict[str, Any] = {}
    for group_column in ["corridor", "junction"]:
        if group_column not in df.columns:
            continue
        points = (
            df[df[group_column] != "unknown"]
            .groupby(group_column)
            .agg(latitude=("latitude", "median"), longitude=("longitude", "median"), event_count=("start_datetime", "count"))
            .reset_index()
        )
        points = points[points["event_count"] >= min_events]
        reference[group_column] = points.to_dict(orient="records")

    if "location_cluster" in df.columns:
        centroids = (
            df[df["location_cluster"] != -1]
            .groupby("location_cluster")
            .agg(latitude=("latitude", "mean"), longitude=("longitude", "mean"), event_count=("start_datetime", "count"))
            .reset_index()
        )
        reference["location_cluster_centroids"] = centroids.to_dict(orient="records")
        # eps=0.015 degrees was the DBSCAN setting in preprocess.py; convert to
        # an approximate km radius at Bangalore's latitude for inference-time
        # nearest-centroid cluster assignment.
        reference["location_cluster_eps_km"] = 0.015 * 111.0

    return reference


def build_entity_lookup(df: pd.DataFrame) -> dict[str, Any]:
    """Snapshot the MOST RECENT safe-historical stats per entity, i.e. what
    you'd actually know "as of now" for a brand-new incoming event."""
    lookup: dict[str, Any] = {"global_fallback": {}}
    lookup["global_fallback"] = {
        "avg_duration": float(df["duration_minutes"].mean()),
        "avg_severity": float(df["severity_encoded"].mean()),
        "avg_impact": float(df["congestion_impact_score"].mean()),
        "event_frequency": float(df.groupby("corridor").size().mean()),
        "rolling_impact_30d": float(df["congestion_impact_score"].tail(200).mean()),
    }

    for group_column in GROUP_COLUMNS:
        latest = (
            df.sort_values("start_datetime")
            .groupby(group_column)
            .tail(1)
            .set_index(group_column)
        )
        cols = {
            "avg_duration": f"safe_{group_column}_avg_duration",
            "avg_severity": f"safe_{group_column}_avg_severity",
            "avg_impact": f"safe_{group_column}_avg_impact",
            "event_frequency": f"safe_{group_column}_event_frequency",
            "rolling_impact_30d": f"safe_{group_column}_rolling_impact_30d",
        }
        entity_map = {}
        for entity_value, row in latest.iterrows():
            entity_map[str(entity_value)] = {key: float(row[col]) for key, col in cols.items()}
        lookup[group_column] = entity_map

    return lookup


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def build_label_metadata(df: pd.DataFrame, tfidf_features: list[str], metadata: dict[str, Any]) -> dict[str, Any]:
    safe_historical_features = [
        f"safe_{group}_{suffix}"
        for group in GROUP_COLUMNS
        for suffix in ["avg_duration", "avg_severity", "avg_impact", "event_frequency", "rolling_impact_30d"]
    ]
    base_numeric = [
        "hour", "day_of_week", "is_weekend", "month", "peak_hour_flag", "is_night", "is_holiday",
        "event_window_code", "distance_to_nearest_junction_km", "distance_to_nearest_corridor_km",
        "is_major_corridor", "event_path_distance_km",
        "contains_water", "contains_tree", "contains_accident", "contains_rally",
        "contains_breakdown", "contains_pothole", "contains_closure",
        "event_type_encoded", "event_cause_encoded", "priority_encoded", "veh_type_encoded",
        "corridor_encoded", "junction_encoded", "zone_encoded", "requires_road_closure",
        "affected_radius", "severity_encoded",
    ]
    recommended_features = [c for c in base_numeric if c in df.columns] + safe_historical_features + tfidf_features

    return {
        "targets": {
            "recommended_personnel": "Proxy label (weak supervision). See module docstring.",
            "recommended_barricades": "Proxy label (weak supervision). See module docstring.",
            "deployment_tier": "Low/Medium/High/Critical, qcut of deployment_risk_index.",
        },
        "label_formula_summary": {
            "recommended_personnel": "2 base + 3*closure + 2*major_corridor + 2*peak_hour "
                                      "+ 4*accident*unplanned + 6*crowd_keyword + 3*heavy_vehicle "
                                      "+ 2*round(affected_radius) + 2*severity_encoded + noise~N(0,1.2), clipped [2,40]",
            "recommended_barricades": "2 base + 4*round(affected_radius) + 4*closure + 3*major_corridor "
                                       "+ 5*crowd_keyword + 2*is_planned + noise~N(0,1.5), clipped [2,60]",
            "deployment_tier": "qcut of (2*severity + 2*closure + 2*crowd_keyword + major_corridor + peak_hour) into 4 bins",
        },
        "how_to_replace_with_real_labels": (
            "If real personnel/barricade counts ever become available (even partially), "
            "create a CSV with columns [id, recommended_personnel, recommended_barricades] "
            "and merge it onto deployment_dataset.csv on 'id', overwriting the synthetic "
            "columns for rows that have real data. Then re-run train_deployment_models.py "
            "unchanged -- it does not care whether labels are synthetic or real."
        ),
        "recommended_feature_columns": recommended_features,
        "excluded_admin_id_columns": ADMIN_ID_COLUMNS,
        "leaky_columns_not_to_use": [
            c for c in metadata.get("numeric_features", [])
            if "historical_avg" in c or "rolling_impact_30d" in c or c == "historical_impact_score"
        ],
        "tfidf_features": tfidf_features,
        "group_columns": GROUP_COLUMNS,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare deployment-model dataset & label metadata.")
    parser.add_argument("--input", type=Path, default=Path("processed_data.csv"))
    parser.add_argument("--metadata", type=Path, default=Path("feature_metadata.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("model_artifacts"))
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading {args.input} ...")
    df = load_dataset(args.input)
    metadata = load_feature_metadata(args.metadata)

    print("Building leakage-safe (point-in-time) historical features ...")
    df = add_safe_historical_features(df)

    print("Refitting & saving TF-IDF vectorizer ...")
    df, tfidf_features = refit_and_save_tfidf(df, args.output_dir)

    print("Synthesizing weak-supervision deployment targets ...")
    df = synthesize_deployment_targets(df)

    print("Building spatial reference & entity lookup artifacts for inference ...")
    spatial_reference = build_spatial_reference(df)
    entity_lookup = build_entity_lookup(df)

    output_csv = args.output_dir / "deployment_dataset.csv"
    df.to_csv(output_csv, index=False)

    label_metadata = build_label_metadata(df, tfidf_features, metadata)
    with open(args.output_dir / "label_metadata.json", "w", encoding="utf-8") as f:
        json.dump(label_metadata, f, indent=2)
    with open(args.output_dir / "spatial_reference.json", "w", encoding="utf-8") as f:
        json.dump(spatial_reference, f, indent=2)
    with open(args.output_dir / "entity_lookup.json", "w", encoding="utf-8") as f:
        json.dump(entity_lookup, f, indent=2)

    print("\nDone.")
    print(f"  {output_csv}  ({len(df)} rows, {len(df.columns)} columns)")
    print(f"  {args.output_dir / 'label_metadata.json'}")
    print(f"  {args.output_dir / 'spatial_reference.json'}")
    print(f"  {args.output_dir / 'entity_lookup.json'}")
    print(f"  {args.output_dir / 'tfidf_vectorizer.joblib'}")
    print("\nTarget distributions:")
    print(df["recommended_personnel"].describe().round(2).to_string())
    print(df["recommended_barricades"].describe().round(2).to_string())
    print(df["deployment_tier"].value_counts().to_string())


if __name__ == "__main__":
    main()
