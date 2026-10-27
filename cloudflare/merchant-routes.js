import { canTransitionOrderStatus, defaultOrderStatusNote } from "./order-workflow.js";

/* Authenticated Cloudflare D1 merchant console (separate from legacy FastAPI).
   Public demo checkout does not accept any real payment or delivery.
   IMPORTANT: This owner identity is not imported from ephemeral SQLite.
*/
const encoder=new TextEncoder();
const hex=arr=>Array.from(new Uint8Array(arr),b=>b.toString(16).padStart(2,"0")).join("");
async function sha256(value){return hex(await crypto.subtle.digest("SHA-256",encoder.encode(value)));}
function newSession(){const a=new Uint8Array(32);crypto.getRandomValues(a);return hex(a);}
function bad(request,error,code,message){return error(request,code,message);}
async function json(request,error,max=10000){
 const text=await request.text();
 if(text.length>max)throw new Error("Payload too large");
 try{return JSON.parse(text);}catch{throw new Error("Invalid JSON");}
}
const short=(value,n=120)=>String(value??"").trim().slice(0,n);
const validEmail=email=>/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)&&email.length<=180;
const integer=(value,min,max)=>Number.isInteger(Number(value))&&Number(value)>=min&&Number(value)<=max;
async function viewer(req,env){
 const bearer=req.headers.get("Authorization")||"";
 const match=/^Bearer ([a-f0-9]{64})$/.exec(bearer);
 if(!match)return null;
 const digest=await sha256(match[1]);
 return env.DB.prepare("SELECT a.id,a.email FROM merchant_sessions s JOIN merchant_accounts a ON a.id=s.account_id WHERE s.token_hash=? AND s.expires_at>?").bind(digest,new Date().toISOString()).first();
}
async function myStore(env,owner){
 return env.DB.prepare("SELECT * FROM commerce_stores WHERE owner_id=? ORDER BY created_at LIMIT 1").bind(owner.id).first();
}
async function storeOnly(env,owner){const row=await myStore(env,owner);if(!row)throw new Error("Create a store first");return row;}
function stripStore(s){return {id:s.id,slug:s.slug,name:s.name,tagline:s.tagline||"",category:s.category||"",area:s.area||"",is_active:!!s.is_active,is_demo:!!s.is_demo,created_at:s.created_at};}
async function dashboard(env,owner){
 const store=await myStore(env,owner);
 if(!store)return {account:{email:owner.email},store:null,products:[],orders:[],metrics:{orders:0,inventory_units:0,placed_total_bdt:0},stock_adjustments:[],cashbook:[]};
 const [products,orders,stats,adjustments,cashbook]=await Promise.all([
  env.DB.prepare("SELECT id,sku,name,category,description,brand,tags,compare_at_price_bdt,unit_label,price_bdt,stock_qty,is_listed,created_at,updated_at FROM commerce_products WHERE store_id=? ORDER BY created_at DESC LIMIT 200").bind(store.id).all(),
  env.DB.prepare("SELECT id,order_number,status,status_note,cancellation_reason,total_bdt,placed_at,payment_method,shipping_name,shipping_phone,shipping_address FROM commerce_orders WHERE store_id=? ORDER BY placed_at DESC LIMIT 150").bind(store.id).all(),
  env.DB.prepare("SELECT (SELECT COUNT(*) FROM commerce_orders WHERE store_id=?) AS orders,(SELECT COALESCE(SUM(stock_qty),0) FROM commerce_products WHERE store_id=?) AS inventory_units,(SELECT COALESCE(SUM(total_bdt),0) FROM commerce_orders WHERE store_id=? AND status!='cancelled') AS placed_total_bdt").bind(store.id,store.id,store.id).first(),
  env.DB.prepare("SELECT product_id,old_quantity,new_quantity,delta,reason,created_at FROM commerce_stock_adjustments WHERE store_id=? ORDER BY created_at DESC LIMIT 25").bind(store.id).all(),
  env.DB.prepare("SELECT id,kind,amount_bdt,description,created_at,related_order_id FROM commerce_cashbook WHERE store_id=? ORDER BY created_at DESC LIMIT 75").bind(store.id).all()
 ]);
 return {account:{email:owner.email},store:stripStore(store),products:products.results,orders:orders.results,metrics:stats,stock_adjustments:adjustments.results,cashbook:cashbook.results};
}
const errorCode=e=>/UNIQUE constraint failed/.test(e.message||"")?409:500;
export async function merchantRouter(req,env,path,output,error){
 if(!path.startsWith("/api/merchant/"))return null;
 const method=req.method;
 try{
  if(method==="GET"&&path==="/api/merchant/health"){
   const secret=newSession(),digest=await sha256(secret);
   return output(req,{status:"ok",db:"D1",auth_key_digest_ok:digest.length===64,auth_mode:"256bit_random_access_key"});
  }
  if(method==="POST"&&path==="/api/merchant/register"){
   const b=await json(req,error),email=short(b.email,200).toLowerCase();
   if(!validEmail(email))return bad(req,error,422,"Valid email required");
   const today=await env.DB.prepare("SELECT COUNT(*) AS n FROM merchant_accounts WHERE created_at >= datetime('now','start of day')").first();
   if(Number(today?.n||0)>=20)return bad(req,error,429,"Daily demo registration limit reached");
   if(await env.DB.prepare("SELECT id FROM merchant_accounts WHERE email=?").bind(email).first())
     return bad(req,error,409,"Account already exists");
   const id=crypto.randomUUID(),key=newSession(),digest=await sha256(key);
   try{await env.DB.prepare("INSERT INTO merchant_accounts(id,email,password_hash,password_salt,access_key_digest) VALUES(?,?,?,?,?)").bind(id,email,"ACCESS_KEY_ONLY","DISABLED",digest).run();}
   catch(e){return bad(req,error,errorCode(e),"Unable to create owner account");}
   return output(req,{created:true,owner_access_key:key,requires_login:true,note:"SAVE THIS KEY NOW. It is never shown again. No email verification or recovery exists."},201);
  }
  if(method==="POST"&&path==="/api/merchant/login"){
   const b=await json(req,error),email=short(b.email,200).toLowerCase();
   const candidate=String(b.access_key||"").trim().toLowerCase();
   if(!validEmail(email)||!/^[0-9a-f]{64}$/.test(candidate))return bad(req,error,401,"Invalid account email or owner access key");
   const now=new Date().toISOString();
   const lock=await env.DB.prepare("SELECT failures,lock_until FROM merchant_login_attempts WHERE email=?").bind(email).first();
   if(lock?.lock_until&&lock.lock_until>now)return bad(req,error,429,"Too many attempts; try again later");
   const acc=await env.DB.prepare("SELECT id,email,access_key_digest FROM merchant_accounts WHERE email=?").bind(email).first();
   const hash=await sha256(candidate),expected=String(acc?.access_key_digest||"");
   let valid=hash.length===expected.length;let xor=0;
   for(let i=0;i<hash.length&&valid;i++)xor|=hash.charCodeAt(i)^expected.charCodeAt(i);
   valid=valid&&xor===0;
   if(!valid){
    const failures=(lock?.failures||0)+1,until=failures>=6?new Date(Date.now()+15*60*1000).toISOString():null;
    await env.DB.prepare("INSERT INTO merchant_login_attempts(email,failures,lock_until) VALUES(?,?,?) ON CONFLICT(email) DO UPDATE SET failures=excluded.failures,lock_until=excluded.lock_until").bind(email,failures,until).run();
    return bad(req,error,401,"Invalid account email or owner access key");
   }
   await env.DB.prepare("DELETE FROM merchant_login_attempts WHERE email=?").bind(email).run();
   const token=newSession(),tokenHash=await sha256(token),expires=new Date(Date.now()+12*60*60*1000).toISOString();
   await env.DB.prepare("INSERT INTO merchant_sessions(token_hash,account_id,expires_at) VALUES(?,?,?)").bind(tokenHash,acc.id,expires).run();
   return output(req,{token,expires_at:expires,email:acc.email});
  }
  const owner=await viewer(req,env);
  if(!owner)return bad(req,error,401,"Merchant login required");
  if(method==="POST"&&path==="/api/merchant/logout"){
   const token=req.headers.get("Authorization").slice(7);
   await env.DB.prepare("DELETE FROM merchant_sessions WHERE token_hash=?").bind(await sha256(token)).run();
   return output(req,{logged_out:true});
  }
  if(method==="POST"&&path==="/api/merchant/delete-account"){
   const body=await json(req,error);
   if(body.confirm!=="DELETE DEMO ACCOUNT")return bad(req,error,422,"Explicit account deletion confirmation required");
   const store=await myStore(env,owner);
   if(store&&(!store.is_demo||!store.id.startsWith("merchant-")))
     return bad(req,error,409,"Only isolated demo stores can be deleted automatically");
   if(store){
     const x=await env.DB.prepare("SELECT COUNT(*) AS n FROM commerce_orders WHERE store_id=?").bind(store.id).first();
     if(x.n)return bad(req,error,409,"Cannot delete account with order history; contact admin for data export and supervised deletion");
   }
   const statements=[];
   if(store){
     statements.push(
       env.DB.prepare("DELETE FROM commerce_cashbook WHERE store_id=?").bind(store.id),
       env.DB.prepare("DELETE FROM commerce_stock_adjustments WHERE store_id=?").bind(store.id),
       env.DB.prepare("DELETE FROM commerce_products WHERE store_id=?").bind(store.id),
       env.DB.prepare("DELETE FROM commerce_stores WHERE owner_id=? AND id=?").bind(owner.id,store.id)
     );
   }
   statements.push(
     env.DB.prepare("DELETE FROM merchant_sessions WHERE account_id=?").bind(owner.id),
     env.DB.prepare("DELETE FROM merchant_login_attempts WHERE email=?").bind(owner.email),
     env.DB.prepare("DELETE FROM merchant_accounts WHERE id=?").bind(owner.id)
   );
   await env.DB.batch(statements);
   return output(req,{deleted:true});
  }
  if(method==="GET"&&path==="/api/merchant/dashboard")return output(req,await dashboard(env,owner));
   if(method==="GET"&&path==="/api/merchant/returns"){
    const store=await storeOnly(env,owner);
    const {results}=await env.DB.prepare(
     "SELECT r.id,r.order_id,r.account_id,r.reason,r.customer_note,r.merchant_note,r.status,r.requested_at,r.updated_at,o.order_number,o.total_bdt,a.display_name AS customer_name,a.email,a.phone " +
     "FROM commerce_order_returns r JOIN commerce_orders o ON o.id=r.order_id JOIN commerce_customer_accounts a ON a.id=r.account_id " +
     "WHERE r.store_id=? ORDER BY r.requested_at DESC LIMIT 100"
    ).bind(store.id).all();
    return output(req,{returns:results});
   }
   const returnStatusMatch=/^\/api\/merchant\/returns\/([a-zA-Z0-9-]{2,90})$/.exec(path);
   if(method==="PATCH"&&returnStatusMatch){
    const store=await storeOnly(env,owner),body=await json(req,error),id=returnStatusMatch[1];
    const row=await env.DB.prepare("SELECT * FROM commerce_order_returns WHERE id=? AND store_id=?").bind(id,store.id).first();
    if(!row)return bad(req,error,404,"Return request not found");
    const status=short(body.status,30),note=short(body.merchant_note,1000);
    const next={requested:["approved","rejected"],approved:["received"],received:["closed_demo"],rejected:[],closed_demo:[]};
    if(!next[row.status]?.includes(status))return bad(req,error,409,"Invalid return status transition");
    const result=await env.DB.prepare("UPDATE commerce_order_returns SET status=?,merchant_note=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND store_id=? AND status=?")
     .bind(status,note||null,id,store.id,row.status).run();
    if(!result.meta?.changes)return bad(req,error,409,"Return request changed; refresh and retry");
    return output(req,{updated:true,status,inventory_restocked:status==="received",note:"Demo return workflow only; no money was refunded"});
   }
   if(method==="GET"&&path==="/api/merchant/chat"){
    const store=await storeOnly(env,owner),url=new URL(req.url),accountId=short(url.searchParams.get("account_id"),80);
    if(accountId)await env.DB.prepare("UPDATE commerce_customer_messages SET read_by_merchant_at=CURRENT_TIMESTAMP WHERE store_id=? AND account_id=? AND sender_role='customer' AND read_by_merchant_at IS NULL").bind(store.id,accountId).run();
    const {results}=await env.DB.prepare(
     "SELECT m.id,m.account_id,m.order_id,m.sender_role,m.message,m.created_at,m.read_by_customer_at,m.read_by_merchant_at,a.display_name AS customer_name,a.email AS customer_email,o.order_number " +
     "FROM commerce_customer_messages m JOIN commerce_customer_accounts a ON a.id=m.account_id LEFT JOIN commerce_orders o ON o.id=m.order_id " +
     "WHERE m.store_id=? AND (?='' OR m.account_id=?) ORDER BY m.created_at DESC LIMIT 150"
    ).bind(store.id,accountId,accountId).all();
    return output(req,{messages:results.reverse()});
   }
   if(method==="POST"&&path==="/api/merchant/chat"){
    const store=await storeOnly(env,owner),body=await json(req,error),accountId=short(body.account_id,80),message=short(body.message,2000),orderId=short(body.order_id,80)||null;
    if(!accountId||message.length<1)return bad(req,error,422,"Customer and message are required");
    const thread=await env.DB.prepare("SELECT id FROM commerce_customer_messages WHERE store_id=? AND account_id=? LIMIT 1").bind(store.id,accountId).first();
    if(!thread)return bad(req,error,404,"Customer conversation not found");
    if(orderId&&!await env.DB.prepare("SELECT id FROM commerce_orders WHERE id=? AND store_id=? AND account_id=?").bind(orderId,store.id,accountId).first())return bad(req,error,403,"Order does not belong to this customer/store");
    const id=crypto.randomUUID();
    await env.DB.prepare("INSERT INTO commerce_customer_messages(id,store_id,account_id,order_id,sender_role,message) VALUES(?,?,?,?,?,?)").bind(id,store.id,accountId,orderId,"merchant",message).run();
    return output(req,{id,account_id:accountId,order_id:orderId,sender_role:"merchant",message,created_at:new Date().toISOString()},201);
   }
  if(method==="POST"&&path==="/api/merchant/store"){
   if(await myStore(env,owner))return bad(req,error,409,"Account already has a store");
   const b=await json(req,error);
   const name=short(b.name,110),category=short(b.category,50),area=short(b.area,100);
   if(name.length<3||!category||!area)return bad(req,error,422,"Store name, category and area are required");
   const id="merchant-"+crypto.randomUUID();
   const slug="shop-"+crypto.randomUUID().slice(0,12);
   await env.DB.prepare("INSERT INTO commerce_stores(id,slug,name,tagline,category,area,theme,color,is_demo,is_active,owner_id,delivery_note) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)").bind(id,slug,name,"Owner-managed demo storefront (not verified real commerce)",category,area,"clean","#087e59",1,0,owner.id,"Demo orders only; no real shipping or payment").run();
   return output(req,{created:true,store:stripStore(await myStore(env,owner))},201);
  }
  if(method==="PATCH"&&path==="/api/merchant/store"){
   const store=await storeOnly(env,owner),b=await json(req,error);
   const name=short(b.name??store.name,110),tagline=short(b.tagline??store.tagline,160);
   const area=short(b.area??store.area,100),category=short(b.category??store.category,50);
   const activate=b.is_active===undefined?store.is_active:(b.is_active===true?1:0);
   if(name.length<3||!area||!category)return bad(req,error,422,"Invalid store profile");
   await env.DB.prepare("UPDATE commerce_stores SET name=?,tagline=?,category=?,area=?,is_active=? WHERE id=? AND owner_id=?").bind(name,tagline,category,area,activate,store.id,owner.id).run();
   return output(req,{store:stripStore(await myStore(env,owner))});
  }
  if(method==="POST"&&path==="/api/merchant/cashbook"){
   const store=await storeOnly(env,owner),b=await json(req,error);
   const kind=short(b.kind,15),amount=Number(b.amount_bdt),description=short(b.description,140);
   if(!["receipt","expense"].includes(kind)||!integer(amount,1,500000)||description.length<3)
    return bad(req,error,422,"Valid kind, demo amount and note required");
   await env.DB.prepare("INSERT INTO commerce_cashbook(id,store_id,kind,amount_bdt,description) VALUES(?,?,?,?,?)").bind(crypto.randomUUID(),store.id,kind,amount,description).run();
   return output(req,{created:true,note:"Demo cashbook only; not a certified accounting ledger"});
  }
  if(method==="POST"&&path==="/api/merchant/pos"){
   const store=await storeOnly(env,owner);
   if(!store.is_demo)return bad(req,error,409,"Only demonstration POS is supported");
   const b=await json(req,error);
   if(!Array.isArray(b.items)||!b.items.length||b.items.length>12)return bad(req,error,422,"1-12 demo POS products required");
   const details=[],seen=new Set();let total=0;
   for(const item of b.items){
    const productId=String(item.product_id||""),qty=Number(item.quantity);
    if(!productId||seen.has(productId)||!integer(qty,1,30))return bad(req,error,422,"Invalid POS line");
    seen.add(productId);
    const p=await env.DB.prepare("SELECT * FROM commerce_products WHERE id=? AND store_id=? AND is_listed=1").bind(productId,store.id).first();
    if(!p||p.stock_qty<qty)return bad(req,error,409,"Demo product unavailable or stock insufficient");
    total+=p.price_bdt*qty;details.push({p,qty});
   }
   if(!integer(total,1,500000))return bad(req,error,422,"Invalid POS amount");
   const oid=crypto.randomUUID(),cid=crypto.randomUUID(),token=newSession(),number="POS-"+oid.slice(0,8).toUpperCase();
   const stmts=[
    env.DB.prepare("INSERT INTO commerce_customers(id,store_id,display_name) VALUES(?,?,?)").bind(cid,store.id,"Anonymous demo counter customer"),
    env.DB.prepare("INSERT INTO commerce_orders(id,store_id,order_number,access_token,status,subtotal_bdt,total_bdt,payment_method,shipping_name,shipping_phone,shipping_address,customer_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)").bind(oid,store.id,number,token,"fulfilled",total,total,"demo_pos","Demo counter customer","","",cid),
    ...details.map(({p,qty})=>env.DB.prepare("INSERT INTO commerce_order_lines(order_id,product_id,product_name,quantity,price_bdt,line_total_bdt) VALUES(?,?,?,?,?,?)").bind(oid,p.id,p.name,qty,p.price_bdt,p.price_bdt*qty)),
    env.DB.prepare("INSERT INTO commerce_cashbook(id,store_id,kind,amount_bdt,description,related_order_id) VALUES(?,?,?,?,?,?)").bind(crypto.randomUUID(),store.id,"receipt",total,"Simulated demo POS receipt",oid)
   ];
   try{await env.DB.batch(stmts);}catch(e){return bad(req,error,409,"Stock or product price changed; refresh and retry");}
   return output(req,{created:true,order_number:number,total_bdt:total,note:"Demo cash sale; no actual customer payment"},201);
  }
  if(method==="POST"&&path==="/api/merchant/products"){
   const store=await storeOnly(env,owner),b=await json(req,error);
   const sku=short(b.sku,45),name=short(b.name,140),cat=short(b.category,65);
   const description=short(b.description,3000),brand=short(b.brand,100),unit=short(b.unit_label||"pcs",24);
   const tags=Array.isArray(b.tags)?JSON.stringify(b.tags.map(x=>short(x,32)).filter(Boolean).slice(0,12)):JSON.stringify([]);
   const compare=b.compare_at_price_bdt===undefined||b.compare_at_price_bdt===""||b.compare_at_price_bdt===null?null:Number(b.compare_at_price_bdt);
   if(!sku||name.length<2||!integer(b.price_bdt,0,10000000)||!integer(b.stock_qty,0,1000000)||
      (compare!==null&&(!integer(compare,0,10000000)||compare<Number(b.price_bdt))))
    return bad(req,error,422,"Invalid SKU, name, price, compare-at price or quantity");
   const id=crypto.randomUUID(),price=Number(b.price_bdt),qty=Number(b.stock_qty);
   try{
    await env.DB.prepare("INSERT INTO commerce_products(id,store_id,sku,name,category,description,brand,tags,compare_at_price_bdt,unit_label,price_bdt,stock_qty,is_listed,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)")
     .bind(id,store.id,sku,name,cat,description||null,brand||null,tags,compare,unit,price,qty,b.is_listed===true?1:0).run();
   }catch(e){return bad(req,error,errorCode(e),"Product SKU must be unique");}
   return output(req,{created:true,product_id:id},201);
  }
  const pp=/^\/api\/merchant\/products\/([a-zA-Z0-9-]{2,90})$/.exec(path);
  if(method==="PATCH"&&pp){
   const store=await storeOnly(env,owner);
   const p=await env.DB.prepare("SELECT * FROM commerce_products WHERE store_id=? AND id=?").bind(store.id,pp[1]).first();
   if(!p)return bad(req,error,404,"Product not found");
   const b=await json(req,error);
   const name=short(b.name??p.name,140),cat=short(b.category??p.category,65);
   const price=b.price_bdt===undefined?p.price_bdt:Number(b.price_bdt);
   const qty=b.stock_qty===undefined?p.stock_qty:Number(b.stock_qty);
   const description=short(b.description===undefined?p.description:b.description,3000),brand=short(b.brand===undefined?p.brand:b.brand,100);
   const unit=short(b.unit_label===undefined?(p.unit_label||"pcs"):b.unit_label,24);
   let tags=p.tags||"[]";
   if(b.tags!==undefined)tags=JSON.stringify(Array.isArray(b.tags)?b.tags.map(x=>short(x,32)).filter(Boolean).slice(0,12):[]);
   const compare=b.compare_at_price_bdt===undefined?p.compare_at_price_bdt:(b.compare_at_price_bdt===""||b.compare_at_price_bdt===null?null:Number(b.compare_at_price_bdt));
   if(!name||!integer(price,0,10000000)||!integer(qty,0,1000000)||
      (compare!==null&&compare!==undefined&&(!integer(compare,0,10000000)||compare<price)))
    return bad(req,error,422,"Invalid product fields");
   const listed=b.is_listed===undefined?p.is_listed:(b.is_listed===true?1:0);
   const diff=qty-p.stock_qty;
   const update=env.DB.prepare("UPDATE commerce_products SET name=?,category=?,description=?,brand=?,tags=?,compare_at_price_bdt=?,unit_label=?,price_bdt=?,stock_qty=?,is_listed=?,updated_at=CURRENT_TIMESTAMP WHERE store_id=? AND id=?").bind(name,cat,description||null,brand||null,tags,compare??null,unit,price,qty,listed,store.id,p.id);
   if(diff) {
    await env.DB.batch([update,env.DB.prepare("INSERT INTO commerce_stock_adjustments(id,store_id,product_id,old_quantity,new_quantity,delta,reason) VALUES(?,?,?,?,?,?,?)").bind(crypto.randomUUID(),store.id,p.id,p.stock_qty,qty,diff,"Owner manual inventory correction")]);
   } else await update.run();
   return output(req,{updated:true,stock_change:diff});
  }
  const oo=/^\/api\/merchant\/orders\/([a-zA-Z0-9-]{2,90})\/status$/.exec(path);
  if(method==="PATCH"&&oo){
   const store=await storeOnly(env,owner),b=await json(req,error);
   const order=await env.DB.prepare("SELECT * FROM commerce_orders WHERE store_id=? AND id=?").bind(store.id,oo[1]).first();
   if(!order)return bad(req,error,404,"Order not found");
   const status=short(b.status,30);
   if(!canTransitionOrderStatus(order.status,status))return bad(req,error,409,"Invalid order status transition");
   const note=short(b.status_note,300)||defaultOrderStatusNote(status,!!store.is_demo);
   const cancellationReason=status==="cancelled"?(short(b.cancellation_reason,250)||"দোকানের পক্ষ থেকে অর্ডার বাতিল করা হয়েছে"):null;
   const updated=await env.DB.prepare("UPDATE commerce_orders SET status=?,status_note=?,cancellation_reason=COALESCE(?,cancellation_reason) WHERE id=? AND store_id=? AND status=?")
    .bind(status,note,cancellationReason,order.id,store.id,order.status).run();
   if(!updated.meta?.changes)return bad(req,error,409,"Order status changed; refresh and retry");
   return output(req,{status,status_note:note});
  }
  return bad(req,error,404,"Merchant route not found");
 }catch(e){
  console.error("merchant route failure",path,e?.message||e);
  return bad(req,error,/Create a store first/.test(e.message)?409:400,e.message==="Payload too large"?"Payload too large":"Merchant request failed");
 }
}
