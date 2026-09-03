import { apiFetch } from "./client";

function buildParams({ start, end, sessionId, limit } = {}) {
  const qs = new URLSearchParams();
  if (start) qs.set("start", start);
  if (end) qs.set("end", end);
  if (sessionId) qs.set("session_id", sessionId);
  if (limit) qs.set("limit", String(limit));
  const str = qs.toString();
  return str ? `?${str}` : "";
}

export async function getMetricsSummary(params = {}) {
  const data = await apiFetch(`/metrics/summary${buildParams(params)}`, {
    method: "GET",
  });
  return data || {};
}

export async function getMetricsTimeseries(params = {}) {
  const data = await apiFetch(`/metrics/timeseries${buildParams(params)}`, {
    method: "GET",
  });
  return Array.isArray(data) ? data : [];
}

export async function getRecentMetrics(params = {}) {
  const data = await apiFetch(`/metrics/recent${buildParams(params)}`, {
    method: "GET",
  });
  return Array.isArray(data) ? data : [];
}

export async function getReactComparison(params = {}) {
  const data = await apiFetch(`/metrics/react${buildParams(params)}`, {
    method: "GET",
  });
  return data || {};
}
