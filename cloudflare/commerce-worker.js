import { merchantRouter } from "./merchant-routes.js";
import { customerRouter, customerFromToken } from "./customer-routes.js";
import { platformAdminRouter } from "./platform-admin-routes.js";
import { defaultOrderStatusNote } from "./order-workflow.js";
/*
 B-SMART Cloudflare D1 Commerce API.
 Public demo-store catalogues, customer accounts, saved addresses, account-linked
 order history, support chat and demo-only checkout. Account contact/address data
 is stored in D1; users must use synthetic information until production security
 and privacy controls are complete. No real payment, physical delivery or refund.
 D1 is the source of truth for this demo catalogue only. Legacy FastAPI business
 and historical customer records are separate and are not synchronized.
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
    "Access-Control-Allow-Methods":"GET,POST,PATCH,PUT,DELETE,OPTIONS",
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
const baseView=(s)=>({
  organization_id:s.id,slug:s.slug,is_demo:!!s.is_demo,is_active:!!s.is_active,
  display_name:s.name,tagline:s.tagline,logo_data_url:null,cover_data_url:null,
  category:s.category,area:s.area,theme_preset:s.theme,theme_color:s.color,
  phone:null,address:null,show_hours:false,hours_json:null,show_price:true,
  show_stock_level:"available_only",payment_cod:true,payment_bkash:false,
  payment_nagad:false,bkash_number:null,nagad_number:null,
  sslcz_store_id:null,bkash_app_key:null,nagad_merchant_id:null,
  min_order_bdt:null,delivery_note:s.delivery_note||"Demo only",
  delivery_inside_dhaka:0,delivery_outside_dhaka:0,delivery_free_above:null,
  allow_zone_restriction:false,allowed_divisions:null,
  meta_title:s.name,meta_desc:s.tagline
});
const productView=(p)=>({
  id:p.id,name:p.name,sku:p.sku,unit:p.unit_label||"pcs",price:p.price_bdt,
  selling_price:p.price_bdt,description:p.description||"পরীক্ষামূলক পণ্য; বাস্তব বিক্রেতা বা ডেলিভারি যাচাই করা হয়নি",
  brand:p.brand||null,compare_at_price:p.compare_at_price_bdt||null,sale_price:null,sale_end:null,image_data_url:p.image_url||null,
  tags:(()=>{try{return JSON.parse(p.tags||"[]")}catch{return []}})(),
  is_featured:!!p.is_featured,sort_order:0,max_order_qty:Math.min(p.stock_qty,10),
  review_avg:Number(p.review_avg||0),review_count:Number(p.review_count||0),
  variants:[],in_stock:p.stock_qty>0,quantity:p.stock_qty,category:p.category
});
async function getStore(env,term,slugMode) {
 const sql=slugMode?
  "SELECT * FROM commerce_stores WHERE slug=? AND is_active=1 LIMIT 1":
  "SELECT * FROM commerce_stores WHERE id=? AND is_active=1 LIMIT 1";
 return env.DB.prepare(sql).bind(term).first();
}
async function storeResponse(env,store) {
 const {results}=await env.DB.prepare(
  "SELECT p.*,COALESCE(AVG(r.rating),0) AS review_avg,COUNT(r.id) AS review_count " +
  "FROM commerce_products p LEFT JOIN commerce_product_reviews r ON r.product_id=p.id AND r.store_id=p.store_id " +
  "WHERE p.store_id=? AND p.is_listed=1 GROUP BY p.id ORDER BY p.is_featured DESC,p.name"
 ).bind(store.id).all();
 return {...baseView(store),products:results.map(productView)};
}
async function orderDetails(env,request,id,token) {
 const order=await env.DB.prepare("SELECT * FROM commerce_orders WHERE store_id=? AND access_token=? LIMIT 1").bind(id,token).first();
 if(!order)return error(request,404,"Order not found");
 const [{results},store]=await Promise.all([
  env.DB.prepare("SELECT product_id,product_name,quantity,price_bdt,line_total_bdt FROM commerce_order_lines WHERE order_id=?").bind(order.id).all(),
  env.DB.prepare("SELECT slug,name,is_demo FROM commerce_stores WHERE id=?").bind(id).first()
 ]);
 return output(request,{
  id:order.id,order_number:order.order_number,document_number:order.order_number,access_token:order.access_token,
  status:order.status,payment_status:"demo_no_payment",status_note:order.status_note||defaultOrderStatusNote(order.status,!!store?.is_demo),
  placed_at:order.placed_at,issued_at:order.placed_at,
  shipping_name:order.shipping_name||"",shipping_phone:order.shipping_phone||"",shipping_address:order.shipping_address||"",
  subtotal:order.subtotal_bdt,tax_amount:0,delivery_fee:0,discount_amount:0,
  coupon_code:null,coupon_discount:0,total:order.total_bdt,organization_id:id,
  store_slug:store?.slug||null,store_name:store?.name||"পরীক্ষামূলক দোকান",is_demo:!!store?.is_demo,
  payment_method:order.payment_method||"demo",
  items:results.map(p=>({product_id:p.product_id,description:p.product_name,product_name:p.product_name,quantity:p.quantity,unit_price:p.price_bdt,line_total:p.line_total_bdt,variant_label:null})),
  whatsapp_notify_url:null,coupon_applied:false,referral_discount:0
 });
}
async function checkout(env,request,id) {
 const store=await getStore(env,id,false);
 if(!store)return error(request,404,"Store not active");
 if(!store.is_demo)return error(request,409,"Merchant checkout is not yet enabled on this D1 service");
 const size=Number(request.headers.get("content-length")||0);
 if(size>10000)return error(request,413,"Order request too large");
 let data;
 try{data=await request.json();}catch{return error(request,400,"Invalid JSON");}
 if(data.payment_method && !["cod","demo"].includes(data.payment_method))
   return error(request,422,"Only free demo/COD checkout is supported. Do not make a payment.");
 const shippingName=safe(data.shipping_name||"Demo customer");
 const shippingPhone=String(data.shipping_phone||"").trim().slice(0,30);
 const shippingAddress=String(data.shipping_address||"").trim().slice(0,500);
 const customerToken=String(data.store_customer_token||data.customer_token||"").trim();
 let account=null;
 if(customerToken){
  account=await customerFromToken(env,customerToken);
  if(!account)return error(request,401,"Customer session expired. Sign in again before placing this demo order.");
 }
 const items=data.items;
 if(!Array.isArray(items)||items.length<1||items.length>12)
   return error(request,422,"An order requires 1-12 distinct products");
 let lineIds=new Set(),details=[],subtotal=0;
 for(const item of items) {
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
 if(subtotal>500000)return error(request,422,"Demo order total too high");
 // A single D1.batch call is a transaction. SQL triggers reject stale/oversold
 // products and roll back every line and header together if stock runs out.
 const oid=crypto.randomUUID();
 const token=crypto.randomUUID().replaceAll("-","")+crypto.randomUUID().replaceAll("-","");
 const no="DEMO-"+oid.slice(0,8).toUpperCase();
 const customerId=crypto.randomUUID();
 const statements=[
  env.DB.prepare("INSERT INTO commerce_customers(id,store_id,display_name) VALUES(?,?,?)")
   .bind(customerId,id,shippingName),
  env.DB.prepare("INSERT INTO commerce_orders(id,store_id,order_number,access_token,status,subtotal_bdt,total_bdt,payment_method,shipping_name,shipping_phone,shipping_address,customer_id,account_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)")
   .bind(oid,id,no,token,"placed",subtotal,subtotal,"demo",shippingName,shippingPhone,shippingAddress,customerId,account?.id||null),
  ...details.map(({p,qty,price})=>env.DB.prepare("INSERT INTO commerce_order_lines(order_id,product_id,product_name,quantity,price_bdt,line_total_bdt) VALUES(?,?,?,?,?,?)")
   .bind(oid,p.id,p.name,qty,price,qty*price))
 ];
 try{await env.DB.batch(statements);}
 catch(e){return error(request,409,"Stock changed during checkout. Refresh the catalogue and retry.");}
 return orderDetails(env,request,id,token);
}
export default {
 async fetch(request,env){
  const path=new URL(request.url).pathname;
  const method=request.method;
  if(method==="OPTIONS")
   return new Response(null,{status:204,headers:cors(request)});
  try{
    const platformAdmin=await platformAdminRouter(request,env,path,output,error);
    if(platformAdmin!==null)return platformAdmin;
   const customer=await customerRouter(request,env,path,output,error);
   if(customer!==null)return customer;
   const merchant=await merchantRouter(request,env,path,output,error);
   if(merchant!==null)return merchant;
   if(path==="/health"&&method==="GET") {
    const row=await env.DB.prepare("SELECT COUNT(*) n FROM commerce_stores WHERE is_active=1").first();
    const pro=await env.DB.prepare("SELECT COUNT(*) n FROM commerce_products WHERE is_listed=1").first();
    return output(request,{status:"ok",database:"Cloudflare D1",scope:"demo_storefronts",stores:row.n,products:pro.n,live_payments:false});
   }
   if((path==="/api/public/store"||path==="/api/public/store/")&&method==="GET") {
    const {results}=await env.DB.prepare("SELECT * FROM commerce_stores WHERE is_active=1 ORDER BY name").all();
    return output(request,results.map(baseView));
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
     const {results}=await env.DB.prepare(
      "SELECT p.*,COALESCE(AVG(r.rating),0) AS review_avg,COUNT(r.id) AS review_count " +
      "FROM commerce_products p LEFT JOIN commerce_product_reviews r ON r.product_id=p.id AND r.store_id=p.store_id " +
      "WHERE p.store_id=? AND p.is_listed=1 GROUP BY p.id ORDER BY p.name"
     ).bind(id).all();
     return output(request,results.map(productView));
    }
    if(method==="POST"&&!action)return checkout(env,request,id);
    if(method==="GET"&&action.startsWith("status/"))
      return orderDetails(env,request,id,action.slice(7));
    if(method==="POST"&&action.startsWith("cancel/")) {
     const token=action.slice(7);
     const d=await env.DB.prepare("UPDATE commerce_orders SET status='cancelled',status_note='ক্রেতার অনুরোধে অর্ডার বাতিল হয়েছে' WHERE store_id=? AND access_token=? AND status='placed'").bind(id,token).run();
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
