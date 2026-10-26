import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {displayStoreCategory,displayProductUnit,displayStoreTagline,displayStoreDelivery,displayStoreArea,isSyntheticDemoArea} from "../src/storeDisplayText.js";
const read=file=>readFileSync(new URL("../src/"+file,import.meta.url),"utf8");

test("known English catalog categories and units display consistently in Bengali",()=>{
 assert.equal(displayStoreCategory("Grocery"),"মুদি");
 assert.equal(displayStoreCategory("Pharmacy"),"ফার্মেসি");
 assert.equal(displayStoreCategory("Fashion"),"পোশাক");
 assert.equal(displayProductUnit("pcs"),"পিস");
 assert.equal(displayProductUnit("kg"),"কেজি");
 assert.equal(displayProductUnit("pack"),"প্যাকেট");
 assert.equal(displayStoreCategory("হস্তশিল্প"),"হস্তশিল্প");
});
test("seed/demo boilerplate is localized only for demo shops",()=>{
 const original="Owner-managed demo storefront (not verified real commerce)";
 assert.match(displayStoreTagline(original,true),/পরীক্ষামূলক দোকান/);
 assert.equal(displayStoreTagline(original,false),original);
 assert.match(displayStoreDelivery("Demo orders only; no real shipping or payment",true),/বাস্তব পেমেন্ট বা ডেলিভারি হবে না/);
 assert.equal(displayStoreDelivery("Demo orders only; no real shipping or payment",false),"Demo orders only; no real shipping or payment");
 assert.equal(displayStoreArea("Automated Test Only",true),"শুধু পরীক্ষামূলক এলাকা");
 assert.equal(isSyntheticDemoArea("Automated Test Only",true),true);
});
test("public demo checkout does not invite customers to send real payments",()=>{
 const store=read("pages/Store.jsx");
 const dir=read("pages/StoreDirectory.jsx");
 assert.match(store,/ডেমো অর্ডার—কোনো টাকা নয়/);
 assert.match(store,/!store.is_demo && store.payment_bkash/);
 assert.match(store,/!store.is_demo && store.payment_nagad/);
 assert.match(store,/displayStoreTagline\(store.tagline, store.is_demo\)/);
 assert.match(store,/displayStoreDelivery\(store.delivery_note, store.is_demo\)/);
 assert.match(dir,/displayStoreCategory\(s.category\)/);
 assert.match(dir,/displayStoreTagline\(s.tagline, s.is_demo\)/);
});
