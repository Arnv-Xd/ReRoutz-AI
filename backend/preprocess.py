"""
Preprocessing and feature engineering for ReRoutz AI.

This module ingests the Astram event dataset and creates a hackathon-ready
feature table for downstream severity, duration, impact, and routing models.

Default usage:
    python preprocess.py

Custom usage:
    python preprocess.py --input Data/Dataset.csv --output processed_data.csv

The ingestion layer intentionally accepts only the dataset path as input. All
other behavior is deterministic and self-contained, with no external routing or
geocoding APIs.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import LabelEncoder

try:
    import holidays
except ImportError:  # pragma: no cover - handled at runtime for demos
    holidays = None

try:
    from haversine import Unit, haversine
except ImportError:  # pragma: no cover - fallback keeps script usable
    Unit = None
    haversine = None


DEFAULT_INPUT = Path("Data/Dataset.csv")
DEFAULT_OUTPUT = Path("processed_data.csv")
DEFAULT_METADATA = Path("feature_metadata.json")
DATETIME_COLUMNS = [
    "start_datetime",
    "end_datetime",
    "modified_datetime",
    "created_date",
    "closed_datetime",
    "resolved_datetime",
]
TEXT_COLUMNS = [
    "event_type",
    "event_cause",
    "description",
    "corridor",
    "junction",
    "priority",
    "veh_type",
    "direction",
    "status",
    "police_station",
    "zone",
]
BOOLEAN_COLUMNS = ["requires_road_closure", "authenticated"]
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
KANNADA_CHAR_PATTERN = re.compile(r"[\u0C80-\u0CFF]")
KANNADA_TRAFFIC_GLOSSARY = {
    "ತಲುಪಲು": "to reach",
    "ರಸ್ತೆ": "road",
    "ಮುಖ್ಯ ರಸ್ತೆ": "main road",
    "ಅಡ್ಡ ರಸ್ತೆ": "cross road",
    "ಜಂಕ್ಷನ್": "junction",
    "ವೃತ್ತ": "circle",
    "ಸರ್ಕಲ್": "circle",
    "ಸಿಗ್ನಲ್": "signal",
    "ಸೇತುವೆ": "bridge",
    "ಫ್ಲೈಓವರ್": "flyover",
    "ಅಂಡರ್ ಪಾಸ್": "underpass",
    "ಬಳಿ": "near",
    "ಹತ್ತಿರ": "near",
    "ಕಡೆ": "towards",
    "ನಗರ": "nagar",
    "ಮಾರುಕಟ್ಟೆ": "market",
    "ಬಸ್ ನಿಲ್ದಾಣ": "bus stand",
    "ರೈಲು ನಿಲ್ದಾಣ": "railway station",
    "ದೇವಸ್ಥಾನ": "temple",
    "ಆಸ್ಪತ್ರೆ": "hospital",
    "ಶಾಲೆ": "school",
    "ಕಾಲೇಜು": "college",
    "ಪೊಲೀಸ್ ಠಾಣೆ": "police station",
}
KANNADA_INDEPENDENT_VOWELS = {
    "ಅ": "a",
    "ಆ": "aa",
    "ಇ": "i",
    "ಈ": "ii",
    "ಉ": "u",
    "ಊ": "uu",
    "ಋ": "ru",
    "ಎ": "e",
    "ಏ": "ee",
    "ಐ": "ai",
    "ಒ": "o",
    "ಓ": "oo",
    "ಔ": "au",
}
KANNADA_CONSONANTS = {
    "ಕ": "k",
    "ಖ": "kh",
    "ಗ": "g",
    "ಘ": "gh",
    "ಙ": "ng",
    "ಚ": "ch",
    "ಛ": "chh",
    "ಜ": "j",
    "ಝ": "jh",
    "ಞ": "ny",
    "ಟ": "t",
    "ಠ": "th",
    "ಡ": "d",
    "ಢ": "dh",
    "ಣ": "n",
    "ತ": "t",
    "ಥ": "th",
    "ದ": "d",
    "ಧ": "dh",
    "ನ": "n",
    "ಪ": "p",
    "ಫ": "ph",
    "ಬ": "b",
    "ಭ": "bh",
    "ಮ": "m",
    "ಯ": "y",
    "ರ": "r",
    "ಲ": "l",
    "ವ": "v",
    "ಶ": "sh",
    "ಷ": "sh",
    "ಸ": "s",
    "ಹ": "h",
    "ಳ": "l",
}
KANNADA_VOWEL_SIGNS = {
    "ಾ": "aa",
    "ಿ": "i",
    "ೀ": "ii",
    "ು": "u",
    "ೂ": "uu",
    "ೃ": "ru",
    "ೆ": "e",
    "ೇ": "ee",
    "ೈ": "ai",
    "ೊ": "o",
    "ೋ": "oo",
    "ೌ": "au",
}
KANNADA_DIACRITICS = {
    "ಂ": "m",
    "ಃ": "h",
}
KANNADA_DIGITS = {
    "೦": "0",
    "೧": "1",
    "೨": "2",
    "೩": "3",
    "೪": "4",
    "೫": "5",
    "೬": "6",
    "೭": "7",
    "೮": "8",
    "೯": "9",
}
KANNADA_VIRAMA = "್"


def load_data(dataset_path: Path) -> pd.DataFrame:
    """Load Astram CSV and parse known datetime-like columns."""
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")

    df = pd.read_csv(
        dataset_path,
        na_values=["NULL", "null", "None", "none", "", "nan", "NaN"],
        keep_default_na=True,
        low_memory=False,
    )

    for column in DATETIME_COLUMNS:
        if column in df.columns:
            df[column] = pd.to_datetime(df[column], errors="coerce", utc=True)

    return df


def transliterate_kannada_token(token: str) -> str:
    """Transliterate one Kannada token into Latin characters.

    This is a deterministic offline transliterator, not a cloud translation API.
    It keeps the pipeline self-contained while converting Kannada-script place
    names into English-friendly tokens for matching and ML features.
    """
    output: list[str] = []
    index = 0
    while index < len(token):
        char = token[index]

        if char in KANNADA_INDEPENDENT_VOWELS:
            output.append(KANNADA_INDEPENDENT_VOWELS[char])
            index += 1
            continue

        if char in KANNADA_DIGITS:
            output.append(KANNADA_DIGITS[char])
            index += 1
            continue

        if char in KANNADA_CONSONANTS:
            base = KANNADA_CONSONANTS[char]
            next_char = token[index + 1] if index + 1 < len(token) else ""
            if next_char == KANNADA_VIRAMA:
                output.append(base)
                index += 2
            elif next_char in KANNADA_VOWEL_SIGNS:
                output.append(base + KANNADA_VOWEL_SIGNS[next_char])
                index += 2
            else:
                output.append(base + "a")
                index += 1
            continue

        if char in KANNADA_VOWEL_SIGNS:
            output.append(KANNADA_VOWEL_SIGNS[char])
        elif char in KANNADA_DIACRITICS:
            output.append(KANNADA_DIACRITICS[char])
        elif char == KANNADA_VIRAMA:
            pass
        else:
            output.append(char)
        index += 1

    return "".join(output)


def normalize_kannada_text(text: str) -> str:
    """Convert Kannada script and common traffic words to English-friendly text."""
    if not KANNADA_CHAR_PATTERN.search(text):
        return text

    normalized = text
    for kannada_phrase, english_phrase in sorted(
        KANNADA_TRAFFIC_GLOSSARY.items(), key=lambda item: len(item[0]), reverse=True
    ):
        normalized = normalized.replace(kannada_phrase, f" {english_phrase} ")

    parts = re.split(r"(\s+)", normalized)
    converted_parts = [
        transliterate_kannada_token(part) if KANNADA_CHAR_PATTERN.search(part) else part
        for part in parts
    ]
    return "".join(converted_parts)


def normalize_mixed_language_value(value: Any) -> Any:
    """Normalize Kannada text in any raw string field while preserving nulls."""
    if pd.isna(value) or not isinstance(value, str):
        return value
    return normalize_kannada_text(value)


def standardize_text(value: Any) -> str:
    """Normalize text into lowercase, underscore-separated English-friendly tokens."""
    if pd.isna(value):
        return "unknown"
    text = normalize_mixed_language_value(str(value)).strip().lower()
    if not text or text in {"null", "none", "nan"}:
        return "unknown"
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "unknown"


def parse_boolean(value: Any) -> int:
    """Convert heterogeneous boolean values into 0/1 integers."""
    if pd.isna(value):
        return 0
    if isinstance(value, bool):
        return int(value)
    text = str(value).strip().lower()
    return int(text in {"true", "t", "yes", "y", "1"})


def clean_coordinates(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce coordinates and replace invalid end coordinates with start point."""
    for column in ["latitude", "longitude", "endlatitude", "endlongitude"]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")

    valid_start = (
        df["latitude"].between(-90, 90)
        & df["longitude"].between(-180, 180)
        & ~((df["latitude"] == 0) & (df["longitude"] == 0))
    )
    df = df.loc[valid_start].copy()

    invalid_end = (
        df["endlatitude"].isna()
        | df["endlongitude"].isna()
        | ~df["endlatitude"].between(-90, 90)
        | ~df["endlongitude"].between(-180, 180)
        | ((df["endlatitude"] == 0) & (df["endlongitude"] == 0))
    )
    df.loc[invalid_end, "endlatitude"] = df.loc[invalid_end, "latitude"]
    df.loc[invalid_end, "endlongitude"] = df.loc[invalid_end, "longitude"]
    return df


