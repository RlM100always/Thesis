/**
 * Store Admin — manages the org's public storefront from within the B-SMART app.
 * Tabs: Overview → Builder → Products → Orders → Settings
 */

import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { explain } from "../errors";
import { money } from "../format";
import { Button, Card, Field, Notice, PageHeader } from "../ui/kit";
import { useFeedback, FeedbackBanner } from "../components/FeedbackBanner";
import Icon from "../ui/Icon";

const TABS = [
  { id: "overview", label: "সারসংক্ষেপ" },
  { id: "builder", label: "স্টোর বিল্ডার" },
  { id: "products", label: "পণ্য তালিকা" },
  { id: "orders", label: "অনলাইন অর্ডার" },
  { id: "settings", label: "সেটিংস" },
];

const PRESETS = [
  { id: "clean", label: "Clean", desc: "সাদা, মিনিমাল" },
  { id: "bold", label: "Bold", desc: "গাঢ়, হাই-কন্ট্রাস্ট" },
  { id: "warm", label: "Warm", desc: "ক্রিম, আর্থি" },
  { id: "fresh", label: "Fresh", desc: "সবুজাভ, হালকা" },
];

const STATUS_LABEL = {
  placed: { label: "নতুন", color: "#f59e0b" },
  confirmed: { label: "নিশ্চিত", color: "#3b82f6" },
  ready: { label: "প্রস্তুত", color: "#6366f1" },
  dispatched: { label: "পাঠানো", color: "#8b5cf6" },
  delivered: { label: "পৌঁছেছে", color: "#10b981" },
  cancelled: { label: "বাতিল", color: "#ef4444" },
};

function statusBadge(status) {
  const s = STATUS_LABEL[status] || { label: status, color: "#6b7280" };
  return (
    <span style={{ background: s.color + "18", color: s.color, borderRadius: 6, padding: "2px 10px", fontSize: 12, fontWeight: 600 }}>
      {s.label}
    </span>
  );
}

// ─── Overview tab ─────────────────────────────────────────────────────────────
function OverviewTab({ store, stats, orgId }) {
  if (!store) return (
    <div style={{ textAlign: "center", padding: "56px 20px" }}>
      <div style={{ fontSize: 56, marginBottom: 16 }}>🏪</div>
      <h3>অনলাইন স্টোর এখনো তৈরি হয়নি</h3>
      <p className="muted">স্টোর বিল্ডার ট্যাবে গিয়ে আপনার স্টোর তৈরি করুন।</p>
    </div>
  );
  const storeUrl = `${window.location.origin}${window.location.pathname.split("/app")[0]}#/store/${orgId}`;
  return (
    <div style={{ display: "grid", gap: 20 }}>
      {/* Status card */}
      <Card>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
          <div>
            <p style={{ margin: 0, fontSize: 13, color: "#6b8a7a", fontWeight: 600, textTransform: "uppercase", letterSpacing: ".04em" }}>স্টোরের অবস্থা</p>
            <h3 style={{ margin: "4px 0 0", fontSize: 20, fontWeight: 800 }}>{store.display_name}</h3>
            <p style={{ margin: "4px 0 0", fontSize: 13, color: "#6b8a7a" }}>{store.tagline}</p>
          </div>
          <div style={{ textAlign: "right" }}>
            {store.is_active
              ? <span style={{ background: "#dcfce7", color: "#15803d", borderRadius: 8, padding: "6px 16px", fontWeight: 700, fontSize: 14 }}>🟢 সক্রিয়</span>
              : <span style={{ background: "#fef3c7", color: "#b45309", borderRadius: 8, padding: "6px 16px", fontWeight: 700, fontSize: 14 }}>🟡 নিষ্ক্রিয়</span>
            }
          </div>
        </div>
        {store.is_active && (
          <div style={{ marginTop: 16, background: "#f0f9f4", borderRadius: 8, padding: "10px 14px", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
            <span style={{ fontSize: 13, fontFamily: "monospace", color: "#0a8752", wordBreak: "break-all" }}>{storeUrl}</span>
            <button
              style={{ background: "none", border: "1px solid #0a8752", color: "#0a8752", borderRadius: 6, padding: "4px 12px", fontSize: 12, cursor: "pointer", fontWeight: 600 }}
              onClick={() => { navigator.clipboard?.writeText(storeUrl).catch(() => {}); }}
            >লিংক কপি</button>
          </div>
        )}
      </Card>

      {/* Stats row */}
      {stats && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: 14 }}>
          {[
            { label: "মোট অর্ডার", value: stats.total_orders, icon: "📦" },
            { label: "অপেক্ষারত", value: stats.pending_orders, icon: "⏳", alert: stats.pending_orders > 0 },
            { label: "রাজস্ব (নিশ্চিত)", value: money(stats.confirmed_revenue_bdt), icon: "💰" },
            { label: "লাইভ পণ্য", value: stats.listed_products, icon: "🏷️" },
          ].map(s => (
            <Card key={s.label}>
              <p style={{ margin: 0, fontSize: 22 }}>{s.icon}</p>
              <p style={{ margin: "6px 0 2px", fontSize: 11, color: "#6b8a7a", fontWeight: 600, textTransform: "uppercase", letterSpacing: ".04em" }}>{s.label}</p>
              <p style={{ margin: 0, fontSize: 22, fontWeight: 800, color: s.alert ? "#f59e0b" : "#0d1f16" }}>{s.value}</p>
            </Card>
          ))}
        </div>
      )}

      {!store.is_active && (
        <Notice tone="warn">স্টোর এখন নিষ্ক্রিয়। স্টোর বিল্ডার ট্যাব থেকে "সক্রিয় করুন" বাটন চাপুন।</Notice>
      )}
    </div>
  );
}

