import { d1Commerce, isD1Store } from "./api";

export { isD1Store };
export const customerTokenKey = storeSlug => isD1Store(storeSlug) ? "sc_d1_token" : "sc_token";

export function getCustomerToken(storeSlug) {
  try { return localStorage.getItem(customerTokenKey(storeSlug)); } catch (_) { return null; }
}
export function saveCustomerToken(token, storeSlug) {
  try { localStorage.setItem(customerTokenKey(storeSlug), token); } catch (_) {}
}
export function clearCustomerToken(storeSlug) {
  try { localStorage.removeItem(customerTokenKey(storeSlug)); } catch (_) {}
}

export async function customerFetch(storeSlug, path, options = {}, token = getCustomerToken(storeSlug)) {
  const method = options.method || "GET";
  let body = options.body;
  if (typeof body === "string") {
    try { body = JSON.parse(body); } catch (_) {}
  }
  if (isD1Store(storeSlug)) {
    const result = await d1Commerce(`/api/customer${path}`, {
      method,
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      ...(body !== undefined ? { body } : {}),
    });
    // Keep one response shape for the shared account UI.
    if (path === "/me" || path === "/profile") return result.customer || result;
    return result;
  }
  const response = await fetch(`/api/sc${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
    ...(body !== undefined ? { body: typeof body === "string" ? body : JSON.stringify(body) } : {}),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw Object.assign(new Error(data.detail || "অনুরোধটি সম্পন্ন করা যায়নি"), { status: response.status });
  return data;
}

export async function submitCustomerReview(storeSlug, order, item, rating, comment, token) {
  const body = {
    product_id: item.product_id, order_id: order.id,
    rating: Number(rating), comment: String(comment || "").trim() || null,
  };
  if (isD1Store(storeSlug)) {
    return customerFetch(storeSlug, `/reviews/${encodeURIComponent(order.organization_id)}`, {
      method: "POST", body,
    }, token);
  }
  const response = await fetch(`/api/public/reviews/${encodeURIComponent(order.organization_id)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || "রিভিউ জমা দেওয়া যায়নি।");
  return data;
}

export async function cancelCustomerOrder(storeSlug, organizationId, accessToken) {
  if (isD1Store(storeSlug)) {
    return d1Commerce(`/api/public/orders/${encodeURIComponent(organizationId)}/cancel/${encodeURIComponent(accessToken)}`, { method: "POST" });
  }
  const response = await fetch(`/api/public/orders/${encodeURIComponent(organizationId)}/cancel/${encodeURIComponent(accessToken)}`, { method: "POST" });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || "অর্ডার বাতিল করা যায়নি");
  return data;
}
