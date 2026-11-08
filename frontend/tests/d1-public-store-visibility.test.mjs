import test from "node:test";
import assert from "node:assert/strict";
import { isPublicStore } from "../../cloudflare/store-visibility.js";

test("retained POS CI fixture stays out of the public storefront directory", () => {
  assert.equal(isPublicStore({ slug: "shop-752c1d2b-b92", is_active: 1, is_demo: 0 }), false);
});

test("inactive or non-operational records never become public storefronts", () => {
  assert.equal(isPublicStore({ slug: "demo-bsmart-grocery", is_active: 0, is_demo: 1 }), false);
  assert.equal(isPublicStore({ slug: "shop-abc123def456", is_active: 1, is_demo: 1 }), false);
  assert.equal(isPublicStore({ slug: "shop-abc123def456", is_active: 0, is_demo: 0 }), false);
});

test("only active operational merchant stores are publicly visible", () => {
  assert.equal(isPublicStore({ slug: "shop-abc123def456", is_active: 1, is_demo: 0 }), true);
});

test("missing or incomplete store rows are never public", () => {
  assert.equal(isPublicStore(null), false);
  assert.equal(isPublicStore(undefined), false);
  assert.equal(isPublicStore({ slug: "shop-abc123def456" }), false);
});
