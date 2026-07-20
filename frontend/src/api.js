// Thin fetch wrapper around the FastAPI backend.
// One place to change the base URL, one place that turns non-2xx into a
// thrown Error so every page can use the same loading/error handling.

const BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

async function request(path) {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail || detail;
    } catch {
      // response had no JSON body; keep the status text
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json();
}

async function post(path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
  return res.json();
}

export const api = {
  health: () => request("/health"),
  overview: () => request("/api/overview"),
  segments: () => request("/api/segments"),
  forecast: () => request("/api/forecast"),
  modelMetrics: () => request("/api/models/metrics"),
  customers: (q = "", page = 1, pageSize = 25) =>
    request(`/api/customers?q=${encodeURIComponent(q)}&page=${page}&page_size=${pageSize}`),
  customer: (id) => request(`/api/customers/${encodeURIComponent(id)}`),
  predictChurn: (features) => post("/api/predict/churn", { features }),
};

// Money is in BDT and runs to billions — plain toLocaleString is unreadable.
export function formatBDT(value) {
  if (value == null || Number.isNaN(value)) return "—";
  if (Math.abs(value) >= 1e9) return `৳${(value / 1e9).toFixed(2)}B`;
  if (Math.abs(value) >= 1e6) return `৳${(value / 1e6).toFixed(2)}M`;
  if (Math.abs(value) >= 1e3) return `৳${(value / 1e3).toFixed(1)}K`;
  return `৳${value.toFixed(0)}`;
}

export function formatPct(value, digits = 1) {
  if (value == null || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

export const SEGMENT_COLORS = {
  "Low-Engagement": "#64748B",
  "Moderate-Spender": "#0D1B2A",
  "High-Value": "#0A8754",
  "VIP-Platinum": "#F5A623",
};
