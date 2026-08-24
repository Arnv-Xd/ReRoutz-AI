const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

async function request(path, options = {}) {
  const url = `${API_BASE_URL}${path}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });

  if (!response.ok) {
    let errorDetail = `Request failed with status ${response.status}`;
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || errJson.message || errorDetail;
    } catch {
      const rawText = await response.text();
      if (rawText) errorDetail = rawText;
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

export function getDataset() {
  return request("/get-dataset");
}

export function calculateClusterDiversion(payload) {
  return request("/calculate-cluster-diversion", {
    method: "POST",
    body: JSON.stringify({
      target: payload.target,
      active_cluster: payload.active_cluster,
    }),
  });
}

export function calculateRouteDiversion(payload) {
  return request("/calculate-route-diversion", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function predictDeployment(payload) {
  return request("/predict-deployment", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function predictDeploymentCluster(payload) {
  return request("/predict-deployment-cluster", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getAnalyticsSummary(startDate, endDate) {
  const params = new URLSearchParams();
  if (startDate) params.append("start_date", String(startDate));
  if (endDate) params.append("end_date", String(endDate));
  return request(`/analytics-summary?${params.toString()}`);
}

export function findSimilarIncidents(payload) {
  return request("/similar-incidents", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function planEvent(payload) {
  return request("/plan-event", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function optimizePatrolRoute(payload) {
  return request("/optimize-patrol-route", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getAuditLogs({ eventType, limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (eventType) params.append("event_type", eventType);
  return request(`/audit-logs?${params.toString()}`);
}

export function getAuditStats() {
  return request("/audit-logs/stats");
}

export const api = {
  getDataset,
  calculateClusterDiversion,
  calculateRouteDiversion,
  predictDeployment,
  predictDeploymentCluster,
  getAnalyticsSummary,
  findSimilarIncidents,
  planEvent,
  optimizePatrolRoute,
  getAuditLogs,
  getAuditStats,
};