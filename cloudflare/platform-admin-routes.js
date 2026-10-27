import { canTransitionOrderStatus, defaultOrderStatusNote } from "./order-workflow.js";

/* Privileged controls for the isolated Cloudflare D1 commerce demo.
 * Configure PLATFORM_ADMIN_KEY as a Worker secret; never hard-code it here.
 */
const encoder = new TextEncoder();
const hex = bytes => Array.from(new Uint8Array(bytes), b => b.toString(16).padStart(2,"0")).join("");
async function digest(value) {
  return hex(await crypto.subtle.digest("SHA-256", encoder.encode(String(value || ""))));
}
async function equalSecret(candidate, expected) {
  if (!candidate || !expected) return false;
  const [a,b] = await Promise.all([digest(candidate),digest(expected)]);
  let diff = a.length ^ b.length;
  for (let i=0;i<Math.max(a.length,b.length);i++) diff |= (a.charCodeAt(i)||0) ^ (b.charCodeAt(i)||0);
  return diff === 0;
}
function short(value,n=250){return String(value??"").trim().slice(0,n);}
async function readBody(req) {
  const text=await req.text();
  if(text.length>15000)throw new Error("Payload too large");
  try{return JSON.parse(text);}catch{throw new Error("Invalid JSON");}
}
async function audit(env,action,targetType,targetId,details) {
  await env.DB.prepare("INSERT INTO commerce_platform_admin_audit(id,action,target_type,target_id,details) VALUES(?,?,?,?,?)")
    .bind(crypto.randomUUID(),action,targetType,targetId||null,JSON.stringify(details||{})).run();
}
export async function platformAdminRouter(req,env,path,output,error) {
  if(!path.startsWith("/api/platform-admin/"))return null;
  if(!env.PLATFORM_ADMIN_KEY || String(env.PLATFORM_ADMIN_KEY).length<32)
    return error(req,503,"Platform admin access is not configured on this Worker");
  const bearer=req.headers.get("Authorization")||"";
  const candidate=/^Bearer (.+)$/.exec(bearer)?.[1]||"";
  if(!await equalSecret(candidate,env.PLATFORM_ADMIN_KEY))
    return error(req,401,"Platform administrator authentication required");
  const method=req.method;
  try {
    if(method==="GET"&&path==="/api/platform-admin/overview") {
      const row=await env.DB.prepare(
        "SELECT (SELECT COUNT(*) FROM commerce_stores) AS stores_total,"+
        "(SELECT COUNT(*) FROM commerce_stores WHERE is_active=1) AS stores_active,"+
        "(SELECT COUNT(*) FROM commerce_products) AS products_total,"+
        "(SELECT COUNT(*) FROM commerce_products WHERE is_listed=1) AS products_listed,"+
        "(SELECT COUNT(*) FROM commerce_customer_accounts) AS customers_total,"+
        "(SELECT COUNT(*) FROM commerce_orders) AS orders_total,"+
        "(SELECT COUNT(*) FROM commerce_orders WHERE status='cancelled') AS orders_cancelled,"+
        "(SELECT COALESCE(SUM(o.total_bdt),0) FROM commerce_orders o JOIN commerce_stores s ON s.id=o.store_id WHERE o.status!='cancelled' AND s.is_demo=1) AS demo_order_value_bdt,"+
        "(SELECT COALESCE(SUM(o.total_bdt),0) FROM commerce_orders o JOIN commerce_stores s ON s.id=o.store_id WHERE o.status!='cancelled' AND s.is_demo=0 AND o.payment_method='cod') AS cod_order_value_bdt,"+
        "(SELECT COALESCE(SUM(o.total_bdt),0) FROM commerce_orders o JOIN commerce_stores s ON s.id=o.store_id WHERE o.status!='cancelled' AND s.is_demo=0 AND o.payment_status='paid') AS cod_paid_total_bdt,"+
        "(SELECT COALESCE(SUM(o.total_bdt),0) FROM commerce_orders o JOIN commerce_stores s ON s.id=o.store_id WHERE o.status!='cancelled' AND s.is_demo=0 AND o.payment_status='pending_cod') AS cod_pending_total_bdt,"+
        "(SELECT COUNT(*) FROM commerce_order_returns WHERE status IN ('requested','approved')) AS returns_open,"+
        "(SELECT COUNT(*) FROM commerce_customer_messages WHERE sender_role='customer' AND read_by_merchant_at IS NULL) AS unread_customer_messages"
      ).first();
      return output(req,{scope:"Cloudflare D1 storefronts; approved operational stores are COD/manual fulfilment only",real_payments:false,real_delivery:false,manual_cod_enabled:true,metrics:row});
    }
    if(method==="GET"&&path==="/api/platform-admin/stores") {
      const {results}=await env.DB.prepare(
        "SELECT s.id,s.slug,s.name,s.category,s.area,s.is_demo,s.is_active,s.created_at,a.email AS owner_email,"+
        "(SELECT COUNT(*) FROM commerce_products p WHERE p.store_id=s.id) AS products_count,"+
        "(SELECT COUNT(*) FROM commerce_orders o WHERE o.store_id=s.id) AS orders_count "+
        "FROM commerce_stores s LEFT JOIN merchant_accounts a ON a.id=s.owner_id ORDER BY s.created_at DESC LIMIT 500"
      ).all();
      return output(req,{stores:results});
    }
    if(method==="GET"&&path==="/api/platform-admin/customers") {
      const {results}=await env.DB.prepare(
        "SELECT a.id,a.display_name,a.email,a.phone,a.created_at,"+
        "(SELECT COUNT(*) FROM commerce_orders o WHERE o.account_id=a.id) AS orders_count,"+
        "(SELECT COUNT(*) FROM commerce_customer_messages m WHERE m.account_id=a.id) AS messages_count "+
        "FROM commerce_customer_accounts a ORDER BY a.created_at DESC LIMIT 500"
      ).all();
      return output(req,{customers:results});
    }
    if(method==="GET"&&path==="/api/platform-admin/orders") {
      const {results}=await env.DB.prepare(
        "SELECT o.id,o.order_number,o.status,o.status_note,o.cancellation_reason,o.subtotal_bdt,o.total_bdt,o.payment_method,o.payment_status,o.payment_received_at,o.payment_received_by,o.payment_note,o.placed_at,o.shipping_name,o.shipping_phone,o.shipping_address,"+
        "s.id AS store_id,s.slug AS store_slug,s.name AS store_name,a.id AS account_id,a.display_name AS customer_name,a.email AS customer_email "+
        "FROM commerce_orders o JOIN commerce_stores s ON s.id=o.store_id "+
        "LEFT JOIN commerce_customer_accounts a ON a.id=o.account_id ORDER BY o.placed_at DESC LIMIT 500"
      ).all();
      return output(req,{orders:results,note:"Demo order values are not revenue. COD collection is merchant-confirmed and is not independently verified by this system."});
    }
    if(method==="GET"&&path==="/api/platform-admin/returns") {
      const {results}=await env.DB.prepare(
        "SELECT r.id,r.reason,r.customer_note,r.merchant_note,r.status,r.requested_at,r.updated_at,o.order_number,o.total_bdt,"+
        "s.id AS store_id,s.slug AS store_slug,s.name AS store_name,a.id AS account_id,a.display_name AS customer_name,a.email AS customer_email "+
        "FROM commerce_order_returns r JOIN commerce_orders o ON o.id=r.order_id JOIN commerce_stores s ON s.id=r.store_id "+
        "JOIN commerce_customer_accounts a ON a.id=r.account_id ORDER BY r.requested_at DESC LIMIT 500"
      ).all();
      return output(req,{returns:results,note:"Return processing does not issue a financial refund."});
    }
    if(method==="GET"&&path==="/api/platform-admin/audit") {
      const {results}=await env.DB.prepare("SELECT id,action,target_type,target_id,details,created_at FROM commerce_platform_admin_audit ORDER BY created_at DESC LIMIT 200").all();
      return output(req,{audit:results});
    }
    const storeMatch=path.match(/^\/api\/platform-admin\/stores\/([^/]+)$/);
    if(method==="PATCH"&&storeMatch) {
      const id=decodeURIComponent(storeMatch[1]),body=await readBody(req);
      if(body.is_active===undefined && body.is_demo===undefined)return error(req,422,"Provide is_active or is_demo");
      if(body.is_active!==undefined && typeof body.is_active!=="boolean")return error(req,422,"is_active must be true or false");
      if(body.is_demo!==undefined && typeof body.is_demo!=="boolean")return error(req,422,"is_demo must be true or false");
      const store=await env.DB.prepare("SELECT id,slug,name,is_active,is_demo,owner_id FROM commerce_stores WHERE id=?").bind(id).first();
      if(!store)return error(req,404,"Store not found");
      const nextActive=body.is_active===undefined?!!store.is_active:body.is_active;
      const nextDemo=body.is_demo===undefined?!!store.is_demo:body.is_demo;
      if(body.is_demo===false && !store.owner_id)return error(req,409,"Seeded demo stores cannot be promoted to operational checkout");
      if(body.is_demo===false && body.confirm_production!=="ENABLE COD CHECKOUT")return error(req,422,"Explicit COD checkout confirmation required");
      const deliveryNote=nextDemo?"Demo orders only; no real shipping or payment":"Cash on delivery; merchant-managed delivery. No online payment gateway or courier integration is active.";
      const result=await env.DB.prepare("UPDATE commerce_stores SET is_active=?,is_demo=?,delivery_note=? WHERE id=? AND is_active=? AND is_demo=?")
        .bind(nextActive?1:0,nextDemo?1:0,deliveryNote,id,store.is_active,store.is_demo).run();
      const action=body.is_demo===false?"store_promoted_to_cod":body.is_demo===true?"store_returned_to_demo":nextActive?"store_activated":"store_suspended";
      await audit(env,action,"store",id,{slug:store.slug,name:store.name,previous_active:!!store.is_active,is_active:nextActive,previous_demo:!!store.is_demo,is_demo:nextDemo,reason:short(body.reason,250)});
      return output(req,{updated:!!result.meta?.changes,store:{...store,is_active:nextActive?1:0,is_demo:nextDemo?1:0,delivery_note:deliveryNote},note:nextDemo?"Demo checkout only.":"COD/manual fulfilment enabled; no online payment or courier integration."});
    }
    const orderMatch=path.match(/^\/api\/platform-admin\/orders\/([^/]+)$/);
    if(method==="PATCH"&&orderMatch) {
      const id=decodeURIComponent(orderMatch[1]),body=await readBody(req),status=short(body.status,30),reason=short(body.reason,250);
      const order=await env.DB.prepare("SELECT o.id,o.store_id,o.order_number,o.status,o.total_bdt,s.is_demo AS store_is_demo FROM commerce_orders o JOIN commerce_stores s ON s.id=o.store_id WHERE o.id=?").bind(id).first();
      if(!order)return error(req,404,"Order not found");
      if(!canTransitionOrderStatus(order.status,status))return error(req,409,"Invalid order status transition");
      const statusNote=short(body.status_note,500)||defaultOrderStatusNote(status,!!order.store_is_demo);
      const result=await env.DB.prepare("UPDATE commerce_orders SET status=?,cancellation_reason=COALESCE(?,cancellation_reason),status_note=? WHERE id=? AND status=?")
        .bind(status,status==="cancelled"?reason||"Platform admin cancellation":null,statusNote,id,order.status).run();
      if(!result.meta?.changes)return error(req,409,"Order status changed; reload before retrying");
      await audit(env,"order_status_changed","order",id,{order_number:order.order_number,from:order.status,to:status,reason});
      return output(req,{updated:true,status,status_note:statusNote,inventory_restored:status==="cancelled",note:"D1 inventory cancellation trigger handles demo stock; no real payment was reversed."});
    }
    return error(req,404,"Platform admin route not found");
  } catch(e) {
    console.error("D1 platform admin route failure",path,e?.message||e);
    return error(req,e?.message==="Payload too large"?413:500,"Platform admin service temporarily unavailable");
  }
}
