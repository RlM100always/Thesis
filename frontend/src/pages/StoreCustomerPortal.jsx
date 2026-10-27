/**
 * Store Customer Portal — পাবলিক স্টোরের কাস্টমার পোর্টাল
 * Sign up / Login → Profile (BD address) → Order history → Chat with store
 */

import { useEffect, useRef, useState } from "react";
import { getDistricts, getThanas, BD_DIVISIONS } from "../bd_address";
import "./StoreCustomerPortal.css";
import { AddressesView, WishlistView, SecurityView } from "./StoreCustomerAccountViews";

// ── API helpers ───────────────────────────────────────────────────────────────

const SC_BASE = "/api/sc";

function scHeaders(token) {
  return { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) };
}

async function scFetch(path, opts = {}, token = null) {
  const res = await fetch(`${SC_BASE}${path}`, {
    ...opts,
    headers: { ...scHeaders(token), ...(opts.headers || {}) },
  });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json.detail || "অনুরোধটি সম্পন্ন করা যায়নি। আবার চেষ্টা করুন।");
  return json;
}

// ── Storage ───────────────────────────────────────────────────────────────────

const SC_KEY = "sc_token";
function saveToken(t) { try { localStorage.setItem(SC_KEY, t); } catch (_) {} }
function loadToken() { try { return localStorage.getItem(SC_KEY); } catch (_) { return null; } }
function clearToken() { try { localStorage.removeItem(SC_KEY); } catch (_) {} }

// ── Sub-components ────────────────────────────────────────────────────────────

function Spinner() {
  return <div style={{ textAlign: "center", padding: 32, color: "var(--text-muted)", fontSize: 13 }}>লোড হচ্ছে…</div>;
}

function Err({ msg }) {
  if (!msg) return null;
  return <div className="sc-alert sc-alert-error" role="alert">{msg}</div>;
}

function Ok({ msg }) {
  if (!msg) return null;
  return <div className="sc-alert sc-alert-success" role="status">{msg}</div>;
}

// ── Auth View ─────────────────────────────────────────────────────────────────

function AuthView({ onLogin }) {
  const [mode, setMode] = useState("login"); // login | register
  const [form, setForm] = useState({ display_name: "", email_or_phone: "", email: "", phone: "", password: "" });
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const set = (k) => (e) => setForm(f => ({ ...f, [k]: e.target.value }));

  async function submit(e) {
    e.preventDefault();
    setErr(""); setLoading(true);
    try {
      let data;
      if (mode === "login") {
        data = await scFetch("/login", { method: "POST", body: JSON.stringify({ email_or_phone: form.email_or_phone, password: form.password }) });
      } else {
        if (!form.email && !form.phone) { setErr("ইমেইল অথবা ফোন নম্বর লিখুন।"); setLoading(false); return; }
        data = await scFetch("/register", { method: "POST", body: JSON.stringify({ display_name: form.display_name, email: form.email || undefined, phone: form.phone || undefined, password: form.password }) });
      }
      saveToken(data.token);
      onLogin(data.token, data.customer);
    } catch (ex) {
      setErr(ex.message);
    } finally {
      setLoading(false);
    }
  }

  const inp = { style: { width: "100%", padding: "10px 12px", borderRadius: 10, border: "1px solid var(--border)", background: "var(--bg)", color: "var(--text)", fontSize: 14, boxSizing: "border-box", marginBottom: 10 } };

  return (
    <div style={{ maxWidth: 380, margin: "0 auto", padding: "24px 20px" }}>
      <div style={{ textAlign: "center", marginBottom: 24 }}>
        <div style={{ fontSize: 32, marginBottom: 6 }}>🛍️</div>
        <h2 style={{ margin: 0, fontSize: 20, color: "var(--text)" }}>ক্রেতার অ্যাকাউন্ট</h2>
        <p style={{ margin: "6px 0 0", fontSize: 13, color: "var(--text-muted)" }}>
          {mode === "login" ? "আপনার অর্ডার দেখুন এবং দোকানের সঙ্গে যোগাযোগ করুন" : "নতুন অ্যাকাউন্ট খুলুন"}
        </p>
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
        {["login", "register"].map(m => (
          <button key={m} onClick={() => { setMode(m); setErr(""); }}
            style={{ flex: 1, padding: "9px 0", borderRadius: 10, border: "none", cursor: "pointer", fontWeight: 600, fontSize: 13,
              background: mode === m ? "var(--green)" : "var(--surface)", color: mode === m ? "var(--sc-on-green)" : "var(--text-muted)" }}>
            {m === "login" ? "লগইন" : "নিবন্ধন"}
          </button>
        ))}
      </div>

      <Err msg={err} />
      <form onSubmit={submit}>
        {mode === "register" && (
          <>
            <input {...inp} placeholder="আপনার নাম *" value={form.display_name} onChange={set("display_name")} required />
            <input {...inp} type="email" placeholder="ইমেইল (ঐচ্ছিক)" value={form.email} onChange={set("email")} />
            <input {...inp} type="tel" placeholder="ফোন নম্বর (ঐচ্ছিক)" value={form.phone} onChange={set("phone")} />
          </>
        )}
        {mode === "login" && (
          <input {...inp} placeholder="ইমেইল বা ফোন নম্বর" value={form.email_or_phone} onChange={set("email_or_phone")} required />
        )}
        <input {...inp} type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} minLength={mode === "register" ? 8 : undefined} placeholder={mode === "register" ? "পাসওয়ার্ড (কমপক্ষে ৮ অক্ষর) *" : "পাসওয়ার্ড *"} value={form.password} onChange={set("password")} required />
        <button type="submit" disabled={loading} style={{ width: "100%", padding: "11px 0", borderRadius: 10, border: "none", background: "var(--green)", color: "var(--sc-on-green)", fontWeight: 700, fontSize: 14, cursor: loading ? "not-allowed" : "pointer", opacity: loading ? .7 : 1 }}>
          {loading ? "অপেক্ষা করুন…" : mode === "login" ? "লগইন করুন" : "অ্যাকাউন্ট তৈরি করুন"}
        </button>
      </form>
    </div>
  );
}

