import test from "node:test";
import assert from "node:assert/strict";
import worker from "../commerce-worker.js";

const nonDemo={id:"merchant-safe",slug:"shop-safe",is_demo:0,is_active:1,
  owner_id:"owner-safe",real_cod_approved:0,name:"Pending merchant",category:"Retail",area:"Dhaka"};
function fakeEnv(store, enabled=false){
 return {ENABLE_REAL_COD:enabled?"true":"false",DB:{
  prepare(sql){
   return {
    bind(...args){this.args=args;return this;},
    async first(){if(sql.includes("FROM commerce_stores")&&sql.includes("LIMIT 1"))return store; throw new Error("Unexpected SQL: "+sql);},
    async all(){if(sql.includes("FROM commerce_stores")&&sql.includes("ORDER BY"))return {results:[store]}; throw new Error("Unexpected SQL: "+sql);}
   };
  }
 }};
}
const req=(url,method="GET")=>new Request("https://worker.example"+url,{method,headers:{"Content-Type":"application/json"},...(method==="POST"?{body:JSON.stringify({payment_method:"cod",items:[]})}:{})});
test("unapproved real merchant never accepts a payment order",async()=>{
 for(const enabled of [false,true]){
  const result=await worker.fetch(req("/api/public/orders/merchant-safe","POST"),fakeEnv(nonDemo,enabled));
  assert.equal(result.status,409);
  assert.match((await result.json()).detail,/not enabled/i);
 }
});
test("enabled flag alone is not enough for merchant approval",async()=>{
 const r=await worker.fetch(req("/api/public/orders/merchant-safe","POST"),fakeEnv({...nonDemo,owner_id:null,real_cod_approved:1},true));
 assert.equal(r.status,409);
});
test("public merchant directory does not advertise COD while gated",async()=>{
 const r=await worker.fetch(req("/api/public/store/"),fakeEnv(nonDemo,true));
 assert.equal(r.status,200);
 const stores=await r.json();
 assert.equal(stores[0].payment_cod,false);
 assert.equal(stores[0].checkout_available,false);
 assert.equal(stores[0].is_demo,false);
});
test("PATCH method is CORS-preflight enabled",async()=>{
 const r=await worker.fetch(new Request("https://worker.example/api/merchant/store",{method:"OPTIONS",headers:{Origin:"https://thesis-j0n8.onrender.com"}}),fakeEnv(nonDemo));
 assert.equal(r.status,204);
 assert.match(r.headers.get("Access-Control-Allow-Methods"),/PATCH/);
});