// ─── Builder tab ──────────────────────────────────────────────────────────────
function BuilderTab({ store, onRefresh }) {
  const { feedback, setFeedback } = useFeedback();
  const [form, setForm] = useState({
    slug: store?.slug || "",
    display_name: store?.display_name || "",
    tagline: store?.tagline || "",
    theme_color: store?.theme_color || "#0a8752",
    theme_preset: store?.theme_preset || "clean",
    category: store?.category || "",
    area: store?.area || "",
    is_active: store?.is_active || false,
  });
  const [busy, setBusy] = useState(false);
  const [logoPreview, setLogoPreview] = useState(store?.logo_data_url || null);
  const [coverPreview, setCoverPreview] = useState(store?.cover_data_url || null);
  const logoRef = useRef();
  const coverRef = useRef();
  const isNew = !store;

  function readImg(file, setter) {
    const r = new FileReader();
    r.onload = e => setter(e.target.result);
    r.readAsDataURL(file);
  }

  async function save(e) {
    e.preventDefault();
    setBusy(true);
    try {
      const payload = { ...form };
      if (logoPreview !== (store?.logo_data_url || null)) payload.logo_data_url = logoPreview;
      if (coverPreview !== (store?.cover_data_url || null)) payload.cover_data_url = coverPreview;

      if (isNew) {
        await api.createStore(payload);
      } else {
        await api.updateStore(payload);
      }
      setFeedback({ type: "success", message: isNew ? "স্টোর তৈরি হয়েছে!" : "স্টোর আপডেট হয়েছে।" });
      onRefresh();
    } catch (err) {
      setFeedback({ type: "error", message: explain(err, { 409: "এই slug অন্য কেউ ব্যবহার করছে।" }) });
    } finally {
      setBusy(false);
    }
  }

  const set = (k) => (e) => setForm(f => ({ ...f, [k]: e.target.value }));
  const toggle = (k) => () => setForm(f => ({ ...f, [k]: !f[k] }));

  return (
    <div>
      <FeedbackBanner feedback={feedback} />
      <form onSubmit={save} className="ui-form">
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 8 }}>
          <Field label="স্টোরের নাম" required>
            <input value={form.display_name} onChange={set("display_name")} required />
          </Field>
          <Field label="Slug (URL এর অংশ)" required hint={`/store/${form.slug || "your-slug"}`}>
            <input value={form.slug} onChange={set("slug")} required pattern="[a-z0-9][a-z0-9\-]{1,78}[a-z0-9]" />
          </Field>
        </div>
        <Field label="ট্যাগলাইন (ঐচ্ছিক)" hint="এক লাইনে ব্যবসার পরিচয়">
          <input value={form.tagline} onChange={set("tagline")} />
        </Field>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          <Field label="ব্যবসার ধরন" hint="যেমন: pharmacy, grocery, fashion">
            <input value={form.category} onChange={set("category")} />
          </Field>
          <Field label="এলাকা" hint="যেমন: Dhanmondi, Chittagong">
            <input value={form.area} onChange={set("area")} />
          </Field>
        </div>

        {/* Theme */}
        <div style={{ marginBottom: 18 }}>
          <label style={{ fontSize: 13, fontWeight: 600, color: "#4a6358", display: "block", marginBottom: 8 }}>
            Theme Preset
          </label>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            {PRESETS.map(p => (
              <button
                key={p.id}
                type="button"
                onClick={() => setForm(f => ({ ...f, theme_preset: p.id }))}
                style={{
                  border: `2px solid ${form.theme_preset === p.id ? form.theme_color : "#d0e0d8"}`,
                  borderRadius: 10, padding: "10px 16px", background: form.theme_preset === p.id ? "#f0f9f4" : "#fff",
                  cursor: "pointer", textAlign: "left",
                }}
              >
                <div style={{ fontWeight: 700, fontSize: 14 }}>{p.label}</div>
                <div style={{ fontSize: 12, color: "#6b8a7a" }}>{p.desc}</div>
              </button>
            ))}
          </div>
        </div>

        <Field label="Accent Color" hint="বাটন ও হাইলাইটের রং">
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <input type="color" value={form.theme_color} onChange={set("theme_color")} style={{ width: 48, height: 40, border: "none", cursor: "pointer", padding: 2, borderRadius: 6 }} />
            <input value={form.theme_color} onChange={set("theme_color")} style={{ fontFamily: "monospace", width: 100 }} pattern="#[0-9a-fA-F]{6}" />
          </div>
        </Field>

        {/* Logo & Cover */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 18 }}>
          <div>
            <label style={{ fontSize: 13, fontWeight: 600, color: "#4a6358", display: "block", marginBottom: 8 }}>লোগো</label>
            <div
              style={{ border: "2px dashed #d0e0d8", borderRadius: 10, padding: 16, textAlign: "center", cursor: "pointer" }}
              onClick={() => logoRef.current?.click()}
            >
              {logoPreview
                ? <img src={logoPreview} alt="" style={{ width: 80, height: 80, objectFit: "cover", borderRadius: 8 }} />
                : <div style={{ fontSize: 32, color: "#a0b8ad" }}>🖼️</div>
              }
              <p style={{ fontSize: 12, color: "#8aaa97", margin: "6px 0 0" }}>ক্লিক করুন</p>
            </div>
            <input ref={logoRef} type="file" accept="image/*" style={{ display: "none" }} onChange={e => e.target.files[0] && readImg(e.target.files[0], setLogoPreview)} />
            {logoPreview && <button type="button" style={{ background: "none", border: "none", color: "#ef4444", fontSize: 12, cursor: "pointer", marginTop: 4 }} onClick={() => setLogoPreview(null)}>সরিয়ে দিন</button>}
          </div>
          <div>
            <label style={{ fontSize: 13, fontWeight: 600, color: "#4a6358", display: "block", marginBottom: 8 }}>Cover Image</label>
            <div
              style={{ border: "2px dashed #d0e0d8", borderRadius: 10, padding: 16, textAlign: "center", cursor: "pointer" }}
              onClick={() => coverRef.current?.click()}
            >
              {coverPreview
                ? <img src={coverPreview} alt="" style={{ width: "100%", height: 80, objectFit: "cover", borderRadius: 8 }} />
                : <div style={{ fontSize: 32, color: "#a0b8ad" }}>🌅</div>
              }
              <p style={{ fontSize: 12, color: "#8aaa97", margin: "6px 0 0" }}>ক্লিক করুন</p>
            </div>
            <input ref={coverRef} type="file" accept="image/*" style={{ display: "none" }} onChange={e => e.target.files[0] && readImg(e.target.files[0], setCoverPreview)} />
            {coverPreview && <button type="button" style={{ background: "none", border: "none", color: "#ef4444", fontSize: 12, cursor: "pointer", marginTop: 4 }} onClick={() => setCoverPreview(null)}>সরিয়ে দিন</button>}
          </div>
        </div>

        {/* Active toggle */}
        {!isNew && (
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", background: form.is_active ? "#dcfce7" : "#fef3c7", borderRadius: 10, padding: "14px 18px", marginBottom: 18 }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: 14 }}>স্টোর {form.is_active ? "সক্রিয়" : "নিষ্ক্রিয়"}</div>
              <div style={{ fontSize: 12, color: "#6b8a7a" }}>{form.is_active ? "Public URL এ দেখা যাচ্ছে" : "Public এ দেখা যাচ্ছে না"}</div>
            </div>
            <button
              type="button"
              onClick={toggle("is_active")}
              style={{ background: form.is_active ? "#15803d" : "#b45309", color: "#fff", border: "none", borderRadius: 8, padding: "8px 20px", fontWeight: 700, fontSize: 14, cursor: "pointer" }}
            >
              {form.is_active ? "বন্ধ করুন" : "সক্রিয় করুন"}
            </button>
          </div>
        )}

        <Button type="submit" loading={busy}>{isNew ? "স্টোর তৈরি করুন" : "পরিবর্তন সংরক্ষণ"}</Button>
      </form>
    </div>
  );
}

