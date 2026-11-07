// Production-safe visibility for known CI fixtures left by old live-write smoke tests.
// Keep their D1 rows for audit/reconciliation, but never expose them as customer storefronts.
export const INTERNAL_TEST_STORE_SLUGS = new Set(["shop-752c1d2b-b92"]);

export function isPublicStore(store) {
  return !!store && Number(store.is_demo ?? 1) === 0 && !INTERNAL_TEST_STORE_SLUGS.has(String(store.slug || ""));
}
