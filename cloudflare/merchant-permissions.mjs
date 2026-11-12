export const MERCHANT_ROLE_PERMISSIONS = Object.freeze({
  owner: new Set(["*"]),
  manager: new Set(["session:logout","dashboard:read","products:read","products:write","inventory:read","inventory:write","orders:read","orders:write","coupons:read","coupons:write","returns:read","returns:write","support:read","support:write","analytics:read","sales:write","finance:write","store:write"]),
  sales: new Set(["session:logout","dashboard:read","products:read","inventory:read","orders:read","orders:write","coupons:read","sales:write"]),
  inventory: new Set(["session:logout","dashboard:read","products:read","inventory:read","inventory:write"]),
  support: new Set(["session:logout","dashboard:read","orders:read","returns:read","returns:write","support:read","support:write"]),
  analyst: new Set(["session:logout","dashboard:read","products:read","inventory:read","orders:read","analytics:read"]),
});

export function hasMerchantPermission(role, permission) {
  const permissions = MERCHANT_ROLE_PERMISSIONS[role];
  return Boolean(permissions && (permissions.has("*") || permissions.has(permission)));
}

export function merchantPermissionFor(method, path) {
  if (method === "POST" && path === "/api/merchant/logout") return "session:logout";
  if (method === "GET" && path === "/api/merchant/dashboard") return "dashboard:read";
  if (method === "GET" && path === "/api/merchant/analytics") return "analytics:read";
  if (method === "GET" && path === "/api/merchant/inventory-alerts") return "inventory:read";
  if (path === "/api/merchant/coupons") return method === "GET" ? "coupons:read" : method === "POST" ? "coupons:write" : null;
  if (/^\/api\/merchant\/coupons\/[^/]+$/.test(path)) return method === "GET" ? "coupons:read" : ["PATCH", "DELETE"].includes(method) ? "coupons:write" : null;
  if (method === "POST" && path === "/api/merchant/assistant") return "analytics:read";
  if (path === "/api/merchant/returns") return method === "GET" ? "returns:read" : null;
  if (/^\/api\/merchant\/returns\/[^/]+$/.test(path) && method === "PATCH") return "returns:write";
  if (path === "/api/merchant/chat") return method === "GET" ? "support:read" : method === "POST" ? "support:write" : null;
  if (path === "/api/merchant/store" && method === "PATCH") return "store:write";
  if (path === "/api/merchant/cashbook" && method === "POST") return "finance:write";
  if (path === "/api/merchant/pos" && method === "POST") return "sales:write";
  if (path === "/api/merchant/products" && method === "POST") return "products:write";
  if (/^\/api\/merchant\/products\/[^/]+$/.test(path) && method === "PATCH") return "products:write";
  if (/^\/api\/merchant\/inventory\/[^/]+$/.test(path) && method === "PATCH") return "inventory:write";
  if (/^\/api\/merchant\/orders\/[^/]+\/status$/.test(path) && method === "PATCH") return "orders:write";
  if (/^\/api\/merchant\/orders\/[^/]+\/payment$/.test(path) && method === "PATCH") return "finance:write";
  return null;
}
