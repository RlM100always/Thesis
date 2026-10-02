// StoreAdmin — world-class storefront management
// BUILD MARKER: chunk-start
import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { explain } from "../errors";
import { money } from "../format";
import { Button, Card, Field, Notice, PageHeader } from "../ui/kit";
import { useFeedback, FeedbackBanner } from "../components/FeedbackBanner";

const TABS = [
  { id: "overview",  label: "সারসংক্ষেপ",   icon: "📊" },
  { id: "builder",   label: "স্টোর বিল্ডার", icon: "🏗️" },
  { id: "products",  label: "পণ্য তালিকা",   icon: "📦" },
  { id: "orders",    label: "অর্ডার",         icon: "🛒" },
  { id: "settings",  label: "সেটিংস",         icon: "⚙️" },
];

const PRESETS = [
  { id: "clean",  label: "Clean",   bg: "#ffffff", card: "#f9fafb", accent: "#0a8752", ink: "#0d1f16", desc: "সাদা, মিনিমাল" },
  { id: "bold",   label: "Bold",    bg: "#0d1f16", card: "#1a2e23", accent: "#22c55e", ink: "#f0f9f4", desc: "গাঢ়, ডার্ক" },
  { id: "warm",   label: "Warm",    bg: "#fdf6ed", card: "#fff8f0", accent: "#b45309", ink: "#3d1d00", desc: "ক্রিম, আর্থি" },
  { id: "fresh",  label: "Fresh",   bg: "#f0f9f4", card: "#e8f5ee", accent: "#059669", ink: "#064e3b", desc: "সবুজাভ, হালকা" },
  { id: "purple", label: "Purple",  bg: "#faf5ff", card: "#f3e8ff", accent: "#7c3aed", ink: "#3b0764", desc: "প্রফেশনাল" },
  { id: "ocean",  label: "Ocean",   bg: "#eff6ff", card: "#dbeafe", accent: "#1d4ed8", ink: "#1e3a5f", desc: "নীল, বিশ্বস্ত" },
];

const DAYS = [
  { k: "mon", l: "সোমবার" }, { k: "tue", l: "মঙ্গলবার" }, { k: "wed", l: "বুধবার" },
  { k: "thu", l: "বৃহস্পতিবার" }, { k: "fri", l: "শুক্রবার" }, { k: "sat", l: "শনিবার" }, { k: "sun", l: "রবিবার" },
];

const STATUS = {
  placed:     { label: "নতুন",     color: "#f59e0b", next: [{ s: "confirmed", l: "✓ নিশ্চিত করুন" }, { s: "cancelled", l: "✗ বাতিল" }] },
  confirmed:  { label: "নিশ্চিত",  color: "#3b82f6", next: [{ s: "dispatched", l: "→ পাঠান" }] },
  ready:      { label: "প্রস্তুত", color: "#6366f1", next: [{ s: "dispatched", l: "→ পাঠান" }] },
  dispatched: { label: "পাঠানো",   color: "#8b5cf6", next: [{ s: "delivered",  l: "✓ পৌঁছেছে" }] },
  delivered:  { label: "পৌঁছেছে",  color: "#10b981", next: [] },
  cancelled:  { label: "বাতিল",    color: "#ef4444", next: [] },
};

// ── Micro components ──────────────────────────────────────────────────────────
function Toggle({ on, onChange, size = "md" }) {
  const w = size === "sm" ? 36 : 48, h = size === "sm" ? 20 : 26;
  return (
    <button type="button" onClick={onChange}
      style={{ width: w, height: h, borderRadius: h / 2, border: "none", background: on ? "#0a8752" : "#d0e0d8", cursor: "pointer", position: "relative", transition: "background .2s", flexShrink: 0 }}>
      <span style={{ position: "absolute", top: 3, left: on ? w - h + 3 : 3, width: h - 6, height: h - 6, borderRadius: "50%", background: "#fff", transition: "left .2s" }} />
    </button>
  );
}

function StatusPill({ status }) {
  const s = STATUS[status] || { label: status, color: "#6b7280" };
  return <span style={{ background: s.color + "18", color: s.color, border: `1px solid ${s.color}30`, borderRadius: 6, padding: "3px 10px", fontSize: 12, fontWeight: 700 }}>{s.label}</span>;
}

function Sh({ children }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, margin: "28px 0 14px", paddingBottom: 10, borderBottom: "2px solid #f0f5f2" }}>
      <span style={{ fontSize: 13, fontWeight: 800, color: "#4a6358", textTransform: "uppercase", letterSpacing: ".07em" }}>{children}</span>
    </div>
  );
}

