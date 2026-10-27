import { useEffect, useMemo, useState } from "react";
import { BD_DIVISIONS, getDistricts, getThanas } from "../bd_address";
import { customerFetch } from "../storeCustomerApi";

const inputStyle = {
  width: "100%", minWidth: 0, padding: "10px 12px", borderRadius: 10,
  border: "1px solid var(--border)", background: "var(--bg)", color: "var(--text)",
  fontSize: 13, fontFamily: "inherit", boxSizing: "border-box",
};
const buttonStyle = {
  border: "1px solid var(--border)", borderRadius: 9, padding: "8px 11px",
  background: "var(--surface)", color: "var(--text)", cursor: "pointer",
  fontSize: 12, fontWeight: 700, fontFamily: "inherit",
};
const primaryStyle = {
  ...buttonStyle, border: "none", background: "var(--green)", color: "var(--sc-on-green)",
};
const cardStyle = {
  padding: 14, border: "1px solid var(--border)", borderRadius: 13,
  background: "var(--surface)", marginBottom: 10, minWidth: 0,
};
function Alert({ children, tone = "error" }) {
  if (!children) return null;
  return <div role={tone === "error" ? "alert" : "status"} style={{
    padding: "9px 11px", marginBottom: 12, borderRadius: 9, fontSize: 12,
    color: tone === "error" ? "#b91c1c" : "#15803d",
    background: tone === "error" ? "rgba(239,68,68,.09)" : "rgba(34,197,94,.10)",
    border: `1px solid ${tone === "error" ? "rgba(239,68,68,.24)" : "rgba(34,197,94,.24)"}`,
  }}>{children}</div>;
}
function Field({ label, children }) {
  return <label style={{ display: "grid", gap: 5, fontSize: 12, color: "var(--text-muted)", fontWeight: 650 }}>{label}{children}</label>;
}
function Empty({ icon, title, detail }) {
  return <div style={{ textAlign: "center", padding: "30px 14px", color: "var(--text-muted)" }}>
    <div style={{ fontSize: 34, marginBottom: 8 }}>{icon}</div>
    <div style={{ color: "var(--text)", fontSize: 14, fontWeight: 750 }}>{title}</div>
    <p style={{ margin: "5px 0 0", fontSize: 12, lineHeight: 1.6 }}>{detail}</p>
  </div>;
}

const blankAddress = () => ({
  label: "বাড়ি", recipient_name: "", phone: "", division: "", district: "",
  thana: "", address_detail: "", postal_code: "", is_default: false,
});

