import test from "node:test";
import assert from "node:assert/strict";
import { webcrypto } from "node:crypto";
import { readFileSync } from "node:fs";
import { merchantRouter } from "../../cloudflare/merchant-routes.js";

if (!globalThis.crypto) globalThis.crypto = webcrypto;
const source = readFileSync(new URL("../../cloudflare/merchant-routes.js", import.meta.url), "utf8");
const ui = readFileSync(new URL("../src/pages/D1MerchantCenter.jsx", import.meta.url), "utf8");
const platformAdminSource = readFileSync(new URL("../../cloudflare/platform-admin-routes.js", import.meta.url), "utf8");
let sentEmails = [];
globalThis.fetch = async (url, options) => {
  assert.equal(url, "https://api.resend.com/emails");
  sentEmails.push(JSON.parse(options.body));
  return new Response(JSON.stringify({ id: "test-email" }), { status: 200 });
};

const output = (_request, body, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
const error = (_request, status, detail) => output(null, { detail }, status);

function createD1Mock() {
  const accounts = new Map();
  const sessions = new Map();
  const attempts = new Map();
  const stores = new Map();
  const env = {
    RESEND_API_KEY: "test-resend-key",
    AUTH_EMAIL_FROM: "B-SMART Tests <test@example.invalid>",
    PUBLIC_APP_URL: "https://thesis-j0n8.onrender.com",
    DB: {
      prepare(sql) {
        let args = [];
        const statement = {
          bind(...values) { args = values; return this; },
          async first() {
            if (sql.startsWith("SELECT COUNT(*) AS n FROM merchant_accounts")) return { n: accounts.size };
            if (sql.startsWith("SELECT id FROM merchant_accounts WHERE email=?") ||
                sql.startsWith("SELECT id,email FROM merchant_accounts WHERE email=?") ||
                sql.startsWith("SELECT id,email,email_verified_at FROM merchant_accounts WHERE email=?")) {
              const row = accounts.get(args[0]);
              return row ? (sql.includes("email_verified_at") ? {id:row.id,email:row.email,email_verified_at:row.email_verified_at} : {id:row.id,email:row.email}) : null;
            }
            if (sql.startsWith("SELECT id FROM merchant_accounts WHERE email_verification_token_hash=?")) {
              const row = [...accounts.values()].find(a => a.email_verification_token_hash === args[0] && a.email_verification_expires_at > args[1]);
              return row ? {id:row.id} : null;
            }
            if (sql.startsWith("SELECT id FROM merchant_accounts WHERE password_reset_token_hash=?")) {
              const row = [...accounts.values()].find(a => a.password_reset_token_hash === args[0] && a.password_reset_expires_at > args[1]);
              return row ? {id:row.id} : null;
            }
            if (sql.startsWith("SELECT failures,lock_until FROM merchant_login_attempts")) return attempts.get(args[0]) || null;
            if (sql.startsWith("SELECT id,email,password_hash,password_salt,access_key_digest,email_verified_at,is_active,role FROM merchant_accounts")) return accounts.get(args[0]) || null;
            if (sql.startsWith("SELECT a.id,a.email,a.role FROM merchant_sessions")) {
              const session = sessions.get(args[0]);
              if (!session || session.expires_at <= args[1]) return null;
              const account = [...accounts.values()].find(row => row.id === session.account_id);
              return account ? { id: account.id, email: account.email } : null;
            }
            if (sql.startsWith("SELECT * FROM commerce_stores WHERE owner_id=?")) {
              return [...stores.values()].find(store => store.owner_id === args[0]) || null;
            }
            throw new Error("Unexpected D1 first query: " + sql);
          },
          async run() {
            if (sql.startsWith("INSERT INTO merchant_accounts")) {
              const [id,email,password_hash,password_salt,verificationHash,verificationExpiry] = args;
              if (accounts.has(email)) throw new Error("UNIQUE constraint failed");
              accounts.set(email,{id,email,password_hash,password_salt,access_key_digest:null,email_verified_at:null,email_verification_token_hash:verificationHash,email_verification_expires_at:verificationExpiry,password_reset_token_hash:null,password_reset_expires_at:null,is_active:1,role:"owner"});
            } else if (sql.startsWith("UPDATE merchant_accounts SET email_verification_token_hash")) {
              const [hash,expiry,id]=args, row=[...accounts.values()].find(a=>a.id===id);
              if(row)Object.assign(row,{email_verification_token_hash:hash,email_verification_expires_at:expiry});
            } else if (sql.startsWith("UPDATE merchant_accounts SET password_reset_token_hash")) {
              const [hash,expiry,id]=args, row=[...accounts.values()].find(a=>a.id===id);
              if(row)Object.assign(row,{password_reset_token_hash:hash,password_reset_expires_at:expiry});
            } else if (sql.startsWith("UPDATE merchant_accounts SET email_verified_at")) {
              const row=[...accounts.values()].find(a=>a.id===args[0]);
              if(row&&!row.email_verified_at){row.email_verified_at=new Date().toISOString();row.email_verification_token_hash=null;row.email_verification_expires_at=null;return {meta:{changes:1}};}
              return {meta:{changes:0}};
            } else if (sql.startsWith("UPDATE merchant_accounts SET password_hash=")) {
              const [password_hash,password_salt,id,tokenHash]=args,row=[...accounts.values()].find(a=>a.id===id);
              if(!row||row.password_reset_token_hash!==tokenHash)return {meta:{changes:0}};
              Object.assign(row,{password_hash,password_salt,email_verified_at:row.email_verified_at||new Date().toISOString(),password_reset_token_hash:null,password_reset_expires_at:null,email_verification_token_hash:null,email_verification_expires_at:null});
            } else if (sql.startsWith("DELETE FROM merchant_accounts")) {
              const row=[...accounts.values()].find(a=>a.id===args[0]);
              if(row)accounts.delete(row.email);
            } else if (sql.startsWith("DELETE FROM merchant_sessions")) {
              for(const [hash,session] of sessions)if(session.account_id===args[0])sessions.delete(hash);
            } else if (sql.startsWith("DELETE FROM merchant_login_attempts WHERE email=(SELECT")) {
              const row=[...accounts.values()].find(a=>a.id===args[0]);if(row)attempts.delete(row.email);
            } else if (sql.startsWith("DELETE FROM merchant_login_attempts")) {
              attempts.delete(args[0]);
            } else if (sql.startsWith("INSERT INTO merchant_login_attempts")) {
              attempts.set(args[0],{failures:args[1],lock_until:args[2]});
            } else if (sql.startsWith("INSERT INTO merchant_sessions")) {
              sessions.set(args[0],{account_id:args[1],expires_at:args[2]});
            } else if (sql.startsWith("INSERT INTO commerce_stores")) {
              const [id,slug,name,tagline,category,area,theme,color,is_demo,is_active,owner_id,delivery_note]=args;
              stores.set(id,{id,slug,name,tagline,category,area,theme,color,is_demo,is_active,owner_id,delivery_note,created_at:"2026-11-07"});
            } else if (sql.startsWith("UPDATE commerce_stores SET name=?")) {
              const [name,tagline,category,area,is_active,id,owner_id]=args;
              const row=stores.get(id);
              if(row&&row.owner_id===owner_id)Object.assign(row,{name,tagline,category,area,is_active});
            } else {
              throw new Error("Unexpected D1 run query: " + sql);
            }
            return {meta:{changes:1}};
          }
        };
        return statement;
      },
      async batch(statements) {
        const results=[];
        for(const statement of statements)results.push(await statement.run());
        return results;
      }
    }
  };
  return Object.assign(env,{inspect:{accounts,sessions,stores,attempts}});
}

async function call(env, path, body, token, method = "POST") {
  const request = new Request("https://example.invalid"+path, {
    method,
    headers: { "content-type":"application/json", ...(token ? {Authorization:"Bearer "+token} : {}) },
    ...(body === undefined ? {} : {body:JSON.stringify(body)}),
  });
  const response = await merchantRouter(request, env, path, output, error);
  return {status:response.status, body:await response.json()};
}
function emailToken(parameter="verify") {
  const email=sentEmails.at(-1);
  const match=email?.text.match(new RegExp(parameter+"=([a-f0-9]{64})"));
  assert.ok(match,"Expected a single-use token in the outbound email link");
  return match[1];
}
async function registerAndVerify(env,email="owner@example.invalid",password="correct-horse-battery") {
  sentEmails=[];
  const registered=await call(env,"/api/merchant/register",{email,password});
  assert.equal(registered.status,201,JSON.stringify(registered.body));
  const token=emailToken("verify");
  const verified=await call(env,"/api/merchant/verify-email",{token});
  assert.equal(verified.status,200,JSON.stringify(verified.body));
  return {registered,token};
}

test("merchant owner registration stores a PBKDF2 hash and sends a hashed, expiring verification token", async () => {
  const env=createD1Mock(),email="owner@example.invalid",password="correct-horse-battery";
  sentEmails=[];
  const registered=await call(env,"/api/merchant/register",{email,password});
  assert.equal(registered.status,201,JSON.stringify(registered.body));
  assert.equal(registered.body.requires_email_verification,true);
  assert.equal(sentEmails.length,1);
  const account=env.inspect.accounts.get(email);
  assert.ok(account.password_hash);
  assert.notEqual(account.password_hash,password);
  assert.equal(account.password_salt.length,32);
  assert.equal(account.access_key_digest,null);
  assert.equal(account.email_verified_at,null);
  const token=emailToken("verify");
  assert.notEqual(account.email_verification_token_hash,token);
  const blocked=await call(env,"/api/merchant/login",{email,password});
  assert.equal(blocked.status,403);
  const verified=await call(env,"/api/merchant/verify-email",{token});
  assert.equal(verified.status,200);
  assert.equal(env.inspect.accounts.get(email).email_verified_at!==null,true);
  const duplicate=await call(env,"/api/merchant/register",{email,password});
  assert.equal(duplicate.status,409);
  const reused=await call(env,"/api/merchant/verify-email",{token});
  assert.equal(reused.status,400);
});

test("merchant login verifies password, requires verified email and rejects incorrect credentials", async () => {
  const env=createD1Mock(),email="owner@example.invalid",password="correct-horse-battery";
  await registerAndVerify(env,email,password);
  const wrong=await call(env,"/api/merchant/login",{email,password:"incorrect-password"});
  assert.equal(wrong.status,401);
  const loggedIn=await call(env,"/api/merchant/login",{email,password});
  assert.equal(loggedIn.status,200,JSON.stringify(loggedIn.body));
  assert.match(loggedIn.body.token,/^[a-f0-9]{64}$/);
});

test("password reset uses a one-time expiring token and revokes existing owner sessions", async () => {
  const env=createD1Mock(),email="owner@example.invalid",password="correct-horse-battery";
  await registerAndVerify(env,email,password);
  const login=await call(env,"/api/merchant/login",{email,password});
  assert.equal(login.status,200);
  sentEmails=[];
  const forgot=await call(env,"/api/merchant/forgot-password",{email});
  assert.equal(forgot.status,202);
  const token=emailToken("reset");
  const reset=await call(env,"/api/merchant/reset-password",{token,password:"a-new-secure-password-2026"});
  assert.equal(reset.status,200,JSON.stringify(reset.body));
  assert.equal(reset.body.sessions_revoked,true);
  const oldSession=await call(env,"/api/merchant/dashboard",undefined,login.body.token,"GET");
  assert.equal(oldSession.status,401);
  const oldPassword=await call(env,"/api/merchant/login",{email,password});
  assert.equal(oldPassword.status,401);
  const newPassword=await call(env,"/api/merchant/login",{email,password:"a-new-secure-password-2026"});
  assert.equal(newPassword.status,200);
  const reused=await call(env,"/api/merchant/reset-password",{token,password:"another-secure-password-2026"});
  assert.equal(reused.status,400);
});

test("owner registration fails closed when an email provider is not configured", async () => {
  const env=createD1Mock();delete env.RESEND_API_KEY;
  const result=await call(env,"/api/merchant/register",{email:"owner@example.invalid",password:"correct-horse-battery"});
  assert.equal(result.status,503);
  assert.equal(env.inspect.accounts.size,0);
});

test("new merchant stores are private until platform approval", async () => {
  const env=createD1Mock(),email="owner@example.invalid",password="correct-horse-battery";
  await registerAndVerify(env,email,password);
  const login=await call(env,"/api/merchant/login",{email,password});
  const created=await call(env,"/api/merchant/store",{name:"Example Shop",tagline:"Local goods",category:"মুদি",area:"Dhaka"},login.body.token);
  assert.equal(created.status,201,JSON.stringify(created.body));
  assert.equal(created.body.store.is_demo,false);
  assert.equal(created.body.store.is_active,false);
  assert.equal(created.body.store.tagline,"Local goods");
  const attemptedPublish=await call(env,"/api/merchant/store",{name:"Example Shop",category:"মুদি",area:"Dhaka",is_active:true},login.body.token,"PATCH");
  assert.equal(attemptedPublish.status,403);
});

test("approved-store POS records real cash collection in D1 rather than a simulated sale", () => {
  assert.match(source,/const methodName=demo\?"demo_pos":"cash"/);
  assert.match(source,/payment_status='paid',payment_received_at=CURRENT_TIMESTAMP,payment_received_by/);
  assert.match(source,/demo\?"Simulated demo POS receipt":"POS cash sale"/);
});

test("merchant UI exposes verification, recovery and owner POS workflows", () => {
  assert.match(ui,/form\.password/);
  assert.match(ui,/\/api\/merchant\/verify-email/);
  assert.match(ui,/\/api\/merchant\/forgot-password/);
  assert.match(ui,/\/api\/merchant\/reset-password/);
  assert.doesNotMatch(ui,/setOneTimeKey|oneTimeKey/);
  assert.match(ui,/\{view==="pos"&&<div className="dm-stack">/);
  assert.doesNotMatch(ui,/filter\(\(\[k\]\)=>k!=="pos"\|\|store\.is_demo\)/);
});

test("platform admin can audit owner access and suspend accounts without exposing credentials",()=>{
  assert.match(platformAdminSource,/api\/platform-admin\/owners/);
  assert.match(platformAdminSource,/a\.email,a\.role,a\.is_active,a\.email_verified_at/);
  assert.match(platformAdminSource,/DELETE FROM merchant_sessions WHERE account_id=/);
  assert.doesNotMatch(platformAdminSource,/password_salt/);
  assert.match(ui,/Owner accounts/);
});
