#!/bin/sh
set -eu

if [ ! -f Data/Dataset.csv ]; then
    echo "Missing /app/Data/Dataset.csv. Put the dataset in backend/Data/ before starting Docker." >&2
    exit 1
fi

if [ ! -f model_artifacts/personnel_model.joblib ] \
    || [ ! -f model_artifacts/barricade_model.joblib ] \
    || [ ! -f model_artifacts/tier_model.joblib ] \
    || [ ! -f model_artifacts/tier_label_encoder.joblib ]; then
    echo "Model artifacts not found; running the first-time training pipeline..."
    python preprocess.py --input Data/Dataset.csv --output processed_data.csv --metadata feature_metadata.json
    python prepare_deployment_dataset.py --input processed_data.csv --metadata feature_metadata.json --output-dir model_artifacts
    python train_deployment_models.py --artifacts-dir model_artifacts
fi

exec uvicorn app_integrated:app --host 0.0.0.0 --port ${PORT:-8000}
