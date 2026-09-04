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
  if (!res.ok) throw new Error(await detailOf(res));
  return res.json();
}

async function appRequest(path, { method = "GET", body, organizationId } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (organizationId) headers["X-Organization-ID"] = organizationId;
  const res = await fetch(`${BASE}${path}`, {
    method, headers, body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await detailOf(res));
  return res.status === 204 ? null : res.json();
}

// The upload endpoints raise 400 with a human-readable `detail` written for a
// non-technical user ("No value in 'price' could be read as a number"). Surface
// that verbatim; a bare status code would waste it.
async function detailOf(res) {
  try {
    const body = await res.json();
    if (body?.detail) return typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
  } catch {
    // no JSON body
  }
  return `${res.status}: ${res.statusText}`;
}

export const api = {
  health: () => request("/health"),
  overview: () => request("/api/overview"),
  segments: () => request("/api/segments"),
  forecast: () => request("/api/forecast"),
  modelMetrics: () => request("/api/models/metrics"),
  realDataValidation: () => request("/api/research/real-data-validation"),
  customers: (q = "", page = 1, pageSize = 25) =>
    request(`/api/customers?q=${encodeURIComponent(q)}&page=${page}&page_size=${pageSize}`),
  customer: (id) => request(`/api/customers/${encodeURIComponent(id)}`),
  predictChurn: (features) => post("/api/predict/churn", { features }),
  predictSegment: (features) => post("/api/predict/segment", { features }),
  modelFeatures: (model) => request(`/api/features/${model}`),

  // Bring-your-own-data
  uploadFile: async (file) => {
    const form = new FormData();
    form.append("file", file);
    // No Content-Type header — the browser must set the multipart boundary.
    const res = await fetch(`${BASE}/api/upload`, { method: "POST", body: form });
    if (!res.ok) throw new Error(await detailOf(res));
    return res.json();
  },
  scoreUpload: (token, mapping) => post(`/api/upload/${token}/score`, mapping),
  uploadOverview: (token, mapping) => post(`/api/upload/${token}/overview`, mapping),
  uploadForecast: (token, mapping) => post(`/api/upload/${token}/forecast`, mapping),
  uploadSegments: (token, mapping) => post(`/api/upload/${token}/segments`, mapping),
  uploadProducts: (token, mapping) => post(`/api/upload/${token}/products`, mapping),
  trainUploadChurn: (token, mapping, horizon = 90) =>
    post(`/api/upload/${token}/train-churn?horizon=${horizon}`, mapping),
  exportUpload: async (token, mapping) => {
    const res = await fetch(`${BASE}/api/upload/${token}/export`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(mapping),
    });
    if (!res.ok) throw new Error(await detailOf(res));
    return res.blob();
  },

  // Operational thesis prototype. The backend supplies one local owner and
  // still enforces organization headers on every tenant-owned record.
  appOrganizations: () => appRequest("/api/app/organizations"),
  createOrganization: (body) => appRequest("/api/app/organizations", { method: "POST", body }),
  branches: (org) => appRequest("/api/app/branches", { organizationId: org }),
  createBranch: (org, body) => appRequest("/api/app/branches", { method: "POST", body, organizationId: org }),
  productsApp: (org) => appRequest("/api/app/products", { organizationId: org }),
  createProduct: (org, body) => appRequest("/api/app/products", { method: "POST", body, organizationId: org }),
  inventoryApp: (org, branch) => appRequest(`/api/app/inventory?branch_id=${encodeURIComponent(branch)}`, { organizationId: org }),
  adjustStock: (org, body) => appRequest("/api/app/inventory/adjust", { method: "POST", body, organizationId: org }),
  createSale: (org, body) => appRequest("/api/app/sales", { method: "POST", body, organizationId: org }),
  salesApp: (org, branch = "") => appRequest(`/api/app/sales${branch ? `?branch_id=${encodeURIComponent(branch)}` : ""}`, { organizationId: org }),
  customersApp: (org) => appRequest("/api/app/customers", { organizationId: org }),
  createCustomer: (org, body) => appRequest("/api/app/customers", { method: "POST", body, organizationId: org }),
  suppliers: (org) => appRequest("/api/app/suppliers", { organizationId: org }),
  createSupplier: (org, body) => appRequest("/api/app/suppliers", { method: "POST", body, organizationId: org }),
  purchases: (org, status = "") => appRequest(`/api/app/purchases${status ? `?status=${encodeURIComponent(status)}` : ""}`, { organizationId: org }),
  createPurchase: (org, body) => appRequest("/api/app/purchases", { method: "POST", body, organizationId: org }),
  receivePurchase: (org, id, body) => appRequest(`/api/app/purchases/${id}/receive`, { method: "POST", body, organizationId: org }),
  returns: (org) => appRequest("/api/app/returns", { organizationId: org }),
  createReturn: (org, sale, body) => appRequest(`/api/app/sales/${sale}/returns`, { method: "POST", body, organizationId: org }),
  createExpense: (org, body) => appRequest("/api/app/expenses", { method: "POST", body, organizationId: org }),
  expenses: (org) => appRequest("/api/app/expenses", { organizationId: org }),
  ledger: (org, type) => appRequest(`/api/app/ledger/${type}`, { organizationId: org }),
  paySupplier: (org, supplier, body) => appRequest(`/api/app/suppliers/${supplier}/payments`, { method: "POST", body, organizationId: org }),
  receiveCustomerPayment: (org, customer, body) => appRequest(`/api/app/customers/${customer}/payments`, { method: "POST", body, organizationId: org }),
  dashboardApp: (org, branch = "") => appRequest(`/api/app/dashboard${branch ? `?branch_id=${encodeURIComponent(branch)}` : ""}`, { organizationId: org }),
  recommendationsApp: (org, branch = "") => appRequest(`/api/app/recommendations${branch ? `?branch_id=${encodeURIComponent(branch)}` : ""}`, { organizationId: org }),

  // Durable real-data intake (api/data_import_routes.py) — feeds the org's own
  // sales history into the operational schema for provenance and, later,
  // ml/real_pipeline.py training. Distinct from uploadFile() above, which is a
  // one-off scoring pass against the thesis pickles and never touches the DB.
  importSalesFile: async (org, file, sourceSystem = "unknown") => {
    const form = new FormData();
    form.append("file", file);
    form.append("source_system", sourceSystem);
    const res = await fetch(`${BASE}/api/app/imports`, {
      method: "POST",
      headers: { "X-Organization-ID": org },
      body: form,
    });
    if (!res.ok) throw new Error(await detailOf(res));
    return res.json();
  },
  validateSalesImport: (org, batchId, mapping) =>
    appRequest(`/api/app/imports/${encodeURIComponent(batchId)}/validate-sales`, {
      method: "POST", body: mapping, organizationId: org,
    }),
  exportSalesDataset: async (org) => {
    const res = await fetch(`${BASE}/api/app/datasets/sales.csv`, {
      headers: { "X-Organization-ID": org },
    });
    if (!res.ok) throw new Error(await detailOf(res));
    return res.blob();
  },
  trainDemandModel: (org) =>
    appRequest("/api/app/train-demand-model", { method: "POST", organizationId: org }),
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