// ─── Products tab ─────────────────────────────────────────────────────────────
function ProductsTab({ orgId }) {
  const { feedback, setFeedback } = useFeedback();
  const [products, setProducts] = useState(null);
  const [saving, setSaving] = useState({});

  useEffect(() => {
    api.getStoreProducts().then(setProducts).catch(() => setProducts([]));
  }, []);

  async function toggle(p) {
    setSaving(s => ({ ...s, [p.id]: true }));
    try {
      await api.updateStoreProduct(p.id, { is_listed: !p.is_listed });
      setProducts(ps => ps.map(x => x.id === p.id ? { ...x, is_listed: !x.is_listed } : x));
    } catch (err) {
      setFeedback({ type: "error", message: explain(err) });
    } finally {
      setSaving(s => ({ ...s, [p.id]: false }));
    }
  }

  async function toggleFeatured(p) {
    setSaving(s => ({ ...s, [p.id + "f"]: true }));
    try {
      await api.updateStoreProduct(p.id, { is_featured: !p.is_featured });
      setProducts(ps => ps.map(x => x.id === p.id ? { ...x, is_featured: !x.is_featured } : x));
    } catch {}
    finally { setSaving(s => ({ ...s, [p.id + "f"]: false })); }
  }

  const listed = products?.filter(p => p.is_listed) || [];
  const unlisted = products?.filter(p => !p.is_listed) || [];

  if (!products) return <p className="muted">লোড হচ্ছে…</p>;

  return (
    <div>
      <FeedbackBanner feedback={feedback} />
      <p className="muted" style={{ marginBottom: 16 }}>
        {listed.length} টি পণ্য অনলাইনে আছে · {unlisted.length} টি লুকানো
      </p>
      <table className="ui-table">
        <thead>
          <tr>
            <th>পণ্য</th>
            <th>মূল দাম</th>
            <th>অনলাইন মূল্য</th>
            <th>অনলাইনে</th>
            <th>ফিচার্ড</th>
          </tr>
        </thead>
        <tbody>
          {products.map(p => (
            <tr key={p.id}>
              <td>
                <div style={{ fontWeight: 600 }}>{p.name}</div>
                <div style={{ fontSize: 12, color: "#8aaa97" }}>{p.sku} · {p.unit}</div>
              </td>
              <td>{money(p.selling_price)}</td>
              <td style={{ fontSize: 13, color: "#6b8a7a" }}>
                {p.online_price_bdt ? money(p.online_price_bdt) : <span style={{ color: "#c0d0c8" }}>—</span>}
              </td>
              <td>
                <button
                  style={{
                    background: p.is_listed ? "#dcfce7" : "#f1f5f4",
                    color: p.is_listed ? "#15803d" : "#6b8a7a",
                    border: "none", borderRadius: 20, padding: "5px 14px",
                    fontSize: 12, fontWeight: 700, cursor: "pointer",
                  }}
                  disabled={saving[p.id]}
                  onClick={() => toggle(p)}
                >
                  {p.is_listed ? "চালু" : "বন্ধ"}
                </button>
              </td>
              <td>
                <button
                  style={{
                    background: p.is_featured ? "#fef3c7" : "#f1f5f4",
                    color: p.is_featured ? "#b45309" : "#6b8a7a",
                    border: "none", borderRadius: 20, padding: "5px 14px",
                    fontSize: 12, fontWeight: 700, cursor: "pointer",
                  }}
                  disabled={saving[p.id + "f"]}
                  onClick={() => toggleFeatured(p)}
                >
                  {p.is_featured ? "⭐" : "—"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── Orders tab ───────────────────────────────────────────────────────────────
function OrdersTab() {
  const [orders, setOrders] = useState(null);
  const [filter, setFilter] = useState("all");

  useEffect(() => {
    api.getStoreOrders().then(setOrders).catch(() => setOrders([]));
  }, []);

  const filtered = orders?.filter(o => filter === "all" || o.status === filter) || [];
  const counts = orders ? Object.groupBy?.(orders, o => o.status) || {} : {};

  return (
    <div>
      <div style={{ display: "flex", gap: 8, marginBottom: 20, flexWrap: "wrap" }}>
        {[
          { id: "all", label: "সব" },
          { id: "placed", label: "নতুন" },
          { id: "confirmed", label: "নিশ্চিত" },
          { id: "dispatched", label: "পাঠানো" },
          { id: "delivered", label: "পৌঁছেছে" },
        ].map(f => (
          <button
            key={f.id}
            onClick={() => setFilter(f.id)}
            style={{
              padding: "7px 16px", borderRadius: 20, border: "1.5px solid",
              borderColor: filter === f.id ? "#0a8752" : "#d0e0d8",
              background: filter === f.id ? "#f0f9f4" : "#fff",
              color: filter === f.id ? "#0a8752" : "#4a6358",
              fontWeight: filter === f.id ? 700 : 500, fontSize: 13, cursor: "pointer",
            }}
          >
            {f.label}
            {f.id !== "all" && orders && (orders.filter(o => o.status === f.id).length > 0) && (
              <span style={{ marginLeft: 6, background: "#0a8752", color: "#fff", borderRadius: 10, padding: "0 6px", fontSize: 11 }}>
                {orders.filter(o => o.status === f.id).length}
              </span>
            )}
          </button>
        ))}
      </div>

      {!orders && <p className="muted">লোড হচ্ছে…</p>}
      {orders && filtered.length === 0 && <p className="muted" style={{ textAlign: "center", padding: "40px 0" }}>কোনো অর্ডার নেই।</p>}

      {filtered.map(o => (
        <Card key={o.id} style={{ marginBottom: 14 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 8, marginBottom: 12 }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: 15 }}>#{o.order_number}</div>
              <div style={{ fontSize: 12, color: "#8aaa97" }}>
                {new Date(o.placed_at).toLocaleDateString("bn-BD", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" })}
              </div>
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              {statusBadge(o.status)}
              <span style={{ fontWeight: 800, fontSize: 16, color: "#0d1f16" }}>{money(o.total)}</span>
            </div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, fontSize: 13, color: "#4a6358", marginBottom: 12 }}>
            <div>👤 <strong>{o.customer_name}</strong></div>
            <div>📞 {o.customer_phone}</div>
            <div style={{ gridColumn: "1 / -1" }}>📍 {o.delivery_address}</div>
          </div>
          <div style={{ fontSize: 13, color: "#6b8a7a" }}>
            {o.items.map((it, i) => (
              <span key={i}>{it.product_name} × {it.quantity}{i < o.items.length - 1 ? ", " : ""}</span>
            ))}
          </div>
          {o.status === "placed" && (
            <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
              <ChangeStatusBtn orderId={o.id} status="confirmed" label="নিশ্চিত করুন ✓" color="#10b981" onDone={() => api.getStoreOrders().then(setOrders)} />
              <ChangeStatusBtn orderId={o.id} status="cancelled" label="বাতিল করুন" color="#ef4444" onDone={() => api.getStoreOrders().then(setOrders)} />
            </div>
          )}
          {o.status === "confirmed" && (
            <div style={{ marginTop: 12 }}>
              <ChangeStatusBtn orderId={o.id} status="dispatched" label="পাঠানো হয়েছে →" color="#6366f1" onDone={() => api.getStoreOrders().then(setOrders)} />
            </div>
          )}
          {o.status === "dispatched" && (
            <div style={{ marginTop: 12 }}>
              <ChangeStatusBtn orderId={o.id} status="delivered" label="ডেলিভারি হয়েছে ✓" color="#10b981" onDone={() => api.getStoreOrders().then(setOrders)} />
            </div>
          )}
        </Card>
      ))}
    </div>
  );
}

function ChangeStatusBtn({ orderId, status, label, color, onDone }) {
  const [busy, setBusy] = useState(false);
  async function go() {
    setBusy(true);
    try {
      await api.changeOrderStatus(orderId, status);
      onDone();
    } catch {}
    finally { setBusy(false); }
  }
  return (
    <button
      onClick={go} disabled={busy}
      style={{ background: color + "18", color, border: `1.5px solid ${color}40`, borderRadius: 8, padding: "7px 16px", fontSize: 13, fontWeight: 700, cursor: "pointer" }}
    >
      {busy ? "…" : label}
    </button>
  );
}

// ─── Settings tab ─────────────────────────────────────────────────────────────
function SettingsTab({ store, onRefresh }) {
  const { feedback, setFeedback } = useFeedback();
  const [form, setForm] = useState({
    show_phone: store?.show_phone ?? false,
    show_exact_address: store?.show_exact_address ?? false,
    show_hours: store?.show_hours ?? true,
    show_price: store?.show_price ?? true,
    show_stock_level: store?.show_stock_level ?? "available_only",
    payment_cod: store?.payment_cod ?? true,
    payment_bkash: store?.payment_bkash ?? false,
    payment_nagad: store?.payment_nagad ?? false,
    min_order_bdt: store?.min_order_bdt ?? "",
    delivery_note: store?.delivery_note ?? "",
  });
  const [busy, setBusy] = useState(false);

  const toggle = (k) => setForm(f => ({ ...f, [k]: !f[k] }));
  const set = (k) => (e) => setForm(f => ({ ...f, [k]: e.target.value }));

  async function save(e) {
    e.preventDefault();
    setBusy(true);
    try {
      await api.updateStore({
        ...form,
        min_order_bdt: form.min_order_bdt ? Number(form.min_order_bdt) : null,
      });
      setFeedback({ type: "success", message: "সেটিংস সংরক্ষিত হয়েছে।" });
      onRefresh();
    } catch (err) {
      setFeedback({ type: "error", message: explain(err) });
    } finally { setBusy(false); }
  }

  if (!store) return <Notice tone="warn">আগে স্টোর তৈরি করুন।</Notice>;

  const ToggleRow = ({ label, hint, field }) => (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 0", borderBottom: "1px solid #f0f5f2" }}>
      <div>
        <div style={{ fontWeight: 600, fontSize: 14 }}>{label}</div>
        {hint && <div style={{ fontSize: 12, color: "#8aaa97" }}>{hint}</div>}
      </div>
      <button
        type="button"
        onClick={() => toggle(field)}
        style={{ width: 48, height: 26, borderRadius: 13, border: "none", background: form[field] ? "#0a8752" : "#d0e0d8", cursor: "pointer", position: "relative", transition: "background .2s" }}
      >
        <span style={{ position: "absolute", top: 3, left: form[field] ? 25 : 3, width: 20, height: 20, borderRadius: "50%", background: "#fff", transition: "left .2s" }} />
      </button>
    </div>
  );

  return (
    <form onSubmit={save}>
      <FeedbackBanner feedback={feedback} />
      <h3 style={{ marginTop: 0, fontSize: 15, fontWeight: 700, color: "#4a6358", textTransform: "uppercase", letterSpacing: ".05em" }}>দৃশ্যমানতা</h3>
      <ToggleRow label="ফোন নম্বর দেখান" hint="Default: না — spam protection" field="show_phone" />
      <ToggleRow label="সঠিক ঠিকানা দেখান" hint="Default: না — শুধু এলাকার নাম দেখায়" field="show_exact_address" />
      <ToggleRow label="ব্যবসার সময় দেখান" field="show_hours" />
      <ToggleRow label="মূল্য দেখান" hint="বন্ধ করলে 'যোগাযোগ করুন' দেখাবে" field="show_price" />

      <div style={{ padding: "12px 0", borderBottom: "1px solid #f0f5f2" }}>
        <label style={{ fontSize: 14, fontWeight: 600, display: "block", marginBottom: 8 }}>স্টক স্তর দেখান</label>
        <div style={{ display: "flex", gap: 8 }}>
          {[
            { v: "hide", l: "লুকান" },
            { v: "available_only", l: "আছে / নেই শুধু" },
            { v: "quantity", l: "পরিমাণও দেখান" },
          ].map(o => (
            <button
              key={o.v} type="button"
              onClick={() => setForm(f => ({ ...f, show_stock_level: o.v }))}
              style={{ padding: "7px 14px", borderRadius: 8, border: "1.5px solid", fontSize: 13, fontWeight: 600, cursor: "pointer",
                borderColor: form.show_stock_level === o.v ? "#0a8752" : "#d0e0d8",
                background: form.show_stock_level === o.v ? "#f0f9f4" : "#fff",
                color: form.show_stock_level === o.v ? "#0a8752" : "#4a6358",
              }}
            >{o.l}</button>
          ))}
        </div>
      </div>

      <h3 style={{ marginTop: 24, fontSize: 15, fontWeight: 700, color: "#4a6358", textTransform: "uppercase", letterSpacing: ".05em" }}>পেমেন্ট</h3>
      <ToggleRow label="Cash on Delivery" hint="ডেলিভারির সময় নগদ পেমেন্ট" field="payment_cod" />
      <ToggleRow label="bKash" hint="Owner নম্বর settings এ যোগ করুন" field="payment_bkash" />
      <ToggleRow label="Nagad" hint="Owner নম্বর settings এ যোগ করুন" field="payment_nagad" />

      <h3 style={{ marginTop: 24, fontSize: 15, fontWeight: 700, color: "#4a6358", textTransform: "uppercase", letterSpacing: ".05em" }}>ডেলিভারি</h3>
      <Field label="সর্বনিম্ন অর্ডার (৳)" hint="খালি রাখলে কোনো সীমা নেই">
        <input type="number" min="0" value={form.min_order_bdt} onChange={set("min_order_bdt")} />
      </Field>
      <Field label="ডেলিভারি নোট" hint="Checkout এ দেখাবে">
        <input value={form.delivery_note} onChange={set("delivery_note")} placeholder="যেমন: শুধু ঢাকায়, ২-৩ দিন সময় লাগে" />
      </Field>

      <div style={{ marginTop: 20 }}>
        <Button type="submit" loading={busy}>সেটিংস সংরক্ষণ</Button>
      </div>
    </form>
  );
}

// ─── Root component ───────────────────────────────────────────────────────────
export default function StoreAdmin() {
  const [tab, setTab] = useState("overview");
  const [store, setStore] = useState(undefined); // undefined=loading, null=not created
  const [stats, setStats] = useState(null);
  const [orgId, setOrgId] = useState("");
  const [error, setError] = useState("");

  async function load() {
    try {
      const data = await api.getStore();
      setStore(data);
      setOrgId(data.organization_id);
    } catch (err) {
      if (err?.status === 404 || err?.response?.status === 404) {
        setStore(null);
      } else {
        setError(explain(err));
      }
    }
    try {
      const s = await api.getStoreStats();
      setStats(s);
    } catch {}
  }

  // Get orgId from auth context for new stores
  useEffect(() => {
    load();
    // Try to get orgId from localStorage fallback
    try { const o = JSON.parse(localStorage.getItem("bsmart_org") || "{}"); if (o.id) setOrgId(o.id); } catch {}
  }, []);

  function refresh() { load(); }

  if (store === undefined) return (
    <div className="page stack">
      <PageHeader title="অনলাইন স্টোর" />
      <p className="muted">লোড হচ্ছে…</p>
    </div>
  );

  return (
    <div className="page stack">
      <PageHeader
        title="অনলাইন স্টোর"
        subtitle="আপনার public storefront পরিচালনা করুন"
        action={store?.is_active && orgId ? (
          <a
            href={`#/store/${orgId}`}
            target="_blank"
            rel="noopener noreferrer"
            style={{ fontSize: 13, color: "#0a8752", fontWeight: 600, textDecoration: "none", display: "flex", alignItems: "center", gap: 6 }}
          >
            <Icon name="globe" size={16} /> স্টোর দেখুন ↗
          </a>
        ) : null}
      />
      {error && <Notice tone="danger">{error}</Notice>}

      {/* Tabs */}
      <div style={{ display: "flex", gap: 2, borderBottom: "2px solid var(--border)", marginBottom: 24, overflowX: "auto" }}>
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            style={{
              padding: "10px 18px", border: "none", background: "none", cursor: "pointer",
              fontSize: 14, fontWeight: tab === t.id ? 700 : 500,
              color: tab === t.id ? "var(--green)" : "var(--muted)",
              borderBottom: `3px solid ${tab === t.id ? "var(--green)" : "transparent"}`,
              marginBottom: -2, whiteSpace: "nowrap",
            }}
          >
            {t.label}
            {t.id === "orders" && stats?.pending_orders > 0 && (
              <span style={{ marginLeft: 6, background: "#f59e0b", color: "#fff", borderRadius: 10, padding: "0 6px", fontSize: 11, fontWeight: 700 }}>
                {stats.pending_orders}
              </span>
            )}
          </button>
        ))}
      </div>

      {tab === "overview" && <OverviewTab store={store} stats={stats} orgId={orgId} />}
      {tab === "builder" && <BuilderTab store={store} onRefresh={refresh} />}
      {tab === "products" && (store ? <ProductsTab orgId={orgId} /> : <Notice tone="warn">আগে স্টোর তৈরি করুন।</Notice>)}
      {tab === "orders" && (store ? <OrdersTab /> : <Notice tone="warn">আগে স্টোর তৈরি করুন।</Notice>)}
      {tab === "settings" && <SettingsTab store={store} onRefresh={refresh} />}
    </div>
  );
}
