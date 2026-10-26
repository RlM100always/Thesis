import test from "node:test";
import assert from "node:assert/strict";
import {summarizeOrderStatuses,merchantInsights} from "../merchant-insights.js";
test("metrics never describe booked COD as received cash",()=>{
 const result=summarizeOrderStatuses([
  {status:"placed",orders:2,amount_bdt:400},
  {status:"fulfilled",orders:1,amount_bdt:300},
  {status:"cancelled",orders:1,amount_bdt:900}
 ]);
 assert.deepEqual(result,{
  orders:4,booked_bdt:700,fulfilled_bdt:300,cancelled:1,open:2,
  avg_order_bdt:233,cancellation_rate_pct:25
 });
 assert.equal(summarizeOrderStatuses([]).avg_order_bdt,0);
 assert.equal(summarizeOrderStatuses([{status:"cancelled",orders:1,amount_bdt:99}]).booked_bdt,0);
});
test("merchant insights scoping uses one store and 7/30/90-day time windows",async()=>{
 const bindings=[];
 const samples=[
  [{status:"placed",orders:1,amount_bdt:220}],
  [{day:"2026-10-26",orders:1,booked_bdt:220}],
  [{product_id:"sku1",product_name:"Item",units:2,amount_bdt:220}],
  [{id:"sku1",name:"Item",stock_qty:1,reorder_point:5,is_listed:1}]
 ];
 const db={prepare(sql){
  const i=bindings.length;
  return {bind(...params){bindings.push({sql,params});return {async all(){return {results:samples[i]}}}}};
 }};
 const result=await merchantInsights(db,"store-123",30);
 assert.equal(result.days,30);
 assert.equal(result.summary.booked_bdt,220);
 assert.equal(result.amounts_are_verified_payments,false);
 assert.equal(result.low_stock_count,1);
 assert.equal(bindings.length,4);
 assert.ok(bindings.every(x=>x.params[0]==="store-123"));
 assert.ok(bindings.slice(0,3).every(x=>x.params[1]==="-30 days"));
 assert.ok(bindings[3].sql.includes("stock_qty<=reorder_point"));
});
