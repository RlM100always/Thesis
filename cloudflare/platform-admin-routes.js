import { canTransitionOrderStatus, defaultOrderStatusNote } from "./order-workflow.js";
import { INTERNAL_TEST_STORE_SLUGS } from "./store-visibility.js";

/* Privileged controls for the Cloudflare Primary commerce platform.
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
const validEmail=email=>/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)&&email.length<=180;
function newInviteToken(){const bytes=new Uint8Array(32);crypto.getRandomValues(bytes);return Array.from(bytes,b=>b.toString(16).padStart(2,"0")).join("");}
function appBase(env){
 return String(env.PUBLIC_APP_URL||"https://thesis-j0n8.onrender.com").replace(/\/$/,"");
}
function ownerPortalLink(env,parameter,token){
 const base=appBase(env);
 return parameter?base+"/#/d1-owner?"+parameter+"="+encodeURIComponent(token):base+"/#/d1-owner";
}
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
        "(SELECT COALESCE(SUM(o.total_bdt),0) FROM commerce_orders o JOIN commerce_stores s ON s.id=o.store_id WHERE o.status!='cancelled' AND s.is_demo=0 AND o.payment_method='cod' AND o.payment_status='paid') AS cod_paid_total_bdt,"+
        "(SELECT COALESCE(SUM(o.total_bdt),0) FROM commerce_orders o JOIN commerce_stores s ON s.id=o.store_id WHERE o.status!='cancelled' AND s.is_demo=0 AND o.payment_method='cod' AND o.payment_status='pending_cod') AS cod_pending_total_bdt,"+
        "(SELECT COUNT(*) FROM commerce_order_returns WHERE status IN ('requested','approved')) AS returns_open,"+
        "(SELECT COUNT(*) FROM commerce_customer_messages WHERE sender_role='customer' AND read_by_merchant_at IS NULL) AS unread_customer_messages"
      ).first();
      return output(req,{scope:"Cloudflare D1 storefronts; approved stores support COD and merchant-managed fulfilment",online_payments:false,cash_on_delivery:true,merchant_managed_delivery:true,courier_integration:false,automated_refunds:false,metrics:row});
    }

    if(method==="GET"&&path==="/api/platform-admin/owner-invites") {
      const {results}=await env.DB.prepare(
        "SELECT id,email,owner_name,store_name,category,area,expires_at,identity_confirmed,accepted_at,revoked_at,created_at "+
        "FROM merchant_owner_invites ORDER BY created_at DESC LIMIT 200"
      ).all();
      return output(req,{invites:results||[]});
    }
    if(method==="POST"&&path==="/api/platform-admin/owner-invites") {
      const body=await readBody(req);
      const email=short(body.email,180).toLowerCase(),ownerName=short(body.owner_name,120);
      const storeName=short(body.store_name,110),category=short(body.category,50),area=short(body.area,100),tagline=short(body.tagline,160);
      if(!validEmail(email)||ownerName.length<2||storeName.length<3||!category||!area)
        return error(req,422,"Provide a valid owner email, owner name, store name, category and area.");
      if(body.identity_confirmed!==true)
        return error(req,422,"Confirm that the business owner and contact email were verified outside this system before issuing access.");
      if(await env.DB.prepare("SELECT id FROM merchant_accounts WHERE email=?").bind(email).first())
        return error(req,409,"An account already exists for this email.");
      const token=newInviteToken(),tokenHash=await digest(token),id=crypto.randomUUID();
      const expires=new Date(Date.now()+72*60*60*1000).toISOString();
      try{
        await env.DB.batch([
          env.DB.prepare("UPDATE merchant_owner_invites SET revoked_at=CURRENT_TIMESTAMP WHERE email=? AND accepted_at IS NULL AND revoked_at IS NULL").bind(email),
          env.DB.prepare("INSERT INTO merchant_owner_invites(id,email,owner_name,store_name,category,area,tagline,token_hash,expires_at,identity_confirmed) VALUES(?,?,?,?,?,?,?,?,?,1)")
            .bind(id,email,ownerName,storeName,category,area,tagline,tokenHash,expires)
        ]);
      }catch(e){return error(req,409,"Owner invitation could not be created.");}
      await audit(env,"owner_invite_created","owner_invite",id,{email,owner_name:ownerName,store_name:storeName,category,area,identity_confirmed:true,expires_at:expires});
      return output(req,{created:true,id,email,store_name:storeName,expires_at:expires,invite_url:ownerPortalLink(env,"owner_invite",token),share_once:true},201);
    }
    const ownerInviteMatch=path.match(/^\/api\/platform-admin\/owner-invites\/([^/]+)$/);
    if(method==="PATCH"&&ownerInviteMatch) {
      const id=decodeURIComponent(ownerInviteMatch[1]),body=await readBody(req);
      if(body.revoke!==true)return error(req,422,"Set revoke=true to revoke this pending invitation.");
      const row=await env.DB.prepare("SELECT id,email,accepted_at,revoked_at FROM merchant_owner_invites WHERE id=?").bind(id).first();
      if(!row)return error(req,404,"Owner invitation not found");
      if(row.accepted_at)return error(req,409,"An accepted invitation cannot be revoked; suspend the owner account instead.");
      const result=await env.DB.prepare("UPDATE merchant_owner_invites SET revoked_at=CURRENT_TIMESTAMP WHERE id=? AND accepted_at IS NULL AND revoked_at IS NULL").bind(id).run();
      await audit(env,"owner_invite_revoked","owner_invite",id,{email:row.email});
      return output(req,{revoked:!!result.meta?.changes});
    }
    if(method==="GET"&&path==="/api/platform-admin/access-register") {
      const [stores,staff]=await Promise.all([
        env.DB.prepare(
          "SELECT s.id,s.slug,s.name,s.category,s.area,s.is_active,s.is_demo,s.created_at,"+
          "a.id AS owner_id,a.email AS owner_email,a.display_name AS owner_name,a.is_active AS owner_active,a.email_verified_at "+
          "FROM commerce_stores s LEFT JOIN merchant_accounts a ON a.id=s.owner_id AND a.role='owner' "+
          "ORDER BY s.created_at DESC LIMIT 500"
        ).all(),
        env.DB.prepare(
          "SELECT x.store_id,a.id,a.email,a.display_name,x.role,x.is_active,a.is_active AS account_active,x.last_login_at "+
          "FROM merchant_staff_store_access x JOIN merchant_accounts a ON a.id=x.account_id ORDER BY x.store_id,a.email"
        ).all()
      ]);
      const byStore=new Map();
      for(const member of (staff.results||[])){
        if(!byStore.has(member.store_id))byStore.set(member.store_id,[]);
        byStore.get(member.store_id).push(member);
      }
      const base=appBase(env);
      return output(req,{generated_at:new Date().toISOString(),owner_login_url:base+"/#/d1-owner",stores:(stores.results||[]).map(s=>({
        store_id:s.id,store_name:s.name,slug:s.slug,public_store_url:base+"/#/store/"+s.slug,
        category:s.category,area:s.area,store_status:s.is_demo?"legacy_test_record":s.is_active?"published":"awaiting_approval",
        owner:{id:s.owner_id,email:s.owner_email,name:s.owner_name,is_active:!!s.owner_active,email_verified:!!s.email_verified_at},
        staff:byStore.get(s.id)||[]
      }))});
    }
    if(method==="GET"&&path==="/api/platform-admin/stores") {
      const {results}=await env.DB.prepare(
        "SELECT s.id,s.slug,s.name,s.category,s.area,s.is_demo,s.is_active,s.created_at,a.email AS owner_email,"+
        "(SELECT COUNT(*) FROM commerce_products p WHERE p.store_id=s.id) AS products_count,"+
        "(SELECT COUNT(*) FROM commerce_orders o WHERE o.store_id=s.id) AS orders_count "+
        "FROM commerce_stores s LEFT JOIN merchant_accounts a ON a.id=s.owner_id AND a.role='owner' ORDER BY s.created_at DESC LIMIT 500"
      ).all();
      return output(req,{stores:results});
    }
    if(method==="GET"&&path==="/api/platform-admin/owners") {
      const {results}=await env.DB.prepare(
        "SELECT a.id,a.email,a.role,a.is_active,a.email_verified_at,a.created_at,CASE WHEN a.password_hash='ACCESS_KEY_ONLY' THEN 'legacy_access_key' ELSE 'password' END AS auth_mode,"+
        "s.id AS store_id,s.slug AS store_slug,s.name AS store_name,"+
        "(SELECT COUNT(*) FROM merchant_sessions ms WHERE ms.account_id=a.id AND datetime(ms.expires_at)>CURRENT_TIMESTAMP) AS active_sessions "+
        "FROM merchant_accounts a LEFT JOIN commerce_stores s ON s.owner_id=a.id "+
        "WHERE a.role='owner' ORDER BY a.created_at DESC LIMIT 500"
      ).all();
      return output(req,{owners:results,note:"Passwords and password hashes are never exposed. Owners use email verification and self-service password reset."});
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
        const ownerMatch=path.match(/^\/api\/platform-admin\/owners\/([^/]+)$/);
    if(method==="PATCH"&&ownerMatch) {
      const id=decodeURIComponent(ownerMatch[1]),body=await readBody(req);
      if(typeof body.is_active!=="boolean")return error(req,422,"is_active must be true or false");
      const owner=await env.DB.prepare("SELECT id,email,is_active,role FROM merchant_accounts WHERE id=?").bind(id).first();
      if(!owner)return error(req,404,"Owner account not found");
      const result=await env.DB.prepare("UPDATE merchant_accounts SET is_active=? WHERE id=? AND is_active=?")
        .bind(body.is_active?1:0,id,owner.is_active).run();
      if(!body.is_active)await env.DB.prepare("DELETE FROM merchant_sessions WHERE account_id=?").bind(id).run();
      await audit(env,body.is_active?"owner_account_activated":"owner_account_suspended","merchant_account",id,{email:owner.email,previous_active:!!owner.is_active,is_active:body.is_active,reason:short(body.reason,250)});
      return output(req,{updated:!!result.meta?.changes,is_active:body.is_active,sessions_revoked:!body.is_active});
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
      if(body.is_demo===false && INTERNAL_TEST_STORE_SLUGS.has(store.slug))return error(req,409,"Internal test records cannot be published as customer stores.");
      if(body.is_demo===false && body.confirm_production!=="ENABLE COD CHECKOUT")return error(req,422,"Explicit COD checkout confirmation required");
      const deliveryNote=nextDemo?"Demo orders only":"Cash on delivery; delivery managed by the store.";
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
