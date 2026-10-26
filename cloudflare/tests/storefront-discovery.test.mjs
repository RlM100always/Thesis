import test from "node:test";
import assert from "node:assert/strict";
import {recentProducts,rememberProduct,toggleCompared,COMPARE_LIMIT} from "../../frontend/src/storefrontDiscovery.js";

test("comparison caps at three, toggles without duplicates and never mutates previous list",()=>{
 let list=[];
 for(const id of ["p1","p2","p3"])list=toggleCompared(list,id);
 assert.deepEqual(list,["p1","p2","p3"]);
 assert.equal(COMPARE_LIMIT,3);
 const before=[...list];
 assert.deepEqual(toggleCompared(list,"p4"),before);
 assert.deepEqual(toggleCompared(list,"p2"),["p1","p3"]);
 assert.deepEqual(list,before);
 assert.deepEqual(toggleCompared(["p1","p2"],"p1"),["p2"]);
});
test("recent products are isolated per shop, deduplicated and limited to 8",()=>{
 const storage=new Map();
 globalThis.localStorage={
  getItem:key=>storage.get(key)||null,
  setItem:(key,value)=>storage.set(key,value)
 };
 for(let i=0;i<14;i++)rememberProduct("shop-one",`p${i}`);
 assert.deepEqual(recentProducts("shop-one"),["p13","p12","p11","p10","p9","p8","p7","p6"]);
 assert.deepEqual(recentProducts("shop-two"),[]);
 rememberProduct("shop-one","p10");
 assert.deepEqual(recentProducts("shop-one").slice(0,3),["p10","p13","p12"]);
 storage.set("bsmart-recent-products:v1:shop-two","not json");
 assert.deepEqual(recentProducts("shop-two"),[]);
 delete globalThis.localStorage;
 assert.deepEqual(recentProducts("shop-one"),[]);
 assert.deepEqual(rememberProduct("shop-one","abc"),["abc"]);
});
