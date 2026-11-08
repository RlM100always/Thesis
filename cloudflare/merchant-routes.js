import { canTransitionOrderStatus, defaultOrderStatusNote } from "./order-workflow.js";
import { ownerAssistantAnswer } from "./assistant-routes.js";

/* Authenticated Cloudflare D1 merchant console (separate from legacy FastAPI).
   Public demo checkout does not accept any real payment or delivery.
   IMPORTANT: This owner identity is not imported from ephemeral SQLite.
*/
const encoder=new TextEncoder();
const hex=arr=>Array.from(new Uint8Array(arr),b=>b.toString(16).padStart(2,"0")).join("");
async function sha256(value){return hex(await crypto.subtle.digest("SHA-256",encoder.encode(value)));}
async function passwordDigest(password,salt){
 const key=await crypto.subtle.importKey("raw",encoder.encode(password),"PBKDF2",false,["deriveBits"]);
 const bits=await crypto.subtle.deriveBits({name:"PBKDF2",salt:encoder.encode(salt),iterations:100000,hash:"SHA-256"},key,256);
 return hex(bits);
}
function constantTimeEqual(left,right){
 const a=String(left??""),b=String(right??"");
 if(a.length!==b.length)return false;
 let diff=0;for(let i=0;i<a.length;i++)diff|=a.charCodeAt(i)^b.charCodeAt(i);
 return diff===0;
}
function randomHex(size=16){const bytes=new Uint8Array(size);crypto.getRandomValues(bytes);return hex(bytes);}
function newSession(){const a=new Uint8Array(32);crypto.getRandomValues(a);return hex(a);}
function bad(request,error,code,message){return error(request,code,message);}
async function json(request,error,max=10000){
 const text=await request.text();
 if(text.length>max)throw new Error("Payload too large");
 try{return JSON.parse(text);}catch{throw new Error("Invalid JSON");}
}
const short=(value,n=120)=>String(value??"").trim().slice(0,n);
const validEmail=email=>/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)&&email.length<=180;
const authMailConfigured=env=>Boolean(env.RESEND_API_KEY&&env.AUTH_EMAIL_FROM);
function ownerPortalLink(env,parameter,token){
 const base=String(env.PUBLIC_APP_URL||"https://thesis-j0n8.onrender.com").replace(/\/$/,"");
 return base+"/#/d1-owner?"+parameter+"="+encodeURIComponent(token);
}
async function sendOwnerAuthEmail(env,to,subject,text){
 if(!authMailConfigured(env))return false;
 try{
  const response=await fetch("https://api.resend.com/emails",{
   method:"POST",
   headers:{"Authorization":"Bearer "+env.RESEND_API_KEY,"Content-Type":"application/json"},
   body:JSON.stringify({from:env.AUTH_EMAIL_FROM,to:[to],subject,text})
  });
  if(!response.ok){console.error("owner authentication email delivery failed",response.status);return false;}
  return true;
 }catch(e){console.error("owner authentication email delivery failed",e?.message||e);return false;}
}
async function issueOwnerEmailToken(env,accountId,kind){
 const token=newSession(),digest=await sha256(token);
 const expires=new Date(Date.now()+(kind==="reset"?60:24*60)*60*1000).toISOString();
 if(kind==="verify"){
  await env.DB.prepare("UPDATE merchant_accounts SET email_verification_token_hash=?,email_verification_expires_at=? WHERE id=?").bind(digest,expires,accountId).run();
 }else{
  await env.DB.prepare("UPDATE merchant_accounts SET password_reset_token_hash=?,password_reset_expires_at=? WHERE id=?").bind(digest,expires,accountId).run();
 }
 return token;
}
async function sendOwnerVerification(env,email,token){
 const link=ownerPortalLink(env,"verify",token);
 return sendOwnerAuthEmail(env,email,"Verify your B-SMART owner email","Verify your B-SMART owner account by opening this link:\n"+link+"\nThis link expires in 24 hours. If you did not request this, ignore this email.");
}
async function sendOwnerPasswordReset(env,email,token){
 const link=ownerPortalLink(env,"reset",token);
 return sendOwnerAuthEmail(env,email,"Reset your B-SMART owner password","A password reset was requested for your B-SMART owner account. Open this link to set a new password:\n"+link+"\nThis link expires in 60 minutes. If you did not request this, ignore this email.");
}
const integer=(value,min,max)=>Number.isInteger(Number(value))&&Number(value)>=min&&Number(value)<=max;
async function viewer(req,env){
 const bearer=req.headers.get("Authorization")||"";
 const match=/^Bearer ([a-f0-9]{64})$/.exec(bearer);
 if(!match)return null;
 const digest=await sha256(match[1]);
 return env.DB.prepare("SELECT a.id,a.email,a.role FROM merchant_sessions s JOIN merchant_accounts a ON a.id=s.account_id WHERE s.token_hash=? AND s.expires_at>? AND a.is_active=1").bind(digest,new Date().toISOString()).first();
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
  env.DB.prepare("SELECT id,sku,name,category,description,brand,tags,compare_at_price_bdt,unit_label,price_bdt,stock_qty,reorder_level,is_listed,created_at,updated_at FROM commerce_products WHERE store_id=? ORDER BY created_at DESC LIMIT 200").bind(store.id).all(),
  env.DB.prepare("SELECT id,order_number,status,status_note,cancellation_reason,total_bdt,placed_at,payment_method,payment_status,payment_received_at,payment_received_by,payment_note,shipping_name,shipping_phone,shipping_address FROM commerce_orders WHERE store_id=? ORDER BY placed_at DESC LIMIT 150").bind(store.id).all(),
  env.DB.prepare("SELECT (SELECT COUNT(*) FROM commerce_orders WHERE store_id=?) AS orders,(SELECT COALESCE(SUM(stock_qty),0) FROM commerce_products WHERE store_id=?) AS inventory_units,(SELECT COALESCE(SUM(total_bdt),0) FROM commerce_orders WHERE store_id=? AND status!='cancelled') AS placed_total_bdt,(SELECT COALESCE(SUM(total_bdt),0) FROM commerce_orders WHERE store_id=? AND status!='cancelled' AND payment_method='cod' AND payment_status='paid') AS cod_paid_total_bdt,(SELECT COALESCE(SUM(total_bdt),0) FROM commerce_orders WHERE store_id=? AND status!='cancelled' AND payment_method='cod' AND payment_status='pending_cod') AS cod_pending_total_bdt,(SELECT COUNT(*) FROM commerce_products WHERE store_id=? AND is_listed=1 AND stock_qty<=reorder_level) AS low_stock_count").bind(store.id,store.id,store.id,store.id,store.id,store.id).first(),
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
   return output(req,{status:"ok",db:"D1",password_auth_ready:true,password_hash:"PBKDF2-HMAC-SHA-256",password_iterations:100000,legacy_access_key_support:true,email_verification_configured:authMailConfigured(env),password_reset_configured:authMailConfigured(env),health_digest_ok:digest.length===64});
  }
  if(method==="POST"&&path==="/api/merchant/register"){
   const b=await json(req,error),email=short(b.email,200).toLowerCase(),password=String(b.password||"");
   if(!validEmail(email))return bad(req,error,422,"Valid email required");
   if(password.length<12||password.length>128)return bad(req,error,422,"Password must contain 12-128 characters");
   if(!authMailConfigured(env))return bad(req,error,503,"Owner email verification is not configured yet");
   const today=await env.DB.prepare("SELECT COUNT(*) AS n FROM merchant_accounts WHERE created_at >= datetime('now','start of day')").first();
   if(Number(today?.n||0)>=20)return bad(req,error,429,"Daily account registration limit reached");
   if(await env.DB.prepare("SELECT id FROM merchant_accounts WHERE email=?").bind(email).first())
     return bad(req,error,409,"Account already exists");
   const id=crypto.randomUUID(),salt=randomHex(16),hash=await passwordDigest(password,salt);
   const verificationToken=newSession(),verificationHash=await sha256(verificationToken);
   const expires=new Date(Date.now()+24*60*60*1000).toISOString();
   try{
    await env.DB.prepare("INSERT INTO merchant_accounts(id,email,password_hash,password_salt,access_key_digest,email_verification_token_hash,email_verification_expires_at) VALUES(?,?,?,?,NULL,?,?)")
     .bind(id,email,hash,salt,verificationHash,expires).run();
   }catch(e){return bad(req,error,errorCode(e),"Unable to create owner account");}
   if(!await sendOwnerVerification(env,email,verificationToken)){
    await env.DB.prepare("DELETE FROM merchant_accounts WHERE id=? AND email_verified_at IS NULL").bind(id).run();
    return bad(req,error,503,"Verification email could not be sent. Please try again later.");
   }
   return output(req,{created:true,requires_email_verification:true},201);
  }
  if(method==="POST"&&path==="/api/merchant/verify-email"){
   const b=await json(req,error),token=String(b.token||"").trim();
   if(!/^[a-f0-9]{64}$/i.test(token))return bad(req,error,400,"Invalid or expired verification link");
   const row=await env.DB.prepare("SELECT id FROM merchant_accounts WHERE email_verification_token_hash=? AND email_verification_expires_at>?").bind(await sha256(token.toLowerCase()),new Date().toISOString()).first();
   if(!row)return bad(req,error,400,"Invalid or expired verification link");
   const result=await env.DB.prepare("UPDATE merchant_accounts SET email_verified_at=CURRENT_TIMESTAMP,email_verification_token_hash=NULL,email_verification_expires_at=NULL WHERE id=? AND email_verified_at IS NULL").bind(row.id).run();
   if(!result.meta?.changes)return bad(req,error,409,"Email is already verified or the link has expired");
   return output(req,{verified:true});
  }
  if(method==="POST"&&path==="/api/merchant/resend-verification"){
   if(!authMailConfigured(env))return bad(req,error,503,"Owner email verification is not configured yet");
   const b=await json(req,error),email=short(b.email,200).toLowerCase();
   if(validEmail(email)){
    const row=await env.DB.prepare("SELECT id,email,email_verified_at FROM merchant_accounts WHERE email=?").bind(email).first();
    if(row&&!row.email_verified_at){
     const token=await issueOwnerEmailToken(env,row.id,"verify");
     if(!await sendOwnerVerification(env,row.email,token))return bad(req,error,503,"Verification email could not be sent. Please try again later.");
    }
   }
   return output(req,{sent:true,message:"If the account needs verification, an email has been sent."},202);
  }
  if(method==="POST"&&path==="/api/merchant/forgot-password"){
   if(!authMailConfigured(env))return bad(req,error,503,"Password recovery email is not configured yet");
   const b=await json(req,error),email=short(b.email,200).toLowerCase();
   if(validEmail(email)){
    const row=await env.DB.prepare("SELECT id,email FROM merchant_accounts WHERE email=?").bind(email).first();
    if(row){
     const token=await issueOwnerEmailToken(env,row.id,"reset");
     if(!await sendOwnerPasswordReset(env,row.email,token))return bad(req,error,503,"Password recovery email could not be sent. Please try again later.");
    }
   }
   return output(req,{sent:true,message:"If an account exists for this email, a password reset link has been sent."},202);
  }
  if(method==="POST"&&path==="/api/merchant/reset-password"){
   const b=await json(req,error),token=String(b.token||"").trim(),password=String(b.password||"");
   if(!/^[a-f0-9]{64}$/i.test(token))return bad(req,error,400,"Invalid or expired password reset link");
   if(password.length<12||password.length>128)return bad(req,error,422,"Password must contain 12-128 characters");
   const row=await env.DB.prepare("SELECT id FROM merchant_accounts WHERE password_reset_token_hash=? AND password_reset_expires_at>?").bind(await sha256(token.toLowerCase()),new Date().toISOString()).first();
   if(!row)return bad(req,error,400,"Invalid or expired password reset link");
   const salt=randomHex(16),hash=await passwordDigest(password,salt);
   const consumed=await env.DB.prepare("UPDATE merchant_accounts SET password_hash=?,password_salt=?,email_verified_at=COALESCE(email_verified_at,CURRENT_TIMESTAMP),password_reset_token_hash=NULL,password_reset_expires_at=NULL,email_verification_token_hash=NULL,email_verification_expires_at=NULL WHERE id=? AND password_reset_token_hash=?").bind(hash,salt,row.id,await sha256(token.toLowerCase())).run();
   if(!consumed.meta?.changes)return bad(req,error,400,"Invalid or expired password reset link");
   await env.DB.batch([
    env.DB.prepare("DELETE FROM merchant_sessions WHERE account_id=?").bind(row.id),
    env.DB.prepare("DELETE FROM merchant_login_attempts WHERE email=(SELECT email FROM merchant_accounts WHERE id=?)").bind(row.id)
   ]);
   return output(req,{reset:true,sessions_revoked:true});
  }
  if(method==="POST"&&path==="/api/merchant/login"){
   const b=await json(req,error),email=short(b.email,200).toLowerCase(),password=String(b.password||"");
   const legacyKey=String(b.access_key||(/^[0-9a-f]{64}$/i.test(password)?password:"")).trim().toLowerCase();
   if(!validEmail(email)||(!password&&!legacyKey))return bad(req,error,401,"Invalid email or password");
   const now=new Date().toISOString();
   const lock=await env.DB.prepare("SELECT failures,lock_until FROM merchant_login_attempts WHERE email=?").bind(email).first();
   if(lock?.lock_until&&lock.lock_until>now)return bad(req,error,429,"Too many attempts; try again later");
   const acc=await env.DB.prepare("SELECT id,email,password_hash,password_salt,access_key_digest,email_verified_at,is_active,role FROM merchant_accounts WHERE email=?").bind(email).first();
   let valid=false;
   if(acc&&password.length>=12&&acc.password_salt&&acc.password_salt!=="DISABLED"&&acc.password_hash!=="ACCESS_KEY_ONLY"){
    valid=constantTimeEqual(await passwordDigest(password,acc.password_salt),acc.password_hash);
   }
   if(!valid&&acc&&/^[0-9a-f]{64}$/.test(legacyKey)){
    valid=constantTimeEqual(await sha256(legacyKey),acc.access_key_digest||"");
   }
   if(valid&&!Number(acc.is_active??1))return bad(req,error,403,"This owner account is suspended. Contact the platform administrator.");
   if(valid&&acc.role!=="owner")return bad(req,error,403,"This account role cannot access the owner panel.");
   if(valid&&acc.password_hash!=="ACCESS_KEY_ONLY"&&!acc.email_verified_at)
    return bad(req,error,403,"Please verify your email before signing in. Use the verification link sent to your inbox.");
   if(!valid){
    const failures=(lock?.failures||0)+1,until=failures>=6?new Date(Date.now()+15*60*1000).toISOString():null;
    await env.DB.prepare("INSERT INTO merchant_login_attempts(email,failures,lock_until) VALUES(?,?,?) ON CONFLICT(email) DO UPDATE SET failures=excluded.failures,lock_until=excluded.lock_until").bind(email,failures,until).run();
    return bad(req,error,401,"Invalid email or password");
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
   if(body.confirm!=="DELETE MERCHANT ACCOUNT")return bad(req,error,422,"Explicit account deletion confirmation required");
   const store=await myStore(env,owner);
   if(store&&!store.id.startsWith("merchant-"))
     return bad(req,error,409,"Only owner-created merchant stores can be deleted automatically");
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
   if(method==="GET"&&path==="/api/merchant/coupons"){
    const store=await storeOnly(env,owner);
    const {results}=await env.DB.prepare("SELECT c.*,(SELECT COUNT(*) FROM commerce_coupon_redemptions r WHERE r.coupon_id=c.id) AS usage_count FROM commerce_coupons c WHERE c.store_id=? ORDER BY c.created_at DESC").bind(store.id).all();
    return output(req,{coupons:results||[]});
   }
   if(method==="POST"&&path==="/api/merchant/coupons"){
    const store=await storeOnly(env,owner),b=await json(req,error);
    const code=short(b.code,32).toUpperCase(),type=String(b.discount_type||"percent");
    const value=Number(b.discount_value),minimum=Number(b.min_order_bdt??0);
    const maximum=b.max_discount_bdt===""||b.max_discount_bdt===null||b.max_discount_bdt===undefined?null:Number(b.max_discount_bdt);
    const usage=b.usage_limit===""||b.usage_limit===null||b.usage_limit===undefined?null:Number(b.usage_limit);
    const perCustomer=b.per_customer_limit===""||b.per_customer_limit===null||b.per_customer_limit===undefined?null:Number(b.per_customer_limit);
    const starts=short(b.starts_at,40)||null,ends=short(b.ends_at,40)||null;
    if(!/^[A-Z0-9_-]{3,32}$/.test(code)||!["percent","fixed"].includes(type)||
       !integer(value,1,type==="percent"?100:10000000)||!integer(minimum,0,5000000)||
       (maximum!==null&&!integer(maximum,1,5000000))||(usage!==null&&!integer(usage,1,10000000))||
       (perCustomer!==null&&!integer(perCustomer,1,1000000))||
       (starts&&!Number.isFinite(Date.parse(starts)))||(ends&&!Number.isFinite(Date.parse(ends)))||
       (starts&&ends&&Date.parse(ends)<=Date.parse(starts)))
      return bad(req,error,422,"কুপনের তথ্য সঠিক নয়। কোড, ছাড়, সীমা ও তারিখ যাচাই করুন।");
    const id=crypto.randomUUID();
    try{
     await env.DB.prepare("INSERT INTO commerce_coupons(id,store_id,code,discount_type,discount_value,min_order_bdt,max_discount_bdt,usage_limit,per_customer_limit,starts_at,ends_at,is_active) VALUES(?,?,?,?,?,?,?,?,?,?,?,1)")
      .bind(id,store.id,code,type,value,minimum,maximum,usage,perCustomer,starts,ends).run();
    }catch(e){return bad(req,error,errorCode(e),"এই কুপন কোডটি আগে থেকেই আছে অথবা তথ্য সংরক্ষণ করা যায়নি।");}
    return output(req,{created:true,id},201);
   }
   const couponPath=/^\/api\/merchant\/coupons\/([a-zA-Z0-9-]{2,90})$/.exec(path);
   if(couponPath&&method==="PATCH"){
    const store=await storeOnly(env,owner),b=await json(req,error);
    const current=await env.DB.prepare("SELECT * FROM commerce_coupons WHERE id=? AND store_id=?").bind(couponPath[1],store.id).first();
    if(!current)return bad(req,error,404,"কুপন পাওয়া যায়নি।");
    const code=short(b.code??current.code,32).toUpperCase(),type=String(b.discount_type??current.discount_type);
    const value=Number(b.discount_value??current.discount_value),minimum=Number(b.min_order_bdt??current.min_order_bdt);
    const maximum=b.max_discount_bdt===undefined?current.max_discount_bdt:(b.max_discount_bdt===""||b.max_discount_bdt===null?null:Number(b.max_discount_bdt));
    const usage=b.usage_limit===undefined?current.usage_limit:(b.usage_limit===""||b.usage_limit===null?null:Number(b.usage_limit));
    const perCustomer=b.per_customer_limit===undefined?current.per_customer_limit:(b.per_customer_limit===""||b.per_customer_limit===null?null:Number(b.per_customer_limit));
    const starts=b.starts_at===undefined?current.starts_at:(short(b.starts_at,40)||null),ends=b.ends_at===undefined?current.ends_at:(short(b.ends_at,40)||null);
    const active=b.is_active===undefined?current.is_active:(b.is_active?1:0);
    if(!/^[A-Z0-9_-]{3,32}$/.test(code)||!["percent","fixed"].includes(type)||
       !integer(value,1,type==="percent"?100:10000000)||!integer(minimum,0,5000000)||
       (maximum!==null&&!integer(maximum,1,5000000))||(usage!==null&&!integer(usage,1,10000000))||
       (perCustomer!==null&&!integer(perCustomer,1,1000000))||
       (starts&&!Number.isFinite(Date.parse(starts)))||(ends&&!Number.isFinite(Date.parse(ends)))||
       (starts&&ends&&Date.parse(ends)<=Date.parse(starts)))
      return bad(req,error,422,"কুপনের তথ্য সঠিক নয়।");
    try{
     await env.DB.prepare("UPDATE commerce_coupons SET code=?,discount_type=?,discount_value=?,min_order_bdt=?,max_discount_bdt=?,usage_limit=?,per_customer_limit=?,starts_at=?,ends_at=?,is_active=? WHERE id=? AND store_id=?")
      .bind(code,type,value,minimum,maximum,usage,perCustomer,starts,ends,active,couponPath[1],store.id).run();
    }catch(e){return bad(req,error,errorCode(e),"কুপন আপডেট করা যায়নি।");}
    return output(req,{updated:true});
   }
   if(couponPath&&method==="DELETE"){
    const store=await storeOnly(env,owner);
    const result=await env.DB.prepare("UPDATE commerce_coupons SET is_active=0 WHERE id=? AND store_id=?").bind(couponPath[1],store.id).run();
    if(!result.meta?.changes)return bad(req,error,404,"কুপন পাওয়া যায়নি।");
    return output(req,{deactivated:true});
   }

   if(method==="POST"&&path==="/api/merchant/assistant"){
    const store=await storeOnly(env,owner),b=await json(req,error,6000),question=short(b.question,500);
    if(question.length<2)return bad(req,error,422,"কমপক্ষে ২ অক্ষরের প্রশ্ন লিখুন।");
    try{return output(req,await ownerAssistantAnswer(env,req,owner,store,question,b.history));}
    catch(e){if(e.status===429)return bad(req,error,429,e.message);throw e;}
   }
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
    return output(req,{updated:true,status,inventory_restocked:status==="received",note:store.is_demo?"Archived return record only; no money was refunded":"Return received and inventory restocked; no automated refund was issued."});
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
   const name=short(b.name,110),tagline=short(b.tagline,160),category=short(b.category,50),area=short(b.area,100);
   if(name.length<3||!category||!area)return bad(req,error,422,"Store name, category and area are required");
   const id="merchant-"+crypto.randomUUID();
   const slug="shop-"+crypto.randomUUID().slice(0,12);
   await env.DB.prepare("INSERT INTO commerce_stores(id,slug,name,tagline,category,area,theme,color,is_demo,is_active,owner_id,delivery_note) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)").bind(id,slug,name,tagline,category,area,"clean","#087e59",0,0,owner.id,"Awaiting platform review").run();
   return output(req,{created:true,store:stripStore(await myStore(env,owner))},201);
  }
  if(method==="PATCH"&&path==="/api/merchant/store"){
   const store=await storeOnly(env,owner),b=await json(req,error);
   const name=short(b.name??store.name,110),tagline=short(b.tagline??store.tagline,160);
   const area=short(b.area??store.area,100),category=short(b.category??store.category,50);
   if(name.length<3||!area||!category)return bad(req,error,422,"Invalid store profile");
   if(b.is_active===true&&!store.is_active)return bad(req,error,403,"A platform administrator must approve and publish this store");
   const active=b.is_active===false?0:Number(store.is_active);
   await env.DB.prepare("UPDATE commerce_stores SET name=?,tagline=?,category=?,area=?,is_active=? WHERE id=? AND owner_id=?").bind(name,tagline,category,area,active,store.id,owner.id).run();
   return output(req,{store:stripStore(await myStore(env,owner))});
  }
  if(method==="POST"&&path==="/api/merchant/cashbook"){
   const store=await storeOnly(env,owner),b=await json(req,error);
   const kind=short(b.kind,15),amount=Number(b.amount_bdt),description=short(b.description,140);
   if(!["receipt","expense"].includes(kind)||!integer(amount,1,500000)||description.length<3)
    return bad(req,error,422,"Valid transaction type, amount and description required");
   await env.DB.prepare("INSERT INTO commerce_cashbook(id,store_id,kind,amount_bdt,description) VALUES(?,?,?,?,?)").bind(crypto.randomUUID(),store.id,kind,amount,description).run();
   return output(req,{created:true,note:"Cashbook entry saved"});
  }
  if(method==="POST"&&path==="/api/merchant/pos"){
   const store=await storeOnly(env,owner),demo=!!store.is_demo;
   const b=await json(req,error);
   if(!Array.isArray(b.items)||!b.items.length||b.items.length>12)return bad(req,error,422,"1-12 distinct products are required");
   const details=[],seen=new Set();let total=0;
   for(const item of b.items){
    const productId=String(item.product_id||""),qty=Number(item.quantity);
    if(!productId||seen.has(productId)||!integer(qty,1,30))return bad(req,error,422,"Invalid POS line");
    seen.add(productId);
    const p=await env.DB.prepare("SELECT * FROM commerce_products WHERE id=? AND store_id=? AND is_listed=1").bind(productId,store.id).first();
    if(!p||p.stock_qty<qty)return bad(req,error,409,"Product unavailable or stock insufficient");
    if(!Number.isSafeInteger(Number(p.price_bdt))||Number(p.price_bdt)<0)return bad(req,error,409,"Invalid product price");
    total+=Number(p.price_bdt)*qty;details.push({p,qty});
   }
   if(!integer(total,1,5000000))return bad(req,error,422,"Invalid POS total");
   const oid=crypto.randomUUID(),cid=crypto.randomUUID(),token=newSession(),number="POS-"+oid.slice(0,8).toUpperCase();
   const methodName=demo?"demo_pos":"cash";
   const customerName=demo?"Anonymous demo counter customer":"Walk-in customer";
   const statements=[
    env.DB.prepare("INSERT INTO commerce_customers(id,store_id,display_name) VALUES(?,?,?)").bind(cid,store.id,customerName),
    env.DB.prepare("INSERT INTO commerce_orders(id,store_id,order_number,access_token,status,subtotal_bdt,total_bdt,payment_method,shipping_name,shipping_phone,shipping_address,customer_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)").bind(oid,store.id,number,token,"fulfilled",total,total,methodName,customerName,"","",cid),
    ...details.map(({p,qty})=>env.DB.prepare("INSERT INTO commerce_order_lines(order_id,product_id,product_name,quantity,price_bdt,line_total_bdt) VALUES(?,?,?,?,?,?)").bind(oid,p.id,p.name,qty,p.price_bdt,p.price_bdt*qty)),
    ...(!demo?[env.DB.prepare("UPDATE commerce_orders SET payment_status='paid',payment_received_at=CURRENT_TIMESTAMP,payment_received_by=?,payment_note='Cash collected at POS' WHERE id=?").bind(owner.email,oid)]:[]),
    env.DB.prepare("INSERT INTO commerce_cashbook(id,store_id,kind,amount_bdt,description,related_order_id) VALUES(?,?,?,?,?,?)").bind(crypto.randomUUID(),store.id,"receipt",total,demo?"Archived POS record":"POS cash sale",oid)
   ];
   try{await env.DB.batch(statements);}catch(e){return bad(req,error,409,"Stock or product data changed; refresh and retry");}
   return output(req,{created:true,order_number:number,total_bdt:total,payment_status:demo?"demo_no_payment":"paid",note:demo?"Demo sale recorded":"Cash sale, payment and stock movement recorded"},201);
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
   const id=crypto.randomUUID(),price=Number(b.price_bdt),qty=Number(b.stock_qty),reorder=integer(b.reorder_level??5,0,1000000)?Number(b.reorder_level??5):5;
   try{
    await env.DB.prepare("INSERT INTO commerce_products(id,store_id,sku,name,category,description,brand,tags,compare_at_price_bdt,unit_label,price_bdt,stock_qty,reorder_level,is_listed,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)")
     .bind(id,store.id,sku,name,cat,description||null,brand||null,tags,compare,unit,price,qty,reorder,b.is_listed===true?1:0).run();
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
   const reorder=b.reorder_level===undefined?Number(p.reorder_level??5):Number(b.reorder_level);
   const description=short(b.description===undefined?p.description:b.description,3000),brand=short(b.brand===undefined?p.brand:b.brand,100);
   const unit=short(b.unit_label===undefined?(p.unit_label||"pcs"):b.unit_label,24);
   let tags=p.tags||"[]";
   if(b.tags!==undefined)tags=JSON.stringify(Array.isArray(b.tags)?b.tags.map(x=>short(x,32)).filter(Boolean).slice(0,12):[]);
   const compare=b.compare_at_price_bdt===undefined?p.compare_at_price_bdt:(b.compare_at_price_bdt===""||b.compare_at_price_bdt===null?null:Number(b.compare_at_price_bdt));
   if(!name||!integer(price,0,10000000)||!integer(qty,0,1000000)||!integer(reorder,0,1000000)||
      (compare!==null&&compare!==undefined&&(!integer(compare,0,10000000)||compare<price)))
    return bad(req,error,422,"Invalid product fields");
   const listed=b.is_listed===undefined?p.is_listed:(b.is_listed===true?1:0);
   const diff=qty-p.stock_qty;
   const update=env.DB.prepare("UPDATE commerce_products SET name=?,category=?,description=?,brand=?,tags=?,compare_at_price_bdt=?,unit_label=?,price_bdt=?,stock_qty=?,reorder_level=?,is_listed=?,updated_at=CURRENT_TIMESTAMP WHERE store_id=? AND id=?").bind(name,cat,description||null,brand||null,tags,compare??null,unit,price,qty,reorder,listed,store.id,p.id);
   if(diff) {
    await env.DB.batch([update,env.DB.prepare("INSERT INTO commerce_stock_adjustments(id,store_id,product_id,old_quantity,new_quantity,delta,reason) VALUES(?,?,?,?,?,?,?)").bind(crypto.randomUUID(),store.id,p.id,p.stock_qty,qty,diff,"Owner manual inventory correction")]);
   } else await update.run();
   return output(req,{updated:true,stock_change:diff});
  }
  const paymentMatch=/^\/api\/merchant\/orders\/([a-zA-Z0-9-]{2,90})\/payment$/.exec(path);
  if(method==="PATCH"&&paymentMatch){
   const store=await storeOnly(env,owner),body=await json(req,error),id=paymentMatch[1];
   if(store.is_demo)return bad(req,error,409,"This order has no payment to collect");
   const order=await env.DB.prepare("SELECT id,status,payment_method,payment_status FROM commerce_orders WHERE store_id=? AND id=?").bind(store.id,id).first();
   if(!order)return bad(req,error,404,"Order not found");
   if(order.payment_method!=="cod")return bad(req,error,409,"Only cash-on-delivery orders can be recorded here");
   if(!["delivered","fulfilled"].includes(order.status))return bad(req,error,409,"Confirm delivery before recording COD collection");
   if(order.payment_status==="paid")return output(req,{updated:false,payment_status:"paid",note:"COD collection was already recorded"});
   if(order.payment_status!=="pending_cod")return bad(req,error,409,"This order is not awaiting COD collection");
   const paymentNote=short(body.payment_note,300);
   const updated=await env.DB.prepare("UPDATE commerce_orders SET payment_status='paid',payment_received_at=CURRENT_TIMESTAMP,payment_received_by=?,payment_note=? WHERE id=? AND store_id=? AND payment_method='cod' AND payment_status='pending_cod' AND status IN ('delivered','fulfilled')")
    .bind(owner.email,paymentNote||null,id,store.id).run();
   if(!updated.meta?.changes)return bad(req,error,409,"Payment status changed; refresh and retry");
   const saved=await env.DB.prepare("SELECT payment_status,payment_received_at,payment_received_by,payment_note FROM commerce_orders WHERE id=? AND store_id=?").bind(id,store.id).first();
   return output(req,{updated:true,...saved});
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
