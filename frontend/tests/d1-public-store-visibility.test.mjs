import test from "node:test";
import assert from "node:assert/strict";
import { isPublicStore } from "../../cloudflare/store-visibility.js";

test("retained POS CI fixture stays out of the public storefront directory", () => {
  assert.equal(isPublicStore({ slug: "shop-752c1d2b-b92" }), false);
});

test("seeded demo stores and new merchant storefronts remain eligible for public visibility", () => {
  assert.equal(isPublicStore({ slug: "demo-bsmart-grocery" }), true);
  assert.equal(isPublicStore({ slug: "shop-abc123def456" }), true);
});

test("missing store rows are never public", () => {
  assert.equal(isPublicStore(null), false);
  assert.equal(isPublicStore(undefined), false);
});
