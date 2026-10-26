import { merchantRouter } from "./merchant-routes.js";
import {realCODReady, normalizeCODContact} from "./checkout-policy.js";
/*
 B-SMART Cloudflare D1 Commerce API.
 Public read-only directory & example-store catalogues, demo checkout (no
 actual payment/delivery), token-only order tracking. No private profile data
 retained for synthetic demo checkout.
 D1 is the source of truth for this demo catalogue only. The pre-existing
 FastAPI operational POS/customer/admin flows still need explicit migration.
*/
const allowed = new Set([
  "https://thesis-j0n8.onrender.com",
  "http://localhost:5173",
  "http://127.0.0.1:5173",
  "http://localhost:3000"
]);
const cors = (request) => {
  const origin=request.headers.get("Origin");
  return {
    "Content-Type":"application/json; charset=utf-8",
    "Cache-Control":"no-store",
    "Vary":"Origin",
    ...(origin && allowed.has(origin) ? {"Access-Control-Allow-Origin":origin} : {}),
    "Access-Control-Allow-Methods":"GET,POST,PATCH,OPTIONS",
    "Access-Control-Allow-Headers":"Content-Type, Authorization",
  };
};
function output(request,value,status=200) {
  return new Response(JSON.stringify(value),{status,headers:cors(request)});
}
function error(request,status,message) {
  return output(request,{detail:message},status);
}
function safe(v) {return String(v||"").slice(0,110);}
const baseView=(s,env)=>({
  organization_id:s.id,slug:s.slug,is_demo:!!s.is_demo,is_active:!!s.is_active,
  checkout_available:!!s.is_demo||realCODReady(s,env),real_cod_enabled:realCODReady(s,env),
  display_name:s.name,tagline:s.tagline,logo_data_url:s.is_demo?null:(s.logo_image_url||null),cover_data_url:s.is_demo?null:(s.cover_image_url||null),
  category:s.category,area:s.area,theme_preset:s.theme,theme_color:s.color,
  phone:s.is_demo?null:(s.public_phone||null),address:s.is_demo?null:(s.public_address||null),show_hours:false,hours_json:null,show_price:true,
  show_stock_level:"available_only",payment_cod:!!s.is_demo||realCODReady(s,env),payment_bkash:false,
  payment_nagad:false,bkash_number:null,nagad_number:null,
  sslcz_store_id:null,bkash_app_key:null,nagad_merchant_id:null,
  min_order_bdt:null,delivery_note:s.is_demo?(s.delivery_note||"Demo only"):
    (realCODReady(s,env)?"Cash on delivery; fulfilled by the merchant. No advance payment.":"Checkout is not yet enabled for this merchant"),
  delivery_inside_dhaka:0,delivery_outside_dhaka:0,delivery_free_above:null,
  allow_zone_restriction:false,allowed_divisions:null,
  meta_title:s.name,meta_desc:s.tagline,
  announcement_text:s.announcement_text||"",
  about_text:s.about_text||"",
  // Demo policies are informational, never evidence of actual dispatch/returns.
  delivery_policy_text:s.is_demo?"Demo only; no delivery is performed":(s.delivery_policy_text||""),
  return_policy_text:s.is_demo?"Demo only; no actual purchases or returns":(s.return_policy_text||"")
});
const productView=(p,isDemo=true)=>({
  id:p.id,name:p.name,sku:p.sku,unit:"pcs",price:p.price_bdt,
  selling_price:p.price_bdt,description:isDemo?(p.description||"Demo product; not a real merchant listing"):(p.description||""),
  sale_price:null,sale_end:null,image_data_url:p.image_url||null,
  tags:p.category?[p.category]:[],is_featured:!!p.is_featured,sort_order:0,max_order_qty:Math.min(p.stock_qty,10),
  variants:[],in_stock:p.stock_qty>0,quantity:p.stock_qty,category:p.category
});
async function getStore(env,term,slugMode) {
 const sql=slugMode?
  "SELECT * FROM commerce_stores WHERE slug=? AND is_active=1 LIMIT 1":
  "SELECT * FROM commerce_stores WHERE id=? AND is_active=1 LIMIT 1";
 return env.DB.prepare(sql).bind(term).first();
}
async function storeResponse(env,store) {
 const {results}=await env.DB.prepare("SELECT * FROM commerce_products WHERE store_id=? AND is_listed=1 ORDER BY is_featured DESC,name").bind(store.id).all();
 return {...baseView(store,env),products:results.map(p=>productView(p,!!store.is_demo))};
}
async function orderDetails(env,request,id,token) {
 const order=await env.DB.prepare("SELECT * FROM commerce_orders WHERE store_id=? AND access_token=? LIMIT 1").bind(id,token).first();
 if(!order)return error(request,404,"Order not found");
 const {results}=await env.DB.prepare("SELECT product_name,quantity,price_bdt,line_total_bdt FROM commerce_order_lines WHERE order_id=?").bind(order.id).all();
 const store=await env.DB.prepare("SELECT is_demo FROM commerce_stores WHERE id=?").bind(id).first();
 const history=await env.DB.prepare("SELECT new_status AS status,created_at FROM commerce_order_events WHERE store_id=? AND order_id=? ORDER BY created_at,id LIMIT 50").bind(id,order.id).all();
 const isDemo=!!store?.is_demo;
 return output(request,{
  id:order.id,order_number:order.order_number,access_token:order.access_token,
  status:order.status,payment_status:isDemo?"demo_no_payment":"cod_unpaid",
  status_note:isDemo?"Synthetic demonstration order; no delivery":"Cash on delivery requested. Seller must confirm and arrange shipment; no payment has been collected by this website.",
  placed_at:order.placed_at,shipping_name:isDemo?"Demo customer":order.shipping_name,
  shipping_phone:isDemo?"":order.shipping_phone,shipping_address:isDemo?"":order.shipping_address,
  subtotal:order.subtotal_bdt,tax_amount:0,delivery_fee:0,discount_amount:0,
  coupon_code:null,coupon_discount:0,total:order.total_bdt,organization_id:id,
  payment_method:isDemo?"demo":"cod",
  status_events:history.results,
  items:results.map(p=>({product_name:p.product_name,quantity:p.quantity,unit_price:p.price_bdt,line_total:p.line_total_bdt,variant_label:null})),
  whatsapp_notify_url:null,coupon_applied:false,referral_discount:0
 });
}
async function limitCOD(env,request,id){
 // Cloudflare sets this header on production traffic. Never accept anonymous
 // unidentifiable requests for real shipments; SHA-256 avoids storing IP text.
 const ip=request.headers.get("CF-Connecting-IP");
 if(!ip || ip.length>80)return false;
 const bytes=await crypto.subtle.digest("SHA-256",new TextEncoder().encode(id+":"+ip));
 const digest=Array.from(new Uint8Array(bytes),x=>x.toString(16).padStart(2,"0")).join("");
 const bucket=Math.floor(Date.now()/3600000);
 await env.DB.prepare("INSERT INTO commerce_checkout_limits(store_id,ip_digest,hour_bucket,attempts) VALUES(?,?,?,1) ON CONFLICT(store_id,ip_digest,hour_bucket) DO UPDATE SET attempts=attempts+1").bind(id,digest,bucket).run();
 const count=await env.DB.prepare("SELECT attempts FROM commerce_checkout_limits WHERE store_id=? AND ip_digest=? AND hour_bucket=?").bind(id,digest,bucket).first();
 return Number(count?.attempts||999)<=5;
}
async function checkout(env,request,id) {
 const store=await getStore(env,id,false);
 if(!store)return error(request,404,"Store not active");
 const isDemo=!!store.is_demo;
 if(!isDemo && !realCODReady(store,env))
   return error(request,409,"Real checkout is not enabled for this merchant. No payment should be sent.");
 const raw=await request.text();
 if(raw.length>10000)return error(request,413,"Order request too large");
 let data;
 try{data=JSON.parse(raw);}catch{return error(request,400,"Invalid JSON");}
 let contact=null;
 const requestId=isDemo?null:String(data.checkout_request_id||"").trim().toLowerCase();
 if(!isDemo){
  try{contact=normalizeCODContact(data);}catch(e){return error(request,422,e.message);}
  if(!/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(requestId))
   return error(request,422,"A valid unique checkout request id is required");
  // Return the first receipt before re-reading stock. Retry must not reserve twice.
  const existing=await env.DB.prepare("SELECT access_token,shipping_name,shipping_phone FROM commerce_orders WHERE store_id=? AND checkout_request_id=?").bind(id,requestId).first();
  if(existing){
   if(existing.shipping_name!==contact.name||existing.shipping_phone!==contact.phone)return error(request,409,"Checkout request id was already used for another contact");
   return orderDetails(env,request,id,existing.access_token);
  }
  try{if(!await limitCOD(env,request,id))return error(request,429,"Too many checkout attempts. Try again later.");}
  catch{return error(request,503,"Checkout protection unavailable. Please try later.");}
 } else if(data.payment_method && !["cod","demo"].includes(data.payment_method)) {
  return error(request,422,"Only example checkout is supported for demo stores. Do not send any money.");
 }
 const items=data.items;
 if(!Array.isArray(items)||items.length<1||items.length>12)
   return error(request,422,"An order requires 1-12 distinct products");
 let lineIds=new Set(),details=[],subtotal=0;
 for(const item of items){
  const pid=String(item.product_id||"");
  const qty=Number(item.quantity);
  if(!pid||lineIds.has(pid)||!Number.isInteger(qty)||qty<1||qty>10)
   return error(request,422,"Invalid product lines or quantities");
  lineIds.add(pid);
  const p=await env.DB.prepare("SELECT * FROM commerce_products WHERE id=? AND store_id=? AND is_listed=1").bind(pid,id).first();
  if(!p||p.stock_qty<qty)return error(request,409,"Product out of stock");
  const price=Number(p.price_bdt);
  if(!Number.isSafeInteger(price)||price<0)return error(request,409,"Invalid product price");
  subtotal+=qty*price;
  details.push({p,qty,price});
 }
 if(subtotal>500000)return error(request,422,"Order total exceeds the checkout limit");
 const oid=crypto.randomUUID();
 const token=crypto.randomUUID().replaceAll("-","")+crypto.randomUUID().replaceAll("-","");
 const no=(isDemo?"DEMO-":"COD-")+oid.slice(0,8).toUpperCase();
 const customerId=crypto.randomUUID();
 const customerName=isDemo?"Anonymous demo customer":contact.name;
 const statements=[
  env.DB.prepare("INSERT INTO commerce_customers(id,store_id,display_name) VALUES(?,?,?)")
   .bind(customerId,id,customerName),
  env.DB.prepare("INSERT INTO commerce_orders(id,store_id,order_number,access_token,status,subtotal_bdt,total_bdt,payment_method,shipping_name,shipping_phone,shipping_address,customer_id,checkout_request_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)")
   .bind(oid,id,no,token,"placed",subtotal,subtotal,isDemo?"demo":"cod",
    isDemo?"Demo customer":contact.name,isDemo?"":contact.phone,isDemo?"":contact.address,customerId,requestId),
  ...details.map(({p,qty,price})=>env.DB.prepare("INSERT INTO commerce_order_lines(order_id,product_id,product_name,quantity,price_bdt,line_total_bdt) VALUES(?,?,?,?,?,?)")
   .bind(oid,p.id,p.name,qty,price,qty*price))
 ];
 // The existing D1 order-line triggers validate stock/price and decrement
 // inventory as part of this single transactional batch.
 try{await env.DB.batch(statements);}
 catch{
  if(requestId){
   const existing=await env.DB.prepare("SELECT access_token,shipping_name,shipping_phone FROM commerce_orders WHERE store_id=? AND checkout_request_id=?").bind(id,requestId).first();
   if(existing){
    if(existing.shipping_name!==contact.name||existing.shipping_phone!==contact.phone)return error(request,409,"Checkout request id was already used for another contact");
    return orderDetails(env,request,id,existing.access_token);
   }
  }
  return error(request,409,"Stock or product price changed. Refresh the catalogue and retry.");
 }
 return orderDetails(env,request,id,token);
}