export function AddressesView({ token, storeSlug }) {
  const [addresses, setAddresses] = useState([]);
  const [form, setForm] = useState(blankAddress);
  const [editingId, setEditingId] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [busyId, setBusyId] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const districts = useMemo(() => getDistricts(form.division), [form.division]);
  const thanas = useMemo(() => getThanas(form.district), [form.district]);

  async function load() {
    try {
      const data = await customerFetch(storeSlug, "/addresses", {}, token);
      setAddresses(data.addresses || []);
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }
  useEffect(() => { load(); }, [token, storeSlug]);

  function setField(key, value) {
    setForm(current => {
      const next = { ...current, [key]: value };
      if (key === "division") { next.district = ""; next.thana = ""; }
      if (key === "district") next.thana = "";
      return next;
    });
  }
  function edit(address) {
    setEditingId(address.id);
    setForm({ ...blankAddress(), ...address });
    setShowForm(true);
    setError(""); setNotice("");
  }
  function startNew() {
    setEditingId(null);
    setForm({ ...blankAddress(), is_default: addresses.length === 0 });
    setShowForm(true); setError(""); setNotice("");
  }
  async function save(event) {
    event.preventDefault(); setSaving(true); setError(""); setNotice("");
    try {
      const path = editingId ? `/addresses/${encodeURIComponent(editingId)}` : "/addresses";
      const result = await customerFetch(storeSlug, path, {
        method: editingId ? "PATCH" : "POST",
        body: JSON.stringify(form),
      }, token);
      setAddresses(current => {
        const next = editingId ? current.map(a => a.id === result.id ? result : a) : [result, ...current];
        return result.is_default ? next.map(a => ({ ...a, is_default: a.id === result.id })) : next;
      });
      await load();
      setShowForm(false); setEditingId(null); setForm(blankAddress());
      setNotice("ডেলিভারি ঠিকানা সংরক্ষণ করা হয়েছে।");
    } catch (e) { setError(e.message); }
    finally { setSaving(false); }
  }
  async function makeDefault(address) {
    setBusyId(address.id); setError(""); setNotice("");
    try {
      await customerFetch(storeSlug, `/addresses/${encodeURIComponent(address.id)}`, {
        method: "PATCH", body: JSON.stringify({ is_default: true }),
      }, token);
      await load(); setNotice("ডিফল্ট ঠিকানা পরিবর্তন হয়েছে।");
    } catch (e) { setError(e.message); }
    finally { setBusyId(null); }
  }
  async function remove(address) {
    if (!window.confirm("এই সংরক্ষিত ঠিকানাটি মুছে ফেলতে চান?")) return;
    setBusyId(address.id); setError(""); setNotice("");
    try {
      await customerFetch(storeSlug, `/addresses/${encodeURIComponent(address.id)}`, { method: "DELETE" }, token);
      await load(); setNotice("ঠিকানা মুছে ফেলা হয়েছে।");
      if (editingId === address.id) { setShowForm(false); setEditingId(null); }
    } catch (e) { setError(e.message); }
    finally { setBusyId(null); }
  }

  return <section>
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, marginBottom: 12 }}>
      <div><h3 style={{ margin: 0, fontSize: 16, color: "var(--text)" }}>ডেলিভারি ঠিকানা</h3>
        <p style={{ margin: "4px 0 0", fontSize: 12, color: "var(--text-muted)" }}>সব দোকানে একই সংরক্ষিত ঠিকানা ব্যবহার করতে পারবেন।</p></div>
      {!showForm && <button style={primaryStyle} onClick={startNew}>＋ নতুন ঠিকানা</button>}
    </div>
    <Alert>{error}</Alert><Alert tone="success">{notice}</Alert>
    {showForm && <form onSubmit={save} style={{ ...cardStyle, display: "grid", gap: 11 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "center" }}>
        <strong style={{ fontSize: 14, color: "var(--text)" }}>{editingId ? "ঠিকানা সম্পাদনা" : "নতুন ঠিকানা যোগ করুন"}</strong>
        <button type="button" style={buttonStyle} onClick={() => { setShowForm(false); setEditingId(null); }}>বন্ধ করুন</button>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2,minmax(0,1fr))", gap: 10 }}>
        <Field label="ঠিকানার নাম"><select style={inputStyle} value={form.label} onChange={e => setField("label", e.target.value)}>
          {["বাড়ি", "অফিস", "অন্যান্য"].map(x => <option key={x}>{x}</option>)}
        </select></Field>
        <Field label="প্রাপকের নাম"><input style={inputStyle} value={form.recipient_name} onChange={e => setField("recipient_name", e.target.value)} required minLength={2} maxLength={100}/></Field>
        <Field label="ফোন নম্বর"><input style={inputStyle} type="tel" value={form.phone} onChange={e => setField("phone", e.target.value)} required minLength={7} maxLength={20} placeholder="01XXXXXXXXX"/></Field>
        <Field label="বিভাগ"><select style={inputStyle} value={form.division} onChange={e => setField("division", e.target.value)} required>
          <option value="">বিভাগ বেছে নিন</option>{BD_DIVISIONS.map(d => <option key={d}>{d}</option>)}
        </select></Field>
        <Field label="জেলা"><select style={inputStyle} value={form.district} onChange={e => setField("district", e.target.value)} required disabled={!form.division}>
          <option value="">জেলা বেছে নিন</option>{districts.map(d => <option key={d}>{d}</option>)}
        </select></Field>
        <Field label="থানা / উপজেলা"><select style={inputStyle} value={form.thana} onChange={e => setField("thana", e.target.value)} disabled={!form.district}>
          <option value="">বেছে নিন</option>{thanas.map(t => <option key={t}>{t}</option>)}
        </select></Field>
      </div>
      <Field label="বাড়ি, রোড, এলাকা ও বিস্তারিত ঠিকানা"><textarea style={{ ...inputStyle, minHeight: 76, resize: "vertical" }} value={form.address_detail} onChange={e => setField("address_detail", e.target.value)} required minLength={3} maxLength={400}/></Field>
      <Field label="পোস্ট কোড (ঐচ্ছিক)"><input style={inputStyle} value={form.postal_code || ""} onChange={e => setField("postal_code", e.target.value)} maxLength={12}/></Field>
      <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "var(--text)" }}>
        <input type="checkbox" checked={!!form.is_default} onChange={e => setField("is_default", e.target.checked)}/> ডিফল্ট ডেলিভারি ঠিকানা হিসেবে রাখুন
      </label>
      <button type="submit" disabled={saving} style={{ ...primaryStyle, padding: 11 }}>{saving ? "সংরক্ষণ হচ্ছে…" : "ঠিকানা সংরক্ষণ করুন"}</button>
    </form>}
    {loading ? <div style={{ padding: 22, color: "var(--text-muted)", fontSize: 13 }}>ঠিকানা লোড হচ্ছে…</div> : addresses.length === 0 && !showForm
      ? <Empty icon="📍" title="এখনো কোনো ঠিকানা সংরক্ষণ করা হয়নি" detail="চেকআউট দ্রুত করতে আপনার বাড়ি বা অফিসের ঠিকানা যোগ করুন।"/>
      : addresses.map(address => <article key={address.id} style={cardStyle}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8 }}>
          <div style={{ minWidth: 0 }}>
            <div style={{ display: "flex", gap: 7, alignItems: "center", flexWrap: "wrap" }}>
              <strong style={{ color: "var(--text)", fontSize: 14 }}>{address.label}</strong>
              {address.is_default && <span style={{ background: "rgba(22,163,74,.12)", color: "#15803d", borderRadius: 6, padding: "2px 7px", fontSize: 10, fontWeight: 800 }}>ডিফল্ট</span>}
            </div>
            <div style={{ color: "var(--text)", fontSize: 12, marginTop: 6, fontWeight: 650 }}>{address.recipient_name} · {address.phone}</div>
            <div style={{ color: "var(--text-muted)", fontSize: 12, marginTop: 4, lineHeight: 1.6 }}>
              {[address.address_detail, address.thana, address.district, address.division, address.postal_code].filter(Boolean).join(", ")}
            </div>
          </div>
          <span aria-hidden="true" style={{ fontSize: 21 }}>📍</span>
        </div>
        <div style={{ display: "flex", gap: 7, flexWrap: "wrap", marginTop: 12 }}>
          <button style={buttonStyle} onClick={() => edit(address)}>সম্পাদনা</button>
          {!address.is_default && <button style={buttonStyle} disabled={busyId === address.id} onClick={() => makeDefault(address)}>{busyId === address.id ? "অপেক্ষা…" : "ডিফল্ট করুন"}</button>}
          <button style={{ ...buttonStyle, color: "#dc2626" }} disabled={busyId === address.id} onClick={() => remove(address)}>মুছুন</button>
        </div>
      </article>)}
  </section>;
}

