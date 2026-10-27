import { defaultOrderStatusNote } from "./order-workflow.js";

/* Global customer identity and account-owned shopping state for the D1 storefronts.
 * D1 demo accounts are shared across D1 stores, but remain separate from the
 * operational FastAPI customer database until a deliberate identity migration.
 */
const encoder = new TextEncoder();
const hex = bytes => Array.from(new Uint8Array(bytes), b => b.toString(16).padStart(2, "0")).join("");
const newSecret = (length = 32) => { const bytes = new Uint8Array(length); crypto.getRandomValues(bytes); return hex(bytes); };
const short = (v, n = 120) => String(v ?? "").trim().slice(0, n);
const validEmail = value => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value) && value.length <= 180;
const validPhone = value => /^[+()\d\-\s]{7,20}$/.test(value);
const validInteger = (v, min, max) => Number.isInteger(Number(v)) && Number(v) >= min && Number(v) <= max;

async function sha256(value) {
  return hex(await crypto.subtle.digest("SHA-256", encoder.encode(value)));
}
async function passwordDigest(password, salt) {
  const key = await crypto.subtle.importKey("raw", encoder.encode(password), "PBKDF2", false, ["deriveBits"]);
  const bits = await crypto.subtle.deriveBits({
    name: "PBKDF2", salt: encoder.encode(salt), iterations: 120000, hash: "SHA-256",
  }, key, 256);
  return hex(bits);
}
function constantTimeEqual(a, b) {
  a = String(a || ""); b = String(b || "");
  if (a.length !== b.length) return false;
  let mismatch = 0;
  for (let i = 0; i < a.length; i++) mismatch |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return mismatch === 0;
}
async function readJson(request, max = 10000) {
  const text = await request.text();
  if (text.length > max) throw new Error("Payload too large");
  try { return JSON.parse(text); } catch { throw new Error("Invalid JSON"); }
}
function customerView(a) {
  return {
    id: a.id, display_name: a.display_name, email: a.email || null, phone: a.phone || null,
    avatar_data_url: a.avatar_data_url || null, division: a.division || "",
    district: a.district || "", thana: a.thana || "", address_detail: a.address_detail || "",
    created_at: a.created_at,
  };
}
async function createSession(env, accountId) {
  const token = newSecret(32);
  const expires = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString();
  await env.DB.prepare("INSERT INTO commerce_customer_sessions(token_hash,account_id,expires_at) VALUES(?,?,?)")
    .bind(await sha256(token), accountId, expires).run();
  return { token, expires_at: expires };
}
export async function customerFromToken(env, rawToken) {
  const token = String(rawToken || "").trim();
  if (!/^[a-f0-9]{64}$/i.test(token)) return null;
  return env.DB.prepare(
    "SELECT a.*, s.expires_at AS session_expires_at FROM commerce_customer_sessions s " +
    "JOIN commerce_customer_accounts a ON a.id=s.account_id WHERE s.token_hash=? AND s.expires_at>? LIMIT 1"
  ).bind(await sha256(token.toLowerCase()), new Date().toISOString()).first();
}
async function customerViewer(request, env) {
  const match = /^Bearer ([a-f0-9]{64})$/i.exec(request.headers.get("Authorization") || "");
  if (!match) return null;
  return customerFromToken(env, match[1]);
}
async function storeBySlug(env, slug) {
  return env.DB.prepare("SELECT * FROM commerce_stores WHERE slug=? AND is_active=1 LIMIT 1").bind(short(slug, 100)).first();
}
async function listedProduct(env, storeId, productId) {
  return env.DB.prepare("SELECT * FROM commerce_products WHERE id=? AND store_id=? AND is_listed=1 LIMIT 1")
    .bind(short(productId, 80), storeId).first();
}
function addressView(row) {
  return {
    id: row.id, label: row.label, recipient_name: row.recipient_name, phone: row.phone,
    division: row.division, district: row.district, thana: row.thana || "",
    address_detail: row.address_detail, postal_code: row.postal_code || "",
    is_default: !!row.is_default, created_at: row.created_at,
  };
}
async function addressesFor(env, accountId) {
  const { results } = await env.DB.prepare(
    "SELECT * FROM commerce_customer_addresses WHERE account_id=? ORDER BY is_default DESC,created_at DESC"
  ).bind(accountId).all();
  return results.map(addressView);
}
function validateAddress(body) {
  const value = {
    label: short(body.label || "বাড়ি", 40),
    recipient_name: short(body.recipient_name, 100),
    phone: short(body.phone, 20).replace(/\s+/g, " "),
    division: short(body.division, 50), district: short(body.district, 50),
    thana: short(body.thana, 80), address_detail: short(body.address_detail, 400),
    postal_code: short(body.postal_code, 12), is_default: body.is_default === true,
  };
  if (value.label.length < 1 || value.recipient_name.length < 2 || !validPhone(value.phone) ||
      value.division.length < 2 || value.district.length < 2 || value.address_detail.length < 3) {
    throw new Error("প্রাপকের নাম, সঠিক ফোন, বিভাগ, জেলা ও বিস্তারিত ঠিকানা দিতে হবে");
  }
  return value;
}
async function setDefaultAddress(env, accountId, keepId) {
  await env.DB.prepare("UPDATE commerce_customer_addresses SET is_default=CASE WHEN id=? THEN 1 ELSE 0 END,updated_at=CURRENT_TIMESTAMP WHERE account_id=?")
    .bind(keepId, accountId).run();
}
async function orderHistory(env, account, url) {
  const page = Math.min(100000, Math.max(1, Number(url.searchParams.get("page") || 1)));
  const perPage = 10;
  const status = short(url.searchParams.get("status"), 20);
  const allowed = new Set(["placed", "confirmed", "processing", "ready", "dispatched", "shipped", "fulfilled", "delivered", "cancelled"]);
  if (status && !allowed.has(status)) return { error: "অর্ডারের অবস্থা সঠিক নয়", status: 422 };
  const count = status
    ? await env.DB.prepare("SELECT COUNT(*) AS total FROM commerce_orders WHERE account_id=? AND status=?").bind(account.id, status).first()
    : await env.DB.prepare("SELECT COUNT(*) AS total FROM commerce_orders WHERE account_id=?").bind(account.id).first();
  const query = status
    ? env.DB.prepare("SELECT o.*,s.slug AS store_slug,s.name AS store_name,s.is_demo AS store_is_demo FROM commerce_orders o JOIN commerce_stores s ON s.id=o.store_id WHERE o.account_id=? AND o.status=? ORDER BY o.placed_at DESC LIMIT ? OFFSET ?").bind(account.id, status, perPage, (page-1)*perPage)
    : env.DB.prepare("SELECT o.*,s.slug AS store_slug,s.name AS store_name,s.is_demo AS store_is_demo FROM commerce_orders o JOIN commerce_stores s ON s.id=o.store_id WHERE o.account_id=? ORDER BY o.placed_at DESC LIMIT ? OFFSET ?").bind(account.id, perPage, (page-1)*perPage);
  const { results: orders } = await query.all();
  if (!orders.length) return { total: Number(count?.total || 0), page, per_page: perPage, orders: [] };
  const ids = orders.map(o => o.id);
  const placeholders = ids.map(() => "?").join(",");
  const { results: lines } = await env.DB.prepare(
    `SELECT * FROM commerce_order_lines WHERE order_id IN (${placeholders}) ORDER BY rowid`
  ).bind(...ids).all();
  const [{ results: returns }] = await Promise.all([
    env.DB.prepare(`SELECT * FROM commerce_order_returns WHERE order_id IN (${placeholders})`).bind(...ids).all(),
  ]);
  const byReturn = new Map(returns.map(r => [r.order_id, r]));
  const byOrder = new Map();
  for (const line of lines) {
    if (!byOrder.has(line.order_id)) byOrder.set(line.order_id, []);
    byOrder.get(line.order_id).push({
      product_id: line.product_id, description: line.product_name, product_name: line.product_name,
      quantity: line.quantity, unit_price: line.price_bdt, line_total: line.line_total_bdt,
      variant_label: line.variant_label || null,
    });
  }
  return {
    total: Number(count?.total || 0), page, per_page: perPage,
    orders: orders.map(o => {
      const ret = byReturn.get(o.id);
      return {
        id: o.id, document_number: o.order_number, order_number: o.order_number,
        access_token: o.access_token, status: o.status, status_note: o.status_note || defaultOrderStatusNote(o.status, !!o.store_is_demo),
        issued_at: o.placed_at, placed_at: o.placed_at,
        subtotal: o.subtotal_bdt, total: o.total_bdt, tax_amount: 0, delivery_fee: 0,
        discount_amount: 0, organization_id: o.store_id, store_slug: o.store_slug,
        store_name: o.store_name, is_demo: !!o.store_is_demo, payment_method: o.payment_method || "demo",
        payment_status: "demo_no_payment", shipping_name: o.shipping_name || "",
        shipping_phone: o.shipping_phone || "", shipping_address: o.shipping_address || "",
        return_id: ret?.id || null, return_status: ret?.status || null,
        return_reason: ret?.reason || null, return_note: ret?.merchant_note || null,
        items: byOrder.get(o.id) || [],
      };
    }),
  };
}
async function customerReviewList(env, storeId, productId) {
  const product = await env.DB.prepare("SELECT id FROM commerce_products WHERE id=? AND store_id=? AND is_listed=1")
    .bind(productId, storeId).first();
  if (!product) return null;
  const [reviews, summary] = await Promise.all([
    env.DB.prepare("SELECT r.id,r.rating,r.comment,r.created_at,a.display_name AS reviewer_name FROM commerce_product_reviews r JOIN commerce_customer_accounts a ON a.id=r.account_id WHERE r.store_id=? AND r.product_id=? ORDER BY r.created_at DESC LIMIT 50").bind(storeId, productId).all(),
    env.DB.prepare("SELECT COUNT(*) AS count,COALESCE(AVG(rating),0) AS average FROM commerce_product_reviews WHERE store_id=? AND product_id=?").bind(storeId, productId).first(),
  ]);
  return { reviews: reviews.results, count: Number(summary?.count || 0), average: Number(summary?.average || 0), average_rating: Number(summary?.average || 0) };
}

