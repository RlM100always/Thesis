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

test("platform admin distinguishes archived order value from live COD collections", () => {
  assert.match(route, /AS demo_order_value_bdt/);
  assert.match(route, /s\.is_demo=0 AND o\.payment_method='cod'/);
  assert.match(page, /Archived order value/);
  assert.match(page, /COD received/);
  assert.match(page, /আর্কাইভ করা অকার্যকর অর্ডারগুলো বাস্তব আয় নয়/);
  assert.doesNotMatch(page, /Demo order value|Demo order values are not revenue/);
});
