import test from "node:test";
import assert from "node:assert/strict";
import { webcrypto } from "node:crypto";
import { readFileSync } from "node:fs";
import { customerRouter } from "../../cloudflare/customer-routes.js";

if (!globalThis.crypto) globalThis.crypto = webcrypto;
const source = readFileSync(new URL("../../cloudflare/customer-routes.js", import.meta.url), "utf8");
const portal = readFileSync(new URL("../src/pages/StoreCustomerPortal.jsx", import.meta.url), "utf8");
const storePage = readFileSync(new URL("../src/pages/Store.jsx", import.meta.url), "utf8");
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
  const failedAttempts = new Map();
  const resetLimits = new Map();
  const stores = new Map([["shop-real", {
    id: "store-real", slug: "shop-real", name: "Real Shop", is_active: 1, is_demo: 0,
  }]]);
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
            if (sql.startsWith("SELECT COUNT(*) AS n FROM commerce_customer_accounts")) return { n: accounts.size };
            if (sql.startsWith("SELECT * FROM commerce_customer_accounts WHERE id=?")) return accounts.get(args[0]) || null;
            if (sql.startsWith("SELECT failures,lock_until")) return failedAttempts.get(args[0]) || null;
            if (sql.startsWith("SELECT * FROM commerce_stores WHERE slug=?")) return stores.get(args[0]) || null;
            if (sql.startsWith("SELECT id,email FROM commerce_customer_accounts WHERE lower(email)=?")) {
              const row = [...accounts.values()].find(a => String(a.email || "").toLowerCase() === args[0]);
              return row ? { id: row.id, email: row.email } : null;
            }
            if (sql.startsWith("SELECT id FROM commerce_customer_accounts WHERE password_reset_token_hash=?")) {
              const row = [...accounts.values()].find(a => a.password_reset_token_hash === args[0] && a.password_reset_expires_at > args[1]);
              return row ? { id: row.id } : null;
            }
            if (sql.startsWith("SELECT request_count FROM commerce_customer_auth_limits WHERE identifier_hash=?")) {
              return resetLimits.get(args[0]) || null;
            }
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
              accounts.set(id, {
                id, display_name, email, phone, password_salt, password_hash,
                password_reset_token_hash: null, password_reset_expires_at: null, created_at: "2026-11-05",
              });
            } else if (sql.startsWith("INSERT INTO commerce_customer_sessions")) {
              const [token_hash, account_id, expires_at] = args;
              sessions.set(token_hash, { account_id, expires_at });
            } else if (sql.startsWith("DELETE FROM commerce_customer_login_attempts")) {
              failedAttempts.delete(args[0]);
            } else if (sql.startsWith("INSERT INTO commerce_customer_login_attempts")) {
              failedAttempts.set(args[0], { failures: args[1], lock_until: args[2] });
            } else if (sql.startsWith("INSERT INTO commerce_customer_auth_limits")) {
              const [hash, windowId] = args, previous = resetLimits.get(hash);
              resetLimits.set(hash, {
                request_count: previous?.window_id === windowId ? previous.request_count + 1 : 1,
                window_id: windowId,
              });
            } else if (sql.startsWith("UPDATE commerce_customer_accounts SET password_reset_token_hash=?")) {
              const [hash, expiry, id] = args, row = accounts.get(id);
              if (row) Object.assign(row, { password_reset_token_hash: hash, password_reset_expires_at: expiry });
            } else if (sql.startsWith("UPDATE commerce_customer_accounts SET password_reset_token_hash=NULL")) {
              const [id, hash] = args, row = accounts.get(id);
              if (row && row.password_reset_token_hash === hash)
                Object.assign(row, { password_reset_token_hash: null, password_reset_expires_at: null });
            } else if (sql.startsWith("UPDATE commerce_customer_accounts SET password_salt=")) {
              const [salt, hash, id, tokenHash, now] = args, row = accounts.get(id);
              if (!row || row.password_reset_token_hash !== tokenHash || row.password_reset_expires_at <= now)
                return { meta: { changes: 0 } };
              Object.assign(row, {
                password_salt: salt, password_hash: hash,
                password_reset_token_hash: null, password_reset_expires_at: null,
              });
              return { meta: { changes: 1 } };
            } else if (sql.startsWith("DELETE FROM commerce_customer_sessions WHERE account_id=?")) {
              for (const [hash, session] of sessions) if (session.account_id === args[0]) sessions.delete(hash);
            } else {
              throw Error("Unexpected D1 run: " + sql);
            }
            return { meta: { changes: 1 } };
          }
        };
        return statement;
      }
    }
  };
  return Object.assign(env, { inspect: { accounts, sessions, failedAttempts, resetLimits, stores } });
}