def initial_cleaning(df: pd.DataFrame) -> pd.DataFrame:
    """Clean text, booleans, coordinates, and missing event-end timestamps."""
    df = df.copy()
    df = clean_coordinates(df)

    object_columns = df.select_dtypes(include=["object", "string"]).columns
    for column in object_columns:
        df[column] = df[column].map(normalize_mixed_language_value)

    for column in TEXT_COLUMNS:
        if column in df.columns:
            df[column] = df[column].map(standardize_text)

    for column in BOOLEAN_COLUMNS:
        if column in df.columns:
            df[column] = df[column].map(parse_boolean).astype(int)

    df["junction"] = df.get("junction", pd.Series(index=df.index, dtype=object)).fillna("unknown")
    df["corridor"] = df.get("corridor", pd.Series(index=df.index, dtype=object)).fillna("unknown")
    df["description"] = df.get("description", pd.Series(index=df.index, dtype=object)).fillna("unknown")

    if "start_datetime" not in df.columns:
        df["start_datetime"] = pd.NaT
    fallback_start = df["start_datetime"].fillna(df.get("created_date")).fillna(df.get("modified_datetime"))
    df["start_datetime"] = fallback_start
    df = df[df["start_datetime"].notna()].copy()

    fallback_end = (
        df.get("end_datetime")
        .fillna(df.get("resolved_datetime"))
        .fillna(df.get("closed_datetime"))
        .fillna(df.get("modified_datetime"))
    )
    if "end_datetime" not in df.columns:
        df["end_datetime"] = fallback_end
    else:
        df["end_datetime"] = df["end_datetime"].fillna(fallback_end)

    # If the event is still active or no useful fallback exists, use a conservative
    # two-hour estimate. This keeps duration usable without leaking future data.
    missing_end = df["end_datetime"].isna() & df["start_datetime"].notna()
    df.loc[missing_end, "end_datetime"] = df.loc[missing_end, "start_datetime"] + pd.Timedelta(hours=2)

    invalid_order = df["end_datetime"].notna() & df["start_datetime"].notna() & (
        df["end_datetime"] < df["start_datetime"]
    )
    df.loc[invalid_order, "end_datetime"] = df.loc[invalid_order, "start_datetime"] + pd.Timedelta(minutes=30)
    return df


