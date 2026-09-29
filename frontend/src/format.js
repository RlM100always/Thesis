// Bangla-first formatting. Numbers, money and dates are shown the way a
// Bangladeshi shop owner reads them (Bengali digits, lakh-style grouping), never
// as raw machine values.

const numberFormat = new Intl.NumberFormat("bn-BD", { maximumFractionDigits: 2 });
const dateFormat = new Intl.DateTimeFormat("bn-BD", { dateStyle: "medium" });
const dateTimeFormat = new Intl.DateTimeFormat("bn-BD", { dateStyle: "medium", timeStyle: "short" });

export const num = (value) => numberFormat.format(Number(value ?? 0));

// Exact money for the till and ledgers. (formatBDT in api.js abbreviates to K/M
// for dashboards; a sale total must never be rounded like that.)
export const money = (value) => `৳ ${numberFormat.format(Number(value ?? 0))}`;

export const dateBn = (iso) => (iso ? dateFormat.format(new Date(iso)) : "—");
export const dateTimeBn = (iso) => (iso ? dateTimeFormat.format(new Date(iso)) : "—");

// "১২ দিন বাকি" / "আজ মেয়াদ শেষ" / "মেয়াদ শেষ (৩ দিন আগে)" / "মেয়াদ অজানা"
export function expiryLabel(days) {
  if (days === null || days === undefined) return "মেয়াদ অজানা";
  if (days < 0) return `মেয়াদ শেষ (${num(-days)} দিন আগে)`;
  if (days === 0) return "আজ মেয়াদ শেষ";
  return `${num(days)} দিন বাকি`;
}

// Tone for an expiry state, shared by every screen that shows one.
export const EXPIRY_TONE = { expired: "danger", near_expiry: "warn", ok: "success", no_expiry: "neutral" };

// The date picker needs local yyyy-mm-dd, not UTC.
export function todayInputValue() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}
