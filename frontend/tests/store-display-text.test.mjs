import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {displayStoreCategory,displayProductUnit,displayStoreTagline,displayStoreDelivery,displayStoreArea,isSyntheticSampleArea} from "../src/storeDisplayText.js";
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
test("unverified sample boilerplate is localized without changing merchant data",()=>{
 const original="Owner-managed sample storefront (not verified real commerce)";
 assert.match(displayStoreTagline(original,true),/যাচাইহীন নমুনা দোকান/);
 assert.equal(displayStoreTagline(original,false),original);
 assert.match(displayStoreDelivery("Sample orders only; no real shipping or payment",true),/বাস্তব পেমেন্ট বা ডেলিভারি হবে না/);
 assert.equal(displayStoreDelivery("Sample orders only; no real shipping or payment",false),"Sample orders only; no real shipping or payment");
 assert.equal(displayStoreArea("Automated Test Only",true),"শুধু পরীক্ষামূলক এলাকা");
 assert.equal(isSyntheticSampleArea("Automated Test Only",true),true);
});
test("public customer copy does not present unverified records as live commerce",()=>{
 const store=read("pages/Store.jsx");
 const dir=read("pages/StoreDirectory.jsx");
 assert.match(store,/যাচাইহীন নমুনা অর্ডারের তথ্য দিন/);
 assert.match(store,/!store.is_demo && store.payment_bkash/);
 assert.match(store,/!store.is_demo && store.payment_nagad/);
 assert.match(store,/displayStoreTagline\(store.tagline, store.is_demo\)/);
 assert.match(store,/displayStoreDelivery\(store.delivery_note, store.is_demo\)/);
 assert.match(dir,/displayStoreCategory\(s.category\)/);
 assert.match(dir,/displayStoreTagline\(s.tagline\)/);
 assert.doesNotMatch(dir,/ডেমো|Demo|demo/);
});