def engineer_temporal_features(df: pd.DataFrame) -> pd.DataFrame:
    """Create calendar, holiday, peak-hour, and event-window features."""
    df = df.copy()
    df["duration_minutes"] = (
        (df["end_datetime"] - df["start_datetime"]).dt.total_seconds() / 60.0
    ).clip(lower=1, upper=7 * 24 * 60)

    df["hour"] = df["start_datetime"].dt.hour.fillna(-1).astype(int)
    df["day_of_week"] = df["start_datetime"].dt.dayofweek.fillna(-1).astype(int)
    df["is_weekend"] = df["day_of_week"].isin([5, 6]).astype(int)
    df["month"] = df["start_datetime"].dt.month.fillna(-1).astype(int)
    df["peak_hour_flag"] = df["hour"].isin(PEAK_MORNING_HOURS | PEAK_EVENING_HOURS).astype(int)
    df["is_night"] = df["hour"].isin(list(range(0, 6)) + [22, 23]).astype(int)

    local_dates = df["start_datetime"].dt.tz_convert("Asia/Kolkata").dt.date
    if holidays is not None:
        india_holidays = holidays.country_holidays("IN", years=sorted(df["start_datetime"].dt.year.dropna().unique()))
        df["is_holiday"] = local_dates.isin(india_holidays).astype(int)
    else:
        warnings.warn("holidays package not installed; is_holiday set to 0.")
        df["is_holiday"] = 0

    df["event_window"] = pd.cut(
        df["hour"],
        bins=[-2, 5, 11, 16, 21, 24],
        labels=["late_night", "morning", "afternoon", "evening", "night"],
    ).astype(str)
    df["event_window_code"] = LabelEncoder().fit_transform(df["event_window"])
    return df


