import test from "node:test";
import assert from "node:assert/strict";
import { calculateCouponDiscount } from "../../cloudflare/commerce-worker.js";

const activeCoupon={
  id:"coupon-a",code:"SAVE10",is_active:1,discount_type:"percent",discount_value:10,
  min_order_bdt:1000,max_discount_bdt:500,usage_limit:100,per_customer_limit:1,
  starts_at:"2026-01-01T00:00:00.000Z",ends_at:"2027-01-01T00:00:00.000Z"
};
const now=Date.parse("2026-11-08T00:00:00.000Z");

test("percentage coupon calculates a bounded discount",()=>{
  const result=calculateCouponDiscount(activeCoupon,10000,now);
  assert.equal(result.discount_amount,500);
  assert.equal(result.code,"SAVE10");
  assert.equal(result.discount_type,"percent");
});

test("fixed coupon cannot discount more than the order subtotal",()=>{
  const result=calculateCouponDiscount({...activeCoupon,discount_type:"fixed",discount_value:5000,max_discount_bdt:null},1200,now);
  assert.equal(result.discount_amount,1200);
});

test("coupon rejects orders below the minimum subtotal",()=>{
  assert.throws(()=>calculateCouponDiscount(activeCoupon,999,now),/Minimum order/);
});

test("coupon rejects inactive, not-yet-started and expired offers",()=>{
  assert.throws(()=>calculateCouponDiscount({...activeCoupon,is_active:0},2000,now),/not active/);
  assert.throws(()=>calculateCouponDiscount({...activeCoupon,starts_at:"2026-12-01T00:00:00.000Z"},2000,now),/not active yet/);
  assert.throws(()=>calculateCouponDiscount({...activeCoupon,ends_at:"2026-10-01T00:00:00.000Z"},2000,now),/expired/);
});

test("coupon discount is always a whole non-negative amount and never exceeds subtotal",()=>{
  const result=calculateCouponDiscount({...activeCoupon,discount_value:17,max_discount_bdt:null},1100,now);
  assert.equal(result.discount_amount,187);
  assert.ok(Number.isInteger(result.discount_amount));
  assert.ok(result.discount_amount>=0&&result.discount_amount<=1100);
});

test("checkout enforces atomic total and per-customer redemption triggers",()=>{
  const migration=await import("node:fs/promises").then(fs=>fs.readFile(new URL("../../cloudflare/migrations/0011_store_coupons.sql",import.meta.url),"utf8"));
  assert.match(migration,/commerce_coupon_total_limit/);
  assert.match(migration,/commerce_coupon_customer_limit/);
  assert.match(migration,/UNIQUE\(store_id,code\)/);
  assert.match(migration,/coupon_discount_bdt/);
});
