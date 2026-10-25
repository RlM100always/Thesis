/**
 * Public store directory — lists all active B-SMART stores.
 * No auth required. Accessible at /stores.
 */
import { useEffect, useState } from "react";
import { api } from "../api";
import { storeCoverImage } from "../storeImages";

const PRESET_GRAD = {
  warm:     "linear-gradient(135deg, #f5c06a 0%, #e8895a 100%)",
  dark:     "linear-gradient(135deg, #1e3a5f 0%, #0d1b2a 100%)",
  pharmacy: "linear-gradient(135deg, #5ecba1 0%, #0a8752 100%)",
  fashion:  "linear-gradient(135deg, #e8b4cb 0%, #c47fa3 100%)",
  clean:    "linear-gradient(135deg, #a8d5b5 0%, #5aab7a 100%)",
};

const CAT_EMOJI = {
  "ফার্মেসি": "💊", "গ্রোসারি": "🥦", "পোশাক": "👗", "রেস্তোরাঁ": "🍽️",
  "ইলেকট্রনিক্স": "💡", "হার্ডওয়্যার": "🔧", "বিউটি": "💄",
  "স্টেশনারি": "✏️", "মোবাইল": "📱", "ফার্নিচার": "🛋️",
};

const DIR_CSS = `
@import url('https://fonts.googleapis.com/css2?family=Hind+Siliguri:wght@400;500;600;700&display=swap');

/* ── Base ── */
.sd-page { min-height: 100vh; background: #f4f7fb; font-family: 'Hind Siliguri', system-ui, sans-serif; color: #0d1b2a; }
.sd-page *, .sd-page *::before, .sd-page *::after { box-sizing: border-box; }

/* ── Header ── */
.sd-header { background: rgba(255,255,255,.92); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px); border-bottom: 1px solid rgba(0,0,0,.07); padding: 0 24px; position: sticky; top: 0; z-index: 50; }
.sd-header-inner { max-width: 1140px; margin: 0 auto; height: 62px; display: flex; align-items: center; gap: 14px; }
.sd-logo { font-size: 21px; font-weight: 800; color: #0a8752; text-decoration: none; letter-spacing: -.3px; display: flex; align-items: center; gap: 8px; }
.sd-logo-dot { width: 8px; height: 8px; border-radius: 50%; background: #0a8752; display: inline-block; }
.sd-tagline { font-size: 13.5px; color: #94a3b8; border-left: 1.5px solid #e2e8f0; padding-left: 14px; }
.sd-header-space { flex: 1; }
.sd-back-link { font-size: 13px; font-weight: 600; color: #64748b; text-decoration: none; display: flex; align-items: center; gap: 5px; transition: color .15s; }
.sd-back-link:hover { color: #0a8752; }

/* ── Hero ── */
.sd-hero {
  background: #087a4b;
  color: #fff; text-align: center; padding: 72px 24px 100px; position: relative; overflow: hidden;
}
.sd-hero::before { content: none; }
.sd-hero-eyebrow { display: inline-flex; align-items: center; gap: 6px; background: rgba(255,255,255,.15); border: 1px solid rgba(255,255,255,.25); border-radius: 20px; padding: 4px 14px; font-size: 12.5px; font-weight: 600; letter-spacing: .04em; margin-bottom: 18px; }
.sd-hero h1 { font-size: clamp(26px, 5vw, 46px); font-weight: 800; margin: 0 0 14px; line-height: 1.15; letter-spacing: -.5px; position: relative; }
.sd-hero p { font-size: 16px; opacity: .82; margin: 0 0 32px; max-width: 440px; margin-inline: auto; line-height: 1.6; position: relative; }
.sd-search-wrap { max-width: 520px; margin: 0 auto; position: relative; }
.sd-search-icon { position: absolute; left: 18px; top: 50%; transform: translateY(-50%); font-size: 17px; pointer-events: none; }
.sd-search { width: 100%; padding: 16px 20px 16px 50px; border-radius: 16px; border: none; font-size: 15px; font-family: inherit; outline: none; box-shadow: 0 8px 32px rgba(0,0,0,.22), 0 2px 8px rgba(0,0,0,.1); transition: box-shadow .2s; }
.sd-search:focus { box-shadow: 0 8px 32px rgba(0,0,0,.28), 0 0 0 3px rgba(255,255,255,.3); }
.sd-hero-stats { display: flex; gap: 24px; justify-content: center; margin-top: 28px; position: relative; }
.sd-hero-stat { text-align: center; }
.sd-hero-stat-num { font-size: 22px; font-weight: 800; line-height: 1; }
.sd-hero-stat-label { font-size: 11px; opacity: .7; margin-top: 3px; font-weight: 500; }
.sd-hero-wave { position: absolute; bottom: -2px; left: 0; right: 0; }

/* ── Filters ── */
.sd-filters-wrap { max-width: 1140px; margin: -1px auto 0; padding: 24px 24px 8px; }
.sd-filters-label { font-size: 12px; font-weight: 700; color: #94a3b8; letter-spacing: .08em; text-transform: uppercase; margin-bottom: 10px; }
.sd-filters { display: flex; gap: 8px; flex-wrap: wrap; }
.sd-filter-btn {
  padding: 8px 18px; border: 1.5px solid #e2e8f0; border-radius: 24px;
  font-size: 13px; font-weight: 500; font-family: inherit; background: #fff; cursor: pointer;
  white-space: nowrap; transition: all .15s; color: #475569; display: flex; align-items: center; gap: 5px;
  box-shadow: 0 1px 3px rgba(0,0,0,.04);
}
.sd-filter-btn:hover { border-color: #0a8752; color: #0a8752; background: #f0fdf4; }
.sd-filter-btn.active { background: #0a8752; color: #fff; border-color: #0a8752; box-shadow: 0 4px 12px rgba(10,135,82,.3); font-weight: 600; }

/* ── Toolbar ── */
.sd-toolbar { max-width: 1140px; margin: 16px auto 0; padding: 0 24px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; }
.sd-count { font-size: 13px; color: #94a3b8; font-weight: 500; }
.sd-count strong { color: #475569; }

/* ── Grid ── */
.sd-grid { max-width: 1140px; margin: 20px auto 0; padding: 0 24px 72px; display: grid; grid-template-columns: repeat(auto-fill, minmax(290px, 1fr)); gap: 22px; }

/* ── Card ── */
.sd-card {
  background: #fff; border-radius: 20px; overflow: hidden;
  box-shadow: 0 1px 4px rgba(13,27,42,.08);
  cursor: pointer; transition: box-shadow .18s ease, transform .18s ease;
  text-decoration: none; color: inherit; display: flex; flex-direction: column;
}
.sd-card:hover { box-shadow: 0 5px 16px rgba(13,27,42,.12); transform: translateY(-2px); }
.sd-card-cover { height: 136px; display: flex; align-items: center; justify-content: center; font-size: 52px; position: relative; overflow: hidden; }
.sd-card-cover img { width: 100%; height: 100%; object-fit: cover; position: absolute; inset: 0; }
.sd-card-cover-overlay { position: absolute; inset: 0; background: linear-gradient(160deg, transparent 40%, rgba(0,0,0,.38)); }
.sd-card-logo {
  position: absolute; bottom: -22px; left: 18px; width: 52px; height: 52px; border-radius: 13px;
  border: 2.5px solid #fff; background: #fff; overflow: hidden; display: flex; align-items: center;
  justify-content: center; font-size: 20px; font-weight: 800;
  box-shadow: 0 3px 12px rgba(0,0,0,.18);
}
.sd-card-logo img { width: 100%; height: 100%; object-fit: cover; }
.sd-card-body { padding: 32px 18px 16px; flex: 1; }
.sd-card-name { font-size: 16px; font-weight: 700; margin: 0 0 5px; color: #0d1b2a; letter-spacing: -.2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.sd-card-tagline { font-size: 13px; color: #64748b; margin: 0 0 12px; line-height: 1.45; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; min-height: 38px; }
.sd-card-chips { display: flex; gap: 6px; flex-wrap: wrap; }
.sd-chip { font-size: 11.5px; padding: 3px 10px; border-radius: 12px; background: #f1f5f9; color: #475569; font-weight: 500; display: flex; align-items: center; gap: 3px; }
.sd-chip-cat { background: #f0fdf4; color: #15803d; }
.sd-chip-area { background: #fef9f0; color: #92400e; }
.sd-card-footer { padding: 12px 18px 16px; display: flex; justify-content: space-between; align-items: center; border-top: 1px solid #f1f5f9; }
.sd-visit-btn { font-size: 13px; font-weight: 700; color: #0a8752; display: flex; align-items: center; gap: 4px; transition: gap .15s; }
.sd-card:hover .sd-visit-btn { gap: 8px; }
.sd-payment-row { display: flex; gap: 5px; }
.sd-pay-badge { width: 26px; height: 26px; border-radius: 6px; background: #f8fafc; border: 1px solid #e2e8f0; display: flex; align-items: center; justify-content: center; font-size: 13px; }

/* ── Empty / Loading ── */
.sd-empty { text-align: center; padding: 96px 20px; color: #64748b; }
.sd-empty-icon { font-size: 56px; margin-bottom: 16px; }
.sd-empty h2 { font-size: 20px; font-weight: 700; color: #334155; margin: 0 0 8px; }
.sd-empty p { font-size: 14px; margin: 0; }
.sd-loading { display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 60vh; gap: 16px; color: #64748b; }
.sd-spinner { width: 36px; height: 36px; border: 3px solid #e2e8f0; border-top-color: #0a8752; border-radius: 50%; animation: sd-spin .7s linear infinite; }
@keyframes sd-spin { to { transform: rotate(360deg); } }

/* ── Footer ── */
.sd-footer { background: #0d1b2a; color: #64748b; text-align: center; padding: 32px 20px; font-size: 13px; margin-top: 0; }
.sd-footer a { color: #94a3b8; text-decoration: none; font-weight: 600; }
.sd-footer a:hover { color: #0a8752; }

/* ── Responsive ── */
@media (max-width: 680px) {
  .sd-hero { padding: 52px 16px 80px; }
  .sd-grid { grid-template-columns: 1fr 1fr; gap: 12px; padding: 0 14px 56px; }
  .sd-card-cover { height: 100px; }
  .sd-card-body { padding: 26px 12px 12px; }
  .sd-card-name { font-size: 14px; }
  .sd-card-tagline { display: none; }
  .sd-card-footer { padding: 10px 12px 12px; }
  .sd-filters-wrap { padding: 16px 14px 4px; }
  .sd-toolbar { padding: 0 14px; }
}
@media (max-width: 380px) {
  .sd-grid { grid-template-columns: 1fr; }
}
`;