async function call(env, path, body, token) {
  const request = new Request("https://example.invalid" + path, {
    method: body === undefined ? "GET" : "POST",
    headers: { "content-type": "application/json", ...(token ? { Authorization: "Bearer " + token } : {}) },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  const response = await customerRouter(request, env, path, output, error);
  return { status: response.status, body: await response.json() };
}

test("D1 password derivation stays within the Cloudflare Worker 100000-iteration limit", () => {
  const match = source.match(/iterations:\s*(\d+),\s*hash:\s*"SHA-256"/);
  assert.ok(match, "Expected PBKDF2 iteration definition");
  assert.equal(Number(match[1]), 100000);
});

test("D1 registration, login and authenticated profile read work against the same database", async () => {
  const env = createD1Mock();
  const email = "customer@example.invalid";
  const registered = await call(env, "/api/customer/register", {
    display_name: "Customer", email, password: "correct-horse-2026",
  });
  assert.equal(registered.status, 201, JSON.stringify(registered.body));
  assert.ok(registered.body.token);
  assert.equal(registered.body.customer.email, email);
  const duplicate = await call(env, "/api/customer/register", {
    display_name: "Customer", email, password: "correct-horse-2026",
  });
  assert.equal(duplicate.status, 409);
  const wrong = await call(env, "/api/customer/login", {
    email_or_phone: email, password: "wrong-password",
  });
  assert.equal(wrong.status, 401);
  const loggedIn = await call(env, "/api/customer/login", {
    email_or_phone: email, password: "correct-horse-2026",
  });
  assert.equal(loggedIn.status, 200, JSON.stringify(loggedIn.body));
  assert.equal(loggedIn.body.customer.id, registered.body.customer.id);
  const profile = await call(env, "/api/customer/me", undefined, loggedIn.body.token);
  assert.equal(profile.status, 200);
  assert.equal(profile.body.customer.email, email);
});

test("customer password recovery sends a one-time token, resets the password and revokes sessions", async () => {
  const env = createD1Mock(), email = "customer@example.invalid";
  sentEmails = [];
  const registered = await call(env, "/api/customer/register", {
    display_name: "Customer", email, password: "correct-horse-2026",
  });
  assert.equal(registered.status, 201);
  const forgot = await call(env, "/api/customer/forgot-password", { email, store_slug: "shop-real" });
  assert.equal(forgot.status, 202, JSON.stringify(forgot.body));
  assert.equal(sentEmails.length, 1);
  const match = sentEmails[0].text.match(/customer_reset=([a-f0-9]{64})/);
  assert.ok(match, "Expected a single-use customer reset link");
  const token = match[1];
  const account = env.inspect.accounts.get(registered.body.customer.id);
  assert.notEqual(account.password_reset_token_hash, token);
  assert.match(sentEmails[0].text, /expires in 60 minutes/);

  const reset = await call(env, "/api/customer/reset-password", { token, password: "a-new-secure-password" });
  assert.equal(reset.status, 200, JSON.stringify(reset.body));
  assert.equal(reset.body.sessions_revoked, true);
  assert.equal(account.password_reset_token_hash, null);
  const oldSession = await call(env, "/api/customer/me", undefined, registered.body.token);
  assert.equal(oldSession.status, 401);
  const oldPassword = await call(env, "/api/customer/login", { email_or_phone: email, password: "correct-horse-2026" });
  assert.equal(oldPassword.status, 401);
  const newPassword = await call(env, "/api/customer/login", { email_or_phone: email, password: "a-new-secure-password" });
  assert.equal(newPassword.status, 200);
  const reused = await call(env, "/api/customer/reset-password", { token, password: "another-secure-password" });
  assert.equal(reused.status, 400);
});

test("customer reset requests do not disclose whether an email account exists", async () => {
  const env = createD1Mock();
  sentEmails = [];
  const result = await call(env, "/api/customer/forgot-password", {
    email: "missing@example.invalid", store_slug: "shop-real",
  });
  assert.equal(result.status, 202);
  assert.equal(sentEmails.length, 0);
  assert.match(result.body.message, /অ্যাকাউন্ট থাকলে/);
});

test("customer password reset fails closed when email delivery is not configured", async () => {
  const env = createD1Mock();
  delete env.RESEND_API_KEY;
  const result = await call(env, "/api/customer/forgot-password", {
    email: "customer@example.invalid", store_slug: "shop-real",
  });
  assert.equal(result.status, 503);
});

test("customer password reset is rate limited per IP and email", async () => {
  const env = createD1Mock();
  for (let i = 0; i < 5; i++) {
    const result = await call(env, "/api/customer/forgot-password", {
      email: "missing@example.invalid", store_slug: "shop-real",
    });
    assert.equal(result.status, 202);
  }
  const limited = await call(env, "/api/customer/forgot-password", {
    email: "missing@example.invalid", store_slug: "shop-real",
  });
  assert.equal(limited.status, 429);
});

test("customer authentication does not overwrite the legacy tenant session", () => {
  assert.doesNotMatch(portal, /saveToken\(data\.token\);/);
  assert.match(portal, /onLogin\(data\.token, data\.customer\);/);
  assert.match(portal, /\/forgot-password/);
  assert.match(portal, /\/reset-password/);
  assert.match(portal, /customer_reset/);
  assert.match(portal, /resetToken={resetToken}/);
  assert.match(portal, /ChatView|chat/);
  assert.match(storePage, /customer_reset/);
});