def distance_km(point_a: tuple[float, float], point_b: tuple[float, float]) -> float:
    """Return Haversine distance in kilometers, using package or local fallback."""
    if haversine is not None and Unit is not None:
        return float(haversine(point_a, point_b, unit=Unit.KILOMETERS))

    lat1, lon1 = map(math.radians, point_a)
    lat2, lon2 = map(math.radians, point_b)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    hav = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371.0088 * 2 * math.atan2(math.sqrt(hav), math.sqrt(1 - hav))


def representative_points(df: pd.DataFrame, group_column: str, min_events: int = 5) -> pd.DataFrame:
    """Get median lat/lon for frequent named spatial entities."""
    if group_column not in df.columns:
        return pd.DataFrame(columns=[group_column, "latitude", "longitude", "event_count"])
    grouped = (
        df[df[group_column] != "unknown"]
        .groupby(group_column)
        .agg(latitude=("latitude", "median"), longitude=("longitude", "median"), event_count=("id", "count"))
        .reset_index()
    )
    return grouped[grouped["event_count"] >= min_events].copy()


def nearest_distance_to_points(df: pd.DataFrame, points: pd.DataFrame) -> pd.Series:
    """Calculate distance from each event to the nearest representative point."""
    if points.empty:
        return pd.Series(np.nan, index=df.index)

    point_tuples = list(zip(points["latitude"], points["longitude"]))
    distances = []
    for latitude, longitude in zip(df["latitude"], df["longitude"]):
        distances.append(min(distance_km((latitude, longitude), point) for point in point_tuples))
    return pd.Series(distances, index=df.index)


def engineer_spatial_features(df: pd.DataFrame) -> pd.DataFrame:
    """Cluster event locations and add corridor/junction proximity features."""
    df = df.copy()
    coordinates = df[["latitude", "longitude"]].to_numpy()
    df["location_cluster"] = DBSCAN(eps=0.015, min_samples=3).fit_predict(coordinates)

    junction_points = representative_points(df, "junction")
    corridor_points = representative_points(df, "corridor")
    df["distance_to_nearest_junction_km"] = nearest_distance_to_points(df, junction_points)
    df["distance_to_nearest_corridor_km"] = nearest_distance_to_points(df, corridor_points)
    df["distance_to_nearest_junction_km"] = df["distance_to_nearest_junction_km"].fillna(
        df["distance_to_nearest_junction_km"].median()
    )
    df["distance_to_nearest_corridor_km"] = df["distance_to_nearest_corridor_km"].fillna(
        df["distance_to_nearest_corridor_km"].median()
    )

    corridor_frequency = df["corridor"].value_counts(normalize=True)
    frequent_corridors = corridor_frequency[corridor_frequency >= 0.02].index
    important_tokens = ["ring_road", "outer_ring", "tumkur", "hosur", "airport", "mysore", "bannerghatta"]
    df["is_major_corridor"] = (
        df["corridor"].isin(frequent_corridors)
        | df["corridor"].str.contains("|".join(important_tokens), regex=True, na=False)
    ).astype(int)

    df["event_path_distance_km"] = [
        distance_km((lat, lon), (end_lat, end_lon))
        for lat, lon, end_lat, end_lon in zip(
            df["latitude"], df["longitude"], df["endlatitude"], df["endlongitude"]
        )
    ]
    return df


