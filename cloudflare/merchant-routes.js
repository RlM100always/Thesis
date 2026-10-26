/* Authenticated Cloudflare D1 merchant console (separate from legacy FastAPI).
   Public demo checkout does not accept any real payment or delivery.
   IMPORTANT: This owner identity is not imported from ephemeral SQLite.
*/
const encoder=new TextEncoder();
const hex=arr=>Array.from(new Uint8Array(arr),b=>b.toString(16).padStart(2,"0")).join("");
async function sha256(value){return hex(await crypto.subtle.digest("SHA-256",encoder.encode(value)));}
async function derive(pass,salt){
 const key=await crypto.subtle.importKey("raw",encoder.encode(pass),"PBKDF2",false,["deriveBits"]);
 return hex(await crypto.subtle.deriveBits({name:"PBKDF2",salt:Uint8Array.from(salt.match(/../g).map(x=>parseInt(x,16))),iterations:210000,hash:"SHA-256"},key,256));
}
function newSalt(){const a=new Uint8Array(16);crypto.getRandomValues(a);return hex(a);}
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
 if(!store)return {account:{email:owner.email},store:null,products:[],orders:[],metrics:{orders:0,inventory_units:0,placed_total_bdt:0},stock_adjustments:[]};
 const [products,orders,stats,adjustments]=await Promise.all([
  env.DB.prepare("SELECT id,sku,name,category,price_bdt,stock_qty,is_listed,created_at FROM commerce_products WHERE store_id=? ORDER BY created_at DESC LIMIT 200").bind(store.id).all(),
  env.DB.prepare("SELECT id,order_number,status,total_bdt,placed_at,payment_method FROM commerce_orders WHERE store_id=? ORDER BY placed_at DESC LIMIT 150").bind(store.id).all(),
  env.DB.prepare("SELECT (SELECT COUNT(*) FROM commerce_orders WHERE store_id=?) AS orders,(SELECT COALESCE(SUM(stock_qty),0) FROM commerce_products WHERE store_id=?) AS inventory_units,(SELECT COALESCE(SUM(total_bdt),0) FROM commerce_orders WHERE store_id=? AND status!='cancelled') AS placed_total_bdt").bind(store.id,store.id,store.id).first(),
  env.DB.prepare("SELECT product_id,old_quantity,new_quantity,delta,reason,created_at FROM commerce_stock_adjustments WHERE store_id=? ORDER BY created_at DESC LIMIT 25").bind(store.id).all()
 ]);
 return {account:{email:owner.email},store:stripStore(store),products:products.results,orders:orders.results,metrics:stats,stock_adjustments:adjustments.results};
}
const errorCode=e=>/UNIQUE constraint failed/.test(e.message||"")?409:500;
export async function merchantRouter(req,env,path,output,error){
 if(!path.startsWith("/api/merchant/"))return null;
 const method=req.method;
 try{
  if(method==="GET"&&path==="/api/merchant/health"){
   const start=Date.now(); let crypto_ok=false, crypto_error=null;
   try{ const salt=newSalt();const passwordHash=await derive("bsmart-health-test",salt);crypto_ok=passwordHash.length===64; }
   catch(e){crypto_error=e.name||"CryptoError";}
   return output(req,{status:"ok",db:"D1",auth_kdf_ok:crypto_ok,auth_kdf_error:crypto_error,kdf_time_ms:Date.now()-start});
  }
  if(method==="POST"&&path==="/api/merchant/register"){
   const b=await json(req,error);
   const email=short(b.email,200).toLowerCase();
   if(!validEmail(email)||typeof b.password!=="string"||b.password.length<12||b.password.length>96)
    return bad(req,error,422,"Valid email and a password of 12-96 characters required");
   // Guard this opt-in demo platform from automated bulk account creation.
   const today=await env.DB.prepare("SELECT COUNT(*) AS n FROM merchant_accounts WHERE created_at >= datetime('now','start of day')").first();
   if(Number(today?.n||0)>=20)return bad(req,error,429,"Daily demo registration limit reached");
   const exists=await env.DB.prepare("SELECT id FROM merchant_accounts WHERE email=?").bind(email).first();
   if(exists)return bad(req,error,409,"Account already exists");
   const salt=newSalt(),hash=await derive(b.password,salt);
   const id=crypto.randomUUID();
   try{await env.DB.prepare("INSERT INTO merchant_accounts(id,email,password_hash,password_salt) VALUES(?,?,?,?)").bind(id,email,hash,salt).run();}
   catch(e){return bad(req,error,errorCode(e),"Unable to register this email");}
   return output(req,{created:true,requires_login:true,note:"Email not yet independently verified"},201);
  }
  if(method==="POST"&&path==="/api/merchant/login"){
   const b=await json(req,error);
   const email=short(b.email,200).toLowerCase();
   const now=new Date().toISOString();
   if(!validEmail(email)||typeof b.password!=="string"||b.password.length>96)return bad(req,error,401,"Invalid credentials");
   const lock=await env.DB.prepare("SELECT failures,lock_until FROM merchant_login_attempts WHERE email=?").bind(email).first();
   if(lock?.lock_until&&lock.lock_until>now)return bad(req,error,429,"Too many attempts; try again later");
   const acc=await env.DB.prepare("SELECT * FROM merchant_accounts WHERE email=?").bind(email).first();
   let valid=false;
   if(acc) {
    const hash=await derive(b.password,acc.password_salt);
    const aa=encoder.encode(hash),bb=encoder.encode(acc.password_hash);
    valid=aa.length===bb.length;
    let xor=0;for(let i=0;i<aa.length&&valid;i++)xor|=aa[i]^bb[i];
    valid=valid&&xor===0;
   }
   if(!valid) {
    const failures=(lock?.failures||0)+1;
    const until=failures>=6?new Date(Date.now()+15*60*1000).toISOString():null;
    await env.DB.prepare("INSERT INTO merchant_login_attempts(email,failures,lock_until) VALUES(?,?,?) ON CONFLICT(email) DO UPDATE SET failures=excluded.failures,lock_until=excluded.lock_until").bind(email,failures,until).run();
    return bad(req,error,401,"Invalid credentials");
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
  if(method==="POST"&&path==="/api/merchant/products"){
   const store=await storeOnly(env,owner),b=await json(req,error);
   const sku=short(b.sku,45),name=short(b.name,140),cat=short(b.category,65);
   if(!sku||name.length<2||!integer(b.price_bdt,0,10000000)||!integer(b.stock_qty,0,1000000))
    return bad(req,error,422,"Invalid SKU, name, price or quantity");
   const id=crypto.randomUUID(),price=Number(b.price_bdt),qty=Number(b.stock_qty);
   try{
    await env.DB.prepare("INSERT INTO commerce_products(id,store_id,sku,name,category,price_bdt,stock_qty,is_listed) VALUES(?,?,?,?,?,?,?,?)").bind(id,store.id,sku,name,cat,price,qty,b.is_listed===true?1:0).run();
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
   if(!name||!integer(price,0,10000000)||!integer(qty,0,1000000))
    return bad(req,error,422,"Invalid product fields");
   const listed=b.is_listed===undefined?p.is_listed:(b.is_listed===true?1:0);
   const diff=qty-p.stock_qty;
   const update=env.DB.prepare("UPDATE commerce_products SET name=?,category=?,price_bdt=?,stock_qty=?,is_listed=? WHERE store_id=? AND id=?").bind(name,cat,price,qty,listed,store.id,p.id);
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
   const next={placed:["confirmed","cancelled"],confirmed:["fulfilled","cancelled"],fulfilled:[],cancelled:[]};
   if(!next[order.status]?.includes(status))return bad(req,error,409,"Invalid order status transition");
   await env.DB.prepare("UPDATE commerce_orders SET status=? WHERE id=? AND store_id=? AND status=?").bind(status,order.id,store.id,order.status).run();
   return output(req,{status});
  }
  return bad(req,error,404,"Merchant route not found");
 }catch(e){
  console.error("merchant route failure",path,e?.message||e);
  return bad(req,error,/Create a store first/.test(e.message)?409:400,e.message==="Payload too large"?"Payload too large":"Merchant request failed");
 }
}
