.PHONY: preprocess prepare-deployment train-deployment pipeline backend frontend dev

preprocess:
	cd backend && python preprocess.py --input Data/Dataset.csv --output processed_data.csv --metadata feature_metadata.json

prepare-deployment:
	cd backend && python prepare_deployment_dataset.py --input processed_data.csv --metadata feature_metadata.json --output-dir model_artifacts

train-deployment:
	cd backend && python train_deployment_models.py --artifacts-dir model_artifacts

pipeline:
	cd backend && python preprocess.py --input Data/Dataset.csv --output processed_data.csv --metadata feature_metadata.json
	cd backend && python prepare_deployment_dataset.py --input processed_data.csv --metadata feature_metadata.json --output-dir model_artifacts
	cd backend && python train_deployment_models.py --artifacts-dir model_artifacts

backend:
	cd backend && uvicorn app_integrated:app --host 0.0.0.0 --port 8000 --reload

frontend:
	cd frontend && npm run dev -- --host 127.0.0.1 --port 5173 --strictPort

dev:
	(cd backend && uvicorn app_integrated:app --host 0.0.0.0 --port 8000 --reload) & (cd frontend && npm run dev -- --host 127.0.0.1 --port 5173 --strictPort) & wait