def add_keyword_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add interpretable keyword flags from description and event cause."""
    df = df.copy()
    combined_text = (df["description"].fillna("") + " " + df["event_cause"].fillna("")).str.lower()
    for feature_name, terms in KEYWORDS.items():
        pattern = "|".join(re.escape(term) for term in terms)
        df[feature_name] = combined_text.str.contains(pattern, regex=True, na=False).astype(int)
    return df


def encode_categoricals(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, dict[str, int]]]:
    """Label encode core categorical fields for tree-based ML models."""
    df = df.copy()
    encoders: dict[str, dict[str, int]] = {}
    for column in ["event_type", "event_cause", "priority", "veh_type", "status", "corridor", "junction", "zone"]:
        if column in df.columns:
            encoded_column = f"{column}_encoded"
            encoder = LabelEncoder()
            df[encoded_column] = encoder.fit_transform(df[column].astype(str))
            encoders[column] = {
                label: int(code) for code, label in enumerate(encoder.classes_)
            }
    return df, encoders


def add_tfidf_features(df: pd.DataFrame, max_features: int = 20) -> tuple[pd.DataFrame, list[str]]:
    """Create compact TF-IDF features from event description text."""
    df = df.copy()
    text = (df["description"].fillna("") + " " + df["event_cause"].fillna("")).astype(str)
    if text.str.strip().eq("").all() or len(df) < 2:
        return df, []

    vectorizer = TfidfVectorizer(max_features=max_features, min_df=2, ngram_range=(1, 2))
    try:
        matrix = vectorizer.fit_transform(text)
    except ValueError:
        return df, []

    names = [f"tfidf_{standardize_text(name)}" for name in vectorizer.get_feature_names_out()]
    tfidf_df = pd.DataFrame(matrix.toarray(), columns=names, index=df.index)
    return pd.concat([df, tfidf_df], axis=1), names


def derive_targets(df: pd.DataFrame) -> pd.DataFrame:
    """Create severity, congestion impact score, and affected radius targets."""
    df = df.copy()
    priority_high = df["priority"].eq("high").astype(int)
    closure = df.get("requires_road_closure", 0)
    duration_component = np.select(
        [df["duration_minutes"] >= 180, df["duration_minutes"] >= 60],
        [2, 1],
        default=0,
    )

    raw_severity_score = priority_high * 2 + closure * 2 + duration_component + df["peak_hour_flag"]
    df["severity_score"] = raw_severity_score
    df["severity"] = pd.cut(
        raw_severity_score,
        bins=[-1, 1, 3, np.inf],
        labels=["Low", "Medium", "High"],
    ).astype(str)
    df["severity_encoded"] = df["severity"].map({"Low": 0, "Medium": 1, "High": 2}).astype(int)

    duration_norm = np.minimum(df["duration_minutes"] / 240.0, 1.0)
    df["congestion_impact_score"] = (
        20
        + duration_norm * 30
        + df["severity_encoded"] * 15
        + closure * 15
        + df["peak_hour_flag"] * 10
        + df["is_major_corridor"] * 10
    ).clip(0, 100).round(2)

    df["affected_radius"] = (
        0.25
        + df["severity_encoded"] * 0.35
        + df["requires_road_closure"] * 0.5
        + df["is_major_corridor"] * 0.3
        + np.minimum(df["event_path_distance_km"], 2.0) * 0.2
    ).clip(0.25, 5.0).round(3)
    return df


def safe_group_stats(df: pd.DataFrame, group_column: str) -> pd.DataFrame:
    """Build historical aggregate stats for one entity column."""
    stats = (
        df.groupby(group_column)
        .agg(
            **{
                f"{group_column}_historical_avg_duration": ("duration_minutes", "mean"),
                f"{group_column}_historical_avg_severity": ("severity_encoded", "mean"),
                f"{group_column}_historical_event_frequency": ("id", "count"),
                f"{group_column}_historical_avg_impact": ("congestion_impact_score", "mean"),
            }
        )
        .reset_index()
    )
    return stats


def add_historical_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add aggregate and 30-day rolling historical impact features."""
    df = df.copy().sort_values("start_datetime")
    df["_row_id"] = np.arange(len(df))
    global_duration = df["duration_minutes"].mean()
    global_severity = df["severity_encoded"].mean()
    global_impact = df["congestion_impact_score"].mean()

    for group_column in ["corridor", "junction", "location_cluster"]:
        stats = safe_group_stats(df, group_column)
        df = df.merge(stats, on=group_column, how="left")
        df[f"{group_column}_historical_avg_duration"] = df[f"{group_column}_historical_avg_duration"].fillna(
            global_duration
        )
        df[f"{group_column}_historical_avg_severity"] = df[f"{group_column}_historical_avg_severity"].fillna(
            global_severity
        )
        df[f"{group_column}_historical_event_frequency"] = df[f"{group_column}_historical_event_frequency"].fillna(0)
        df[f"{group_column}_historical_avg_impact"] = df[f"{group_column}_historical_avg_impact"].fillna(global_impact)

    df = df.reset_index(drop=True)
    for group_column in ["corridor", "junction", "location_cluster"]:
        rolling_column = f"{group_column}_rolling_impact_30d"
        df[rolling_column] = global_impact
        for group_index in df.groupby(group_column, sort=False).groups.values():
            ordered = df.loc[group_index].sort_values("start_datetime")
            rolling_values = (
                pd.Series(
                    ordered["congestion_impact_score"].to_numpy(),
                    index=ordered["start_datetime"],
                )
                .rolling("30D", min_periods=1)
                .mean()
                .to_numpy()
            )
            df.loc[ordered.index, rolling_column] = rolling_values

    similar_groups = ["event_cause", "priority", "requires_road_closure"]
    df["historical_impact_score"] = (
        df.groupby(similar_groups)["congestion_impact_score"]
        .transform("mean")
        .fillna(global_impact)
        .round(2)
    )
    return df.drop(columns=["_row_id"])


