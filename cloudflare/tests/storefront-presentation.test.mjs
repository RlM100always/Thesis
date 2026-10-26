import test from "node:test";
import assert from "node:assert/strict";
import worker from "../commerce-worker.js";
const real={
 id:"merchant-brand-1",slug:"shop-brand-1",is_demo:0,is_active:1,
 owner_id:"owner-1",real_cod_approved:0,
 name:"Real example shop",tagline:"Quality everyday essentials",category:"Clothing",
 area:"Rajshahi",theme:"purple",color:"#774499",
 logo_image_url:"https://example.org/logo.png",cover_image_url:"https://example.org/cover.jpg",
 public_phone:"01712345678",public_address:"Rajshahi Bangladesh",
 announcement_text:"Fresh collection now available",about_text:"Independent shop",
 delivery_policy_text:"Dispatch after merchant confirmation",return_policy_text:"Contact seller for returns"
};
function envFor(store){
 return {ENABLE_REAL_COD:"false",DB:{prepare(sql){
  return {bind(){return this;},async first(){if(sql.includes("FROM commerce_stores"))return store;throw Error("Unexpected SQL "+sql);},
   async all(){if(sql.includes("FROM commerce_products"))return {results:[{
    id:"product-1",sku:"SOCK-01",name:"Cotton socks",category:"Socks",description:"Soft breathable cotton",
    price_bdt:250,stock_qty:4,image_url:"https://example.org/socks.jpg",is_featured:1,is_listed:1
   }]};throw Error("Unexpected SQL "+sql);}};
 }}};
}
const request=new Request("https://worker.example/api/public/store/slug/shop-brand-1");
test("real merchant storefront uses brand, contact and accurate product category",async()=>{
 const response=await worker.fetch(request,envFor(real));
 assert.equal(response.status,200);
 const s=await response.json();
 assert.equal(s.display_name,"Real example shop");
 assert.equal(s.theme_preset,"purple");
 assert.equal(s.theme_color,"#774499");
 assert.equal(s.logo_data_url,"https://example.org/logo.png");
 assert.equal(s.cover_data_url,"https://example.org/cover.jpg");
 assert.equal(s.phone,"01712345678");
 assert.equal(s.address,"Rajshahi Bangladesh");
 assert.equal(s.announcement_text,"Fresh collection now available");
 assert.equal(s.about_text,"Independent shop");
 assert.equal(s.delivery_policy_text,"Dispatch after merchant confirmation");
 assert.equal(s.return_policy_text,"Contact seller for returns");
 assert.equal(s.checkout_available,false);
 assert.equal(s.payment_cod,false);
 assert.equal(s.products[0].description,"Soft breathable cotton");
 assert.deepEqual(s.products[0].tags,["Socks"]);
 assert.equal(s.products[0].is_featured,true);
});
test("demo shop contact stays private and product never masquerades as real",async()=>{
 const response=await worker.fetch(request,envFor({...real,is_demo:1,tagline:"Demo only",delivery_note:"Do not pay"}));
 assert.equal(response.status,200);
 const s=await response.json();
 assert.equal(s.is_demo,true);
 assert.equal(s.logo_data_url,null);
 assert.equal(s.cover_data_url,null);
 assert.equal(s.phone,null);
 assert.equal(s.address,null);
 assert.equal(s.delivery_policy_text,"Demo only; no delivery is performed");
 assert.equal(s.return_policy_text,"Demo only; no actual purchases or returns");
 assert.equal(s.products[0].description,"Soft breathable cotton");
});