export function WishlistView({ token, storeSlug, onAddToCart }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  async function load() {
    try { const data = await customerFetch(storeSlug, "/wishlist", {}, token); setItems(data.items || []); }
    catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }
  useEffect(() => { load(); }, [token]);
  async function remove(item) {
    setBusy(item.id); setError("");
    try {
      await customerFetch(storeSlug, `/wishlist/${encodeURIComponent(item.store_slug)}/${encodeURIComponent(item.product_id)}`, { method: "DELETE" }, token);
      setItems(current => current.filter(x => x.id !== item.id));
    } catch (e) { setError(e.message); }
    finally { setBusy(""); }
  }
  function visit(item) {
    if (item.store_slug !== storeSlug) window.location.assign(`/store/${encodeURIComponent(item.store_slug)}`);
  }
  return <section>
    <div style={{ marginBottom: 12 }}>
      <h3 style={{ margin: 0, fontSize: 16, color: "var(--text)" }}>আমার পছন্দের পণ্য</h3>
      <p style={{ margin: "4px 0 0", fontSize: 12, color: "var(--text-muted)" }}>পছন্দের পণ্য বিভিন্ন দোকান থেকে এখানে সংরক্ষিত থাকবে।</p>
    </div>
    <Alert>{error}</Alert>
    {loading ? <div style={{ padding: 22, color: "var(--text-muted)", fontSize: 13 }}>পছন্দের পণ্য লোড হচ্ছে…</div>
      : items.length === 0 ? <Empty icon="♡" title="পছন্দের তালিকা খালি" detail="দোকানের পণ্য কার্ডে থাকা হার্ট চিহ্নে চাপ দিয়ে পণ্য সংরক্ষণ করুন।"/>
      : <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(210px,1fr))", gap: 10 }}>
        {items.map(item => <article key={item.id} style={{ ...cardStyle, margin: 0, padding: 0, overflow: "hidden" }}>
          {item.image_data_url ? <img src={item.image_data_url} alt={item.product_name} style={{ width: "100%", height: 130, objectFit: "cover", background: "var(--bg)" }}/> :
            <div style={{ height: 100, display: "grid", placeItems: "center", background: "var(--bg)", fontSize: 36 }}>🛍️</div>}
          <div style={{ padding: 12 }}>
            <div style={{ color: "var(--text)", fontWeight: 750, fontSize: 13 }}>{item.product_name}</div>
            <div style={{ color: "var(--text-muted)", fontSize: 11, marginTop: 3 }}>{item.store_name}</div>
            <div style={{ color: "var(--green)", fontWeight: 800, fontSize: 14, marginTop: 7 }}>{item.price == null ? "দাম জানতে যোগাযোগ করুন" : `৳${Number(item.price).toLocaleString("bn-BD")}`}</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, marginTop: 10 }}>
              <button style={buttonStyle} onClick={() => visit(item)}>{item.store_slug === storeSlug ? "এই দোকানে" : "দোকান দেখুন"}</button>
              {item.store_slug === storeSlug && onAddToCart && <button style={primaryStyle} onClick={() => onAddToCart(item.product_id)}>কার্টে যোগ</button>}
            </div>
            <button style={{ ...buttonStyle, width: "100%", marginTop: 6, color: "#dc2626" }} disabled={busy === item.id} onClick={() => remove(item)}>{busy === item.id ? "মুছছে…" : "♡ তালিকা থেকে সরান"}</button>
          </div>
        </article>)}
      </div>}
  </section>;
}

