import { merchantRouter } from "./merchant-routes.js";
import { customerRouter, customerFromToken } from "./customer-routes.js";
import { platformAdminRouter } from "./platform-admin-routes.js";
import { defaultOrderStatusNote } from "./order-workflow.js";
import { isPublicStore, INTERNAL_TEST_STORE_SLUGS } from "./store-visibility.js";
import { customerAssistantRouter } from "./assistant-routes.js";
/*
B-SMART Cloudflare Primary Commerce API.
 The existing bsmart-commerce D1 database is the source of truth for storefront,
 customer, merchant, order, coupon and inventory records. Only verified,
 platform-approved merchant stores are publicly listed. Checkout currently
 supports cash-on-delivery and merchant-managed fulfilment; no online payment
 gateway, courier API or automated refund provider is configured. Legacy FastAPI
 operational modules remain a separate, explicitly staged migration.
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
async function hashValue(value){
 const bytes=await crypto.subtle.digest("SHA-256",new TextEncoder().encode(String(value)));
 return Array.from(new Uint8Array(bytes),b=>b.toString(16).padStart(2,"0")).join("");
}
export function calculateCouponDiscount(coupon,subtotal,now=Date.now()){
 const amount=Number(subtotal),current=typeof now==="number"?now:Date.parse(now);
 if(!coupon||!Number(coupon.is_active))throw new Error("Coupon is not active");
 if(!Number.isSafeInteger(amount)||amount<0)throw new Error("Invalid order subtotal");
 const starts=coupon.starts_at?Date.parse(coupon.starts_at):null;
 const ends=coupon.ends_at?Date.parse(coupon.ends_at):null;
 if(starts!==null&&Number.isFinite(starts)&&current<starts)throw new Error("Coupon is not active yet");
 if(ends!==null&&Number.isFinite(ends)&&current>ends)throw new Error("Coupon has expired");
 if(amount<Number(coupon.min_order_bdt||0))throw new Error("Minimum order amount is not reached");
 const value=Number(coupon.discount_value);
 if(!Number.isSafeInteger(value)||value<=0)throw new Error("Invalid coupon discount");
 let discount=coupon.discount_type==="percent"?Math.floor(amount*value/100):coupon.discount_type==="fixed"?value:NaN;
 if(!Number.isFinite(discount))throw new Error("Invalid coupon type");
 if(coupon.max_discount_bdt!==null&&coupon.max_discount_bdt!==undefined)discount=Math.min(discount,Number(coupon.max_discount_bdt));
 discount=Math.max(0,Math.min(amount,Math.floor(discount)));
 if(!discount)throw new Error("Coupon does not apply to this order");
 return {code:String(coupon.code),discount_amount:discount,discount_type:coupon.discount_type};
}
async function allowCouponPreview(env,store,request){
 const ip=String(request.headers.get("CF-Connecting-IP")||"unknown").slice(0,80);
 const key=await hashValue("coupon-preview:"+store.id+":"+ip);
 const windowId=Math.floor(Date.now()/60000);
 await env.DB.prepare("INSERT INTO commerce_ai_rate_limits(key_hash,window_id,request_count) VALUES(?,?,1) ON CONFLICT(key_hash) DO UPDATE SET request_count=CASE WHEN commerce_ai_rate_limits.window_id=excluded.window_id THEN commerce_ai_rate_limits.request_count+1 ELSE 1 END,window_id=excluded.window_id,updated_at=CURRENT_TIMESTAMP").bind(key,windowId).run();
 const row=await env.DB.prepare("SELECT request_count FROM commerce_ai_rate_limits WHERE key_hash=?").bind(key).first();
 return Number(row?.request_count||0)<=12;
}
async function couponForOrder(env,store,code,subtotal,customerKeyHash=null){
 const normalised=String(code||"").trim().toUpperCase();
 if(!/^[A-Z0-9_-]{3,32}$/.test(normalised))throw new Error("Enter a valid coupon code");
 const coupon=await env.DB.prepare("SELECT * FROM commerce_coupons WHERE store_id=? AND code=? AND is_active=1 LIMIT 1").bind(store.id,normalised).first();
 if(!coupon)throw new Error("Coupon code is invalid or inactive");
 const calculated=calculateCouponDiscount(coupon,subtotal);
 if(coupon.usage_limit!==null&&coupon.usage_limit!==undefined){
  const used=await env.DB.prepare("SELECT COUNT(*) AS n FROM commerce_coupon_redemptions WHERE coupon_id=?").bind(coupon.id).first();
  if(Number(used?.n||0)>=Number(coupon.usage_limit))throw new Error("Coupon usage limit has been reached");
 }
 if(customerKeyHash&&coupon.per_customer_limit!==null&&coupon.per_customer_limit!==undefined){
  const used=await env.DB.prepare("SELECT COUNT(*) AS n FROM commerce_coupon_redemptions WHERE coupon_id=? AND customer_key_hash=?").bind(coupon.id,customerKeyHash).first();
  if(Number(used?.n||0)>=Number(coupon.per_customer_limit))throw new Error("You have already used this coupon the allowed number of times");
 }
 return {coupon,...calculated};
}

// Accept ordinary Bangladeshi/international phone formatting while requiring
// 7–15 digits. Keeping this in a named helper makes checkout validation testable.
export function isValidShippingPhone(value) {
 const phone=String(value??"").trim();
 const digits=phone.replace(/\D/g,"");
 return /^\+?[0-9()\s-]{7,20}$/.test(phone) && digits.length>=7 && digits.length<=15;
}
const baseView=(s)=>({
  organization_id:s.id,slug:s.slug,is_demo:!!s.is_demo,is_active:!!s.is_active,
  display_name:s.name,tagline:s.tagline,logo_data_url:null,cover_data_url:null,
  category:s.category,area:s.area,theme_preset:s.theme,theme_color:s.color,
  phone:null,address:null,show_hours:false,hours_json:null,show_price:true,
  show_stock_level:"available_only",payment_cod:true,payment_bkash:false,
  payment_nagad:false,bkash_number:null,nagad_number:null,
  sslcz_store_id:null,bkash_app_key:null,nagad_merchant_id:null,
  min_order_bdt:null,delivery_note:s.delivery_note||"",
  delivery_inside_dhaka:0,delivery_outside_dhaka:0,delivery_free_above:null,
  allow_zone_restriction:false,allowed_divisions:null,
  meta_title:s.name,meta_desc:s.tagline
});
const productView=(p)=>({
  id:p.id,name:p.name,sku:p.sku,unit:p.unit_label||"pcs",price:p.price_bdt,
  selling_price:p.price_bdt,description:p.description||"",
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
 const row=await env.DB.prepare(sql).bind(term).first();
 return isPublicStore(row)?row:null;
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
  status:order.status,payment_status:order.payment_status||(store?.is_demo?"demo_no_payment":(order.payment_method==="cod"?(order.status==="cancelled"?"cancelled_no_payment":"pending_cod"):"unpaid")),payment_received_at:order.payment_received_at||null,payment_received_by:order.payment_received_by||null,payment_note:order.payment_note||null,status_note:order.status_note||defaultOrderStatusNote(order.status,!!store?.is_demo),
  placed_at:order.placed_at,issued_at:order.placed_at,
  shipping_name:order.shipping_name||"",shipping_phone:order.shipping_phone||"",shipping_address:order.shipping_address||"",
  subtotal:order.subtotal_bdt,tax_amount:0,delivery_fee:0,discount_amount:Number(order.coupon_discount_bdt||0),
  coupon_code:order.coupon_code||null,coupon_discount:Number(order.coupon_discount_bdt||0),total:order.total_bdt,organization_id:id,
  store_slug:store?.slug||null,store_name:store?.name||"দোকান",is_demo:!!store?.is_demo,
  payment_method:order.payment_method||"demo",
  items:results.map(p=>({product_id:p.product_id,description:p.product_name,product_name:p.product_name,quantity:p.quantity,unit_price:p.price_bdt,line_total:p.line_total_bdt,variant_label:null})),
  whatsapp_notify_url:null,coupon_applied:!!order.coupon_code,referral_discount:0
 });
}
async function checkout(env,request,id) {
 const store=await getStore(env,id,false);
 if(!store)return error(request,404,"Store not active");
 const size=Number(request.headers.get("content-length")||0);
 if(size>10000)return error(request,413,"Order request too large");
 let data;
 try{data=await request.json();}catch{return error(request,400,"Invalid JSON");}
 if(store.is_demo && data.payment_method && !["cod","demo"].includes(data.payment_method))
   return error(request,422,"Demo stores do not accept real payments.");
 if(!store.is_demo && data.payment_method!=="cod")
   return error(request,422,"This store accepts cash on delivery only; online payments are not configured.");
 const shippingName=safe(data.shipping_name||(store.is_demo?"Demo customer":""));
 const shippingPhone=String(data.shipping_phone||"").trim().slice(0,30);
 const shippingAddress=String(data.shipping_address||"").trim().slice(0,500);
 if(!store.is_demo && (shippingName.length<2 || !isValidShippingPhone(shippingPhone) || shippingAddress.length<8))
   return error(request,422,"Enter a valid customer name, phone number and delivery address for COD.");
 const customerToken=String(data.store_customer_token||data.customer_token||"").trim();
 let account=null;
 if(customerToken){
  account=await customerFromToken(env,customerToken);
  if(!account)return error(request,401,"Customer session expired. Sign in again before placing the order.");
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
 if(subtotal>(store.is_demo?500000:5000000))return error(request,422,store.is_demo?"Demo order total too high":"Order total exceeds the store limit.");
  const couponCode=String(data.coupon_code||"").trim().toUpperCase();
  let coupon=null,couponDiscount=0,customerKeyHash=null;
  if(couponCode){
   if(store.is_demo)return error(request,422,"Coupons are not available on sample stores.");
     if(!await allowCouponPreview(env,store,request))return error(request,429,"Too many coupon checks. Please wait a minute and try again.");
   const customerIdentity=account?.id?"account:"+account.id:"phone:"+shippingPhone.replace(/[^0-9]/g,"");
   customerKeyHash=await hashValue(store.id+":"+customerIdentity);
   try{
    const result=await couponForOrder(env,store,couponCode,subtotal,customerKeyHash);
    coupon=result.coupon;couponDiscount=result.discount_amount;
   }catch(e){return error(request,422,e.message||"Coupon could not be applied");}
  }
  const orderTotal=subtotal-couponDiscount;
 // A single D1.batch call is a transaction. SQL triggers reject stale/oversold
 // products and roll back every line and header together if stock runs out.
 const oid=crypto.randomUUID();
 const token=crypto.randomUUID().replaceAll("-","")+crypto.randomUUID().replaceAll("-","");
 const no=(store.is_demo?"DEMO-":"ORD-")+oid.slice(0,8).toUpperCase();
 const customerId=crypto.randomUUID();
 const paymentMethod=store.is_demo?"demo":"cod";
 const statements=[
  env.DB.prepare("INSERT INTO commerce_customers(id,store_id,display_name) VALUES(?,?,?)")
   .bind(customerId,id,shippingName),
  env.DB.prepare("INSERT INTO commerce_orders(id,store_id,order_number,access_token,status,subtotal_bdt,total_bdt,payment_method,shipping_name,shipping_phone,shipping_address,customer_id,account_id,coupon_code,coupon_discount_bdt) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)")
   .bind(oid,id,no,token,"placed",subtotal,orderTotal,paymentMethod,shippingName,shippingPhone,shippingAddress,customerId,account?.id||null,coupon?.code||null,couponDiscount),
  ...details.map(({p,qty,price})=>env.DB.prepare("INSERT INTO commerce_order_lines(order_id,product_id,product_name,quantity,price_bdt,line_total_bdt) VALUES(?,?,?,?,?,?)")
   .bind(oid,p.id,p.name,qty,price,qty*price))
 ];
 if(coupon)statements.push(env.DB.prepare("INSERT INTO commerce_coupon_redemptions(id,coupon_id,store_id,order_id,account_id,customer_key_hash,discount_bdt) VALUES(?,?,?,?,?,?,?)")
  .bind(crypto.randomUUID(),coupon.id,id,oid,account?.id||null,customerKeyHash,couponDiscount));
 try{await env.DB.batch(statements);}
 catch(e){const message=String(e?.message||"");if(message.includes("COUPON_USAGE_LIMIT"))return error(request,409,"Coupon usage limit was reached. Please refresh and try another code.");if(message.includes("COUPON_CUSTOMER_LIMIT"))return error(request,409,"This coupon has already been used the allowed number of times.");return error(request,409,"Stock or coupon availability changed during checkout. Refresh and retry.");}
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
   const assistant=await customerAssistantRouter(request,env,path,output,error);
   if(assistant!==null)return assistant;
   const customer=await customerRouter(request,env,path,output,error);
   if(customer!==null)return customer;
   const merchant=await merchantRouter(request,env,path,output,error);
   if(merchant!==null)return merchant;
   if(path==="/health"&&method==="GET") {
    const excluded=[...INTERNAL_TEST_STORE_SLUGS],marks=excluded.map(()=>"?").join(",");
    const row=await env.DB.prepare("SELECT COUNT(*) n FROM commerce_stores WHERE is_active=1 AND slug NOT IN ("+marks+")").bind(...excluded).first();
    const pro=await env.DB.prepare("SELECT COUNT(*) n FROM commerce_products p JOIN commerce_stores s ON s.id=p.store_id WHERE p.is_listed=1 AND s.is_active=1 AND s.slug NOT IN ("+marks+")").bind(...excluded).first();
    return output(request,{status:"ok",database:"Cloudflare D1",scope:"public_storefronts",stores:row.n,products:pro.n,live_payments:false,assistant_enabled:env.AI_ENABLED!=="false"&&!!env.AI});
   }
   if((path==="/api/public/store"||path==="/api/public/store/")&&method==="GET") {
    const excluded=[...INTERNAL_TEST_STORE_SLUGS],marks=excluded.map(()=>"?").join(",");
    const {results}=await env.DB.prepare("SELECT * FROM commerce_stores WHERE is_active=1 AND slug NOT IN ("+marks+") ORDER BY name").bind(...excluded).all();
    return output(request,results.filter(isPublicStore).map(baseView));
   }
   if(path==="/api/public/store/diagnostics"&&method==="GET") {
    const excluded=[...INTERNAL_TEST_STORE_SLUGS],marks=excluded.map(()=>"?").join(",");
    const stores=await env.DB.prepare("SELECT COUNT(*) n FROM commerce_stores WHERE is_active=1 AND slug NOT IN ("+marks+")").bind(...excluded).first();
    const products=await env.DB.prepare("SELECT COUNT(*) n FROM commerce_products p JOIN commerce_stores s ON s.id=p.store_id WHERE p.is_listed=1 AND s.is_active=1 AND s.slug NOT IN ("+marks+")").bind(...excluded).first();
    return output(request,{active_stores:stores.n,listed_products:products.n,catalog_ready:!!(stores.n&&products.n),source:"cloudflare_d1",mode:"cloudflare_primary"});
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
       const couponRoute=/^\/api\/public\/coupons\/([^/]+)\/validate$/.exec(path);
    if(method==="POST"&&couponRoute){
     const id=decodeURIComponent(couponRoute[1]),store=await getStore(env,id,false);
     if(!store)return error(request,404,"Store not found");
     if(store.is_demo)return error(request,422,"Coupons are not available on sample stores.");
      if(!await allowCouponPreview(env,store,request))return error(request,429,"Too many coupon checks. Please wait a minute and try again.");
     const raw=await request.text();if(raw.length>2000)return error(request,413,"Coupon request too large");
     let body;try{body=JSON.parse(raw);}catch{return error(request,400,"Invalid JSON");}
     const subtotal=Number(body.order_subtotal);
     if(!Number.isSafeInteger(subtotal)||subtotal<0||subtotal>5000000)return error(request,422,"Invalid order subtotal");
     let customerKeyHash=null;
     const bearer=/^Bearer ([a-f0-9]{64})$/i.exec(request.headers.get("Authorization")||"");
     if(bearer){
      const account=await customerFromToken(env,bearer[1]);
      if(account)customerKeyHash=await hashValue(store.id+":account:"+account.id);
     }
     try{
      const result=await couponForOrder(env,store,body.code,subtotal,customerKeyHash);
      return output(request,{valid:true,code:result.code,discount_amount:result.discount_amount,discount_type:result.discount_type});
     }catch(e){return error(request,422,e.message||"Coupon could not be applied");}
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
