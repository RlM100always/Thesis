/**
 * Public storefront — completely separate visual identity from the B-SMART app.
 * One file, one SPA: view state machine drives home → product → checkout → done.
 * All store data fetched once at mount from /api/public/store/{orgId}.
 * Cart lives in component state (no account, no server persistence).
 * Dynamic theming: store's theme_color + theme_preset written as CSS vars on mount.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useParams } from "react-router-dom";
import { api } from "../api";
import { explain } from "../errors";
import { productImage, storeCoverImage } from "../storeImages";
import StoreCustomerPortal from "./StoreCustomerPortal";
import {readFavorites,toggleFavorite} from "../storefrontFavorites";
import {recentProducts,rememberProduct,toggleCompared,COMPARE_LIMIT} from "../storefrontDiscovery";
import StoreProductCompare from "../components/StoreProductCompare";

// ─── Utility ─────────────────────────────────────────────────────────────────
const money = (v) => `৳${Number(v).toLocaleString("bn-BD", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
const clamp = (v, min, max) => Math.min(max, Math.max(min, v));
const maxOrderQuantity = product => Math.max(0, Math.min(product.max_order_qty || 99, Number.isFinite(product.quantity) ? product.quantity : 99));

const STORE_PALETTES = {
  clean:  { bg: "#f7faf8", card: "#ffffff", ink: "#0d1f16", muted: "#5f7268", border: "#e1e9e4" },
  bold:   { bg: "#0d1f16", card: "#1a2e23", ink: "#f0f9f4", muted: "#b5cbbd", border: "#345342" },
  warm:   { bg: "#fdf6ed", card: "#fff8f0", ink: "#3d1d00", muted: "#806c58", border: "#eadfce" },
  fresh:  { bg: "#f0f9f4", card: "#ffffff", ink: "#064e3b", muted: "#527467", border: "#cfe8d9" },
  purple: { bg: "#faf5ff", card: "#ffffff", ink: "#3b0764", muted: "#766382", border: "#e9ddf4" },
  ocean:  { bg: "#eff6ff", card: "#ffffff", ink: "#1e3a5f", muted: "#5f7188", border: "#d6e2f1" },
};

function hexToRgb(hex) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `${r} ${g} ${b}`;
}

function contrastColor(hex) {
  const channels = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255).map(c => c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  const luminance = 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
  return luminance > 0.42 ? "#13231b" : "#ffffff";
}

// ─── Theme injection ──────────────────────────────────────────────────────────
function applyTheme(color = "#0a8752", preset = "clean") {
  const root = document.documentElement;
  const safeColor = /^#[0-9a-f]{6}$/i.test(color) ? color : "#0a8752";
  const palette = STORE_PALETTES[preset] || STORE_PALETTES.clean;
  root.style.setProperty("--store-accent", safeColor);
  root.style.setProperty("--store-accent-on", contrastColor(safeColor));
  root.style.setProperty("--store-accent-rgb", hexToRgb(safeColor));
  // Derive lighter tones
  root.style.setProperty("--store-accent-bg", `rgba(${hexToRgb(safeColor)} / 0.08)`);
  root.style.setProperty("--store-accent-bg2", `rgba(${hexToRgb(safeColor)} / 0.14)`);
  root.style.setProperty("--s-bg", palette.bg);
  root.style.setProperty("--s-card", palette.card);
  root.style.setProperty("--s-ink", palette.ink);
  root.style.setProperty("--s-muted", palette.muted);
  root.style.setProperty("--s-border", palette.border);
  root.setAttribute("data-store-preset", STORE_PALETTES[preset] ? preset : "clean");
}
function clearTheme() {
  const root = document.documentElement;
  root.style.removeProperty("--store-accent");
  root.style.removeProperty("--store-accent-on");
  root.style.removeProperty("--store-accent-rgb");
  root.style.removeProperty("--store-accent-bg");
  root.style.removeProperty("--store-accent-bg2");
  root.style.removeProperty("--s-bg");
  root.style.removeProperty("--s-card");
  root.style.removeProperty("--s-ink");
  root.style.removeProperty("--s-muted");
  root.style.removeProperty("--s-border");
  root.removeAttribute("data-store-preset");
}

// ─── Store CSS (scoped to .s-site) ───────────────────────────────────────────
const STORE_CSS = `
@import url('https://fonts.googleapis.com/css2?family=Hind+Siliguri:wght@400;500;600;700&display=swap');

/* ── Base ── */
.s-site { --sa: var(--store-accent, #0a8752); --sa-rgb: var(--store-accent-rgb, 10 135 82); --sa-bg: var(--store-accent-bg, rgba(10 135 82 / .08)); --sa-bg2: var(--store-accent-bg2, rgba(10 135 82 / .16)); }
.s-site *, .s-site *::before, .s-site *::after { box-sizing: border-box; }
.s-site { min-height: 100vh; font-family: 'Hind Siliguri', system-ui, sans-serif; background: var(--s-bg, #f7faf8); color: var(--s-ink, #0d1f16); }
.s-site img { max-width: 100%; }

/* ── Header ── */
.s-header { position: sticky; top: 0; z-index: 60; background: rgba(255,255,255,.93); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); border-bottom: 1px solid rgba(0,0,0,.07); padding: 0 20px; }
.s-header-inner { max-width: 1100px; margin: 0 auto; height: 62px; display: flex; align-items: center; gap: 12px; }
.s-logo-wrap { display: flex; align-items: center; gap: 10px; text-decoration: none; flex: 0 0 auto; background: none; border: none; cursor: pointer; padding: 0; }
.s-logo-img { width: 38px; height: 38px; border-radius: 10px; object-fit: cover; box-shadow: 0 2px 6px rgba(0,0,0,.12); }
.s-logo-placeholder { width: 38px; height: 38px; border-radius: 10px; background: var(--sa-bg2); display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 16px; color: var(--sa); }
.s-store-name { font-weight: 700; font-size: 15.5px; color: #0d1f16; letter-spacing: -.2px; }
.s-header-gap { flex: 1; }
.s-cart-btn { display: flex; align-items: center; gap: 8px; background: var(--sa); color: var(--store-accent-on, #fff); border: none; border-radius: 24px; padding: 9px 18px; font-size: 13.5px; font-weight: 700; font-family: inherit; cursor: pointer; transition: opacity .15s, transform .12s; box-shadow: 0 4px 12px rgba(var(--sa-rgb) / .35); }
.s-cart-btn:hover { opacity: .9; transform: translateY(-1px); }
.s-cart-badge { background: #fff; color: var(--sa); border-radius: 50%; width: 22px; height: 22px; font-size: 12px; font-weight: 800; display: flex; align-items: center; justify-content: center; }

/* ── Hero ── */
.s-hero { padding: 34px 20px 44px; text-align: center; background: linear-gradient(180deg, #fff 0%, var(--s-bg, #f7faf8) 100%); }
.s-hero h1 { font-size: clamp(24px, 5vw, 42px); font-weight: 800; margin: 0 0 10px; color: var(--s-ink, #0d1f16); line-height: 1.15; letter-spacing: -.5px; }
.s-hero p { font-size: 15.5px; color: #4a6358; margin: 0 0 20px; max-width: 480px; margin-inline: auto; line-height: 1.6; }
.s-trust-row { display: flex; gap: 10px; justify-content: center; flex-wrap: wrap; margin-top: 14px; }
.s-trust-chip { background: var(--sa-bg); color: var(--sa); border-radius: 20px; padding: 5px 14px; font-size: 13px; font-weight: 600; border: 1px solid rgba(var(--sa-rgb) / .15); }
.s-payment-chips { display: flex; gap: 8px; justify-content: center; flex-wrap: wrap; margin-top: 12px; }
.s-payment-chip { border: 1px solid #d0e0d8; border-radius: 8px; padding: 5px 12px; font-size: 12.5px; font-weight: 600; color: #4a6358; background: #fff; display: flex; align-items: center; gap: 5px; }

/* ── Section ── */
.s-section { max-width: 1100px; margin: 0 auto; padding: 0 20px 56px; }
.s-section-head { display: flex; align-items: center; gap: 10px; margin-bottom: 20px; }
.s-section-head h2 { font-size: 20px; font-weight: 800; margin: 0; letter-spacing: -.2px; }
.s-section-head .s-badge { background: var(--sa-bg); color: var(--sa); border-radius: 8px; padding: 3px 11px; font-size: 12px; font-weight: 700; }

/* ── Product grid ── */
.s-product-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 16px; }
.s-product-card-wrap { position: relative; }
.s-product-card { background: #fff; border: 1px solid #e8eeeb; border-radius: 16px; overflow: hidden; cursor: pointer; transition: box-shadow .22s cubic-bezier(.4,0,.2,1), transform .22s cubic-bezier(.4,0,.2,1); display: flex; flex-direction: column; }
.s-product-card:hover { box-shadow: 0 12px 32px rgba(0,0,0,.11); transform: translateY(-3px); }
.s-product-img { width: 100%; aspect-ratio: 1; object-fit: cover; }
.s-product-img-button { display: block; width: 100%; padding: 0; border: 0; background: #f1f5f2; cursor: pointer; }
.s-product-name-button { display: block; padding: 0; border: 0; background: transparent; color: var(--s-ink, #0d1f16); text-align: left; font: inherit; font-weight: 700; cursor: pointer; }
.s-product-img-placeholder { width: 100%; aspect-ratio: 1; background: linear-gradient(135deg, var(--sa-bg) 0%, rgba(var(--sa-rgb)/.05) 100%); display: flex; align-items: center; justify-content: center; font-size: 44px; }
.s-product-body { padding: 13px 14px 14px; flex: 1; display: flex; flex-direction: column; gap: 5px; }
.s-product-name { font-size: 14px; font-weight: 700; color: #0d1f16; line-height: 1.35; letter-spacing: -.1px; }
.s-product-unit { font-size: 11.5px; color: #7a9a8a; }
.s-product-price { font-size: 18px; font-weight: 800; color: var(--sa); letter-spacing: -.3px; }
.s-product-tags { display: flex; gap: 4px; flex-wrap: wrap; }
.s-tag { background: var(--sa-bg); color: var(--sa); border-radius: 5px; padding: 2px 7px; font-size: 11px; font-weight: 600; }
.s-stock-ok { font-size: 11.5px; color: #059669; font-weight: 600; display: flex; align-items: center; gap: 4px; }
.s-stock-out { font-size: 11.5px; color: #dc2626; font-weight: 600; }
.s-add-btn { margin-top: auto; background: var(--sa); color: var(--store-accent-on, #fff); border: none; border-radius: 10px; padding: 10px; font-size: 13.5px; font-weight: 700; font-family: inherit; cursor: pointer; transition: opacity .15s, transform .12s; width: 100%; }
.s-add-btn:hover { opacity: .88; transform: translateY(-1px); }
.s-add-btn:disabled { background: #e2ece7; color: #9ab8ac; cursor: not-allowed; transform: none; }
.s-featured-badge { position: absolute; top: 10px; right: 10px; background: linear-gradient(135deg, #f59e0b, #f97316); color: #fff; font-size: 11px; font-weight: 700; padding: 3px 9px; border-radius: 6px; box-shadow: 0 2px 8px rgba(249,115,22,.4); }

/* ── Search / filter bar ── */
.s-filter-bar { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; align-items: center; }
.s-search-wrap-inner { flex: 1; min-width: 180px; position: relative; }
.s-search-icon-inner { position: absolute; left: 13px; top: 50%; transform: translateY(-50%); font-size: 14px; pointer-events: none; }
.s-search { width: 100%; padding: 11px 14px 11px 38px; border: 1.5px solid #d8e8e0; border-radius: 12px; font-size: 14px; font-family: inherit; outline: none; background: #fff; transition: border-color .15s, box-shadow .15s; }
.s-search:focus { border-color: var(--sa); box-shadow: 0 0 0 3px var(--sa-bg); }
.s-filter-btn { padding: 9px 16px; border: 1.5px solid #d8e8e0; border-radius: 12px; font-size: 13px; font-weight: 500; font-family: inherit; background: #fff; cursor: pointer; white-space: nowrap; transition: all .12s; color: #4a6358; }
.s-filter-btn:hover { border-color: var(--sa); color: var(--sa); }
.s-filter-btn.active { background: var(--sa); border-color: var(--sa); color: #fff; font-weight: 700; box-shadow: 0 4px 10px rgba(var(--sa-rgb)/.3); }

/* ── Product detail page ── */
.s-detail { max-width: 900px; margin: 0 auto; padding: 28px 20px 64px; }
.s-back-btn { background: none; border: none; font-size: 14px; color: var(--sa); cursor: pointer; font-weight: 700; font-family: inherit; padding: 8px 0; margin-bottom: 24px; display: flex; align-items: center; gap: 5px; transition: gap .12s; }
.s-back-btn:hover { gap: 8px; }
.s-detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 36px; align-items: start; }
.s-detail-image { border-radius: 20px; overflow: hidden; aspect-ratio: 1; background: linear-gradient(135deg, var(--sa-bg), rgba(var(--sa-rgb)/.04)); display: flex; align-items: center; justify-content: center; font-size: 80px; box-shadow: 0 4px 24px rgba(0,0,0,.08); }
.s-detail-image img { width: 100%; height: 100%; object-fit: cover; }
.s-detail-info { display: flex; flex-direction: column; gap: 14px; }
.s-detail-name { font-size: 26px; font-weight: 800; color: #0d1f16; margin: 0; line-height: 1.2; letter-spacing: -.3px; }
.s-detail-price { font-size: 30px; font-weight: 800; color: var(--sa); letter-spacing: -.5px; }
.s-detail-desc { font-size: 14.5px; color: #4a6358; line-height: 1.7; }
.s-qty-row { display: flex; align-items: center; gap: 12px; }
.s-qty-btn { width: 38px; height: 38px; border-radius: 50%; border: 2px solid var(--sa); background: #fff; color: var(--sa); font-size: 20px; font-weight: 700; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: background .12s, transform .1s; }
.s-qty-btn:hover { background: var(--sa-bg); transform: scale(1.08); }
.s-qty-num { font-size: 20px; font-weight: 800; min-width: 36px; text-align: center; }
.s-add-to-cart-btn { background: var(--sa); color: #fff; border: none; border-radius: 14px; padding: 15px 28px; font-size: 16px; font-weight: 700; font-family: inherit; cursor: pointer; transition: opacity .15s, transform .12s, box-shadow .15s; width: 100%; box-shadow: 0 4px 16px rgba(var(--sa-rgb)/.35); }
.s-add-to-cart-btn:hover { opacity: .9; transform: translateY(-2px); box-shadow: 0 8px 24px rgba(var(--sa-rgb)/.4); }
.s-add-to-cart-btn:disabled { background: #e2ece7; color: #9ab8ac; cursor: not-allowed; transform: none; box-shadow: none; }

/* ── Cart drawer ── */
.s-cart-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.45); z-index: 90; backdrop-filter: blur(2px); animation: s-fade-in .2s ease; }
.s-cart-drawer { position: fixed; right: 0; top: 0; bottom: 0; width: min(420px, 100vw); background: #fff; z-index: 91; box-shadow: -12px 0 48px rgba(0,0,0,.16); display: flex; flex-direction: column; animation: s-slide-in .25s cubic-bezier(.4,0,.2,1); }
@keyframes s-slide-in { from { transform: translateX(100%); } to { transform: translateX(0); } }
@keyframes s-fade-in { from { opacity: 0; } to { opacity: 1; } }
.s-cart-header { padding: 22px 22px 18px; border-bottom: 1px solid #f0f5f2; display: flex; justify-content: space-between; align-items: center; }
.s-cart-header h3 { margin: 0; font-size: 19px; font-weight: 800; letter-spacing: -.2px; }
.s-cart-close { background: #f4f7f5; border: none; border-radius: 50%; width: 34px; height: 34px; font-size: 16px; cursor: pointer; color: #4a6358; display: flex; align-items: center; justify-content: center; transition: background .12s; }
.s-cart-close:hover { background: #e8eeeb; }
.s-cart-body { flex: 1; overflow-y: auto; padding: 12px 20px; }
.s-cart-item { display: grid; grid-template-columns: auto 1fr auto; gap: 12px; padding: 14px 0; border-bottom: 1px solid #f4f7f5; align-items: center; }
.s-cart-item:last-child { border-bottom: none; }
.s-cart-item-img { width: 48px; height: 48px; border-radius: 10px; background: var(--sa-bg); overflow: hidden; display: flex; align-items: center; justify-content: center; font-size: 20px; flex-shrink: 0; }
.s-cart-item-img img { width: 100%; height: 100%; object-fit: cover; }
.s-cart-item-name { font-size: 14px; font-weight: 700; color: #0d1f16; line-height: 1.3; }
.s-cart-item-price { font-size: 12.5px; color: #6b8a7a; }
.s-cart-item-right { display: flex; flex-direction: column; align-items: flex-end; gap: 8px; }
.s-cart-item-total { font-size: 15px; font-weight: 800; color: var(--sa); }
.s-cart-qty-row { display: flex; align-items: center; gap: 8px; background: #f4f7f5; border-radius: 20px; padding: 3px 6px; }
.s-cart-qty-btn { width: 26px; height: 26px; border-radius: 50%; border: none; background: #fff; color: var(--sa); font-size: 16px; font-weight: 700; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: background .1s; box-shadow: 0 1px 4px rgba(0,0,0,.1); }
.s-cart-qty-btn:hover { background: var(--sa-bg); }
.s-cart-qty-num { font-size: 14px; font-weight: 700; min-width: 22px; text-align: center; }
.s-cart-footer { padding: 18px 22px 22px; border-top: 1px solid #f0f5f2; }
.s-cart-subtotal-row { display: flex; justify-content: space-between; font-size: 13.5px; color: #6b8a7a; margin-bottom: 8px; }
.s-cart-total-row { display: flex; justify-content: space-between; font-size: 16px; font-weight: 800; margin-bottom: 18px; }
.s-cart-total-row strong { font-size: 20px; color: var(--sa); }
.s-checkout-btn { width: 100%; background: var(--sa); color: #fff; border: none; border-radius: 14px; padding: 15px; font-size: 16px; font-weight: 700; font-family: inherit; cursor: pointer; transition: opacity .15s, box-shadow .15s; box-shadow: 0 4px 16px rgba(var(--sa-rgb)/.35); }
.s-checkout-btn:hover { opacity: .9; box-shadow: 0 6px 20px rgba(var(--sa-rgb)/.45); }
.s-empty-cart { text-align: center; color: #a8bbb2; padding: 48px 20px; }
.s-empty-cart p:first-child { font-size: 40px; margin: 0 0 12px; }

/* ── Checkout ── */
.s-checkout { max-width: 620px; margin: 0 auto; padding: 36px 20px 80px; }
.s-checkout h2 { font-size: 24px; font-weight: 800; margin: 0 0 28px; letter-spacing: -.3px; }
.s-form-group { margin-bottom: 18px; }
.s-form-group label { display: block; font-size: 13px; font-weight: 700; color: #4a6358; margin-bottom: 7px; }
.s-form-group label span { color: #dc2626; }
.s-input { width: 100%; padding: 12px 15px; border: 1.5px solid #d0e0d8; border-radius: 12px; font-size: 14.5px; font-family: inherit; outline: none; transition: border-color .15s, box-shadow .15s; color: #0d1f16; }
.s-input:focus { border-color: var(--sa); box-shadow: 0 0 0 3px var(--sa-bg); }
.s-textarea { width: 100%; padding: 12px 15px; border: 1.5px solid #d0e0d8; border-radius: 12px; font-size: 14.5px; font-family: inherit; outline: none; resize: vertical; min-height: 88px; transition: border-color .15s, box-shadow .15s; color: #0d1f16; }
.s-textarea:focus { border-color: var(--sa); box-shadow: 0 0 0 3px var(--sa-bg); }
.s-payment-options { display: grid; gap: 10px; }
.s-payment-option { width: 100%; border: 2px solid #d8e8e0; border-radius: 14px; padding: 15px 17px; cursor: pointer; display: flex; align-items: center; gap: 14px; transition: border-color .15s, background .15s; font: inherit; text-align: left; color: inherit; }
.s-payment-option:hover { border-color: var(--sa); }
.s-payment-option.selected { border-color: var(--sa); background: var(--sa-bg); box-shadow: 0 0 0 1px rgba(var(--sa-rgb)/.15); }
.s-payment-option-icon { font-size: 24px; width: 40px; height: 40px; background: #fff; border-radius: 10px; display: flex; align-items: center; justify-content: center; box-shadow: 0 1px 4px rgba(0,0,0,.08); }
.s-provider-mark { min-width: 48px; height: 30px; padding: 0 6px; border-radius: 5px; display: inline-flex; align-items: center; justify-content: center; font: 800 12px Arial,sans-serif; letter-spacing: 0; background: #fff; border: 1px solid #e5e7eb; }
.s-provider-bkash { color: #d12053; }
.s-provider-nagad { color: #f15a24; }
.s-payment-option-label { font-size: 14.5px; font-weight: 700; }
.s-payment-option-desc { font-size: 12px; color: #6b8a7a; margin-top: 2px; }

/* ── bKash / Nagad branded payment UI ── */

/* bKash instruction card */
.bkash-instruction { background:linear-gradient(135deg,#fff0f4,#ffe8ef);border:2px solid #d12053;border-radius:16px;overflow:hidden;margin:16px 0; }
.bkash-instruction-header { background:#d12053;padding:14px 18px;display:flex;align-items:center;gap:10px; }
.bkash-instruction-header-logo { background:rgba(255,255,255,.2);border-radius:8px;padding:4px 10px; }
.bkash-instruction-header-text { color:#fff;font-weight:700;font-size:15px; }
.bkash-instruction-body { padding:16px 18px; }
.bkash-step { display:flex;align-items:flex-start;gap:12px;margin-bottom:14px; }
.bkash-step:last-child { margin-bottom:0; }
.bkash-step-num { width:26px;height:26px;background:#d12053;color:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:800;flex-shrink:0;margin-top:1px; }
.bkash-step-content { flex:1; }
.bkash-step-label { font-size:13px;color:#6b2a3a;font-weight:600;margin-bottom:2px; }
.bkash-number-display { background:#fff;border:2px solid #d12053;border-radius:10px;padding:10px 14px;display:flex;justify-content:space-between;align-items:center;margin-top:8px; }
.bkash-number-text { font-size:22px;font-weight:900;color:#d12053;letter-spacing:1px; }
.bkash-copy-btn { background:#d12053;color:#fff;border:none;border-radius:7px;padding:6px 12px;font-size:12px;font-weight:700;cursor:pointer;font-family:inherit; }
.bkash-amount-chip { background:#fff0f4;border:1.5px solid #d12053;border-radius:8px;padding:8px 12px;display:inline-block;margin-top:6px; }
.bkash-amount-value { font-size:20px;font-weight:900;color:#d12053; }
.bkash-ref-note { background:#fff;border-left:3px solid #d12053;padding:8px 12px;border-radius:0 8px 8px 0;margin-top:8px;font-size:13px;color:#4a1526; }

/* Nagad instruction card */
.nagad-instruction { background:linear-gradient(135deg,#fff5f0,#ffe8df);border:2px solid #f15a24;border-radius:16px;overflow:hidden;margin:16px 0; }
.nagad-instruction-header { background:linear-gradient(135deg,#f15a24,#e8400e);padding:14px 18px;display:flex;align-items:center;gap:10px; }
.nagad-instruction-header-text { color:#fff;font-weight:700;font-size:15px; }
.nagad-instruction-body { padding:16px 18px; }
.nagad-step { display:flex;align-items:flex-start;gap:12px;margin-bottom:14px; }
.nagad-step:last-child { margin-bottom:0; }
.nagad-step-num { width:26px;height:26px;background:#f15a24;color:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:800;flex-shrink:0;margin-top:1px; }
.nagad-step-content { flex:1; }
.nagad-step-label { font-size:13px;color:#6b2a10;font-weight:600;margin-bottom:2px; }
.nagad-number-display { background:#fff;border:2px solid #f15a24;border-radius:10px;padding:10px 14px;display:flex;justify-content:space-between;align-items:center;margin-top:8px; }
.nagad-number-text { font-size:22px;font-weight:900;color:#f15a24;letter-spacing:1px; }
.nagad-copy-btn { background:#f15a24;color:#fff;border:none;border-radius:7px;padding:6px 12px;font-size:12px;font-weight:700;cursor:pointer;font-family:inherit; }
.nagad-amount-chip { background:#fff5f0;border:1.5px solid #f15a24;border-radius:8px;padding:8px 12px;display:inline-block;margin-top:6px; }
.nagad-amount-value { font-size:20px;font-weight:900;color:#f15a24; }
.nagad-ref-note { background:#fff;border-left:3px solid #f15a24;padding:8px 12px;border-radius:0 8px 8px 0;margin-top:8px;font-size:13px;color:#4a2010; }

/* Payment option branded icons */
.s-payment-bkash-icon { background:#d12053;border-radius:9px;width:44px;height:44px;display:flex;align-items:center;justify-content:center;flex-shrink:0; }
.s-payment-nagad-icon { background:linear-gradient(135deg,#f15a24,#e8400e);border-radius:9px;width:44px;height:44px;display:flex;align-items:center;justify-content:center;flex-shrink:0; }
.s-payment-cod-icon { background:#10b981;border-radius:9px;width:44px;height:44px;display:flex;align-items:center;justify-content:center;flex-shrink:0;font-size:22px; }
.s-payment-option.bkash-selected { border-color:#d12053;background:#fff0f4;box-shadow:0 0 0 1px rgba(209,32,83,.15); }
.s-payment-option.nagad-selected { border-color:#f15a24;background:#fff5f0;box-shadow:0 0 0 1px rgba(241,90,36,.15); }

/* Screenshot upload styled */
.s-screenshot-upload { border:2px dashed #d0e0d8;border-radius:12px;padding:16px;text-align:center;cursor:pointer;transition:border-color .15s,background .15s;background:#fafcfa; }
.s-screenshot-upload:hover { border-color:var(--sa);background:var(--sa-bg); }
.s-screenshot-upload.bkash-upload { border-color:#d12053;background:#fff0f4; }
.s-screenshot-upload.nagad-upload { border-color:#f15a24;background:#fff5f0; }
.s-screenshot-preview { width:100%;max-height:180px;object-fit:contain;border-radius:8px;margin-top:8px;border:1px solid #e5e7eb; }
.s-order-summary { background: linear-gradient(135deg, var(--sa-bg) 0%, #f8faf8 100%); border: 1px solid rgba(var(--sa-rgb)/.15); border-radius: 14px; padding: 18px; margin-bottom: 24px; }
.s-order-summary h3 { font-size: 12px; font-weight: 700; margin: 0 0 14px; color: var(--sa); text-transform: uppercase; letter-spacing: .06em; }
.s-order-row { display: flex; justify-content: space-between; font-size: 14px; padding: 5px 0; }
.s-order-row.total { border-top: 1px solid rgba(var(--sa-rgb)/.15); margin-top: 8px; padding-top: 12px; font-weight: 800; font-size: 17px; }
.s-place-order-btn { width: 100%; background: var(--sa); color: var(--store-accent-on, #fff); border: none; border-radius: 14px; padding: 17px; font-size: 17px; font-weight: 700; font-family: inherit; cursor: pointer; transition: opacity .15s, transform .12s, box-shadow .15s; box-shadow: 0 4px 16px rgba(var(--sa-rgb)/.35); }
.s-place-order-btn:hover { opacity: .9; transform: translateY(-2px); }
.s-place-order-btn:disabled { background: #e2ece7; color: #9ab8ac; cursor: not-allowed; transform: none; box-shadow: none; }
.s-error-box { background: #fff5f5; border: 1px solid #fca5a5; border-radius: 10px; padding: 12px 16px; font-size: 13.5px; color: #b91c1c; margin-bottom: 18px; display: flex; gap: 8px; align-items: flex-start; }
.s-min-order-note { background: var(--sa-bg); border-radius: 10px; padding: 11px 15px; font-size: 13.5px; color: var(--sa); font-weight: 600; margin-bottom: 18px; display: flex; gap: 6px; align-items: center; }

/* ── Confirmation ── */
.s-confirm { max-width: 520px; margin: 0 auto; padding: 56px 20px 80px; text-align: center; }
.s-confirm-lottie { font-size: 72px; margin-bottom: 16px; animation: s-pop .5s cubic-bezier(.36,.07,.19,.97) both; }
@keyframes s-pop { 0% { transform: scale(0); } 60% { transform: scale(1.2); } 100% { transform: scale(1); } }
.s-confirm h2 { font-size: 28px; font-weight: 800; margin: 0 0 10px; color: #0d1f16; letter-spacing: -.4px; }
.s-confirm p { font-size: 15px; color: #4a6358; margin: 0 0 16px; line-height: 1.6; }
.s-confirm-token { font-family: 'Courier New', monospace; font-size: 14px; background: var(--sa-bg); color: var(--sa); border-radius: 10px; padding: 12px 20px; display: inline-block; margin-bottom: 24px; word-break: break-all; font-weight: 700; border: 1px solid rgba(var(--sa-rgb)/.2); }
.s-track-btn { display: inline-flex; align-items: center; gap: 6px; background: var(--sa); color: #fff; border: none; border-radius: 14px; padding: 15px 32px; font-size: 15.5px; font-weight: 700; font-family: inherit; cursor: pointer; text-decoration: none; transition: opacity .15s, transform .12s; box-shadow: 0 4px 16px rgba(var(--sa-rgb)/.35); }
.s-track-btn:hover { opacity: .9; transform: translateY(-2px); }
.s-continue-btn { display: block; background: none; border: 2px solid var(--sa); color: var(--sa); border-radius: 14px; padding: 14px 28px; font-size: 15px; font-weight: 700; font-family: inherit; cursor: pointer; margin: 12px auto 0; transition: background .15s; }
.s-continue-btn:hover { background: var(--sa-bg); }

/* ── Footer ── */
.s-footer { background: linear-gradient(135deg, #0a1f14 0%, #0d2018 100%); color: #4a6a56; text-align: center; padding: 36px 20px; font-size: 13px; }
.s-footer-inner { max-width: 1040px; margin: 0 auto; display: grid; grid-template-columns: 1.2fr 1fr 1fr; gap: 28px; text-align: left; }
.s-footer h3 { color: #f0f9f4; font-size: 15px; margin: 0 0 12px; }
.s-footer p { margin: 0 0 8px; line-height: 1.6; }
.s-footer-column { min-width: 0; }
.s-footer-details { margin: 10px 0; }
.s-footer-details summary { cursor: pointer; color: #a6c2b1; font-weight: 600; }
.s-footer-details ul { margin: 8px 0; padding-left: 18px; }
.s-footer-details li { margin: 4px 0; }
.s-footer-bottom { max-width: 1040px; margin: 24px auto 0; padding-top: 16px; border-top: 1px solid rgba(255,255,255,.1); display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.s-footer a { color: #6b9a82; text-decoration: none; font-weight: 600; transition: color .15s; }
.s-footer a:hover { color: var(--sa); }
.s-footer-badge { display: inline-flex; align-items: center; gap: 7px; margin-top: 12px; font-size: 12.5px; background: rgba(255,255,255,.05); border: 1px solid rgba(255,255,255,.08); border-radius: 20px; padding: 5px 14px; }
.s-footer-badge strong { color: #8aaa97; font-weight: 700; }

/* ── Loading / Error ── */
.s-loading { display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 60vh; gap: 16px; color: #4a6358; }
.s-spinner { width: 40px; height: 40px; border: 3px solid var(--sa-bg2); border-top-color: var(--sa); border-radius: 50%; animation: s-spin .7s linear infinite; }
@keyframes s-spin { to { transform: rotate(360deg); } }
.s-not-found { text-align: center; padding: 80px 16px; }
.s-not-found h2 { font-size: 22px; font-weight: 700; color: #0d1f16; }
.s-not-found p { color: #6b8a7a; }

/* ── Delivery note ── */
.s-delivery-note { background: var(--sa-bg); border-radius: 8px; padding: 12px 16px; font-size: 13.5px; color: #0d2018; margin-bottom: 20px; display: flex; gap: 10px; align-items: flex-start; }

/* ── Cover image with logo overlap ── */
.s-cover-wrap { position: relative; width: min(1120px, 100%); height: clamp(210px, 32vw, 340px); overflow: visible; margin: 0 auto 58px; border-radius: 22px; box-shadow: 0 22px 60px rgba(13,31,22,.16); }
.s-cover-img { width: 100%; height: 100%; object-fit: cover; display: block; border-radius: inherit; }
.s-cover-overlay { position: absolute; inset: 0; border-radius: inherit; background: linear-gradient(180deg, rgba(0,0,0,.06) 0%, rgba(0,0,0,.12) 48%, rgba(0,0,0,.46) 100%); box-shadow: inset 0 0 0 1px rgba(255,255,255,.35); pointer-events: none; }
.s-cover-logo-ring { position: absolute; bottom: -42px; left: 50%; transform: translateX(-50%); width: 84px; height: 84px; border-radius: 50%; border: 4px solid #fff; overflow: hidden; box-shadow: 0 8px 26px rgba(0,0,0,.22); background: #fff; }
.s-cover-logo-img { width: 100%; height: 100%; object-fit: cover; }
.s-cover-logo-fallback { width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; background: var(--sa-bg2); font-size: 28px; font-weight: 800; color: var(--sa); }
.s-hero-logo-center { display: flex; justify-content: center; margin-bottom: 16px; }
.s-hero-logo-solo { width: 80px; height: 80px; border-radius: 50%; object-fit: cover; border: 3px solid var(--sa-bg2); }
.s-hero-logo-placeholder { width: 80px; height: 80px; border-radius: 50%; background: var(--sa-bg2); display: flex; align-items: center; justify-content: center; font-size: 28px; font-weight: 800; color: var(--sa); }
.s-chip-open { background: #d1fae5 !important; color: #065f46 !important; }
.s-chip-closed { background: #fee2e2 !important; color: #991b1b !important; }

/* ── WhatsApp share button ── */
.s-wa-btn { display: flex; align-items: center; justify-content: center; width: 38px; height: 38px; border-radius: 50%; background: #25d366; color: #fff; font-size: 16px; text-decoration: none; transition: opacity .15s; flex-shrink: 0; }
.s-wa-btn:hover { opacity: .85; }

/* ── Floating cart button (mobile) ── */
.s-float-cart { position: fixed; bottom: 20px; right: 20px; z-index: 80; background: var(--sa); color: var(--store-accent-on, #fff); border: none; border-radius: 50px; padding: 14px 20px; font-size: 18px; font-weight: 700; box-shadow: 0 4px 20px rgba(0,0,0,.25); cursor: pointer; display: flex; align-items: center; gap: 8px; transition: transform .15s, box-shadow .15s; }
.s-float-cart:hover { transform: translateY(-2px); box-shadow: 0 6px 24px rgba(0,0,0,.3); }
.s-float-cart-count { background: #fff; color: var(--sa); border-radius: 50%; width: 24px; height: 24px; font-size: 13px; font-weight: 800; display: flex; align-items: center; justify-content: center; }

/* ── Preset themes ── */
[data-store-preset="warm"] { --s-bg: #fdf6ec; --s-ink: #1a0a00; }
[data-store-preset="dark"] { --s-bg: #0d1b2a; --s-ink: #e8f0f5; }
[data-store-preset="dark"] .s-header { background: rgba(13 27 42 / .95); border-bottom-color: #1e3a50; }
[data-store-preset="dark"] .s-product-card { background: #1a2e40; border-color: #1e3a50; }
[data-store-preset="dark"] .s-product-name { color: #e8f0f5; }
[data-store-preset="dark"] .s-product-unit { color: #7a9bb0; }
[data-store-preset="dark"] .s-cart-drawer { background: #1a2e40; }
[data-store-preset="dark"] .s-cart-header { border-bottom-color: #1e3a50; }
[data-store-preset="dark"] .s-cart-header h3 { color: #e8f0f5; }
[data-store-preset="pharmacy"] { --s-bg: #f0faf5; --s-ink: #0a2518; }
[data-store-preset="fashion"] { --s-bg: #fafafa; --s-ink: #1a0a14; }

/* ── Product modal (sheet) ── */
.s-modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,.45); z-index: 100; display: flex; align-items: flex-end; justify-content: center; }
@media (min-width: 641px) { .s-modal-backdrop { align-items: center; } }
.s-modal { background: #fff; border-radius: 20px 20px 0 0; width: 100%; max-width: 640px; max-height: 92vh; overflow-y: auto; padding: 0; }
@media (min-width: 641px) { .s-modal { border-radius: 20px; max-height: 80vh; } }
.s-modal-handle { width: 40px; height: 4px; background: #d0e0d8; border-radius: 2px; margin: 12px auto 0; }
.s-modal-inner { padding: 20px 20px 32px; }
.s-modal-img { width: 100%; aspect-ratio: 16/9; object-fit: cover; border-radius: 12px; background: var(--sa-bg); display: flex; align-items: center; justify-content: center; font-size: 64px; margin-bottom: 16px; overflow: hidden; }
.s-modal-img img { width: 100%; height: 100%; object-fit: cover; }
.s-modal-close { float: right; background: #f0f5f2; border: none; border-radius: 50%; width: 32px; height: 32px; font-size: 16px; cursor: pointer; display: flex; align-items: center; justify-content: center; margin-left: 8px; }
.s-modal-full-btn { background: transparent; border: 0; color: var(--sa); font: inherit; font-weight: 700; cursor: pointer; padding: 8px 0; }

/* ── Sticky cart bar ── */
.s-sticky-bar { position: fixed; bottom: 0; left: 0; right: 0; z-index: 70; background: var(--sa); color: #fff; padding: 14px 20px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 -4px 20px rgba(0,0,0,.15); cursor: pointer; transition: transform .2s; }
.s-sticky-bar:hover { filter: brightness(1.06); }
.s-sticky-bar-left { font-size: 15px; font-weight: 600; }
.s-sticky-bar-right { font-size: 15px; font-weight: 700; }

/* ── Category tab strip ── */
.s-cat-strip { display: flex; gap: 8px; overflow-x: auto; padding: 0 0 2px; scrollbar-width: none; margin-bottom: 16px; }
.s-cat-strip::-webkit-scrollbar { display: none; }
.s-cat-tab { flex-shrink: 0; padding: 8px 16px; border: 1.5px solid #d0e0d8; border-radius: 20px; font-size: 13px; font-weight: 500; background: #fff; cursor: pointer; white-space: nowrap; transition: all .12s; }
.s-cat-tab.active { background: var(--sa); border-color: var(--sa); color: #fff; font-weight: 600; }

/* ── Inline qty stepper on card ── */
.s-card-qty-row { display: flex; align-items: center; gap: 6px; margin-top: 6px; }
.s-card-qty-btn { width: 28px; height: 28px; border-radius: 50%; border: 1.5px solid var(--sa); background: #fff; color: var(--sa); font-size: 15px; font-weight: 700; cursor: pointer; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.s-card-qty-num { font-size: 14px; font-weight: 700; min-width: 20px; text-align: center; color: #0d1f16; }
.s-card-in-cart { font-size: 11px; color: var(--sa); font-weight: 600; }

/* ── Search result count ── */
.s-result-count { font-size: 12px; color: #8aaa97; margin-bottom: 12px; }
.s-store-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin: 0 0 16px; }
.s-sort-select { min-width: 180px; padding: 9px 12px; border: 1px solid #d8e3dd; border-radius: 8px; background: #fff; color: #263b31; font: inherit; }
.s-store-nav { display: flex; align-items: center; gap: 18px; }
.s-store-nav button { border: 0; background: transparent; color: #52655b; font-family: inherit; font-size: 13px; font-weight: 600; cursor: pointer; padding: 8px 0; }
.s-store-nav button:hover { color: var(--sa); }
.s-store-benefits { max-width: 1060px; margin: 0 auto 36px; padding: 0 20px; display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: 12px; }
.s-store-benefit { border: 1px solid #e1e9e4; border-radius: 8px; background: #fff; padding: 14px 16px; display: flex; align-items: flex-start; gap: 10px; color: #52655b; font-size: 12.5px; line-height: 1.5; }
.s-store-benefit strong { display: block; color: #1f3027; font-size: 13px; margin-bottom: 2px; }
.s-stock-low { color: #b45309; font-size: 11.5px; font-weight: 700; }
.s-product-card { cursor: default; }
.s-product-open { cursor: pointer; }
.s-contact-price { color: #475569; font-size: 13px; font-weight: 700; }
button.s-contact-price { background: transparent; border: 0; padding: 4px 0; text-align: left; cursor: pointer; font: inherit; font-weight: 700; color: var(--sa); }

/* ── Responsive ── */
@media (max-width: 640px) {
  .s-header-inner { height: auto; min-height: 60px; flex-wrap: wrap; padding: 8px 0; }
  .s-store-nav { display: flex; order: 5; flex-basis: 100%; justify-content: space-around; border-top: 1px solid var(--s-border, #e1e9e4); padding-top: 4px; }
  .s-hero { padding: 24px 12px 30px; }
  .s-cover-wrap { height: 190px; border-radius: 18px; margin-bottom: 52px; }
  .s-store-benefits { grid-template-columns: 1fr; gap: 8px; }
  .s-store-toolbar { align-items: stretch; flex-direction: column; }
  .s-sort-select { width: 100%; }
  .s-footer-inner { grid-template-columns: 1fr; gap: 20px; }
  .s-footer-bottom { align-items: flex-start; flex-direction: column; }
  .s-detail-grid { grid-template-columns: 1fr; }
  .s-product-grid { grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; }
  .s-hero { padding: 36px 16px 32px; }
  .s-float-cart { bottom: 16px; right: 16px; padding: 12px 16px; font-size: 16px; }
}
@media (max-width: 400px) {
  .s-product-grid { grid-template-columns: 1fr 1fr; }
}
@media (min-width: 641px) {
  .s-float-cart { display: none; }
}

/* Keep store colors tied to the merchant accent without the artificial glow. */
.s-hero { background: linear-gradient(180deg, #fff 0%, var(--s-bg, #f7faf8) 100%); }
.s-header, .s-product-card, .s-store-benefit, .s-modal, .s-cart-drawer { background-color: var(--s-card, #fff); }
.s-store-name, .s-product-name, .s-detail-name, .s-section-head h2, .s-cart-header h3,
.s-cart-item-name, .s-checkout h2, .s-form-group label, .s-order-row, .s-confirm h2 { color: var(--s-ink, #0d1f16); }
.s-product-card, .s-store-benefit, .s-search, .s-filter-btn, .s-cat-tab, .s-input, .s-textarea,
.s-payment-option, .s-order-summary, .s-cart-item, .s-cart-header, .s-cart-footer { border-color: var(--s-border, #e1e9e4); }
.s-product-unit, .s-detail-desc, .s-form-group label, .s-payment-option-desc, .s-cart-item-price,
.s-cart-subtotal-row, .s-confirm p { color: var(--s-muted, #5f7268); }
.s-store-benefit { color: var(--s-muted, #5f7268); }
.s-store-benefit strong, .s-modal h2 { color: var(--s-ink, #0d1f16); }
.s-cart-btn, .s-add-btn, .s-add-to-cart-btn, .s-checkout-btn, .s-place-order-btn, .s-track-btn,
.s-filter-btn.active, .s-cat-tab.active, .s-sticky-bar, .s-float-cart { color: var(--store-accent-on, #fff); }
.s-search, .s-filter-btn, .s-cat-tab, .s-input, .s-textarea, .s-qty-btn { background-color: var(--s-card, #fff); color: var(--s-ink, #0d1f16); }
.s-order-summary { background: var(--s-card, #fff); }
.s-cart-qty-row, .s-cart-close { background-color: color-mix(in srgb, var(--s-card, #fff) 88%, var(--s-border, #e1e9e4)); }
.s-cart-qty-btn { background: var(--s-card, #fff); }
.s-cart-item-name, .s-card-qty-num { color: var(--s-ink, #0d1f16); }
.s-cart-btn, .s-checkout-btn, .s-add-to-cart-btn, .s-place-order-btn, .s-track-btn, .s-filter-btn.active {
  box-shadow: none;
}
.s-product-card:hover { box-shadow: 0 4px 14px rgba(13,31,22,.09); transform: translateY(-1px); }
.s-add-to-cart-btn:hover, .s-place-order-btn:hover, .s-track-btn:hover { box-shadow: none; transform: none; }

/* Storefront premium refresh: merchant theme-aware, mobile-first, no invented ratings. */
.s-site {background:var(--s-bg);color:var(--s-ink);letter-spacing:0}
.s-site :is(button,a,input,select,textarea):focus-visible{outline:3px solid var(--sa);outline-offset:3px}
.s-header{background:color-mix(in srgb,var(--s-card) 94%,transparent);border-bottom:1px solid var(--s-border);box-shadow:0 2px 18px rgba(13,31,22,.045)}
.s-header-inner{max-width:1180px;min-height:70px}
.s-store-name{color:var(--s-ink);font-size:16px;font-weight:800}
.s-logo-img,.s-logo-placeholder{border-radius:13px;width:42px;height:42px}
.s-cart-btn{border-radius:14px;padding:10px 16px}
.s-hero{max-width:1180px;margin:22px auto 30px;padding:18px 24px 26px;border:1px solid var(--s-border);border-radius:26px;background:var(--s-card);box-shadow:0 12px 42px rgba(13,31,22,.045)}
.s-hero h1{color:var(--s-ink);font-size:clamp(25px,4vw,42px)}
.s-hero p{color:var(--s-muted)}
.s-hero-metrics{display:flex;gap:0;justify-content:center;align-items:stretch;max-width:540px;margin:16px auto 8px;background:var(--s-bg);border:1px solid var(--s-border);border-radius:16px;padding:12px 2px}
.s-hero-metrics div{display:grid;align-content:center;gap:3px;flex:1;min-width:0;padding:2px 9px}
.s-hero-metrics div+div{border-left:1px solid var(--s-border)}
.s-hero-metrics strong{font-size:19px;color:var(--s-ink);line-height:1.2}
.s-hero-metrics span{font-size:11px;color:var(--s-muted);line-height:1.3}
.s-trust-chip{border-radius:10px;padding:7px 11px}
.s-section{max-width:1180px;padding-bottom:32px}
.s-section-head{justify-content:space-between}
.s-section-head h2{font-size:clamp(18px,2.5vw,23px)}
.s-product-grid{grid-template-columns:repeat(auto-fill,minmax(195px,1fr));gap:16px}
.s-product-card-wrap{min-width:0}
.s-product-card{height:100%;border:1px solid var(--s-border);border-radius:17px;background:var(--s-card);box-shadow:0 5px 18px rgba(13,31,22,.04);overflow:hidden}
.s-product-card:hover{box-shadow:0 10px 32px rgba(13,31,22,.12);transform:translateY(-3px)}
.s-product-img-button{overflow:hidden;display:block;background:var(--s-bg)}
.s-product-img{aspect-ratio:1.05;object-fit:cover;transition:transform .25s ease}
.s-product-card:hover .s-product-img{transform:scale(1.045)}
.s-product-body{padding:14px;gap:7px}
.s-product-name-button{font-size:14px;font-weight:800;min-height:38px;line-height:1.4}
.s-product-name-button:hover{color:var(--sa)}
.s-product-unit{color:var(--s-muted)}
.s-product-price{font-size:20px}
.s-featured-badge{top:10px;right:10px;border-radius:9px;z-index:4}
.s-product-favorite{position:absolute;z-index:7;top:11px;left:11px;width:38px;height:38px;display:grid;place-items:center;background:color-mix(in srgb,var(--s-card) 94%,transparent);border:1px solid var(--s-border);color:var(--s-ink);border-radius:13px;font-size:25px;cursor:pointer;line-height:1;box-shadow:0 2px 10px rgba(0,0,0,.11)}
.s-product-favorite:hover,.s-product-favorite.selected{color:#e11d48;background:color-mix(in srgb,#ffe3eb 80%,var(--s-card))}
.s-detail-title-row{display:flex;align-items:flex-start;gap:12px;justify-content:space-between}
.s-detail-favorite{flex:none;width:46px;height:46px;border:1px solid var(--s-border);background:var(--s-card);color:var(--s-ink);border-radius:14px;font-size:26px;cursor:pointer}
.s-detail-favorite.selected{color:#e11d48}
.s-shopping-filters{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:6px 0 14px}
.s-shopping-filter,.s-shopping-clear{border:1px solid var(--s-border);border-radius:999px;padding:9px 15px;background:var(--s-card);color:var(--s-ink);font-family:inherit;font-size:13px;font-weight:700;cursor:pointer}
.s-shopping-filter.active{background:var(--sa-bg2);border-color:var(--sa);color:var(--sa)}
.s-shopping-clear{border:0;background:transparent;color:var(--sa);text-decoration:underline}
.s-search{background:var(--s-card);color:var(--s-ink);border-color:var(--s-border);border-radius:15px}
.s-cat-tab{border-radius:12px}
.s-store-benefits{max-width:1180px}
.s-store-benefit{border-radius:15px}
.s-store-toolbar{gap:10px}
.s-sort-select{background:var(--s-card);color:var(--s-ink);border-color:var(--s-border);border-radius:12px}
.s-add-btn,.s-add-to-cart-btn{border-radius:12px;min-height:44px}
.s-sticky-bar{border:0;font:inherit;cursor:pointer}
.s-detail{max-width:1060px}
@media(max-width:680px){
 .s-header-inner{min-height:64px}
 .s-hero{margin:10px 10px 24px;padding:12px 12px 20px;border-radius:19px}
 .s-hero h1{font-size:26px}
 .s-hero-metrics{margin:14px auto 8px}
 .s-hero-metrics strong{font-size:16px}
 .s-hero-metrics span{font-size:10px}
 .s-section{padding:0 12px 30px}
 .s-product-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
 .s-product-body{padding:11px;gap:5px}
 .s-product-name-button{font-size:13px}
 .s-product-price{font-size:17px}
 .s-product-favorite{width:35px;height:35px;font-size:22px}
 .s-featured-badge{font-size:10px;top:10px}
 .s-shopping-filter{padding:8px 11px;font-size:12px}
 .s-section-head{margin-bottom:14px}
 .s-store-benefits{margin:0 10px 24px}
 .s-detail{padding:18px 13px 70px}
}
@media(max-width:350px){
 .s-product-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}
 .s-product-body{padding:9px}
 .s-product-favorite{width:32px;height:32px}
}
@media(prefers-reduced-motion:reduce){.s-product-card,.s-product-img{transition:none}.s-product-card:hover{transform:none}}

/* Store v11: comparison sheet, recent browsing, owner-published information */
.s-announcement{padding:10px 15px;background:var(--sa);color:var(--store-accent-on,#fff);text-align:center;font-size:13px;font-weight:700;line-height:1.55;overflow-wrap:anywhere;display:flex;gap:8px;justify-content:center;align-items:center}
.s-announcement span{font-size:18px;opacity:.9}
.s-product-compare{display:inline-flex;align-items:center;justify-content:center;gap:6px;border:1px solid var(--s-border);background:var(--s-card);color:var(--s-ink);border-radius:9px;font:inherit;font-size:12px;font-weight:700;padding:7px 10px;cursor:pointer;width:100%}
.s-product-compare:hover,.s-product-compare.selected{background:var(--sa-bg);border-color:var(--sa);color:var(--sa)}
.s-product-compare:disabled{opacity:.43;cursor:not-allowed}
.s-compare-tray{display:flex;align-items:center;justify-content:space-between;gap:14px;margin:10px 0 16px;padding:13px 16px;border:1px solid var(--s-border);border-radius:15px;background:var(--s-card);box-shadow:0 3px 14px rgba(0,0,0,.04)}
.s-compare-tray>div:first-child{display:grid;gap:2px;min-width:0}
.s-compare-tray strong{font-size:14px;color:var(--s-ink)}
.s-compare-tray span{font-size:12px;color:var(--s-muted)}
.s-compare-tray-actions{display:flex;align-items:center;gap:8px}
.s-compare-open{border:0;border-radius:11px;background:var(--sa);color:var(--store-accent-on,#fff);font:inherit;font-size:13px;font-weight:700;padding:10px 13px;cursor:pointer;white-space:nowrap}
.s-compare-open:disabled{opacity:.45;cursor:not-allowed}
.s-compare-overlay{position:fixed;inset:0;background:rgba(0,0,0,.55);backdrop-filter:blur(4px);z-index:160;display:flex;justify-content:center;align-items:center;padding:20px}
.s-compare-dialog{background:var(--s-card);color:var(--s-ink);width:min(960px,100%);max-height:min(89vh,880px);overflow:auto;border-radius:23px;box-shadow:0 20px 75px #0003;padding:20px}
.s-compare-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:18px}
.s-compare-heading h2{font-size:23px;line-height:1.2;margin:3px 0;color:var(--s-ink)}
.s-compare-heading small{font-size:10px;font-weight:800;color:var(--sa);letter-spacing:.14em}
.s-compare-heading p{font-size:12px;color:var(--s-muted);margin:5px 0}
.s-compare-close{width:38px;height:38px;flex:none;border:1px solid var(--s-border);border-radius:12px;background:var(--s-bg);color:var(--s-ink);cursor:pointer}
.s-compare-columns{display:grid;gap:12px;min-width:max-content}
.s-compare-item{background:var(--s-bg);border:1px solid var(--s-border);border-radius:15px;padding:13px;position:relative;display:flex;flex-direction:column;gap:9px;min-width:180px;max-width:300px}
.s-compare-picture{border:0;border-radius:10px;overflow:hidden;padding:0;background:var(--s-card);cursor:pointer}
.s-compare-picture img{width:100%;height:135px;object-fit:cover;display:block}
.s-compare-item strong{font-size:14px;min-height:36px;line-height:1.35}
.s-compare-price{font-size:17px;font-weight:800;color:var(--sa)}
.s-compare-remove{position:absolute;z-index:3;right:18px;top:18px;min-width:30px;height:30px;border:0;border-radius:9px;cursor:pointer;font-size:21px;line-height:1;color:var(--s-ink);background:color-mix(in srgb,var(--s-card) 94%,transparent)}
.s-compare-table-wrap{overflow-x:auto;max-width:100%;margin-top:18px}
.s-compare-table{border-collapse:collapse;width:100%;font-size:13px;line-height:1.5}
.s-compare-table th,.s-compare-table td{text-align:left;vertical-align:top;padding:12px;min-width:170px;border-bottom:1px solid var(--s-border);overflow-wrap:anywhere;white-space:pre-line}
.s-compare-table th{min-width:120px;width:150px;color:var(--s-muted);font-weight:700}
.s-compare-note{color:var(--s-muted);font-size:12px;line-height:1.6;margin:15px 0 0}
.s-recent-section{padding-top:7px}
.s-store-information{padding-top:10px}
.s-info-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:13px}
.s-info-card{padding:20px;border:1px solid var(--s-border);background:var(--s-card);border-radius:16px;box-shadow:0 4px 14px rgba(0,0,0,.03)}
.s-info-icon{display:inline-flex;font-size:22px;background:var(--sa-bg);border-radius:11px;align-items:center;justify-content:center;width:43px;height:43px}
.s-info-card h3{font-size:16px;margin:11px 0 7px;color:var(--s-ink)}
.s-info-card p{font-size:13px;line-height:1.8;color:var(--s-muted);white-space:pre-line;overflow-wrap:anywhere;margin:0}
.s-info-disclaimer{font-size:12px;color:var(--s-muted);line-height:1.7;margin:12px 2px}
@media(max-width:640px){
 .s-announcement{font-size:12px;padding:9px 12px}
 .s-compare-tray{align-items:stretch;flex-direction:column;padding:11px}
 .s-compare-tray-actions{justify-content:space-between}
 .s-compare-overlay{padding:0;align-items:flex-end}
 .s-compare-dialog{width:100%;border-radius:21px 21px 0 0;max-height:89dvh;padding:15px}
 .s-compare-heading h2{font-size:20px}
 .s-compare-columns{gap:9px}
 .s-compare-item{min-width:160px;max-width:210px;padding:10px}
 .s-compare-picture img{height:105px}
 .s-compare-table th,.s-compare-table td{padding:9px;min-width:140px}
 .s-compare-table th{min-width:96px}
 .s-info-grid{grid-template-columns:1fr}
 .s-info-card{padding:15px}
}
`;

function useInjectCSS(css) {
  useEffect(() => {
    const el = document.createElement("style");
    el.id = "bsmart-store-css";
    el.textContent = css;
    document.head.appendChild(el);
    return () => el.remove();
  }, [css]);
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function FlashSaleCountdown({ saleEnd }) {
  const [left, setLeft] = useState("");
  useEffect(() => {
    function calc() {
      const diff = new Date(saleEnd) - new Date();
      if (diff <= 0) { setLeft("শেষ"); return; }
      const h = Math.floor(diff / 3600000);
      const m = Math.floor((diff % 3600000) / 60000);
      const s = Math.floor((diff % 60000) / 1000);
      setLeft(`${h}ঘ ${m}মি ${s}সে`);
    }
    calc();
    const id = setInterval(calc, 1000);
    return () => clearInterval(id);
  }, [saleEnd]);
  return <span style={{ fontSize: 11, color: "#dc2626", fontWeight: 700 }}>⏰ {left} বাকি</span>;
}

function StarRating({ value, count }) {
  if (!value) return null;
  const stars = Math.round(value);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12, marginBottom: 4 }}>
      {[1,2,3,4,5].map(i => <span key={i} style={{ color: i <= stars ? "#f59e0b" : "#d1d5db" }}>★</span>)}
      <span style={{ color: "#6b7280" }}>{value.toFixed(1)} ({count})</span>
    </div>
  );
}

function ProductCard({ product, cartQty, onAdd, onQtyChange, onView, storeCategory, showStockLevel,
  isFavorite=false, onFavorite, isCompared=false, compareDisabled=false, onCompare }) {
  const outOfStock = product.in_stock === false;
  const inCart = (cartQty || 0) > 0;
  const hasFlashSale = product.sale_price != null;
  const displayPrice = hasFlashSale ? product.sale_price : product.price;
  return (
    <div className="s-product-card-wrap">
      {product.is_featured && <span className="s-featured-badge">⭐ বিশেষ</span>}
      <button type="button" className={`s-product-favorite${isFavorite?" selected":""}`}
        aria-label={isFavorite?`${product.name} পছন্দের তালিকা থেকে সরান`:`${product.name} পছন্দের তালিকায় রাখুন`}
        aria-pressed={isFavorite} title={isFavorite?"পছন্দের তালিকায় আছে":"পছন্দের তালিকায় রাখুন"}
        onClick={()=>onFavorite?.(product.id)}>{isFavorite?"♥":"♡"}</button>
      {hasFlashSale && <span className="s-featured-badge" style={{ background: "#dc2626", right: 8, left: "auto" }}>🔥 সেল</span>}
      <div className="s-product-card">
        {product.price != null ? <button type="button" className="s-product-img-button" onClick={() => onView(product)} aria-label={`${product.name} বিস্তারিত দেখুন`}>
          <img src={product.image_data_url || productImage(product, storeCategory)} alt={product.name} className="s-product-img" loading="lazy" />
        </button> : <img src={product.image_data_url || productImage(product, storeCategory)} alt={product.name} className="s-product-img" loading="lazy" />}
        <div className="s-product-body">
          {product.price != null ? <button type="button" className="s-product-name-button" onClick={() => onView(product)}>{product.name}</button> : <div className="s-product-name">{product.name}</div>}
          <div className="s-product-unit">{product.unit}</div>
          {product.review_avg && <StarRating value={product.review_avg} count={product.review_count || 0} />}
          {product.price != null ? (
            <div className="s-product-price">
              {hasFlashSale && <span style={{ textDecoration: "line-through", color: "#9ca3af", fontSize: 13, marginRight: 6 }}>{money(product.price)}</span>}
              <span style={hasFlashSale ? { color: "#dc2626" } : {}}>{money(displayPrice)}</span>
              {hasFlashSale && product.sale_end && <div><FlashSaleCountdown saleEnd={product.sale_end} /></div>}
            </div>
          ) : <button type="button" className="s-contact-price" onClick={() => document.getElementById("store-contact")?.scrollIntoView({ behavior: "smooth" })}>দাম জানতে যোগাযোগ করুন →</button>}
          {onCompare&&<button type="button" className={`s-product-compare${isCompared?" selected":""}`}
            aria-label={isCompared?`${product.name} তুলনা থেকে সরান`:`${product.name} তুলনায় যোগ করুন`}
            aria-pressed={isCompared} disabled={compareDisabled}
            onClick={()=>onCompare(product.id)}>{isCompared?"✓ তুলনায় আছে":"⇄ তুলনা করুন"}</button>}
          {product.tags?.length > 0 && (
            <div className="s-product-tags">
              {product.tags.slice(0, 2).map(t => <span key={t} className="s-tag">{t}</span>)}
            </div>
          )}
          {showStockLevel === "quantity" && product.quantity !== undefined && !inCart && (
            <span className={product.quantity > 0 && product.quantity <= 5 ? "s-stock-low" : product.quantity > 0 ? "s-stock-ok" : "s-stock-out"}>
              {product.quantity > 0 ? `${product.quantity} ${product.unit} মজুত` : "স্টক নেই"}
            </span>
          )}
          {showStockLevel !== "hide" && showStockLevel !== "quantity" && product.in_stock === false && !inCart && <span className="s-stock-out">স্টক নেই</span>}
          {showStockLevel !== "hide" && showStockLevel !== "quantity" && product.in_stock === true && !inCart && <span className="s-stock-ok">পাওয়া যাচ্ছে</span>}
          {inCart && product.price != null ? (
            <div className="s-card-qty-row" onClick={e => e.stopPropagation()}>
              <button className="s-card-qty-btn" onClick={() => onQtyChange(product.id, cartQty - 1)}>−</button>
              <span className="s-card-qty-num">{cartQty}</span>
              <button className="s-card-qty-btn" disabled={cartQty >= maxOrderQuantity(product)} onClick={() => onQtyChange(product.id, cartQty + 1)}>+</button>
              <span className="s-card-in-cart">কার্টে আছে</span>
            </div>
          ) : product.price != null ? (
            <button
              className="s-add-btn"
              disabled={outOfStock || product.price == null}
              onClick={(e) => { e.stopPropagation(); if (!outOfStock) onAdd(product); }}
            >
              + কার্টে যোগ
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function ProductModal({ product, cartQty, onClose, onAdd, onQtyChange, onViewFull, storeCategory, showStockLevel, orgId }) {
  const outOfStock = product.in_stock === false;
  const [qty, setQty] = useState(1);
  const [selectedVariants, setSelectedVariants] = useState({});  // variantId → option
  const [reviews, setReviews] = useState(null);
  const inCart = (cartQty || 0) > 0;
  const hasFlashSale = product.sale_price != null;
  const displayPrice = hasFlashSale ? product.sale_price : product.price;

  useEffect(() => {
    const onKeyDown = e => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  useEffect(() => {
    if (orgId && product.id) {
      api.getReviews(orgId, product.id).then(setReviews).catch(() => {});
    }
  }, [orgId, product.id]);

  function handleBackdrop(e) { if (e.target === e.currentTarget) onClose(); }

  // Build variant_label string e.g. "Size: L, Color: Red"
  function getVariantLabel() {
    const parts = (product.variants || []).map(v => {
      const sel = selectedVariants[v.id];
      return sel ? `${v.name}: ${sel}` : null;
    }).filter(Boolean);
    return parts.length ? parts.join(", ") : undefined;
  }

  // Check all variant groups have a selection
  const allVariantsSelected = (product.variants || []).every(v => selectedVariants[v.id]);

  return (
    <div className="s-modal-backdrop" onClick={handleBackdrop}>
      <div className="s-modal" role="dialog" aria-modal="true" aria-label={product.name} onClick={e => e.stopPropagation()}>
        <div className="s-modal-handle" />
        <div className="s-modal-inner">
          <button className="s-modal-close" onClick={onClose}>✕</button>
          <div className="s-modal-img" style={{ position: "relative" }}>
            {hasFlashSale && <div style={{ position: "absolute", top: 8, left: 8, background: "#dc2626", color: "#fff", borderRadius: 6, padding: "2px 8px", fontSize: 12, fontWeight: 700 }}>🔥 সেল</div>}
            <img src={product.image_data_url || productImage(product, storeCategory)} alt={product.name} loading="lazy" />
          </div>
          <h2 style={{ margin: "0 0 6px", fontSize: 22, fontWeight: 800, lineHeight: 1.2 }}>{product.name}</h2>
          <div style={{ fontSize: 13, color: "#6b8a7a", marginBottom: 6 }}>{product.unit}</div>
          {reviews?.average && <StarRating value={reviews.average} count={reviews.count} />}
          {product.price != null && (
            <div style={{ fontSize: 26, fontWeight: 700, color: hasFlashSale ? "#dc2626" : "var(--sa)", marginBottom: 4 }}>
              {hasFlashSale && <span style={{ textDecoration: "line-through", color: "#9ca3af", fontSize: 16, marginRight: 8 }}>{money(product.price)}</span>}
              {money(displayPrice)}
            </div>
          )}
          {hasFlashSale && product.sale_end && <div style={{ marginBottom: 10 }}><FlashSaleCountdown saleEnd={product.sale_end} /></div>}
          {product.price == null && <div className="s-contact-price">দাম জানতে দোকানের সাথে যোগাযোগ করুন</div>}
          {product.description && (
            <p style={{ fontSize: 14, color: "#4a6358", lineHeight: 1.65, margin: "0 0 14px" }}>{product.description}</p>
          )}
          {product.tags?.length > 0 && (
            <div className="s-product-tags" style={{ marginBottom: 16 }}>
              {product.tags.map(t => <span key={t} className="s-tag">{t}</span>)}
            </div>
          )}

          {/* Variant picker */}
          {(product.variants || []).map(v => (
            <div key={v.id} style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 6, color: "var(--ink)" }}>{v.name} বেছে নিন</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {v.options.map(opt => {
                  const delta = v.price_deltas?.[opt];
                  const sel = selectedVariants[v.id] === opt;
                  return (
                    <button key={opt} type="button"
                      onClick={() => setSelectedVariants(prev => ({ ...prev, [v.id]: opt }))}
                      style={{ padding: "6px 14px", borderRadius: 8, border: `2px solid ${sel ? "var(--sa)" : "var(--border)"}`, background: sel ? "var(--sa)" : "var(--card)", color: sel ? "#fff" : "var(--ink)", fontWeight: sel ? 700 : 400, cursor: "pointer", fontSize: 13, fontFamily: "inherit" }}>
                      {opt}{delta ? ` (+${money(delta)})` : ""}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}

          <button type="button" className="s-modal-full-btn" onClick={() => onViewFull(product)}>পূর্ণ বিবরণ দেখুন →</button>
          {showStockLevel === "quantity" && product.quantity !== undefined ? (
            <div style={{ marginBottom: 16 }}><span className={product.quantity <= 0 ? "s-stock-out" : product.quantity <= 5 ? "s-stock-low" : "s-stock-ok"}>{product.quantity > 0 ? `${product.quantity} ${product.unit} মজুত` : "স্টক নেই"}</span></div>
          ) : showStockLevel !== "hide" && product.in_stock !== undefined && (
            <div style={{ marginBottom: 16 }}>
              <span className={outOfStock ? "s-stock-out" : "s-stock-ok"}>{outOfStock ? "✗ স্টকে নেই" : "✓ পাওয়া যাচ্ছে"}</span>
            </div>
          )}
          {product.price == null ? null : inCart ? (
            <div>
              <div style={{ fontSize: 13, color: "var(--sa)", fontWeight: 600, marginBottom: 8 }}>✓ কার্টে আছে ({cartQty}টি)</div>
              <div className="s-card-qty-row" style={{ marginBottom: 16 }}>
                <button className="s-card-qty-btn" onClick={() => onQtyChange(product.id, cartQty - 1)}>−</button>
                <span className="s-card-qty-num">{cartQty}</span>
                <button className="s-card-qty-btn" disabled={cartQty >= maxOrderQuantity(product)} onClick={() => onQtyChange(product.id, cartQty + 1)}>+</button>
              </div>
            </div>
          ) : (
            <div>
              <div className="s-qty-row" style={{ marginBottom: 16 }}>
                <button className="s-qty-btn" onClick={() => setQty(q => Math.max(1, q - 1))}>−</button>
                <span className="s-qty-num">{qty}</span>
                <button className="s-qty-btn" disabled={qty >= maxOrderQuantity(product)} onClick={() => setQty(q => Math.min(maxOrderQuantity(product), q + 1))}>+</button>
                <span style={{ fontSize: 13, color: "#6b8a7a" }}>{product.unit}</span>
              </div>
              {product.variants?.length > 0 && !allVariantsSelected && (
                <p style={{ fontSize: 13, color: "#dc2626", marginBottom: 8 }}>⚠ সব ভ্যারিয়েন্ট বেছে নিন</p>
              )}
              <button
                className="s-add-to-cart-btn"
                disabled={outOfStock || (product.variants?.length > 0 && !allVariantsSelected)}
                onClick={() => { onAdd(product, qty, getVariantLabel()); onClose(); }}
              >
                {product.price != null ? `কার্টে যোগ — ${money(qty * (displayPrice || product.price))}` : "কার্টে যোগ করুন"}
              </button>
            </div>
          )}

          {/* Reviews section */}
          {reviews && reviews.count > 0 && (
            <div style={{ marginTop: 20, borderTop: "1px solid var(--border)", paddingTop: 16 }}>
              <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 10 }}>রিভিউ ({reviews.count}টি)</div>
              {reviews.reviews.slice(0, 3).map(r => (
                <div key={r.id} style={{ marginBottom: 12, padding: "10px 12px", background: "var(--bg)", borderRadius: 8 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                    <span style={{ fontWeight: 600, fontSize: 13 }}>{r.reviewer_name}</span>
                    <span>{[1,2,3,4,5].map(i => <span key={i} style={{ color: i <= r.rating ? "#f59e0b" : "#d1d5db", fontSize: 13 }}>★</span>)}</span>
                  </div>
                  {r.comment && <p style={{ fontSize: 13, color: "#4a6358", margin: 0 }}>{r.comment}</p>}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function CartDrawer({ cart, products, storeCategory, onClose, onQtyChange, onCheckout }) {
  const items = Object.entries(cart).filter(([, q]) => q > 0);
  const total = items.reduce((s, [id, q]) => s + q * (products[id]?.price || 0), 0);
  useEffect(() => {
    const onKeyDown = e => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);
  return (
    <>
      <div className="s-cart-overlay" onClick={onClose} />
      <div className="s-cart-drawer" role="dialog" aria-modal="true" aria-label="শপিং কার্ট">
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
                <div className="s-cart-item-img">
                  <img src={p.image_data_url || productImage(p, storeCategory)} alt={p.name} loading="lazy" />
                </div>
                <div>
                  <div className="s-cart-item-name">{p.name}</div>
                  <div className="s-cart-item-price">{money(p.price)} / {p.unit}</div>
                </div>
                <div className="s-cart-item-right">
                  <div className="s-cart-item-total">{money(qty * p.price)}</div>
                  <div className="s-cart-qty-row">
                    <button className="s-cart-qty-btn" onClick={() => onQtyChange(pid, qty - 1)}>−</button>
                    <span className="s-cart-qty-num">{qty}</span>
                    <button className="s-cart-qty-btn" disabled={qty >= maxOrderQuantity(p)} onClick={() => onQtyChange(pid, qty + 1)}>+</button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
        {items.length > 0 && (
          <div className="s-cart-footer">
            <div className="s-cart-subtotal-row"><span>{items.length} টি পণ্য</span><span>{money(total)}</span></div>
            <div className="s-cart-total-row"><span>মোট</span><strong>{money(total)}</strong></div>
            <button className="s-checkout-btn" onClick={onCheckout}>অর্ডার করুন →</button>
          </div>
        )}
      </div>
    </>
  );
}

const BD_DIVISIONS = ["ঢাকা","চট্টগ্রাম","রাজশাহী","খুলনা","বরিশাল","সিলেট","রংপুর","ময়মনসিংহ"];

/* ── SSLCommerz logo SVG ── */
function SSLCommerzLogo({ size = 32 }) {
  const h = size;
  const w = size * 3.2;
  return (
    <svg width={w} height={h} viewBox="0 0 96 30" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="96" height="30" rx="6" fill="#0a6ebd"/>
      <text x="6" y="21" fontFamily="Arial,sans-serif" fontWeight="900" fontSize="14" fill="white" letterSpacing=".5">SSL</text>
      <text x="34" y="21" fontFamily="Arial,sans-serif" fontWeight="400" fontSize="12" fill="#90c8f0">Commerz</text>
      {/* lock icon */}
      <rect x="80" y="9" width="10" height="8" rx="2" fill="none" stroke="#ffd200" strokeWidth="1.5"/>
      <path d="M82 9V7a3 3 0 016 0v2" stroke="#ffd200" strokeWidth="1.5" fill="none" strokeLinecap="round"/>
      <circle cx="85" cy="13" r="1.2" fill="#ffd200"/>
    </svg>
  );
}

/* ── Real bKash logo SVG (matches official bKash brand) ── */
function BkashLogo({ size = 32 }) {
  return (
    <svg width={size * 2.2} height={size} viewBox="0 0 88 40" fill="none" xmlns="http://www.w3.org/2000/svg">
      {/* Pink rounded rect background */}
      <rect width="88" height="40" rx="8" fill="#E2136E"/>
      {/* White "b" letterform */}
      <path d="M12 8h4v8.5c1.2-1.5 3-2.5 5.2-2.5 4.2 0 7.3 3.4 7.3 8s-3.1 8-7.3 8c-2.2 0-4-1-5.2-2.5V30h-4V8zm8.5 18.5c2.4 0 4-1.9 4-4.5s-1.6-4.5-4-4.5-4 1.9-4 4.5 1.6 4.5 4 4.5z" fill="white"/>
      {/* "Kash" text */}
      <text x="34" y="27" fontFamily="Arial, sans-serif" fontWeight="700" fontSize="16" fill="white" letterSpacing=".5">Kash</text>
    </svg>
  );
}

/* ── Real Nagad logo SVG (matches official Nagad brand) ── */
function NagadLogo({ size = 32 }) {
  return (
    <svg width={size * 2.5} height={size} viewBox="0 0 100 40" fill="none" xmlns="http://www.w3.org/2000/svg">
      {/* Orange gradient background */}
      <rect width="100" height="40" rx="8" fill="url(#nagad-grad)"/>
      <defs>
        <linearGradient id="nagad-grad" x1="0" y1="0" x2="100" y2="40" gradientUnits="userSpaceOnUse">
          <stop stopColor="#F7941D"/>
          <stop offset="1" stopColor="#EF3A22"/>
        </linearGradient>
      </defs>
      {/* Yellow dot (Nagad brand mark) */}
      <circle cx="14" cy="20" r="6" fill="#FFD200"/>
      {/* "nagad" Bangla-inspired wordmark in white */}
      <text x="26" y="27" fontFamily="Arial, sans-serif" fontWeight="900" fontSize="15" fill="white" letterSpacing="1">nagad</text>
    </svg>
  );
}

function CheckoutView({ store, cart, products, onBack, onDone, scCustomer, variantSelections }) {
  const orgId = store.organization_id;
  const defaultPayment = store.payment_cod ? "cod" : store.payment_bkash ? "bkash" : store.payment_nagad ? "nagad" : "cod";
  const prefillDiv = scCustomer?.division || "";

  // Auto-fill from logged-in customer profile
  const prefillAddress = scCustomer
    ? [scCustomer.address_detail, scCustomer.thana, scCustomer.district, scCustomer.division]
        .filter(Boolean).join(", ")
    : "";
  const [form, setForm] = useState({
    name: scCustomer?.display_name || "",
    phone: scCustomer?.phone || "",
    address: prefillAddress,
    division: prefillDiv,
    payment: defaultPayment,
    note: "",
    payment_screenshot: null,
  });
  const [busy, setBusy] = useState(false);
  const [submitCooldown, setSubmitCooldown] = useState(0);
  const [error, setError] = useState("");
  const [couponCode, setCouponCode] = useState("");
  const [couponResult, setCouponResult] = useState(null);   // { discount_amount, code } | null
  const [couponErr, setCouponErr] = useState("");
  const [couponBusy, setCouponBusy] = useState(false);
  const [privacyConsent, setPrivacyConsent] = useState(false);
  const [checkoutRequestId] = useState(() => crypto.randomUUID());
  const isD1RealCOD = store.real_cod_enabled === true;
  const checkoutBlocked = store.checkout_available === false;
  const set = (k) => (e) => setForm(f => ({ ...f, [k]: e.target.value }));

  const items = Object.entries(cart).filter(([, q]) => q > 0);
  const subtotal = items.reduce((s, [id, q]) => s + q * (products[id]?.price || 0), 0);
  const meetsMin = !store.min_order_bdt || subtotal >= store.min_order_bdt;

  // Delivery fee calculation
  const deliveryFee = (() => {
    if (!store.delivery_inside_dhaka && !store.delivery_outside_dhaka) return 0;
    if (store.delivery_free_above && subtotal >= store.delivery_free_above) return 0;
    if (!form.division) return store.delivery_inside_dhaka || 0;
    return form.division === "ঢাকা"
      ? (store.delivery_inside_dhaka || 0)
      : (store.delivery_outside_dhaka || store.delivery_inside_dhaka || 0);
  })();
  const couponDiscount = couponResult?.discount_amount || 0;
  const grandTotal = Math.max(0, subtotal + deliveryFee - couponDiscount);

  async function applyCoupon() {
    if (!couponCode.trim()) return;
    setCouponBusy(true); setCouponErr("");
    try {
      const res = await api.validateCoupon(orgId, couponCode.trim(), subtotal);
      setCouponResult(res);
      setCouponErr("");
    } catch (e) {
      setCouponErr(e.message || "অবৈধ কুপন কোড");
      setCouponResult(null);
    } finally { setCouponBusy(false); }
  }

  // Zone restriction check
  const zoneBlocked = store.allow_zone_restriction && store.allowed_divisions && form.division
    ? !store.allowed_divisions.split(",").map(d => d.trim()).includes(form.division)
    : false;

  // Countdown effect
  useEffect(() => {
    if (submitCooldown <= 0) return;
    const t = setTimeout(() => setSubmitCooldown(c => c - 1), 1000);
    return () => clearTimeout(t);
  }, [submitCooldown]);

  async function place(e) {
    e.preventDefault();
    if (submitCooldown > 0) return;
    if (checkoutBlocked) { setError("এই দোকানের বাস্তব অর্ডার এখনো চালু হয়নি।"); return; }
    if (isD1RealCOD && !privacyConsent) { setError("ডেলিভারির জন্য তথ্য শেয়ার করার সম্মতি দিন।"); return; }
    if (!form.name.trim() || !form.phone.trim() || !form.address.trim()) {
      setError("নাম, ফোন নম্বর ও ঠিকানা দিতে হবে।");
      return;
    }
    const phone = form.phone.replace(/[\s()-]/g, "");
    if (!/^(?:\+?88)?01[3-9]\d{8}$/.test(phone)) {
      setError("সঠিক বাংলাদেশি মোবাইল নম্বর দিন (যেমন 01XXXXXXXXX)।");
      return;
    }
    if (items.some(([id]) => products[id]?.price == null)) {
      setError("দাম নির্ধারিত নয় এমন পণ্য অর্ডার করা যাবে না। দোকানের সাথে যোগাযোগ করুন।");
      return;
    }
    if (!meetsMin) {
      setError(`সর্বনিম্ন অর্ডার ${money(store.min_order_bdt)} হতে হবে।`);
      return;
    }
    if (zoneBlocked) {
      setError("দুঃখিত, এই এলাকায় ডেলিভারি দেওয়া সম্ভব নয়।");
      return;
    }
    setBusy(true); setError("");
    try {
      const scToken = (() => { try { return localStorage.getItem("sc_token"); } catch (_) { return null; } })();
      const order = await api.placePublicOrder(orgId, {
        shipping_name: form.name,
        shipping_phone: phone,
        shipping_address: form.address + (form.note ? `\nনোট: ${form.note}` : ""),
        notes: form.note || null,
        payment_method: form.payment,
        privacy_consent: isD1RealCOD && privacyConsent,
        checkout_request_id: isD1RealCOD ? checkoutRequestId : undefined,
        delivery_division: form.division || undefined,
        payment_screenshot: form.payment_screenshot || undefined,
        items: items.map(([product_id, quantity]) => ({
          product_id,
          quantity,
          variant_label: variantSelections?.[product_id] || undefined,
        })),
        store_customer_token: isD1RealCOD ? undefined : scToken || undefined,
        coupon_code: couponResult?.code || undefined,
      });
      setSubmitCooldown(30);
      onDone({ ...order, payment_method: form.payment });
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
      {scCustomer && (
        <div style={{ background: "color-mix(in srgb,var(--sa,#0a8752) 10%,transparent)", border: "1px solid color-mix(in srgb,var(--sa,#0a8752) 30%,transparent)", borderRadius: 10, padding: "10px 14px", marginBottom: 18, fontSize: 13, display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 16 }}>✅</span>
          <span><strong>{scCustomer.display_name}</strong> হিসেবে লগইন আছেন — তথ্য স্বয়ংক্রিয়ভাবে পূরণ হয়েছে, এই অর্ডারটি আপনার অ্যাকাউন্টে সংরক্ষিত হবে</span>
        </div>
      )}

      <div className="s-order-summary">
        <h3>অর্ডার সারসংক্ষেপ</h3>
        {items.map(([pid, qty]) => (
          <div key={pid} className="s-order-row">
            <span>{products[pid]?.name} × {qty}</span>
            <span>{money(qty * (products[pid]?.price || 0))}</span>
          </div>
        ))}
        <div className="s-order-row"><span>পণ্য মোট</span><span>{money(subtotal)}</span></div>
        {deliveryFee > 0 && <div className="s-order-row"><span>ডেলিভারি চার্জ</span><span>{money(deliveryFee)}</span></div>}
        {store.delivery_free_above && subtotal >= store.delivery_free_above && (
          <div className="s-order-row" style={{color:"var(--green)",fontSize:13}}><span>🎉 বিনামূল্যে ডেলিভারি</span><span>-</span></div>
        )}
        {couponDiscount > 0 && (
          <div className="s-order-row" style={{color:"#16a34a",fontSize:13}}><span>🎟 কুপন ({couponResult.code})</span><span>-{money(couponDiscount)}</span></div>
        )}
        <div className="s-order-row total"><span>সর্বমোট</span><span>{money(grandTotal)}</span></div>
      </div>

      {/* Coupon input */}
      <div style={{display:"flex",gap:8,margin:"14px 0 6px"}}>
        <input
          className="s-input"
          placeholder="কুপন কোড (যদি থাকে)"
          value={couponCode}
          onChange={e => { setCouponCode(e.target.value); setCouponResult(null); setCouponErr(""); }}
          style={{flex:1,fontSize:14}}
        />
        <button type="button" onClick={applyCoupon} disabled={couponBusy || !couponCode.trim()}
          style={{background:"var(--sa)",color:"#fff",border:"none",borderRadius:10,padding:"0 16px",fontWeight:700,cursor:"pointer",fontSize:14,fontFamily:"inherit"}}>
          {couponBusy ? "…" : "প্রয়োগ"}
        </button>
      </div>
      {couponErr && <div style={{color:"#dc2626",fontSize:13,marginBottom:8}}>{couponErr}</div>}
      {couponResult && <div style={{color:"#16a34a",fontSize:13,marginBottom:8}}>✅ কুপন সফল! {money(couponDiscount)} ছাড় পেলেন</div>}

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
          <input className="s-input" autoComplete="name" value={form.name} onChange={set("name")} required />
        </div>
        <div className="s-form-group">
          <label>ফোন নম্বর <span>*</span></label>
          <input className="s-input" type="tel" autoComplete="tel" value={form.phone} onChange={set("phone")} required inputMode="tel" placeholder="01XXXXXXXXX" />
        </div>
        <div className="s-form-group">
          <label>ডেলিভারি ঠিকানা <span>*</span></label>
          <textarea className="s-textarea" autoComplete="street-address" value={form.address} onChange={set("address")} required rows={3} />
        </div>
        <div className="s-form-group">
          <label>বিভাগ (ডেলিভারি চার্জের জন্য)</label>
          <select className="s-input" value={form.division} onChange={set("division")}>
            <option value="">বিভাগ বেছে নিন</option>
            {BD_DIVISIONS.map(d => <option key={d} value={d}>{d}</option>)}
          </select>
          {zoneBlocked && <div style={{color:"var(--red,#e63946)",fontSize:13,marginTop:4}}>দুঃখিত, এই বিভাগে ডেলিভারি দেওয়া হয় না।</div>}
        </div>
        <div className="s-form-group">
          <label>বিশেষ নির্দেশনা (ঐচ্ছিক)</label>
          <input className="s-input" value={form.note} onChange={set("note")} />
        </div>

        <div className="s-form-group">
          <label>পেমেন্ট পদ্ধতি <span>*</span></label>
          <div className="s-payment-options" role="radiogroup" aria-label="পেমেন্ট পদ্ধতি">
            {store.payment_cod && (
              <button type="button" role="radio" aria-checked={form.payment === "cod"} className={`s-payment-option${form.payment === "cod" ? " selected" : ""}`} onClick={() => setForm(f => ({ ...f, payment: "cod" }))}>
                <span className="s-payment-cod-icon">💵</span>
                <div>
                  <div className="s-payment-option-label">ক্যাশ অন ডেলিভারি</div>
                  <div className="s-payment-option-desc">ডেলিভারির সময় নগদে পেমেন্ট করুন</div>
                </div>
                {form.payment === "cod" && <span style={{marginLeft:"auto",color:"#10b981",fontSize:20}}>✓</span>}
              </button>
            )}
            {store.payment_bkash && (
              <button type="button" role="radio" aria-checked={form.payment === "bkash"} className={`s-payment-option${form.payment === "bkash" ? " bkash-selected" : ""}`} onClick={() => setForm(f => ({ ...f, payment: "bkash" }))}>
                <BkashLogo size={20} />
                <div>
                  <div className="s-payment-option-label" style={{color: form.payment === "bkash" ? "#E2136E" : undefined}}>bKash</div>
                  <div className="s-payment-option-desc">Send Money করে অর্ডার নিশ্চিত করুন</div>
                </div>
                {form.payment === "bkash" && <span style={{marginLeft:"auto",color:"#E2136E",fontSize:20}}>✓</span>}
              </button>
            )}
            {store.payment_nagad && (
              <button type="button" role="radio" aria-checked={form.payment === "nagad"} className={`s-payment-option${form.payment === "nagad" ? " nagad-selected" : ""}`} onClick={() => setForm(f => ({ ...f, payment: "nagad" }))}>
                <NagadLogo size={20} />
                <div>
                  <div className="s-payment-option-label" style={{color: form.payment === "nagad" ? "#F7941D" : undefined}}>Nagad</div>
                  <div className="s-payment-option-desc">Send Money করে অর্ডার নিশ্চিত করুন</div>
                </div>
                {form.payment === "nagad" && <span style={{marginLeft:"auto",color:"#F7941D",fontSize:20}}>✓</span>}
              </button>
            )}
            {store.sslcz_store_id && (
              <button type="button" role="radio" aria-checked={form.payment === "sslcommerz"} className={`s-payment-option${form.payment === "sslcommerz" ? " selected" : ""}`} onClick={() => setForm(f => ({ ...f, payment: "sslcommerz" }))}>
                <SSLCommerzLogo size={20} />
                <div>
                  <div className="s-payment-option-label" style={{color: form.payment === "sslcommerz" ? "#0a6ebd" : undefined}}>
                    অনলাইন পেমেন্ট
                  </div>
                  <div className="s-payment-option-desc">bKash · Nagad · Card · Net Banking</div>
                </div>
                {form.payment === "sslcommerz" && <span style={{marginLeft:"auto",color:"#0a6ebd",fontSize:20}}>✓</span>}
              </button>
            )}
          </div>
        </div>

        {form.payment === "bkash" && store.bkash_number && (
          <div className="bkash-instruction">
            <div className="bkash-instruction-header">
              <BkashLogo size={22} />
              <div className="bkash-instruction-header-text">bKash-এ পেমেন্ট করুন</div>
            </div>
            <div className="bkash-instruction-body">
              <div className="bkash-step">
                <div className="bkash-step-num">১</div>
                <div className="bkash-step-content">
                  <div className="bkash-step-label">আপনার bKash অ্যাপ খুলুন</div>
                  <div style={{fontSize:12,color:"#9a6070"}}>bKash App → Send Money</div>
                </div>
              </div>
              <div className="bkash-step">
                <div className="bkash-step-num">২</div>
                <div className="bkash-step-content">
                  <div className="bkash-step-label">এই নম্বরে Send Money করুন</div>
                  <div className="bkash-number-display">
                    <span className="bkash-number-text">{store.bkash_number}</span>
                    <button className="bkash-copy-btn" type="button" onClick={() => { navigator.clipboard?.writeText(store.bkash_number); }}>কপি</button>
                  </div>
                </div>
              </div>
              <div className="bkash-step">
                <div className="bkash-step-num">৩</div>
                <div className="bkash-step-content">
                  <div className="bkash-step-label">পরিমাণ</div>
                  <div className="bkash-amount-chip">
                    <span className="bkash-amount-value">৳ {grandTotal.toLocaleString("bn-BD")}</span>
                  </div>
                </div>
              </div>
              <div className="bkash-step">
                <div className="bkash-step-num">৪</div>
                <div className="bkash-step-content">
                  <div className="bkash-step-label">Reference-এ লিখুন</div>
                  <div className="bkash-ref-note">আপনার নাম বা ফোন নম্বর লিখুন। অর্ডার দেওয়ার পর নম্বর পাবেন।</div>
                </div>
              </div>
              <div className="bkash-step">
                <div className="bkash-step-num">৫</div>
                <div className="bkash-step-content">
                  <div className="bkash-step-label">স্ক্রিনশট আপলোড করুন (ঐচ্ছিক)</div>
                  <label className={`s-screenshot-upload bkash-upload`} style={{display:"block",marginTop:8}}>
                    <input type="file" accept="image/*" style={{display:"none"}} onChange={async e => {
                      const file = e.target.files[0]; if (!file) return;
                      const reader = new FileReader();
                      reader.onload = ev => setForm(f => ({ ...f, payment_screenshot: ev.target.result }));
                      reader.readAsDataURL(file);
                    }} />
                    {form.payment_screenshot
                      ? <><img src={form.payment_screenshot} alt="screenshot" className="s-screenshot-preview" /><div style={{fontSize:12,color:"#d12053",marginTop:4,fontWeight:700}}>✓ স্ক্রিনশট আপলোড হয়েছে</div></>
                      : <div style={{fontSize:13,color:"#d12053"}}>📷 পেমেন্ট স্ক্রিনশট ছবি যোগ করুন</div>
                    }
                  </label>
                </div>
              </div>
            </div>
          </div>
        )}

        {form.payment === "nagad" && store.nagad_number && (
          <div className="nagad-instruction">
            <div className="nagad-instruction-header">
              <NagadLogo size={22} />
              <div className="nagad-instruction-header-text">Nagad-এ পেমেন্ট করুন</div>
            </div>
            <div className="nagad-instruction-body">
              <div className="nagad-step">
                <div className="nagad-step-num">১</div>
                <div className="nagad-step-content">
                  <div className="nagad-step-label">আপনার Nagad অ্যাপ খুলুন</div>
                  <div style={{fontSize:12,color:"#9a6040"}}>Nagad App → Send Money</div>
                </div>
              </div>
              <div className="nagad-step">
                <div className="nagad-step-num">২</div>
                <div className="nagad-step-content">
                  <div className="nagad-step-label">এই নম্বরে Send Money করুন</div>
                  <div className="nagad-number-display">
                    <span className="nagad-number-text">{store.nagad_number}</span>
                    <button className="nagad-copy-btn" type="button" onClick={() => { navigator.clipboard?.writeText(store.nagad_number); }}>কপি</button>
                  </div>
                </div>
              </div>
              <div className="nagad-step">
                <div className="nagad-step-num">৩</div>
                <div className="nagad-step-content">
                  <div className="nagad-step-label">পরিমাণ</div>
                  <div className="nagad-amount-chip">
                    <span className="nagad-amount-value">৳ {grandTotal.toLocaleString("bn-BD")}</span>
                  </div>
                </div>
              </div>
              <div className="nagad-step">
                <div className="nagad-step-num">৪</div>
                <div className="nagad-step-content">
                  <div className="nagad-step-label">Reference-এ লিখুন</div>
                  <div className="nagad-ref-note">আপনার নাম বা ফোন নম্বর লিখুন। অর্ডার দেওয়ার পর নম্বর পাবেন।</div>
                </div>
              </div>
              <div className="nagad-step">
                <div className="nagad-step-num">৫</div>
                <div className="nagad-step-content">
                  <div className="nagad-step-label">স্ক্রিনশট আপলোড করুন (ঐচ্ছিক)</div>
                  <label className={`s-screenshot-upload nagad-upload`} style={{display:"block",marginTop:8}}>
                    <input type="file" accept="image/*" style={{display:"none"}} onChange={async e => {
                      const file = e.target.files[0]; if (!file) return;
                      const reader = new FileReader();
                      reader.onload = ev => setForm(f => ({ ...f, payment_screenshot: ev.target.result }));
                      reader.readAsDataURL(file);
                    }} />
                    {form.payment_screenshot
                      ? <><img src={form.payment_screenshot} alt="screenshot" className="s-screenshot-preview" /><div style={{fontSize:12,color:"#f15a24",marginTop:4,fontWeight:700}}>✓ স্ক্রিনশট আপলোড হয়েছে</div></>
                      : <div style={{fontSize:13,color:"#f15a24"}}>📷 পেমেন্ট স্ক্রিনশট ছবি যোগ করুন</div>
                    }
                  </label>
                </div>
              </div>
            </div>
          </div>
        )}

        {form.payment === "bkash" && !store.bkash_number && (
          <div style={{background:"#fff0f4",border:"1.5px solid #d12053",borderRadius:12,padding:"12px 16px",fontSize:13,color:"#d12053",marginBottom:16}}>
            📱 অর্ডার দেওয়ার পর দোকান থেকে bKash নম্বর জানানো হবে।
          </div>
        )}
        {form.payment === "nagad" && !store.nagad_number && (
          <div style={{background:"#fff5f0",border:"1.5px solid #f15a24",borderRadius:12,padding:"12px 16px",fontSize:13,color:"#f15a24",marginBottom:16}}>
            💳 অর্ডার দেওয়ার পর দোকান থেকে Nagad নম্বর জানানো হবে।
          </div>
        )}

        {isD1RealCOD && <label style={{display:"flex",gap:10,alignItems:"flex-start",lineHeight:1.6,margin:"16px 0",fontSize:13}}>
          <input type="checkbox" checked={privacyConsent} onChange={e=>setPrivacyConsent(e.target.checked)} required />
          আমি সম্মতি দিচ্ছি যে ডেলিভারি ও অর্ডার নিশ্চিত করার জন্য আমার নাম, ফোন ও ঠিকানা এই দোকানের মালিকের সঙ্গে শেয়ার হবে। অগ্রিম টাকা পাঠাতে হবে না।
        </label>}
        {checkoutBlocked && <div className="s-error-box">এই দোকান এখনো যাচাইকৃত real COD checkout চালু করেনি। কোনো টাকা পাঠাবেন না।</div>}
        <button className="s-place-order-btn" type="submit" disabled={busy || checkoutBlocked || (isD1RealCOD && !privacyConsent) || !meetsMin || zoneBlocked || submitCooldown > 0}>
          {busy ? "অর্ডার দেওয়া হচ্ছে…" : checkoutBlocked ? "অর্ডার এখন বন্ধ" : submitCooldown > 0 ? `অপেক্ষা করুন (${submitCooldown}s)` : `অর্ডার করুন — ${money(grandTotal)}`}
        </button>
      </form>
    </div>
  );
}

function ConfirmationView({ order, store, orgId, onContinue }) {
  const pm = order.payment_method;
  // Direct API mode (store has merchant credentials)
  const hasBkashApi  = store?.bkash_app_key;
  const hasNagadApi  = store?.nagad_merchant_id;
  const isBkashDirect = pm === "bkash" && hasBkashApi;
  const isNagadDirect = pm === "nagad" && hasNagadApi;
  // Manual Send Money mode (store only has phone number)
  const isBkashManual = pm === "bkash" && store?.payment_bkash && store?.bkash_number && !hasBkashApi;
  const isNagadManual = pm === "nagad" && store?.payment_nagad && store?.nagad_number && !hasNagadApi;
  const isSSL = pm === "sslcommerz" && store?.sslcz_store_id;

  const [busy, setBusy] = useState(false);
  const [payErr, setPayErr] = useState("");

  async function redirectToBkash() {
    setBusy(true); setPayErr("");
    try {
      const data = await api.initiateBkashPayment(order.organization_id, order.id);
      window.location.href = data.bkashURL;
    } catch (e) { setPayErr(e.message || "bKash পেমেন্ট শুরু করা যায়নি"); setBusy(false); }
  }
  async function redirectToNagad() {
    setBusy(true); setPayErr("");
    try {
      const data = await api.initiateNagadPayment(order.organization_id, order.id);
      window.location.href = data.callBackUrl;
    } catch (e) { setPayErr(e.message || "Nagad পেমেন্ট শুরু করা যায়নি"); setBusy(false); }
  }
  async function redirectToSSL() {
    setBusy(true); setPayErr("");
    try {
      const { gateway_url } = await api.initiateSSLCommerzPayment(order.organization_id, order.id);
      window.location.href = gateway_url;
    } catch (e) { setPayErr(e.message || "পেমেন্ট শুরু করা যায়নি"); setBusy(false); }
  }

  return (
    <div className="s-confirm">
      <div className="s-confirm-lottie">✅</div>
      <h2>অর্ডার পেয়েছি!</h2>
      <p>আপনার অর্ডার নম্বর: <strong style={{color:"var(--sa)",fontSize:20}}>#{order.order_number}</strong></p>

      {payErr && <div style={{background:"#fee2e2",color:"#b91c1c",borderRadius:10,padding:"10px 14px",fontSize:13,margin:"8px 0"}}>{payErr}</div>}

      {/* bKash Direct API — redirect to official bKash checkout */}
      {isBkashDirect && (
        <div style={{background:"linear-gradient(135deg,#fff0f4,#ffe4ed)",border:"2px solid #E2136E",borderRadius:16,padding:"20px 22px",margin:"16px 0",textAlign:"center"}}>
          <div style={{marginBottom:12}}><BkashLogo size={24} /></div>
          <p style={{fontSize:14,color:"#7a1a40",margin:"0 0 6px",lineHeight:1.6}}>
            অর্ডার <strong style={{color:"#E2136E"}}>#{order.order_number}</strong> — পরিমাণ <strong style={{color:"#E2136E"}}>৳{Number(order.total).toLocaleString("bn-BD")}</strong>
          </p>
          <p style={{fontSize:12,color:"#9a3055",margin:"0 0 16px"}}>বাটনে ক্লিক করলে official bKash payment page-এ যাবেন</p>
          <button onClick={redirectToBkash} disabled={busy} style={{background:"#E2136E",color:"#fff",border:"none",borderRadius:12,padding:"14px 32px",fontSize:16,fontWeight:800,cursor:"pointer",width:"100%",fontFamily:"inherit",display:"flex",alignItems:"center",justifyContent:"center",gap:10}}>
            {busy ? "রিডাইরেক্ট হচ্ছে…" : <><BkashLogo size={16} /><span>bKash-এ পেমেন্ট করুন</span></>}
          </button>
          <p style={{fontSize:11,color:"#c06080",marginTop:8}}>🔒 আপনি bKash-এর নিরাপদ পেজে যাবেন</p>
        </div>
      )}

      {/* Nagad Direct API — redirect to official Nagad checkout */}
      {isNagadDirect && (
        <div style={{background:"linear-gradient(135deg,#fff8f0,#ffe8d6)",border:"2px solid #F7941D",borderRadius:16,padding:"20px 22px",margin:"16px 0",textAlign:"center"}}>
          <div style={{marginBottom:12}}><NagadLogo size={24} /></div>
          <p style={{fontSize:14,color:"#7a3a10",margin:"0 0 6px",lineHeight:1.6}}>
            অর্ডার <strong style={{color:"#F7941D"}}>#{order.order_number}</strong> — পরিমাণ <strong style={{color:"#F7941D"}}>৳{Number(order.total).toLocaleString("bn-BD")}</strong>
          </p>
          <p style={{fontSize:12,color:"#9a4020",margin:"0 0 16px"}}>বাটনে ক্লিক করলে official Nagad payment page-এ যাবেন</p>
          <button onClick={redirectToNagad} disabled={busy} style={{background:"linear-gradient(135deg,#F7941D,#EF3A22)",color:"#fff",border:"none",borderRadius:12,padding:"14px 32px",fontSize:16,fontWeight:800,cursor:"pointer",width:"100%",fontFamily:"inherit",display:"flex",alignItems:"center",justifyContent:"center",gap:10}}>
            {busy ? "রিডাইরেক্ট হচ্ছে…" : <><NagadLogo size={16} /><span>Nagad-এ পেমেন্ট করুন</span></>}
          </button>
          <p style={{fontSize:11,color:"#c06030",marginTop:8}}>🔒 আপনি Nagad-এর নিরাপদ পেজে যাবেন</p>
        </div>
      )}

      {/* bKash Manual (no API credentials — Send Money) */}
      {isBkashManual && (
        <div className="bkash-instruction" style={{textAlign:"left"}}>
          <div className="bkash-instruction-header">
            <BkashLogo size={22} />
            <div className="bkash-instruction-header-text">এখনই bKash-এ পেমেন্ট করুন</div>
          </div>
          <div className="bkash-instruction-body">
            <div className="bkash-step">
              <div className="bkash-step-num">১</div>
              <div className="bkash-step-content">
                <div className="bkash-step-label">bKash App → Send Money</div>
              </div>
            </div>
            <div className="bkash-step">
              <div className="bkash-step-num">২</div>
              <div className="bkash-step-content">
                <div className="bkash-step-label">নম্বর</div>
                <div className="bkash-number-display">
                  <span className="bkash-number-text">{store.bkash_number}</span>
                  <button className="bkash-copy-btn" type="button" onClick={() => navigator.clipboard?.writeText(store.bkash_number)}>কপি</button>
                </div>
              </div>
            </div>
            <div className="bkash-step">
              <div className="bkash-step-num">৩</div>
              <div className="bkash-step-content">
                <div className="bkash-step-label">পরিমাণ পাঠান</div>
                <div className="bkash-amount-chip"><span className="bkash-amount-value">৳ {order.total ? Number(order.total).toLocaleString("bn-BD") : "—"}</span></div>
              </div>
            </div>
            <div className="bkash-step">
              <div className="bkash-step-num">৪</div>
              <div className="bkash-step-content">
                <div className="bkash-step-label">Reference-এ অর্ডার নম্বর লিখুন</div>
                <div className="bkash-ref-note">
                  <strong style={{color:"#d12053",fontSize:16}}>#{order.order_number}</strong>
                  <button style={{marginLeft:12,background:"#d12053",color:"#fff",border:"none",borderRadius:6,padding:"3px 9px",fontSize:11,fontWeight:700,cursor:"pointer"}} type="button" onClick={() => navigator.clipboard?.writeText(order.order_number)}>কপি</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {isNagadManual && (
        <div className="nagad-instruction" style={{textAlign:"left"}}>
          <div className="nagad-instruction-header">
            <NagadLogo size={22} />
            <div className="nagad-instruction-header-text">এখনই Nagad-এ পেমেন্ট করুন</div>
          </div>
          <div className="nagad-instruction-body">
            <div className="nagad-step">
              <div className="nagad-step-num">১</div>
              <div className="nagad-step-content">
                <div className="nagad-step-label">Nagad App → Send Money</div>
              </div>
            </div>
            <div className="nagad-step">
              <div className="nagad-step-num">২</div>
              <div className="nagad-step-content">
                <div className="nagad-step-label">নম্বর</div>
                <div className="nagad-number-display">
                  <span className="nagad-number-text">{store.nagad_number}</span>
                  <button className="nagad-copy-btn" type="button" onClick={() => navigator.clipboard?.writeText(store.nagad_number)}>কপি</button>
                </div>
              </div>
            </div>
            <div className="nagad-step">
              <div className="nagad-step-num">৩</div>
              <div className="nagad-step-content">
                <div className="nagad-step-label">পরিমাণ পাঠান</div>
                <div className="nagad-amount-chip"><span className="nagad-amount-value">৳ {order.total ? Number(order.total).toLocaleString("bn-BD") : "—"}</span></div>
              </div>
            </div>
            <div className="nagad-step">
              <div className="nagad-step-num">৪</div>
              <div className="nagad-step-content">
                <div className="nagad-step-label">Reference-এ অর্ডার নম্বর লিখুন</div>
                <div className="nagad-ref-note">
                  <strong style={{color:"#f15a24",fontSize:16}}>#{order.order_number}</strong>
                  <button style={{marginLeft:12,background:"#f15a24",color:"#fff",border:"none",borderRadius:6,padding:"3px 9px",fontSize:11,fontWeight:700,cursor:"pointer"}} type="button" onClick={() => navigator.clipboard?.writeText(order.order_number)}>কপি</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {isSSL && (
        <div style={{background:"linear-gradient(135deg,#f0f7ff,#e8f2ff)",border:"2px solid #0a6ebd",borderRadius:16,padding:"20px 22px",margin:"16px 0",textAlign:"center"}}>
          <div style={{marginBottom:12}}><SSLCommerzLogo size={22} /></div>
          <p style={{fontSize:14,color:"#1a4a7a",margin:"0 0 16px",lineHeight:1.6}}>
            অর্ডার নম্বর <strong>#{order.order_number}</strong> পেয়েছি।<br/>
            নিচের বাটনে ক্লিক করে bKash / Nagad / Card দিয়ে পেমেন্ট সম্পন্ন করুন।
          </p>
          {payErr && <div style={{color:"#dc2626",fontSize:13,marginBottom:10}}>{payErr}</div>}
          <button
            onClick={redirectToSSL}
            disabled={busy}
            style={{background:"#0a6ebd",color:"#fff",border:"none",borderRadius:12,padding:"14px 32px",fontSize:16,fontWeight:800,cursor:"pointer",width:"100%",fontFamily:"inherit",boxShadow:"0 4px 16px rgba(10,110,189,.35)"}}
          >
            {busy ? "রিডাইরেক্ট হচ্ছে…" : "💳 এখনই পেমেন্ট করুন"}
          </button>
          <p style={{fontSize:12,color:"#5a8ab0",marginTop:10}}>
            🔒 SSL Secured · bKash · Nagad · Visa · Mastercard
          </p>
        </div>
      )}

      {Number(order.delivery_fee) > 0 && (
        <p style={{fontSize:14}}>ডেলিভারি চার্জ: <strong>৳ {Number(order.delivery_fee).toLocaleString("bn-BD")}</strong></p>
      )}
      {order.coupon_discount > 0 && (
        <p style={{fontSize:14,color:"#16a34a"}}>🎟 কুপন ছাড়: <strong>-৳{Number(order.coupon_discount).toLocaleString("bn-BD")}</strong></p>
      )}
      <p>দোকান থেকে নিশ্চিত হলে জানানো হবে। এই লিংক দিয়ে যেকোনো সময় অর্ডারের অবস্থা জানুন:</p>
      <div className="s-confirm-token">#{order.order_number}</div>
      <br />
      <a className="s-track-btn" href={`#/order-status/${order.organization_id}/${order.access_token}`}>
        অর্ডার ট্র্যাক করুন
      </a>
      {order.whatsapp_notify_url && (
        <div style={{marginTop:12,background:"#dcfce7",border:"1px solid #86efac",borderRadius:10,padding:"10px 14px",fontSize:13,color:"#166534"}}>
          💬 দোকানদারকে WhatsApp-এ জানাতে পারেন:
          <a href={order.whatsapp_notify_url} target="_blank" rel="noreferrer"
            style={{display:"block",marginTop:6,background:"#25D366",color:"#fff",borderRadius:8,padding:"8px 16px",textDecoration:"none",fontWeight:700,textAlign:"center"}}>
            WhatsApp-এ অর্ডার জানান
          </a>
        </div>
      )}
      <br />
      <button className="s-continue-btn" onClick={onContinue}>আরও কেনাকাটা করুন</button>
    </div>
  );
}

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function loadCart(orgId) {
  try { return JSON.parse(localStorage.getItem(`cart_${orgId}`) || "{}"); } catch { return {}; }
}
function saveCart(orgId, cart) {
  try { localStorage.setItem(`cart_${orgId}`, JSON.stringify(cart)); } catch { /* ignore */ }
}

// ─── Main component ───────────────────────────────────────────────────────────
export default function StorePage() {
  const { storeId } = useParams();
  const location=useLocation();
  useInjectCSS(STORE_CSS);

  const [store, setStore] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  // view: "home" | "product" | "checkout" | "done"
  const [view, setView] = useState("home");
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [cart, setCart] = useState({});
  const [variantSelections, setVariantSelections] = useState({});  // productId → label
  const [cartOpen, setCartOpen] = useState(false);
  const [portalOpen, setPortalOpen] = useState(false);
  const [scCustomer, setScCustomer] = useState(null); // logged-in store customer
  const [chatUnread, setChatUnread] = useState(0);
  const [search, setSearch] = useState("");
  const [activeCat, setActiveCat] = useState(null);
  const [sortOrder, setSortOrder] = useState("recommended");
  const [onlyAvailable,setOnlyAvailable]=useState(false);
  const [onlyFavorites,setOnlyFavorites]=useState(false);
  const [favoriteProducts,setFavoriteProducts]=useState([]);
  const [recentIds,setRecentIds]=useState([]);
  const [compareIds,setCompareIds]=useState([]);
  const [compareOpen,setCompareOpen]=useState(false);
  const [visibleCount, setVisibleCount] = useState(20);
  const [modalProduct, setModalProduct] = useState(null);
  const [confirmedOrder, setConfirmedOrder] = useState(null);
  const [detailQty, setDetailQty] = useState(1);

  // Bootstrap logged-in store customer from localStorage token
  useEffect(() => {
    const token = (() => { try { return localStorage.getItem("sc_token"); } catch (_) { return null; } })();
    if (!token) return;
    fetch("/api/sc/me", { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : null)
      .then(c => { if (c) setScCustomer(c); })
      .catch(() => {});
  }, []);

  // Poll unread chat count for account button badge
  useEffect(() => {
    if (!scCustomer || !store?.slug) return;
    const token = (() => { try { return localStorage.getItem("sc_token"); } catch (_) { return null; } })();
    if (!token) return;
    const poll = () => fetch(`/api/sc/unread/${store.slug}`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : { count: 0 })
      .then(d => setChatUnread(d.count))
      .catch(() => {});
    poll();
    const id = setInterval(poll, 15000);
    return () => clearInterval(id);
  }, [scCustomer, store?.slug]);

  useEffect(() => {
    if (!storeId) return;
    const fetch = UUID_RE.test(storeId)
      ? api.getPublicStore(storeId)
      : api.getPublicStoreBySlug(storeId);
    fetch
      .then(data => {
        setStore(data);
        setFavoriteProducts(readFavorites("products:"+data.organization_id));
        setRecentIds(recentProducts(data.organization_id));
        setCompareIds([]);
        setCompareOpen(false);
        applyTheme(data.theme_color, data.theme_preset);
        // SEO meta tags
        document.title = data.meta_title || data.display_name;
        let metaDesc = document.querySelector('meta[name="description"]');
        if (!metaDesc) { metaDesc = document.createElement('meta'); metaDesc.name = 'description'; document.head.appendChild(metaDesc); }
        metaDesc.content = data.meta_desc || data.tagline || '';
        const ogTags = { 'og:title': data.meta_title || data.display_name, 'og:description': data.meta_desc || data.tagline || '', 'og:image': data.cover_data_url || '', 'og:type': 'website' };
        Object.entries(ogTags).forEach(([prop, content]) => {
          let el = document.querySelector(`meta[property="${prop}"]`);
          if (!el) { el = document.createElement('meta'); el.setAttribute('property', prop); document.head.appendChild(el); }
          el.setAttribute('content', content);
        });
        const saved = loadCart(data.organization_id);
        const allowed = new Set((data.products || []).filter(p => p.price != null && p.in_stock !== false).map(p => p.id));
        const validCart = Object.fromEntries(Object.entries(saved).filter(([id]) => allowed.has(id)));
        setCart(validCart);
        saveCart(data.organization_id, validCart);
      })
      .catch(e => setErr(explain(e, { 404: "এই স্টোরটি পাওয়া যায়নি বা এখন বন্ধ।" })))
      .finally(() => setLoading(false));
    return () => { clearTheme(); document.title = 'B-SMART'; };
  }, [storeId]);

  const products = useMemo(() => [...(store?.products || [])].sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0)), [store]);
  useEffect(()=>{
    const requested=new URLSearchParams(location.search).get("product");
    if(!requested||!store)return;
    const match=products.find(p=>String(p.id)===requested);
    if(match){setModalProduct(match);setView("home");}
  },[location.search,store?.organization_id,products]);
  const productMap = useMemo(() => Object.fromEntries(products.map(p => [p.id, p])), [products]);
  const cartCount = useMemo(() => Object.entries(cart).reduce((s, [id, qty]) => s + (productMap[id]?.price != null ? qty : 0), 0), [cart, productMap]);
  const cartTotal = useMemo(() => Object.entries(cart).reduce((s, [id, q]) => s + q * (productMap[id]?.price || 0), 0), [cart, productMap]);
  const allCats = useMemo(() => {
    const cats = new Set();
    products.forEach(p => { const category = String(p.category||p.tags?.[0]||"").trim(); if (category) cats.add(category); });
    return [...cats].sort((a, b) => a.localeCompare(b, "bn"));
  }, [products]);

  const filtered = useMemo(() => {
    let list = [...products];
    if (search) {
      const q = search.toLowerCase();
      list = list.filter(p => `${p.name} ${p.sku || ""} ${p.category || ""} ${(p.tags || []).join(" ")} ${p.description || ""}`.toLowerCase().includes(q));
    }
    if (activeCat) list = list.filter(p => p.category===activeCat||p.tags?.includes(activeCat));
    if(onlyAvailable) list=list.filter(p=>p.in_stock!==false && maxOrderQuantity(p)>0);
    if(onlyFavorites)list=list.filter(p=>favoriteProducts.includes(String(p.id)));
    return list;
  }, [products, search, activeCat,onlyAvailable,onlyFavorites,favoriteProducts]);

  const featured = useMemo(() => products.filter(p => p.is_featured), [products]);
  const sortedProducts = useMemo(() => {
    const list = [...filtered];
    if (sortOrder === "price-low" || sortOrder === "price-high") list.sort((a, b) => {
      if (a.price == null) return b.price == null ? 0 : 1;
      if (b.price == null) return -1;
      return sortOrder === "price-low" ? a.price - b.price : b.price - a.price;
    });
    if (sortOrder === "name") list.sort((a, b) => a.name.localeCompare(b.name, "bn"));
    if (sortOrder === "available") list.sort((a,b)=>Number(b.in_stock!==false)-Number(a.in_stock!==false));
    if (sortOrder === "featured") list.sort((a,b)=>Number(!!b.is_featured)-Number(!!a.is_featured));
    return list;
  }, [filtered, sortOrder]);

  const orgId = store?.organization_id;
  const favCount=useMemo(()=>favoriteProducts.filter(id=>products.some(p=>String(p.id)===id)).length,[favoriteProducts,products]);
  const recentVisible=useMemo(()=>recentIds.map(id=>productMap[id]).filter(Boolean).slice(0,6),[recentIds,productMap]);
  const comparisonProducts=useMemo(()=>compareIds.map(id=>productMap[id]).filter(Boolean),[compareIds,productMap]);
  function toggleComparison(id){
    if(compareIds.includes(String(id))&&compareIds.length<=2)setCompareOpen(false);
    setCompareIds(old=>toggleCompared(old,String(id)));
  }
  function clearComparison(){setCompareOpen(false);setCompareIds([]);}
  function recordRecent(p){if(orgId)setRecentIds(rememberProduct(orgId,p.id));}
  function favoriteProduct(id){
    if(!orgId)return;
    setFavoriteProducts(current=>toggleFavorite("products:"+orgId,current,String(id)));
  }

  function addToCart(product, qty = 1, variantLabel) {
    const max = maxOrderQuantity(product);
    setCart(c => {
      const next = { ...c, [product.id]: clamp((c[product.id] || 0) + qty, 0, max) };
      if (orgId) saveCart(orgId, next);
      return next;
    });
    if (variantLabel) {
      setVariantSelections(v => ({ ...v, [product.id]: variantLabel }));
    }
  }
  function setQty(pid, qty) {
    if (qty <= 0) {
      setCart(c => { const n = { ...c }; delete n[pid]; if (orgId) saveCart(orgId, n); return n; });
    } else {
      const max = maxOrderQuantity(productMap[pid] || {});
      setCart(c => { const next = { ...c, [pid]: clamp(qty, 1, max) }; if (orgId) saveCart(orgId, next); return next; });
    }
  }

  function viewProduct(p) { recordRecent(p); setModalProduct(p); }
  function viewProductFull(p) { recordRecent(p); setSelectedProduct(p); setDetailQty(1); setView("product"); window.scrollTo(0, 0); }
  function goToSection(id) {
    if (view !== "home") {
      setView("home");
      window.setTimeout(() => document.getElementById(id)?.scrollIntoView({ behavior: "smooth" }), 0);
    } else document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
  }

  function handleOrderDone(order) {
    setConfirmedOrder(order);
    setCart({});
    if (orgId) saveCart(orgId, {});
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
  const storeUrl = typeof window !== "undefined" ? window.location.href : "";
  const waShareUrl = `https://wa.me/?text=${encodeURIComponent(`${store.display_name} - অনলাইনে অর্ডার করুন: ${storeUrl}`)}`;

  // Business hours: check if open now
  function getTodayOpenStatus() {
    if (!store.show_hours || !store.hours_json) return null;
    const now = new Date();
    const shortDay = new Intl.DateTimeFormat("en-US", { timeZone: "Asia/Dhaka", weekday: "short" }).format(now).toLowerCase();
    const fullDay = new Intl.DateTimeFormat("en-US", { timeZone: "Asia/Dhaka", weekday: "long" }).format(now).toLowerCase();
    let schedule = store.hours_json?.[shortDay] || store.hours_json?.[fullDay];
    if (typeof schedule === "string") {
      const match = schedule.match(/(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})/);
      schedule = match ? { open: true, from: match[1], to: match[2] } : { open: false };
    }
    if (!schedule || schedule.closed === true || schedule.open === false) return { open: false, label: "আজ বন্ধ" };
    const fromLabel = schedule.from || schedule.open || "09:00";
    const toLabel = schedule.to || schedule.close || "21:00";
    const current = Number(new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Dhaka", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(now).replace(":", ""));
    const from = Number(String(fromLabel).replace(":", ""));
    const to = Number(String(toLabel).replace(":", ""));
    const open = from <= to ? current >= from && current < to : current >= from || current < to;
    return { open, label: `${open ? "এখন খোলা" : "এখন বন্ধ"} · ${fromLabel}–${toLabel}` };
  }
  const todayHours = getTodayOpenStatus();

  return (
    <div className="s-site">
      {store.is_demo && <div role="status" style={{position:"relative",zIndex:50,padding:"12px 16px",background:"#fef3c7",color:"#78350f",fontWeight:700,textAlign:"center"}}>
        Cloudflare D1-তে চালু ডেমো দোকান — অর্ডার রেকর্ড হবে, কিন্তু বাস্তব ডেলিভারি বা পেমেন্ট নেই। নাম/ফোন/ঠিকানায় নমুনা তথ্য ব্যবহার করুন; আসল টাকা পাঠাবেন না।
      </div>}
      {!!store.announcement_text&&<div className="s-announcement" role="note"><span>✦</span>{store.announcement_text}</div>}
      {/* Floating cart button (mobile) */}
      {cartCount > 0 && (
        <button className="s-float-cart" onClick={() => setCartOpen(true)} aria-label="কার্ট খুলুন">
          🛒 <span className="s-float-cart-count">{cartCount}</span>
        </button>
      )}

      {/* Product modal */}
      {modalProduct && (
        <ProductModal
          product={modalProduct}
          cartQty={cart[modalProduct.id] || 0}
          storeCategory={store?.category}
          showStockLevel={store?.show_stock_level}
          orgId={orgId}
          onClose={() => setModalProduct(null)}
          onViewFull={p => { setModalProduct(null); viewProductFull(p); }}
          onAdd={(p, qty, variantLabel) => { addToCart(p, qty, variantLabel); }}
          onQtyChange={(pid, qty) => { setQty(pid, qty); }}
        />
      )}

      {compareOpen && comparisonProducts.length>=2&&<StoreProductCompare
        items={comparisonProducts} storeCategory={store.category}
        onClose={()=>setCompareOpen(false)} onRemove={toggleComparison}
        onView={p=>{setCompareOpen(false);viewProduct(p);}}
        onAdd={p=>addToCart(p)} />}
      {/* Sticky cart bar (desktop) */}
      {cartCount > 0 && view === "home" && (
        <button type="button" className="s-sticky-bar" onClick={() => setCartOpen(true)} style={{ display: "flex" }} aria-label="কার্ট খুলুন">
          <span className="s-sticky-bar-left">🛒 {cartCount}টি পণ্য কার্টে</span>
          <span className="s-sticky-bar-right">কার্ট দেখুন — {money(cartTotal)} →</span>
        </button>
      )}

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
          <nav className="s-store-nav" aria-label="স্টোর নেভিগেশন">
            <button onClick={() => goToSection("store-products")}>সব পণ্য</button>
            {allCats.length > 0 && <button onClick={() => goToSection("store-categories")}>বিভাগ</button>}
            <button onClick={() => goToSection("store-contact")}>যোগাযোগ</button>
          </nav>
          <a href={waShareUrl} target="_blank" rel="noopener noreferrer" className="s-wa-btn" title="WhatsApp-এ শেয়ার করুন">
            📤
          </a>
          {!store.is_demo && store.real_cod_enabled === undefined && <button onClick={() => setPortalOpen(true)} title="আমার অ্যাকাউন্ট"
            style={{ background: "none", border: "1px solid var(--border,rgba(0,0,0,.12))", borderRadius: 20, padding: "7px 13px", fontSize: 13, fontWeight: 600, cursor: "pointer", color: "var(--sa)", display: "flex", alignItems: "center", gap: 5, position: "relative" }}>
            👤 {scCustomer ? scCustomer.display_name.split(" ")[0] : "অ্যাকাউন্ট"}
            {chatUnread > 0 && (
              <span style={{ position: "absolute", top: -4, right: -4, background: "#ef4444", color: "#fff", borderRadius: "50%", width: 18, height: 18, fontSize: 10, fontWeight: 800, display: "flex", alignItems: "center", justifyContent: "center" }}>
                {chatUnread > 9 ? "9+" : chatUnread}
              </span>
            )}
          </button>}
          <button className="s-cart-btn" onClick={() => setCartOpen(true)} aria-label={`কার্ট, ${cartCount}টি পণ্য`}>
            🛒 কার্ট <span className="s-cart-badge">{cartCount}</span>
          </button>
        </div>
      </header>

      {/* Customer portal */}
      {portalOpen && !store.is_demo && store.real_cod_enabled === undefined && (
        <StoreCustomerPortal
          storeSlug={store.slug}
          storeName={store.display_name}
          onClose={() => setPortalOpen(false)}
          onAuthChange={(c) => { setScCustomer(c); if (!c) setChatUnread(0); }}
          onReorder={(items) => {
            // items: [{product_id, quantity, description}]
            const newCart = { ...cart };
            items.forEach(({ product_id, quantity }) => {
              if (productMap[product_id]?.price != null) {
                newCart[product_id] = Math.min(
                  maxOrderQuantity(productMap[product_id] || {}),
                  Number(quantity) || 1,
                );
              }
            });
            setCart(newCart);
            saveCart(store.organization_id, newCart);
            setCartOpen(true);
          }}
        />
      )}

      {/* Cart drawer */}
      {cartOpen && (
        <CartDrawer
          cart={cart}
          products={productMap}
          storeCategory={store.category}
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
            <div className="s-cover-wrap">
              <img src={storeCoverImage(store)} alt={`${store.display_name} দোকান`} className="s-cover-img" />
              <div className="s-cover-overlay" />
              <div className="s-cover-logo-ring">
                {store.logo_data_url
                  ? <img src={store.logo_data_url} alt={store.display_name} className="s-cover-logo-img" />
                  : <div className="s-cover-logo-fallback">{logoInitial}</div>
                }
              </div>
            </div>
            <h1>{store.display_name}</h1>
            {store.tagline && <p>{store.tagline}</p>}
            <div className="s-hero-metrics">
              <div><strong>{products.length}</strong><span>প্রকাশিত পণ্য</span></div>
              <div><strong>{allCats.length}</strong><span>পণ্যের বিভাগ</span></div>
              <div><strong>{store.is_demo?"ডেমো":store.real_cod_enabled?"COD":"স্টোর"}</strong>
                <span>{store.is_demo?"বাস্তব অর্ডার নয়":store.real_cod_enabled?"ডেলিভারির সময় মূল্য":"দোকানের তথ্য"}</span></div>
            </div>
            <div className="s-trust-row">
              {store.category && <span className="s-trust-chip">🏷️ {store.category}</span>}
              {store.area && <span className="s-trust-chip">📍 {store.area}</span>}
              {todayHours && (
                <span className={`s-trust-chip ${todayHours.open ? "s-chip-open" : "s-chip-closed"}`}>
                  {todayHours.open ? "🟢" : "🔴"} {todayHours.label}
                </span>
              )}
            </div>
            {(store.payment_cod || store.payment_bkash || store.payment_nagad) && (
              <div className="s-payment-chips" style={{ marginTop: 14 }}>
                <span style={{ fontSize: 12, color: "#6b8a7a", alignSelf: "center" }}>পেমেন্ট:</span>
                {store.payment_cod && <span className="s-payment-chip">💵 ক্যাশ অন ডেলিভারি</span>}
                {store.payment_bkash && (
                  <span className="s-payment-chip" style={{padding:"3px 8px",border:"1.5px solid #E2136E",background:"#fff0f6"}}>
                    <BkashLogo size={16} />
                  </span>
                )}
                {store.payment_nagad && (
                  <span className="s-payment-chip" style={{padding:"3px 8px",border:"1.5px solid #F7941D",background:"#fff8f0"}}>
                    <NagadLogo size={16} />
                  </span>
                )}
              </div>
            )}
          </section>

          <div className="s-store-benefits" aria-label="দোকানের তথ্য">
            <div className="s-store-benefit"><span>🚚</span><div><strong>ডেলিভারি</strong>{store.delivery_note || "ডেলিভারির বিস্তারিত অর্ডার নিশ্চিতের সময় জানানো হবে"}</div></div>
            <div className="s-store-benefit"><span>🧾</span><div><strong>সর্বনিম্ন অর্ডার</strong>{store.min_order_bdt ? money(store.min_order_bdt) : "কোনো ন্যূনতম অর্ডার নেই"}</div></div>
            <div className="s-store-benefit"><span>🕘</span><div><strong>আজকের সময়</strong>{todayHours?.label || "ব্যবসার সময় দেওয়া নেই"}</div></div>
          </div>

          {/* Featured */}
          {featured.length > 0 && (
            <div className="s-section">
              <div className="s-section-head">
                <h2>⭐ বিশেষ পণ্য</h2>
                <span className="s-badge">{featured.length}</span>
              </div>
              <div className="s-product-grid">
                {featured.map(p => (
                  <ProductCard key={p.id} product={p} cartQty={cart[p.id] || 0}
                    storeCategory={store.category}
                    showStockLevel={store.show_stock_level}
                    isFavorite={favoriteProducts.includes(String(p.id))} onFavorite={favoriteProduct}
                     isCompared={compareIds.includes(String(p.id))} compareDisabled={compareIds.length>=COMPARE_LIMIT&&!compareIds.includes(String(p.id))} onCompare={toggleComparison}
                     onAdd={addToCart} onQtyChange={setQty} onView={viewProduct} />
                ))}
              </div>
            </div>
          )}

          {/* All products */}
          <div className="s-section" id="store-products" style={{ paddingBottom: cartCount > 0 ? 80 : undefined }}>
            <div className="s-section-head">
              <h2>পণ্য খুঁজুন ও কিনুন</h2>
              <span className="s-badge">{products.length}</span>
            </div>
            {/* Category tabs */}
            {allCats.length > 0 && (
              <div className="s-cat-strip" id="store-categories">
                <button className={`s-cat-tab${!activeCat ? " active" : ""}`} onClick={() => setActiveCat(null)}>সব</button>
                {allCats.map(c => (
                  <button key={c} className={`s-cat-tab${activeCat === c ? " active" : ""}`} onClick={() => setActiveCat(activeCat === c ? null : c)}>{c}</button>
                ))}
              </div>
            )}
            <div className="s-filter-bar">
              <div className="s-search-wrap-inner">
                <span className="s-search-icon-inner">🔍</span>
                <input
                  className="s-search"
                  placeholder="পণ্য খুঁজুন…"
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                />
              </div>
            </div>
            <div className="s-shopping-filters" role="group" aria-label="পণ্যের দ্রুত ফিল্টার">
              <button type="button" className={`s-shopping-filter${onlyAvailable?" active":""}`} aria-pressed={onlyAvailable} onClick={()=>setOnlyAvailable(v=>!v)}>✓ মজুত আছে</button>
              <button type="button" className={`s-shopping-filter${onlyFavorites?" active":""}`} aria-pressed={onlyFavorites} onClick={()=>setOnlyFavorites(v=>!v)}>♥ পছন্দের পণ্য ({favCount})</button>
              {(search||activeCat||onlyFavorites||onlyAvailable)&&<button type="button" className="s-shopping-clear" onClick={()=>{setSearch("");setActiveCat(null);setOnlyAvailable(false);setOnlyFavorites(false);setVisibleCount(20);}}>সব ফিল্টার মুছুন</button>}
            </div>
            {compareIds.length>0&&<div className="s-compare-tray" aria-live="polite">
              <div><strong>⇄ পণ্য তুলনা ({compareIds.length}/{COMPARE_LIMIT})</strong>
                <span>{compareIds.length===1?"আরেকটি পণ্য বেছে নিন":"নির্বাচিত পণ্যের বৈশিষ্ট্য একসঙ্গে দেখুন"}</span>
              </div>
              <div className="s-compare-tray-actions">
                <button type="button" className="s-shopping-clear" onClick={clearComparison}>মুছুন</button>
                <button type="button" className="s-compare-open" disabled={comparisonProducts.length<2}
                  onClick={()=>setCompareOpen(true)}>তুলনা দেখুন</button>
              </div>
            </div>}
            <div className="s-store-toolbar">
              <span className="s-result-count">{sortedProducts.length}টি পণ্য দেখানো হচ্ছে</span>
              <select className="s-sort-select" aria-label="পণ্য সাজান" value={sortOrder} onChange={e => setSortOrder(e.target.value)}>
                <option value="recommended">প্রস্তাবিত ক্রম</option>
                <option value="price-low">দাম: কম থেকে বেশি</option>
                <option value="price-high">দাম: বেশি থেকে কম</option>
                <option value="name">নাম অনুযায়ী</option>
                <option value="available">মজুত আছে আগে</option>
                <option value="featured">বিশেষ পণ্য আগে</option>
              </select>
            </div>
            {filtered.length === 0 && (
              <div style={{ textAlign: "center", padding: "48px 16px" }}>
                <div style={{ fontSize: 48, marginBottom: 12 }}>🔍</div>
                <p style={{ color: "var(--s-muted)" }}>এই ফিল্টারে কোনো পণ্য পাওয়া যায়নি। অন্য বিভাগ বা পছন্দের তালিকা দেখুন।</p>
                <button type="button" className="s-shopping-clear" onClick={()=>{setSearch("");setActiveCat(null);setOnlyFavorites(false);setOnlyAvailable(false);}}>সব পণ্য দেখুন</button>
              </div>
            )}
            <div className="s-product-grid">
              {sortedProducts.slice(0, visibleCount).map(p => (
                <ProductCard key={p.id} product={p} cartQty={cart[p.id] || 0}
                  storeCategory={store.category}
                  showStockLevel={store.show_stock_level}
                  isFavorite={favoriteProducts.includes(String(p.id))} onFavorite={favoriteProduct}
                     isCompared={compareIds.includes(String(p.id))} compareDisabled={compareIds.length>=COMPARE_LIMIT&&!compareIds.includes(String(p.id))} onCompare={toggleComparison}
                     onAdd={addToCart} onQtyChange={setQty} onView={viewProduct} />
              ))}
            </div>
            {visibleCount < sortedProducts.length && (
              <div style={{textAlign:"center",marginTop:16}}>
                <button
                  className="s-load-more-btn"
                  style={{padding:"10px 28px",background:"var(--surface)",border:"1px solid var(--border)",borderRadius:8,cursor:"pointer",fontFamily:"inherit",fontSize:14,color:"var(--text)"}}
                  onClick={() => setVisibleCount(c => c + 20)}
                >
                  আরো {Math.min(20, sortedProducts.length - visibleCount)} টি পণ্য দেখুন
                </button>
              </div>
            )}
          </div>

          {recentVisible.length>0&&<section className="s-section s-recent-section" aria-labelledby="s-recent-title">
            <div className="s-section-head">
              <h2 id="s-recent-title">সর্বশেষ দেখা পণ্য</h2>
              <span className="s-badge">এই ডিভাইসে সংরক্ষিত</span>
            </div>
            <div className="s-product-grid">
              {recentVisible.map(p=><ProductCard key={p.id} product={p}
                storeCategory={store.category} showStockLevel={store.show_stock_level}
                cartQty={cart[p.id]||0} isFavorite={favoriteProducts.includes(String(p.id))}
                onFavorite={favoriteProduct} isCompared={compareIds.includes(String(p.id))}
                compareDisabled={compareIds.length>=COMPARE_LIMIT&&!compareIds.includes(String(p.id))}
                onCompare={toggleComparison} onAdd={addToCart} onQtyChange={setQty} onView={viewProduct}/>)}
            </div>
          </section>}

          {(store.about_text||store.delivery_policy_text||store.return_policy_text)&&
            <section className="s-section s-store-information" aria-labelledby="s-info-title">
              <div className="s-section-head"><h2 id="s-info-title">দোকান সম্পর্কে জানুন</h2></div>
              <div className="s-info-grid">
                {store.about_text&&<article className="s-info-card"><span className="s-info-icon">🏬</span><h3>আমাদের সম্পর্কে</h3><p>{store.about_text}</p></article>}
                {store.delivery_policy_text&&<article className="s-info-card"><span className="s-info-icon">🚚</span><h3>ডেলিভারি তথ্য</h3><p>{store.delivery_policy_text}</p></article>}
                {store.return_policy_text&&<article className="s-info-card"><span className="s-info-icon">↩</span><h3>রিটার্ন / এক্সচেঞ্জ</h3><p>{store.return_policy_text}</p></article>}
              </div>
              <p className="s-info-disclaimer">{store.is_demo?"এই দোকান ডেমো। বাস্তব ক্রয়, টাকা লেনদেন বা পণ্য ডেলিভারি করা হয় না।":"এই বিবরণ দোকান কর্তৃক প্রকাশিত; প্ল্যাটফর্ম নিজে ডেলিভারি বা রিটার্ন সম্পন্ন হওয়ার নিশ্চয়তা দেয় না।"}</p>
            </section>}
        </>
      )}

      {view === "product" && selectedProduct && (
        <div className="s-detail">
          <button className="s-back-btn" onClick={() => setView("home")}>← সব পণ্য</button>
          <div className="s-detail-grid">
            <div className="s-detail-image">
              <img src={selectedProduct.image_data_url || productImage(selectedProduct, store.category)} alt={selectedProduct.name} loading="lazy" />
            </div>
            <div className="s-detail-info">
              <div className="s-detail-title-row"><h1 className="s-detail-name">{selectedProduct.name}</h1>
                 <button className={`s-detail-favorite${favoriteProducts.includes(String(selectedProduct.id))?" selected":""}`}
                   type="button" aria-label="পছন্দের তালিকা পরিবর্তন করুন" aria-pressed={favoriteProducts.includes(String(selectedProduct.id))}
                   onClick={()=>favoriteProduct(selectedProduct.id)}>{favoriteProducts.includes(String(selectedProduct.id))?"♥":"♡"}</button>
               </div>
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
              {store.show_stock_level === "quantity" && selectedProduct.quantity !== undefined ? (
                <span className={selectedProduct.quantity <= 0 ? "s-stock-out" : selectedProduct.quantity <= 5 ? "s-stock-low" : "s-stock-ok"}>
                  {selectedProduct.quantity > 0 ? `${selectedProduct.quantity} ${selectedProduct.unit} মজুত` : "স্টক নেই"}
                </span>
              ) : store.show_stock_level !== "hide" && selectedProduct.in_stock !== undefined && (
                <span className={selectedProduct.in_stock ? "s-stock-ok" : "s-stock-out"}>
                  {selectedProduct.in_stock ? "পাওয়া যাচ্ছে" : "স্টক নেই"}
                </span>
              )}
              <div className="s-qty-row">
                <button className="s-qty-btn" onClick={() => setDetailQty(q => Math.max(1, q - 1))}>−</button>
                <span className="s-qty-num">{detailQty}</span>
                <button className="s-qty-btn" disabled={detailQty >= maxOrderQuantity(selectedProduct)} onClick={() => setDetailQty(q => Math.min(maxOrderQuantity(selectedProduct), q + 1))}>+</button>
                <span style={{ fontSize: 13, color: "#6b8a7a", marginLeft: 4 }}>{selectedProduct.unit}</span>
              </div>
              <button
                className="s-add-to-cart-btn"
                disabled={selectedProduct.in_stock === false || selectedProduct.price == null}
                onClick={() => { addToCart(selectedProduct, detailQty); setCartOpen(true); }}
              >
                {selectedProduct.price != null ? `কার্টে যোগ — ${money(detailQty * selectedProduct.price)}` : "দাম জানতে যোগাযোগ করুন"}
              </button>
              <button onClick={() => {
                const url = `${window.location.origin}${window.location.pathname}#/store/${storeId}?product=${selectedProduct.id}`;
                if (navigator.share) navigator.share({ title: selectedProduct.name, text: selectedProduct.description || "", url });
                else { navigator.clipboard?.writeText(url); alert('লিংক কপি হয়েছে!'); }
              }} style={{marginTop:8,background:"none",border:"1px solid var(--border)",borderRadius:8,padding:"8px 14px",cursor:"pointer",fontSize:13,color:"var(--text-muted)",width:"100%"}}>📤 শেয়ার করুন</button>
            </div>
          </div>
          {/* Related products */}
          {(() => {
            const catTag = selectedProduct.tags?.[0];
            const related = catTag ? products.filter(p => p.id !== selectedProduct.id && p.tags?.[0] === catTag).slice(0, 4) : [];
            return related.length > 0 ? (
              <div style={{padding:"16px 0"}}>
                <div style={{fontWeight:700,marginBottom:12,fontSize:15}}>একই বিভাগের পণ্য</div>
                <div style={{display:"grid",gridTemplateColumns:"repeat(2,1fr)",gap:8}}>
                  {related.map(p => (
                    <div key={p.id} style={{border:"1px solid var(--border)",borderRadius:10,padding:10,cursor:"pointer",background:"var(--surface)"}} onClick={() => viewProductFull(p)}>
                      <img src={p.image_data_url || productImage(p, store.category)} alt={p.name} style={{width:"100%",height:80,objectFit:"cover",borderRadius:6,marginBottom:6}} loading="lazy" />
                      <div style={{fontWeight:600,fontSize:13}}>{p.name}</div>
                      {p.price != null && <div style={{color:"var(--green,#0a8752)",fontSize:13}}>{money(p.price)}</div>}
                    </div>
                  ))}
                </div>
              </div>
            ) : null;
          })()}
        </div>
      )}

      {view === "checkout" && cartCount > 0 && (
        <CheckoutView
          store={store}
          cart={cart}
          products={productMap}
          onBack={() => { setCartOpen(true); setView("home"); }}
          onDone={handleOrderDone}
          scCustomer={scCustomer}
          variantSelections={variantSelections}
        />
      )}

      {view === "done" && confirmedOrder && (
        <ConfirmationView
          order={confirmedOrder}
          store={store}
          orgId={orgId}
          onContinue={() => { setView("home"); window.scrollTo(0, 0); }}
        />
      )}

      {/* Footer */}
      <footer className="s-footer" id="store-contact">
        <div className="s-footer-inner">
          <div className="s-footer-column">
            <h3>{store.display_name}</h3>
            {store.tagline && <p>{store.tagline}</p>}
            <p>{[store.category, store.area].filter(Boolean).join(" · ")}</p>
            {store.phone && <p><a href={`tel:${store.phone.replace(/[^+\d]/g, "")}`}>ফোন করুন: {store.phone}</a></p>}
          </div>
          <div className="s-footer-column">
            <h3>দোকানে আসুন</h3>
            {store.address ? <p>{store.address}</p> : <p>{store.area || "ঠিকানা প্রকাশ করা হয়নি"}</p>}
            {(store.address || store.area) && <a href={`https://maps.google.com/?q=${encodeURIComponent(store.address || store.area)}`} target="_blank" rel="noopener noreferrer">মানচিত্রে খুলুন ↗</a>}
            {store.show_hours && store.hours_json && <details className="s-footer-details">
              <summary>সাপ্তাহিক সময়সূচি</summary>
              <ul>{[["mon","monday","সোমবার"],["tue","tuesday","মঙ্গলবার"],["wed","wednesday","বুধবার"],["thu","thursday","বৃহস্পতিবার"],["fri","friday","শুক্রবার"],["sat","saturday","শনিবার"],["sun","sunday","রবিবার"]].map(([shortKey, fullKey, label]) => {
                const day = store.hours_json[shortKey] || store.hours_json[fullKey];
                const isOpen = day && day.closed !== true && day.open !== false;
                const from = day?.from || day?.open || "09:00";
                const to = day?.to || day?.close || "21:00";
                return <li key={shortKey}>{label}: {isOpen ? `${from}–${to}` : "বন্ধ"}</li>;
              })}</ul>
            </details>}
          </div>
          <div className="s-footer-column">
            <h3>অর্ডার ও পেমেন্ট</h3>
            <p>{store.delivery_note || "ডেলিভারির তথ্য অর্ডার নিশ্চিত করার সময় জানানো হবে।"}</p>
            <p>{store.payment_cod ? "ক্যাশ অন ডেলিভারি" : "পেমেন্টের নির্দেশনা দোকান থেকে জানানো হবে"}</p>
            {store.min_order_bdt ? <p>সর্বনিম্ন অর্ডার: {money(store.min_order_bdt)}</p> : null}
          </div>
        </div>
        <div className="s-footer-bottom">
          <span>© {new Date().getFullYear()} {store.display_name}</span>
          <a href="#/stores" className="s-footer-badge" style={{ textDecoration: "none" }}>
            <span>Powered by</span><strong style={{ color: "#8aaa97" }}>B-SMART</strong>
          </a>
        </div>
      </footer>
    </div>
  );
}