export async function customerRouter(request, env, path, output, error) {
  const method = request.method;
  if (path.startsWith("/api/public/reviews/") && method === "GET") {
    const m = path.match(/^\/api\/public\/reviews\/([^/]+)\/([^/]+)$/);
    if (!m) return error(request, 404, "Review route not found");
    const storeId = decodeURIComponent(m[1]), productId = decodeURIComponent(m[2]);
    const result = await customerReviewList(env, storeId, productId);
    return result ? output(request, result) : error(request, 404, "Product not found");
  }
  if (!path.startsWith("/api/customer/")) return null;
  try {
    if (method === "POST" && path === "/api/customer/register") {
      const body = await readJson(request);
      const displayName = short(body.display_name, 100);
      const email = short(body.email, 180).toLowerCase() || null;
      const phone = short(body.phone, 20).replace(/\s+/g, " ") || null;
      const password = String(body.password || "");
      if (displayName.length < 2 || (!email && !phone) || (email && !validEmail(email)) ||
          (phone && !validPhone(phone)) || password.length < 8 || password.length > 128) {
        return error(request, 422, "নাম, সঠিক ইমেইল বা ফোন এবং কমপক্ষে ৮ অক্ষরের পাসওয়ার্ড দিন");
      }
      const daily = await env.DB.prepare("SELECT COUNT(*) AS n FROM commerce_customer_accounts WHERE created_at >= datetime('now','start of day')").first();
      if (Number(daily?.n || 0) >= 50) return error(request, 429, "আজকের নতুন অ্যাকাউন্ট তৈরির সীমা শেষ হয়েছে");
      const salt = newSecret(16), hash = await passwordDigest(password, salt), id = crypto.randomUUID();
      try {
        await env.DB.prepare("INSERT INTO commerce_customer_accounts(id,display_name,email,phone,password_salt,password_hash) VALUES(?,?,?,?,?,?)")
          .bind(id, displayName, email, phone, salt, hash).run();
      } catch (e) {
        if (/UNIQUE constraint failed/.test(e?.message || "")) return error(request, 409, "এই ইমেইল বা ফোন দিয়ে আগেই অ্যাকাউন্ট আছে");
        throw e;
      }
      const session = await createSession(env, id);
      const account = await env.DB.prepare("SELECT * FROM commerce_customer_accounts WHERE id=?").bind(id).first();
      return output(request, { ...session, customer: customerView(account) }, 201);
    }
    if (method === "POST" && path === "/api/customer/login") {
      const body = await readJson(request);
      const identifier = short(body.email_or_phone, 180);
      const key = identifier.includes("@") ? identifier.toLowerCase() : identifier.replace(/\s+/g, " ");
      const password = String(body.password || "");
      if (!key || password.length > 128) return error(request, 401, "ইমেইল/ফোন বা পাসওয়ার্ড সঠিক নয়");
      const now = new Date().toISOString();
      const lock = await env.DB.prepare("SELECT failures,lock_until FROM commerce_customer_login_attempts WHERE identifier=?").bind(key).first();
      if (lock?.lock_until && lock.lock_until > now) return error(request, 429, "অনেকবার চেষ্টা করা হয়েছে। ১৫ মিনিট পরে আবার চেষ্টা করুন");
      const account = await env.DB.prepare("SELECT * FROM commerce_customer_accounts WHERE lower(email)=? OR phone=? LIMIT 1")
        .bind(key, key).first();
      const salt = account?.password_salt || "bsmart-customer-invalid-account-salt";
      const actual = await passwordDigest(password, salt);
      const valid = !!account && constantTimeEqual(actual, account.password_hash);
      if (!valid) {
        const failures = Number(lock?.failures || 0) + 1;
        const lockUntil = failures >= 6 ? new Date(Date.now() + 15*60*1000).toISOString() : null;
        await env.DB.prepare("INSERT INTO commerce_customer_login_attempts(identifier,failures,lock_until,updated_at) VALUES(?,?,?,CURRENT_TIMESTAMP) ON CONFLICT(identifier) DO UPDATE SET failures=excluded.failures,lock_until=excluded.lock_until,updated_at=CURRENT_TIMESTAMP")
          .bind(key, failures, lockUntil).run();
        return error(request, 401, "ইমেইল/ফোন বা পাসওয়ার্ড সঠিক নয়");
      }
      await env.DB.prepare("DELETE FROM commerce_customer_login_attempts WHERE identifier=?").bind(key).run();
      const session = await createSession(env, account.id);
      return output(request, { ...session, customer: customerView(account) });
    }
    if (method === "GET" && path === "/api/customer/me") {
      const account = await customerViewer(request, env);
      return account ? output(request, { customer: customerView(account) }) : error(request, 401, "অ্যাকাউন্টে আবার লগইন করুন");
    }
    if (method === "PATCH" && path === "/api/customer/profile") {
      const account = await customerViewer(request, env);
      if (!account) return error(request, 401, "অ্যাকাউন্টে আবার লগইন করুন");
      const body = await readJson(request, 700000);
      const displayName = body.display_name === undefined ? account.display_name : short(body.display_name, 100);
      const phone = body.phone === undefined ? account.phone : (short(body.phone, 20).replace(/\s+/g, " ") || null);
      const avatar = body.avatar_data_url === undefined ? account.avatar_data_url : (body.avatar_data_url || null);
      const division = body.division === undefined ? account.division : short(body.division, 50);
      const district = body.district === undefined ? account.district : short(body.district, 50);
      const thana = body.thana === undefined ? account.thana : short(body.thana, 80);
      const address = body.address_detail === undefined ? account.address_detail : short(body.address_detail, 400);
      if (displayName.length < 2) return error(request, 422, "নাম কমপক্ষে ২ অক্ষরের হতে হবে");
      if (phone && !validPhone(phone)) return error(request, 422, "সঠিক ফোন নম্বর দিন");
      if (!account.email && !phone) return error(request, 422, "অ্যাকাউন্টে ইমেইল বা ফোন নম্বর থাকতে হবে");
      if (avatar && (avatar.length > 500000 || !avatar.startsWith("data:image/"))) return error(request, 422, "ছবির আকার ৩৫০ KB-এর মধ্যে এবং ফরম্যাট image হতে হবে");
      if (phone && phone !== account.phone) {
        const exists = await env.DB.prepare("SELECT id FROM commerce_customer_accounts WHERE phone=? AND id<>? LIMIT 1").bind(phone, account.id).first();
        if (exists) return error(request, 409, "এই ফোন নম্বর দিয়ে অন্য অ্যাকাউন্ট আছে");
      }
      await env.DB.prepare("UPDATE commerce_customer_accounts SET display_name=?,phone=?,avatar_data_url=?,division=?,district=?,thana=?,address_detail=?,updated_at=CURRENT_TIMESTAMP WHERE id=?")
        .bind(displayName, phone, avatar, division, district, thana, address, account.id).run();
      const updated = await env.DB.prepare("SELECT * FROM commerce_customer_accounts WHERE id=?").bind(account.id).first();
      return output(request, { customer: customerView(updated) });
    }
    if (method === "POST" && path === "/api/customer/password") {
      const account = await customerViewer(request, env);
      if (!account) return error(request, 401, "অ্যাকাউন্টে আবার লগইন করুন");
      const body = await readJson(request);
      const current = String(body.current_password || ""), next = String(body.new_password || "");
      if (next.length < 8 || next.length > 128) return error(request, 422, "নতুন পাসওয়ার্ড কমপক্ষে ৮ অক্ষরের হতে হবে");
      const currentHash = await passwordDigest(current, account.password_salt);
      if (!constantTimeEqual(currentHash, account.password_hash)) return error(request, 400, "বর্তমান পাসওয়ার্ড সঠিক নয়");
      if (constantTimeEqual(await passwordDigest(next, account.password_salt), account.password_hash)) return error(request, 422, "নতুন পাসওয়ার্ড আগেরটির থেকে আলাদা হতে হবে");
      const salt = newSecret(16), hash = await passwordDigest(next, salt);
      await env.DB.prepare("UPDATE commerce_customer_accounts SET password_salt=?,password_hash=?,updated_at=CURRENT_TIMESTAMP WHERE id=?").bind(salt, hash, account.id).run();
      await env.DB.prepare("DELETE FROM commerce_customer_sessions WHERE account_id=?").bind(account.id).run();
      const session = await createSession(env, account.id);
      const updated = await env.DB.prepare("SELECT * FROM commerce_customer_accounts WHERE id=?").bind(account.id).first();
      return output(request, { ...session, customer: customerView(updated) });
    }
    if (method === "POST" && path === "/api/customer/logout") {
      const token = /^Bearer ([a-f0-9]{64})$/i.exec(request.headers.get("Authorization") || "")?.[1];
      if (!token) return error(request, 401, "অ্যাকাউন্টে আবার লগইন করুন");
      await env.DB.prepare("DELETE FROM commerce_customer_sessions WHERE token_hash=?").bind(await sha256(token.toLowerCase())).run();
      return output(request, { logged_out: true });
    }

    const account = await customerViewer(request, env);
    if (!account) return error(request, 401, "অ্যাকাউন্টে আবার লগইন করুন");

    if (path === "/api/customer/addresses" && method === "GET") {
      return output(request, { addresses: await addressesFor(env, account.id) });
    }
    if (path === "/api/customer/addresses" && method === "POST") {
      const body = await readJson(request);
      let value;
      try { value = validateAddress(body); } catch (e) { return error(request, 422, e.message); }
      const first = await env.DB.prepare("SELECT id FROM commerce_customer_addresses WHERE account_id=? LIMIT 1").bind(account.id).first();
      const id = crypto.randomUUID(), isDefault = value.is_default || !first;
      if (isDefault) await env.DB.prepare("UPDATE commerce_customer_addresses SET is_default=0,updated_at=CURRENT_TIMESTAMP WHERE account_id=?").bind(account.id).run();
      await env.DB.prepare("INSERT INTO commerce_customer_addresses(id,account_id,label,recipient_name,phone,division,district,thana,address_detail,postal_code,is_default) VALUES(?,?,?,?,?,?,?,?,?,?,?)")
        .bind(id, account.id, value.label, value.recipient_name, value.phone, value.division, value.district, value.thana || null, value.address_detail, value.postal_code || null, isDefault ? 1 : 0).run();
      const row = await env.DB.prepare("SELECT * FROM commerce_customer_addresses WHERE id=?").bind(id).first();
      return output(request, addressView(row), 201);
    }
    const addressMatch = path.match(/^\/api\/customer\/addresses\/([^/]+)$/);
    if (addressMatch && method === "PATCH") {
      const id = decodeURIComponent(addressMatch[1]);
      const row = await env.DB.prepare("SELECT * FROM commerce_customer_addresses WHERE id=? AND account_id=?").bind(id, account.id).first();
      if (!row) return error(request, 404, "ঠিকানাটি পাওয়া যায়নি");
      const body = await readJson(request);
      const merged = {
        label: body.label === undefined ? row.label : body.label,
        recipient_name: body.recipient_name === undefined ? row.recipient_name : body.recipient_name,
        phone: body.phone === undefined ? row.phone : body.phone,
        division: body.division === undefined ? row.division : body.division,
        district: body.district === undefined ? row.district : body.district,
        thana: body.thana === undefined ? row.thana : body.thana,
        address_detail: body.address_detail === undefined ? row.address_detail : body.address_detail,
        postal_code: body.postal_code === undefined ? row.postal_code : body.postal_code,
        is_default: body.is_default === undefined ? !!row.is_default : body.is_default === true,
      };
      let value;
      try { value = validateAddress(merged); } catch (e) { return error(request, 422, e.message); }
      if (body.is_default === true) await env.DB.prepare("UPDATE commerce_customer_addresses SET is_default=0,updated_at=CURRENT_TIMESTAMP WHERE account_id=?").bind(account.id).run();
      await env.DB.prepare("UPDATE commerce_customer_addresses SET label=?,recipient_name=?,phone=?,division=?,district=?,thana=?,address_detail=?,postal_code=?,is_default=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND account_id=?")
        .bind(value.label,value.recipient_name,value.phone,value.division,value.district,value.thana||null,value.address_detail,value.postal_code||null,value.is_default?1:0,id,account.id).run();
      if (body.is_default === false && row.is_default) {
        const next = await env.DB.prepare("SELECT id FROM commerce_customer_addresses WHERE account_id=? AND id<>? ORDER BY created_at DESC LIMIT 1").bind(account.id,id).first();
        if (next) await setDefaultAddress(env,account.id,next.id);
      }
      const updated = await env.DB.prepare("SELECT * FROM commerce_customer_addresses WHERE id=?").bind(id).first();
      return output(request,addressView(updated));
    }
    if (addressMatch && method === "DELETE") {
      const id = decodeURIComponent(addressMatch[1]);
      const row = await env.DB.prepare("SELECT id,is_default FROM commerce_customer_addresses WHERE id=? AND account_id=?").bind(id,account.id).first();
      if (!row) return error(request,404,"ঠিকানাটি পাওয়া যায়নি");
      await env.DB.prepare("DELETE FROM commerce_customer_addresses WHERE id=? AND account_id=?").bind(id,account.id).run();
      if (row.is_default) {
        const next = await env.DB.prepare("SELECT id FROM commerce_customer_addresses WHERE account_id=? ORDER BY created_at DESC LIMIT 1").bind(account.id).first();
        if (next) await setDefaultAddress(env,account.id,next.id);
      }
      return output(request,{ok:true});
    }

    if (path === "/api/customer/wishlist" && method === "GET") {
      const url = new URL(request.url), slug = short(url.searchParams.get("store_slug"),100);
      const { results } = await env.DB.prepare(
        "SELECT w.id,s.slug AS store_slug,s.name AS store_name,p.id AS product_id,p.name AS product_name,p.sku,p.price_bdt AS price,p.image_url AS image_data_url,p.category,p.stock_qty,p.created_at " +
        "FROM commerce_customer_wishlist_items w JOIN commerce_stores s ON s.id=w.store_id JOIN commerce_products p ON p.id=w.product_id " +
        "WHERE w.account_id=? AND s.is_active=1 AND p.is_listed=1 AND (?='' OR s.slug=?) ORDER BY w.created_at DESC"
      ).bind(account.id,slug,slug).all();
      return output(request,{items:results.map(p=>({...p,price:Number(p.price),description:"",tags:[],in_stock:Number(p.stock_qty)>0})),total:results.length});
    }
    if (path === "/api/customer/wishlist" && method === "POST") {
      const body = await readJson(request), store = await storeBySlug(env,body.store_slug);
      if (!store) return error(request,404,"দোকানটি পাওয়া যায়নি");
      const product = await listedProduct(env,store.id,body.product_id);
      if (!product) return error(request,404,"পণ্যটি এই দোকানে উপলভ্য নয়");
      const id = crypto.randomUUID();
      await env.DB.prepare("INSERT INTO commerce_customer_wishlist_items(id,account_id,store_id,product_id) VALUES(?,?,?,?) ON CONFLICT(account_id,store_id,product_id) DO NOTHING")
        .bind(id,account.id,store.id,product.id).run();
      const row = await env.DB.prepare("SELECT id FROM commerce_customer_wishlist_items WHERE account_id=? AND store_id=? AND product_id=?").bind(account.id,store.id,product.id).first();
      return output(request,{ok:true,id:row.id},201);
    }
    const wishlistMatch = path.match(/^\/api\/customer\/wishlist\/([^/]+)\/([^/]+)$/);
    if (wishlistMatch && method === "DELETE") {
      const slug=decodeURIComponent(wishlistMatch[1]), productId=decodeURIComponent(wishlistMatch[2]);
      const store=await env.DB.prepare("SELECT id FROM commerce_stores WHERE slug=? LIMIT 1").bind(slug).first();
      if(store)await env.DB.prepare("DELETE FROM commerce_customer_wishlist_items WHERE account_id=? AND store_id=? AND product_id=?").bind(account.id,store.id,productId).run();
      return output(request,{ok:true});
    }

    const cartMatch = path.match(/^\/api\/customer\/cart\/([^/]+)$/);
    if (cartMatch) {
      const slug=decodeURIComponent(cartMatch[1]), store=await storeBySlug(env,slug);
      if(!store)return error(request,404,"দোকানটি পাওয়া যায়নি");
      if(method==="GET"){
        const {results}=await env.DB.prepare("SELECT c.product_id,c.quantity,c.variant_label,p.name AS product_name,p.price_bdt AS price,p.image_url AS image_data_url,p.stock_qty FROM commerce_customer_cart_items c JOIN commerce_products p ON p.id=c.product_id WHERE c.account_id=? AND c.store_id=? AND p.is_listed=1 ORDER BY c.created_at")
          .bind(account.id,store.id).all();
        return output(request,{store_slug:store.slug,items:results.map(p=>({...p,price:Number(p.price)}))});
      }
      if(method==="PUT"){
        const body=await readJson(request),items=body.items;
        if(!Array.isArray(items)||items.length>50)return error(request,422,"কার্টে সর্বোচ্চ ৫০ ধরনের পণ্য রাখা যাবে");
        const seen=new Set(),checked=[];
        for(const item of items){
          const productId=short(item.product_id,80),qty=Number(item.quantity);
          if(!productId||seen.has(productId)||!validInteger(qty,1,99))return error(request,422,"কার্টের পণ্য বা পরিমাণ সঠিক নয়");
          seen.add(productId);
          const p=await listedProduct(env,store.id,productId);
          if(!p||Number(p.stock_qty)<qty||qty>10)return error(request,409,"পণ্যের মজুত বদলেছে; কার্ট আপডেট করুন");
          checked.push({id:crypto.randomUUID(),product_id:productId,quantity:qty,variant_label:short(item.variant_label,100)});
        }
        const statements=[env.DB.prepare("DELETE FROM commerce_customer_cart_items WHERE account_id=? AND store_id=?").bind(account.id,store.id),
          ...checked.map(i=>env.DB.prepare("INSERT INTO commerce_customer_cart_items(id,account_id,store_id,product_id,quantity,variant_label) VALUES(?,?,?,?,?,?)").bind(i.id,account.id,store.id,i.product_id,i.quantity,i.variant_label||null))];
        await env.DB.batch(statements);
        return output(request,{ok:true,items_count:checked.length});
      }
      if(method==="DELETE"){
        await env.DB.prepare("DELETE FROM commerce_customer_cart_items WHERE account_id=? AND store_id=?").bind(account.id,store.id).run();
        return output(request,{ok:true});
      }
    }

    if (path === "/api/customer/orders" && method === "GET") {
      const result = await orderHistory(env,account,new URL(request.url));
      return result.error ? error(request,result.status,result.error) : output(request,result);
    }
    const customerCancelMatch = path.match(/^\/api\/customer\/orders\/([^/]+)\/cancel$/);
    if (customerCancelMatch && method === "POST") {
      const orderId = decodeURIComponent(customerCancelMatch[1]);
      const body = await readJson(request);
      const reason = short(body.reason, 250);
      const order = await env.DB.prepare("SELECT id,status FROM commerce_orders WHERE id=? AND account_id=?")
        .bind(orderId,account.id).first();
      if (!order) return error(request,404,"অর্ডারটি পাওয়া যায়নি");
      if (order.status !== "placed") return error(request,409,"শুধু নতুন অর্ডার বাতিল করা যাবে");
      const result = await env.DB.prepare("UPDATE commerce_orders SET status='cancelled',cancellation_reason=?,status_note='ক্রেতার অনুরোধে বাতিল' WHERE id=? AND account_id=? AND status='placed'")
        .bind(reason || null,orderId,account.id).run();
      if (!result.meta?.changes) return error(request,409,"অর্ডারটির অবস্থা বদলে গেছে; আবার লোড করুন");
      return output(request,{ok:true,status:"cancelled",inventory_restored:true});
    }
    const returnOrderMatch = path.match(/^\/api\/customer\/orders\/([^/]+)\/return$/);
    if (returnOrderMatch && method === "POST") {
      const orderId = decodeURIComponent(returnOrderMatch[1]), body = await readJson(request);
      const reason = short(body.reason,100), note = short(body.note,1000);
      if (!["damaged","wrong_item","missing_item","not_as_described","other"].includes(reason))
        return error(request,422,"ফেরতের একটি কারণ নির্বাচন করুন");
      const order = await env.DB.prepare("SELECT id,store_id,status,placed_at FROM commerce_orders WHERE id=? AND account_id=?")
        .bind(orderId,account.id).first();
      if (!order) return error(request,404,"অর্ডারটি পাওয়া যায়নি");
      if (!["fulfilled","delivered"].includes(order.status)) return error(request,409,"অর্ডার সম্পন্ন হলে ফেরতের অনুরোধ করা যাবে");
      const previous = await env.DB.prepare("SELECT id,status FROM commerce_order_returns WHERE order_id=?").bind(orderId).first();
      if (previous) return error(request,409,"এই অর্ডারের ফেরতের অনুরোধ আগেই জমা হয়েছে");
      const id = crypto.randomUUID();
      await env.DB.prepare("INSERT INTO commerce_order_returns(id,store_id,order_id,account_id,reason,customer_note) VALUES(?,?,?,?,?,?)")
        .bind(id,order.store_id,order.id,account.id,reason,note||null).run();
      return output(request,{created:true,id,status:"requested",note:"এটি পরীক্ষামূলক ফেরত অনুরোধ; কোনো অর্থ ফেরত দেওয়া হয়নি"},201);
    }
    if (path === "/api/customer/returns" && method === "GET") {
      const {results} = await env.DB.prepare(
        "SELECT r.id,r.order_id,r.reason,r.customer_note,r.merchant_note,r.status,r.requested_at,r.updated_at,o.order_number,o.total_bdt,s.slug AS store_slug,s.name AS store_name " +
        "FROM commerce_order_returns r JOIN commerce_orders o ON o.id=r.order_id JOIN commerce_stores s ON s.id=r.store_id " +
        "WHERE r.account_id=? ORDER BY r.requested_at DESC LIMIT 100"
      ).bind(account.id).all();
      return output(request,{returns:results});
    }
    const chatMatch = path.match(/^\/api\/customer\/chat\/([^/]+)$/);
    if (chatMatch) {
      const slug = decodeURIComponent(chatMatch[1]), store = await storeBySlug(env,slug);
      if (!store) return error(request,404,"দোকানটি পাওয়া যায়নি");
      if (method === "GET") {
        await env.DB.prepare("UPDATE commerce_customer_messages SET read_by_customer_at=CURRENT_TIMESTAMP WHERE store_id=? AND account_id=? AND sender_role='merchant' AND read_by_customer_at IS NULL")
          .bind(store.id,account.id).run();
        const {results} = await env.DB.prepare("SELECT id,store_id,account_id,order_id,sender_role,message,created_at,read_by_customer_at,read_by_merchant_at FROM commerce_customer_messages WHERE store_id=? AND account_id=? ORDER BY created_at DESC LIMIT 100")
          .bind(store.id,account.id).all();
        return output(request,{messages:results.reverse()});
      }
      if (method === "POST") {
        const body = await readJson(request), message = short(body.message || body.body,2000);
        if (message.length < 1) return error(request,422,"বার্তা লিখুন");
        const orderId = short(body.order_id,80) || null;
        if (orderId) {
          const owned = await env.DB.prepare("SELECT id FROM commerce_orders WHERE id=? AND store_id=? AND account_id=?").bind(orderId,store.id,account.id).first();
          if (!owned) return error(request,403,"এই অর্ডারের সঙ্গে বার্তাটি যুক্ত করা যাবে না");
        }
        const id = crypto.randomUUID();
        await env.DB.prepare("INSERT INTO commerce_customer_messages(id,store_id,account_id,order_id,sender_role,message) VALUES(?,?,?,?,?,?)")
          .bind(id,store.id,account.id,orderId,"customer",message).run();
        return output(request,{id,sender_role:"customer",message,created_at:new Date().toISOString()},201);
      }
    }
    const unreadMatch = path.match(/^\/api\/customer\/unread\/([^/]+)$/);
    if (unreadMatch && method === "GET") {
      const store = await storeBySlug(env,decodeURIComponent(unreadMatch[1]));
      if (!store) return error(request,404,"দোকানটি পাওয়া যায়নি");
      const row = await env.DB.prepare("SELECT COUNT(*) AS count FROM commerce_customer_messages WHERE store_id=? AND account_id=? AND sender_role='merchant' AND read_by_customer_at IS NULL")
        .bind(store.id,account.id).first();
      return output(request,{count:Number(row?.count||0)});
    }
    const reviewMatch = path.match(/^\/api\/customer\/reviews\/([^/]+)$/);
    if (reviewMatch && method === "POST") {
      const storeId=decodeURIComponent(reviewMatch[1]),body=await readJson(request);
      const rating=Number(body.rating),comment=short(body.comment,1000),orderId=short(body.order_id,80),productId=short(body.product_id,80);
      if(!validInteger(rating,1,5))return error(request,422,"১ থেকে ৫-এর মধ্যে রেটিং দিন");
      const order=await env.DB.prepare("SELECT * FROM commerce_orders WHERE id=? AND store_id=? AND account_id=?").bind(orderId,storeId,account.id).first();
      if(!order)return error(request,403,"এই অর্ডারের জন্য আপনি রিভিউ দিতে পারবেন না");
      if(!["fulfilled","delivered"].includes(order.status))return error(request,409,"অর্ডার সম্পন্ন হলে রিভিউ দিতে পারবেন");
      const line=await env.DB.prepare("SELECT product_id FROM commerce_order_lines WHERE order_id=? AND product_id=?").bind(order.id,productId).first();
      if(!line)return error(request,403,"এই পণ্যটি ওই অর্ডারে ছিল না");
      const product=await listedProduct(env,storeId,productId);
      if(!product)return error(request,404,"পণ্যটি পাওয়া যায়নি");
      const id=crypto.randomUUID();
      await env.DB.prepare("INSERT INTO commerce_product_reviews(id,account_id,store_id,product_id,order_id,rating,comment) VALUES(?,?,?,?,?,?,?) ON CONFLICT(account_id,store_id,product_id) DO UPDATE SET order_id=excluded.order_id,rating=excluded.rating,comment=excluded.comment,updated_at=CURRENT_TIMESTAMP")
        .bind(id,account.id,storeId,productId,orderId,rating,comment||null).run();
      return output(request,{ok:true,rating,comment},201);
    }
    return error(request,404,"Customer route not found");
  } catch (e) {
    console.error("D1 customer route failure",path,e?.message||e);
    const message = e?.message === "Payload too large" ? "অনুরোধটি খুব বড়" : "Customer service temporarily unavailable";
    return error(request,e?.message === "Payload too large" ? 413 : 500,message);
  }
}
