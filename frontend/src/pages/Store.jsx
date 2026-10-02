/**
 * Public storefront — completely separate visual identity from the B-SMART app.
 * One file, one SPA: view state machine drives home → product → checkout → done.
 * All store data fetched once at mount from /api/public/store/{orgId}.
 * Cart lives in component state (no account, no server persistence).
 * Dynamic theming: store's theme_color + theme_preset written as CSS vars on mount.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { explain } from "../errors";

// ─── Utility ─────────────────────────────────────────────────────────────────
const money = (v) => `৳${Number(v).toLocaleString("bn-BD", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
const clamp = (v, min, max) => Math.min(max, Math.max(min, v));

const STATUS_LABEL = {
  placed: { bn: "অর্ডার পেয়েছি", color: "#f59e0b" },
  confirmed: { bn: "নিশ্চিত হয়েছে", color: "#3b82f6" },
  ready: { bn: "প্রস্তুত", color: "#3b82f6" },
  dispatched: { bn: "পাঠানো হয়েছে", color: "#6366f1" },
  delivered: { bn: "ডেলিভারি হয়েছে", color: "#10b981" },
  cancelled: { bn: "বাতিল", color: "#ef4444" },
};

function hexToRgb(hex) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `${r} ${g} ${b}`;
}

// ─── Theme injection ──────────────────────────────────────────────────────────
function applyTheme(color = "#0a8752", preset = "clean") {
  const root = document.documentElement;
  root.style.setProperty("--sa", color);
  root.style.setProperty("--sa-rgb", hexToRgb(color));
  // Derive lighter tones
  root.style.setProperty("--sa-bg", `rgba(${hexToRgb(color)} / 0.08)`);
  root.style.setProperty("--sa-bg2", `rgba(${hexToRgb(color)} / 0.14)`);
  root.setAttribute("data-store-preset", preset);
}
function clearTheme() {
  const root = document.documentElement;
  root.style.removeProperty("--sa");
  root.style.removeProperty("--sa-rgb");
  root.style.removeProperty("--sa-bg");
  root.style.removeProperty("--sa-bg2");
  root.removeAttribute("data-store-preset");
}

// ─── Store CSS (scoped to .s-site) ───────────────────────────────────────────
const STORE_CSS = `
.s-site { --sa: #0a8752; --sa-rgb: 10 135 82; --sa-bg: rgba(10 135 82 / .08); --sa-bg2: rgba(10 135 82 / .14); }
.s-site *,
.s-site *::before,
.s-site *::after { box-sizing: border-box; }
.s-site { min-height: 100vh; font-family: system-ui, 'Segoe UI', sans-serif; background: var(--s-bg, #f8faf8); color: var(--s-ink, #0d1f16); }
.s-site img { max-width: 100%; }

/* ── Header ── */
.s-header { position: sticky; top: 0; z-index: 60; background: rgba(255 255 255 / .95); backdrop-filter: blur(14px); border-bottom: 1px solid #e5ede9; padding: 0 16px; }
.s-header-inner { max-width: 1100px; margin: 0 auto; height: 60px; display: flex; align-items: center; gap: 12px; }
.s-logo-wrap { display: flex; align-items: center; gap: 10px; text-decoration: none; flex: 0 0 auto; }
.s-logo-img { width: 36px; height: 36px; border-radius: 8px; object-fit: cover; }
.s-logo-placeholder { width: 36px; height: 36px; border-radius: 8px; background: var(--sa-bg2); display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 16px; color: var(--sa); }
.s-store-name { font-weight: 700; font-size: 15px; color: #0d1f16; }
.s-header-gap { flex: 1; }
.s-cart-btn { display: flex; align-items: center; gap: 7px; background: var(--sa); color: #fff; border: none; border-radius: 24px; padding: 8px 16px; font-size: 13.5px; font-weight: 600; cursor: pointer; transition: opacity .15s; }
.s-cart-btn:hover { opacity: .88; }
.s-cart-badge { background: #fff; color: var(--sa); border-radius: 50%; width: 20px; height: 20px; font-size: 12px; font-weight: 700; display: flex; align-items: center; justify-content: center; }

/* ── Hero ── */
.s-hero { background: linear-gradient(135deg, var(--sa-bg) 0%, rgba(255 255 255 / 0) 60%); padding: 56px 16px 48px; text-align: center; }
.s-hero-cover { width: 100%; max-height: 320px; object-fit: cover; border-radius: 16px; margin-bottom: 32px; }
.s-hero h1 { font-size: clamp(26px, 5vw, 44px); font-weight: 800; margin: 0 0 12px; color: #0d1f16; line-height: 1.15; }
.s-hero p { font-size: 16px; color: #4a6358; margin: 0 0 24px; max-width: 520px; margin-inline: auto; }
.s-trust-row { display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; margin-top: 16px; }
.s-trust-chip { background: var(--sa-bg); color: var(--sa); border-radius: 20px; padding: 5px 14px; font-size: 13px; font-weight: 500; }
.s-payment-chips { display: flex; gap: 8px; justify-content: center; flex-wrap: wrap; }
.s-payment-chip { border: 1px solid #d0e0d8; border-radius: 8px; padding: 4px 12px; font-size: 12px; font-weight: 600; color: #4a6358; background: #fff; }

/* ── Section heading ── */
.s-section { max-width: 1100px; margin: 0 auto; padding: 0 16px 56px; }
.s-section-head { display: flex; align-items: center; gap: 8px; margin-bottom: 20px; }
.s-section-head h2 { font-size: 20px; font-weight: 700; margin: 0; }
.s-section-head .s-badge { background: var(--sa-bg); color: var(--sa); border-radius: 6px; padding: 2px 10px; font-size: 12px; font-weight: 600; }

/* ── Product grid ── */
.s-product-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 16px; }
.s-product-card { background: #fff; border: 1px solid #e5ede9; border-radius: 12px; overflow: hidden; cursor: pointer; transition: box-shadow .18s, transform .18s; display: flex; flex-direction: column; }
.s-product-card:hover { box-shadow: 0 8px 24px rgba(0 0 0 / .1); transform: translateY(-2px); }
.s-product-img { width: 100%; aspect-ratio: 1; object-fit: cover; background: var(--sa-bg); display: flex; align-items: center; justify-content: center; font-size: 40px; color: var(--sa); }
.s-product-img-placeholder { width: 100%; aspect-ratio: 1; background: var(--sa-bg); display: flex; align-items: center; justify-content: center; font-size: 40px; color: var(--sa); }
.s-product-body { padding: 14px; flex: 1; display: flex; flex-direction: column; gap: 6px; }
.s-product-name { font-size: 14px; font-weight: 600; color: #0d1f16; line-height: 1.35; }
.s-product-unit { font-size: 12px; color: #6b8a7a; }
.s-product-price { font-size: 17px; font-weight: 700; color: var(--sa); }
.s-product-tags { display: flex; gap: 4px; flex-wrap: wrap; }
.s-tag { background: var(--sa-bg); color: var(--sa); border-radius: 4px; padding: 1px 7px; font-size: 11px; font-weight: 500; }
.s-stock-ok { font-size: 12px; color: #10b981; font-weight: 500; }
.s-stock-out { font-size: 12px; color: #ef4444; font-weight: 500; }
.s-add-btn { margin-top: auto; background: var(--sa); color: #fff; border: none; border-radius: 8px; padding: 9px; font-size: 13.5px; font-weight: 600; cursor: pointer; transition: opacity .15s; width: 100%; }
.s-add-btn:hover { opacity: .88; }
.s-add-btn:disabled { background: #d0e0d8; color: #8aaa97; cursor: not-allowed; }
.s-featured-badge { position: absolute; top: 8px; left: 8px; background: var(--sa); color: #fff; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 4px; }
.s-product-card-wrap { position: relative; }

/* ── Search / filter bar ── */
.s-filter-bar { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 20px; align-items: center; }
.s-search { flex: 1; min-width: 180px; padding: 10px 14px; border: 1px solid #d0e0d8; border-radius: 10px; font-size: 14px; outline: none; background: #fff; }
.s-search:focus { border-color: var(--sa); box-shadow: 0 0 0 3px var(--sa-bg); }
.s-filter-btn { padding: 9px 16px; border: 1px solid #d0e0d8; border-radius: 10px; font-size: 13px; font-weight: 500; background: #fff; cursor: pointer; white-space: nowrap; transition: background .12s, border-color .12s; }
.s-filter-btn.active { background: var(--sa-bg2); border-color: var(--sa); color: var(--sa); font-weight: 600; }

/* ── Product detail ── */
.s-detail { max-width: 900px; margin: 0 auto; padding: 24px 16px 56px; }
.s-back-btn { background: none; border: none; font-size: 14px; color: var(--sa); cursor: pointer; font-weight: 600; padding: 0; margin-bottom: 20px; display: flex; align-items: center; gap: 4px; }
.s-detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 32px; }
.s-detail-image { border-radius: 14px; overflow: hidden; aspect-ratio: 1; background: var(--sa-bg); display: flex; align-items: center; justify-content: center; font-size: 80px; color: var(--sa); }
.s-detail-image img { width: 100%; height: 100%; object-fit: cover; }
.s-detail-info { display: flex; flex-direction: column; gap: 14px; }
.s-detail-name { font-size: 24px; font-weight: 800; color: #0d1f16; margin: 0; line-height: 1.2; }
.s-detail-price { font-size: 28px; font-weight: 700; color: var(--sa); }
.s-detail-desc { font-size: 14px; color: #4a6358; line-height: 1.65; }
.s-qty-row { display: flex; align-items: center; gap: 12px; }
.s-qty-btn { width: 36px; height: 36px; border-radius: 50%; border: 2px solid var(--sa); background: #fff; color: var(--sa); font-size: 20px; font-weight: 700; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: background .12s; }
.s-qty-btn:hover { background: var(--sa-bg); }
.s-qty-num { font-size: 18px; font-weight: 700; min-width: 32px; text-align: center; }
.s-add-to-cart-btn { background: var(--sa); color: #fff; border: none; border-radius: 12px; padding: 14px 28px; font-size: 16px; font-weight: 700; cursor: pointer; transition: opacity .15s; width: 100%; }
.s-add-to-cart-btn:hover { opacity: .88; }
.s-add-to-cart-btn:disabled { background: #d0e0d8; color: #8aaa97; cursor: not-allowed; }

/* ── Cart drawer ── */
.s-cart-overlay { position: fixed; inset: 0; background: rgba(0 0 0 / .4); z-index: 90; }
.s-cart-drawer { position: fixed; right: 0; top: 0; bottom: 0; width: min(400px, 100vw); background: #fff; z-index: 91; box-shadow: -8px 0 40px rgba(0 0 0 / .15); display: flex; flex-direction: column; }
.s-cart-header { padding: 20px; border-bottom: 1px solid #e5ede9; display: flex; justify-content: space-between; align-items: center; }
.s-cart-header h3 { margin: 0; font-size: 18px; font-weight: 700; }
.s-cart-close { background: none; border: none; font-size: 22px; cursor: pointer; color: #4a6358; padding: 4px; }
.s-cart-body { flex: 1; overflow-y: auto; padding: 16px 20px; }
.s-cart-item { display: grid; grid-template-columns: 1fr auto; gap: 10px; padding: 14px 0; border-bottom: 1px solid #f0f5f2; align-items: center; }
.s-cart-item:last-child { border-bottom: none; }
.s-cart-item-name { font-size: 14px; font-weight: 600; color: #0d1f16; }
.s-cart-item-price { font-size: 13px; color: #4a6358; }
.s-cart-item-right { display: flex; flex-direction: column; align-items: flex-end; gap: 6px; }
.s-cart-item-total { font-size: 15px; font-weight: 700; color: var(--sa); }
.s-cart-qty-row { display: flex; align-items: center; gap: 8px; }
.s-cart-qty-btn { width: 28px; height: 28px; border-radius: 50%; border: 1.5px solid var(--sa); background: #fff; color: var(--sa); font-size: 16px; cursor: pointer; display: flex; align-items: center; justify-content: center; }
.s-cart-qty-num { font-size: 14px; font-weight: 600; min-width: 20px; text-align: center; }
.s-cart-footer { padding: 20px; border-top: 1px solid #e5ede9; }
.s-cart-total-row { display: flex; justify-content: space-between; margin-bottom: 16px; font-size: 15px; }
.s-cart-total-row strong { font-size: 18px; font-weight: 700; color: var(--sa); }
.s-checkout-btn { width: 100%; background: var(--sa); color: #fff; border: none; border-radius: 12px; padding: 14px; font-size: 16px; font-weight: 700; cursor: pointer; transition: opacity .15s; }
.s-checkout-btn:hover { opacity: .88; }
.s-empty-cart { text-align: center; color: #8aaa97; padding: 40px 20px; }

/* ── Checkout ── */
.s-checkout { max-width: 640px; margin: 0 auto; padding: 32px 16px 72px; }
.s-checkout h2 { font-size: 22px; font-weight: 800; margin: 0 0 24px; }
.s-form-group { margin-bottom: 18px; }
.s-form-group label { display: block; font-size: 13px; font-weight: 600; color: #4a6358; margin-bottom: 6px; }
.s-form-group label span { color: #ef4444; }
.s-input { width: 100%; padding: 11px 14px; border: 1.5px solid #d0e0d8; border-radius: 10px; font-size: 14px; outline: none; transition: border-color .15s; }
.s-input:focus { border-color: var(--sa); box-shadow: 0 0 0 3px var(--sa-bg); }
.s-textarea { width: 100%; padding: 11px 14px; border: 1.5px solid #d0e0d8; border-radius: 10px; font-size: 14px; outline: none; resize: vertical; min-height: 80px; transition: border-color .15s; }
.s-textarea:focus { border-color: var(--sa); box-shadow: 0 0 0 3px var(--sa-bg); }
.s-payment-options { display: grid; gap: 10px; }
.s-payment-option { border: 2px solid #d0e0d8; border-radius: 10px; padding: 14px 16px; cursor: pointer; display: flex; align-items: center; gap: 12px; transition: border-color .12s, background .12s; }
.s-payment-option.selected { border-color: var(--sa); background: var(--sa-bg); }
.s-payment-option-icon { font-size: 22px; }
.s-payment-option-label { font-size: 14px; font-weight: 600; }
.s-payment-option-desc { font-size: 12px; color: #6b8a7a; }
.s-order-summary { background: #f8faf8; border: 1px solid #e5ede9; border-radius: 12px; padding: 16px; margin-bottom: 24px; }
.s-order-summary h3 { font-size: 14px; font-weight: 700; margin: 0 0 12px; color: #4a6358; text-transform: uppercase; letter-spacing: .05em; }
.s-order-row { display: flex; justify-content: space-between; font-size: 14px; padding: 4px 0; }
.s-order-row.total { border-top: 1px solid #d0e0d8; margin-top: 8px; padding-top: 10px; font-weight: 700; font-size: 16px; }
.s-place-order-btn { width: 100%; background: var(--sa); color: #fff; border: none; border-radius: 12px; padding: 16px; font-size: 16px; font-weight: 700; cursor: pointer; transition: opacity .15s; }
.s-place-order-btn:hover { opacity: .88; }
.s-place-order-btn:disabled { background: #d0e0d8; color: #8aaa97; cursor: not-allowed; }
.s-error-box { background: #fef2f2; border: 1px solid #fca5a5; border-radius: 8px; padding: 12px 14px; font-size: 13.5px; color: #991b1b; margin-bottom: 16px; }
.s-min-order-note { background: var(--sa-bg); border-radius: 8px; padding: 10px 14px; font-size: 13px; color: var(--sa); font-weight: 500; margin-bottom: 16px; }

/* ── Confirmation ── */
.s-confirm { max-width: 540px; margin: 0 auto; padding: 48px 16px 72px; text-align: center; }
.s-confirm-icon { font-size: 64px; margin-bottom: 20px; }
.s-confirm h2 { font-size: 26px; font-weight: 800; margin: 0 0 12px; color: #0d1f16; }
.s-confirm p { font-size: 15px; color: #4a6358; margin: 0 0 16px; }
.s-confirm-token { font-family: monospace; font-size: 13px; background: var(--sa-bg); color: var(--sa); border-radius: 8px; padding: 10px 16px; display: inline-block; margin-bottom: 24px; word-break: break-all; }
.s-track-btn { display: inline-block; background: var(--sa); color: #fff; border: none; border-radius: 12px; padding: 14px 32px; font-size: 15px; font-weight: 700; cursor: pointer; text-decoration: none; transition: opacity .15s; }
.s-track-btn:hover { opacity: .88; }
.s-continue-btn { background: none; border: 2px solid var(--sa); color: var(--sa); border-radius: 12px; padding: 13px 28px; font-size: 15px; font-weight: 700; cursor: pointer; margin-top: 12px; transition: background .15s; }
.s-continue-btn:hover { background: var(--sa-bg); }

/* ── Footer ── */
.s-footer { background: #0d2018; color: #6b9a82; text-align: center; padding: 32px 16px; font-size: 13px; }
.s-footer a { color: #8aaa97; text-decoration: none; }
.s-footer-badge { display: inline-flex; align-items: center; gap: 6px; margin-top: 10px; font-size: 12px; opacity: .7; }

/* ── Loading / Error ── */
.s-loading { display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 60vh; gap: 16px; color: #4a6358; }
.s-spinner { width: 40px; height: 40px; border: 3px solid var(--sa-bg2); border-top-color: var(--sa); border-radius: 50%; animation: s-spin .7s linear infinite; }
@keyframes s-spin { to { transform: rotate(360deg); } }
.s-not-found { text-align: center; padding: 80px 16px; }
.s-not-found h2 { font-size: 22px; font-weight: 700; color: #0d1f16; }
.s-not-found p { color: #6b8a7a; }

/* ── Delivery note ── */
.s-delivery-note { background: var(--sa-bg); border-radius: 8px; padding: 12px 16px; font-size: 13.5px; color: #0d2018; margin-bottom: 20px; display: flex; gap: 10px; align-items: flex-start; }

/* ── Responsive ── */
@media (max-width: 640px) {
  .s-detail-grid { grid-template-columns: 1fr; }
  .s-product-grid { grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; }
  .s-hero { padding: 36px 16px 32px; }
}
@media (max-width: 400px) {
  .s-product-grid { grid-template-columns: 1fr 1fr; }
}
`;

function useInjectCSS(css) {
  useEffect(() => {
    const el = document.createElement("style");
    el.id = "bsmart-store-css";
    el.textContent = css;
    document.head.appendChild(el);
    return () => el.remove();
  }, []);
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function ProductCard({ product, onAdd, onView }) {
  const outOfStock = product.in_stock === false;
  return (
    <div className="s-product-card-wrap">
      {product.is_featured && <span className="s-featured-badge">স্টার</span>}
      <div className="s-product-card" onClick={() => onView(product)}>
        {product.image_data_url
          ? <img src={product.image_data_url} alt={product.name} className="s-product-img" />
          : <div className="s-product-img-placeholder">💊</div>
        }
        <div className="s-product-body">
          <div className="s-product-name">{product.name}</div>
          <div className="s-product-unit">{product.unit}</div>
          {product.price != null && <div className="s-product-price">{money(product.price)}</div>}
          {product.tags?.length > 0 && (
            <div className="s-product-tags">
              {product.tags.slice(0, 2).map(t => <span key={t} className="s-tag">{t}</span>)}
            </div>
          )}
          {product.in_stock !== undefined && (
            <span className={outOfStock ? "s-stock-out" : "s-stock-ok"}>
              {outOfStock ? "স্টক নেই" : "পাওয়া যাচ্ছে"}
            </span>
          )}
          <button
            className="s-add-btn"
            disabled={outOfStock}
            onClick={(e) => { e.stopPropagation(); if (!outOfStock) onAdd(product); }}
          >
            + কার্টে যোগ
          </button>
        </div>
      </div>
    </div>
  );
}

function CartDrawer({ cart, products, onClose, onQtyChange, onCheckout }) {
  const items = Object.entries(cart).filter(([, q]) => q > 0);
  const total = items.reduce((s, [id, q]) => s + q * (products[id]?.price || 0), 0);
  return (
    <>
      <div className="s-cart-overlay" onClick={onClose} />
      <div className="s-cart-drawer">
        <div className="s-cart-header">
          <h3>🛒 কার্ট</h3>
          <button className="s-cart-close" onClick={onClose}>✕</button>
        </div>
        <div className="s-cart-body">
          {items.length === 0 && <div className="s-empty-cart"><p style={{ fontSize: 32, margin: "0 0 10px" }}>🛒</p><p>কার্ট খালি</p></div>}
          {items.map(([pid, qty]) => {
            const p = products[pid];
            if (!p) return null;
            return (
              <div key={pid} className="s-cart-item">
                <div>
                  <div className="s-cart-item-name">{p.name}</div>
                  <div className="s-cart-item-price">{money(p.price)} / {p.unit}</div>
                </div>
                <div className="s-cart-item-right">
                  <div className="s-cart-item-total">{money(qty * p.price)}</div>
                  <div className="s-cart-qty-row">
                    <button className="s-cart-qty-btn" onClick={() => onQtyChange(pid, qty - 1)}>−</button>
                    <span className="s-cart-qty-num">{qty}</span>
                    <button className="s-cart-qty-btn" onClick={() => onQtyChange(pid, qty + 1)}>+</button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
        {items.length > 0 && (
          <div className="s-cart-footer">
            <div className="s-cart-total-row"><span>মোট</span><strong>{money(total)}</strong></div>
            <button className="s-checkout-btn" onClick={onCheckout}>অর্ডার করুন →</button>
          </div>
        )}
      </div>
    </>
  );
}

function CheckoutView({ store, cart, products, orgId, onBack, onDone }) {
  const [form, setForm] = useState({ name: "", phone: "", address: "", payment: store.payment_cod ? "cod" : "bkash", note: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const set = (k) => (e) => setForm(f => ({ ...f, [k]: e.target.value }));

  const items = Object.entries(cart).filter(([, q]) => q > 0);
  const subtotal = items.reduce((s, [id, q]) => s + q * (products[id]?.price || 0), 0);
  const meetsMin = !store.min_order_bdt || subtotal >= store.min_order_bdt;

  async function place(e) {
    e.preventDefault();
    if (!form.name.trim() || !form.phone.trim() || !form.address.trim()) {
      setError("নাম, ফোন নম্বর ও ঠিকানা দিতে হবে।");
      return;
    }
    if (!meetsMin) {
      setError(`সর্বনিম্ন অর্ডার ${money(store.min_order_bdt)} হতে হবে।`);
      return;
    }
    setBusy(true); setError("");
    try {
      const order = await api.placePublicOrder(orgId, {
        shipping_name: form.name,
        shipping_phone: form.phone,
        shipping_address: form.address + (form.note ? `\nনোট: ${form.note}` : ""),
        items: items.map(([product_id, quantity]) => ({ product_id, quantity })),
      });
      onDone(order);
    } catch (err) {
      setError(explain(err, { 404: "একটি পণ্য এখন পাওয়া যাচ্ছে না।", 409: "এই দোকান এখন অর্ডার নিচ্ছে না।" }));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="s-checkout">
      <button className="s-back-btn" onClick={onBack}>← কার্টে ফিরুন</button>
      <h2>ডেলিভারি তথ্য দিন</h2>

      <div className="s-order-summary">
        <h3>অর্ডার সারসংক্ষেপ</h3>
        {items.map(([pid, qty]) => (
          <div key={pid} className="s-order-row">
            <span>{products[pid]?.name} × {qty}</span>
            <span>{money(qty * (products[pid]?.price || 0))}</span>
          </div>
        ))}
        <div className="s-order-row total"><span>মোট</span><span>{money(subtotal)}</span></div>
      </div>

      {store.delivery_note && (
        <div className="s-delivery-note">📦 {store.delivery_note}</div>
      )}

      {!meetsMin && (
        <div className="s-min-order-note">সর্বনিম্ন অর্ডার: {money(store.min_order_bdt)}</div>
      )}

      {error && <div className="s-error-box">{error}</div>}

      <form onSubmit={place}>
        <div className="s-form-group">
          <label>আপনার নাম <span>*</span></label>
          <input className="s-input" value={form.name} onChange={set("name")} required />
        </div>
        <div className="s-form-group">
          <label>ফোন নম্বর <span>*</span></label>
          <input className="s-input" type="tel" value={form.phone} onChange={set("phone")} required inputMode="tel" />
        </div>
        <div className="s-form-group">
          <label>ডেলিভারি ঠিকানা <span>*</span></label>
          <textarea className="s-textarea" value={form.address} onChange={set("address")} required rows={3} />
        </div>
        <div className="s-form-group">
          <label>বিশেষ নির্দেশনা (ঐচ্ছিক)</label>
          <input className="s-input" value={form.note} onChange={set("note")} />
        </div>

        <div className="s-form-group">
          <label>পেমেন্ট পদ্ধতি <span>*</span></label>
          <div className="s-payment-options">
            {store.payment_cod && (
              <div className={`s-payment-option${form.payment === "cod" ? " selected" : ""}`} onClick={() => setForm(f => ({ ...f, payment: "cod" }))}>
                <span className="s-payment-option-icon">💵</span>
                <div><div className="s-payment-option-label">ক্যাশ অন ডেলিভারি</div><div className="s-payment-option-desc">ডেলিভারির সময় পেমেন্ট করুন</div></div>
              </div>
            )}
            {store.payment_bkash && (
              <div className={`s-payment-option${form.payment === "bkash" ? " selected" : ""}`} onClick={() => setForm(f => ({ ...f, payment: "bkash" }))}>
                <span className="s-payment-option-icon">📱</span>
                <div><div className="s-payment-option-label">bKash</div><div className="s-payment-option-desc">নিশ্চিত হওয়ার পর নম্বর পাবেন</div></div>
              </div>
            )}
            {store.payment_nagad && (
              <div className={`s-payment-option${form.payment === "nagad" ? " selected" : ""}`} onClick={() => setForm(f => ({ ...f, payment: "nagad" }))}>
                <span className="s-payment-option-icon">💳</span>
                <div><div className="s-payment-option-label">Nagad</div><div className="s-payment-option-desc">নিশ্চিত হওয়ার পর নম্বর পাবেন</div></div>
              </div>
            )}
          </div>
        </div>

        <button className="s-place-order-btn" type="submit" disabled={busy || !meetsMin}>
          {busy ? "অর্ডার দেওয়া হচ্ছে…" : `অর্ডার করুন — ${money(subtotal)}`}
        </button>
      </form>
    </div>
  );
}

function ConfirmationView({ order, orgId, onContinue }) {
  return (
    <div className="s-confirm">
      <div className="s-confirm-icon">✅</div>
      <h2>অর্ডার পেয়েছি!</h2>
      <p>আপনার অর্ডার নম্বর: <strong>{order.order_number}</strong></p>
      <p>দোকান থেকে নিশ্চিত হলে জানানো হবে। এই লিংক দিয়ে যেকোনো সময় অর্ডারের অবস্থা জানুন:</p>
      <div className="s-confirm-token">#{order.order_number}</div>
      <br />
      <a className="s-track-btn" href={`#/order-status/${orgId}/${order.access_token}`}>
        অর্ডার ট্র্যাক করুন
      </a>
      <br />
      <button className="s-continue-btn" onClick={onContinue}>আরও কেনাকাটা করুন</button>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────
export default function StorePage() {
  const { orgId } = useParams();
  const navigate = useNavigate();
  useInjectCSS(STORE_CSS);

  const [store, setStore] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  // view: "home" | "product" | "checkout" | "done"
  const [view, setView] = useState("home");
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [cart, setCart] = useState({}); // product_id → quantity
  const [cartOpen, setCartOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [activeTag, setActiveTag] = useState(null);
  const [confirmedOrder, setConfirmedOrder] = useState(null);
  const [detailQty, setDetailQty] = useState(1);

  useEffect(() => {
    if (!orgId) return;
    api.getPublicStore(orgId)
      .then(data => {
        setStore(data);
        applyTheme(data.theme_color, data.theme_preset);
      })
      .catch(e => setErr(explain(e, { 404: "এই স্টোরটি পাওয়া যায়নি বা এখন বন্ধ।" })))
      .finally(() => setLoading(false));
    return () => clearTheme();
  }, [orgId]);

  const products = store?.products || [];
  const productMap = useMemo(() => Object.fromEntries(products.map(p => [p.id, p])), [products]);
  const cartCount = useMemo(() => Object.values(cart).reduce((s, v) => s + v, 0), [cart]);
  const allTags = useMemo(() => {
    const tags = new Set();
    products.forEach(p => p.tags?.forEach(t => t && tags.add(t)));
    return [...tags];
  }, [products]);

  const filtered = useMemo(() => {
    let list = products.filter(p => p.in_stock !== false || true); // show OOS too, just greyed
    if (search) {
      const q = search.toLowerCase();
      list = list.filter(p => p.name.toLowerCase().includes(q) || p.sku?.toLowerCase().includes(q));
    }
    if (activeTag) list = list.filter(p => p.tags?.includes(activeTag));
    return list;
  }, [products, search, activeTag]);

  const featured = useMemo(() => products.filter(p => p.is_featured), [products]);

  function addToCart(product, qty = 1) {
    const max = product.max_order_qty || 99;
    setCart(c => ({ ...c, [product.id]: clamp((c[product.id] || 0) + qty, 0, max) }));
  }
  function setQty(pid, qty) {
    if (qty <= 0) {
      setCart(c => { const n = { ...c }; delete n[pid]; return n; });
    } else {
      const max = productMap[pid]?.max_order_qty || 99;
      setCart(c => ({ ...c, [pid]: clamp(qty, 1, max) }));
    }
  }

  function viewProduct(p) { setSelectedProduct(p); setDetailQty(1); setView("product"); window.scrollTo(0, 0); }

  function handleOrderDone(order) {
    setConfirmedOrder(order);
    setCart({});
    setView("done");
    window.scrollTo(0, 0);
  }

  if (loading) return (
    <div className="s-site"><div className="s-loading"><div className="s-spinner" /><p>স্টোর লোড হচ্ছে…</p></div></div>
  );
  if (err) return (
    <div className="s-site">
      <div className="s-not-found">
        <div style={{ fontSize: 56, marginBottom: 16 }}>🏪</div>
        <h2>স্টোর পাওয়া যায়নি</h2>
        <p>{err}</p>
      </div>
    </div>
  );
  if (!store) return null;

  const logoInitial = store.display_name?.[0]?.toUpperCase() || "S";

  return (
    <div className="s-site">
      {/* Header */}
      <header className="s-header">
        <div className="s-header-inner">
          <button className="s-logo-wrap" onClick={() => setView("home")} style={{ background: "none", border: "none", cursor: "pointer" }}>
            {store.logo_data_url
              ? <img src={store.logo_data_url} alt={store.display_name} className="s-logo-img" />
              : <div className="s-logo-placeholder">{logoInitial}</div>
            }
            <span className="s-store-name">{store.display_name}</span>
          </button>
          <div className="s-header-gap" />
          {cartCount > 0 && (
            <button className="s-cart-btn" onClick={() => setCartOpen(true)}>
              🛒 কার্ট <span className="s-cart-badge">{cartCount}</span>
            </button>
          )}
        </div>
      </header>

      {/* Cart drawer */}
      {cartOpen && (
        <CartDrawer
          cart={cart}
          products={productMap}
          onClose={() => setCartOpen(false)}
          onQtyChange={setQty}
          onCheckout={() => { setCartOpen(false); setView("checkout"); window.scrollTo(0, 0); }}
        />
      )}

      {/* Views */}
      {view === "home" && (
        <>
          {/* Hero */}
          <section className="s-hero">
            {store.cover_data_url && <img src={store.cover_data_url} alt="" className="s-hero-cover" />}
            <h1>{store.display_name}</h1>
            {store.tagline && <p>{store.tagline}</p>}
            <div className="s-trust-row">
              {store.category && <span className="s-trust-chip">🏷️ {store.category}</span>}
              {store.area && <span className="s-trust-chip">📍 {store.area}</span>}
              {store.show_hours && store.hours_json && (
                <span className="s-trust-chip">🕘 {store.hours_json?.mon || "খোলা আছে"}</span>
              )}
            </div>
            {(store.payment_cod || store.payment_bkash || store.payment_nagad) && (
              <div className="s-payment-chips" style={{ marginTop: 14 }}>
                <span style={{ fontSize: 12, color: "#6b8a7a", alignSelf: "center" }}>পেমেন্ট:</span>
                {store.payment_cod && <span className="s-payment-chip">💵 COD</span>}
                {store.payment_bkash && <span className="s-payment-chip">📱 bKash</span>}
                {store.payment_nagad && <span className="s-payment-chip">💳 Nagad</span>}
              </div>
            )}
          </section>

          {/* Featured */}
          {featured.length > 0 && (
            <div className="s-section">
              <div className="s-section-head">
                <h2>⭐ বিশেষ পণ্য</h2>
                <span className="s-badge">{featured.length}</span>
              </div>
              <div className="s-product-grid">
                {featured.map(p => <ProductCard key={p.id} product={p} onAdd={addToCart} onView={viewProduct} />)}
              </div>
            </div>
          )}

          {/* All products */}
          <div className="s-section">
            <div className="s-section-head">
              <h2>সব পণ্য</h2>
              <span className="s-badge">{products.length}</span>
            </div>
            <div className="s-filter-bar">
              <input
                className="s-search"
                placeholder="পণ্য খুঁজুন…"
                value={search}
                onChange={e => setSearch(e.target.value)}
              />
              {allTags.map(t => (
                <button key={t} className={`s-filter-btn${activeTag === t ? " active" : ""}`} onClick={() => setActiveTag(activeTag === t ? null : t)}>
                  {t}
                </button>
              ))}
            </div>
            {filtered.length === 0 && <p style={{ color: "#8aaa97", textAlign: "center", padding: "32px 0" }}>কোনো পণ্য পাওয়া যায়নি।</p>}
            <div className="s-product-grid">
              {filtered.map(p => <ProductCard key={p.id} product={p} onAdd={addToCart} onView={viewProduct} />)}
            </div>
          </div>
        </>
      )}

      {view === "product" && selectedProduct && (
        <div className="s-detail">
          <button className="s-back-btn" onClick={() => setView("home")}>← সব পণ্য</button>
          <div className="s-detail-grid">
            <div className="s-detail-image">
              {selectedProduct.image_data_url
                ? <img src={selectedProduct.image_data_url} alt={selectedProduct.name} />
                : "💊"
              }
            </div>
            <div className="s-detail-info">
              <h1 className="s-detail-name">{selectedProduct.name}</h1>
              <div className="s-product-unit">{selectedProduct.unit}</div>
              {selectedProduct.price != null && (
                <div className="s-detail-price">{money(selectedProduct.price)}</div>
              )}
              {selectedProduct.description && (
                <p className="s-detail-desc">{selectedProduct.description}</p>
              )}
              {selectedProduct.tags?.length > 0 && (
                <div className="s-product-tags">
                  {selectedProduct.tags.map(t => <span key={t} className="s-tag">{t}</span>)}
                </div>
              )}
              {selectedProduct.in_stock !== undefined && (
                <span className={selectedProduct.in_stock ? "s-stock-ok" : "s-stock-out"}>
                  {selectedProduct.in_stock ? "✓ পাওয়া যাচ্ছে" : "✗ স্টক নেই"}
                </span>
              )}
              <div className="s-qty-row">
                <button className="s-qty-btn" onClick={() => setDetailQty(q => Math.max(1, q - 1))}>−</button>
                <span className="s-qty-num">{detailQty}</span>
                <button className="s-qty-btn" onClick={() => setDetailQty(q => Math.min(selectedProduct.max_order_qty || 99, q + 1))}>+</button>
                <span style={{ fontSize: 13, color: "#6b8a7a", marginLeft: 4 }}>{selectedProduct.unit}</span>
              </div>
              <button
                className="s-add-to-cart-btn"
                disabled={selectedProduct.in_stock === false}
                onClick={() => { addToCart(selectedProduct, detailQty); setCartOpen(true); }}
              >
                {selectedProduct.price != null ? `কার্টে যোগ — ${money(detailQty * selectedProduct.price)}` : "কার্টে যোগ করুন"}
              </button>
            </div>
          </div>
        </div>
      )}

      {view === "checkout" && cartCount > 0 && (
        <CheckoutView
          store={store}
          cart={cart}
          products={productMap}
          orgId={orgId}
          onBack={() => { setCartOpen(true); setView("home"); }}
          onDone={handleOrderDone}
        />
      )}

      {view === "done" && confirmedOrder && (
        <ConfirmationView
          order={confirmedOrder}
          orgId={orgId}
          onContinue={() => { setView("home"); window.scrollTo(0, 0); }}
        />
      )}

      {/* Footer */}
      <footer className="s-footer">
        <p>{store.display_name}{store.area ? ` · ${store.area}` : ""}</p>
        {store.phone && <p>📞 {store.phone}</p>}
        {store.address && <p>📍 {store.address}</p>}
        <div className="s-footer-badge">
          <span>Powered by</span><strong style={{ color: "#8aaa97" }}>B-SMART</strong>
        </div>
      </footer>
    </div>
  );
}
