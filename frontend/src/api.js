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

async function appRequest(path, { method = "GET", body, organizationId, formData } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (organizationId) headers["X-Organization-ID"] = organizationId;
  // formData: pass a FormData object directly (browser sets multipart boundary)
  const fetchBody = formData !== undefined ? formData
    : body !== undefined ? JSON.stringify(body)
    : undefined;
  const res = await authedFetch(BASE, path, {
    method, headers, body: fetchBody,
  });
  // The status rides on the error so screens can show the right Bangla message
  // (see errors.js) instead of the server's English text.
  if (!res.ok) throw Object.assign(new Error(await detailOf(res)), { status: res.status });
  return res.status === 204 ? null : res.json();
}

async function appDownload(path, filename) {
  const res = await authedFetch(BASE, path);
  if (!res.ok) throw Object.assign(new Error(await detailOf(res)), { status: res.status });
  const url = URL.createObjectURL(await res.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
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
  bangladeshReference: () => request("/api/reference/bangladesh"),
  health: () => request("/health"),
  overview: () => request("/api/overview"),
  segments: () => request("/api/segments"),
  forecast: () => request("/api/forecast"),
  modelMetrics: () => request("/api/models/metrics"),
  realDataValidation: () => request("/api/research/real-data-validation"),

  // Research Portal
  portalDatasets:    () => request("/api/research/portal/datasets"),
  portalSchema:      () => request("/api/research/portal/vertical-schema"),
  portalExperiments: () => request("/api/research/portal/experiments"),
  portalGetExp:      (id) => request(`/api/research/portal/experiments/${encodeURIComponent(id)}`),
  portalStatus:      (id) => request(`/api/research/portal/experiments/${encodeURIComponent(id)}/status`),
  portalCreateExp:   (body) => post("/api/research/portal/experiments", body),
  portalRunExp:      (id) => post(`/api/research/portal/experiments/${encodeURIComponent(id)}/run`, {}),
  portalDeleteExp:   (id) => fetch(`${BASE}/api/research/portal/experiments/${encodeURIComponent(id)}`, { method: "DELETE" }).then(r => r.json()),
  portalCompare:     (ids) => post("/api/research/portal/compare", { experiment_ids: ids }),
  portalUpload: (file) => {
    const fd = new FormData(); fd.append("file", file);
    return fetch(`${BASE}/api/research/portal/upload-dataset`, { method: "POST", body: fd }).then(r => r.json());
  },

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
  bsmartRunLive: (org) =>
    appRequest("/api/app/bsmart/run", { method: "POST", organizationId: org }),
  bsmartExplain: (org, id) =>
    appRequest(`/api/app/bsmart/recommendations/${encodeURIComponent(id)}/explain`, { organizationId: org }),

  bsmartMeasure: (org, id, windowDays = 30) =>
    appRequest(`/api/app/bsmart/recommendations/${encodeURIComponent(id)}/measure`,
      { method: "POST", body: { observation_window_days: windowDays }, organizationId: org }),

  platformOrganizations: () => appRequest("/api/platform/organizations"),
  platformOnboarding: () => appRequest("/api/platform/organizations/onboarding"),
  platformOrganization: (id) => appRequest(`/api/platform/organizations/${encodeURIComponent(id)}`),
  platformUpdateOrganization: (id, body) => appRequest(`/api/platform/organizations/${encodeURIComponent(id)}`, { method: "PATCH", body }),
  platformUpdateMembership: (orgId, membershipId, body) => appRequest(`/api/platform/organizations/${encodeURIComponent(orgId)}/members/${encodeURIComponent(membershipId)}`, { method: "PATCH", body }),
  platformSummary: () => appRequest("/api/platform/summary"),
  platformSystemHealth: () => appRequest("/api/platform/system-health"),
  platformIntegrationOperations: () => appRequest("/api/platform/integration-operations"),
  platformSecurity: () => appRequest("/api/platform/security"),
  platformFeatureRollout: () => appRequest("/api/platform/features"),
  platformSetFeatureRollout: (key, enabled, organizationIds = null) => appRequest(`/api/platform/features/${encodeURIComponent(key)}`, { method: "PATCH", body: { enabled, organization_ids: organizationIds } }),
  platformUsers: (q = "", filter = "all", page = 1, pageSize = 50) => {
    const params = new URLSearchParams({ filter, page: String(page), page_size: String(pageSize) });
    if (q) params.set("q", q);
    return appRequest(`/api/platform/users?${params.toString()}`);
  },
  platformUser: (id) => appRequest(`/api/platform/users/${encodeURIComponent(id)}`),
  platformRevokeUserSession: (userId, sessionId) => appRequest(`/api/platform/users/${encodeURIComponent(userId)}/sessions/${encodeURIComponent(sessionId)}/revoke`, { method: "POST" }),
  platformSetUserAccess: (id, active) => appRequest(`/api/platform/users/${encodeURIComponent(id)}/access`, { method: "PATCH", body: { active } }),
  platformAdministrators: () => appRequest("/api/platform/administrators"),
  platformSetAdministrator: (id, isPlatformAdmin) => appRequest(`/api/platform/administrators/${encodeURIComponent(id)}`, { method: "PATCH", body: { is_platform_admin: isPlatformAdmin } }),
  platformAnnouncements: () => appRequest("/api/platform/announcements"),
  platformSendAnnouncement: (body) => appRequest("/api/platform/announcements", { method: "POST", body }),
  platformSuspend: (id, reason) => appRequest(`/api/platform/organizations/${encodeURIComponent(id)}/suspend`, { method: "POST", body: { reason } }),
  platformUnsuspend: (id) => appRequest(`/api/platform/organizations/${encodeURIComponent(id)}/unsuspend`, { method: "POST" }),
  platformDeleteOrganization: (id) => appRequest(`/api/platform/organizations/${encodeURIComponent(id)}`, { method: "DELETE" }),
  platformSetFeatures: (id, flags) => appRequest(`/api/platform/organizations/${encodeURIComponent(id)}/features`, { method: "PATCH", body: { flags } }),
  platformImpersonate: async (orgId, userId) => {
    const session = await appRequest(`/api/platform/organizations/${encodeURIComponent(orgId)}/impersonate/${encodeURIComponent(userId)}`, { method: "POST" });
    saveTokens(session);
    return session.user;
  },
  platformSiteContent: () => appRequest("/api/platform/site-content"),
  platformSetSiteContent: (key, value) => appRequest(`/api/platform/site-content/${encodeURIComponent(key)}`, { method: "PUT", body: { value } }),
  platformResetSiteContent: (key) => appRequest(`/api/platform/site-content/${encodeURIComponent(key)}`, { method: "DELETE" }),
  publicSiteContent: () => request("/api/app/site-content"),
  platformAudit: (cursor = "", action = "") => {
    const params = new URLSearchParams();
    if (cursor) params.set("cursor", cursor);
    if (action) params.set("action", action);
    const query = params.toString();
    return appRequest(`/api/platform/audit${query ? `?${query}` : ""}`);
  },
  platformTrends: (days = 30) => appRequest(`/api/platform/trends?days=${days}`),
  platformStaleOrganizations: (inactiveDays = 14) => appRequest(`/api/platform/organizations/stale?inactive_days=${inactiveDays}`),
  platformBackups: () => appRequest("/api/platform/backups"),
  platformCreateBackup: () => appRequest("/api/platform/backups", { method: "POST" }),
  platformDownloadBackup: (filename) => appDownload(`/api/platform/backups/${encodeURIComponent(filename)}/download`, filename),
  platformDeleteBackup: (filename) => appRequest(`/api/platform/backups/${encodeURIComponent(filename)}`, { method: "DELETE" }),
  platformRestoreDrill: (filename) => appRequest(`/api/platform/backups/${encodeURIComponent(filename)}/restore-drill`, { method: "POST" }),
  platformConversations: () => appRequest("/api/platform/conversations"),
  platformGetConversation: (orgId) => appRequest(`/api/platform/conversations/${orgId}/messages`),
  platformSendMessage: (orgId, content, attachment_url, attachment_name, attachment_size) =>
    appRequest(`/api/platform/conversations/${orgId}/messages`, { method: "POST", body: { content: content || "", attachment_url, attachment_name, attachment_size } }),
  // Business side
  getAdminMessages: () => appRequest("/api/app/messages"),
  getAdminMessagesUnread: () => appRequest("/api/app/messages/unread-count"),
  replyToAdmin: (content, attachment_url, attachment_name, attachment_size) =>
    appRequest("/api/app/messages", { method: "POST", body: { content: content || "", attachment_url, attachment_name, attachment_size } }),
  uploadChatFile: (formData) => appRequest("/api/app/messages/upload", { method: "POST", formData }),
  platformUploadChatFile: (formData) => appRequest("/api/platform/messages/upload", { method: "POST", formData }),

  // ── Admin platform — all 50 capabilities ──────────────────────────────
  adminOverview: () => appRequest("/api/admin/overview"),
  adminSearch: (q) => appRequest(`/api/admin/search?q=${encodeURIComponent(q)}`),
  adminMissionQueue: (status = "open") => appRequest(`/api/admin/mission-queue?status=${status}`),
  adminGenerateMissionQueue: () => appRequest("/api/admin/mission-queue/generate", { method: "POST" }),
  adminCreateMissionItem: (body) => appRequest("/api/admin/mission-queue", { method: "POST", body }),
  adminUpdateMissionItem: (id, body) => appRequest(`/api/admin/mission-queue/${id}`, { method: "PATCH", body }),
  adminShiftHandovers: () => appRequest("/api/admin/shift-handovers"),
  adminCreateShiftHandover: (body) => appRequest("/api/admin/shift-handovers", { method: "POST", body }),
  adminAcknowledgeHandover: (id) => appRequest(`/api/admin/shift-handovers/${id}/acknowledge`, { method: "POST" }),
  adminDecisionJournal: () => appRequest("/api/admin/decision-journal"),
  adminCreateDecision: (body) => appRequest("/api/admin/decision-journal", { method: "POST", body }),
  adminTransitionTenantState: (orgId, body) => appRequest(`/api/admin/organizations/${orgId}/state-transition`, { method: "POST", body }),
  adminTenantStateHistory: (orgId) => appRequest(`/api/admin/organizations/${orgId}/state-history`),
  adminTenantHealthScore: (orgId) => appRequest(`/api/admin/organizations/${orgId}/health-score`),
  adminPlans: () => appRequest("/api/admin/plans"),
  adminCreatePlan: (body) => appRequest("/api/admin/plans", { method: "POST", body }),
  adminUpdatePlan: (id, body) => appRequest(`/api/admin/plans/${id}`, { method: "PATCH", body }),
  adminOrgSubscription: (orgId) => appRequest(`/api/admin/organizations/${orgId}/subscription`),
  adminAssignSubscription: (orgId, body) => appRequest(`/api/admin/organizations/${orgId}/subscription`, { method: "POST", body }),
  adminOrgOverrides: (orgId) => appRequest(`/api/admin/organizations/${orgId}/overrides`),
  adminAddOverride: (orgId, body) => appRequest(`/api/admin/organizations/${orgId}/overrides`, { method: "POST", body }),
  adminUsage: (month) => appRequest(`/api/admin/usage${month ? `?period_month=${month}` : ""}`),
  adminRecordUsage: (body) => appRequest("/api/admin/usage/events", { method: "POST", body }),
  adminBillingLedger: (orgId) => appRequest(`/api/admin/organizations/${orgId}/billing`),
  adminAddBillingEntry: (orgId, body) => appRequest(`/api/admin/organizations/${orgId}/billing`, { method: "POST", body }),
  adminReconciliation: (status) => appRequest(`/api/admin/reconciliation?status=${status}`),
  adminAddCollection: (body) => appRequest("/api/admin/reconciliation", { method: "POST", body }),
  adminMatchCollection: (id, body) => appRequest(`/api/admin/reconciliation/${id}/match`, { method: "POST", body }),
  adminSupportCases: (status) => appRequest(`/api/admin/support-cases?status=${status}`),
  adminCreateSupportCase: (body) => appRequest("/api/admin/support-cases", { method: "POST", body }),
  adminUpdateSupportCase: (id, body) => appRequest(`/api/admin/support-cases/${id}`, { method: "PATCH", body }),
  adminCaseEvents: (id) => appRequest(`/api/admin/support-cases/${id}/events`),
  adminSlaSummary: () => appRequest("/api/admin/support-cases/sla-summary"),
  adminSupportSessions: (activeOnly = true) => appRequest(`/api/admin/support-sessions?active_only=${activeOnly}`),
  adminCreateSupportSession: (body) => appRequest("/api/admin/support-sessions", { method: "POST", body }),
  adminEndSupportSession: (id) => appRequest(`/api/admin/support-sessions/${id}/end`, { method: "POST" }),
  adminComputeChurnRisk: () => appRequest("/api/admin/churn-risk/compute", { method: "POST" }),
  adminChurnRisk: (level) => appRequest(`/api/admin/churn-risk${level ? `?risk_level=${level}` : ""}`),
  adminSecurityAlerts: (status = "open") => appRequest(`/api/admin/security-alerts?status=${status}`),
  adminCreateAlert: (body) => appRequest("/api/admin/security-alerts", { method: "POST", body }),
  adminResolveAlert: (id, body) => appRequest(`/api/admin/security-alerts/${id}/resolve`, { method: "POST", body }),
  adminJitGrants: (activeOnly = true) => appRequest(`/api/admin/jit-access?active_only=${activeOnly}`),
  adminGrantJit: (body) => appRequest("/api/admin/jit-access", { method: "POST", body }),
  adminRevokeJit: (id) => appRequest(`/api/admin/jit-access/${id}`, { method: "DELETE" }),
  adminCertCycles: () => appRequest("/api/admin/access-certifications"),
  adminCreateCertCycle: (body) => appRequest("/api/admin/access-certifications", { method: "POST", body }),
  adminCertDecide: (cycleId, itemId, body) => appRequest(`/api/admin/access-certifications/${cycleId}/items/${itemId}/decide`, { method: "POST", body }),
  adminEmergencyContain: (body) => appRequest("/api/admin/emergency-containment", { method: "POST", body }),
  adminIncidents: (status = "open") => appRequest(`/api/admin/incidents?status=${status}`),
  adminCreateIncident: (body) => appRequest("/api/admin/incidents", { method: "POST", body }),
  adminUpdateIncident: (id, body) => appRequest(`/api/admin/incidents/${id}`, { method: "PATCH", body }),
  adminIncidentTimeline: (id) => appRequest(`/api/admin/incidents/${id}/timeline`),
  adminJobs: (status) => appRequest(`/api/admin/jobs?status=${status}`),
  adminEnqueueJob: (body) => appRequest("/api/admin/jobs", { method: "POST", body }),
  adminRetryJob: (id) => appRequest(`/api/admin/jobs/${id}/retry`, { method: "POST" }),
  adminRolloutConfigs: () => appRequest("/api/admin/rollout-configs"),
  adminCreateRollout: (body) => appRequest("/api/admin/rollout-configs", { method: "POST", body }),
  adminAdvanceRollout: (id, body) => appRequest(`/api/admin/rollout-configs/${id}/advance`, { method: "POST", body }),
  adminRollbackRollout: (id) => appRequest(`/api/admin/rollout-configs/${id}/rollback`, { method: "POST" }),
  adminConfigVersions: (key) => appRequest(`/api/admin/config-versions${key ? `?config_key=${key}` : ""}`),
  adminSaveConfig: (body) => appRequest("/api/admin/config-versions", { method: "POST", body }),
  adminProviderCredentials: () => appRequest("/api/admin/provider-credentials"),
  adminAddCredential: (body) => appRequest("/api/admin/provider-credentials", { method: "POST", body }),
  adminRotateCredential: (id) => appRequest(`/api/admin/provider-credentials/${id}/rotate`, { method: "POST" }),
  adminWebhooks: (status) => appRequest(`/api/admin/webhook-events?status=${status}`),
  adminReplayWebhook: (id) => appRequest(`/api/admin/webhook-events/${id}/replay`, { method: "POST" }),
  adminIntegrationCerts: (orgId) => appRequest(`/api/admin/organizations/${orgId}/integration-certifications`),
  adminUpdateIntegrationCert: (orgId, body) => appRequest(`/api/admin/organizations/${orgId}/integration-certifications`, { method: "POST", body }),
  adminDataInventory: () => appRequest("/api/admin/data-inventory"),
  adminAddDataInventory: (body) => appRequest("/api/admin/data-inventory", { method: "POST", body }),
  adminDataExports: (status) => appRequest(`/api/admin/data-exports${status ? `?status=${status}` : ""}`),
  adminCreateDataExport: (body) => appRequest("/api/admin/data-exports", { method: "POST", body }),
  adminCompleteDataExport: (id) => appRequest(`/api/admin/data-exports/${id}/complete`, { method: "POST" }),
  adminRetentionPolicies: () => appRequest("/api/admin/retention-policies"),
  adminUpsertRetentionPolicy: (body) => appRequest("/api/admin/retention-policies", { method: "POST", body }),
  adminPrivacyRequests: (status) => appRequest(`/api/admin/privacy-requests?status=${status || "pending"}`),
  adminCreatePrivacyRequest: (body) => appRequest("/api/admin/privacy-requests", { method: "POST", body }),
  adminUpdatePrivacyRequest: (id, body) => appRequest(`/api/admin/privacy-requests/${id}`, { method: "PATCH", body }),
  adminModelRegistry: () => appRequest("/api/admin/model-registry"),
  adminRegisterModel: (body) => appRequest("/api/admin/model-registry", { method: "POST", body }),
  adminAiBudgets: () => appRequest("/api/admin/ai-cost-budgets"),
  adminSetAiBudget: (body) => appRequest("/api/admin/ai-cost-budgets", { method: "POST", body }),
  adminModelOutcomes: (feature, vertical) => appRequest(`/api/admin/model-outcomes${feature ? `?feature=${feature}` : ""}${vertical ? `&vertical=${vertical}` : ""}`),
  adminRecordOutcome: (body) => appRequest("/api/admin/model-outcomes", { method: "POST", body }),
  adminKillSwitches: () => appRequest("/api/admin/ai-kill-switches"),
  adminSetKillSwitch: (body) => appRequest("/api/admin/ai-kill-switches", { method: "POST", body }),
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
  // Returns either { user } on success, or { mfa_required: true, mfa_token }
  // when the account has TOTP MFA on — tokens are never saved for that case,
  // only after the second step (verifyMfa) succeeds.
  login: async (email, password) => {
    const session = await authRequest("/api/app/auth/login", { email, password });
    if (session.mfa_required) return session;
    saveTokens(session);
    return session.user;
  },
  setupMfa: () => appRequest("/api/app/auth/mfa/setup", { method: "POST" }),
  enableMfa: (code) => appRequest("/api/app/auth/mfa/enable", { method: "POST", body: { code } }),
  disableMfa: (password) => appRequest("/api/app/auth/mfa/disable", { method: "POST", body: { password } }),
  sessions: () => appRequest("/api/app/auth/sessions"),
  revokeSession: (sessionId) => appRequest(`/api/app/auth/sessions/${encodeURIComponent(sessionId)}/revoke`, { method: "POST" }),
  verifyMfa: async (mfaToken, code) => {
    const session = await authRequest("/api/app/auth/mfa/verify", { mfa_token: mfaToken, code });
    saveTokens(session);
    return session.user;
  },
  register: async (payload) => {
    const session = await authRequest("/api/app/auth/register", payload);
    saveTokens(session);
    return session.user;
  },
  forgotPassword: async (email) => authRequest("/api/app/auth/forgot-password", { email }),
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
  askAssistant: (org, question) => appRequest("/api/app/assistant/ask", { method: "POST", body: { question }, organizationId: org }),
  teamMessages: (org, afterId) =>
    appRequest(`/api/app/team-chat/messages${afterId ? `?after_id=${encodeURIComponent(afterId)}` : ""}`, { organizationId: org }),
  postTeamMessage: (org, body, branchId) =>
    appRequest("/api/app/team-chat/messages", { method: "POST", body: { body, branch_id: branchId || null }, organizationId: org }),
  updateProfile: (patch) => appRequest("/api/app/auth/profile", { method: "PATCH", body: patch }),
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
  stockCounts: (org, branch, status = "") => appRequest(`/api/app/inventory/stock-counts?branch_id=${encodeURIComponent(branch)}${status ? `&status=${status}` : ""}`, { organizationId: org }),
  stockCount: (org, id) => appRequest(`/api/app/inventory/stock-counts/${id}`, { organizationId: org }),
  startStockCount: (org, body) => appRequest("/api/app/inventory/stock-counts", { method: "POST", body, organizationId: org }),
  enterStockCount: (org, countId, lineId, countedQty) => appRequest(`/api/app/inventory/stock-counts/${countId}/lines/${lineId}`, { method: "PATCH", body: { counted_qty: countedQty }, organizationId: org }),
  completeStockCount: (org, countId) => appRequest(`/api/app/inventory/stock-counts/${countId}/complete`, { method: "POST", body: {}, organizationId: org }),
  brief: (org) => appRequest("/api/app/brief", { organizationId: org }),
  alerts: (org) => appRequest("/api/app/alerts", { organizationId: org }),
  cashDay: (org, branch, day = "") =>
    appRequest(`/api/app/cash/day?branch_id=${encodeURIComponent(branch)}${day ? `&day=${day}` : ""}`, { organizationId: org }),
  cashClose: (org, body) => appRequest("/api/app/cash/close", { method: "POST", body, organizationId: org }),
  cashCloses: (org, branch = "") =>
    appRequest(`/api/app/cash/closes${branch ? `?branch_id=${encodeURIComponent(branch)}` : ""}`, { organizationId: org }),
  currentShift: (org, branch) => appRequest(`/api/app/shifts/current?branch_id=${encodeURIComponent(branch)}`, { organizationId: org }),
  openShift: (org, body) => appRequest("/api/app/shifts/open", { method: "POST", body, organizationId: org }),
  shiftMovement: (org, shiftId, body) => appRequest(`/api/app/shifts/${shiftId}/movements`, { method: "POST", body, organizationId: org }),
  closeShift: (org, shiftId, body) => appRequest(`/api/app/shifts/${shiftId}/close`, { method: "POST", body, organizationId: org }),
  shiftHistory: (org, branch = "") =>
    appRequest(`/api/app/shifts/history${branch ? `?branch_id=${encodeURIComponent(branch)}` : ""}`, { organizationId: org }),
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
  salesDocuments: (org, type = "", channel = "") => {
    const params = new URLSearchParams();
    if (type) params.set("document_type", type);
    if (channel) params.set("channel", channel);
    const qs = params.toString();
    return appRequest(`/api/app/sales-documents${qs ? `?${qs}` : ""}`, { organizationId: org });
  },
  createSalesDocument: (org, body) => appRequest("/api/app/sales-documents", { method: "POST", body, organizationId: org }),
  salesDocumentStatus: (org, id, status) => appRequest(`/api/app/sales-documents/${id}/status`, { method: "POST", body: { status }, organizationId: org }),
  convertQuote: (org, id, body) => appRequest(`/api/app/sales-documents/${id}/convert-to-order`, { method: "POST", body, organizationId: org }),
  invoiceSalesOrder: (org, id, body) => appRequest(`/api/app/sales-documents/${id}/invoice`, { method: "POST", body, organizationId: org }),
  // Public online-storefront checkout — no auth, no org header.
  publicCatalog: (orgId) => request(`/api/public/orders/${orgId}/products`),
  placePublicOrder: (orgId, body) => post(`/api/public/orders/${orgId}`, body),
  publicOrderStatus: (orgId, token) => request(`/api/public/orders/${orgId}/status/${token}`),
  getPublicStore: (orgId) => request(`/api/public/store/${orgId}`),
  // Store admin — tenant-scoped, JWT required.
  getStore: () => appRequest("/api/app/store"),
  createStore: (body) => appRequest("/api/app/store", { method: "POST", body }),
  updateStore: (body) => appRequest("/api/app/store", { method: "PATCH", body }),
  getStoreProducts: () => appRequest("/api/app/store/products"),
  updateStoreProduct: (productId, body) => appRequest(`/api/app/store/products/${productId}`, { method: "PUT", body }),
  getStoreOrders: (status) => appRequest(`/api/app/store/orders${status ? `?status=${status}` : ""}`),
  getStoreStats: () => appRequest("/api/app/store/stats"),
  changeOrderStatus: (orderId, status) => appRequest(`/api/app/sales-documents/${orderId}/status`, { method: "POST", body: { status } }),
  customersApp: (org) => appRequest("/api/app/customers", { organizationId: org }),
  createCustomer: (org, body) => appRequest("/api/app/customers", { method: "POST", body, organizationId: org }),
  suppliers: (org) => appRequest("/api/app/suppliers", { organizationId: org }),
  createSupplier: (org, body) => appRequest("/api/app/suppliers", { method: "POST", body, organizationId: org }),
  purchases: (org, status = "") => appRequest(`/api/app/purchases${status ? `?status=${encodeURIComponent(status)}` : ""}`, { organizationId: org }),
  createPurchase: (org, body) => appRequest("/api/app/purchases", { method: "POST", body, organizationId: org }),
  receivePurchase: (org, id, body) => appRequest(`/api/app/purchases/${id}/receive`, { method: "POST", body, organizationId: org }),
  purchaseReturns: (org, status = "") => appRequest(`/api/app/purchase-returns${status ? `?status=${encodeURIComponent(status)}` : ""}`, { organizationId: org }),
  createPurchaseReturn: (org, body) => appRequest("/api/app/purchase-returns", { method: "POST", body, organizationId: org }),
  dispatchPurchaseReturn: (org, id, body) => appRequest(`/api/app/purchase-returns/${id}/dispatch`, { method: "POST", body, organizationId: org }),
  creditPurchaseReturn: (org, id, body) => appRequest(`/api/app/purchase-returns/${id}/credit-note`, { method: "POST", body, organizationId: org }),
  rejectPurchaseReturn: (org, id, body) => appRequest(`/api/app/purchase-returns/${id}/reject`, { method: "POST", body, organizationId: org }),
  returns: (org) => appRequest("/api/app/returns", { organizationId: org }),
  createReturn: (org, sale, body) => appRequest(`/api/app/sales/${sale}/returns`, { method: "POST", body, organizationId: org }),
  createExpense: (org, body) => appRequest("/api/app/expenses", { method: "POST", body, organizationId: org }),
  approvals: (org, status = "pending") => appRequest(`/api/app/approvals?status=${status}`, { organizationId: org }),
  decideApproval: (org, id, decision, reason) => appRequest(`/api/app/approvals/${id}/${decision}`, { method: "POST", body: { reason: reason || null }, organizationId: org }),
  approvalRules: (org) => appRequest("/api/app/approvals/rules", { organizationId: org }),
  updateApprovalRule: (org, kind, body) => appRequest(`/api/app/approvals/rules/${kind}`, { method: "PATCH", body, organizationId: org }),
  expenses: (org) => appRequest("/api/app/expenses", { organizationId: org }),
  ledger: (org, type) => appRequest(`/api/app/ledger/${type}`, { organizationId: org }),
  paySupplier: (org, supplier, body) => appRequest(`/api/app/suppliers/${supplier}/payments`, { method: "POST", body, organizationId: org }),
  receiveCustomerPayment: (org, customer, body) => appRequest(`/api/app/customers/${customer}/payments`, { method: "POST", body, organizationId: org }),
  dashboardApp: (org, branch = "") => appRequest(`/api/app/dashboard${branch ? `?branch_id=${encodeURIComponent(branch)}` : ""}`, { organizationId: org }),
  trialBalance: (org, asOf = "") => appRequest(`/api/app/accounting/trial-balance${asOf ? `?as_of=${asOf}` : ""}`, { organizationId: org }),
  profitAndLoss: (org, dateFrom, dateTo) => appRequest(`/api/app/accounting/profit-and-loss?date_from=${dateFrom}&date_to=${dateTo}`, { organizationId: org }),
  cashLocked: (org) => appRequest("/api/app/insights/cash-locked", { organizationId: org }),
  abcXyz: (org, days = 90) => appRequest(`/api/app/insights/abc-xyz?days=${days}`, { organizationId: org }),
  priceWatch: (org, threshold = 0.05) => appRequest(`/api/app/insights/price-watch?threshold=${threshold}`, { organizationId: org }),
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
  updateOrganizationOperations: (org, body) => appRequest("/api/app/organization/operations", { method: "PATCH", body, organizationId: org }),
  reorderPlan: (org, branch, coverDays = 14) =>
    appRequest(`/api/app/reorder-plan?branch_id=${encodeURIComponent(branch)}&cover_days=${coverDays}`, { organizationId: org }),
  createPlanOrders: (org, body) => appRequest("/api/app/reorder-plan/orders", { method: "POST", body, organizationId: org }),
  updateProduct: (org, id, body) => appRequest(`/api/app/products/${encodeURIComponent(id)}`, { method: "PATCH", body, organizationId: org }),
  updateCustomer: (org, id, body) => appRequest(`/api/app/customers/${encodeURIComponent(id)}`, { method: "PATCH", body, organizationId: org }),
  voidSale: (org, id, body) => appRequest(`/api/app/sales/${encodeURIComponent(id)}/void`, { method: "POST", body, organizationId: org }),
  receivablesAgeing: (org) => appRequest("/api/app/receivables/ageing", { organizationId: org }),
  trainDemandModel: (org) =>
    appRequest("/api/app/train-demand-model", { method: "POST", organizationId: org }),

  loyaltyRule: (org) => appRequest("/api/app/loyalty/rule", { organizationId: org }),
  updateLoyaltyRule: (org, body) => appRequest("/api/app/loyalty/rule", { method: "PATCH", body, organizationId: org }),
  customerLoyalty: (org, customerId) =>
    appRequest(`/api/app/customers/${encodeURIComponent(customerId)}/loyalty`, { organizationId: org }),

  // Owner intelligence
  healthScore: (org) => appRequest("/api/app/health-score", { organizationId: org }),
  missionQueue: (org, limit = 20) => appRequest(`/api/app/mission-queue?limit=${limit}`, { organizationId: org }),
  riskExceptions: (org, days = 30) => appRequest(`/api/app/risk/exceptions?days=${days}`, { organizationId: org }),

  // In-app notifications (Notification Center)
  notifications: (org, unreadOnly = false) => appRequest(`/api/app/notifications${unreadOnly ? "?unread_only=true" : ""}`, { organizationId: org }),
  notificationsUnreadCount: (org) => appRequest("/api/app/notifications/unread-count", { organizationId: org }),
  markNotificationRead: (org, id) => appRequest(`/api/app/notifications/${encodeURIComponent(id)}/read`, { method: "POST", organizationId: org }),
  markAllNotificationsRead: (org) => appRequest("/api/app/notifications/read-all", { method: "POST", organizationId: org }),

  // Workforce: attendance, leave, roster, commission, targets, advances, payroll
  checkIn: (org, body = {}) => appRequest("/api/app/attendance/check-in", { method: "POST", body, organizationId: org }),
  checkOut: (org) => appRequest("/api/app/attendance/check-out", { method: "POST", body: {}, organizationId: org }),
  myAttendance: (org) => appRequest("/api/app/attendance/me", { organizationId: org }),
  teamAttendance: (org) => appRequest("/api/app/attendance", { organizationId: org }),
  correctAttendance: (org, body) => appRequest("/api/app/attendance/correct", { method: "POST", body, organizationId: org }),

  requestLeave: (org, body) => appRequest("/api/app/leave", { method: "POST", body, organizationId: org }),
  myLeave: (org) => appRequest("/api/app/leave/me", { organizationId: org }),
  teamLeave: (org, status = "") => appRequest(`/api/app/leave${status ? `?status=${status}` : ""}`, { organizationId: org }),
  decideLeave: (org, id, body) => appRequest(`/api/app/leave/${encodeURIComponent(id)}/decide`, { method: "POST", body, organizationId: org }),
  cancelLeave: (org, id) => appRequest(`/api/app/leave/${encodeURIComponent(id)}/cancel`, { method: "POST", body: {}, organizationId: org }),

  myRoster: (org, params = {}) => appRequest(`/api/app/roster/me${params.from_date ? `?from_date=${params.from_date}&to_date=${params.to_date}` : ""}`, { organizationId: org }),
  teamRoster: (org, branchId = "") => appRequest(`/api/app/roster${branchId ? `?branch_id=${branchId}` : ""}`, { organizationId: org }),
  createShift: (org, body) => appRequest("/api/app/roster", { method: "POST", body, organizationId: org }),
  deleteShift: (org, id) => appRequest(`/api/app/roster/${encodeURIComponent(id)}`, { method: "DELETE", organizationId: org }),

  commissionRule: (org) => appRequest("/api/app/commission/rule", { organizationId: org }),
  updateCommissionRule: (org, body) => appRequest("/api/app/commission/rule", { method: "PATCH", body, organizationId: org }),
  myCommission: (org) => appRequest("/api/app/commission/me", { organizationId: org }),
  teamCommission: (org) => appRequest("/api/app/commission", { organizationId: org }),

  myTargets: (org) => appRequest("/api/app/targets/me", { organizationId: org }),
  teamTargets: (org) => appRequest("/api/app/targets", { organizationId: org }),
  createTarget: (org, body) => appRequest("/api/app/targets", { method: "POST", body, organizationId: org }),

  myAdvances: (org) => appRequest("/api/app/advances/me", { organizationId: org }),
  teamAdvances: (org, status = "") => appRequest(`/api/app/advances${status ? `?status=${status}` : ""}`, { organizationId: org }),
  issueAdvance: (org, body) => appRequest("/api/app/advances", { method: "POST", body, organizationId: org }),
  repayAdvance: (org, id, body) => appRequest(`/api/app/advances/${encodeURIComponent(id)}/repay`, { method: "POST", body, organizationId: org }),

  setBaseSalary: (org, membershipId, body) => appRequest(`/api/app/payroll/salary/${encodeURIComponent(membershipId)}`, { method: "PATCH", body, organizationId: org }),
  payrollRuns: (org) => appRequest("/api/app/payroll/runs", { organizationId: org }),
  payrollRun: (org, id) => appRequest(`/api/app/payroll/runs/${encodeURIComponent(id)}`, { organizationId: org }),
  createPayrollRun: (org, body) => appRequest("/api/app/payroll/runs", { method: "POST", body, organizationId: org }),
  approvePayrollRun: (org, id) => appRequest(`/api/app/payroll/runs/${encodeURIComponent(id)}/approve`, { method: "POST", body: {}, organizationId: org }),
  payPayrollRun: (org, id) => appRequest(`/api/app/payroll/runs/${encodeURIComponent(id)}/pay`, { method: "POST", body: {}, organizationId: org }),
  myPayslips: (org) => appRequest("/api/app/payroll/me", { organizationId: org }),

  // CRM: tickets, leads, feedback, customer 360
  tickets: (org, status = "") => appRequest(`/api/app/tickets${status ? `?status=${status}` : ""}`, { organizationId: org }),
  ticket: (org, id) => appRequest(`/api/app/tickets/${encodeURIComponent(id)}`, { organizationId: org }),
  createTicket: (org, body) => appRequest("/api/app/tickets", { method: "POST", body, organizationId: org }),
  updateTicket: (org, id, body) => appRequest(`/api/app/tickets/${encodeURIComponent(id)}`, { method: "PATCH", body, organizationId: org }),
  ticketMessages: (org, id) => appRequest(`/api/app/tickets/${encodeURIComponent(id)}/messages`, { organizationId: org }),
  addTicketMessage: (org, id, body) => appRequest(`/api/app/tickets/${encodeURIComponent(id)}/messages`, { method: "POST", body, organizationId: org }),

  leads: (org, stage = "") => appRequest(`/api/app/leads${stage ? `?stage=${stage}` : ""}`, { organizationId: org }),
  createLead: (org, body) => appRequest("/api/app/leads", { method: "POST", body, organizationId: org }),
  updateLead: (org, id, body) => appRequest(`/api/app/leads/${encodeURIComponent(id)}`, { method: "PATCH", body, organizationId: org }),
  convertLead: (org, id) => appRequest(`/api/app/leads/${encodeURIComponent(id)}/convert`, { method: "POST", body: {}, organizationId: org }),
  leadActivities: (org, id) => appRequest(`/api/app/leads/${encodeURIComponent(id)}/activities`, { organizationId: org }),
  addLeadActivity: (org, id, body) => appRequest(`/api/app/leads/${encodeURIComponent(id)}/activities`, { method: "POST", body, organizationId: org }),

  submitFeedback: (org, body) => appRequest("/api/app/feedback", { method: "POST", body, organizationId: org }),
  feedbackList: (org) => appRequest("/api/app/feedback", { organizationId: org }),
  feedbackSummary: (org) => appRequest("/api/app/feedback/summary", { organizationId: org }),

  customer360: (org, id) => appRequest(`/api/app/customers/${encodeURIComponent(id)}/360`, { organizationId: org }),

  // Fulfilment: reservations, deliveries, COD
  createReservation: (org, body) => appRequest("/api/app/reservations", { method: "POST", body, organizationId: org }),
  reservations: (org, status = "") => appRequest(`/api/app/reservations${status ? `?status=${status}` : ""}`, { organizationId: org }),
  releaseReservation: (org, documentId) => appRequest(`/api/app/reservations/${encodeURIComponent(documentId)}/release`, { method: "POST", body: {}, organizationId: org }),

  createDelivery: (org, body) => appRequest("/api/app/deliveries", { method: "POST", body, organizationId: org }),
  myDeliveries: (org) => appRequest("/api/app/deliveries/me", { organizationId: org }),
  teamDeliveries: (org, status = "") => appRequest(`/api/app/deliveries${status ? `?status=${status}` : ""}`, { organizationId: org }),
  startDelivery: (org, id) => appRequest(`/api/app/deliveries/${encodeURIComponent(id)}/out-for-delivery`, { method: "POST", body: {}, organizationId: org }),
  completeDelivery: (org, id, body) => appRequest(`/api/app/deliveries/${encodeURIComponent(id)}/complete`, { method: "POST", body, organizationId: org }),
  handOverCod: (org, id, body) => appRequest(`/api/app/deliveries/${encodeURIComponent(id)}/handover`, { method: "POST", body, organizationId: org }),

  // Supplier payable ageing, approval simulation, accounting period close
  payablesAgeing: (org) => appRequest("/api/app/payables/ageing", { organizationId: org }),
  simulateApprovalRule: (org, body) => appRequest("/api/app/approvals/rules/simulate", { method: "POST", body, organizationId: org }),
  accountingPeriods: (org) => appRequest("/api/app/accounting/periods", { organizationId: org }),
  closePeriod: (org, body) => appRequest("/api/app/accounting/periods/close", { method: "POST", body, organizationId: org }),
  reopenPeriod: (org, id, body) => appRequest(`/api/app/accounting/periods/${encodeURIComponent(id)}/reopen`, { method: "POST", body, organizationId: org }),
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