def build_metadata(
    df: pd.DataFrame,
    encoders: dict[str, dict[str, int]],
    tfidf_features: list[str],
    output_path: Path,
) -> dict[str, Any]:
    """Create a compact feature registry for downstream modules."""
    target_columns = ["severity", "severity_encoded", "congestion_impact_score", "affected_radius", "duration_minutes"]
    datetime_columns = [column for column in DATETIME_COLUMNS if column in df.columns]
    excluded_columns = {
        "id",
        "address",
        "end_address",
        "description",
        "route_path",
        "meta_data",
        "comment",
        *datetime_columns,
        *target_columns,
    }
    feature_columns = [
        column
        for column in df.columns
        if column not in excluded_columns and not pd.api.types.is_datetime64_any_dtype(df[column])
    ]
    categorical_columns = [
        column for column in df.columns if df[column].dtype == "object" and column not in excluded_columns
    ]
    numeric_features = [
        column for column in feature_columns if pd.api.types.is_numeric_dtype(df[column])
    ]

    metadata = {
        "input_dataset": str(DEFAULT_INPUT),
        "output_dataset": str(output_path),
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "feature_columns": feature_columns,
        "numeric_features": numeric_features,
        "categorical_columns": categorical_columns,
        "target_columns": target_columns,
        "datetime_columns": datetime_columns,
        "tfidf_features": tfidf_features,
        "label_encoders": encoders,
        "notes": [
            "No external routing/geocoding APIs are used.",
            "Severity is rule-derived from priority, duration, closure, and peak-hour context.",
            "Historical features use in-dataset aggregates and 30-day rolling impact.",
        ],
    }
    return metadata