function ImgDrop({ src, onFile, onRemove, aspect = "1/1", placeholder = "📷", hint = "ক্লিক করুন বা ড্র্যাগ করুন" }) {
  const ref = useRef();
  const [drag, setDrag] = useState(false);
  function handleFile(file) {
    if (!file || !file.type.startsWith("image/")) return;
    const r = new FileReader();
    r.onload = e => onFile(e.target.result);
    r.readAsDataURL(file);
  }
  return (
    <div>
      <div onClick={() => ref.current?.click()}
        onDragOver={e => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={e => { e.preventDefault(); setDrag(false); handleFile(e.dataTransfer.files[0]); }}
        style={{ border: `2px dashed ${drag ? "#0a8752" : "#d0e0d8"}`, borderRadius: 12, aspectRatio: aspect, display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer", overflow: "hidden", background: drag ? "#f0f9f4" : "#fafbfa", transition: "all .15s" }}>
        {src
          ? <img src={src} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
          : <div style={{ textAlign: "center", color: "#a0b8ad", pointerEvents: "none" }}>
              <div style={{ fontSize: 32, marginBottom: 6 }}>{placeholder}</div>
              <div style={{ fontSize: 12 }}>{hint}</div>
            </div>
        }
      </div>
      <input ref={ref} type="file" accept="image/*" style={{ display: "none" }} onChange={e => e.target.files[0] && handleFile(e.target.files[0])} />
      {src && <button type="button" onClick={onRemove} style={{ marginTop: 6, background: "none", border: "none", color: "#ef4444", fontSize: 12, cursor: "pointer", padding: 0, fontWeight: 600 }}>× সরান</button>}
    </div>
  );
}

function StatCard({ icon, label, value, sub, color = "#0a8752", onClick }) {
  return (
    <div onClick={onClick}
      style={{ background: "#fff", border: "1px solid #e5ede9", borderRadius: 14, padding: "20px", cursor: onClick ? "pointer" : "default", position: "relative", overflow: "hidden", transition: "box-shadow .15s, transform .15s" }}
      onMouseEnter={e => { if (onClick) { e.currentTarget.style.boxShadow = "0 4px 16px rgba(0,0,0,.08)"; e.currentTarget.style.transform = "translateY(-2px)"; } }}
      onMouseLeave={e => { e.currentTarget.style.boxShadow = ""; e.currentTarget.style.transform = ""; }}>
      <div style={{ position: "absolute", top: 0, left: 0, width: 4, height: "100%", background: color, borderRadius: "12px 0 0 12px" }} />
      <div style={{ paddingLeft: 8 }}>
        <div style={{ fontSize: 26, marginBottom: 8 }}>{icon}</div>
        <div style={{ fontSize: 11, fontWeight: 700, color: "#6b8a7a", textTransform: "uppercase", letterSpacing: ".05em", marginBottom: 4 }}>{label}</div>
        <div style={{ fontSize: 26, fontWeight: 800, color: "#0d1f16", lineHeight: 1 }}>{value}</div>
        {sub && <div style={{ fontSize: 12, color: "#8aaa97", marginTop: 4 }}>{sub}</div>}
      </div>
    </div>
  );
}

// ── Overview tab ──────────────────────────────────────────────────────────────
function OverviewTab({ store, stats, orgId, onTab }) {
  const [copied, setCopied] = useState(false);
  const storeUrl = `${window.location.origin}/#/store/${orgId}`;
  function copy() {
    navigator.clipboard?.writeText(storeUrl).then(() => { setCopied(true); setTimeout(() => setCopied(false), 2000); }).catch(() => {});
  }
  if (!store) return (
    <div style={{ textAlign: "center", padding: "64px 24px" }}>
      <div style={{ width: 96, height: 96, background: "#f0f9f4", borderRadius: 24, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 48, margin: "0 auto 20px" }}>🏪</div>
      <h2 style={{ margin: "0 0 10px", fontSize: 22, fontWeight: 800, color: "#0d1f16" }}>অনলাইন স্টোর চালু করুন</h2>
      <p style={{ color: "#6b8a7a", margin: "0 0 28px", maxWidth: 400, marginInline: "auto", lineHeight: 1.6 }}>আপনার ব্যবসার জন্য একটি সুন্দর অনলাইন স্টোর তৈরি করুন।</p>
      <Button onClick={() => onTab("builder")}>স্টোর বিল্ডার খুলুন →</Button>
    </div>
  );
  return (
    <div style={{ display: "grid", gap: 20 }}>
      <div style={{ background: "linear-gradient(135deg,#0a8752,#065f3c)", borderRadius: 16, padding: "28px", color: "#fff", position: "relative", overflow: "hidden" }}>
        <div style={{ position: "absolute", right: -20, top: -20, width: 160, height: 160, background: "rgba(255,255,255,.06)", borderRadius: "50%" }} />
        <div style={{ display: "flex", gap: 16, alignItems: "center", marginBottom: 18, flexWrap: "wrap" }}>
          {store.logo_data_url
            ? <img src={store.logo_data_url} alt="" style={{ width: 56, height: 56, borderRadius: 12, objectFit: "cover", flexShrink: 0 }} />
            : <div style={{ width: 56, height: 56, borderRadius: 12, background: "rgba(255,255,255,.2)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 24, fontWeight: 800, flexShrink: 0 }}>{store.display_name?.[0]?.toUpperCase()}</div>
          }
          <div style={{ flex: 1 }}>
            <h2 style={{ margin: 0, fontSize: 22, fontWeight: 800 }}>{store.display_name}</h2>
            {store.tagline && <p style={{ margin: "4px 0 0", opacity: .8, fontSize: 14 }}>{store.tagline}</p>}
          </div>
          {store.is_active
            ? <span style={{ background: "#dcfce7", color: "#15803d", borderRadius: 8, padding: "6px 16px", fontWeight: 700, fontSize: 13 }}>🟢 সক্রিয়</span>
            : <span style={{ background: "#fef3c7", color: "#b45309", borderRadius: 8, padding: "6px 16px", fontWeight: 700, fontSize: 13 }}>🟡 নিষ্ক্রিয়</span>
          }
        </div>
        {store.is_active
          ? <div style={{ background: "rgba(255,255,255,.12)", borderRadius: 10, padding: "10px 14px", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 10 }}>
              <span style={{ fontSize: 12.5, fontFamily: "monospace", opacity: .9, wordBreak: "break-all" }}>{storeUrl}</span>
              <div style={{ display: "flex", gap: 8 }}>
                <button onClick={copy} style={{ background: "rgba(255,255,255,.2)", border: "none", color: "#fff", borderRadius: 7, padding: "5px 14px", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>{copied ? "✓ কপি" : "লিংক কপি"}</button>
                <a href={storeUrl} target="_blank" rel="noopener noreferrer" style={{ background: "#fff", color: "#0a8752", borderRadius: 7, padding: "5px 14px", fontSize: 12, fontWeight: 700, textDecoration: "none" }}>খুলুন ↗</a>
              </div>
            </div>
          : <button onClick={() => onTab("builder")} style={{ background: "rgba(255,255,255,.15)", border: "1px solid rgba(255,255,255,.3)", color: "#fff", borderRadius: 9, padding: "9px 18px", fontSize: 13, fontWeight: 600, cursor: "pointer" }}>স্টোর সক্রিয় করুন →</button>
        }
      </div>
      {stats && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(200px,1fr))", gap: 14 }}>
          <StatCard icon="📦" label="মোট অর্ডার" value={stats.total_orders} />
          <StatCard icon="⏳" label="অপেক্ষারত" value={stats.pending_orders} color={stats.pending_orders > 0 ? "#f59e0b" : "#0a8752"} sub={stats.pending_orders > 0 ? "দ্রুত নিশ্চিত করুন" : "সব ঠিক আছে"} onClick={stats.pending_orders > 0 ? () => onTab("orders") : undefined} />
          <StatCard icon="💰" label="নিশ্চিত রাজস্ব" value={money(stats.confirmed_revenue_bdt)} color="#6366f1" />
          <StatCard icon="🏷️" label="লাইভ পণ্য" value={stats.listed_products} color="#06b6d4" onClick={() => onTab("products")} />
        </div>
      )}
      <div style={{ background: "#fff", border: "1px solid #e5ede9", borderRadius: 14, padding: "20px" }}>
        <h4 style={{ margin: "0 0 14px", fontSize: 13, fontWeight: 700, color: "#4a6358", textTransform: "uppercase", letterSpacing: ".05em" }}>সেটআপ চেকলিস্ট</h4>
        {[
          { done: !!store, l: "স্টোর তৈরি করুন", t: "builder" },
          { done: !!store?.logo_data_url, l: "লোগো আপলোড করুন", t: "builder" },
          { done: store?.is_active, l: "স্টোর সক্রিয় করুন", t: "builder" },
          { done: (stats?.listed_products || 0) > 0, l: "কমপক্ষে ১টি পণ্য যোগ করুন", t: "products" },
          { done: store?.payment_cod || store?.payment_bkash || store?.payment_nagad, l: "পেমেন্ট পদ্ধতি চালু করুন", t: "settings" },
        ].map((c, i) => (
          <div key={i} onClick={c.done ? undefined : () => onTab(c.t)}
            style={{ display: "flex", alignItems: "center", gap: 12, padding: "9px 0", borderBottom: i < 4 ? "1px solid #f0f5f2" : "none", cursor: c.done ? "default" : "pointer" }}>
            <span style={{ width: 24, height: 24, borderRadius: "50%", background: c.done ? "#dcfce7" : "#f1f5f4", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14, color: c.done ? "#15803d" : "#8aaa97", flexShrink: 0 }}>{c.done ? "✓" : "○"}</span>
            <span style={{ fontSize: 14, color: c.done ? "#6b8a7a" : "#0d1f16", fontWeight: c.done ? 400 : 600, textDecoration: c.done ? "line-through" : "none" }}>{c.l}</span>
            {!c.done && <span style={{ marginLeft: "auto", fontSize: 12, color: "#0a8752", fontWeight: 600 }}>করুন →</span>}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Builder tab ───────────────────────────────────────────────────────────────
function BuilderTab({ store, onRefresh }) {
  const { feedback, setFeedback } = useFeedback();
  const isNew = !store;
  const [form, setForm] = useState({
    slug: store?.slug || "", display_name: store?.display_name || "", tagline: store?.tagline || "",
    theme_color: store?.theme_color || "#0a8752", theme_preset: store?.theme_preset || "clean",
    category: store?.category || "", area: store?.area || "", is_active: store?.is_active || false,
    meta_title: store?.meta_title || "", meta_desc: store?.meta_desc || "",
  });
  const [logo, setLogo] = useState(store?.logo_data_url || null);
  const [cover, setCover] = useState(store?.cover_data_url || null);
  const [busy, setBusy] = useState(false);
  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }));

  async function save(e) {
    e.preventDefault(); setBusy(true);
    try {
      const payload = { ...form };
      ["meta_title","meta_desc","tagline","category","area"].forEach(k => { if (payload[k] === "") payload[k] = null; });
      if (logo !== (store?.logo_data_url || null)) payload.logo_data_url = logo;
      if (cover !== (store?.cover_data_url || null)) payload.cover_data_url = cover;
      isNew ? await api.createStore(payload) : await api.updateStore(payload);
      setFeedback({ type: "success", message: isNew ? "স্টোর তৈরি হয়েছে!" : "সংরক্ষিত হয়েছে।" });
      onRefresh();
    } catch (err) { setFeedback({ type: "error", message: explain(err, { 409: "এই slug অন্য কেউ ব্যবহার করছে।" }) }); }
    finally { setBusy(false); }
  }

  const preset = PRESETS.find(p => p.id === form.theme_preset) || PRESETS[0];

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr minmax(300px,380px)", gap: 24, alignItems: "start" }}>
      <div>
        <FeedbackBanner feedback={feedback} />
        <form onSubmit={save} className="ui-form">
          <Sh>🏪 পরিচয়</Sh>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
            <Field label="স্টোরের নাম" required><input value={form.display_name} onChange={set("display_name")} required placeholder="মেডি ফার্মা" /></Field>
            <Field label="Slug (URL)" required hint={`/store/${form.slug || "slug"}`}><input value={form.slug} onChange={set("slug")} required pattern="[a-z0-9][a-z0-9\-]{1,78}[a-z0-9]" placeholder="medi-pharma" /></Field>
          </div>
          <Field label="ট্যাগলাইন"><input value={form.tagline} onChange={set("tagline")} placeholder="দ্রুত ডেলিভারি, বিশ্বস্ত সেবা" /></Field>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
            <Field label="ক্যাটাগরি"><input value={form.category} onChange={set("category")} placeholder="Pharmacy" /></Field>
            <Field label="এলাকা"><input value={form.area} onChange={set("area")} placeholder="Dhanmondi, Dhaka" /></Field>
          </div>
          <Sh>🎨 থিম</Sh>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 10, marginBottom: 18 }}>
            {PRESETS.map(p => (
              <button key={p.id} type="button" onClick={() => setForm(f => ({ ...f, theme_preset: p.id, theme_color: p.accent }))}
                style={{ border: `2px solid ${form.theme_preset === p.id ? p.accent : "#e5ede9"}`, borderRadius: 12, padding: "12px 8px", cursor: "pointer", textAlign: "center", background: p.bg, transition: "all .15s", transform: form.theme_preset === p.id ? "scale(1.04)" : "scale(1)" }}>
                <div style={{ width: 28, height: 28, borderRadius: "50%", background: p.accent, margin: "0 auto 8px" }} />
                <div style={{ fontWeight: 700, fontSize: 13, color: p.ink }}>{p.label}</div>
                <div style={{ fontSize: 11, color: p.ink + "99", marginTop: 2 }}>{p.desc}</div>
              </button>
            ))}
          </div>
          <Field label="Accent Color">
            <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
              <input type="color" value={form.theme_color} onChange={set("theme_color")} style={{ width: 52, height: 44, border: "none", cursor: "pointer", padding: 2, borderRadius: 8 }} />
              <input value={form.theme_color} onChange={set("theme_color")} style={{ fontFamily: "monospace", width: 110 }} />
              <div style={{ width: 44, height: 44, borderRadius: 10, background: form.theme_color, border: "1px solid rgba(0,0,0,.1)" }} />
            </div>
          </Field>
          <Sh>🖼️ ছবি</Sh>
          <div style={{ display: "grid", gridTemplateColumns: "150px 1fr", gap: 16, marginBottom: 20 }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: "#4a6358", marginBottom: 8 }}>লোগো (1:1)</div>
              <ImgDrop src={logo} onFile={setLogo} onRemove={() => setLogo(null)} placeholder="🏪" hint="লোগো" />
            </div>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: "#4a6358", marginBottom: 8 }}>কভার ব্যানার (3:1)</div>
              <ImgDrop src={cover} onFile={setCover} onRemove={() => setCover(null)} aspect="3/1" placeholder="🌅" hint="কভার ব্যানার" />
            </div>
          </div>
          <Sh>🔍 SEO</Sh>
          <Field label="Page Title">
            <div style={{ position: "relative" }}>
              <input value={form.meta_title} onChange={set("meta_title")} maxLength={160} placeholder={form.display_name || "স্টোরের নাম"} />
              <span style={{ position: "absolute", right: 10, top: "50%", transform: "translateY(-50%)", fontSize: 11, color: form.meta_title.length > 60 ? "#f59e0b" : "#8aaa97" }}>{form.meta_title.length}/160</span>
            </div>
          </Field>
          <Field label="Meta Description">
            <textarea value={form.meta_desc} onChange={set("meta_desc")} maxLength={320} rows={2} style={{ resize: "vertical" }} placeholder={form.tagline || "আপনার ব্যবসার পরিচয়"} />
          </Field>
          {!isNew && (
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", background: form.is_active ? "linear-gradient(135deg,#f0fdf4,#dcfce7)" : "linear-gradient(135deg,#fffbeb,#fef3c7)", borderRadius: 14, padding: "18px 20px", margin: "24px 0 20px" }}>
              <div>
                <div style={{ fontWeight: 700, fontSize: 16 }}>{form.is_active ? "🟢 স্টোর সক্রিয়" : "🟡 স্টোর নিষ্ক্রিয়"}</div>
                <div style={{ fontSize: 13, color: "#6b8a7a", marginTop: 3 }}>{form.is_active ? "যে কেউ ভিজিট করে অর্ডার করতে পারছে" : "Public এ দেখা যাচ্ছে না"}</div>
              </div>
              <button type="button" onClick={() => setForm(f => ({ ...f, is_active: !f.is_active }))}
                style={{ background: form.is_active ? "#ef4444" : "#0a8752", color: "#fff", border: "none", borderRadius: 10, padding: "10px 24px", fontWeight: 700, fontSize: 14, cursor: "pointer" }}>
                {form.is_active ? "বন্ধ করুন" : "সক্রিয় করুন"}
              </button>
            </div>
          )}
          <Button type="submit" loading={busy} style={{ width: "100%", padding: "13px" }}>{isNew ? "✓ স্টোর তৈরি করুন" : "✓ পরিবর্তন সংরক্ষণ"}</Button>
        </form>
      </div>
      {/* Live preview */}
      <div style={{ position: "sticky", top: 80 }}>
        <div style={{ background: "#fff", border: "1px solid #e5ede9", borderRadius: 16, overflow: "hidden", boxShadow: "0 4px 24px rgba(0,0,0,.06)" }}>
          <div style={{ padding: "10px 14px", borderBottom: "1px solid #f0f5f2", display: "flex", gap: 6, alignItems: "center" }}>
            <div style={{ display: "flex", gap: 5 }}>{["#f87171","#fbbf24","#34d399"].map(c => <div key={c} style={{ width: 9, height: 9, borderRadius: "50%", background: c }} />)}</div>
            <div style={{ flex: 1, background: "#f1f5f4", borderRadius: 6, height: 20, fontSize: 10, display: "flex", alignItems: "center", paddingLeft: 8, color: "#8aaa97" }}>bsmart.app/store/{form.slug || "your-store"}</div>
          </div>
          <div style={{ background: preset.bg }}>
            <div style={{ background: "rgba(255,255,255,.95)", borderBottom: `1px solid ${preset.accent}20`, padding: "8px 12px", display: "flex", alignItems: "center", gap: 8 }}>
              <div style={{ width: 26, height: 26, borderRadius: 6, background: logo ? "transparent" : preset.accent + "20", overflow: "hidden", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                {logo ? <img src={logo} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }} /> : <span style={{ fontSize: 13, fontWeight: 800, color: preset.accent }}>{form.display_name?.[0]?.toUpperCase() || "S"}</span>}
              </div>
              <span style={{ fontWeight: 700, fontSize: 12, color: preset.ink, flex: 1 }}>{form.display_name || "স্টোরের নাম"}</span>
              <div style={{ background: preset.accent, color: "#fff", borderRadius: 12, padding: "2px 8px", fontSize: 10, fontWeight: 600 }}>🛒</div>
            </div>
            {cover && <div style={{ width: "100%", height: 80, overflow: "hidden" }}><img src={cover} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }} /></div>}
            <div style={{ padding: "14px 12px 6px", textAlign: "center" }}>
              <div style={{ fontSize: 15, fontWeight: 800, color: preset.ink }}>{form.display_name || "স্টোরের নাম"}</div>
              {form.tagline && <div style={{ fontSize: 11, color: preset.ink + "80", marginTop: 3 }}>{form.tagline}</div>}
              {form.category && <span style={{ display: "inline-block", background: preset.accent + "18", color: preset.accent, borderRadius: 12, padding: "2px 9px", fontSize: 10, marginTop: 5 }}>{form.category}</span>}
            </div>
            <div style={{ padding: "8px 12px 14px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
              {[1,2].map(n => (
                <div key={n} style={{ background: preset.card, borderRadius: 8, overflow: "hidden", border: `1px solid ${preset.accent}15` }}>
                  <div style={{ height: 56, background: preset.accent + "12", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20 }}>💊</div>
                  <div style={{ padding: "7px 8px" }}>
                    <div style={{ fontSize: 11, fontWeight: 600, color: preset.ink }}>পণ্যের নাম</div>
                    <div style={{ fontSize: 12, fontWeight: 700, color: preset.accent, marginTop: 2 }}>৳ ১৫০</div>
                    <div style={{ background: preset.accent, color: "#fff", borderRadius: 5, padding: "3px", fontSize: 10, fontWeight: 600, textAlign: "center", marginTop: 5 }}>+ কার্টে</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
        <div style={{ marginTop: 10, fontSize: 12, color: "#8aaa97", textAlign: "center" }}>Live preview — পরিবর্তন করলে এখানে দেখাবে</div>
      </div>
    </div>
  );
}

// ── Product edit drawer ────────────────────────────────────────────────────────
function ProductEditDrawer({ product, onSave, onClose }) {
  const [form, setForm] = useState({
    online_price_bdt: product.online_price_bdt ?? "",
    description_long: product.description_long ?? "",
    tags: product.tags ?? "",
    max_order_qty: product.max_order_qty ?? "",
    sort_order: product.sort_order ?? 0,
    is_listed: product.is_listed ?? false,
    is_featured: product.is_featured ?? false,
  });
  const [img, setImg] = useState(product.image_data_url || null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }));
  const tags = (form.tags || "").split(",").map(t => t.trim()).filter(Boolean);
  const discountPct = form.online_price_bdt && Number(form.online_price_bdt) < product.selling_price
    ? Math.round((1 - Number(form.online_price_bdt) / product.selling_price) * 100) : 0;

  async function save() {
    setBusy(true); setError("");
    try {
      const payload = {
        is_listed: form.is_listed, is_featured: form.is_featured,
        sort_order: Number(form.sort_order) || 0,
        online_price_bdt: form.online_price_bdt !== "" ? Number(form.online_price_bdt) : null,
        description_long: form.description_long || null,
        tags: form.tags || null,
        max_order_qty: form.max_order_qty !== "" ? Number(form.max_order_qty) : null,
      };
      if (img !== (product.image_data_url || null)) payload.image_data_url = img;
      await api.updateStoreProduct(product.id, payload);
      onSave();
    } catch (err) { setError(explain(err)); }
    finally { setBusy(false); }
  }

  return (
    <>
      <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.45)", zIndex: 90 }} onClick={onClose} />
      <div style={{ position: "fixed", right: 0, top: 0, bottom: 0, width: "min(520px,100vw)", background: "#fff", zIndex: 91, display: "flex", flexDirection: "column", boxShadow: "-12px 0 48px rgba(0,0,0,.15)" }}>
        <div style={{ padding: "20px 24px 16px", borderBottom: "1px solid #e5ede9", display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <h3 style={{ margin: "0 0 4px", fontSize: 17, fontWeight: 800 }}>{product.name}</h3>
            <div style={{ fontSize: 12.5, color: "#8aaa97" }}>{product.sku} · মূল দাম: <strong style={{ color: "#0d1f16" }}>{money(product.selling_price)}</strong></div>
          </div>
          <button onClick={onClose} style={{ background: "#f1f5f4", border: "none", borderRadius: "50%", width: 34, height: 34, fontSize: 18, cursor: "pointer", color: "#6b7280", display: "flex", alignItems: "center", justifyContent: "center" }}>✕</button>
        </div>
        <div style={{ flex: 1, overflowY: "auto", padding: "20px 24px" }}>
          {error && <div style={{ background: "#fef2f2", border: "1px solid #fca5a5", borderRadius: 8, padding: "10px 14px", fontSize: 13, color: "#991b1b", marginBottom: 14 }}>{error}</div>}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 22 }}>
            {[
              { field: "is_listed", icon: form.is_listed ? "✅" : "⬜", label: "স্টোরে দেখান", sub: form.is_listed ? "পাবলিক পেজে দৃশ্যমান" : "লুকানো", color: "#0a8752" },
              { field: "is_featured", icon: form.is_featured ? "⭐" : "☆", label: "ফিচার্ড", sub: form.is_featured ? "হোমে হাইলাইট" : "সাধারণ তালিকায়", color: "#b45309" },
            ].map(o => (
              <button key={o.field} type="button" onClick={() => setForm(f => ({ ...f, [o.field]: !f[o.field] }))}
                style={{ padding: "14px", borderRadius: 12, border: `2px solid ${form[o.field] ? o.color : "#e5ede9"}`, background: form[o.field] ? o.color + "10" : "#fafafa", cursor: "pointer", textAlign: "center", transition: "all .15s" }}>
                <div style={{ fontSize: 28, marginBottom: 6 }}>{o.icon}</div>
                <div style={{ fontSize: 14, fontWeight: 700, color: form[o.field] ? o.color : "#6b7280" }}>{o.label}</div>
                <div style={{ fontSize: 11, color: "#8aaa97", marginTop: 2 }}>{o.sub}</div>
              </button>
            ))}
          </div>
          <div style={{ marginBottom: 20 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: "#4a6358", marginBottom: 8 }}>পণ্যের ছবি</div>
            <div style={{ display: "flex", gap: 14, alignItems: "flex-start" }}>
              <div style={{ width: 130, flexShrink: 0 }}><ImgDrop src={img} onFile={setImg} onRemove={() => setImg(null)} placeholder="💊" hint="ছবি আপলোড" /></div>
              <div style={{ fontSize: 12.5, color: "#6b8a7a", lineHeight: 1.7, paddingTop: 6 }}>
                <p style={{ margin: "0 0 4px" }}>✓ স্কয়ার ছবি (1:1) সবচেয়ে ভালো</p>
                <p style={{ margin: "0 0 4px" }}>✓ পণ্যটি স্পষ্ট দেখা যাওয়া চাই</p>
                <p style={{ margin: 0 }}>✓ সর্বোচ্চ আকার: 2MB</p>
              </div>
            </div>
          </div>
          <div style={{ marginBottom: 18 }}>
            <label style={{ fontSize: 13, fontWeight: 700, color: "#4a6358", display: "block", marginBottom: 6 }}>অনলাইন মূল্য (৳)</label>
            <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
              <input type="number" min="0" step="0.01" value={form.online_price_bdt} onChange={set("online_price_bdt")} placeholder={String(product.selling_price)}
                style={{ flex: 1, padding: "11px 14px", border: "1.5px solid #d0e0d8", borderRadius: 9, fontSize: 15, fontWeight: 600, outline: "none" }} />
              {discountPct > 0 && <span style={{ background: "#dcfce7", color: "#15803d", borderRadius: 7, padding: "5px 10px", fontSize: 12, fontWeight: 700, whiteSpace: "nowrap" }}>↓ {discountPct}% ছাড়</span>}
            </div>
          </div>
          <div style={{ marginBottom: 18 }}>
            <label style={{ fontSize: 13, fontWeight: 700, color: "#4a6358", display: "block", marginBottom: 6 }}>পণ্যের বিবরণ</label>
            <textarea value={form.description_long} onChange={set("description_long")} rows={4}
              placeholder="ব্যবহারের নিয়ম, উপাদান, ডোজ, সতর্কতা…"
              style={{ width: "100%", padding: "11px 14px", border: "1.5px solid #d0e0d8", borderRadius: 9, fontSize: 14, outline: "none", resize: "vertical", lineHeight: 1.6, boxSizing: "border-box" }} />
          </div>
          <div style={{ marginBottom: 18 }}>
            <label style={{ fontSize: 13, fontWeight: 700, color: "#4a6358", display: "block", marginBottom: 6 }}>ট্যাগ <span style={{ fontWeight: 400, color: "#8aaa97" }}>— কমা দিয়ে আলাদা করুন</span></label>
            <input value={form.tags} onChange={set("tags")} placeholder="antibiotic, fever, children, 500mg"
              style={{ width: "100%", padding: "11px 14px", border: "1.5px solid #d0e0d8", borderRadius: 9, fontSize: 14, outline: "none" }} />
            {tags.length > 0 && (
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
                {tags.map(t => <span key={t} style={{ background: "#f0f9f4", color: "#0a8752", border: "1px solid #d0f0e0", borderRadius: 6, padding: "3px 10px", fontSize: 12 }}>{t}</span>)}
              </div>
            )}
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
            <div>
              <label style={{ fontSize: 13, fontWeight: 700, color: "#4a6358", display: "block", marginBottom: 6 }}>সর্বোচ্চ অর্ডার</label>
              <input type="number" min="1" value={form.max_order_qty} onChange={set("max_order_qty")} placeholder="সীমা নেই"
                style={{ width: "100%", padding: "10px 12px", border: "1.5px solid #d0e0d8", borderRadius: 8, fontSize: 14, outline: "none" }} />
            </div>
            <div>
              <label style={{ fontSize: 13, fontWeight: 700, color: "#4a6358", display: "block", marginBottom: 6 }}>ক্রম</label>
              <input type="number" value={form.sort_order} onChange={set("sort_order")}
                style={{ width: "100%", padding: "10px 12px", border: "1.5px solid #d0e0d8", borderRadius: 8, fontSize: 14, outline: "none" }} />
            </div>
          </div>
        </div>
        <div style={{ padding: "16px 24px", borderTop: "1px solid #e5ede9", display: "flex", gap: 10 }}>
          <button onClick={onClose} style={{ flex: 1, padding: "12px", borderRadius: 10, border: "1.5px solid #d0e0d8", background: "#fff", fontSize: 14, fontWeight: 600, cursor: "pointer", color: "#4a6358" }}>বাতিল</button>
          <button onClick={save} disabled={busy} style={{ flex: 2, padding: "12px", borderRadius: 10, border: "none", background: "#0a8752", color: "#fff", fontSize: 14, fontWeight: 700, cursor: "pointer", opacity: busy ? .7 : 1 }}>
            {busy ? "সংরক্ষণ হচ্ছে…" : "✓ সংরক্ষণ করুন"}
          </button>
        </div>
      </div>
    </>
  );
}

// ── Products tab ───────────────────────────────────────────────────────────────
function ProductsTab() {
  const { feedback, setFeedback } = useFeedback();
  const [products, setProducts] = useState(null);
  const [edit, setEdit] = useState(null);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [busyAll, setBusyAll] = useState(false);

  async function load() { try { setProducts(await api.getStoreProducts()); } catch { setProducts([]); } }
  useEffect(() => { load(); }, []);

  async function quickToggle(p, field) {
    try {
      await api.updateStoreProduct(p.id, { [field]: !p[field] });
      setProducts(ps => ps.map(x => x.id === p.id ? { ...x, [field]: !x[field] } : x));
    } catch (err) { setFeedback({ type: "error", message: explain(err) }); }
  }

  async function bulkList(val) {
    setBusyAll(true);
    try {
      await Promise.all(products.map(p => api.updateStoreProduct(p.id, { is_listed: val })));
      setProducts(ps => ps.map(p => ({ ...p, is_listed: val })));
      setFeedback({ type: "success", message: val ? "সব পণ্য চালু।" : "সব পণ্য বন্ধ।" });
    } catch (err) { setFeedback({ type: "error", message: explain(err) }); }
    finally { setBusyAll(false); }
  }

  if (!products) return <div style={{ padding: "40px", textAlign: "center", color: "#8aaa97" }}>লোড হচ্ছে…</div>;
  if (!products.length) return <Notice tone="warn">কোনো পণ্য নেই। প্রথমে পণ্য যোগ করুন।</Notice>;

  const listed = products.filter(p => p.is_listed).length;
  const displayed = products.filter(p => {
    const ms = !search || p.name.toLowerCase().includes(search.toLowerCase()) || (p.sku || "").toLowerCase().includes(search.toLowerCase());
    const mf = filter === "all" || (filter === "on" ? p.is_listed : filter === "off" ? !p.is_listed : filter === "featured" && p.is_featured);
    return ms && mf;
  });

  return (
    <div>
      <FeedbackBanner feedback={feedback} />
      {edit && <ProductEditDrawer product={edit} onSave={() => { setEdit(null); load(); setFeedback({ type: "success", message: "আপডেট হয়েছে।" }); }} onClose={() => setEdit(null)} />}
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 16, alignItems: "center" }}>
        <div style={{ flex: 1, position: "relative", minWidth: 180 }}>
          <span style={{ position: "absolute", left: 11, top: "50%", transform: "translateY(-50%)", fontSize: 14, color: "#8aaa97" }}>🔍</span>
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="পণ্য খুঁজুন…"
            style={{ width: "100%", padding: "9px 12px 9px 34px", border: "1.5px solid #d0e0d8", borderRadius: 9, fontSize: 13, outline: "none", boxSizing: "border-box" }} />
        </div>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {[{v:"all",l:`সব (${products.length})`},{v:"on",l:`চালু (${listed})`},{v:"off",l:`বন্ধ (${products.length-listed})`},{v:"featured",l:"⭐ ফিচার্ড"}].map(o => (
            <button key={o.v} onClick={() => setFilter(o.v)}
              style={{ padding: "7px 12px", borderRadius: 8, border: "1.5px solid", fontSize: 12, fontWeight: 600, cursor: "pointer", borderColor: filter===o.v?"#0a8752":"#d0e0d8", background: filter===o.v?"#f0f9f4":"#fff", color: filter===o.v?"#0a8752":"#6b7280" }}>
              {o.l}
            </button>
          ))}
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          <button disabled={busyAll} onClick={() => bulkList(true)} style={{ padding: "7px 12px", borderRadius: 8, border: "1px solid #0a875240", background: "#0a875210", color: "#0a8752", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>সব চালু</button>
          <button disabled={busyAll} onClick={() => bulkList(false)} style={{ padding: "7px 12px", borderRadius: 8, border: "1px solid #ef444440", background: "#ef444410", color: "#ef4444", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>সব বন্ধ</button>
        </div>
      </div>
      <div style={{ fontSize: 12, color: "#8aaa97", marginBottom: 12, display: "flex", gap: 12 }}>
        <span>{displayed.length} টি দেখাচ্ছে</span>·
        <span style={{ color: "#0a8752", fontWeight: 600 }}>{listed} টি পাবলিক</span>·
        <span style={{ color: "#f59e0b", fontWeight: 600 }}>{products.filter(p=>p.is_featured).length} টি ফিচার্ড</span>
      </div>
      <div style={{ display: "grid", gap: 8 }}>
        {displayed.map(p => (
          <div key={p.id} style={{ display: "grid", gridTemplateColumns: "52px 1fr auto auto auto", gap: 14, alignItems: "center", background: "#fff", border: `1.5px solid ${p.is_listed?"#e5ede9":"#f0f0f0"}`, borderRadius: 12, padding: "12px 16px", opacity: p.is_listed?1:0.6, transition: "opacity .2s" }}>
            <div style={{ width: 52, height: 52, borderRadius: 10, background: "#f0f9f4", overflow: "hidden", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 22, flexShrink: 0 }}>
              {p.image_data_url ? <img src={p.image_data_url} alt="" style={{ width:"100%",height:"100%",objectFit:"cover" }} /> : "💊"}
            </div>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontWeight: 700, fontSize: 14, color: "#0d1f16" }}>{p.name}{p.is_featured && " ⭐"}</div>
              <div style={{ fontSize: 12, color: "#8aaa97", marginTop: 2 }}>
                {p.sku} · <strong style={{ color: "#0d1f16" }}>{money(p.selling_price)}</strong>
                {p.online_price_bdt && <span style={{ color: "#0a8752", fontWeight: 600 }}> → {money(p.online_price_bdt)}</span>}
              </div>
              {p.tags && (
                <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginTop: 4 }}>
                  {p.tags.split(",").filter(Boolean).slice(0,4).map(t => <span key={t} style={{ background: "#f0f9f4", color: "#0a8752", border: "1px solid #d0f0e0", borderRadius: 5, padding: "1px 7px", fontSize: 11 }}>{t.trim()}</span>)}
                </div>
              )}
            </div>
            <button onClick={() => quickToggle(p,"is_featured")} style={{ background: p.is_featured?"#fffbeb":"#f8f9fa", border: `1px solid ${p.is_featured?"#f59e0b40":"#e0e0e0"}`, borderRadius: 8, padding: "7px 10px", cursor: "pointer", fontSize: 18 }}>
              {p.is_featured ? "⭐" : "☆"}
            </button>
            <Toggle on={p.is_listed} onChange={() => quickToggle(p,"is_listed")} />
            <button onClick={() => setEdit(p)}
              style={{ padding: "8px 16px", borderRadius: 9, border: "1.5px solid #d0e0d8", background: "#fff", fontSize: 13, fontWeight: 600, color: "#0a8752", cursor: "pointer", whiteSpace: "nowrap" }}>
              সম্পাদনা
            </button>
          </div>
        ))}
        {displayed.length === 0 && <div style={{ textAlign: "center", padding: "40px", color: "#8aaa97" }}>কোনো পণ্য পাওয়া যায়নি।</div>}
      </div>
    </div>
  );
}