export default function StoreDirectory() {
  const [stores, setStores] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [search, setSearch] = useState("");
  const [activeCategory, setActiveCategory] = useState(null);
  const [activeArea, setActiveArea] = useState(null);

  useEffect(() => {
    const el = document.createElement("style");
    el.id = "bsmart-dir-css";
    el.textContent = DIR_CSS;
    document.head.appendChild(el);
    return () => el.remove();
  }, []);

  async function loadStores() {
    setLoading(true);
    setLoadError("");
    try {
      const data = await api.getPublicStores();
      setStores(Array.isArray(data) ? data : []);
    } catch {
      setLoadError("দোকানের তালিকা এখন আনা যাচ্ছে না। ইন্টারনেট সংযোগ দেখে আবার চেষ্টা করুন।");
    } finally { setLoading(false); }
  }
  useEffect(() => { loadStores(); }, []);

  const categories = [...new Set(stores.map(s => s.category).filter(Boolean))];
  const areas = [...new Set(stores.map(s => s.area).filter(Boolean))].sort((a, b) => a.localeCompare(b, "bn"));

  const filtered = stores.filter(s => {
    if (search) {
      const q = search.toLowerCase();
      if (!s.display_name?.toLowerCase().includes(q) &&
          !s.tagline?.toLowerCase().includes(q) &&
          !s.area?.toLowerCase().includes(q) &&
          !s.category?.toLowerCase().includes(q)) return false;
    }
    if (activeCategory && s.category !== activeCategory) return false;
    if (activeArea && s.area !== activeArea) return false;
    return true;
  });

  return (
    <div className="sd-page">
      {/* Header */}
      <header className="sd-header">
        <div className="sd-header-inner">
          <a href="#/" className="sd-logo">
            <span className="sd-logo-dot" />B‑SMART
          </a>
          <span className="sd-tagline">বাংলাদেশের অনলাইন মার্কেটপ্লেস</span>
          <div className="sd-header-space" />
          <a href="#/" className="sd-back-link">← মূল পাতা</a>
        </div>
      </header>

      {/* Hero */}
      <div className="sd-hero">
        <div className="sd-hero-eyebrow">🇧🇩 Made in Bangladesh</div>
        <h1>সেরা দোকানগুলো এখন অনলাইনে</h1>
        <p>এলাকা ও ব্যবসার ধরন অনুযায়ী দোকান খুঁজে অর্ডার করুন</p>
        <div className="sd-search-wrap">
          <span className="sd-search-icon">🔍</span>
          <input
            className="sd-search"
            placeholder="দোকানের নাম, এলাকা বা ব্যবসার ধরন লিখুন…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        {!loading && (
          <div className="sd-hero-stats">
            <div className="sd-hero-stat">
              <div className="sd-hero-stat-num">{stores.length}</div>
              <div className="sd-hero-stat-label">দোকান</div>
            </div>
            <div className="sd-hero-stat">
              <div className="sd-hero-stat-num">{categories.length}</div>
              <div className="sd-hero-stat-label">বিভাগ</div>
            </div>
            <div className="sd-hero-stat">
              <div className="sd-hero-stat-num">{stores.filter(s => s.payment_cod).length}</div>
              <div className="sd-hero-stat-label">COD সুবিধা</div>
            </div>
          </div>
        )}
        {/* Wave */}
        <svg className="sd-hero-wave" viewBox="0 0 1440 36" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M0,36 C360,0 1080,0 1440,36 L1440,36 L0,36 Z" fill="#f4f7fb"/>
        </svg>
      </div>

      {areas.length > 1 && (
        <div className="sd-filters-wrap" style={{ paddingTop: 4 }}>
          <div className="sd-filters-label">এলাকা বেছে নিন</div>
          <div className="sd-filters">
            <button className={`sd-filter-btn${!activeArea ? " active" : ""}`} onClick={() => setActiveArea(null)}>সব এলাকা</button>
            {areas.map(area => <button key={area} className={`sd-filter-btn${activeArea === area ? " active" : ""}`} onClick={() => setActiveArea(activeArea === area ? null : area)}>📍 {area}</button>)}
          </div>
        </div>
      )}

      {/* Category filters */}
      <div className="sd-filters-wrap">
        <div className="sd-filters-label">বিভাগ বেছে নিন</div>
        <div className="sd-filters">
          <button className={`sd-filter-btn${!activeCategory ? " active" : ""}`} onClick={() => setActiveCategory(null)}>
            🏪 সব দোকান
          </button>
          {categories.map(c => (
            <button key={c} className={`sd-filter-btn${activeCategory === c ? " active" : ""}`}
              onClick={() => setActiveCategory(activeCategory === c ? null : c)}>
              {CAT_EMOJI[c]} {c}
            </button>
          ))}
        </div>
      </div>

      {/* Toolbar */}
      {!loading && (
        <div className="sd-toolbar">
          <p className="sd-count"><strong>{filtered.length}</strong> টি দোকান{activeCategory ? ` — ${activeCategory}` : ""}{activeArea ? ` — ${activeArea}` : ""}{search ? ` — "${search}"` : ""}</p>
        </div>
      )}

      {/* Content */}
      {loading ? (
        <div className="sd-loading">
          <div className="sd-spinner" />
          <span>দোকান লোড হচ্ছে…</span>
        </div>
      ) : loadError ? (
        <div className="sd-empty">
          <h2>দোকান লোড হয়নি</h2>
          <p>{loadError}</p>
          <button className="sd-filter-btn" onClick={loadStores}>আবার চেষ্টা করুন</button>
        </div>
      ) : filtered.length === 0 ? (
        <div className="sd-empty">
          <div className="sd-empty-icon">🔍</div>
          <h2>কোনো দোকান পাওয়া যায়নি</h2>
          <p>অন্য কীওয়ার্ড বা বিভাগ চেষ্টা করুন।</p>
        </div>
      ) : (
        <div className="sd-grid">
          {filtered.map(s => {
            const initial = s.display_name?.[0]?.toUpperCase() || "S";
            const accent = s.theme_color || "#0a8752";
            const emoji = CAT_EMOJI[s.category] || "🏪";
            return (
              <a key={s.slug} href={`#/store/${s.slug}`} className="sd-card">
                {/* Cover */}
                <div className="sd-card-cover" style={{ background: PRESET_GRAD[s.theme_preset] || PRESET_GRAD.clean }}>
                  <img src={storeCoverImage(s)} alt={`${s.display_name} দোকান`} loading="lazy" />
                  <div className="sd-card-cover-overlay" />
                  <div className="sd-card-logo" style={{ color: accent }}>
                    {s.logo_data_url ? <img src={s.logo_data_url} alt={s.display_name} /> : initial}
                  </div>
                </div>
                {/* Body */}
                <div className="sd-card-body">
                  <div className="sd-card-name">{s.display_name}</div>
                  <div className="sd-card-tagline">{s.tagline || " "}</div>
                  <div className="sd-card-chips">
                    {s.category && <span className="sd-chip sd-chip-cat">{emoji} {s.category}</span>}
                    {s.area && <span className="sd-chip sd-chip-area">📍 {s.area}</span>}
                  </div>
                </div>
                {/* Footer */}
                <div className="sd-card-footer">
                  <span className="sd-visit-btn">দোকান দেখুন <span>→</span></span>
                  <div className="sd-payment-row">
                    {s.payment_cod && <span className="sd-pay-badge" title="ক্যাশ অন ডেলিভারি">💵</span>}
                    {s.payment_bkash && <span className="sd-pay-badge" title="bKash">📱</span>}
                    {s.payment_nagad && <span className="sd-pay-badge" title="Nagad">💳</span>}
                  </div>
                </div>
              </a>
            );
          })}
        </div>
      )}

      {/* Footer */}
      <footer className="sd-footer">
        <p>Powered by <a href="#/">B-SMART</a> — AI-Powered Business Analytics for Bangladeshi SMEs</p>
      </footer>
    </div>
  );
}