export default {
 async fetch(request,env){
  const path=new URL(request.url).pathname;
  const method=request.method;
  if(method==="OPTIONS")
   return new Response(null,{status:204,headers:cors(request)});
  try{
   const merchant=await merchantRouter(request,env,path,output,error);
   if(merchant!==null)return merchant;
   if(path==="/health"&&method==="GET") {
    const row=await env.DB.prepare("SELECT COUNT(*) n FROM commerce_stores WHERE is_active=1").first();
    const pro=await env.DB.prepare("SELECT COUNT(*) n FROM commerce_products WHERE is_listed=1").first();
    return output(request,{status:"ok",database:"Cloudflare D1",scope:"demo_and_approved_cod",stores:row.n,products:pro.n,live_payments:false,real_cod_feature_enabled:env.ENABLE_REAL_COD==="true"});
   }
   if((path==="/api/public/store"||path==="/api/public/store/")&&method==="GET") {
    const {results}=await env.DB.prepare("SELECT * FROM commerce_stores WHERE is_active=1 ORDER BY name").all();
    return output(request,results.map(s=>baseView(s,env)));
   }
   if(path==="/api/public/store/diagnostics"&&method==="GET") {
    const stores=await env.DB.prepare("SELECT COUNT(*) n FROM commerce_stores WHERE is_active=1").first();
    const products=await env.DB.prepare("SELECT COUNT(*) n FROM commerce_products WHERE is_listed=1").first();
    return output(request,{active_stores:stores.n,listed_products:products.n,catalog_ready:!!(stores.n&&products.n),source:"cloudflare_d1",mode:"demo"});
   }
   if(path.startsWith("/api/public/store/slug/")&&method==="GET"){
    const slug=decodeURIComponent(path.slice("/api/public/store/slug/".length));
    const store=await getStore(env,safe(slug),true);
    return store?output(request,await storeResponse(env,store)):error(request,404,"Store not found");
   }
   if(path.startsWith("/api/public/store/")&&method==="GET") {
    const id=decodeURIComponent(path.slice("/api/public/store/".length));
    if(!id.includes("/")){
      const store=await getStore(env,safe(id),false);
      return store?output(request,await storeResponse(env,store)):error(request,404,"Store not found");
    }
   }
   const m=path.match(/^\/api\/public\/orders\/([^/]+)(?:\/(.*))?$/);
   if(m){
    const id=decodeURIComponent(m[1]), action=m[2]||"";
    if(method==="GET"&&action==="products") {
     const store=await getStore(env,id,false);
     if(!store)return error(request,404,"Store not found");
     const {results}=await env.DB.prepare("SELECT * FROM commerce_products WHERE store_id=? AND is_listed=1 ORDER BY name").bind(id).all();
     return output(request,results.map(p=>productView(p,!!store.is_demo)));
    }
    if(method==="POST"&&!action)return checkout(env,request,id);
    if(method==="GET"&&action.startsWith("status/"))
      return orderDetails(env,request,id,action.slice(7));
    if(method==="POST"&&action.startsWith("cancel/")) {
     const token=action.slice(7);
     const d=await env.DB.prepare("UPDATE commerce_orders SET status='cancelled' WHERE store_id=? AND access_token=? AND status='placed'").bind(id,token).run();
     if(!d.meta?.changes)return error(request,409,"Order cannot be cancelled");
     return orderDetails(env,request,id,token);
    }
    if(method==="POST"&&action.startsWith("payment-screenshot/"))
      return error(request,501,"Demo store does not accept payment evidence.");
   }
   return error(request,404,"Route not found");
  }catch(e){
   console.error("bsmart-commerce route failure",path,e?.message||e);
   return error(request,500,"Commerce service temporarily unavailable");
  }
 }
};