// ── Orders tab ─────────────────────────────────────────────────────────────────
function ChangeStatusBtn({ orderId, status, label, color, onDone }) {
  const [busy, setBusy] = useState(false);
  async function go() { setBusy(true); try { await api.changeOrderStatus(orderId, status); onDone(); } catch {} finally { setBusy(false); } }
  return <button onClick={go} disabled={busy} style={{ background: color + "15", color, border: `1.5px solid ${color}40`, borderRadius: 9, padding: "9px 18px", fontSize: 13, fontWeight: 700, cursor: "pointer", opacity: busy ? .6 : 1 }}>{busy ? "…" : label}</button>;
}

function OrdersTab() {
  const [orders, setOrders] = useState(null);
  const [filter, setFilter] = useState("all");
  const [expanded, setExpanded] = useState(null);
  const [search, setSearch] = useState("");

  async function load() { try { setOrders(await api.getStoreOrders()); } catch { setOrders([]); } }
  useEffect(() => { load(); }, []);

  const counts = (orders || []).reduce((a, o) => { a[o.status] = (a[o.status] || 0) + 1; return a; }, {});
  const revenue = (orders || []).filter(o => ["confirmed","dispatched","delivered"].includes(o.status)).reduce((s, o) => s + o.total, 0);
  const displayed = (orders || []).filter(o => {
    const mf = filter === "all" || o.status === filter;
    const ms = !search || (o.customer_name || "").toLowerCase().includes(search.toLowerCase()) || (o.order_number || "").toLowerCase().includes(search.toLowerCase()) || (o.customer_phone || "").includes(search);
    return mf && ms;
  });

  return (
    <div>
      {orders && orders.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(150px,1fr))", gap: 10, marginBottom: 20 }}>
          {[{l:"মোট অর্ডার",v:orders.length,c:"#6366f1"},{l:"নতুন",v:counts.placed||0,c:"#f59e0b"},{l:"সক্রিয়",v:(counts.confirmed||0)+(counts.dispatched||0),c:"#3b82f6"},{l:"রাজস্ব",v:money(revenue),c:"#0a8752"}].map(s => (
            <div key={s.l} style={{ background: "#fff", border: "1px solid #e5ede9", borderRadius: 10, padding: "14px 16px" }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: "#6b8a7a", textTransform: "uppercase", letterSpacing: ".04em" }}>{s.l}</div>
              <div style={{ fontSize: 22, fontWeight: 800, color: s.c, marginTop: 4 }}>{s.v}</div>
            </div>
          ))}
        </div>
      )}
      <div style={{ position: "relative", marginBottom: 12 }}>
        <span style={{ position: "absolute", left: 11, top: "50%", transform: "translateY(-50%)", fontSize: 14, color: "#8aaa97" }}>🔍</span>
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="অর্ডার নম্বর, নাম বা ফোন…"
          style={{ width: "100%", padding: "10px 12px 10px 34px", border: "1.5px solid #d0e0d8", borderRadius: 9, fontSize: 13, outline: "none", boxSizing: "border-box" }} />
      </div>
      <div style={{ display: "flex", gap: 6, marginBottom: 18, flexWrap: "wrap" }}>
        {[{id:"all",label:"সব"},{id:"placed",label:"নতুন"},{id:"confirmed",label:"নিশ্চিত"},{id:"dispatched",label:"পাঠানো"},{id:"delivered",label:"পৌঁছেছে"},{id:"cancelled",label:"বাতিল"}].map(f => {
          const cnt = f.id === "all" ? orders?.length : counts[f.id];
          const s = STATUS[f.id];
          return (
            <button key={f.id} onClick={() => setFilter(f.id)}
              style={{ padding: "7px 14px", borderRadius: 20, border: "1.5px solid", fontSize: 13, fontWeight: filter===f.id?700:500, cursor: "pointer", borderColor: filter===f.id?(s?.color||"#0a8752"):"#d0e0d8", background: filter===f.id?((s?.color||"#0a8752")+"12"):"#fff", color: filter===f.id?(s?.color||"#0a8752"):"#4a6358", display: "flex", alignItems: "center", gap: 6 }}>
              {f.label}
              {cnt > 0 && <span style={{ background: filter===f.id?(s?.color||"#0a8752"):"#94a3b8", color: "#fff", borderRadius: 10, padding: "0 6px", fontSize: 11, fontWeight: 700 }}>{cnt}</span>}
            </button>
          );
        })}
      </div>
      {!orders && <div style={{ textAlign: "center", padding: "40px", color: "#8aaa97" }}>লোড হচ্ছে…</div>}
      {orders && displayed.length === 0 && (
        <div style={{ textAlign: "center", padding: "56px 20px", color: "#8aaa97" }}>
          <div style={{ fontSize: 44, marginBottom: 14 }}>📭</div>
          <div style={{ fontSize: 15, fontWeight: 600, color: "#4a6358" }}>কোনো অর্ডার নেই</div>
        </div>
      )}
      <div style={{ display: "grid", gap: 10 }}>
        {displayed.map(o => {
          const isExp = expanded === o.id;
          const nexts = STATUS[o.status]?.next || [];
          return (
            <div key={o.id} style={{ background: "#fff", border: "1.5px solid #e5ede9", borderRadius: 14, overflow: "hidden" }}>
              <div onClick={() => setExpanded(e => e === o.id ? null : o.id)}
                style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "14px 18px", cursor: "pointer", flexWrap: "wrap", gap: 10 }}>
                <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
                  <div style={{ fontWeight: 800, fontSize: 15 }}>#{o.order_number}</div>
                  <StatusPill status={o.status} />
                  <div style={{ fontSize: 13, color: "#4a6358" }}><strong>{o.customer_name}</strong> · {o.customer_phone}</div>
                </div>
                <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontWeight: 800, fontSize: 17 }}>{money(o.total)}</div>
                    <div style={{ fontSize: 11, color: "#8aaa97" }}>{new Date(o.placed_at).toLocaleDateString("bn-BD",{day:"numeric",month:"short"})} · {o.items?.length || 0} পণ্য</div>
                  </div>
                  <span style={{ fontSize: 18, color: "#8aaa97", transition: "transform .2s", display: "inline-block", transform: isExp ? "rotate(180deg)" : "rotate(0)" }}>⌄</span>
                </div>
              </div>
              {isExp && (
                <div style={{ borderTop: "1px solid #f0f5f2", padding: "16px 18px", background: "#fafbfa" }}>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 14 }}>
                    <div style={{ background: "#fff", borderRadius: 10, padding: "14px", border: "1px solid #e5ede9" }}>
                      <div style={{ fontSize: 12, fontWeight: 700, color: "#4a6358", textTransform: "uppercase", letterSpacing: ".04em", marginBottom: 8 }}>📍 ডেলিভারি ঠিকানা</div>
                      <div style={{ fontSize: 13.5, color: "#0d1f16", lineHeight: 1.6, whiteSpace: "pre-wrap" }}>{o.delivery_address}</div>
                    </div>
                    <div style={{ background: "#fff", borderRadius: 10, padding: "14px", border: "1px solid #e5ede9" }}>
                      <div style={{ fontSize: 12, fontWeight: 700, color: "#4a6358", textTransform: "uppercase", letterSpacing: ".04em", marginBottom: 8 }}>📦 পণ্য</div>
                      {(o.items || []).map((it, i) => (
                        <div key={i} style={{ display: "flex", justifyContent: "space-between", fontSize: 13, padding: "4px 0", borderBottom: i < (o.items.length - 1) ? "1px solid #f0f5f2" : "none" }}>
                          <span>{it.product_name} <span style={{ color:"#8aaa97" }}>×{it.quantity}</span></span>
                          <span style={{ fontWeight: 600 }}>{money(it.line_total)}</span>
                        </div>
                      ))}
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 14, fontWeight: 800, paddingTop: 8, marginTop: 4, borderTop: "1.5px solid #e5ede9" }}>
                        <span>মোট</span><span style={{ color: "#0a8752" }}>{money(o.total)}</span>
                      </div>
                    </div>
                  </div>
                  {nexts.length > 0 && (
                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
                      {nexts.map(n => <ChangeStatusBtn key={n.s} orderId={o.id} status={n.s} label={n.l} color={STATUS[n.s]?.color || "#0a8752"} onDone={load} />)}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Settings tab ───────────────────────────────────────────────────────────────
function HoursEditor({ value, onChange }) {
  const def = { open: false, from: "09:00", to: "21:00" };
  const h = value || {};
  const upd = (day, field, val) => onChange({ ...h, [day]: { ...(h[day] || def), [field]: val } });
  return (
    <div style={{ display: "grid", gap: 6 }}>
      {DAYS.map(d => {
        const day = h[d.k] || def;
        return (
          <div key={d.k} style={{ display: "grid", gridTemplateColumns: "100px 48px 1fr 16px 1fr", gap: 10, alignItems: "center", padding: "8px 12px", background: day.open ? "#f0f9f4" : "#f8f8f8", borderRadius: 9, border: `1.5px solid ${day.open ? "#c8ead8" : "#eee"}` }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: day.open ? "#0d1f16" : "#8aaa97" }}>{d.l}</span>
            <Toggle on={day.open} onChange={() => upd(d.k, "open", !day.open)} size="sm" />
            <input type="time" value={day.from} onChange={e => upd(d.k, "from", e.target.value)} disabled={!day.open}
              style={{ padding: "6px 8px", border: "1.5px solid #d0e0d8", borderRadius: 6, fontSize: 13, outline: "none", opacity: day.open ? 1 : .3, width: "100%" }} />
            <span style={{ textAlign: "center", color: "#8aaa97" }}>–</span>
            <input type="time" value={day.to} onChange={e => upd(d.k, "to", e.target.value)} disabled={!day.open}
              style={{ padding: "6px 8px", border: "1.5px solid #d0e0d8", borderRadius: 6, fontSize: 13, outline: "none", opacity: day.open ? 1 : .3, width: "100%" }} />
          </div>
        );
      })}
    </div>
  );
}

function SettingsTab({ store, onRefresh }) {
  const { feedback, setFeedback } = useFeedback();
  const [form, setForm] = useState({
    show_phone: store?.show_phone ?? false, show_exact_address: store?.show_exact_address ?? false,
    show_hours: store?.show_hours ?? true, show_price: store?.show_price ?? true,
    show_stock_level: store?.show_stock_level ?? "available_only",
    payment_cod: store?.payment_cod ?? true, payment_bkash: store?.payment_bkash ?? false, payment_nagad: store?.payment_nagad ?? false,
    min_order_bdt: store?.min_order_bdt ?? "", delivery_note: store?.delivery_note ?? "",
    hours_json: store?.hours_json ?? null,
  });
  const [busy, setBusy] = useState(false);
  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }));

  async function save(e) {
    e.preventDefault(); setBusy(true);
    try {
      await api.updateStore({ ...form, min_order_bdt: form.min_order_bdt ? Number(form.min_order_bdt) : null });
      setFeedback({ type: "success", message: "✓ সেটিংস সংরক্ষিত।" }); onRefresh();
    } catch (err) { setFeedback({ type: "error", message: explain(err) }); }
    finally { setBusy(false); }
  }

  if (!store) return <Notice tone="warn">আগে স্টোর বিল্ডার থেকে স্টোর তৈরি করুন।</Notice>;

  const Row = ({ label, hint, field }) => (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "13px 0", borderBottom: "1px solid #f0f5f2" }}>
      <div>
        <div style={{ fontWeight: 600, fontSize: 14 }}>{label}</div>
        {hint && <div style={{ fontSize: 12, color: "#8aaa97", marginTop: 2 }}>{hint}</div>}
      </div>
      <Toggle on={form[field]} onChange={() => setForm(f => ({ ...f, [field]: !f[field] }))} />
    </div>
  );

  return (
    <form onSubmit={save}>
      <FeedbackBanner feedback={feedback} />
      <Sh>👁️ দৃশ্যমানতা</Sh>
      <Row label="ফোন নম্বর দেখান" hint="Default: বন্ধ — গোপনীয়তা রক্ষা" field="show_phone" />
      <Row label="সঠিক ঠিকানা দেখান" hint="Default: বন্ধ — শুধু এলাকা দেখায়" field="show_exact_address" />
      <Row label="মূল্য দেখান" hint="বন্ধ করলে 'যোগাযোগ করুন' দেখাবে" field="show_price" />
      <Row label="ব্যবসার সময় দেখান" hint="" field="show_hours" />
      <div style={{ padding: "13px 0", borderBottom: "1px solid #f0f5f2" }}>
        <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 10 }}>স্টক স্তর</div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {[{v:"hide",l:"🙈 লুকান"},{v:"available_only",l:"✓/✗ আছে/নেই"},{v:"quantity",l:"📊 পরিমাণও"}].map(o => (
            <button key={o.v} type="button" onClick={() => setForm(f => ({ ...f, show_stock_level: o.v }))}
              style={{ padding: "8px 16px", borderRadius: 9, border: "1.5px solid", fontSize: 13, fontWeight: 600, cursor: "pointer", borderColor: form.show_stock_level === o.v ? "#0a8752" : "#d0e0d8", background: form.show_stock_level === o.v ? "#f0f9f4" : "#fff", color: form.show_stock_level === o.v ? "#0a8752" : "#6b7280" }}>
              {o.l}
            </button>
          ))}
        </div>
      </div>
      <Sh>💳 পেমেন্ট</Sh>
      <Row label="💵 Cash on Delivery" hint="ডেলিভারির সময় নগদ" field="payment_cod" />
      <Row label="📱 bKash" hint="Checkout এ bKash অপশন" field="payment_bkash" />
      <Row label="💳 Nagad" hint="Checkout এ Nagad অপশন" field="payment_nagad" />
      <Sh>🚚 ডেলিভারি</Sh>
      <div style={{ marginBottom: 16 }}>
        <label style={{ fontSize: 13, fontWeight: 700, color: "#4a6358", display: "block", marginBottom: 7 }}>সর্বনিম্ন অর্ডার (৳)</label>
        <input type="number" min="0" value={form.min_order_bdt} onChange={set("min_order_bdt")} placeholder="0"
          style={{ padding: "10px 14px", border: "1.5px solid #d0e0d8", borderRadius: 9, fontSize: 14, outline: "none", width: 200 }} />
      </div>
      <div style={{ marginBottom: 16 }}>
        <label style={{ fontSize: 13, fontWeight: 700, color: "#4a6358", display: "block", marginBottom: 7 }}>ডেলিভারি নোট</label>
        <input value={form.delivery_note} onChange={set("delivery_note")} placeholder="যেমন: শুধু ঢাকায়, ২–৩ দিন লাগে"
          style={{ width: "100%", padding: "10px 14px", border: "1.5px solid #d0e0d8", borderRadius: 9, fontSize: 14, outline: "none", boxSizing: "border-box" }} />
      </div>
      <Sh>🕘 ব্যবসার সময়সূচি</Sh>
      <p style={{ fontSize: 13, color: "#6b8a7a", margin: "0 0 12px", lineHeight: 1.5 }}>"সময় দেখান" চালু থাকলে স্টোরের হোমে দেখাবে।</p>
      <HoursEditor value={form.hours_json} onChange={h => setForm(f => ({ ...f, hours_json: h }))} />
      <div style={{ marginTop: 28 }}><Button type="submit" loading={busy} style={{ padding: "13px 32px" }}>✓ সেটিংস সংরক্ষণ</Button></div>
    </form>
  );
}

