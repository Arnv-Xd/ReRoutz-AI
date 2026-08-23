"""
train_deployment_models.py
===========================
ReRoutz AI — Stage 2b: train the manpower & barricading models.

Trains THREE real ML models (not lookup tables) against the proxy labels
produced by `prepare_deployment_dataset.py`:

    1. RandomForestRegressor  -> recommended_personnel
    2. RandomForestRegressor  -> recommended_barricades
    3. RandomForestClassifier -> deployment_tier (Low/Medium/High/Critical)

Why this satisfies "should actually learn, not just lookup":
  - The model is fit on a feature matrix (~70 engineered columns: temporal,
    spatial, categorical-encoded, keyword, TF-IDF, point-in-time historical
    aggregates) and learns nonlinear interactions between them via decision
    tree ensembles -- it is evaluated on a held-out TIME-BASED split (the
    most recent ~20% of events the model never saw during training), not a
    random split, so the reported metrics reflect genuine forecasting
    ability on unseen future events rather than memorized lookups.
  - Feature importances + permutation importance are reported so you can
    see which signals actually drive predictions (and sanity-check that the
    model isn't just keying off one column).

USAGE
-----
    python train_deployment_models.py --artifacts-dir model_artifacts

Outputs (inside --artifacts-dir):
    personnel_model.joblib
    barricade_model.joblib
    tier_model.joblib
    tier_label_encoder.joblib
    training_report.json       -- metrics, feature importances, CV scores
    feature_columns.json       -- exact column list/order the models expect
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)
from sklearn.model_selection import KFold, cross_val_score
from sklearn.preprocessing import LabelEncoder

RANDOM_SEED = 42
TEST_FRACTION = 0.2


def load_artifacts(artifacts_dir: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    df = pd.read_csv(artifacts_dir / "deployment_dataset.csv", low_memory=False)
    df["start_datetime"] = pd.to_datetime(df["start_datetime"], errors="coerce", utc=True)
    df = df.sort_values("start_datetime").reset_index(drop=True)
    with open(artifacts_dir / "label_metadata.json", "r", encoding="utf-8") as f:
        label_metadata = json.load(f)
    return df, label_metadata


def time_based_split(df: pd.DataFrame, test_fraction: float = TEST_FRACTION) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Hold out the most RECENT events as the test set -- mirrors how the
    model will actually be used (trained on history, scored on what comes
    next), and is a much harder/more honest test than a random split."""
    split_index = int(len(df) * (1 - test_fraction))
    return df.iloc[:split_index].copy(), df.iloc[split_index:].copy()


def select_feature_matrix(df: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
    available = [c for c in feature_columns if c in df.columns]
    missing = [c for c in feature_columns if c not in df.columns]
    if missing:
        print(f"  (note: {len(missing)} configured features not found in this dataset, skipping: {missing[:5]}...)")
    X = df[available].copy()
    for col in X.columns:
        X[col] = pd.to_numeric(X[col], errors="coerce")
    X = X.fillna(X.median(numeric_only=True)).fillna(0)
    return X, available


def train_regressor(X_train, y_train, X_test, y_test, label: str) -> tuple[RandomForestRegressor, dict[str, Any]]:
    model = RandomForestRegressor(
        n_estimators=300,
        max_depth=14,
        min_samples_leaf=3,
        n_jobs=-1,
        random_state=RANDOM_SEED,
    )
    model.fit(X_train, y_train)

    cv_scores = cross_val_score(
        model, X_train, y_train, cv=KFold(5, shuffle=True, random_state=RANDOM_SEED),
        scoring="neg_mean_absolute_error", n_jobs=-1,
    )

    predictions = model.predict(X_test)
    report = {
        "test_mae": float(mean_absolute_error(y_test, predictions)),
        "test_rmse": float(np.sqrt(mean_squared_error(y_test, predictions))),
        "test_r2": float(r2_score(y_test, predictions)),
        "cv_mae_mean": float(-cv_scores.mean()),
        "cv_mae_std": float(cv_scores.std()),
        "target_mean": float(y_train.mean()),
        "target_std": float(y_train.std()),
    }
    print(f"  [{label}] test MAE={report['test_mae']:.2f}  RMSE={report['test_rmse']:.2f}  "
          f"R2={report['test_r2']:.3f}  (5-fold CV MAE={report['cv_mae_mean']:.2f} ± {report['cv_mae_std']:.2f})")
    return model, report


def train_classifier(X_train, y_train, X_test, y_test, label: str) -> tuple[RandomForestClassifier, LabelEncoder, dict[str, Any]]:
    encoder = LabelEncoder()
    y_train_enc = encoder.fit_transform(y_train)
    y_test_enc = encoder.transform(y_test)

    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=12,
        min_samples_leaf=3,
        class_weight="balanced",
        n_jobs=-1,
        random_state=RANDOM_SEED,
    )
    model.fit(X_train, y_train_enc)

    cv_scores = cross_val_score(
        model, X_train, y_train_enc, cv=KFold(5, shuffle=True, random_state=RANDOM_SEED),
        scoring="f1_macro", n_jobs=-1,
    )

    predictions = model.predict(X_test)
    report = {
        "test_accuracy": float(accuracy_score(y_test_enc, predictions)),
        "test_f1_macro": float(f1_score(y_test_enc, predictions, average="macro")),
        "cv_f1_macro_mean": float(cv_scores.mean()),
        "cv_f1_macro_std": float(cv_scores.std()),
        "classes": list(encoder.classes_),
        "classification_report": classification_report(
            y_test_enc, predictions, target_names=[str(c) for c in encoder.classes_], output_dict=True
        ),
    }
    print(f"  [{label}] test accuracy={report['test_accuracy']:.3f}  macro-F1={report['test_f1_macro']:.3f}  "
          f"(5-fold CV macro-F1={report['cv_f1_macro_mean']:.3f} ± {report['cv_f1_macro_std']:.3f})")
    return model, encoder, report


