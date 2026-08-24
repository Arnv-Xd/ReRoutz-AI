# 🚦 ReRoutz AI

### AI-Powered Dynamic Traffic Diversion & Operational Resource Dispatch Engine

An end-to-end intelligent urban traffic command platform that combines **graph-based diversion routing**, **multi-target ML resource prediction**, and **temporal incident telemetry** to mitigate congestion across complex metropolitan road networks.

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Core Capabilities](#-core-capabilities)
- [System Architecture](#-system-architecture)
- [Dashboard Modules](#-dashboard-modules)
- [API Reference](#-api-reference)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [How It Works](#-how-it-works)
- [Getting Started](#-getting-started)
- [License](#-license)

---

## 🎯 Overview

**ReRoutz AI** is built for urban traffic command centers, municipal authorities, and emergency response teams. It processes city-scale incident feeds (tested on Bengaluru's complex urban road topology), preprocesses raw events through a multi-stage ML pipeline, and serves an interactive real-time operations console where traffic controllers can:

1. **Visualize active incidents** across temporal and spatial dimensions.
2. **Compute dynamic diversion corridors** by severing damaged/choked road segments on a live OpenStreetMap (OSM) graph.
3. **Dispatch optimal resources** (personnel count, barricades, and response tier) using multi-output machine learning models.
4. **Evaluate historical congestion trends** through synchronized analytical telemetry.

The system utilizes an asynchronous **FastAPI** backend that maintains the complete geospatial graph in memory alongside serialized ML artifacts for sub-second, real-time routing decisions.

---

## 🔥 Core Capabilities

| Capability | Description |
| :--- | :--- |
| **In-Memory Graph Diversion** | Loads and maintains an urban drive-type network (~134k nodes, ~340k edges) via OSMnx. Dynamically severs blocked edges and calculates non-overlapping macro-flank bypass routes using Dijkstra/A*. |
| **ML Resource Deployment** | Trained ensemble models (RandomForest) predict required **Personnel Count**, **Barricade Allocation**, and **Operational Response Tier** (Tier 1–Tier 3) across 70+ engineered features. |
| **Point-to-Point Corridor Routing** | Computes incident-aware shortest paths between custom origin-destination pairs by actively routing traffic outside a bounding box of live incidents. |
| **Cluster-Wide Resource Aggregation** | Aggregates resource demands across all active incidents within an operator-controlled spatial radius (km) to generate unified emergency response manifests. |
| **NLP Event Classification** | TF-IDF vectorization and semantic mapping over raw incident descriptions and location context for real-time priority scoring. |
| **Multi-Incident Patrol Routing** | Solves the Travelling Salesman Problem (TSP) using a greedy Nearest-Neighbor heuristic refined with 2-Opt local search on the true road network. |
| **Planned Event Risk Indexing** | Calculates a 0–100 pre-event risk score and recommended deployment lead times for scheduled gatherings, VIP movements, and construction. |
| **Telemetry & Incident Analytics** | Real-time analytics engine providing time-series volume distributions, hotspot corridor rankings, cause breakdowns, and day×hour congestion heatmaps. |

---

## 🏗 System Architecture

```
                   ┌────────────────────────────────────────┐
                   │           React + Vite SPA              │
                   │    (Leaflet Map + Recharts Telemetry)   │
                   └───────────────────┬────────────────────┘
                                       │  HTTP / REST
                                       ▼
                   ┌────────────────────────────────────────┐
                   │          FastAPI Async Server           │
                   │       (Uvicorn / Dynamic Port)          │
                   └─────┬────────────────────────────┬──────┘
                         │                             │
         ┌───────────────┴──────────────┐   ┌──────────┴───────────────┐
         │    Graph Diversion Engine    │   │  ML Deployment Service   │
         ├──────────────────────────────┤   ├───────────────────────────┤
         │ • OSMnx In-Memory Graph      │   │ • 70+ Feature Pipeline    │
         │ • Edge Severance Engine      │   │ • TF-IDF NLP Vectorizer   │
         │ • Macro-Flank Depth Explorer │   │ • Personnel / Barricade   │
         │ • 2-Opt TSP Patrol Optimizer │   │   RandomForest Models     │
         └──────────────────────────────┘   └───────────────────────────┘
```

---

## 📊 Dashboard Modules

| # | Module | Description |
| :-: | :--- | :--- |
| **1** | **Live Operations Map** | Interactive Leaflet map displaying active incident clusters, diversion corridors, barricade drop zones, and dynamic patrol paths. |
| **2** | **Timeline Scrubber** | Temporal filter slider to replay historical traffic states and simulate live incident progression. |
| **3** | **Radius Control** | Adjustable spatial filter (0.5 km – 10 km) that scopes the diversion and deployment engine around focus coordinates. |
| **4** | **Point-to-Point Route Planner** | Origin-destination navigation tool that calculates optimal transit paths around real-time road closures. |
| **5** | **ML Deployment Predictor** | Outputs recommended on-ground personnel, physical barricades, urgency tier, and natural-language operational justification. |
| **6** | **Cluster Deployment Aggregator** | Area-wide resource rollup aggregating required logistics across multiple simultaneous grid incidents. |
| **7** | **Patrol Route Optimizer** | Solves multi-point route sequencing to minimize patrol vehicle transit times across active hotspots. |
| **8** | **Planned Event Assessment** | Computes risk index, recommended lead time, and resource buffer requirements for upcoming events. |
| **9** | **Manual Incident Injector** | Form-based input to inject live bottlenecks, roadwork, or unmapped blockages directly into the routing graph. |
| **10** | **Analytics & Telemetry Dashboard** | Visual charts showing incident distribution by severity, hotspot corridor metrics, and temporal congestion heatmaps. |

---

## 🔌 API Reference

### 1. Diversion & Routing Engines

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/get-dataset` | Fetches parsed incident entries with spatial coordinates. |
| `POST` | `/calculate-cluster-diversion` | Severs cluster edges on the OSM network and returns flank diversion routes for approaching traffic. |
| `POST` | `/calculate-route-diversion` | Computes a clean origin-to-destination path avoiding all active bottlenecks within the corridor. |
| `POST` | `/optimize-patrol-route` | Solves TSP across selected incident coordinates using Nearest-Neighbor + 2-Opt. |

### 2. ML Inference & Resource Dispatch

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/predict-deployment` | Predicts personnel, barricades, severity tier, and reasoning for a single incident. |
| `POST` | `/predict-deployment-cluster` | Computes area-level aggregated resource requirements for multi-point clusters. |
| `POST` | `/similar-incidents` | Performs TF-IDF cosine similarity search to retrieve top historical incident matches and their resolution data. |
| `POST` | `/plan-event` | Evaluates planned event risk (0–100 score), required lead times, and resource allocations. |

### 3. Analytics & Health Checks

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/analytics-summary` | Returns aggregated metrics, hourly distributions, corridor rankings, and incident breakdowns. |
| `GET` | `/health` | System liveness probe verifying graph memory state and loaded model artifacts. |

---

## 🛠 Tech Stack

### Frontend
- **Framework:** React 18 (Vite SPA)
- **Mapping & GIS:** Leaflet, React-Leaflet
- **Data Visualization:** Recharts
- **Styling:** TailwindCSS
- **Dynamic Config:** `VITE_API_URL` environment binding

### Backend
- **Framework:** FastAPI, Uvicorn, Pydantic
- **Graph Processing & Spatial Analytics:** OSMnx, NetworkX, GeoPandas, Haversine
- **Machine Learning & NLP:** Scikit-Learn (RandomForest, TF-IDF, LabelEncoders), Joblib, Pandas, NumPy

### Infrastructure
- Dockerized backend with dynamic port handling, ready for Railway / cloud platforms
- Vercel SPA hosting for the frontend

---

## 📁 Project Structure

```
ReRoutz-AI/
├── backend/
│   ├── Dockerfile                     # Containerization setup (Uvicorn on dynamic port)
│   ├── requirements.txt               # Backend Python dependencies
│   │
│   ├── app_integrated.py              # Main FastAPI server & routing endpoints
│   ├── routing_engine.py              # OSMnx graph management & diversion routing
│   ├── deployment_service.py          # ML resource dispatch & inference service
│   ├── analytics_service.py           # Historical aggregation & telemetry router
│   ├── inference_features.py          # 70+ feature transformation builder
│   │
│   ├── preprocess.py                  # Stage 1: Feature engineering & cleaning
│   ├── prepare_deployment_dataset.py  # Stage 2: Leakage-safe target extraction
│   ├── train_deployment_models.py     # Stage 3: Multi-model training pipeline
│   │
│   ├── Data/
│   │   ├── Dataset.csv                # Primary incident dataset
│   │   └── Live_Incidents.csv         # Streamed active incident feed
│   └── model_artifacts/               # Serialized models (.joblib) & feature maps (.json)
│
└── frontend/
    ├── package.json                   # React + Leaflet + Recharts dependencies
    ├── vite.config.js                 # Vite build & proxy settings
    ├── vercel.json                    # SPA URL rewrite configuration
    │
    └── src/
        ├── App.jsx                    # Root state & workflow coordinator
        ├── api/
        │   └── client.js              # Centralized dynamic API client
        └── components/
            ├── MapView.jsx            # Dynamic Leaflet operations map
            ├── TimelineScrubber.jsx   # Temporal incident slider
            ├── RadiusSlider.jsx       # Cluster radius controller
            ├── RoutePlannerPanel.jsx  # Point-to-Point A/B routing UI
            ├── DeploymentPanel.jsx    # Personnel & barricade dispatch display
            ├── AnalyticsPanel.jsx     # Recharts telemetry & heatmap dashboard
            ├── IncidentForm.jsx       # Live incident injection interface
            └── PlanEventForm.jsx      # Pre-event risk assessment panel
```

---

## ⚙️ How It Works

### 1. In-Memory Graph & Edge Severance

```
[Approaching Traffic] ────► [Approaching Node] ────X [Severed Incident Edge] X────► [Blocked Node]
                                    │
                                    └────► [Dijkstra Macro-Flank Recovery] ────► [Clear Corridor]
```

- At startup, the server initializes an OSMnx `MultiDiGraph` centered around the urban zone with calculated travel times on each edge.
- When an incident occurs, the engine locates the nearest graph node and edge keys, dynamically severing incoming and parallel edges.
- For each approaching road vector, Dijkstra shortest-path calculations identify non-blocked bypass routes. If the immediate adjacent node is within the dead zone, an iterative depth search (up to 5 intersections via ego graphs) determines viable exit corridors.
- For A→B routing, all active incidents within a padded bounding box are severed, then a single shortest path is computed between the user's clicked origin and destination.
- For multi-incident patrol routing, the engine computes a full distance matrix between all cluster incidents using single-source Dijkstra, solves TSP with greedy nearest-neighbor, then refines with 2-opt local search.

### 2. ML Resource Prediction

- Incoming incidents are transformed through `DeploymentFeatureBuilder` to generate 70+ spatial, temporal, and lexical features using saved metadata (label encoders, TF-IDF vectorizer, spatial reference points, entity lookup tables). No model is fit at inference time — everything is a lookup or transform.
- Pre-trained **RandomForest models** score the feature vector to output:
  1. **Deployment Tier:** Urgency ranking (Tier 1 – Tier 3).
  2. **Personnel:** Required traffic officers and field personnel.
  3. **Barricades:** Physical barricade units needed for isolation.
- A rule-based explanation builder synthesizes these predictions into an operational natural-language briefing for field commanders — e.g. *"A road closure increases both traffic-control staffing and barricade requirements"*, *"The incident is on a major corridor, increasing control points and diversion complexity."*

---

## 🚀 Getting Started

### Prerequisites

| Requirement | Minimum Version |
| :--- | :--- |
| Python | 3.11+ |
| Node.js | 18+ |
| Git LFS | For serialized model artifacts |

### 1. Clone & Setup Backend

```bash
# Clone the repository
git clone https://github.com/Arnav-Xd/reroutz-backend.git
cd reroutz-backend

# Initialize virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start the FastAPI engine
python app_integrated.py
```

Backend runs at `http://localhost:8000` (Interactive Swagger docs available at `/docs`).

### 2. Setup Frontend

```bash
# In a new terminal, navigate to frontend
cd frontend

# Install Node modules
npm install

# Start Vite dev server
npm run dev
```

Frontend runs at `http://localhost:5173`.

### 3. Run the ML Pipeline (first time only)

```bash
python preprocess.py
python prepare_deployment_dataset.py
python train_deployment_models.py
```

---
