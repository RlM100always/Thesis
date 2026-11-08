import test from "node:test";
import assert from "node:assert/strict";
import {
  ORDER_STATUS_TRANSITIONS,
  canTransitionOrderStatus,
  defaultOrderStatusNote,
} from "../../cloudflare/order-workflow.js";

test("order status advances through the customer-visible fulfilment stages", () => {
  const flow = [
    ["placed", "confirmed"],
    ["confirmed", "processing"],
    ["processing", "ready"],
    ["ready", "dispatched"],
    ["dispatched", "delivered"],
  ];
  for (const [current, next] of flow) assert.equal(canTransitionOrderStatus(current, next), true);
});

test("platform and merchant order transitions share the same guarded workflow", () => {
  assert.equal(canTransitionOrderStatus("placed", "confirmed"), true);
  assert.equal(canTransitionOrderStatus("confirmed", "processing"), true);
  assert.equal(canTransitionOrderStatus("processing", "ready"), true);
  assert.equal(canTransitionOrderStatus("ready", "dispatched"), true);
  assert.equal(canTransitionOrderStatus("dispatched", "delivered"), true);
});

test("cancellation is unavailable after dispatch and terminal states cannot advance", () => {
  assert.equal(canTransitionOrderStatus("placed", "cancelled"), true);
  assert.equal(canTransitionOrderStatus("confirmed", "cancelled"), true);
  assert.equal(canTransitionOrderStatus("ready", "cancelled"), true);
  assert.equal(canTransitionOrderStatus("dispatched", "cancelled"), false);
  assert.equal(canTransitionOrderStatus("delivered", "cancelled"), false);
  assert.equal(canTransitionOrderStatus("cancelled", "confirmed"), false);
  assert.equal(canTransitionOrderStatus("fulfilled", "delivered"), false);
  assert.deepEqual(ORDER_STATUS_TRANSITIONS.delivered, []);
});

test("status notes distinguish archived and operational orders", () => {
  assert.match(defaultOrderStatusNote("processing", true), /আর্কাইভ করা অর্ডার/);
  assert.match(defaultOrderStatusNote("processing", true), /পণ্য প্রস্তুত করা হচ্ছে/);
  assert.doesNotMatch(defaultOrderStatusNote("processing", false), /আর্কাইভ করা/);
  assert.match(defaultOrderStatusNote("delivered", false), /ডেলিভারি সম্পন্ন/);
});