def feature_importance_table(model, feature_names: list[str], X_test, y_test, top_n: int = 15) -> list[dict[str, Any]]:
    builtin = dict(zip(feature_names, model.feature_importances_))
    perm = permutation_importance(
        model, X_test, y_test, n_repeats=8, random_state=RANDOM_SEED, n_jobs=-1
    )
    perm_means = dict(zip(feature_names, perm.importances_mean))

    rows = [
        {"feature": name, "builtin_importance": float(builtin[name]), "permutation_importance": float(perm_means[name])}
        for name in feature_names
    ]
    rows.sort(key=lambda r: r["permutation_importance"], reverse=True)
    return rows[:top_n]


def main() -> None:
    parser = argparse.ArgumentParser(description="Train manpower/barricade deployment models.")
    parser.add_argument("--artifacts-dir", type=Path, default=Path("model_artifacts"))
    args = parser.parse_args()

    print(f"Loading deployment dataset from {args.artifacts_dir} ...")
    df, label_metadata = load_artifacts(args.artifacts_dir)
    feature_columns = label_metadata["recommended_feature_columns"]

    train_df, test_df = time_based_split(df)
    print(f"Time-based split: {len(train_df)} train rows (older) / {len(test_df)} test rows (most recent)")

    X_train, used_features = select_feature_matrix(train_df, feature_columns)
    X_test, _ = select_feature_matrix(test_df, feature_columns)
    X_test = X_test[X_train.columns]  # enforce identical column order

    report: dict[str, Any] = {"feature_columns_used": used_features, "n_train": len(train_df), "n_test": len(test_df)}

    print("\nTraining personnel regressor ...")
    personnel_model, personnel_report = train_regressor(
        X_train, train_df["recommended_personnel"], X_test, test_df["recommended_personnel"], "personnel"
    )
    report["personnel_model"] = personnel_report
    report["personnel_model"]["top_features"] = feature_importance_table(
        personnel_model, used_features, X_test, test_df["recommended_personnel"]
    )

    print("\nTraining barricade regressor ...")
    barricade_model, barricade_report = train_regressor(
        X_train, train_df["recommended_barricades"], X_test, test_df["recommended_barricades"], "barricades"
    )
    report["barricade_model"] = barricade_report
    report["barricade_model"]["top_features"] = feature_importance_table(
        barricade_model, used_features, X_test, test_df["recommended_barricades"]
    )

    print("\nTraining deployment-tier classifier ...")
    tier_model, tier_encoder, tier_report = train_classifier(
        X_train, train_df["deployment_tier"], X_test, test_df["deployment_tier"], "tier"
    )
    report["tier_model"] = tier_report
    report["tier_model"]["top_features"] = feature_importance_table(
        tier_model, used_features, X_test, tier_encoder.transform(test_df["deployment_tier"])
    )

    joblib.dump(personnel_model, args.artifacts_dir / "personnel_model.joblib")
    joblib.dump(barricade_model, args.artifacts_dir / "barricade_model.joblib")
    joblib.dump(tier_model, args.artifacts_dir / "tier_model.joblib")
    joblib.dump(tier_encoder, args.artifacts_dir / "tier_label_encoder.joblib")
    with open(args.artifacts_dir / "feature_columns.json", "w", encoding="utf-8") as f:
        json.dump(used_features, f, indent=2)
    with open(args.artifacts_dir / "training_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\nSaved models + training_report.json to {args.artifacts_dir}/")
    print("\nTop personnel-model features (by permutation importance):")
    for row in report["personnel_model"]["top_features"][:8]:
        print(f"    {row['feature']:<45} {row['permutation_importance']:.4f}")


if __name__ == "__main__":
    main()
