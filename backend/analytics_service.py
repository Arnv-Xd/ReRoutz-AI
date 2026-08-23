from fastapi import APIRouter
from typing import Optional
import pandas as pd
from pathlib import Path
import os
import json

router = APIRouter()

# Global DataFrame to hold the cached dataset to avoid reading it on every request
_df = None

def load_analytics_data():
    global _df
    if _df is None:
        dataset_path = Path("model_artifacts/deployment_dataset.csv")
        if not dataset_path.exists():
            # fallback if model_artifacts is not there
            dataset_path = Path("processed_data.csv")
        
        if dataset_path.exists():
            _df = pd.read_csv(dataset_path, low_memory=False)
            if 'start_datetime' in _df.columns:
                _df['parsed_start'] = pd.to_datetime(_df['start_datetime'], errors='coerce')
        else:
            _df = pd.DataFrame()

@router.get("/analytics-summary")
def get_analytics_summary(start_date: Optional[float] = None, end_date: Optional[float] = None):
    """
    Returns analytics based on the Simulation Time range [start_date, end_date].
    Expects timestamps (milliseconds).
    """
    load_analytics_data()

    if _df is None or _df.empty or start_date is None or end_date is None:
        return _empty_response(start_date, end_date)

    # Convert timestamps from frontend to datetime (frontend sends epoch in ms)
    start_dt = pd.to_datetime(start_date, unit='ms', utc=True).tz_localize(None)
    end_dt = pd.to_datetime(end_date, unit='ms', utc=True).tz_localize(None)

    # Ensure the dataframe column is tz-naive as well
    if _df['parsed_start'].dt.tz is not None:
        _df['parsed_start'] = _df['parsed_start'].dt.tz_localize(None)

    mask = (_df['parsed_start'] >= start_dt) & (_df['parsed_start'] <= end_dt)
    filtered = _df.loc[mask]

    if filtered.empty:
        return _empty_response(start_date, end_date)

    # 1. incident_volume_timeseries (bucketed by day)
    filtered = filtered.copy()
    filtered['date'] = filtered['parsed_start'].dt.strftime('%Y-%m-%d')
    volume_ts = filtered.groupby('date').size().reset_index(name='count').to_dict(orient='records')

    # 2. incident_type_breakdown
    cause_col = 'event_cause' if 'event_cause' in filtered.columns else 'event_type'
    if cause_col in filtered.columns:
        type_breakdown = filtered.groupby(cause_col).size().reset_index(name='count').sort_values('count', ascending=False).to_dict(orient='records')
    else:
        type_breakdown = []

    # 3. severity_tier_distribution
    tier_col = 'deployment_tier'
    if tier_col in filtered.columns:
        tier_dist = filtered.groupby(tier_col).size().reset_index(name='count').to_dict(orient='records')
    else:
        tier_dist = []

    # 4. top_hotspot_corridors
    corridor_col = 'corridor'
    if corridor_col in filtered.columns:
        # replace unknown or empty
        hotspots_df = filtered[~filtered[corridor_col].isin(['unknown', '', 'Non-corridor'])].copy()
        top_corridors = hotspots_df.groupby(corridor_col).size().reset_index(name='count').sort_values('count', ascending=False).head(8).to_dict(orient='records')
    else:
        top_corridors = []

    # 5. avg_personnel_barricades_trend
    has_personnel = 'recommended_personnel' in filtered.columns and 'recommended_barricades' in filtered.columns
    if has_personnel:
        avg_pb = filtered.groupby('date')[['recommended_personnel', 'recommended_barricades']].mean().reset_index().round(1)
        avg_pb_trend = avg_pb.to_dict(orient='records')
    else:
        avg_pb_trend = []

    # 6. temporal_pattern_heatmap (day_of_week x hour_of_day)
    filtered['day_of_week'] = filtered['parsed_start'].dt.day_name()
    filtered['hour'] = filtered['parsed_start'].dt.hour
    heatmap_data = filtered.groupby(['day_of_week', 'hour']).size().reset_index(name='count').to_dict(orient='records')

    return {
        "window_start": start_date,
        "window_end": end_date,
        "incident_count_in_window": len(filtered),
        "incident_volume_timeseries": volume_ts,
        "incident_type_breakdown": type_breakdown,
        "severity_tier_distribution": tier_dist,
        "top_hotspot_corridors": top_corridors,
        "avg_personnel_barricades_trend": avg_pb_trend,
        "temporal_pattern_heatmap": heatmap_data
    }

def _empty_response(start_date, end_date):
    return {
        "window_start": start_date,
        "window_end": end_date,
        "incident_count_in_window": 0,
        "incident_volume_timeseries": [],
        "incident_type_breakdown": [],
        "severity_tier_distribution": [],
        "top_hotspot_corridors": [],
        "avg_personnel_barricades_trend": [],
        "temporal_pattern_heatmap": []
    }
