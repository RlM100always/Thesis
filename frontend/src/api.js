// Thin fetch wrapper around the FastAPI backend.
// One place to change the base URL, one place that turns non-2xx into a
// thrown Error so every page can use the same loading/error handling.

import { authedFetch, clearTokens, getTokens, saveTokens } from "./auth";

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
  const res = await authedFetch(BASE, path, {
    method, headers, body: body === undefined ? undefined : JSON.stringify(body),
  });
  // The status rides on the error so screens can show the right Bangla message
  // (see errors.js) instead of the server's English text.
  if (!res.ok) throw Object.assign(new Error(await detailOf(res)), { status: res.status });
  return res.status === 204 ? null : res.json();
}

// A file upload plus form fields; the browser sets the multipart boundary itself.
async function formRequest(path, organizationId, fields, file) {
  const form = new FormData();
  for (const [key, value] of Object.entries(fields)) form.append(key, value);
  form.append("file", file);
  const res = await authedFetch(BASE, path, { method: "POST", headers: { "X-Organization-ID": organizationId }, body: form });
  if (!res.ok) throw Object.assign(new Error(await detailOf(res)), { status: res.status });
  return res.json();
}

// Sign-in calls need the HTTP status to show the right Bangla message, which
// detailOf() discards, so they get their own error shape.
async function authRequest(path, body) {
  const res = await authedFetch(BASE, path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw Object.assign(new Error(await detailOf(res)), { status: res.status });
  return res.json();
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

  // B-SMART Algorithm 1 (docs/BSMART_ARCHITECTURE.md).
  // Layer 5 is read-only research evidence; layers 9-10 write the owner's
  // decision and the observed outcome against a tenant's own recommendations.
  bsmartLatest: () => request("/api/research/bsmart/latest"),
  bsmartRecommendations: (org) =>
    appRequest("/api/app/bsmart/recommendations", { organizationId: org }),
  bsmartDecision: (org, id, body) =>
    appRequest(`/api/app/bsmart/recommendations/${encodeURIComponent(id)}/decision`,
      { method: "POST", body, organizationId: org }),
  bsmartOutcome: (org, id, body) =>
    appRequest(`/api/app/bsmart/recommendations/${encodeURIComponent(id)}/outcome`,
      { method: "POST", body, organizationId: org }),
  bsmartImportRun: (org) =>
    appRequest("/api/app/bsmart/import-run", { method: "POST", organizationId: org }),
  bsmartMonitoring: (org) =>
    appRequest("/api/app/bsmart/monitoring", { organizationId: org }),
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
  // Accounts (api/auth_routes.py). Tokens are stored by the client, not the caller.
  login: async (email, password) => {
    const session = await authRequest("/api/app/auth/login", { email, password });
    saveTokens(session);
    return session.user;
  },
  register: async (payload) => {
    const session = await authRequest("/api/app/auth/register", payload);
    saveTokens(session);
    return session.user;
  },
  logout: async () => {
    try {
      if (getTokens()) await appRequest("/api/app/auth/logout", { method: "POST" });
    } finally {
      clearTokens(); // signed out locally even if the server call failed
    }
  },
  setPassword: async (token, password) => {
    const session = await authRequest("/api/app/auth/set-password", { token, password });
    saveTokens(session);
    return session.user;
  },
  changePassword: async (currentPassword, newPassword) => {
    const session = await authRequest("/api/app/auth/change-password", {
      current_password: currentPassword, new_password: newPassword,
    });
    saveTokens(session); // other devices are signed out; this one continues
    return session.user;
  },
  audit: (org, { actions = "", cursor = "", limit = 30 } = {}) => {
    const query = new URLSearchParams({ limit: String(limit) });
    if (actions) query.set("actions", actions);
    if (cursor) query.set("cursor", cursor);
    return appRequest(`/api/app/audit?${query}`, { organizationId: org });
  },
  staff: (org) => appRequest("/api/app/staff", { organizationId: org }),
  inviteStaff: (org, body) => appRequest("/api/app/staff", { method: "POST", body, organizationId: org }),
  updateStaff: (org, membershipId, body) =>
    appRequest(`/api/app/staff/${encodeURIComponent(membershipId)}`, { method: "PATCH", body, organizationId: org }),
  staffSetupLink: (org, membershipId) =>
    appRequest(`/api/app/staff/${encodeURIComponent(membershipId)}/setup-link`, { method: "POST", organizationId: org }),
  me: () => appRequest("/api/app/auth/me"),
  permissions: (org) => appRequest("/api/app/auth/permissions", { organizationId: org }),

  appOrganizations: () => appRequest("/api/app/organizations"),
  createOrganization: (body) => appRequest("/api/app/organizations", { method: "POST", body }),
  branches: (org) => appRequest("/api/app/branches", { organizationId: org }),
  createBranch: (org, body) => appRequest("/api/app/branches", { method: "POST", body, organizationId: org }),
  productsApp: (org) => appRequest("/api/app/products?limit=500", { organizationId: org }),
  createProduct: (org, body) => appRequest("/api/app/products", { method: "POST", body, organizationId: org }),
  inventoryApp: (org, branch) => appRequest(`/api/app/inventory?branch_id=${encodeURIComponent(branch)}`, { organizationId: org }),
  brief: (org) => appRequest("/api/app/brief", { organizationId: org }),
  alerts: (org) => appRequest("/api/app/alerts", { organizationId: org }),
  cashDay: (org, branch, day = "") =>
    appRequest(`/api/app/cash/day?branch_id=${encodeURIComponent(branch)}${day ? `&day=${day}` : ""}`, { organizationId: org }),
  cashClose: (org, body) => appRequest("/api/app/cash/close", { method: "POST", body, organizationId: org }),
  cashCloses: (org, branch = "") =>
    appRequest(`/api/app/cash/closes${branch ? `?branch_id=${encodeURIComponent(branch)}` : ""}`, { organizationId: org }),
  customerSummary: (org, id) => appRequest(`/api/app/customers/${encodeURIComponent(id)}/summary`, { organizationId: org }),
  supplierStats: (org, id) => appRequest(`/api/app/suppliers/${encodeURIComponent(id)}/stats`, { organizationId: org }),
  transferStock: (org, body) => appRequest("/api/app/inventory/transfer", { method: "POST", body, organizationId: org }),
  salesSearch: (org, { branch = "", q = "", customer = "", from = "", to = "", limit = 100 } = {}) => {
    const query = new URLSearchParams({ limit: String(limit) });
    if (branch) query.set("branch_id", branch);
    if (q) query.set("q", q);
    if (customer) query.set("customer_id", customer);
    if (from) query.set("date_from", from);
    if (to) query.set("date_to", to);
    return appRequest(`/api/app/sales?${query}`, { organizationId: org });
  },
  enableExpiryTracking: (org, productId) =>
    appRequest(`/api/app/products/${encodeURIComponent(productId)}/track-expiry`, { method: "POST", organizationId: org }),
  batches: (org, branch, { state = "all", days = 90, productId = "" } = {}) =>
    appRequest(`/api/app/inventory/batches?branch_id=${encodeURIComponent(branch)}&state=${state}&days=${days}${productId ? `&product_id=${encodeURIComponent(productId)}` : ""}`, { organizationId: org }),
  expirySummary: (org, branch) =>
    appRequest(`/api/app/inventory/expiry-summary?branch_id=${encodeURIComponent(branch)}`, { organizationId: org }),
  setBatchStatus: (org, batchId, body) =>
    appRequest(`/api/app/inventory/batches/${encodeURIComponent(batchId)}/status`, { method: "POST", body, organizationId: org }),
  reconciliation: (org, branch) =>
    appRequest(`/api/app/inventory/reconciliation?branch_id=${encodeURIComponent(branch)}`, { organizationId: org }),
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
    const res = await authedFetch(BASE, "/api/app/imports", {
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
    const res = await authedFetch(BASE, "/api/app/datasets/sales.csv", {
      headers: { "X-Organization-ID": org },
    });
    if (!res.ok) throw new Error(await detailOf(res));
    return res.blob();
  },
  // Bulk intake of products / customers / opening stock (api/bulk_import_routes.py).
  importPreview: (org, kind, file) => formRequest("/api/app/import/preview", org, { kind }, file),
  importCommit: (org, kind, file, mapping, { mode = "skip_existing", branchId = "" } = {}) =>
    formRequest("/api/app/import/commit", org, { kind, mapping: JSON.stringify(mapping), mode, ...(branchId ? { branch_id: branchId } : {}) }, file),
  updateOrganization: (org, body) => appRequest("/api/app/organization", { method: "PATCH", body, organizationId: org }),
  reorderPlan: (org, branch, coverDays = 14) =>
    appRequest(`/api/app/reorder-plan?branch_id=${encodeURIComponent(branch)}&cover_days=${coverDays}`, { organizationId: org }),
  createPlanOrders: (org, body) => appRequest("/api/app/reorder-plan/orders", { method: "POST", body, organizationId: org }),
  updateProduct: (org, id, body) => appRequest(`/api/app/products/${encodeURIComponent(id)}`, { method: "PATCH", body, organizationId: org }),
  updateCustomer: (org, id, body) => appRequest(`/api/app/customers/${encodeURIComponent(id)}`, { method: "PATCH", body, organizationId: org }),
  voidSale: (org, id, body) => appRequest(`/api/app/sales/${encodeURIComponent(id)}/void`, { method: "POST", body, organizationId: org }),
  receivablesAgeing: (org) => appRequest("/api/app/receivables/ageing", { organizationId: org }),
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
