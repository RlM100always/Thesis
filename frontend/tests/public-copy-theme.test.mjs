import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {contrastRatio,contrastColor,readableAccent} from "../src/storeContrast.js";
const read=file=>readFileSync(new URL("../src/"+file,import.meta.url),"utf8");

test("every supported background/merchant accent pair meets 4.5:1 for small text",()=>{
 const backgrounds=["#ffffff","#f7faf8","#fdf6ed","#faf5ff","#091710","#13251b","#0d1f16"];
 const accents=["#fff000","#ffffff","#000000","#ff00ff","#eeeeee","#087e59","#f15a24","#004477","#555555"];
 for(const bg of backgrounds)for(const accent of accents){
  const actual=readableAccent(accent,bg);
  assert.ok(contrastRatio(actual,bg)>=4.5,`${accent}/${bg}: ${actual} ${contrastRatio(actual,bg)}`);
  assert.ok(contrastRatio(actual,contrastColor(actual))>=4.5);
 }
});
test("important public pages use semantic scoped dark-mode colors",()=>{
 const store=read("pages/Store.jsx");
 const dir=read("pages/StoreDirectory.jsx");
 const landing=read("index.css");
 const tracking=read("pages/OrderStatus.css");
 const portal=read("pages/StoreCustomerPortal.css");
 assert.match(store,/readableAccent\(color, darkSurface/);
 assert.match(store,/--s-ink:#f2f8f3/);
 assert.match(dir,/--sd-active-text/);
 assert.match(landing,/Public-facing visual QA v13/);
 assert.match(tracking,/order-status-timeline/);
 assert.match(portal,/--sc-on-green/);
 for(const text of [store,dir,landing,tracking,portal])assert.match(text,/data-theme="dark"/);
});
test("old misleading and mixed public copy stays removed",()=>{
 const store=read("pages/Store.jsx");
 const directory=read("pages/StoreDirectory.jsx");
 const tracking=read("pages/OrderStatus.jsx");
 assert.doesNotMatch(store,/ডেমো স্টোর|পরীক্ষামূলক অর্ডার/);
 assert.match(tracking,/অর্ডারের সর্বশেষ অবস্থা/);
 for(const obsolete of ["operational database-এ","Activate করে পণ্য Publish","independent owner account"]){
  assert.ok(!directory.includes(obsolete),obsolete);
 }
});

test("customers can switch theme on all standalone public shopping routes",()=>{
 const store=read("pages/Store.jsx");
 const directory=read("pages/StoreDirectory.jsx");
 const tracking=read("pages/OrderStatus.jsx");
 for(const page of [store,directory,tracking]){
  assert.match(page,/useUi\(\)/);
  assert.match(page,/toggleTheme/);\n assert.doesNotMatch(page,/পরীক্ষামূলক দোকান|নমুনা বিক্রি|ডেমো বিক্রি/);
  assert.match(page,/লাইট মোড চালু করুন/);
  assert.match(page,/ডার্ক মোড চালু করুন/);
 }
});
test("public shopping pages show only approved operational stores",()=>{
 const directory=read("pages/StoreDirectory.jsx");
 const store=read("pages/Store.jsx");
 const login=read("pages/Login.jsx");
 const site=read("pages/PublicSite.jsx");
 assert.doesNotMatch(directory,/ডেমো দোকানে|পরীক্ষামূলক দোকান/);
 assert.match(directory,/stores\.filter\(s => s\.payment_cod\)/);
 assert.match(directory,/অনুমোদিত দোকান/);
 assert.match(store,/দোকানটি দেখুন/);
 assert.ok(!login.includes("Owner account খুলুন"));
 assert.ok(!login.includes("actor-aware operation"));
 assert.ok(!site.includes("শুধু শুধু ফিচারের সংখ্যা"));
});

test("D1 owner UI uses neutral operational status copy",()=>{
 const page=read("pages/D1MerchantCenter.jsx");
 const css=read("pages/D1MerchantCenter.css");
 assert.match(page,/ORDER_STATUS_BN/);
 assert.match(page,/CASH_KIND_BN/);
 assert.match(page,/নতুন দোকান মালিকের অ্যাকাউন্ট/);
 assert.match(page,/কাউন্টার বিক্রি/);
 assert.match(page,/নগদ হিসাব/);
 assert.match(page,/toggleTheme/);
 assert.match(css,/--dm-error-bg/);
 assert.match(css,/--dm-success-bg/);
 assert.match(css,/data-theme=dark/);
 for(const phrase of ["Demo counter POS","Cashbook entry (demo)","Store owner login","Create D1 Store","Owner access key (64 hex characters)"])
  assert.ok(!page.includes(phrase),phrase);
});
