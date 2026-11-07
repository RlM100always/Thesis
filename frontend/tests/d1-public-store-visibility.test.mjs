import test from "node:test";
import assert from "node:assert/strict";
import { isPublicStore } from "../../cloudflare/store-visibility.js";

test("all seeded or unverified stores stay out of public discovery", () => {
  assert.equal(isPublicStore({ slug: "demo-bsmart-grocery", is_demo: 1 }), false);
  assert.equal(isPublicStore({ slug: "shop-752c1d2b-b92", is_demo: 1 }), false);
  assert.equal(isPublicStore({ slug: "old-row-without-provenance-flag" }), false);
});

test("only owner-created, non-sample stores can be public", () => {
  assert.equal(isPublicStore({ slug: "shop-abc123def456", is_demo: 0 }), true);
  assert.equal(isPublicStore({ slug: "merchant-real-store", is_demo: false }), true);
});

test("missing store rows are never public", () => {
  assert.equal(isPublicStore(null), false);
  assert.equal(isPublicStore(undefined), false);
});
