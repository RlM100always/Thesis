import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
const pages=["Store.jsx","StoreDirectory.jsx","OrderStatus.jsx","PublicSite.jsx","StoreCustomerPortal.jsx"];
const read=path=>readFileSync(new URL("../../frontend/src/"+path,import.meta.url),"utf8");
test("public-page copy never regresses to mixed UI-development instructions",()=>{
 const combined=pages.map(name=>read("pages/"+name)).join("\n");
 for(const phrase of [
  "operational database-এ","Activate করে পণ্য Publish","নতুন independent owner account",
  "এই তথ্য অ্যাপের status changes","Courier delivery বা টাকা সংগ্রহের",
  "যাচাইকৃত real COD checkout","অনলাইনে অর্ডার করুন: ${storeUrl}"
 ])assert.equal(combined.includes(phrase),false,phrase);
 assert.match(read("pages/Store.jsx"),/এটি একটি পরীক্ষামূলক দোকান/);
 assert.match(read("pages/StoreDirectory.jsx"),/শুধু বাস্তব দোকান/);
 assert.match(read("pages/OrderStatus.jsx"),/অর্ডারের সর্বশেষ অবস্থা/);
});
test("dark-mode surfaces and native form themes have scoped semantic colors",()=>{
 const store=read("pages/Store.jsx");
 const dir=read("pages/StoreDirectory.jsx");
 const marketing=read("index.css");
 const tracking=read("pages/OrderStatus.css");
 const portal=read("pages/StoreCustomerPortal.css");
 for(const src of [store,dir,marketing,tracking,portal]){
  assert.match(src,/data-theme="dark"/);
  assert.match(src,/prefers-color-scheme:dark|prefers-color-scheme: dark/);
 }
 for(const required of ["--s-bg:#091710","--s-ink:#f2f8f3","--s-border:#365241","--s-muted:#bed4c5"]){
  assert.ok(store.includes(required),required);
 }
 assert.match(store,/readableAccent\(color, palette.bg\)/);
 assert.match(dir,/--sd-active-text/);
});