// ── Profile View ──────────────────────────────────────────────────────────────

function ProfileView({ customer, token, onUpdate }) {
  const [form, setForm] = useState({
    display_name: customer.display_name || "",
    phone: customer.phone || "",
    division: customer.division || "",
    district: customer.district || "",
    thana: customer.thana || "",
    address_detail: customer.address_detail || "",
    avatar_data_url: customer.avatar_data_url || "",
  });
  const [ok, setOk] = useState(""); const [err, setErr] = useState(""); const [saving, setSaving] = useState(false);

  const districts = getDistricts(form.division);
  const thanas = getThanas(form.district);

  const set = (k) => (e) => {
    const val = e.target.value;
    setForm(f => {
      const next = { ...f, [k]: val };
      if (k === "division") { next.district = ""; next.thana = ""; }
      if (k === "district") { next.thana = ""; }
      return next;
    });
  };
  function uploadAvatar(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) { setErr("ছবির ফাইল নির্বাচন করুন।"); return; }
    if (file.size > 1024 * 1024) { setErr("প্রোফাইল ছবির আকার ১ MB-এর মধ্যে রাখুন।"); return; }
    const reader = new FileReader();
    reader.onload = () => setForm(current => ({ ...current, avatar_data_url: String(reader.result || "") }));
    reader.onerror = () => setErr("ছবিটি পড়া যায়নি। আবার চেষ্টা করুন।");
    reader.readAsDataURL(file);
  }

  async function save(e) {
    e.preventDefault(); setSaving(true); setErr(""); setOk("");
    try {
      const updated = await scFetch("/me", { method: "PATCH", body: JSON.stringify(form) }, token);
      setOk("প্রোফাইল সংরক্ষিত হয়েছে ✓");
      onUpdate(updated);
    } catch (ex) { setErr(ex.message); }
    finally { setSaving(false); }
  }

  const sel = { style: { width: "100%", padding: "10px 12px", borderRadius: 10, border: "1px solid var(--border)", background: "var(--bg)", color: "var(--text)", fontSize: 14, boxSizing: "border-box", marginBottom: 10 } };
  const inp = { style: { ...sel.style } };

  return (
    <form onSubmit={save} style={{ padding: "0 4px" }}>
      <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 16, color: "var(--text)" }}>আমার প্রোফাইল</h3>
      <Ok msg={ok} /><Err msg={err} />

      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14 }}>
        <div style={{ width: 62, height: 62, borderRadius: "50%", overflow: "hidden", flexShrink: 0, display: "grid", placeItems: "center", background: "var(--surface)", border: "1px solid var(--border)", color: "var(--green)", fontSize: 24, fontWeight: 800 }}>
          {form.avatar_data_url ? <img src={form.avatar_data_url} alt="প্রোফাইল ছবি" style={{ width: "100%", height: "100%", objectFit: "cover" }} /> : (form.display_name?.[0] || "👤")}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <label style={{ fontSize: 12, color: "var(--text-muted)", fontWeight: 650, display: "block", marginBottom: 5 }}>প্রোফাইল ছবি (সর্বোচ্চ ১ MB)</label>
          <input type="file" accept="image/*" onChange={uploadAvatar} style={{ width: "100%", fontSize: 12, color: "var(--text)" }} />
          {form.avatar_data_url && <button type="button" onClick={() => setForm(current => ({ ...current, avatar_data_url: "" }))} style={{ marginTop: 5, border: 0, background: "none", color: "#dc2626", cursor: "pointer", fontSize: 11 }}>ছবি সরান</button>}
        </div>
      </div>

      <label style={{ fontSize: 12, color: "var(--text-muted)", fontWeight: 600 }}>নাম</label>
      <input {...inp} value={form.display_name} onChange={set("display_name")} required />

      <label style={{ fontSize: 12, color: "var(--text-muted)", fontWeight: 600 }}>অ্যাকাউন্টের ইমেইল</label>
      <input {...inp} value={customer.email || "ইমেইল যোগ করা হয়নি"} disabled style={{ ...inp.style, opacity: .72 }} />
      <label style={{ fontSize: 12, color: "var(--text-muted)", fontWeight: 600 }}>ফোন নম্বর</label>
      <input {...inp} type="tel" value={form.phone} onChange={set("phone")} placeholder="01XXXXXXXXX" />

      <div style={{ background: "color-mix(in srgb,var(--green) 6%,transparent)", borderRadius: 12, padding: "14px 14px 6px", marginBottom: 10, border: "1px solid color-mix(in srgb,var(--green) 20%,transparent)" }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: "var(--green)", marginBottom: 10 }}>📍 ঠিকানা</div>

        <label style={{ fontSize: 12, color: "var(--text-muted)", fontWeight: 600 }}>বিভাগ</label>
        <select {...sel} value={form.division} onChange={set("division")}>
          <option value="">বিভাগ বেছে নিন</option>
          {BD_DIVISIONS.map(d => <option key={d} value={d}>{d}</option>)}
        </select>

        <label style={{ fontSize: 12, color: "var(--text-muted)", fontWeight: 600 }}>জেলা</label>
        <select {...sel} value={form.district} onChange={set("district")} disabled={!form.division}>
          <option value="">জেলা বেছে নিন</option>
          {districts.map(d => <option key={d} value={d}>{d}</option>)}
        </select>

        <label style={{ fontSize: 12, color: "var(--text-muted)", fontWeight: 600 }}>থানা / উপজেলা</label>
        <select {...sel} value={form.thana} onChange={set("thana")} disabled={!form.district}>
          <option value="">থানা বেছে নিন</option>
          {thanas.map(t => <option key={t} value={t}>{t}</option>)}
        </select>

        <label style={{ fontSize: 12, color: "var(--text-muted)", fontWeight: 600 }}>বিস্তারিত ঠিকানা</label>
        <input {...inp} value={form.address_detail} onChange={set("address_detail")} placeholder="বাড়ি / রোড / এলাকা" />
      </div>

      <button type="submit" disabled={saving} style={{ width: "100%", padding: "11px 0", borderRadius: 10, border: "none", background: "var(--green)", color: "var(--sc-on-green)", fontWeight: 700, fontSize: 14, cursor: saving ? "not-allowed" : "pointer", opacity: saving ? .7 : 1 }}>
        {saving ? "সংরক্ষণ হচ্ছে…" : "সংরক্ষণ করুন"}
      </button>
    </form>
  );
}