// ── Root ───────────────────────────────────────────────────────────────────────
export default function StoreAdmin() {
  const [tab, setTab] = useState("overview");
  const [store, setStore] = useState(undefined);
  const [stats, setStats] = useState(null);
  const [orgId, setOrgId] = useState("");
  const [error, setError] = useState("");

  async function load() {
    try { const d = await api.getStore(); setStore(d); setOrgId(d.organization_id); }
    catch (err) { if (err?.status === 404 || err?.response?.status === 404) setStore(null); else setError(explain(err)); }
    try { setStats(await api.getStoreStats()); } catch {}
  }

  useEffect(() => {
    load();
    try { const o = JSON.parse(localStorage.getItem("bsmart_org") || "{}"); if (o.id) setOrgId(o.id); } catch {}
  }, []);

  if (store === undefined) return <div className="page stack"><PageHeader title="অনলাইন স্টোর" /><p className="muted">লোড হচ্ছে…</p></div>;

  return (
    <div className="page stack">
      <PageHeader
        title="অনলাইন স্টোর"
        subtitle="আপনার public storefront পরিচালনা করুন"
        action={store?.is_active && orgId ? (
          <a href={`#/store/${orgId}`} target="_blank" rel="noopener noreferrer"
            style={{ fontSize: 13, color: "#0a8752", fontWeight: 600, textDecoration: "none", display: "flex", alignItems: "center", gap: 6, border: "1.5px solid #0a8752", borderRadius: 8, padding: "6px 14px" }}>
            🌐 স্টোর দেখুন ↗
          </a>
        ) : null}
      />
      {error && <Notice tone="danger">{error}</Notice>}
      <div style={{ display: "flex", gap: 0, borderBottom: "2px solid var(--border)", marginBottom: 24, overflowX: "auto" }}>
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            style={{ padding: "11px 18px", border: "none", background: "none", cursor: "pointer", fontSize: 14, fontWeight: tab === t.id ? 700 : 500, color: tab === t.id ? "var(--green)" : "var(--muted)", borderBottom: `3px solid ${tab === t.id ? "var(--green)" : "transparent"}`, marginBottom: -2, whiteSpace: "nowrap", display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ fontSize: 14 }}>{t.icon}</span>{t.label}
            {t.id === "orders" && stats?.pending_orders > 0 && <span style={{ marginLeft: 2, background: "#f59e0b", color: "#fff", borderRadius: 10, padding: "0 6px", fontSize: 11, fontWeight: 700 }}>{stats.pending_orders}</span>}
          </button>
        ))}
      </div>
      {tab === "overview" && <OverviewTab store={store} stats={stats} orgId={orgId} onTab={setTab} />}
      {tab === "builder"  && <BuilderTab store={store} onRefresh={load} />}
      {tab === "products" && (store ? <ProductsTab /> : <Notice tone="warn">আগে স্টোর বিল্ডার থেকে স্টোর তৈরি করুন।</Notice>)}
      {tab === "orders"   && (store ? <OrdersTab /> : <Notice tone="warn">আগে স্টোর বিল্ডার থেকে স্টোর তৈরি করুন।</Notice>)}
      {tab === "settings" && <SettingsTab store={store} onRefresh={load} />}
    </div>
  );
}
