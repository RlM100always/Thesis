import test from "node:test";
import assert from "node:assert/strict";
import { hasMerchantPermission, merchantPermissionFor } from "../cloudflare/merchant-permissions.mjs";

test("owner and manager permissions cover store operations", () => {
  assert.equal(hasMerchantPermission("owner", "anything"), true);
  for (const permission of ["products:write","inventory:write","orders:write","coupons:write","returns:write","support:write","analytics:read","sales:write","finance:write","store:write"]) {
    assert.equal(hasMerchantPermission("manager", permission), true, permission);
  }
});

test("inventory staff can adjust stock but cannot change product data or sales", () => {
  assert.equal(hasMerchantPermission("inventory", "products:read"), true);
  assert.equal(hasMerchantPermission("inventory", "inventory:write"), true);
  assert.equal(hasMerchantPermission("inventory", "products:write"), false);
  assert.equal(hasMerchantPermission("inventory", "orders:write"), false);
  assert.equal(hasMerchantPermission("inventory", "finance:write"), false);
});

test("sales staff can create POS sales and update order status only", () => {
  assert.equal(hasMerchantPermission("sales", "sales:write"), true);
  assert.equal(hasMerchantPermission("sales", "orders:write"), true);
  assert.equal(hasMerchantPermission("sales", "finance:write"), false);
  assert.equal(hasMerchantPermission("sales", "products:write"), false);
});

test("support staff can manage support and returns but not stock or sales", () => {
  assert.equal(hasMerchantPermission("support", "support:write"), true);
  assert.equal(hasMerchantPermission("support", "returns:write"), true);
  assert.equal(hasMerchantPermission("support", "orders:write"), false);
  assert.equal(hasMerchantPermission("support", "inventory:write"), false);
});

test("analysts are read-only", () => {
  assert.equal(hasMerchantPermission("analyst", "analytics:read"), true);
  assert.equal(hasMerchantPermission("analyst", "orders:read"), true);
  assert.equal(hasMerchantPermission("analyst", "orders:write"), false);
  assert.equal(hasMerchantPermission("analyst", "products:write"), false);
});

test("API paths map to the intended least-privilege permission", () => {
  assert.equal(merchantPermissionFor("PATCH", "/api/merchant/inventory/product-1"), "inventory:write");
  assert.equal(merchantPermissionFor("PATCH", "/api/merchant/products/product-1"), "products:write");
  assert.equal(merchantPermissionFor("POST", "/api/merchant/pos"), "sales:write");
  assert.equal(merchantPermissionFor("POST", "/api/merchant/cashbook"), "finance:write");
  assert.equal(merchantPermissionFor("PATCH", "/api/merchant/orders/order-1/status"), "orders:write");
  assert.equal(merchantPermissionFor("PATCH", "/api/merchant/orders/order-1/payment"), "finance:write");
  assert.equal(merchantPermissionFor("POST", "/api/merchant/chat"), "support:write");
  assert.equal(merchantPermissionFor("DELETE", "/api/merchant/staff"), null);
});