def print_summary(df: pd.DataFrame, metadata: dict[str, Any]) -> None:
    """Print concise run summary and feature importance hints."""
    print("\nReRoutz AI preprocessing complete")
    print("=" * 44)
    print(f"Rows: {len(df):,}")
    print(f"Columns: {len(df.columns):,}")
    print(f"Feature columns: {len(metadata['feature_columns']):,}")
    print("\nSeverity distribution:")
    print(df["severity"].value_counts(dropna=False).to_string())
    print("\nDuration summary (minutes):")
    print(df["duration_minutes"].describe(percentiles=[0.25, 0.5, 0.75, 0.9]).round(2).to_string())
    print("\nHigh-value feature hints for first ML models:")
    hints = [
        "historical_impact_score",
        "corridor_rolling_impact_30d",
        "location_cluster_historical_avg_impact",
        "duration_minutes",
        "requires_road_closure",
        "peak_hour_flag",
        "event_cause_encoded",
        "priority_encoded",
        "distance_to_nearest_junction_km",
        "is_major_corridor",
    ]
    print(", ".join(feature for feature in hints if feature in df.columns))


def fallback_path(path: Path) -> Path:
    """Create a timestamped fallback path next to a locked output file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return path.with_name(f"{path.stem}_{timestamp}{path.suffix}")


def write_csv_with_lock_fallback(df: pd.DataFrame, output_path: Path) -> Path:
    """Write CSV, falling back to a timestamped file if Windows locks the target."""
    try:
        df.to_csv(output_path, index=False)
        return output_path
    except PermissionError:
        alternate_path = fallback_path(output_path)
        warnings.warn(
            f"Could not write {output_path} because it is locked or open in another app. "
            f"Writing {alternate_path} instead."
        )
        df.to_csv(alternate_path, index=False)
        return alternate_path


def write_json_with_lock_fallback(metadata: dict[str, Any], metadata_path: Path) -> Path:
    """Write JSON metadata, falling back if the target metadata file is locked."""
    content = json.dumps(metadata, indent=2)
    try:
        metadata_path.write_text(content, encoding="utf-8")
        return metadata_path
    except PermissionError:
        alternate_path = fallback_path(metadata_path)
        warnings.warn(
            f"Could not write {metadata_path} because it is locked or open in another app. "
            f"Writing {alternate_path} instead."
        )
        alternate_path.write_text(content, encoding="utf-8")
        return alternate_path


def preprocess(dataset_path: Path = DEFAULT_INPUT, output_path: Path = DEFAULT_OUTPUT, metadata_path: Path = DEFAULT_METADATA) -> pd.DataFrame:
    """Run the complete preprocessing pipeline and write engineered outputs."""
    df = load_data(dataset_path)
    df = initial_cleaning(df)
    df = engineer_temporal_features(df)
    df = engineer_spatial_features(df)
    df = add_keyword_features(df)
    df, encoders = encode_categoricals(df)
    df, tfidf_features = add_tfidf_features(df)
    df = derive_targets(df)
    df = add_historical_features(df)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    actual_output_path = write_csv_with_lock_fallback(df, output_path)
    metadata = build_metadata(df, encoders, tfidf_features, actual_output_path)
    metadata["input_dataset"] = str(dataset_path)
    actual_metadata_path = write_json_with_lock_fallback(metadata, metadata_path)
    print_summary(df, metadata)
    print(f"\nSaved engineered data: {actual_output_path}")
    print(f"Saved metadata: {actual_metadata_path}")
    return df


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments while keeping dataset path as the only ingestion input."""
    parser = argparse.ArgumentParser(description="Preprocess Astram events for ReRoutz AI.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Path to Astram CSV dataset.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Path for engineered CSV output.")
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA, help="Path for feature metadata JSON.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    preprocess(args.input, args.output, args.metadata)
