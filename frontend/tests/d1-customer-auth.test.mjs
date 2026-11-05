import test from "node:test";
import assert from "node:assert/strict";
import { webcrypto } from "node:crypto";
import { readFileSync } from "node:fs";
import { customerRouter } from "../../cloudflare/customer-routes.js";

if (!globalThis.crypto) globalThis.crypto = webcrypto;
const source = readFileSync(new URL("../../cloudflare/customer-routes.js", import.meta.url), "utf8");

const output = (_request, body, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
const error = (_request, status, detail) => output(null, { detail }, status);

function createD1Mock() {
  const accounts = new Map();
  const sessions = new Map();
  const failedAttempts = new Map();
  return { DB: {
    prepare(sql) {
      let args = [];
      const statement = {
        bind(...values) { args = values; return this; },
        async first() {
          if (sql.startsWith("SELECT COUNT(*) AS n FROM commerce_customer_accounts")) return { n: accounts.size };
          if (sql.startsWith("SELECT * FROM commerce_customer_accounts WHERE id=?")) return accounts.get(args[0]) || null;
          if (sql.startsWith("SELECT failures,lock_until")) return failedAttempts.get(args[0]) || null;
          if (sql.startsWith("SELECT * FROM commerce_customer_accounts WHERE lower(email)")) {
            return [...accounts.values()].find(a => a.email === args[0] || a.phone === args[1]) || null;
          }
          if (sql.startsWith("SELECT a.*, s.expires_at AS session_expires_at")) {
            const session = sessions.get(args[0]);
            return session?.expires_at > args[1] ? accounts.get(session.account_id) : null;
          }
          throw Error("Unexpected D1 first: " + sql);
        },
        async run() {
          if (sql.startsWith("INSERT INTO commerce_customer_accounts")) {
            const [id, display_name, email, phone, password_salt, password_hash] = args;
            if ([...accounts.values()].some(a => (email && a.email === email) || (phone && a.phone === phone)))
              throw Error("UNIQUE constraint failed");
            accounts.set(id, {id,display_name,email,phone,password_salt,password_hash,created_at:"2026-11-05"});
          } else if (sql.startsWith("INSERT INTO commerce_customer_sessions")) {
            const [token_hash, account_id, expires_at] = args;
            sessions.set(token_hash, {account_id,expires_at});
          } else if (sql.startsWith("DELETE FROM commerce_customer_login_attempts")) {
            failedAttempts.delete(args[0]);
          } else if (sql.startsWith("INSERT INTO commerce_customer_login_attempts")) {
            failedAttempts.set(args[0], {failures:args[1],lock_until:args[2]});
          } else {
            throw Error("Unexpected D1 run: " + sql);
          }
          return {meta:{changes:1}};
        }
      };
      return statement;
    }
  }};
}
async function call(env, path, body, token) {
  const request = new Request("https://example.invalid"+path, {
    method: body === undefined ? "GET" : "POST",
    headers: token ? {Authorization:"Bearer "+token} : {},
    ...(body === undefined ? {} : {body:JSON.stringify(body)}),
  });
  const response = await customerRouter(request, env, path, output, error);
  return {status:response.status, body:await response.json()};
}

test("D1 password derivation stays within the Cloudflare Worker 100000-iteration limit", () => {
  const match = source.match(/iterations:\s*(\d+),\s*hash:\s*"SHA-256"/);
  assert.ok(match, "Expected PBKDF2 iteration definition");
  assert.equal(Number(match[1]), 100000);
});

test("D1 registration, login and authenticated profile read work against the same database", async () => {
  const env = createD1Mock();
  const email = "customer@example.invalid";
  const registered = await call(env,"/api/customer/register",{
    display_name:"Customer", email, password:"correct-horse-2026"
  });
  assert.equal(registered.status,201, JSON.stringify(registered.body));
  assert.ok(registered.body.token);
  assert.equal(registered.body.customer.email,email);
  const duplicate = await call(env,"/api/customer/register",{
    display_name:"Customer", email, password:"correct-horse-2026"
  });
  assert.equal(duplicate.status,409);
  const wrong = await call(env,"/api/customer/login",{
    email_or_phone:email,password:"wrong-password"
  });
  assert.equal(wrong.status,401);
  const loggedIn = await call(env,"/api/customer/login",{
    email_or_phone:email,password:"correct-horse-2026"
  });
  assert.equal(loggedIn.status,200, JSON.stringify(loggedIn.body));
  assert.equal(loggedIn.body.customer.id,registered.body.customer.id);
  const profile = await call(env,"/api/customer/me",undefined,loggedIn.body.token);
  assert.equal(profile.status,200);
  assert.equal(profile.body.customer.email,email);
});

test("customer authentication does not overwrite the legacy tenant session", () => {
  const portal = readFileSync(new URL("../src/pages/StoreCustomerPortal.jsx",import.meta.url),"utf8");
  assert.doesNotMatch(portal,/saveToken\(data\.token\);/);
  assert.match(portal,/onLogin\(data\.token, data\.customer\);/);
});