export function SecurityView({ token, storeSlug, onTokenChange }) {
  const [form, setForm] = useState({ current_password: "", new_password: "", confirm_password: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const set = key => event => setForm(current => ({ ...current, [key]: event.target.value }));
  async function submit(event) {
    event.preventDefault(); setError(""); setNotice("");
    if (form.new_password !== form.confirm_password) { setError("নতুন পাসওয়ার্ড দুবার একইভাবে লিখুন।"); return; }
    if (form.new_password.length < 8) { setError("নতুন পাসওয়ার্ড কমপক্ষে ৮ অক্ষরের হতে হবে।"); return; }
    setBusy(true);
    try {
      const data = await customerFetch(storeSlug, "/password", {
        method: "POST",
        body: JSON.stringify({ current_password: form.current_password, new_password: form.new_password }),
      }, token);
      onTokenChange?.(data.token, data.customer);
      setForm({ current_password: "", new_password: "", confirm_password: "" });
      setNotice("পাসওয়ার্ড পরিবর্তন হয়েছে। অন্য ডিভাইসের পুরোনো সেশন বন্ধ করা হয়েছে।");
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  return <section style={{ maxWidth: 520 }}>
    <h3 style={{ margin: "0 0 5px", fontSize: 16, color: "var(--text)" }}>নিরাপত্তা ও পাসওয়ার্ড</h3>
    <p style={{ margin: "0 0 16px", fontSize: 12, color: "var(--text-muted)", lineHeight: 1.6 }}>পাসওয়ার্ড বদলালে এই অ্যাকাউন্টের অন্য সক্রিয় লগইন সেশনও বাতিল হবে।</p>
    <Alert>{error}</Alert><Alert tone="success">{notice}</Alert>
    <form onSubmit={submit} style={{ ...cardStyle, display: "grid", gap: 12 }}>
      <Field label="বর্তমান পাসওয়ার্ড"><input style={inputStyle} type="password" autoComplete="current-password" value={form.current_password} onChange={set("current_password")} required/></Field>
      <Field label="নতুন পাসওয়ার্ড (কমপক্ষে ৮ অক্ষর)"><input style={inputStyle} type="password" autoComplete="new-password" minLength={8} value={form.new_password} onChange={set("new_password")} required/></Field>
      <Field label="নতুন পাসওয়ার্ড আবার লিখুন"><input style={inputStyle} type="password" autoComplete="new-password" minLength={8} value={form.confirm_password} onChange={set("confirm_password")} required/></Field>
      <button type="submit" disabled={busy} style={{ ...primaryStyle, padding: 11 }}>{busy ? "পরিবর্তন হচ্ছে…" : "পাসওয়ার্ড পরিবর্তন করুন"}</button>
    </form>
    <div style={{ ...cardStyle, marginTop: 12 }}>
      <strong style={{ color: "var(--text)", fontSize: 13 }}>অ্যাকাউন্ট সুরক্ষা</strong>
      <p style={{ margin: "5px 0 0", color: "var(--text-muted)", fontSize: 12, lineHeight: 1.65 }}>আপনার পাসওয়ার্ড অন্য কারও সঙ্গে শেয়ার করবেন না। পাসওয়ার্ড ভুলে গেলে ইমেইল-ভিত্তিক রিসেট ব্যবস্থা কনফিগার না হওয়া পর্যন্ত দোকান বা প্ল্যাটফর্মের সহায়তা নিন।</p>
    </div>
  </section>;
}
