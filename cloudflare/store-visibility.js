// Public storefront visibility is deliberately fail-closed.
// A store is public only after it is active and explicitly marked operational.
// Retained sample and CI rows stay in D1 for audit/reconciliation, never customer discovery.
export const INTERNAL_TEST_STORE_SLUGS = new Set(["shop-752c1d2b-b92"]);

export function isPublicStore(store) {
  return !!store &&
    Number(store.is_active) === 1 &&
    Number(store.is_demo) === 0 &&
    !INTERNAL_TEST_STORE_SLUGS.has(String(store.slug || ""));
}
