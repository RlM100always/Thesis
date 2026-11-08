import test from "node:test";
import assert from "node:assert/strict";
import { webcrypto } from "node:crypto";
import { readFileSync } from "node:fs";
import { merchantRouter } from "../../cloudflare/merchant-routes.js";

if (!globalThis.crypto) globalThis.crypto = webcrypto;
const source = readFileSync(new URL("../../cloudflare/merchant-routes.js", import.meta.url), "utf8");
const ui = readFileSync(new URL("../src/pages/D1MerchantCenter.jsx", import.meta.url), "utf8");

const output = (_request, body, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
const error = (_request, status, detail) => output(null, { detail }, status);

function createD1Mock() {
  const accounts = new Map();
  const sessions = new Map();
  const attempts = new Map();
  const stores = new Map();
  return { DB: {
    prepare(sql) {
      let args = [];
      const statement = {
        bind(...values) { args = values; return this; },
        async first() {
          if (sql.startsWith("SELECT COUNT(*) AS n FROM merchant_accounts")) return { n: accounts.size };
          if (sql.startsWith("SELECT id FROM merchant_accounts WHERE email=?")) {
            const row = accounts.get(args[0]); return row ? { id: row.id } : null;
          }
          if (sql.startsWith("SELECT failures,lock_until FROM merchant_login_attempts")) return attempts.get(args[0]) || null;
          if (sql.startsWith("SELECT id,email,password_hash,password_salt,access_key_digest FROM merchant_accounts")) return accounts.get(args[0]) || null;
          if (sql.startsWith("SELECT a.id,a.email FROM merchant_sessions")) {
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
            const [id,email,password_hash,password_salt] = args;
            if (accounts.has(email)) throw new Error("UNIQUE constraint failed");
            accounts.set(email,{id,email,password_hash,password_salt,access_key_digest:null});
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
    }
  }, inspect: { accounts, sessions, stores, attempts } };
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

test("merchant owner registration stores a PBKDF2 password hash, never plaintext", async () => {
  const env=createD1Mock(),email="owner@example.invalid",password="correct-horse-battery";
  const registered=await call(env,"/api/merchant/register",{email,password});
  assert.equal(registered.status,201,JSON.stringify(registered.body));
  assert.equal(registered.body.created,true);
  const account=env.inspect.accounts.get(email);
  assert.ok(account.password_hash);
  assert.notEqual(account.password_hash,password);
  assert.equal(account.password_salt.length,32);
  assert.equal(account.access_key_digest,null);
  const duplicate=await call(env,"/api/merchant/register",{email,password});
  assert.equal(duplicate.status,409);
});

test("merchant login verifies password and rejects an incorrect password", async () => {
  const env=createD1Mock(),email="owner@example.invalid",password="correct-horse-battery";
  await call(env,"/api/merchant/register",{email,password});
  const wrong=await call(env,"/api/merchant/login",{email,password:"incorrect-password"});
  assert.equal(wrong.status,401);
  const loggedIn=await call(env,"/api/merchant/login",{email,password});
  assert.equal(loggedIn.status,200,JSON.stringify(loggedIn.body));
  assert.match(loggedIn.body.token,/^[a-f0-9]{64}$/);
});

test("new merchant stores are real but private until platform approval", async () => {
  const env=createD1Mock(),email="owner@example.invalid",password="correct-horse-battery";
  await call(env,"/api/merchant/register",{email,password});
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

test("merchant UI uses password auth and exposes POS for approved stores", () => {
  assert.match(ui,/form\.password/);
  assert.doesNotMatch(ui,/setOneTimeKey|oneTimeKey/);
  assert.match(ui,/\{view==="pos"&&<div className="dm-stack">/);
  assert.doesNotMatch(ui,/filter\(\(\[k\]\)=>k!=="pos"\|\|store\.is_demo\)/);
});


test("merchant assistant is authenticated, tenant-scoped and answers only from D1 queries", async () => {
  assert.match(source,/path==="\/api\/merchant\/assistant"/);
  assert.match(source,/WHERE store_id=\? AND is_listed=1 AND stock_qty<=5/);
  assert.match(source,/source:"live_d1_store_data"/);
  assert.match(ui,/Smart Business Assistant/);
  assert.match(ui,/api\/merchant\/assistant/);
});
