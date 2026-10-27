import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const read = path => readFileSync(new URL(path, import.meta.url), "utf8");
const route = read("../../cloudflare/platform-admin-routes.js");
const page = read("../src/pages/D1PlatformAdmin.jsx");

test("platform admin order endpoint supplies all payment audit fields used by its UI", () => {
  assert.match(route, /o\.payment_method,o\.payment_status,o\.payment_received_at,o\.payment_received_by,o\.payment_note,o\.placed_at/);
  assert.match(page, /PAYMENT_STATUS\[r\.payment_status\]/);
  assert.match(page, /r\.payment_received_at/);
  assert.match(page, /r\.payment_received_by/);
  assert.match(page, /r\.payment_note/);
});

test("platform admin does not describe every order amount as a demo amount", () => {
  assert.match(route, /Demo order values are not revenue/);
  assert.match(route, /COD collection is merchant-confirmed/);
  assert.doesNotMatch(route, /Amounts are demo order values, not money received/);
});