function OrderReviewForm({ order, item, token }) {
  const [rating, setRating] = useState("5");
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError(""); setSuccess("");
    try {
      const response = await fetch(`/api/public/reviews/${encodeURIComponent(order.organization_id)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ product_id: item.product_id, order_id: order.id, rating: Number(rating), comment: comment.trim() || null }),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail || "রিভিউ জমা দেওয়া যায়নি।");
      setSuccess("রিভিউ সংরক্ষণ হয়েছে। ধন্যবাদ!");
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  return <form onSubmit={submit} style={{ border: "1px solid var(--border)", borderRadius: 10, padding: 10, marginTop: 8, display: "grid", gap: 7 }}>
    <div style={{ fontSize: 12, fontWeight: 700, color: "var(--text)" }}>{item.description || "পণ্য"} — রিভিউ</div>
    <div style={{ display: "grid", gridTemplateColumns: "90px 1fr", gap: 7 }}>
      <select aria-label="রেটিং" value={rating} onChange={e => setRating(e.target.value)} style={{ padding: "7px 8px", borderRadius: 8, border: "1px solid var(--border)", background: "var(--bg)", color: "var(--text)", fontSize: 12 }}>
        {[5,4,3,2,1].map(n => <option key={n} value={n}>{n} ★</option>)}
      </select>
      <input value={comment} onChange={e => setComment(e.target.value)} maxLength={1000} placeholder="আপনার অভিজ্ঞতা লিখুন (ঐচ্ছিক)" style={{ minWidth: 0, padding: "7px 9px", borderRadius: 8, border: "1px solid var(--border)", background: "var(--bg)", color: "var(--text)", fontSize: 12 }}/>
    </div>
    {error && <div role="alert" style={{ color: "#dc2626", fontSize: 11 }}>{error}</div>}
    {success && <div role="status" style={{ color: "#15803d", fontSize: 11 }}>{success}</div>}
    <button type="submit" disabled={busy} style={{ justifySelf: "start", padding: "7px 11px", borderRadius: 8, border: 0, background: "var(--green)", color: "var(--sc-on-green)", fontSize: 11, fontWeight: 700, cursor: "pointer" }}>{busy ? "জমা হচ্ছে…" : "রিভিউ জমা দিন"}</button>
  </form>;
}

// ── Orders View ───────────────────────────────────────────────────────────────

const STATUS_STEPS = ["placed", "confirmed", "ready", "dispatched", "delivered"];
const STATUS_LABEL = { placed: "অর্ডার দেওয়া হয়েছে", confirmed: "নিশ্চিত", ready: "প্রস্তুত", processing: "প্রস্তুত হচ্ছে", dispatched: "পাঠানো হয়েছে", shipped: "পাঠানো হয়েছে", delivered: "ডেলিভারি হয়েছে", cancelled: "বাতিল" };
const STATUS_COLOR = { placed: "#f59e0b", confirmed: "#3b82f6", processing: "#8b5cf6", shipped: "#06b6d4", delivered: "#22c55e", cancelled: "#ef4444" };
const STATUS_ICON = { placed: "📝", confirmed: "✅", ready: "⚙️", processing: "⚙️", dispatched: "🚚", shipped: "🚚", delivered: "🎉", cancelled: "❌" };

function OrderTimeline({ status }) {
  if (status === "cancelled") return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, padding: "8px 0", color: "#ef4444", fontSize: 12, fontWeight: 600 }}>❌ অর্ডার বাতিল হয়েছে</div>
  );
  const normalizedStatus = status === "processing" ? "ready" : status === "shipped" ? "dispatched" : status;
  const cur = STATUS_STEPS.indexOf(normalizedStatus);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 0, padding: "10px 0 6px", overflowX: "auto" }}>
      {STATUS_STEPS.map((s, i) => {
        const done = i <= cur;
        const active = i === cur;
        return (
          <div key={s} style={{ display: "flex", alignItems: "center", flex: i < STATUS_STEPS.length - 1 ? 1 : 0 }}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 3, minWidth: 52 }}>
              <div style={{ width: 28, height: 28, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14,
                background: done ? (active ? STATUS_COLOR[s] : "#22c55e") : "var(--surface)",
                border: `2px solid ${done ? (active ? STATUS_COLOR[s] : "#22c55e") : "var(--border)"}`,
                boxShadow: active ? `0 0 0 3px ${STATUS_COLOR[s]}33` : "none",
                transition: "all .3s" }}>
                {done ? (active ? STATUS_ICON[s] : "✓") : <span style={{ fontSize: 8, color: "var(--text-muted)" }}>○</span>}
              </div>
              <div style={{ fontSize: 9, color: done ? "var(--text)" : "var(--text-muted)", fontWeight: done ? 700 : 400, textAlign: "center", lineHeight: 1.2, maxWidth: 50 }}>
                {STATUS_LABEL[s]?.split(" ")[0]}
              </div>
            </div>
            {i < STATUS_STEPS.length - 1 && (
              <div style={{ flex: 1, height: 2, background: i < cur ? "#22c55e" : "var(--border)", margin: "0 2px", marginBottom: 18, transition: "background .3s" }} />
            )}
          </div>
        );
      })}
    </div>
  );
}

function OrdersView({ storeSlug, token, onReorder }) {
  const [orders, setOrders] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [expanded, setExpanded] = useState(null);
  const [cancelling, setCancelling] = useState(null);

  useEffect(() => {
    setLoading(true); setErr("");
    scFetch(`/orders?page=${page}${statusFilter ? `&status=${statusFilter}` : ""}`, {}, token)
      .then(d => { setOrders(d.orders || []); setTotal(d.total || 0); })
      .catch(ex => setErr(ex.message))
      .finally(() => setLoading(false));
  }, [page, statusFilter, token]);

  async function cancelOrder(o) {
    if (!o.organization_id || !o.access_token) { setErr("এই অর্ডারটি বাতিল করা যাচ্ছে না।"); return; }
    if (!window.confirm("এই অর্ডারটি বাতিল করতে চান?")) return;
    setCancelling(o.id);
    try {
      const res = await fetch(`/api/public/orders/${o.organization_id}/cancel/${o.access_token}`, { method: "POST" });
      if (!res.ok) { const d = await res.json(); throw new Error(d.detail || "অর্ডার বাতিল করা যায়নি।"); }
      // Refresh orders
      const d = await scFetch(`/orders?page=${page}${statusFilter ? `&status=${statusFilter}` : ""}`, {}, token);
      setOrders(d.orders || []);
    } catch (ex) { setErr(ex.message); }
    finally { setCancelling(null); }
  }

  const filtered = search
    ? orders.filter(o => o.document_number?.toLowerCase().includes(search.toLowerCase()) ||
        o.items?.some(i => i.description?.toLowerCase().includes(search.toLowerCase())))
    : orders;

  return (
    <div>
      <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 14, color: "var(--text)" }}>সব দোকানের অর্ডার</h3>
      <div style={{ display: "flex", gap: 8, marginBottom: 14, flexWrap: "wrap" }}>
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="অর্ডার নম্বর / পণ্য খুঁজুন"
          style={{ flex: 1, minWidth: 140, padding: "8px 12px", borderRadius: 10, border: "1px solid var(--border)", background: "var(--bg)", color: "var(--text)", fontSize: 13 }} />
        <select value={statusFilter} onChange={e => { setStatusFilter(e.target.value); setPage(1); }}
          style={{ padding: "8px 12px", borderRadius: 10, border: "1px solid var(--border)", background: "var(--bg)", color: "var(--text)", fontSize: 13 }}>
          <option value="">সব অবস্থা</option>
          {Object.entries(STATUS_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </div>
      <Err msg={err} />
      {loading ? <Spinner /> : filtered.length === 0 ? (
        <div style={{ textAlign: "center", padding: 32, color: "var(--text-muted)", fontSize: 13 }}>এখনো কোনো অর্ডার পাওয়া যায়নি।</div>
      ) : (
        filtered.map(o => (
          <div key={o.id} style={{ background: "var(--surface)", borderRadius: 12, border: "1px solid var(--border)", marginBottom: 10, overflow: "hidden" }}>
            <div onClick={() => setExpanded(e => e === o.id ? null : o.id)}
              style={{ padding: "12px 14px", cursor: "pointer", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
              <div>
                <div style={{ fontWeight: 700, fontSize: 13, color: "var(--text)" }}>{o.document_number}</div>
                {o.store_name && <div style={{ fontSize: 11, color: "var(--green)", marginTop: 2 }}>{o.store_name}{o.is_demo ? " · পরীক্ষামূলক দোকান" : ""}</div>}
                <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>
                  {o.issued_at ? new Date(o.issued_at).toLocaleDateString("bn-BD", { day: "numeric", month: "long", year: "numeric" }) : "—"} · ৳{Number(o.total).toLocaleString("bn-BD")}
                </div>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ fontSize: 11, fontWeight: 700, borderRadius: 8, padding: "3px 10px", background: `${STATUS_COLOR[o.status] || "#64748b"}22`, color: STATUS_COLOR[o.status] || "#64748b" }}>
                  {STATUS_LABEL[o.status] || o.status}
                </span>
                <span style={{ color: "var(--text-muted)", fontSize: 16 }}>{expanded === o.id ? "▲" : "▼"}</span>
              </div>
            </div>
            {expanded === o.id && (
              <div style={{ borderTop: "1px solid var(--border)", padding: "12px 14px" }}>
                {/* Status timeline */}
                <OrderTimeline status={o.status} />

                {/* Items */}
                <div style={{ marginTop: 8 }}>
                  {o.items?.map((item, i) => (
                    <div key={i} style={{ display: "flex", justifyContent: "space-between", fontSize: 13, padding: "5px 0", color: "var(--text)", borderBottom: i < o.items.length - 1 ? "1px solid var(--border)" : "none" }}>
                      <span>{item.description} <span style={{ color: "var(--text-muted)" }}>× {Number(item.quantity)}</span></span>
                      <span style={{ fontWeight: 600 }}>৳{Number(item.line_total).toLocaleString("bn-BD")}</span>
                    </div>
                  ))}
                </div>
                {o.notes && <div style={{ marginTop: 8, fontSize: 12, color: "var(--text-muted)" }}>📝 {o.notes}</div>}
                {o.shipping_address && <div style={{ marginTop: 4, fontSize: 12, color: "var(--text-muted)" }}>📍 {o.shipping_address}</div>}
                {o.status_note && (
                  <div style={{ marginTop: 8, padding: "8px 12px", background: "color-mix(in srgb, #3b82f6 10%, transparent)", borderRadius: 8, border: "1px solid #3b82f640", fontSize: 13, color: "var(--text)" }}>
                    💬 দোকান থেকে: {o.status_note}
                  </div>
                )}
                {o.status === "delivered" && o.items?.length > 0 && (
                  <div style={{ marginTop: 12, paddingTop: 10, borderTop: "1px solid var(--border)" }}>
                    <div style={{ color: "var(--text)", fontSize: 13, fontWeight: 750 }}>⭐ কেনা পণ্যের রিভিউ</div>
                    {o.items.map((item, index) => <OrderReviewForm key={`${o.id}-${item.product_id}-${index}`} order={o} item={item} token={token} />)}
                  </div>
                )}
                {Number(o.delivery_fee) > 0 && (
                  <div style={{ marginTop: 6, fontSize: 12, color: "var(--text-muted)" }}>🚚 ডেলিভারি খরচ: ৳{Number(o.delivery_fee).toLocaleString("bn-BD")}</div>
                )}

                {/* Cancel button */}
                {o.status === "placed" && (
                  <button disabled={cancelling === o.id} onClick={() => cancelOrder(o)}
                    style={{ marginTop: 12, width: "100%", padding: "9px 0", borderRadius: 10, border: "2px solid #ef4444", background: "transparent", color: "#ef4444", fontWeight: 700, fontSize: 13, cursor: "pointer" }}>
                    {cancelling === o.id ? "বাতিল হচ্ছে…" : "✕ অর্ডার বাতিল করুন"}
                  </button>
                )}

                {/* Reorder */}
                {o.status !== "cancelled" && o.items?.length > 0 && o.store_slug && o.store_slug !== storeSlug ? (
                  <button onClick={() => window.location.assign(`/store/${encodeURIComponent(o.store_slug)}`)} style={{ marginTop: 12, width: "100%", padding: "9px 0", borderRadius: 10, border: "1px solid var(--green)", background: "var(--surface)", color: "var(--green)", fontWeight: 700, fontSize: 13, cursor: "pointer" }}>
                    🏪 এই দোকানে যান
                  </button>
                ) : o.status !== "cancelled" && o.items?.length > 0 && onReorder && (
                  <button onClick={() => onReorder(o.items)} style={{ marginTop: 12, width: "100%", padding: "9px 0", borderRadius: 10, border: "2px solid var(--green)", background: "transparent", color: "var(--green)", fontWeight: 700, fontSize: 13, cursor: "pointer" }}>
                    🔄 আবার অর্ডার করুন
                  </button>
                )}
              </div>
            )}
          </div>
        ))
      )}
      {total > 10 && (
        <div style={{ display: "flex", gap: 6, justifyContent: "center", marginTop: 10 }}>
          {page > 1 && <button onClick={() => setPage(p => p - 1)} style={{ padding: "6px 14px", borderRadius: 8, border: "1px solid var(--border)", background: "var(--surface)", color: "var(--text)", cursor: "pointer", fontSize: 13 }}>← আগের</button>}
          <span style={{ padding: "6px 10px", fontSize: 13, color: "var(--text-muted)" }}>পাতা {page}</span>
          {orders.length === 10 && <button onClick={() => setPage(p => p + 1)} style={{ padding: "6px 14px", borderRadius: 8, border: "1px solid var(--border)", background: "var(--surface)", color: "var(--text)", cursor: "pointer", fontSize: 13 }}>পরের →</button>}
        </div>
      )}
    </div>
  );
}

// ── Chat View ─────────────────────────────────────────────────────────────────

function ChatView({ storeSlug, token, storeName }) {
  const [msgs, setMsgs] = useState([]);
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [err, setErr] = useState("");
  const bottomRef = useRef(null);

  const load = () => {
    scFetch(`/chat/${storeSlug}`, {}, token)
      .then(d => { setMsgs(d.messages || []); setLoading(false); })
      .catch(ex => { setErr(ex.message); setLoading(false); });
  };

  useEffect(() => { load(); const id = setInterval(load, 8000); return () => clearInterval(id); }, [storeSlug, token]);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs]);

  async function send(e) {
    e.preventDefault();
    if (!text.trim()) return;
    setSending(true); setErr("");
    try {
      const msg = await scFetch(`/chat/${storeSlug}`, { method: "POST", body: JSON.stringify({ body: text.trim() }) }, token);
      setMsgs(m => [...m, msg]);
      setText("");
    } catch (ex) { setErr(ex.message); }
    finally { setSending(false); }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 12, color: "var(--text)", flexShrink: 0 }}>{storeName} — চ্যাট</h3>
      <div style={{ flex: 1, overflowY: "auto", paddingRight: 4, minHeight: 200, maxHeight: 380 }}>
        {loading ? <Spinner /> : msgs.length === 0 ? (
          <div style={{ textAlign: "center", padding: 32, color: "var(--text-muted)", fontSize: 13 }}>
            দোকানে বার্তা পাঠিয়ে আপনার প্রশ্ন জানাতে পারেন।
          </div>
        ) : msgs.map(m => (
          <div key={m.id} style={{ display: "flex", justifyContent: m.sender === "customer" ? "flex-end" : "flex-start", marginBottom: 8 }}>
            <div style={{
              maxWidth: "75%", padding: "9px 13px", borderRadius: m.sender === "customer" ? "14px 14px 4px 14px" : "14px 14px 14px 4px",
              background: m.sender === "customer" ? "var(--green)" : "var(--surface)",
              color: m.sender === "customer" ? "var(--sc-on-green)" : "var(--text)",
              border: m.sender === "store" ? "1px solid var(--border)" : "none",
              fontSize: 13, lineHeight: 1.5,
            }}>
              {m.body}
              <div style={{ fontSize: 10, opacity: .65, marginTop: 3, textAlign: "right" }}>
                {m.created_at ? new Date(m.created_at).toLocaleTimeString("bn-BD", { hour: "2-digit", minute: "2-digit" }) : ""}
                {m.sender === "customer" && m.read_at ? " ✓✓" : m.sender === "customer" ? " ✓" : ""}
              </div>
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
      <Err msg={err} />
      <form onSubmit={send} style={{ display: "flex", gap: 8, marginTop: 10, flexShrink: 0 }}>
        <input value={text} onChange={e => setText(e.target.value)} placeholder="মেসেজ লিখুন…"
          style={{ flex: 1, padding: "10px 14px", borderRadius: 12, border: "1px solid var(--border)", background: "var(--bg)", color: "var(--text)", fontSize: 14 }} />
        <button type="submit" disabled={sending || !text.trim()}
          style={{ padding: "10px 18px", borderRadius: 12, border: "none", background: "var(--green)", color: "var(--sc-on-green)", fontWeight: 700, cursor: sending ? "not-allowed" : "pointer", opacity: sending ? .7 : 1 }}>
          পাঠান
        </button>
      </form>
    </div>
  );
}

// ── Main Portal Component ─────────────────────────────────────────────────────

const TABS = [
  { id: "profile", label: "প্রোফাইল", icon: "👤" },
  { id: "addresses", label: "ঠিকানা", icon: "📍" },
  { id: "orders", label: "অর্ডার", icon: "📦" },
  { id: "wishlist", label: "পছন্দ", icon: "♡" },
  { id: "security", label: "নিরাপত্তা", icon: "🔐" },
  { id: "chat", label: "চ্যাট", icon: "💬" },
];

export default function StoreCustomerPortal({ storeSlug, storeName, onClose, onAuthChange, onReorder, onAddToCart }) {
  const [token, setToken] = useState(() => loadToken());
  const [customer, setCustomer] = useState(null);
  const [tab, setTab] = useState("profile");
  const [loading, setLoading] = useState(!!loadToken());

  useEffect(() => {
    if (token && !customer) {
      scFetch("/me", {}, token)
        .then(c => { setCustomer(c); setLoading(false); })
        .catch(() => { clearToken(); setToken(null); setLoading(false); });
    } else {
      setLoading(false);
    }
  }, [token]);

  function handleLogin(t, c) { setToken(t); setCustomer(c); saveToken(t); onAuthChange?.(c); }
  async function handleLogout() {
    const current = token;
    try { if (current) await scFetch("/logout", { method: "POST" }, current); } catch (_) {}
    clearToken(); setToken(null); setCustomer(null); onAuthChange?.(null);
  }
  function handleTokenChange(nextToken, nextCustomer) {
    saveToken(nextToken); setToken(nextToken); setCustomer(nextCustomer); onAuthChange?.(nextCustomer);
  }

  return (
    <div className="store-customer-portal" style={{ position: "fixed", inset: 0, zIndex: 1200, display: "flex", alignItems: "center", justifyContent: "center", padding: 20, pointerEvents: "none" }}>
      {/* Backdrop */}
      <div onClick={onClose} style={{ position: "absolute", inset: 0, background: "rgba(0,0,0,.4)", pointerEvents: "all" }} />

      {/* Panel */}
      <div className="sc-account-panel" style={{ position: "relative", width: "min(980px, calc(100vw - 40px))", height: "min(820px, calc(100vh - 40px))", background: "var(--bg)", border: "1px solid var(--border)", borderRadius: 22, boxShadow: "0 24px 80px rgba(0,0,0,.28)", display: "flex", flexDirection: "column", pointerEvents: "all", overflow: "hidden" }}>
        {/* Header */}
        <div style={{ padding: "16px 18px 12px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: "var(--text)" }}>
              {customer ? `স্বাগতম, ${customer.display_name}` : "ক্রেতার অ্যাকাউন্ট"}
            </div>
            <div style={{ fontSize: 11, color: "var(--text-muted)" }}>{storeName} · সব দোকানে একই অ্যাকাউন্ট</div>
          </div>
          {customer && (
            <button onClick={handleLogout} style={{ fontSize: 11, color: "var(--text-muted)", background: "none", border: "1px solid var(--border)", borderRadius: 8, padding: "4px 10px", cursor: "pointer" }}>
              লগআউট
            </button>
          )}
          <button onClick={onClose} style={{ background: "none", border: "none", fontSize: 20, cursor: "pointer", color: "var(--text-muted)", lineHeight: 1 }}>✕</button>
        </div>

        {/* Content */}
        <div style={{ flex: 1, overflowY: "auto", padding: "16px 18px" }}>
          {loading ? <Spinner /> : !token || !customer ? (
            <AuthView onLogin={handleLogin} />
          ) : (
            <>
              {/* Tabs */}
              <div className="sc-account-tabs" role="tablist" aria-label="অ্যাকাউন্ট ব্যবস্থাপনা" style={{ display: "flex", gap: 5, marginBottom: 18, background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, padding: 4, overflowX: "auto", flexShrink: 0 }}>
                {TABS.map(t => (
                  <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)}
                    style={{ flex: "1 0 auto", minWidth: 86, padding: "9px 10px", borderRadius: 9, border: "none", cursor: "pointer", fontWeight: 700, fontSize: 12, transition: "all .15s",
                      background: tab === t.id ? "var(--green)" : "transparent",
                      color: tab === t.id ? "var(--sc-on-green)" : "var(--text-muted)" }}>
                    <span style={{ marginRight: 4 }}>{t.icon}</span>{t.label}
                  </button>
                ))}
              </div>

              {tab === "profile" && <ProfileView customer={customer} token={token} onUpdate={setCustomer} />}
              {tab === "addresses" && <AddressesView token={token} />}
              {tab === "orders" && <OrdersView storeSlug={storeSlug} token={token} onReorder={onReorder ? (items) => { onReorder(items); onClose(); } : null} />}
              {tab === "wishlist" && <WishlistView token={token} storeSlug={storeSlug} onAddToCart={onAddToCart ? (productId) => { onAddToCart(productId); onClose(); } : null} />}
              {tab === "security" && <SecurityView token={token} onTokenChange={handleTokenChange} />}
              {tab === "chat" && <ChatView storeSlug={storeSlug} token={token} storeName={storeName} />}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
