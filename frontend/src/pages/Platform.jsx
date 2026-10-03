import { Component, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid,
  Cell, Legend, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api } from "../api";
import Icon from "../ui/Icon";
import { Badge, Button, EmptyState, Field, Modal, Notice, Skeleton, Stat } from "../ui/kit";
import { useToast } from "../ui/Toast";
import { useConfirm } from "../components/ConfirmDialog";

// ─── NAV ──────────────────────────────────────────────────────────────────────
const NAV_GROUPS = [
  { label: "কমান্ড", items: [
    { value: "command", label: "কমান্ড সেন্টার", icon: "zap" },
  ]},
  { label: "টেন্যান্ট ও ডেটা", items: [
    { value: "tenants",       label: "ব্যবসা তালিকা",         icon: "users" },
    { value: "data-readiness",label: "ডেটা প্রস্তুতি",        icon: "fileText" },
  ]},
  { label: "AI ও রেকমেন্ডেশন", items: [
    { value: "ai-governance", label: "AI পরিচালনা",           icon: "zap" },
    { value: "recom-ops",     label: "রেকমেন্ডেশন অপারেশন",  icon: "trend" },
  ]},
  { label: "প্ল্যান ও সাপোর্ট", items: [
    { value: "plans",         label: "প্ল্যান ও এনটাইটেলমেন্ট", icon: "sliders" },
    { value: "support",       label: "সাপোর্ট ও সাফল্য",      icon: "bell" },
  ]},
  { label: "নিরাপত্তা ও সিস্টেম", items: [
    { value: "security-audit",label: "নিরাপত্তা ও অডিট",      icon: "shield" },
    { value: "system-ops",    label: "সিস্টেম অপারেশন",       icon: "refresh" },
  ]},
  { label: "কন্টেন্ট", items: [
    { value: "site",          label: "পাবলিক সাইট",         icon: "globe" },
    { value: "announcements", label: "অ্যানাউন্সমেন্ট",    icon: "bell" },
  ]},
];
const ALL_TABS = NAV_GROUPS.flatMap(g => g.items);

// ─── HELPERS ──────────────────────────────────────────────────────────────────
function useData(fn, deps = []) {
  const [data, setData]     = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState(null);
  const load = () => {
    setLoading(true); setError(null);
    fn().then(d => { setData(d); setLoading(false); })
       .catch(e => { setError(e.message); setLoading(false); });
  };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(load, deps);
  return { data, loading, error, reload: load };
}

function useAutoRefresh(reloadFn, intervalMs = 30000) {
  useEffect(() => {
    const id = setInterval(reloadFn, intervalMs);
    return () => clearInterval(id);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intervalMs]);
}

const PAGE_SIZE = 20;
function usePaged(items) {
  const [page, setPage] = useState(0);
  const total = items.length;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const slice = items.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const reset = () => setPage(0);
  const pager = pages <= 1 ? null : (
    <div className="pa-pager">
      <button className="pa-pager-btn" disabled={page === 0} onClick={() => setPage(p => p - 1)}>‹</button>
      <span className="pa-pager-info">{page + 1} / {pages} ({total} টি)</span>
      <button className="pa-pager-btn" disabled={page >= pages - 1} onClick={() => setPage(p => p + 1)}>›</button>
    </div>
  );
  return { slice, page, pages, total, setPage, reset, pager };
}

function exportCsv(filename, rows, cols) {
  const hdr = cols.map(c => c.label).join(",");
  const body = rows.map(r => cols.map(c => {
    const v = c.get(r) ?? "";
    return `"${String(v).replace(/"/g, '""')}"`;
  }).join(",")).join("\n");
  const blob = new Blob(["﻿" + hdr + "\n" + body], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a"); a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

function Head({ title, sub, action }) {
  return (
    <div className="pa-page-head" style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
      <div><h2>{title}</h2>{sub && <p>{sub}</p>}</div>
      {action && <div>{action}</div>}
    </div>
  );
}
function fmt(n) { return n != null ? Number(n).toLocaleString() : "—"; }
function dateBn(s) { return s ? new Date(s).toLocaleDateString("bn-BD") : "—"; }
function dateTimeBn(s) { return s ? new Date(s).toLocaleString("bn-BD") : "—"; }
function pct(n, d) { return d ? `${((n / d) * 100).toFixed(1)}%` : "—"; }

const TONE_MAP = { low: "success", medium: "warn", high: "danger", critical: "danger" };
const STATE_TONE = { active: "success", trial: "info", suspended: "danger", churned: "neutral", onboarding: "warn", inactive: "neutral" };

// Orgs don't have a `state` string field — derive it from active+suspended_at
function orgState(org) {
  if (!org.active && org.suspended_at) return "suspended";
  if (!org.active) return "inactive";
  return "active";
}

// ─── DARK MODE ────────────────────────────────────────────────────────────────
// Delegates to the pa-shell element's pa-dark class (owned by App.jsx's PlatformShell).
// Platform.jsx's toggle syncs with it via a custom event so both toggles stay in sync.
const PA_DARK_EVENT = "pa-dark-toggle";
function useDarkMode() {
  const [dark, setDark] = useState(() => {
    const shell = document.querySelector(".pa-shell");
    return shell ? shell.classList.contains("pa-dark") : localStorage.getItem("pa-theme") === "dark";
  });
  useEffect(() => {
    function handler(e) { setDark(e.detail.dark); }
    window.addEventListener(PA_DARK_EVENT, handler);
    return () => window.removeEventListener(PA_DARK_EVENT, handler);
  }, []);
  const toggle = () => {
    const shell = document.querySelector(".pa-shell");
    if (shell) {
      const next = !shell.classList.contains("pa-dark");
      shell.classList.toggle("pa-dark", next);
      localStorage.setItem("pa-theme", next ? "dark" : "light");
      window.dispatchEvent(new CustomEvent(PA_DARK_EVENT, { detail: { dark: next } }));
    }
  };
  return { dark, toggle };
}

// ─── COUNTDOWN HOOK ───────────────────────────────────────────────────────────
function useCountdown(targetIso) {
  const [label, setLabel] = useState("");
  const [urgent, setUrgent] = useState(false);
  useEffect(() => {
    if (!targetIso) return;
    function tick() {
      const ms = new Date(targetIso) - Date.now();
      if (ms <= 0) { setLabel("মেয়াদ শেষ"); setUrgent(true); return; }
      const h = Math.floor(ms / 3600000);
      const m = Math.floor((ms % 3600000) / 60000);
      setLabel(h > 0 ? `${h}ঘ ${m}মি` : `${m}মি`);
      setUrgent(ms < 3600000);
    }
    tick();
    const id = setInterval(tick, 60000);
    return () => clearInterval(id);
  }, [targetIso]);
  return { label, urgent };
}

// ─── ANOMALY DETECTION ────────────────────────────────────────────────────────
function useAnomalyDetect(series = []) {
  return useMemo(() => {
    if (series.length < 14) return [];
    const half = Math.floor(series.length / 2);
    const prev = series.slice(-half * 2, -half);
    const curr = series.slice(-half);
    const sumSales = arr => arr.reduce((s, d) => s + (d.sales_bdt || 0), 0);
    const prevTotal = sumSales(prev);
    const currTotal = sumSales(curr);
    const anomalies = [];
    if (prevTotal > 0) {
      const pct = ((currTotal - prevTotal) / prevTotal) * 100;
      if (pct < -25) anomalies.push({ metric: "বিক্রয়", pct: pct.toFixed(0), dir: "down" });
      if (pct > 50)  anomalies.push({ metric: "বিক্রয়", pct: `+${pct.toFixed(0)}`, dir: "up" });
    }
    return anomalies;
  }, [series]);
}
function useMemo(fn, deps) {
  const ref = useRef({ val: undefined, deps: null });
  const changed = !ref.current.deps || deps.some((d, i) => d !== ref.current.deps[i]);
  if (changed) { ref.current.val = fn(); ref.current.deps = deps; }
  return ref.current.val;
}

// ─── COMMAND PALETTE ──────────────────────────────────────────────────────────
function CommandPalette({ setParams, onClose }) {
  const [q, setQ] = useState("");
  const [idx, setIdx] = useState(0);
  const { data: orgsData } = useData(() => api.platformOrganizations());
  const toast = useToast();
  const confirm = useConfirm();
  const orgs = orgsData?.organizations || orgsData || [];

  const STATIC_CMDS = [
    { label: "কমান্ড সেন্টারে যান",     icon: "zap",     action: () => { setParams({ tab: "command" }); onClose(); } },
    { label: "ব্যবসা তালিকায় যান",      icon: "users",   action: () => { setParams({ tab: "tenants" }); onClose(); } },
    { label: "সিকিউরিটি অ্যালার্ট",    icon: "shield",  action: () => { setParams({ tab: "security-audit" }); onClose(); } },
    { label: "সিস্টেম অপারেশন",         icon: "refresh", action: () => { setParams({ tab: "system-ops" }); onClose(); } },
    { label: "সাপোর্ট কেস",             icon: "bell",    action: () => { setParams({ tab: "support" }); onClose(); } },
    { label: "অ্যানাউন্সমেন্ট পাঠান",  icon: "bell",    action: () => { setParams({ tab: "announcements" }); onClose(); } },
    { label: "AI পরিচালনা",             icon: "zap",     action: () => { setParams({ tab: "ai-governance" }); onClose(); } },
    { label: "প্ল্যান ও এনটাইটেলমেন্ট",icon: "sliders", action: () => { setParams({ tab: "plans" }); onClose(); } },
    { label: "পাবলিক সাইট কন্টেন্ট",   icon: "globe",   action: () => { setParams({ tab: "site" }); onClose(); } },
    { label: "রেকমেন্ডেশন অপারেশন",    icon: "trend",   action: () => { setParams({ tab: "recom-ops" }); onClose(); } },
  ];

  const tenantCmds = q.length >= 2 ? orgs
    .filter(o => o.name?.toLowerCase().includes(q.toLowerCase()) || o.slug?.includes(q))
    .slice(0, 4)
    .map(o => ({
      label: `${orgState(o) === "suspended" ? "✓ সক্রিয়" : "⊘ স্থগিত"} করুন — ${o.name}`,
      icon: "users",
      action: async () => {
        onClose();
        if (orgState(o) === "suspended") {
          if (!await confirm(`"${o.name}" পুনরায় সক্রিয় করবেন?`)) return;
          try { await api.platformUnsuspend(o.id); toast.success("সক্রিয় হয়েছে"); pushNotif({ kind: "action", title: `"${o.name}" সক্রিয় হয়েছে` }); }
          catch (e) { toast.error(e.message); }
        } else {
          const reason = window.prompt("স্থগিতের কারণ:");
          if (!reason) return;
          try { await api.platformSuspend(o.id, reason); toast.success("স্থগিত হয়েছে"); pushNotif({ kind: "action", title: `"${o.name}" স্থগিত হয়েছে` }); }
          catch (e) { toast.error(e.message); }
        }
      },
    })) : [];

  const all = q.length >= 1
    ? [...STATIC_CMDS.filter(c => c.label.toLowerCase().includes(q.toLowerCase())), ...tenantCmds]
    : STATIC_CMDS;

  useEffect(() => { setIdx(0); }, [q]);

  useEffect(() => {
    function handler(e) {
      if (e.key === "Escape") { onClose(); return; }
      if (e.key === "ArrowDown") { e.preventDefault(); setIdx(i => Math.min(i + 1, all.length - 1)); }
      if (e.key === "ArrowUp") { e.preventDefault(); setIdx(i => Math.max(i - 1, 0)); }
      if (e.key === "Enter") { e.preventDefault(); if (all[idx]) all[idx].action(); }
    }
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [all, idx, onClose]);

  return (
    <div className="pa-gsearch-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="pa-gsearch-box">
        <div className="pa-gsearch-input-wrap">
          <Icon name="zap" size={16} />
          <input autoFocus className="pa-gsearch-input" placeholder="কমান্ড টাইপ করুন বা tenant নাম… (↑↓ নেভিগেট, Enter চালু করুন)" value={q} onChange={e => setQ(e.target.value)} />
          <kbd style={{ fontSize: 10, padding: "2px 5px", background: "var(--surface-2)", borderRadius: 4, color: "var(--pa-muted)", border: "1px solid var(--pa-border)" }}>Esc</kbd>
        </div>
        <div className="pa-gsearch-results">
          {all.map((cmd, i) => (
            <button key={i} className={`pa-gsearch-item${i === idx ? " pa-gsearch-focused" : ""}`}
              onClick={cmd.action} onMouseEnter={() => setIdx(i)}>
              <Icon name={cmd.icon} size={14} />
              <span className="pa-gsearch-label">{cmd.label}</span>
            </button>
          ))}
          {all.length === 0 && <div className="pa-gsearch-empty">কোনো কমান্ড পাওয়া যায়নি</div>}
        </div>
      </div>
      {confirm.dialog}
    </div>
  );
}

// ─── HOTKEY SHEET ─────────────────────────────────────────────────────────────
function HotkeySheet({ onClose }) {
  return (
    <div className="pa-gsearch-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="pa-gsearch-box" style={{ maxWidth: 480 }}>
        <div style={{ padding: "14px 16px", borderBottom: "1px solid var(--pa-border)", display: "flex", justifyContent: "space-between" }}>
          <strong>কীবোর্ড শর্টকাট</strong>
          <button className="pa-link-btn" onClick={onClose}>✕</button>
        </div>
        <div style={{ padding: "12px 16px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
          {[
            ["Ctrl+K", "গ্লোবাল সার্চ"],
            ["Ctrl+P", "কমান্ড প্যালেট"],
            ["G then C", "কমান্ড সেন্টার"],
            ["G then T", "ব্যবসা তালিকা"],
            ["G then S", "সাপোর্ট"],
            ["G then E", "সিকিউরিটি"],
            ["G then O", "সিস্টেম অপস"],
            ["G then A", "AI পরিচালনা"],
            ["G then P", "প্ল্যান"],
            ["G then N", "অ্যানাউন্সমেন্ট"],
            ["?", "এই শর্টকাট তালিকা"],
            ["Esc", "বন্ধ করুন"],
          ].map(([key, desc]) => (
            <div key={key} style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 13 }}>
              <kbd style={{ padding: "2px 7px", background: "var(--surface-2)", borderRadius: 4, fontSize: 11, border: "1px solid var(--pa-border)", fontFamily: "monospace", flexShrink: 0 }}>{key}</kbd>
              <span>{desc}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── PLATFORM HEALTH SCORE ────────────────────────────────────────────────────
function PlatformHealthScore({ overview }) {
  const o = overview || {};
  let score = 100;
  if ((o.incidents?.open || 0) > 0)     score -= Math.min(30, o.incidents.open * 10);
  if ((o.security?.open_alerts || 0) > 0) score -= Math.min(20, o.security.open_alerts * 4);
  if ((o.jobs?.failed || 0) > 0)         score -= Math.min(15, o.jobs.failed * 5);
  if ((o.churn_risk?.high || 0) > 0)     score -= Math.min(10, o.churn_risk.high * 2);
  score = Math.max(0, score);
  const tone = score >= 80 ? "success" : score >= 50 ? "warn" : "danger";
  const color = tone === "success" ? "#0a8754" : tone === "warn" ? "#b45309" : "#e63946";
  return (
    <div title={`প্ল্যাটফর্ম স্বাস্থ্য স্কোর: ${score}/100`}
      style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12, fontWeight: 700, color }}>
      <span style={{ fontSize: 10 }}>●</span>{score}
    </div>
  );
}

// ─── ACTIVITY FEED ────────────────────────────────────────────────────────────
function ActivityFeed({ entries = [], loading }) {
  if (loading) return <Skeleton lines={4} />;
  if (!entries.length) return <div className="pa-muted" style={{ fontSize: 12, padding: "12px 0" }}>কোনো সাম্প্রতিক কার্যকলাপ নেই</div>;
  return (
    <div className="pa-activity-feed">
      {entries.slice(0, 12).map((e, i) => (
        <div key={i} className="pa-activity-item">
          <span className="pa-activity-dot" />
          <div>
            <div style={{ fontSize: 12, fontWeight: 500 }}>{e.action?.replace(/\./g, " › ")}</div>
            <div style={{ fontSize: 11, color: "var(--pa-muted)" }}>{e.actor_email || "system"} · {dateTimeBn(e.created_at)}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── SSE HOOK ─────────────────────────────────────────────────────────────────
function useSSEAlerts(onAlert) {
  useEffect(() => {
    let es;
    try {
      es = new EventSource("/api/admin/security-alerts/stream");
      es.onmessage = e => {
        try { onAlert(JSON.parse(e.data)); } catch {}
      };
      es.onerror = () => es.close();
    } catch {}
    return () => es?.close();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}

// ─── UNDO HOOK ────────────────────────────────────────────────────────────────
function useUndo(toast) {
  const timerRef = useRef(null);
  const commit = useCallback((label, action, undo) => {
    clearTimeout(timerRef.current);
    let cancelled = false;
    const dismiss = toast.info(
      <span>{label} — <button className="pa-undo-btn" onClick={() => { cancelled = true; dismiss?.(); undo(); }}>পূর্বাবস্থায় ফিরুন</button></span>,
      { duration: 8000 }
    );
    timerRef.current = setTimeout(() => { if (!cancelled) action(); }, 8000);
    return () => { cancelled = true; clearTimeout(timerRef.current); };
  }, [toast]);
  useEffect(() => () => clearTimeout(timerRef.current), []);
  return commit;
}

// ─── FORM VALIDATION ──────────────────────────────────────────────────────────
function useForm(initial, rules = {}) {
  const [values, setValues] = useState(initial);
  const [touched, setTouch] = useState({});
  const errors = {};
  for (const [k, rule] of Object.entries(rules)) {
    const e = rule(values[k], values);
    if (e) errors[k] = e;
  }
  const valid = Object.keys(errors).length === 0;
  const set = (k, v) => setValues(p => ({ ...p, [k]: v }));
  const touch = k => setTouch(p => ({ ...p, [k]: true }));
  const touchAll = () => setTouch(Object.fromEntries(Object.keys(rules).map(k => [k, true])));
  const reset = () => { setValues(initial); setTouch({}); };
  function FieldErr({ name }) {
    if (!touched[name] || !errors[name]) return null;
    return <div className="pa-field-error">{errors[name]}</div>;
  }
  return { values, set, errors, valid, touched, touch, touchAll, reset, FieldErr };
}

// ─── NOTIFICATION CENTER ──────────────────────────────────────────────────────
const MAX_NOTIFS = 30;
let _notifListeners = [];
const _notifs = [];
function pushNotif(n) {
  _notifs.unshift({ ...n, id: Date.now() + Math.random(), at: new Date() });
  if (_notifs.length > MAX_NOTIFS) _notifs.length = MAX_NOTIFS;
  _notifListeners.forEach(fn => fn([..._notifs]));
}
function useNotifications() {
  const [notifs, setNotifs] = useState([..._notifs]);
  useEffect(() => {
    _notifListeners.push(setNotifs);
    return () => { _notifListeners = _notifListeners.filter(f => f !== setNotifs); };
  }, []);
  const clear = () => { _notifs.length = 0; _notifListeners.forEach(fn => fn([])); };
  return { notifs, clear };
}

// ─── GLOBAL SEARCH ────────────────────────────────────────────────────────────
function GlobalSearch({ setParams, onClose }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [focusIdx, setFocusIdx] = useState(0);
  const debounceRef = useRef(null);

  useEffect(() => {
    if (!q.trim() || q.length < 2) { setResults([]); return; }
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        const [orgsRes, casesRes, alertsRes] = await Promise.allSettled([
          api.platformOrganizations(),
          api.adminSupportCases("open"),
          api.adminSecurityAlerts("open"),
        ]);
        const qq = q.toLowerCase();
        const hits = [];
        (orgsRes.value?.organizations || orgsRes.value || []).forEach(o => {
          if (o.name?.toLowerCase().includes(qq) || o.slug?.includes(qq))
            hits.push({ type: "tenant", label: o.name, sub: o.slug, tab: "tenants", icon: "users" });
        });
        (casesRes.value?.cases || casesRes.value || []).forEach(c => {
          if ((c.subject || c.title)?.toLowerCase().includes(qq))
            hits.push({ type: "case", label: c.subject || c.title, sub: `priority: ${c.priority}`, tab: "support", icon: "bell" });
        });
        (alertsRes.value?.alerts || alertsRes.value || []).forEach(a => {
          if (a.description?.toLowerCase().includes(qq))
            hits.push({ type: "alert", label: a.description, sub: a.severity, tab: "security-audit", icon: "shield" });
        });
        setResults(hits.slice(0, 8));
      } catch {}
      setLoading(false);
    }, 280);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  useEffect(() => { setFocusIdx(0); }, [results]);

  useEffect(() => {
    function handler(e) {
      if (e.key === "Escape") { onClose(); return; }
      if (e.key === "ArrowDown") { e.preventDefault(); setFocusIdx(i => Math.min(i + 1, results.length - 1)); }
      if (e.key === "ArrowUp") { e.preventDefault(); setFocusIdx(i => Math.max(i - 1, 0)); }
      if (e.key === "Enter" && results[focusIdx]) { setParams({ tab: results[focusIdx].tab }); onClose(); }
    }
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onClose, results, focusIdx]);

  return (
    <div className="pa-gsearch-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="pa-gsearch-box">
        <div className="pa-gsearch-input-wrap">
          <Icon name="search" size={16} />
          <input autoFocus className="pa-gsearch-input" placeholder="Tenant, case, alert খুঁজুন… (↑↓ নেভিগেট, Enter যান, Esc বন্ধ)" value={q} onChange={e => setQ(e.target.value)} />
          {loading && <span className="pa-gsearch-spin">⟳</span>}
        </div>
        {results.length > 0 && (
          <div className="pa-gsearch-results">
            {results.map((r, i) => (
              <button key={i} className={`pa-gsearch-item${i === focusIdx ? " pa-gsearch-focused" : ""}`}
                onClick={() => { setParams({ tab: r.tab }); onClose(); }}
                onMouseEnter={() => setFocusIdx(i)}>
                <Icon name={r.icon} size={14} />
                <div>
                  <div className="pa-gsearch-label">{r.label}</div>
                  <div className="pa-gsearch-sub">{r.type} · {r.sub}</div>
                </div>
              </button>
            ))}
          </div>
        )}
        {q.length >= 2 && !loading && results.length === 0 && (
          <div className="pa-gsearch-empty">কোনো ফলাফল পাওয়া যায়নি</div>
        )}
      </div>
    </div>
  );
}

// ─── ERROR BOUNDARY ───────────────────────────────────────────────────────────
class PanelBoundary extends Component {
  constructor(p) { super(p); this.state = { err: null }; }
  static getDerivedStateFromError(e) { return { err: e }; }
  render() {
    if (this.state.err) return (
      <div style={{ padding: 32, textAlign: "center" }}>
        <Notice tone="danger">এই প্যানেলে সমস্যা হয়েছে: {this.state.err.message}</Notice>
        <Button style={{ marginTop: 12 }} onClick={() => this.setState({ err: null })}>পুনরায় চেষ্টা করুন</Button>
      </div>
    );
    return this.props.children;
  }
}

// ─── AI RISK SUMMARY ──────────────────────────────────────────────────────────
function AiRiskSummary({ overview, churn, sla }) {
  const risks = [];
  if (overview?.incidents?.open > 0)
    risks.push(`${overview.incidents.open}টি সক্রিয় ইনসিডেন্ট চলছে`);
  if (overview?.security?.open_alerts > 5)
    risks.push(`${overview.security.open_alerts}টি সিকিউরিটি অ্যালার্ট মনোযোগ চাইছে`);
  if (sla?.resolution_breached > 0)
    risks.push(`${sla.resolution_breached}টি সাপোর্ট কেসের SLA ভঙ্গ হয়েছে`);
  const highChurn = (churn?.risks || []).filter(t => t.risk_level === "high").length;
  if (highChurn > 0) risks.push(`${highChurn}টি ব্যবসা উচ্চ চার্ন ঝুঁকিতে`);
  if (overview?.jobs?.failed > 0) risks.push(`${overview.jobs.failed}টি ব্যাকগ্রাউন্ড জব ব্যর্থ হয়েছে`);

  if (risks.length === 0) return (
    <div className="pa-ai-summary pa-ai-ok">
      <Icon name="check" size={14} /> <span>সব ঠিক আছে — কোনো জরুরি ইস্যু নেই</span>
    </div>
  );
  return (
    <div className="pa-ai-summary pa-ai-warn">
      <div className="pa-ai-title"><Icon name="zap" size={14} /> AI সারসংক্ষেপ — {risks.length}টি মনোযোগ প্রয়োজন</div>
      <ul className="pa-ai-list">{risks.map((r, i) => <li key={i}>{r}</li>)}</ul>
    </div>
  );
}

// ─── TENANT COMPARE ───────────────────────────────────────────────────────────
function TenantCompareModal({ orgs, onClose }) {
  const [selA, setSelA] = useState("");
  const [selB, setSelB] = useState("");
  const { data: hA } = useData(() => selA ? api.adminTenantHealthScore(selA) : Promise.resolve(null), [selA]);
  const { data: hB } = useData(() => selB ? api.adminTenantHealthScore(selB) : Promise.resolve(null), [selB]);
  const orgA = orgs.find(o => o.id === selA);
  const orgB = orgs.find(o => o.id === selB);

  function CompareCol({ org, health }) {
    if (!org) return <div className="pa-compare-col pa-compare-empty">ব্যবসা নির্বাচন করুন</div>;
    return (
      <div className="pa-compare-col">
        <div className="pa-compare-name">{org.name}</div>
        <div className="pa-kv-list" style={{ marginTop: 12 }}>
          <div className="pa-kv-row"><span>অবস্থা</span><Badge tone={STATE_TONE[orgState(org)]}>{orgState(org)}</Badge></div>
          <div className="pa-kv-row"><span>সেক্টর</span><span>{org.sector || "—"}</span></div>
          <div className="pa-kv-row"><span>সদস্য</span><span>{org.member_count ?? "—"}</span></div>
          <div className="pa-kv-row"><span>পণ্য</span><span>{org.product_count ?? "—"}</span></div>
          <div className="pa-kv-row"><span>তৈরি</span><span>{dateBn(org.created_at)}</span></div>
          {health && <>
            <div className="pa-kv-row"><span>স্বাস্থ্য স্কোর</span><Badge tone={health.score >= 70 ? "success" : health.score >= 40 ? "warn" : "danger"}>{health.score ?? "—"}</Badge></div>
            <div className="pa-kv-row"><span>ঝুঁকি</span><span>{health.risk_level || "—"}</span></div>
          </>}
        </div>
      </div>
    );
  }

  return (
    <Modal title="ব্যবসা তুলনা করুন" onClose={onClose}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
        <Field label="ব্যবসা A">
          <select className="pa-input" value={selA} onChange={e => setSelA(e.target.value)}>
            <option value="">বেছে নিন…</option>
            {orgs.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
          </select>
        </Field>
        <Field label="ব্যবসা B">
          <select className="pa-input" value={selB} onChange={e => setSelB(e.target.value)}>
            <option value="">বেছে নিন…</option>
            {orgs.filter(o => o.id !== selA).map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
          </select>
        </Field>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <CompareCol org={orgA} health={hA} />
        <CompareCol org={orgB} health={hB} />
      </div>
    </Modal>
  );
}

// ─── 1. COMMAND CENTER ────────────────────────────────────────────────────────
function CommandCenterPanel({ onNavigate }) {
  const { data: overview, loading: ol, error: oe, reload: oReload } = useData(() => api.adminOverview());
  const { data: mq, loading: ml, error: me, reload: mqReload } = useData(() => api.adminMissionQueue("open"));
  const { data: alerts, loading: al, error: ae, reload: aReload } = useData(() => api.adminSecurityAlerts("open"));
  const { data: trends, loading: tl } = useData(() => api.platformTrends(30));
  const { data: tenantGrowth } = useData(() => api.platformOrganizations());
  const { data: churnData } = useData(() => api.adminChurnRisk("high"));
  const { data: slaData } = useData(() => api.adminSlaSummary());
  const { data: auditData, loading: auditL } = useData(() => api.platformAudit());
  const toast = useToast();
  const o = overview || {};

  useAutoRefresh(() => { oReload(); aReload(); }, 30000);

  // SSE: push new alerts into notification center + badge
  useSSEAlerts(alert => {
    pushNotif({ kind: "alert", title: `নতুন অ্যালার্ট: ${alert.description || alert.alert_type}`, severity: alert.severity });
    aReload();
  });

  async function generateQueue() {
    try { await api.adminGenerateMissionQueue(); toast.success("Queue রিফ্রেশ হয়েছে"); mqReload(); }
    catch (e) { toast.error(e.message); }
  }

  const series = trends?.series || [];
  const items = mq?.items || mq || [];
  const alertList = alerts?.alerts || alerts || [];
  const auditEntries = auditData?.entries || [];
  const anomalies = useAnomalyDetect(series);

  // Build alert severity distribution for bar chart
  const severityCounts = alertList.reduce((acc, a) => {
    acc[a.severity] = (acc[a.severity] || 0) + 1;
    return acc;
  }, {});
  const alertChartData = Object.entries(severityCounts).map(([name, value]) => ({ name, value }));

  // Build monthly tenant growth from org created_at
  const orgs = tenantGrowth?.organizations || tenantGrowth || [];
  const growthMap = {};
  orgs.forEach(org => {
    if (!org.created_at) return;
    const m = org.created_at.slice(0, 7);
    growthMap[m] = (growthMap[m] || 0) + 1;
  });
  const growthData = Object.entries(growthMap).sort(([a],[b]) => a.localeCompare(b))
    .slice(-6).map(([month, count]) => ({ month: month.slice(5), count }));

  return (
    <>
      <Head title="কমান্ড সেন্টার" sub="আজকের সবচেয়ে গুরুত্বপূর্ণ ইস্যু এবং প্ল্যাটফর্মের সামগ্রিক অবস্থা" />

      <AiRiskSummary overview={o} churn={churnData} sla={slaData} />

      {/* Anomaly detection */}
      {anomalies.length > 0 && (
        <div className="pa-anomaly-banner">
          <Icon name="zap" size={14} /> <strong>অস্বাভাবিক পরিবর্তন সনাক্ত:</strong>
          {anomalies.map((a, i) => (
            <span key={i} className={`pa-anomaly-chip ${a.dir === "down" ? "pa-anomaly-down" : "pa-anomaly-up"}`}>
              {a.metric} {a.pct}%
            </span>
          ))}
        </div>
      )}

      {/* KPI row — clickable, jumps to relevant panel */}
      {ol ? <Skeleton lines={2} /> : oe ? <Notice tone="danger">{oe}</Notice> : (
        <div className="pa-stats-grid pa-stats-clickable" style={{ marginBottom: 24 }}>
          <div className="pa-stat-link" onClick={() => onNavigate("system-ops")} title="System Ops বোর্ডে যান">
            <Stat label="ইনসিডেন্ট (খোলা)"  value={fmt(o.incidents?.open)}              tone={o.incidents?.open > 0 ? "danger" : "success"} />
          </div>
          <div className="pa-stat-link" onClick={() => onNavigate("security-audit")} title="Security বোর্ডে যান">
            <Stat label="সিকিউরিটি অ্যালার্ট" value={fmt(o.security?.open_alerts)}      tone={o.security?.open_alerts > 0 ? "danger" : "success"} />
          </div>
          <div className="pa-stat-link" onClick={() => onNavigate("support")} title="Support বোর্ডে যান">
            <Stat label="চার্ন রিস্ক (উচ্চ)" value={fmt(o.churn_risk?.high)}            tone={o.churn_risk?.high > 0 ? "warn" : "success"} />
          </div>
          <div className="pa-stat-link" onClick={() => onNavigate("system-ops")} title="Jobs বোর্ডে যান">
            <Stat label="ব্যর্থ জব"          value={fmt(o.jobs?.failed)}                tone={o.jobs?.failed > 0 ? "danger" : "success"} />
          </div>
          <div className="pa-stat-link" onClick={() => onNavigate("support")} title="Support বোর্ডে যান">
            <Stat label="খোলা সাপোর্ট কেস"  value={fmt(o.support?.open_cases)}          tone="neutral" />
          </div>
          <Stat label="মিশন কিউ (খোলা)"   value={fmt(o.mission_queue?.open)}          tone={o.mission_queue?.open > 10 ? "danger" : "warn"} />
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginBottom: 24 }}>
        {/* Mission queue */}
        <div>
          <div className="pa-section-title" style={{ marginBottom: 8, display: "flex", alignItems: "center", gap: 8 }}>
            আজকের মিশন কিউ
            <Button size="sm" variant="secondary" onClick={generateQueue}>রিফ্রেশ</Button>
          </div>
          {ml ? <Skeleton lines={4} /> : me ? <Notice tone="danger">{me}</Notice> : (
            <div className="pa-table-wrap">
              {items.length === 0 ? <EmptyState title="কোনো খোলা আইটেম নেই" /> : (
                <table className="pa-table">
                  <thead><tr><th>অগ্রাধিকার</th><th>বিষয়</th><th>ধরন</th></tr></thead>
                  <tbody>{items.slice(0, 8).map(item => (
                    <tr key={item.id}>
                      <td><Badge tone={TONE_MAP[item.priority] || "neutral"}>{item.priority}</Badge></td>
                      <td style={{ fontSize: 13 }}>{item.title}</td>
                      <td className="pa-muted" style={{ fontSize: 12 }}>{item.item_type}</td>
                    </tr>
                  ))}</tbody>
                </table>
              )}
            </div>
          )}
        </div>

        {/* Security alerts */}
        <div>
          <div className="pa-section-title" style={{ marginBottom: 8 }}>সক্রিয় সিকিউরিটি অ্যালার্ট</div>
          {al ? <Skeleton lines={4} /> : ae ? <Notice tone="danger">{ae}</Notice> : (
            <div className="pa-table-wrap">
              {alertList.length === 0 ? <EmptyState title="কোনো সক্রিয় অ্যালার্ট নেই" /> : (
                <table className="pa-table">
                  <thead><tr><th>ধরন</th><th>বিবরণ</th><th>তারিখ</th></tr></thead>
                  <tbody>{alertList.slice(0, 8).map(a => (
                    <tr key={a.id}>
                      <td><Badge tone={TONE_MAP[a.severity] || "neutral"}>{a.severity}</Badge></td>
                      <td style={{ fontSize: 13 }}>{a.description}</td>
                      <td className="pa-muted" style={{ fontSize: 12 }}>{dateBn(a.triggered_at)}</td>
                    </tr>
                  ))}</tbody>
                </table>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Charts row */}
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr", gap: 20, marginBottom: 8 }}>
        <div>
          <div className="pa-section-title" style={{ marginBottom: 6 }}>গত ৩০ দিনের বিক্রয় ট্রেন্ড (৳)</div>
          {!tl && (
            <div className="pa-chart-box">
              <ResponsiveContainer width="100%" height={140}>
                <AreaChart data={series} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
                  <defs><linearGradient id="ccg" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#0a8754" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="#0a8754" stopOpacity={0} />
                  </linearGradient></defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="date" tick={{ fontSize: 10 }} tickLine={false} />
                  <YAxis tick={{ fontSize: 10 }} tickLine={false} axisLine={false} />
                  <Tooltip formatter={v => `৳${Number(v).toLocaleString()}`} />
                  <Area type="monotone" dataKey="sales_bdt" stroke="#0a8754" fill="url(#ccg)" strokeWidth={2} dot={false} name="বিক্রয়" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
        <div>
          <div className="pa-section-title" style={{ marginBottom: 6 }}>নতুন ব্যবসা (মাসিক)</div>
          {growthData.length > 0 && (
            <div className="pa-chart-box">
              <ResponsiveContainer width="100%" height={140}>
                <BarChart data={growthData} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="month" tick={{ fontSize: 10 }} tickLine={false} />
                  <YAxis tick={{ fontSize: 10 }} tickLine={false} axisLine={false} allowDecimals={false} />
                  <Tooltip />
                  <Bar dataKey="count" fill="#0d1b2a" name="ব্যবসা" radius={[3,3,0,0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
        <div>
          <div className="pa-section-title" style={{ marginBottom: 6 }}>অ্যালার্ট বিভাজন</div>
          {alertChartData.length > 0 ? (
            <div className="pa-chart-box">
              <ResponsiveContainer width="100%" height={140}>
                <BarChart data={alertChartData} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="name" tick={{ fontSize: 10 }} tickLine={false} />
                  <YAxis tick={{ fontSize: 10 }} tickLine={false} axisLine={false} allowDecimals={false} />
                  <Tooltip />
                  <Bar dataKey="value" fill="#e63946" name="অ্যালার্ট" radius={[3,3,0,0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : <div className="pa-muted" style={{ fontSize: 12, padding: "20px 0" }}>কোনো অ্যালার্ট নেই</div>}
        </div>
      </div>

      {/* Activity feed */}
      <div style={{ marginTop: 24 }}>
        <div className="pa-section-title" style={{ marginBottom: 8 }}>সাম্প্রতিক কার্যকলাপ</div>
        <ActivityFeed entries={auditEntries} loading={auditL} />
      </div>
    </>
  );
}

// ─── 2. TENANTS ───────────────────────────────────────────────────────────────
// Lazy-loaded per-row health badge — fetches only when rendered
const _healthCache = {};
function TenantHealthBadge({ orgId }) {
  const [score, setScore] = useState(_healthCache[orgId] ?? null);
  const [loading, setLoading] = useState(score === null);
  useEffect(() => {
    if (score !== null) return;
    api.adminTenantHealthScore(orgId)
      .then(d => { const s = d?.score ?? null; _healthCache[orgId] = s; setScore(s); setLoading(false); })
      .catch(() => { setLoading(false); });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orgId]);
  if (loading) return <span className="pa-muted" style={{ fontSize: 11 }}>…</span>;
  if (score === null) return <span className="pa-muted" style={{ fontSize: 11 }}>—</span>;
  const tone = score >= 70 ? "success" : score >= 40 ? "warn" : "danger";
  return <Badge tone={tone}>{score}</Badge>;
}

function Tenant360Drawer({ org, onClose }) {
  const { data: health } = useData(() => api.adminTenantHealthScore(org.id), [org.id]);
  const { data: sub }    = useData(() => api.adminOrgSubscription(org.id), [org.id]);
  const { data: cases }  = useData(() => api.adminSupportCases("open"), []);
  const [caseForm, setCaseForm] = useState(false);
  const [newCase, setNewCase]   = useState({ subject: "", priority: "normal" });
  const [annForm, setAnnForm]   = useState(false);
  const [annMsg, setAnnMsg]     = useState("");
  const toast = useToast();
  const confirm = useConfirm();
  const tenantCases = (cases?.cases || cases || []).filter(c => c.organization_id === org.id);

  async function suspendOrg() {
    const reason = window.prompt("স্থগিতের কারণ:");
    if (!reason) return;
    if (!await confirm(`"${org.name}" স্থগিত করবেন?`)) return;
    try { await api.platformSuspend(org.id, reason); toast.success("স্থগিত হয়েছে"); onClose(); }
    catch (e) { toast.error(e.message); }
  }
  async function unsuspendOrg() {
    if (!await confirm(`"${org.name}" সক্রিয় করবেন?`)) return;
    try { await api.platformUnsuspend(org.id); toast.success("সক্রিয় হয়েছে"); onClose(); }
    catch (e) { toast.error(e.message); }
  }
  async function createCase() {
    try { await api.adminCreateSupportCase({ ...newCase, organization_id: org.id }); toast.success("কেস তৈরি হয়েছে"); setCaseForm(false); }
    catch (e) { toast.error(e.message); }
  }
  async function sendAnn() {
    if (!annMsg.trim()) return;
    try {
      await api.platformSendAnnouncement({ title: annMsg.slice(0, 200), body: annMsg, type: "info", organization_ids: [org.id] });
      toast.success("বার্তা পাঠানো হয়েছে"); setAnnForm(false); setAnnMsg("");
    } catch (e) { toast.error(e.message); }
  }

  return (
    <div className="pa-drawer-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="pa-drawer">
        <div className="pa-drawer-head">
          <div>
            <div style={{ fontWeight: 700, fontSize: 16 }}>{org.name}</div>
            <div className="pa-muted" style={{ fontSize: 13 }}>{org.slug} · {org.id?.slice(0, 12)}</div>
          </div>
          <button className="pa-drawer-close" onClick={onClose}><Icon name="x" size={18} /></button>
        </div>

        {/* Quick actions */}
        <div style={{ display: "flex", gap: 8, marginTop: 14, flexWrap: "wrap" }}>
          {orgState(org) === "suspended"
            ? <Button size="sm" onClick={unsuspendOrg}>সক্রিয় করুন</Button>
            : <Button size="sm" variant="danger" onClick={suspendOrg}>স্থগিত করুন</Button>}
          <Button size="sm" variant="secondary" onClick={() => setCaseForm(true)}>সাপোর্ট কেস খুলুন</Button>
          <Button size="sm" variant="secondary" onClick={() => setAnnForm(true)}>বার্তা পাঠান</Button>
        </div>

        {caseForm && (
          <div className="pa-inline-form" style={{ marginTop: 12 }}>
            <Field label="বিষয়"><input className="pa-input" value={newCase.subject} onChange={e => setNewCase(p => ({ ...p, subject: e.target.value }))} /></Field>
            <Field label="প্রাধান্য">
              <select className="pa-input" value={newCase.priority} onChange={e => setNewCase(p => ({ ...p, priority: e.target.value }))}>
                <option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option><option value="urgent">Urgent</option>
              </select>
            </Field>
            <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
              <Button size="sm" onClick={createCase}>তৈরি করুন</Button>
              <Button size="sm" variant="secondary" onClick={() => setCaseForm(false)}>বাতিল</Button>
            </div>
          </div>
        )}

        {annForm && (
          <div className="pa-inline-form" style={{ marginTop: 12 }}>
            <Field label="বার্তা"><textarea className="pa-textarea" rows={2} value={annMsg} onChange={e => setAnnMsg(e.target.value)} /></Field>
            <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
              <Button size="sm" onClick={sendAnn}>পাঠান</Button>
              <Button size="sm" variant="secondary" onClick={() => setAnnForm(false)}>বাতিল</Button>
            </div>
          </div>
        )}

        <div className="pa-section-title" style={{ marginTop: 16 }}>স্বাস্থ্য স্কোর</div>
        {health ? (
          <>
            <div className="pa-stats-grid" style={{ marginBottom: 8 }}>
              <Stat label="স্কোর" value={health.score != null ? health.score : "—"} tone={health.score >= 70 ? "success" : health.score >= 40 ? "warn" : "danger"} />
              <Stat label="ঝুঁকি" value={health.risk_level || "—"} tone={TONE_MAP[health.risk_level] || "neutral"} />
              <Stat label="অ্যাক্টিভিটি" value={health.factors?.recent_activity ?? "—"} />
              <Stat label="টিম ব্যবহার" value={health.factors?.team_adoption ?? "—"} />
            </div>
            {health.recommendation && <div className="pa-muted" style={{ fontSize: 12, marginBottom: 4 }}>{health.recommendation}</div>}
          </>
        ) : <Skeleton lines={1} />}

        <div className="pa-section-title" style={{ marginTop: 16 }}>প্ল্যান ও সাবস্ক্রিপশন</div>
        {sub === null ? <Skeleton lines={1} /> : (() => {
          const s = sub?.subscription;
          return s ? (
            <div className="pa-kv-list">
              <div className="pa-kv-row"><span>প্ল্যান</span><strong>{s.plan_name || s.plan_id || "—"}</strong></div>
              <div className="pa-kv-row"><span>অবস্থা</span><Badge tone={STATE_TONE[s.status] || "neutral"}>{s.status}</Badge></div>
              <div className="pa-kv-row"><span>শুরু</span><span>{dateBn(s.starts_at)}</span></div>
              <div className="pa-kv-row"><span>শেষ</span><span>{dateBn(s.ends_at)}</span></div>
            </div>
          ) : <div className="pa-muted" style={{ fontSize: 13 }}>কোনো সাবস্ক্রিপশন নেই</div>;
        })()}

        <div className="pa-section-title" style={{ marginTop: 16 }}>খোলা সাপোর্ট কেস</div>
        {tenantCases.length === 0 ? <div className="pa-muted" style={{ fontSize: 13 }}>কোনো কেস নেই</div> : (
          <table className="pa-table">
            <thead><tr><th>কেস</th><th>প্রাধান্য</th><th>তৈরি</th></tr></thead>
            <tbody>{tenantCases.map(c => (
              <tr key={c.id}>
                <td style={{ fontSize: 13 }}>{c.title || c.subject || c.id}</td>
                <td><Badge tone={TONE_MAP[c.priority] || "neutral"}>{c.priority}</Badge></td>
                <td className="pa-muted" style={{ fontSize: 12 }}>{dateBn(c.created_at)}</td>
              </tr>
            ))}</tbody>
          </table>
        )}

        <div className="pa-section-title" style={{ marginTop: 16 }}>প্রাতিষ্ঠানিক তথ্য</div>
        <div className="pa-kv-list">
          <div className="pa-kv-row"><span>অবস্থা</span><Badge tone={STATE_TONE[orgState(org)] || "neutral"}>{orgState(org)}</Badge></div>
          <div className="pa-kv-row"><span>সেক্টর</span><span>{org.sector || "—"}</span></div>
          <div className="pa-kv-row"><span>তৈরি</span><span>{dateBn(org.created_at)}</span></div>
          <div className="pa-kv-row"><span>ফোন</span><span>{org.phone || "—"}</span></div>
          <div className="pa-kv-row"><span>সদস্য</span><span>{org.member_count ?? "—"}</span></div>
          <div className="pa-kv-row"><span>পণ্য</span><span>{org.product_count ?? "—"}</span></div>
        </div>
        {confirm.dialog}
      </div>
    </div>
  );
}

function TenantsPanel() {
  const { data, loading, error, reload } = useData(() => api.platformOrganizations());
  const [selected, setSelected] = useState(null);
  const [comparing, setComparing] = useState(false);
  const [q, setQ] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [checked, setChecked] = useState(new Set());
  // optimistic overrides: id → "suspended" | "active"
  const [optimistic, setOptimistic] = useState({});
  const toast = useToast();
  const confirm = useConfirm();

  const allOrgs = data?.organizations || data || [];
  // apply optimistic state
  const allOrgsOpt = allOrgs.map(o => optimistic[o.id] === "suspended"
    ? { ...o, active: false, suspended_at: new Date().toISOString() }
    : optimistic[o.id] === "active"
    ? { ...o, active: true, suspended_at: null }
    : o
  );
  const orgs = allOrgsOpt.filter(o => {
    const matchQ = !q || o.name?.toLowerCase().includes(q.toLowerCase()) || o.slug?.includes(q);
    const matchS = statusFilter === "all" || orgState(o) === statusFilter;
    return matchQ && matchS;
  });
  const paged = usePaged(orgs);

  function toggleCheck(id) {
    setChecked(s => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  }
  function toggleAll() {
    setChecked(s => s.size === paged.slice.length ? new Set() : new Set(paged.slice.map(o => o.id)));
  }

  async function suspend(org) {
    const reason = window.prompt("স্থগিতের কারণ লিখুন:");
    if (!reason) return;
    if (!await confirm(`"${org.name}" স্থগিত করবেন?`)) return;
    setOptimistic(p => ({ ...p, [org.id]: "suspended" }));
    try {
      await api.platformSuspend(org.id, reason);
      toast.success("স্থগিত হয়েছে");
      pushNotif({ kind: "action", title: `"${org.name}" স্থগিত হয়েছে` });
      reload();
    } catch (e) { toast.error(e.message); setOptimistic(p => { const n={...p}; delete n[org.id]; return n; }); }
  }

  async function unsuspend(org) {
    if (!await confirm(`"${org.name}" পুনরায় সক্রিয় করবেন?`)) return;
    setOptimistic(p => ({ ...p, [org.id]: "active" }));
    try {
      await api.platformUnsuspend(org.id);
      toast.success("সক্রিয় হয়েছে");
      pushNotif({ kind: "action", title: `"${org.name}" পুনরায় সক্রিয় হয়েছে` });
      reload();
    } catch (e) { toast.error(e.message); setOptimistic(p => { const n={...p}; delete n[org.id]; return n; }); }
  }

  async function bulkSuspend() {
    const targets = orgs.filter(o => checked.has(o.id) && orgState(o) !== "suspended");
    if (!targets.length) return;
    const reason = window.prompt(`${targets.length}টি ব্যবসা স্থগিত করার কারণ:`);
    if (!reason) return;
    if (!await confirm(`${targets.length}টি ব্যবসা স্থগিত করবেন?`)) return;
    targets.forEach(o => setOptimistic(p => ({ ...p, [o.id]: "suspended" })));
    let ok = 0;
    for (const o of targets) {
      try { await api.platformSuspend(o.id, reason); ok++; } catch {}
    }
    toast.success(`${ok}টি স্থগিত হয়েছে`); setChecked(new Set()); reload();
  }

  async function bulkUnsuspend() {
    const targets = orgs.filter(o => checked.has(o.id) && orgState(o) === "suspended");
    if (!targets.length) return;
    if (!await confirm(`${targets.length}টি ব্যবসা সক্রিয় করবেন?`)) return;
    targets.forEach(o => setOptimistic(p => ({ ...p, [o.id]: "active" })));
    let ok = 0;
    for (const o of targets) {
      try { await api.platformUnsuspend(o.id); ok++; } catch {}
    }
    toast.success(`${ok}টি সক্রিয় হয়েছে`); setChecked(new Set()); reload();
  }

  function doExport() {
    exportCsv("tenants.csv", orgs, [
      { label: "নাম",    get: o => o.name },
      { label: "Slug",   get: o => o.slug },
      { label: "অবস্থা", get: o => orgState(o) },
      { label: "সেক্টর", get: o => o.sector || "" },
      { label: "তৈরি",   get: o => o.created_at || "" },
    ]);
  }

  return (
    <>
      <Head title="ব্যবসা তালিকা" sub="সব ব্যবসার তালিকা, স্বাস্থ্য এবং ৩৬০° বিশদ"
        action={<div style={{ display:"flex", gap:8 }}>
          <Button size="sm" variant="secondary" onClick={() => setComparing(true)}>তুলনা করুন</Button>
          <Button size="sm" variant="secondary" onClick={doExport}>CSV ডাউনলোড</Button>
        </div>} />

      <div style={{ display: "flex", gap: 10, marginBottom: 16, flexWrap: "wrap" }}>
        <input className="pa-search" style={{ flex: 1, minWidth: 180 }} placeholder="নাম বা slug খুঁজুন…" value={q}
          onChange={e => { setQ(e.target.value); paged.reset(); }} />
        <select className="pa-input" style={{ width: 130 }} value={statusFilter}
          onChange={e => { setStatusFilter(e.target.value); paged.reset(); }}>
          <option value="all">সব অবস্থা</option>
          <option value="active">সক্রিয়</option>
          <option value="suspended">স্থগিত</option>
          <option value="inactive">নিষ্ক্রিয়</option>
        </select>
      </div>

      {checked.size > 0 && (
        <div className="pa-bulk-bar">
          <span>{checked.size}টি নির্বাচিত</span>
          <Button size="sm" variant="danger" onClick={bulkSuspend}>স্থগিত করুন</Button>
          <Button size="sm" variant="secondary" onClick={bulkUnsuspend}>সক্রিয় করুন</Button>
          <Button size="sm" variant="secondary" onClick={() => setChecked(new Set())}>বাতিল</Button>
        </div>
      )}

      {loading ? <Skeleton lines={6} /> : error ? <Notice tone="danger">{error}</Notice> : (
        <>
          <div className="pa-table-wrap">
            <table className="pa-table">
              <thead><tr>
                <th style={{ width: 32 }}><input type="checkbox" checked={checked.size === paged.slice.length && paged.slice.length > 0} onChange={toggleAll} /></th>
                <th>নাম</th><th>Slug</th><th>অবস্থা</th><th>স্বাস্থ্য</th><th>সেক্টর</th><th>তৈরি</th><th>অ্যাকশন</th>
              </tr></thead>
              <tbody>{paged.slice.map(o => (
                <tr key={o.id} className={checked.has(o.id) ? "pa-row-checked" : ""}>
                  <td><input type="checkbox" checked={checked.has(o.id)} onChange={() => toggleCheck(o.id)} /></td>
                  <td><button className="pa-link-btn" onClick={() => setSelected(o)}>{o.name}</button></td>
                  <td className="pa-muted" style={{ fontFamily: "monospace", fontSize: 12 }}>{o.slug}</td>
                  <td><Badge tone={STATE_TONE[orgState(o)] || "neutral"}>{orgState(o)}</Badge></td>
                  <td><TenantHealthBadge orgId={o.id} /></td>
                  <td className="pa-muted" style={{ fontSize: 12 }}>{o.sector || "—"}</td>
                  <td className="pa-muted" style={{ fontSize: 12 }}>{dateBn(o.created_at)}</td>
                  <td>
                    <div className="pa-row-actions">
                      <Button size="sm" variant="secondary" onClick={() => setSelected(o)}>৩৬০°</Button>
                      {orgState(o) === "suspended"
                        ? <Button size="sm" variant="secondary" onClick={() => unsuspend(o)}>সক্রিয় করুন</Button>
                        : <Button size="sm" variant="danger" onClick={() => suspend(o)}>স্থগিত</Button>}
                    </div>
                  </td>
                </tr>
              ))}</tbody>
            </table>
            {orgs.length === 0 && <EmptyState title="কোনো ব্যবসা পাওয়া যায়নি" />}
          </div>
          {paged.pager}
        </>
      )}
      {selected && <Tenant360Drawer org={selected} onClose={() => { setSelected(null); reload(); }} />}
      {comparing && <TenantCompareModal orgs={allOrgsOpt} onClose={() => setComparing(false)} />}
      {confirm.dialog}
    </>
  );
}

// ─── 3. DATA READINESS ────────────────────────────────────────────────────────
function DataReadinessPanel() {
  const { data: orgsData, loading: ol } = useData(() => api.platformOrganizations());
  const orgs = orgsData?.organizations || orgsData || [];

  // Derive readiness from real org fields
  function readinessScore(org) {
    if (!org.active) return 10;
    // More products + recent sales = better data readiness
    const base = 35;
    const productBonus = Math.min(30, (org.product_count || 0) * 2);
    const recentBonus = org.last_sale_at ? 20 : 0;
    const memberBonus = Math.min(10, (org.member_count || 0) * 2);
    const sectorBonus = org.sector === "pharmacy" ? 5 : 0;
    return Math.min(100, base + productBonus + recentBonus + memberBonus + sectorBonus);
  }
  function readinessTone(s) { return s >= 70 ? "success" : s >= 40 ? "warn" : "danger"; }

  return (
    <>
      <Head title="ডেটা প্রস্তুতি" sub="প্রতিটি টেন্যান্টের AI-প্রস্তুতি এবং ডেটা মান পরীক্ষা" />
      {ol ? <Skeleton lines={6} /> : (
        <>
          <div className="pa-stats-grid" style={{ marginBottom: 20 }}>
            <Stat label="মোট টেন্যান্ট" value={fmt(orgs.length)} />
            <Stat label="AI-প্রস্তুত (≥70)" value={fmt(orgs.filter(o => readinessScore(o) >= 70).length)} tone="success" />
            <Stat label="নিষ্ক্রিয়" value={fmt(orgs.filter(o => !o.active).length)} tone="warn" />
          </div>
          <div className="pa-table-wrap">
            <table className="pa-table">
              <thead><tr><th>ব্যবসা</th><th>অবস্থা</th><th>AI স্কোর</th><th>প্রয়োজনীয় পদক্ষেপ</th></tr></thead>
              <tbody>{orgs.map(o => {
                const score = readinessScore(o);
                const issues = [];
                if (!o.active) issues.push("ব্যবসা নিষ্ক্রিয়");
                if (!o.last_sale_at) issues.push("সাম্প্রতিক বিক্রয় নেই");
                if ((o.product_count || 0) < 5) issues.push("পণ্য কম");
                if (score < 70 && issues.length === 0) issues.push("ডেটা বাড়ান");
                return (
                  <tr key={o.id}>
                    <td style={{ fontWeight: 500 }}>{o.name}</td>
                    <td><Badge tone={STATE_TONE[orgState(o)] || "neutral"}>{orgState(o)}</Badge></td>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <div style={{ width: 60, height: 6, background: "var(--border)", borderRadius: 3 }}>
                          <div style={{ width: `${score}%`, height: "100%", background: score >= 70 ? "#0a8754" : score >= 40 ? "#f59e0b" : "#e63946", borderRadius: 3 }} />
                        </div>
                        <Badge tone={readinessTone(score)}>{score}</Badge>
                      </div>
                    </td>
                    <td style={{ fontSize: 12, color: "var(--text-muted)" }}>
                      {issues.length === 0 ? <Badge tone="success">ঠিক আছে</Badge> : issues.join(" · ")}
                    </td>
                  </tr>
                );
              })}</tbody>
            </table>
            {orgs.length === 0 && <EmptyState title="কোনো টেন্যান্ট পাওয়া যায়নি" />}
          </div>
        </>
      )}
    </>
  );
}

// ─── 4. AI GOVERNANCE ─────────────────────────────────────────────────────────
function AiGovernancePanel() {
  const { data: registry, loading: rl, error: re, reload: rReload } = useData(() => api.adminModelRegistry());
  const { data: kills,    loading: kl, error: ke, reload: kReload } = useData(() => api.adminKillSwitches());
  const { data: outcomes, loading: outl } = useData(() => api.adminModelOutcomes());
  const toast = useToast();
  const [subTab, setSubTab] = useState("registry");

  const models = registry?.entries || [];
  const switches = kills?.switches || kills || [];
  const outcomeList = outcomes?.records || [];

  async function toggleKill(sw) {
    try {
      await api.adminSetKillSwitch({ feature: sw.feature, disabled: !sw.killed, reason: sw.killed ? "Restored" : "Admin kill" });
      toast.success("Kill switch আপডেট হয়েছে"); kReload();
    } catch (e) { toast.error(e.message); }
  }

  const STAT_TONE = { validated: "success", active: "success", training: "warn", failed: "danger", stale: "neutral", "not-ready": "neutral" };

  return (
    <>
      <Head title="AI পরিচালনা" sub="মডেল রেজিস্ট্রি, ট্রেনিং স্ট্যাটাস, ড্রিফট এবং কিল সুইচ" />
      <div className="pa-sub-tabs" style={{ marginBottom: 20 }}>
        {[["registry","মডেল রেজিস্ট্রি"],["kill-switches","কিল সুইচ"],["outcomes","আউটকাম"]].map(([v,l]) => (
          <button key={v} className={`pa-sub-tab${subTab===v?" active":""}`} onClick={() => setSubTab(v)}>{l}</button>
        ))}
      </div>

      {subTab === "registry" && (
        <>
          {rl ? <Skeleton lines={5} /> : re ? <Notice tone="danger">{re}</Notice> : (
            <div className="pa-table-wrap">
              <table className="pa-table">
                <thead><tr><th>ফিচার</th><th>ভার্টিকাল</th><th>ভার্সন</th><th>স্ট্যাটাস</th><th>মেট্রিক্স</th><th>তারিখ</th></tr></thead>
                <tbody>{models.map((m, i) => (
                  <tr key={i}>
                    <td style={{ fontWeight: 500 }}>{m.feature}</td>
                    <td className="pa-muted">{m.vertical}</td>
                    <td style={{ fontFamily: "monospace", fontSize: 12 }}>{m.version}</td>
                    <td><Badge tone={STAT_TONE[m.status] || "neutral"}>{m.status}</Badge></td>
                    <td style={{ fontSize: 12 }}>
                      {m.metrics ? Object.entries(m.metrics).slice(0, 2).map(([k, v]) => `${k}: ${typeof v === "number" ? v.toFixed(3) : v}`).join(" · ") : "—"}
                    </td>
                    <td className="pa-muted" style={{ fontSize: 12 }}>{dateBn(m.trained_at)}</td>
                  </tr>
                ))}</tbody>
              </table>
              {models.length === 0 && <EmptyState title="কোনো মডেল নেই" />}
            </div>
          )}
        </>
      )}

      {subTab === "kill-switches" && (
        <>
          <Notice tone="warn" style={{ marginBottom: 16 }}>কিল সুইচ চালু করলে সেই ফিচারের AI বন্ধ হয়ে ফলব্যাক চালু হবে।</Notice>
          {kl ? <Skeleton lines={4} /> : ke ? <Notice tone="danger">{ke}</Notice> : (
            <div className="pa-table-wrap">
              <table className="pa-table">
                <thead><tr><th>ফিচার</th><th>অবস্থা</th><th>কারণ</th><th>সময়</th><th>অ্যাকশন</th></tr></thead>
                <tbody>{switches.map((sw, i) => (
                  <tr key={i}>
                    <td style={{ fontWeight: 500 }}>{sw.feature}</td>
                    <td><Badge tone={sw.killed ? "danger" : "success"}>{sw.killed ? "বন্ধ" : "চালু"}</Badge></td>
                    <td className="pa-muted" style={{ fontSize: 12 }}>{sw.reason || "—"}</td>
                    <td className="pa-muted" style={{ fontSize: 12 }}>{dateTimeBn(sw.updated_at)}</td>
                    <td>
                      <Button size="sm" variant={sw.killed ? "secondary" : "danger"} onClick={() => toggleKill(sw)}>
                        {sw.killed ? "চালু করুন" : "বন্ধ করুন"}
                      </Button>
                    </td>
                  </tr>
                ))}</tbody>
              </table>
              {switches.length === 0 && <EmptyState title="কোনো কিল সুইচ কনফিগার নেই" />}
            </div>
          )}
        </>
      )}

      {subTab === "outcomes" && (
        <>
          {outl ? <Skeleton lines={5} /> : (
            <div className="pa-table-wrap">
              <table className="pa-table">
                <thead><tr><th>ফিচার</th><th>ভার্টিকাল</th><th>মেট্রিক</th><th>প্রকৃত</th><th>পূর্বাভাস</th><th>তারিখ</th></tr></thead>
                <tbody>{outcomeList.map((o, i) => (
                  <tr key={i}>
                    <td>{o.feature}</td>
                    <td className="pa-muted">{o.vertical}</td>
                    <td className="pa-muted">{o.metric_name}</td>
                    <td>{o.actual_value != null ? o.actual_value.toFixed(3) : "—"}</td>
                    <td>{o.predicted_value != null ? o.predicted_value.toFixed(3) : "—"}</td>
                    <td className="pa-muted" style={{ fontSize: 12 }}>{dateBn(o.measured_at)}</td>
                  </tr>
                ))}</tbody>
              </table>
              {outcomeList.length === 0 && <EmptyState title="কোনো আউটকাম ডেটা নেই" />}
            </div>
          )}
        </>
      )}
    </>
  );
}

// ─── 5. RECOMMENDATION OPS ────────────────────────────────────────────────────
function RecommendationOpsPanel() {
  const { data, loading, error } = useData(() => api.bsmartMonitoring(null));

  const d = data || {};
  const decisions = d.decisions || [];
  const total = decisions.length;
  const accepted = decisions.filter(x => x.decision === "accept").length;
  const rejected = decisions.filter(x => x.decision === "reject").length;
  const deferred = decisions.filter(x => x.decision === "defer").length;
  const measured = decisions.filter(x => x.outcome_metrics != null).length;

  return (
    <>
      <Head title="রেকমেন্ডেশন অপারেশন" sub="B-SMART Algorithm 1 এর অ্যাগ্রিগেট আউটকাম ও ইউটিলিটি স্কোর বিশ্লেষণ" />
      {loading ? <Skeleton lines={4} /> : error ? <Notice tone="danger">{error}</Notice> : (
        <>
          <div className="pa-stats-grid" style={{ marginBottom: 24 }}>
            <Stat label="মোট সিদ্ধান্ত"   value={fmt(total)} />
            <Stat label="গৃহীত"            value={fmt(accepted)}  tone="success" />
            <Stat label="প্রত্যাখ্যাত"    value={fmt(rejected)}  tone="danger" />
            <Stat label="স্থগিত"          value={fmt(deferred)}  tone="warn" />
            <Stat label="পরিমাপ করা হয়েছে" value={fmt(measured)} tone="info" />
            <Stat label="পরিমাপের হার"     value={pct(measured, total)} />
          </div>

          {decisions.length > 0 && (
            <>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginBottom: 20 }}>
                <div>
                  <div className="pa-section-title" style={{ marginBottom: 6 }}>সিদ্ধান্ত বিভাজন</div>
                  <div className="pa-chart-box">
                    <ResponsiveContainer width="100%" height={120}>
                      <BarChart data={[
                        { name: "গৃহীত",       value: accepted,  fill: "#0a8754" },
                        { name: "প্রত্যাখ্যাত", value: rejected, fill: "#e63946" },
                        { name: "স্থগিত",       value: deferred, fill: "#f59e0b" },
                        { name: "পরিমাপ",       value: measured,  fill: "#64748b" },
                      ]} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                        <XAxis dataKey="name" tick={{ fontSize: 10 }} tickLine={false} />
                        <YAxis tick={{ fontSize: 10 }} tickLine={false} axisLine={false} allowDecimals={false} />
                        <Tooltip />
                        <Bar dataKey="value" name="সংখ্যা" radius={[3,3,0,0]}>
                          {[accepted, rejected, deferred, measured].map((_, i) => (
                            <rect key={i} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
                <div className="pa-stats-grid" style={{ alignContent: "start" }}>
                  <Stat label="পরিমাপের হার" value={pct(measured, total)} tone={measured / total > 0.5 ? "success" : "warn"} />
                  <Stat label="গ্রহণের হার"  value={pct(accepted, total)} tone={accepted / total > 0.5 ? "success" : "neutral"} />
                </div>
              </div>
              <div className="pa-section-title" style={{ marginBottom: 8 }}>সাম্প্রতিক সিদ্ধান্ত</div>
              <div className="pa-table-wrap">
                <table className="pa-table">
                  <thead><tr><th>রেকমেন্ডেশন</th><th>সিদ্ধান্ত</th><th>আউটকাম</th><th>তারিখ</th></tr></thead>
                  <tbody>{decisions.slice(0, 10).map(dec => (
                    <tr key={dec.id}>
                      <td style={{ fontSize: 13 }}>{dec.recommendation_id}</td>
                      <td><Badge tone={dec.decision === "accept" ? "success" : dec.decision === "reject" ? "danger" : "warn"}>{dec.decision}</Badge></td>
                      <td style={{ fontSize: 12 }}>
                        {dec.outcome_metrics != null
                          ? <Badge tone="info">পরিমাপ করা হয়েছে</Badge>
                          : <span className="pa-muted">অপেক্ষমান</span>}
                      </td>
                      <td className="pa-muted" style={{ fontSize: 12 }}>{dateBn(dec.decided_at)}</td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>
            </>
          )}

          {decisions.length === 0 && (
            <EmptyState title="কোনো রেকমেন্ডেশন সিদ্ধান্ত নেই" sub="ব্যবসাগুলো B-SMART রেকমেন্ডেশন দেখতে ও গ্রহণ করতে শুরু করলে এখানে ডেটা আসবে।" />
          )}
        </>
      )}
    </>
  );
}

// ─── 6. PLANS & ENTITLEMENTS ──────────────────────────────────────────────────
function PlansPanel() {
  const { data: plansData, loading, error, reload } = useData(() => api.adminPlans());
  const { data: usageData } = useData(() => api.adminUsage());
  const [creating, setCreating] = useState(false);
  const [newPlan, setNewPlan]   = useState({ code: "", name: "", price_bdt: 0 });
  const toast = useToast();

  const plans = plansData?.plans || plansData || [];
  const usage = usageData?.tenants || [];

  async function createPlan() {
    try { await api.adminCreatePlan(newPlan); toast.success("প্ল্যান তৈরি হয়েছে"); reload(); setCreating(false); }
    catch (e) { toast.error(e.message); }
  }

  return (
    <>
      <Head
        title="প্ল্যান ও এনটাইটেলমেন্ট"
        sub="সাবস্ক্রিপশন প্ল্যান, কোটা এবং ফিচার এনটাইটেলমেন্ট"
        action={<Button size="sm" onClick={() => setCreating(true)}>নতুন প্ল্যান</Button>}
      />

      {loading ? <Skeleton lines={5} /> : error ? <Notice tone="danger">{error}</Notice> : (
        <div className="pa-table-wrap" style={{ marginBottom: 24 }}>
          <table className="pa-table">
            <thead><tr><th>প্ল্যান</th><th>মূল্য (৳/মাস)</th><th>ব্যবহারকারী</th><th>শাখা</th><th>AI</th><th>ট্রায়াল দিন</th></tr></thead>
            <tbody>{plans.map(p => (
              <tr key={p.id}>
                <td style={{ fontWeight: 600 }}>{p.name}</td>
                <td>{fmt(p.price_bdt)}</td>
                <td>{p.max_users ?? "∞"}</td>
                <td>{p.max_branches ?? "∞"}</td>
                <td><Badge tone={p.ai_enabled ? "success" : "neutral"}>{p.ai_enabled ? "চালু" : "বন্ধ"}</Badge></td>
                <td>{p.trial_days ?? "—"}</td>
              </tr>
            ))}</tbody>
          </table>
          {plans.length === 0 && <EmptyState title="কোনো প্ল্যান নেই" />}
        </div>
      )}

      {usage.length > 0 && (
        <>
          <div className="pa-section-title" style={{ marginBottom: 8 }}>ব্যবহারের সারসংক্ষেপ</div>
          <div className="pa-table-wrap">
            <table className="pa-table">
              <thead><tr><th>ব্যবসা</th><th>ইভেন্ট</th><th>পরিমাণ</th><th>মাস</th></tr></thead>
              <tbody>{usage.slice(0, 10).map((u, i) => (
                <tr key={i}>
                  <td>{u.organization_id}</td>
                  <td>{u.event_type}</td>
                  <td>{fmt(u.quantity)}</td>
                  <td className="pa-muted">{u.period_month}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </>
      )}

      {creating && (
        <Modal title="নতুন প্ল্যান তৈরি করুন" onClose={() => setCreating(false)}>
          <Field label="কোড"><input className="pa-input" value={newPlan.code} onChange={e => setNewPlan(p => ({ ...p, code: e.target.value }))} placeholder="যেমন: starter, pro" /></Field>
          <Field label="নাম"><input className="pa-input" value={newPlan.name} onChange={e => setNewPlan(p => ({ ...p, name: e.target.value }))} /></Field>
          <Field label="মূল্য (৳/মাস)"><input className="pa-input" type="number" value={newPlan.price_bdt} onChange={e => setNewPlan(p => ({ ...p, price_bdt: +e.target.value }))} /></Field>
          <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
            <Button onClick={createPlan}>তৈরি করুন</Button>
            <Button variant="secondary" onClick={() => setCreating(false)}>বাতিল</Button>
          </div>
        </Modal>
      )}
    </>
  );
}

// ─── SLA COUNTDOWN ROW ────────────────────────────────────────────────────────
function CaseRow({ c }) {
  // SLA: urgent = 4h, high = 8h, normal = 24h, low = 72h from created_at
  const SLA_HOURS = { urgent: 4, high: 8, normal: 24, low: 72 };
  const deadline = c.created_at
    ? new Date(new Date(c.created_at).getTime() + (SLA_HOURS[c.priority] || 24) * 3600000).toISOString()
    : null;
  const { label, urgent } = useCountdown(deadline);
  return (
    <tr>
      <td style={{ fontSize: 13 }}>{c.title || c.subject}</td>
      <td><Badge tone={TONE_MAP[c.priority] || "neutral"}>{c.priority}</Badge></td>
      <td><Badge tone={c.status === "resolved" ? "success" : "warn"}>{c.status}</Badge></td>
      <td style={{ fontSize: 12, fontWeight: urgent ? 700 : 400, color: urgent ? "var(--danger)" : "var(--pa-muted)" }}>
        {c.status === "resolved" ? <span style={{ color: "var(--green)" }}>✓ সমাধান</span> : (label || "—")}
      </td>
      <td className="pa-muted" style={{ fontSize: 12 }}>{dateBn(c.created_at)}</td>
    </tr>
  );
}

// ─── 7. SUPPORT & SUCCESS ─────────────────────────────────────────────────────
function SupportSuccessPanel() {
  const { data: casesData, loading: cl, error: ce, reload: cReload } = useData(() => api.adminSupportCases("open"));
  const { data: sla } = useData(() => api.adminSlaSummary());
  const { data: churnData, loading: chl } = useData(() => api.adminChurnRisk("high"));
  const toast = useToast();
  const [subTab, setSubTab] = useState("cases");
  const [creating, setCreating] = useState(false);
  const [newCase, setNewCase] = useState({ subject: "", priority: "normal", organization_id: "" });

  const cases = casesData?.cases || casesData || [];
  const churned = churnData?.risks || [];

  async function createCase() {
    try { await api.adminCreateSupportCase(newCase); toast.success("কেস তৈরি হয়েছে"); cReload(); setCreating(false); }
    catch (e) { toast.error(e.message); }
  }

  async function computeChurn() {
    try { await api.adminComputeChurnRisk(); toast.success("চার্ন স্কোর পুনর্গণনা হয়েছে"); }
    catch (e) { toast.error(e.message); }
  }

  return (
    <>
      <Head title="সাপোর্ট ও সাফল্য" sub="সাপোর্ট কেস, SLA স্ট্যাটাস এবং চার্ন রিস্ক" />
      <div className="pa-sub-tabs" style={{ marginBottom: 20 }}>
        {[["cases","সাপোর্ট কেস"],["sla","SLA সারসংক্ষেপ"],["churn","চার্ন রিস্ক"]].map(([v,l]) => (
          <button key={v} className={`pa-sub-tab${subTab===v?" active":""}`} onClick={() => setSubTab(v)}>{l}</button>
        ))}
      </div>

      {subTab === "cases" && (
        <>
          <div style={{ marginBottom: 12 }}>
            <Button size="sm" onClick={() => setCreating(true)}>নতুন কেস</Button>
          </div>
          {cl ? <Skeleton lines={5} /> : ce ? <Notice tone="danger">{ce}</Notice> : (
            <div className="pa-table-wrap">
              <table className="pa-table">
                <thead><tr><th>বিষয়</th><th>প্রাধান্য</th><th>অবস্থা</th><th>SLA বাকি</th><th>তৈরি</th></tr></thead>
                <tbody>{cases.map(c => <CaseRow key={c.id} c={c} />)}</tbody>
              </table>
              {cases.length === 0 && <EmptyState title="কোনো খোলা কেস নেই" />}
            </div>
          )}
          {creating && (
            <Modal title="নতুন সাপোর্ট কেস" onClose={() => setCreating(false)}>
              <Field label="বিষয়"><input className="pa-input" value={newCase.subject} onChange={e => setNewCase(p => ({ ...p, subject: e.target.value }))} /></Field>
              <Field label="প্রাধান্য">
                <select className="pa-input" value={newCase.priority} onChange={e => setNewCase(p => ({ ...p, priority: e.target.value }))}>
                  <option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option><option value="urgent">Urgent</option>
                </select>
              </Field>
              <Field label="Org ID"><input className="pa-input" value={newCase.organization_id} onChange={e => setNewCase(p => ({ ...p, organization_id: e.target.value }))} /></Field>
              <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
                <Button onClick={createCase}>তৈরি করুন</Button>
                <Button variant="secondary" onClick={() => setCreating(false)}>বাতিল</Button>
              </div>
            </Modal>
          )}
        </>
      )}

      {subTab === "sla" && (
        <>
          {sla ? (
            <div className="pa-stats-grid">
              <Stat label="মোট খোলা কেস"       value={fmt(sla.total_open)} />
              <Stat label="রেসপন্স ভঙ্গ"       value={fmt(sla.response_breached)}    tone={sla.response_breached > 0 ? "danger" : "success"} />
              <Stat label="রেজোলিউশন ভঙ্গ"     value={fmt(sla.resolution_breached)}  tone={sla.resolution_breached > 0 ? "danger" : "success"} />
              <Stat label="রেসপন্স ঝুঁকিতে"    value={fmt(sla.at_risk_response)}     tone={sla.at_risk_response > 0 ? "warn" : "success"} />
            </div>
          ) : <Skeleton lines={2} />}
        </>
      )}

      {subTab === "churn" && (
        <>
          <div style={{ marginBottom: 12 }}>
            <Button size="sm" variant="secondary" onClick={computeChurn}>চার্ন স্কোর পুনর্গণনা করুন</Button>
          </div>
          {chl ? <Skeleton lines={5} /> : (
            <div className="pa-table-wrap">
              <table className="pa-table">
                <thead><tr><th>ব্যবসা</th><th>চার্ন স্কোর</th><th>ঝুঁকি</th><th>শেষ লগইন</th></tr></thead>
                <tbody>{churned.map(t => (
                  <tr key={t.organization_id || t.id}>
                    <td style={{ fontWeight: 500 }}>{t.organization_name || t.organization_id}</td>
                    <td>{t.churn_score != null ? (t.churn_score * 100).toFixed(1) + "%" : "—"}</td>
                    <td><Badge tone={TONE_MAP[t.risk_level] || "neutral"}>{t.risk_level}</Badge></td>
                    <td className="pa-muted" style={{ fontSize: 12 }}>{dateBn(t.last_login_at)}</td>
                  </tr>
                ))}</tbody>
              </table>
              {churned.length === 0 && <EmptyState title="কোনো উচ্চ চার্ন রিস্ক নেই" />}
            </div>
          )}
        </>
      )}
    </>
  );
}

// ─── AUDIT LOG SUB-COMPONENT ─────────────────────────────────────────────────
function AuditLogTab({ audit, loading }) {
  const [actionQ, setActionQ] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo]   = useState("");

  const filtered = audit.filter(e => {
    const matchA = !actionQ || e.action?.includes(actionQ) || e.actor_email?.includes(actionQ);
    const matchF = !dateFrom || new Date(e.created_at) >= new Date(dateFrom);
    const matchT = !dateTo   || new Date(e.created_at) <= new Date(dateTo + "T23:59:59");
    return matchA && matchF && matchT;
  });
  const paged = usePaged(filtered);

  function doExport() {
    exportCsv("audit_log.csv", filtered, [
      { label: "অ্যাকশন",  get: e => e.action },
      { label: "অ্যাক্টর", get: e => e.actor_email || "system" },
      { label: "টার্গেট",  get: e => `${e.entity_type} ${e.entity_id || ""}` },
      { label: "সময়",     get: e => e.created_at },
    ]);
  }

  return (
    <>
      <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap", alignItems: "center" }}>
        <input className="pa-search" style={{ flex: 1, minWidth: 160 }} placeholder="অ্যাকশন বা অ্যাক্টর খুঁজুন…"
          value={actionQ} onChange={e => { setActionQ(e.target.value); paged.reset(); }} />
        <input type="date" className="pa-input" style={{ width: 140 }} value={dateFrom}
          onChange={e => { setDateFrom(e.target.value); paged.reset(); }} />
        <span className="pa-muted">—</span>
        <input type="date" className="pa-input" style={{ width: 140 }} value={dateTo}
          onChange={e => { setDateTo(e.target.value); paged.reset(); }} />
        <Button size="sm" variant="secondary" onClick={doExport}>CSV</Button>
      </div>
      {loading ? <Skeleton lines={5} /> : (
        <>
          <div className="pa-table-wrap">
            <table className="pa-table">
              <thead><tr><th>অ্যাকশন</th><th>অ্যাক্টর</th><th>টার্গেট</th><th>সময়</th></tr></thead>
              <tbody>{paged.slice.map((e, i) => (
                <tr key={i}>
                  <td style={{ fontFamily: "monospace", fontSize: 12 }}>{e.action}</td>
                  <td style={{ fontSize: 12 }}>{e.actor_email || "system"}</td>
                  <td style={{ fontSize: 12 }} className="pa-muted">{e.entity_type} {e.entity_id?.slice(0, 8)}</td>
                  <td className="pa-muted" style={{ fontSize: 12 }}>{dateTimeBn(e.created_at)}</td>
                </tr>
              ))}</tbody>
            </table>
            {filtered.length === 0 && <EmptyState title="কোনো লগ পাওয়া যায়নি" />}
          </div>
          {paged.pager}
        </>
      )}
    </>
  );
}

// ─── 8. SECURITY & AUDIT ─────────────────────────────────────────────────────
function SecurityAuditPanel() {
  const [subTab, setSubTab] = useState("alerts");
  const { data: alertsData, loading: al, error: ae, reload: aReload } = useData(() => api.adminSecurityAlerts("open"));
  const { data: jitData, loading: jl, reload: jReload } = useData(() => api.adminJitGrants(true));
  const { data: auditData, loading: auditL } = useData(() => api.platformAudit());
  const { data: adminsData, loading: adminL, reload: adminReload } = useData(() => api.platformAdministrators());
  const toast = useToast();
  const confirm = useConfirm();
  const [jitForm, setJitForm] = useState(null);
  const [newJit, setNewJit] = useState({ grantee_id: "", permission: "", reason: "", duration_minutes: 60 });

  const alerts = alertsData?.alerts || alertsData || [];
  const jit = jitData?.grants || jitData || [];
  const audit = auditData?.entries || [];
  const admins = adminsData?.administrators || [];

  async function resolveAlert(a) {
    const resolution = window.prompt("সমাধানের বিবরণ:");
    if (!resolution) return;
    try { await api.adminResolveAlert(a.id, { response_action: resolution }); toast.success("সমাধান হয়েছে"); aReload(); }
    catch (e) { toast.error(e.message); }
  }

  async function grantJit() {
    if (!newJit.grantee_id.trim() || !newJit.permission.trim() || !newJit.reason.trim()) return;
    try {
      await api.adminGrantJit({ grantee_id: newJit.grantee_id, permission: newJit.permission, reason: newJit.reason, duration_minutes: newJit.duration_minutes });
      toast.success("JIT অ্যাক্সেস দেওয়া হয়েছে");
      setJitForm(null);
      setNewJit({ grantee_id: "", permission: "", reason: "", duration_minutes: 60 });
      jReload();
    }
    catch (e) { toast.error(e.message); }
  }

  async function toggleAdmin(u) {
    const next = !u.is_platform_admin;
    if (!await confirm(`${u.email} কে ${next ? "অ্যাডমিন করবেন" : "অ্যাডমিন থেকে সরাবেন"}?`)) return;
    try { await api.platformSetAdministrator(u.id, next); toast.success("আপডেট হয়েছে"); adminReload(); }
    catch (e) { toast.error(e.message); }
  }

  return (
    <>
      <Head title="নিরাপত্তা ও অডিট" sub="অ্যালার্ট, JIT অ্যাক্সেস, অ্যাডমিন টিম এবং কার্যকলাপ লগ" />
      <div className="pa-sub-tabs" style={{ marginBottom: 20 }}>
        {[["alerts","সিকিউরিটি অ্যালার্ট"],["jit","JIT অ্যাক্সেস"],["admins","অ্যাডমিন টিম"],["audit","অডিট লগ"]].map(([v,l]) => (
          <button key={v} className={`pa-sub-tab${subTab===v?" active":""}`} onClick={() => setSubTab(v)}>{l}</button>
        ))}
      </div>

      {subTab === "alerts" && (
        <>
          {al ? <Skeleton lines={5} /> : ae ? <Notice tone="danger">{ae}</Notice> : (
            <div className="pa-table-wrap">
              <table className="pa-table">
                <thead><tr><th>ধরন</th><th>বিবরণ</th><th>তীব্রতা</th><th>সময়</th><th>অ্যাকশন</th></tr></thead>
                <tbody>{alerts.map(a => (
                  <tr key={a.id}>
                    <td style={{ fontSize: 13 }}>{a.alert_type}</td>
                    <td style={{ fontSize: 13 }}>{a.description}</td>
                    <td><Badge tone={TONE_MAP[a.severity] || "neutral"}>{a.severity}</Badge></td>
                    <td className="pa-muted" style={{ fontSize: 12 }}>{dateTimeBn(a.triggered_at)}</td>
                    <td><Button size="sm" variant="secondary" onClick={() => resolveAlert(a)}>সমাধান করুন</Button></td>
                  </tr>
                ))}</tbody>
              </table>
              {alerts.length === 0 && <EmptyState title="কোনো সক্রিয় অ্যালার্ট নেই" />}
            </div>
          )}
        </>
      )}

      {subTab === "jit" && (
        <>
          <div style={{ marginBottom: 12 }}>
            <Button size="sm" onClick={() => setJitForm(true)}>JIT অ্যাক্সেস দিন</Button>
          </div>
          {jitForm && (
            <Modal title="JIT অ্যাক্সেস দিন" onClose={() => setJitForm(null)}>
              <Field label="User ID"><input className="pa-input" value={newJit.grantee_id} onChange={e => setNewJit(p => ({ ...p, grantee_id: e.target.value }))} placeholder="ব্যবহারকারীর ID" /></Field>
              <Field label="পারমিশন"><input className="pa-input" value={newJit.permission} onChange={e => setNewJit(p => ({ ...p, permission: e.target.value }))} placeholder="যেমন: platform.admin" /></Field>
              <Field label="কারণ"><input className="pa-input" value={newJit.reason} onChange={e => setNewJit(p => ({ ...p, reason: e.target.value }))} placeholder="JIT অ্যাক্সেসের কারণ" /></Field>
              <Field label="সময়সীমা (মিনিট)">
                <select className="pa-input" value={newJit.duration_minutes} onChange={e => setNewJit(p => ({ ...p, duration_minutes: +e.target.value }))}>
                  <option value={15}>১৫ মিনিট</option>
                  <option value={30}>৩০ মিনিট</option>
                  <option value={60}>১ ঘন্টা</option>
                  <option value={240}>৪ ঘন্টা</option>
                  <option value={1440}>২৪ ঘন্টা</option>
                </select>
              </Field>
              <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
                <Button onClick={grantJit}>দিন</Button>
                <Button variant="secondary" onClick={() => setJitForm(null)}>বাতিল</Button>
              </div>
            </Modal>
          )}
          {jl ? <Skeleton lines={4} /> : (
            <div className="pa-table-wrap">
              <table className="pa-table">
                <thead><tr><th>User</th><th>কারণ</th><th>সময়সীমা</th><th>অবস্থা</th></tr></thead>
                <tbody>{jit.map(g => (
                  <tr key={g.id}>
                    <td>{g.target_user_id}</td>
                    <td style={{ fontSize: 13 }}>{g.reason}</td>
                    <td className="pa-muted">{g.expires_at ? dateTimeBn(g.expires_at) : "—"}</td>
                    <td><Badge tone={g.revoked_at ? "neutral" : "success"}>{g.revoked_at ? "প্রত্যাহৃত" : "সক্রিয়"}</Badge></td>
                  </tr>
                ))}</tbody>
              </table>
              {jit.length === 0 && <EmptyState title="কোনো সক্রিয় JIT গ্রান্ট নেই" />}
            </div>
          )}
        </>
      )}

      {subTab === "admins" && (
        <>
          {adminL ? <Skeleton lines={4} /> : (
            <div className="pa-table-wrap">
              <table className="pa-table">
                <thead><tr><th>ইমেইল</th><th>নাম</th><th>অ্যাডমিন</th><th>অ্যাকশন</th></tr></thead>
                <tbody>{admins.map(u => (
                  <tr key={u.id}>
                    <td>{u.email}</td>
                    <td>{u.display_name || "—"}</td>
                    <td><Badge tone={u.is_platform_admin ? "success" : "neutral"}>{u.is_platform_admin ? "হ্যাঁ" : "না"}</Badge></td>
                    <td>
                      <Button size="sm" variant={u.is_platform_admin ? "danger" : "secondary"} onClick={() => toggleAdmin(u)}>
                        {u.is_platform_admin ? "সরান" : "অ্যাডমিন করুন"}
                      </Button>
                    </td>
                  </tr>
                ))}</tbody>
              </table>
              {admins.length === 0 && <EmptyState title="কোনো অ্যাডমিন নেই" />}
            </div>
          )}
        </>
      )}

      {subTab === "audit" && (
        <AuditLogTab audit={audit} loading={auditL} />
      )}
      {confirm.dialog}
    </>
  );
}

// ─── 9. SYSTEM OPS ────────────────────────────────────────────────────────────
function SystemOpsPanel() {
  const [subTab, setSubTab] = useState("health");
  const { data: health, loading: hl } = useData(() => api.platformSystemHealth());
  const { data: jobsData, loading: jl, reload: jReload } = useData(() => api.adminJobs("failed"));
  const { data: inciData, loading: il, reload: iReload } = useData(() => api.adminIncidents("open"));
  const { data: rolloutData, loading: rl } = useData(() => api.adminRolloutConfigs());
  const { data: backupsData, loading: bl, reload: bReload } = useData(() => api.platformBackups());
  const toast = useToast();
  const confirm = useConfirm();
  const [inciForm, setInciForm] = useState(false);
  const [newInci, setNewInci]   = useState({ title: "", severity: "p2" });
  const [resolveForm, setResolveForm] = useState(null);
  const [resolveNote, setResolveNote] = useState("");

  const h = health || {};
  const jobs = jobsData?.jobs || jobsData || [];
  const incidents = inciData?.incidents || inciData || [];
  const rollouts = rolloutData?.configs || rolloutData || [];
  const backups = backupsData?.backups || [];
  const jobsPaged = usePaged(jobs);

  async function retryJob(job) {
    try { await api.adminRetryJob(job.id); toast.success("পুনরায় চেষ্টা শুরু হয়েছে"); jReload(); }
    catch (e) { toast.error(e.message); }
  }

  async function createIncident() {
    if (!newInci.title.trim()) return;
    try {
      await api.adminCreateIncident(newInci);
      toast.success("ইনসিডেন্ট তৈরি হয়েছে"); setInciForm(false);
      setNewInci({ title: "", severity: "p2" }); iReload();
    } catch (e) { toast.error(e.message); }
  }

  async function resolveIncident() {
    try {
      await api.adminUpdateIncident(resolveForm.id, { status: "resolved", resolution_summary: resolveNote });
      toast.success("সমাধান হয়েছে"); setResolveForm(null); setResolveNote(""); iReload();
    } catch (e) { toast.error(e.message); }
  }

  async function createBackup() {
    try { await api.platformCreateBackup(); toast.success("ব্যাকআপ তৈরি হচ্ছে"); bReload(); }
    catch (e) { toast.error(e.message); }
  }

  async function deleteBackup(b) {
    if (!await confirm(`"${b.filename}" মুছবেন?`)) return;
    try { await api.platformDeleteBackup(b.filename); toast.success("মুছে গেছে"); bReload(); }
    catch (e) { toast.error(e.message); }
  }

  const HEALTH_TONE = { healthy: "success", degraded: "warn", down: "danger" };

  return (
    <>
      <Head title="সিস্টেম অপারেশন" sub="সিস্টেম স্বাস্থ্য, ব্যর্থ জব, ইনসিডেন্ট, রোলআউট এবং ব্যাকআপ" />
      <div className="pa-sub-tabs" style={{ marginBottom: 20 }}>
        {[["health","স্বাস্থ্য"],["jobs","ব্যর্থ জব"],["incidents","ইনসিডেন্ট"],["rollouts","রোলআউট"],["backups","ব্যাকআপ"]].map(([v,l]) => (
          <button key={v} className={`pa-sub-tab${subTab===v?" active":""}`} onClick={() => setSubTab(v)}>{l}</button>
        ))}
      </div>

      {subTab === "health" && (
        <>
          {hl ? <Skeleton lines={3} /> : (
            <>
              <div className="pa-stats-grid" style={{ marginBottom: 16 }}>
                <Stat label="ডেটাবেজ"       value={h.database?.connected ? "সংযুক্ত" : "বিচ্ছিন্ন"} tone={h.database?.connected ? "success" : "danger"} />
                <Stat label="পরিবেশ"         value={h.environment || "—"} />
                <Stat label="Auth মোড"        value={h.auth_mode || "—"} />
                <Stat label="Integration"     value={h.integration_mode || "—"} />
                <Stat label="Provider প্রস্তুত" value={`${h.provider_ready_count ?? 0} / ${h.provider_total ?? 0}`} tone={h.provider_ready_count > 0 ? "success" : "warn"} />
              </div>
              {(h.providers || []).length > 0 && (
                <div className="pa-table-wrap">
                  <table className="pa-table">
                    <thead><tr><th>Provider</th><th>ধরন</th><th>অবস্থা</th></tr></thead>
                    <tbody>{(h.providers || []).map(p => (
                      <tr key={p.key}>
                        <td style={{ fontWeight: 500 }}>{p.name}</td>
                        <td className="pa-muted">{p.category}</td>
                        <td><Badge tone={p.configured ? "success" : "neutral"}>{p.configured ? "কনফিগার্ড" : "কনফিগার নেই"}</Badge></td>
                      </tr>
                    ))}</tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </>
      )}

      {subTab === "jobs" && (
        <>
          {jl ? <Skeleton lines={5} /> : (
            <>
              <div className="pa-table-wrap">
                <table className="pa-table">
                  <thead><tr><th>জব টাইপ</th><th>অবস্থা</th><th>ত্রুটি</th><th>সময়</th><th>অ্যাকশন</th></tr></thead>
                  <tbody>{jobsPaged.slice.map(j => (
                    <tr key={j.id}>
                      <td>{j.job_type}</td>
                      <td><Badge tone={j.status === "failed" ? "danger" : "neutral"}>{j.status}</Badge></td>
                      <td style={{ fontSize: 12 }} className="pa-muted">{j.error_message?.slice(0, 60) || "—"}</td>
                      <td className="pa-muted" style={{ fontSize: 12 }}>{dateTimeBn(j.created_at)}</td>
                      <td><Button size="sm" variant="secondary" onClick={() => retryJob(j)}>পুনরায় চেষ্টা</Button></td>
                    </tr>
                  ))}</tbody>
                </table>
                {jobs.length === 0 && <EmptyState title="কোনো ব্যর্থ জব নেই" />}
              </div>
              {jobsPaged.pager}
            </>
          )}
        </>
      )}

      {subTab === "incidents" && (
        <>
          <div style={{ marginBottom: 12 }}>
            <Button size="sm" onClick={() => setInciForm(true)}>নতুন ইনসিডেন্ট</Button>
          </div>
          {inciForm && (
            <Modal title="নতুন ইনসিডেন্ট" onClose={() => setInciForm(false)}>
              <Field label="শিরোনাম"><input className="pa-input" value={newInci.title} onChange={e => setNewInci(p => ({ ...p, title: e.target.value }))} placeholder="সমস্যার সংক্ষিপ্ত বিবরণ" /></Field>
              <Field label="তীব্রতা">
                <select className="pa-input" value={newInci.severity} onChange={e => setNewInci(p => ({ ...p, severity: e.target.value }))}>
                  <option value="p1">P1 — সর্বোচ্চ জরুরি</option>
                  <option value="p2">P2 — উচ্চ</option>
                  <option value="p3">P3 — মাঝারি</option>
                  <option value="p4">P4 — কম</option>
                </select>
              </Field>
              <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
                <Button onClick={createIncident}>তৈরি করুন</Button>
                <Button variant="secondary" onClick={() => setInciForm(false)}>বাতিল</Button>
              </div>
            </Modal>
          )}
          {resolveForm && (
            <Modal title={`সমাধান: ${resolveForm.title}`} onClose={() => setResolveForm(null)}>
              <Field label="সমাধানের বিবরণ">
                <textarea className="pa-textarea" rows={3} value={resolveNote} onChange={e => setResolveNote(e.target.value)} placeholder="কীভাবে সমাধান হলো…" />
              </Field>
              <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
                <Button onClick={resolveIncident}>সমাধান করুন</Button>
                <Button variant="secondary" onClick={() => setResolveForm(null)}>বাতিল</Button>
              </div>
            </Modal>
          )}
          {il ? <Skeleton lines={4} /> : (
            <div className="pa-table-wrap">
              <table className="pa-table">
                <thead><tr><th>শিরোনাম</th><th>তীব্রতা</th><th>অবস্থা</th><th>শুরু</th><th>অ্যাকশন</th></tr></thead>
                <tbody>{incidents.map(inc => (
                  <tr key={inc.id}>
                    <td style={{ fontWeight: 500 }}>{inc.title}</td>
                    <td><Badge tone={inc.severity === "p1" ? "danger" : inc.severity === "p2" ? "warn" : "neutral"}>{inc.severity?.toUpperCase()}</Badge></td>
                    <td><Badge tone={inc.status === "resolved" ? "success" : "warn"}>{inc.status}</Badge></td>
                    <td className="pa-muted" style={{ fontSize: 12 }}>{dateTimeBn(inc.started_at)}</td>
                    <td>
                      {inc.status !== "resolved" && (
                        <Button size="sm" variant="secondary" onClick={() => { setResolveForm(inc); setResolveNote(""); }}>সমাধান করুন</Button>
                      )}
                    </td>
                  </tr>
                ))}</tbody>
              </table>
              {incidents.length === 0 && <EmptyState title="কোনো সক্রিয় ইনসিডেন্ট নেই" />}
            </div>
          )}
        </>
      )}

      {subTab === "rollouts" && (
        <>
          {rl ? <Skeleton lines={4} /> : (
            <div className="pa-table-wrap">
              <table className="pa-table">
                <thead><tr><th>ফিচার</th><th>ধাপ</th><th>অবস্থা</th><th>তৈরি</th><th>অ্যাকশন</th></tr></thead>
                <tbody>{rollouts.map(r => (
                  <tr key={r.id}>
                    <td style={{ fontWeight: 500 }}>{r.feature_key}</td>
                    <td>{r.current_stage}</td>
                    <td><Badge tone={r.status === "active" ? "success" : r.status === "rolled_back" ? "danger" : "neutral"}>{r.status}</Badge></td>
                    <td className="pa-muted" style={{ fontSize: 12 }}>{dateBn(r.created_at)}</td>
                    <td>
                      <div className="pa-row-actions">
                        <Button size="sm" variant="secondary" onClick={() => api.adminAdvanceRollout(r.id, {}).catch(e => toast.error(e.message))}>এগিয়ে নিন</Button>
                        <Button size="sm" variant="danger" onClick={() => api.adminRollbackRollout(r.id).catch(e => toast.error(e.message))}>রোলব্যাক</Button>
                      </div>
                    </td>
                  </tr>
                ))}</tbody>
              </table>
              {rollouts.length === 0 && <EmptyState title="কোনো রোলআউট কনফিগ নেই" />}
            </div>
          )}
        </>
      )}

      {subTab === "backups" && (
        <>
          <div style={{ marginBottom: 12 }}>
            <Button size="sm" onClick={createBackup}>নতুন ব্যাকআপ তৈরি করুন</Button>
          </div>
          {bl ? <Skeleton lines={4} /> : (
            <div className="pa-table-wrap">
              <table className="pa-table">
                <thead><tr><th>ফাইল</th><th>আকার</th><th>তারিখ</th><th>অ্যাকশন</th></tr></thead>
                <tbody>{backups.map(b => (
                  <tr key={b.filename}>
                    <td style={{ fontFamily: "monospace", fontSize: 12 }}>{b.filename}</td>
                    <td className="pa-muted">{b.size_mb != null ? `${b.size_mb} MB` : "—"}</td>
                    <td className="pa-muted">{dateTimeBn(b.created_at)}</td>
                    <td>
                      <div className="pa-row-actions">
                        <Button size="sm" variant="secondary" onClick={() => api.platformDownloadBackup(b.filename)}>ডাউনলোড</Button>
                        <Button size="sm" variant="danger" onClick={() => deleteBackup(b)}>মুছুন</Button>
                      </div>
                    </td>
                  </tr>
                ))}</tbody>
              </table>
              {backups.length === 0 && <EmptyState title="কোনো ব্যাকআপ নেই" />}
            </div>
          )}
        </>
      )}
      {confirm.dialog}
    </>
  );
}

// ─── SITE CONTENT ─────────────────────────────────────────────────────────────
const SITE_SCHEMA = [
  // ── হোম পেজ ──────────────────────────────────────────────────────────────
  { group: "হিরো ব্যানার", keys: [
    { key: "hero.kicker",        label: "Kicker ট্যাগ",         type: "string", rows: 1 },
    { key: "hero.title",         label: "শিরোনাম (H1)",         type: "string", rows: 2 },
    { key: "hero.subtitle",      label: "সাবটাইটেল",            type: "string", rows: 3 },
    { key: "hero.cta_primary",   label: "প্রাথমিক বোতাম",      type: "string", rows: 1 },
    { key: "hero.cta_secondary", label: "সেকেন্ডারি বোতাম",    type: "string", rows: 1 },
    { key: "hero.assurance_1",   label: "আশ্বাস ১",             type: "string", rows: 1 },
    { key: "hero.assurance_2",   label: "আশ্বাস ২",             type: "string", rows: 1 },
    { key: "hero.assurance_3",   label: "আশ্বাস ৩",             type: "string", rows: 1 },
  ]},
  { group: "স্ট্রিপ ব্যান্ড", keys: [
    { key: "strip.label",  label: "লেবেল",   type: "string", rows: 1 },
    { key: "strip.item_1", label: "আইটেম ১", type: "string", rows: 1 },
    { key: "strip.item_2", label: "আইটেম ২", type: "string", rows: 1 },
    { key: "strip.item_3", label: "আইটেম ৩", type: "string", rows: 1 },
    { key: "strip.item_4", label: "আইটেম ৪", type: "string", rows: 1 },
    { key: "strip.item_5", label: "আইটেম ৫", type: "string", rows: 1 },
    { key: "strip.item_6", label: "আইটেম ৬", type: "string", rows: 1 },
  ]},
  { group: "সমস্যা সেকশন", keys: [
    { key: "problems.eyebrow", label: "Eyebrow",       type: "string", rows: 1 },
    { key: "problems.title",   label: "শিরোনাম",      type: "string", rows: 2 },
    { key: "problems.text",    label: "সাবটেক্সট",    type: "string", rows: 2 },
    { key: "owner_problems",   label: "সমস্যা JSON",   type: "json",   rows: 8 },
  ]},
  { group: "বাংলাদেশ রেডি", keys: [
    { key: "bd_ready.eyebrow", label: "Eyebrow",      type: "string", rows: 1 },
    { key: "bd_ready.title",   label: "শিরোনাম",     type: "string", rows: 2 },
    { key: "bd_ready.text",    label: "সাবটেক্সট",   type: "string", rows: 2 },
    { key: "bangladesh_ready", label: "আইটেম JSON",  type: "json",   rows: 8 },
  ]},
  // ── শেয়ারড কম্পোনেন্ট ─────────────────────────────────────────────────
  { group: "CTA ব্যান্ড", keys: [
    { key: "cta_band.eyebrow",       label: "Eyebrow",           type: "string", rows: 1 },
    { key: "cta_band.title",         label: "শিরোনাম",          type: "string", rows: 2 },
    { key: "cta_band.text",          label: "সাবটেক্সট",        type: "string", rows: 2 },
    { key: "cta_band.cta_primary",   label: "প্রাথমিক বোতাম",  type: "string", rows: 1 },
    { key: "cta_band.cta_secondary", label: "সেকেন্ডারি বোতাম",type: "string", rows: 1 },
  ]},
  { group: "পেজ হিরো (শেয়ারড)", keys: [
    { key: "pagehero.cta_primary",   label: "প্রাথমিক বোতাম",  type: "string", rows: 1 },
    { key: "pagehero.cta_secondary", label: "সেকেন্ডারি বোতাম",type: "string", rows: 1 },
  ]},
  { group: "ফুটার", keys: [
    { key: "footer.tagline", label: "ট্যাগলাইন", type: "string", rows: 1 },
    { key: "footer.copy",    label: "Copyright",  type: "string", rows: 1 },
  ]},
  // ── ইনার পেজ ─────────────────────────────────────────────────────────────
  { group: "ফিচার পেজ", keys: [
    { key: "features.eyebrow", label: "Eyebrow",    type: "string", rows: 1 },
    { key: "features.title",   label: "শিরোনাম",   type: "string", rows: 2 },
    { key: "features.text",    label: "সাবটেক্সট", type: "string", rows: 2 },
    { key: "core_features",    label: "ফিচার JSON", type: "json",   rows: 8 },
  ]},
  { group: "সলিউশন পেজ", keys: [
    { key: "solutions.eyebrow", label: "Eyebrow",    type: "string", rows: 1 },
    { key: "solutions.title",   label: "শিরোনাম",   type: "string", rows: 2 },
    { key: "solutions.text",    label: "সাবটেক্সট", type: "string", rows: 2 },
  ]},
  { group: "প্রাইসিং পেজ", keys: [
    { key: "pricing.eyebrow", label: "Eyebrow",       type: "string", rows: 1 },
    { key: "pricing.title",   label: "শিরোনাম",      type: "string", rows: 2 },
    { key: "pricing.text",    label: "সাবটেক্সট",    type: "string", rows: 2 },
    { key: "pricing_plans",   label: "প্ল্যান JSON",  type: "json",   rows: 8 },
  ]},
  { group: "সিকিউরিটি পেজ", keys: [
    { key: "security.eyebrow", label: "Eyebrow",      type: "string", rows: 1 },
    { key: "security.title",   label: "শিরোনাম",     type: "string", rows: 2 },
    { key: "security.text",    label: "সাবটেক্সট",   type: "string", rows: 2 },
    { key: "trust_items",      label: "ট্রাস্ট JSON", type: "json",   rows: 6 },
  ]},
  { group: "About পেজ", keys: [
    { key: "about.eyebrow", label: "Eyebrow",    type: "string", rows: 1 },
    { key: "about.title",   label: "শিরোনাম",   type: "string", rows: 2 },
    { key: "about.text",    label: "সাবটেক্সট", type: "string", rows: 2 },
  ]},
  { group: "Help পেজ", keys: [
    { key: "help.eyebrow", label: "Eyebrow",    type: "string", rows: 1 },
    { key: "help.title",   label: "শিরোনাম",   type: "string", rows: 2 },
    { key: "help.text",    label: "সাবটেক্সট", type: "string", rows: 2 },
    { key: "faq_items",    label: "FAQ JSON",   type: "json",   rows: 8 },
  ]},
  { group: "Guidelines পেজ", keys: [
    { key: "guidelines.eyebrow", label: "Eyebrow",          type: "string", rows: 1 },
    { key: "guidelines.title",   label: "শিরোনাম",         type: "string", rows: 2 },
    { key: "guidelines.text",    label: "সাবটেক্সট",       type: "string", rows: 2 },
    { key: "role_guides",        label: "রোল গাইড JSON",   type: "json",   rows: 8 },
  ]},
  { group: "Contact পেজ", keys: [
    { key: "contact.eyebrow", label: "Eyebrow",    type: "string", rows: 1 },
    { key: "contact.title",   label: "শিরোনাম",   type: "string", rows: 2 },
    { key: "contact.text",    label: "সাবটেক্সট", type: "string", rows: 2 },
  ]},
  { group: "Privacy পেজ", keys: [
    { key: "privacy.eyebrow", label: "Eyebrow",    type: "string", rows: 1 },
    { key: "privacy.title",   label: "শিরোনাম",   type: "string", rows: 2 },
    { key: "privacy.text",    label: "সাবটেক্সট", type: "string", rows: 2 },
  ]},
  { group: "Terms পেজ", keys: [
    { key: "terms.eyebrow", label: "Eyebrow",    type: "string", rows: 1 },
    { key: "terms.title",   label: "শিরোনাম",   type: "string", rows: 2 },
    { key: "terms.text",    label: "সাবটেক্সট", type: "string", rows: 2 },
  ]},
  { group: "Status পেজ", keys: [
    { key: "status.eyebrow", label: "Eyebrow",    type: "string", rows: 1 },
    { key: "status.title",   label: "শিরোনাম",   type: "string", rows: 2 },
    { key: "status.text",    label: "সাবটেক্সট", type: "string", rows: 2 },
  ]},
  { group: "Meta / SEO", keys: [
    { key: "meta.title",       label: "Site Title",  type: "string", rows: 1 },
    { key: "meta.description", label: "Description", type: "string", rows: 2 },
  ]},
];

function SitePanel() {
  const { data, loading, error, reload } = useData(() => api.platformSiteContent());
  const [activeGroup, setActiveGroup] = useState(SITE_SCHEMA[0].group);
  const [drafts, setDrafts] = useState({});
  const [saving, setSaving] = useState({});
  const toast = useToast();

  const items = data?.content || {};

  function getValue(key) {
    const draft = drafts[key];
    if (draft !== undefined) return draft;
    const v = items[key];
    if (v == null) return "";
    if (typeof v === "string") return v;
    return JSON.stringify(v, null, 2);
  }

  function isDirty(key) { return drafts[key] !== undefined && drafts[key] !== (() => { const v = items[key]; return v == null ? "" : typeof v === "string" ? v : JSON.stringify(v, null, 2); })(); }

  async function save(key, type) {
    const raw = drafts[key] ?? getValue(key);
    let value = raw;
    if (type === "json") {
      try { value = JSON.parse(raw); } catch { toast.error(`${key}: JSON পার্স ত্রুটি`); return; }
    }
    setSaving(s => ({ ...s, [key]: true }));
    try {
      await api.platformSetSiteContent(key, value);
      setDrafts(d => { const n = { ...d }; delete n[key]; return n; });
      toast.success("সংরক্ষিত হয়েছে"); reload();
    } catch (e) { toast.error(e.message); }
    setSaving(s => ({ ...s, [key]: false }));
  }

  async function reset(key) {
    try {
      await api.platformResetSiteContent(key);
      setDrafts(d => { const n = { ...d }; delete n[key]; return n; });
      toast.success("ডিফল্টে ফিরে গেছে"); reload();
    } catch (e) { toast.error(e.message); }
  }

  const group = SITE_SCHEMA.find(g => g.group === activeGroup);
  const allKeys = new Set(SITE_SCHEMA.flatMap(g => g.keys.map(k => k.key)));
  const customKeys = Object.keys(items).filter(k => !allKeys.has(k));

  // Count dirty keys per group
  function dirtyCount(g) {
    return g.keys.filter(f => {
      const cur = items[f.key];
      const curStr = cur == null ? "" : typeof cur === "string" ? cur : JSON.stringify(cur, null, 2);
      return drafts[f.key] !== undefined && drafts[f.key] !== curStr;
    }).length;
  }

  return (
    <>
      <Head title="পাবলিক সাইট কন্টেন্ট" sub="সব পেজের টেক্সট ও কনফিগ এখান থেকে পরিবর্তন করুন" />

      {loading ? <Skeleton lines={6} /> : error ? <Notice tone="danger">{error}</Notice> : (
        <div className="pa-site-editor">
          {/* Left nav */}
          <div className="pa-site-nav">
            {SITE_SCHEMA.map(g => {
              const dc = dirtyCount(g);
              return (
                <button
                  key={g.group}
                  className={`pa-site-nav-btn${activeGroup === g.group ? " active" : ""}`}
                  onClick={() => setActiveGroup(g.group)}
                >
                  {g.group}
                  {dc > 0 && <Badge tone="warn" style={{ marginLeft: 6, fontSize: 10 }}>{dc}</Badge>}
                </button>
              );
            })}
            {customKeys.length > 0 && (
              <button
                className={`pa-site-nav-btn${activeGroup === "__custom" ? " active" : ""}`}
                onClick={() => setActiveGroup("__custom")}
              >
                কাস্টম কী ({customKeys.length})
              </button>
            )}
          </div>

          {/* Right editor */}
          <div>
            {activeGroup !== "__custom" && group && group.keys.map(field => {
              const cur = items[field.key];
              const curStr = cur == null ? "" : typeof cur === "string" ? cur : JSON.stringify(cur, null, 2);
              const val = getValue(field.key);
              const dirty = drafts[field.key] !== undefined && drafts[field.key] !== curStr;
              return (
                <div key={field.key} className={`pa-site-row${dirty ? " dirty" : ""}`}>
                  <div className="pa-site-label-row">
                    <strong style={{ fontSize: 13 }}>{field.label}</strong>
                    <code className="pa-site-key-code">{field.key}</code>
                    <Badge tone="neutral">{field.type === "json" ? "JSON" : "টেক্সট"}</Badge>
                    {cur != null && <Badge tone="info">DB</Badge>}
                  </div>
                  <textarea
                    className="pa-textarea"
                    rows={field.rows || 2}
                    value={val}
                    onChange={e => setDrafts(d => ({ ...d, [field.key]: e.target.value }))}
                  />
                  <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
                    <Button size="sm" loading={saving[field.key]} disabled={!dirty} onClick={() => save(field.key, field.type)}>সংরক্ষণ</Button>
                    {cur != null && <Button size="sm" variant="secondary" onClick={() => reset(field.key)}>রিসেট</Button>}
                    {dirty && <Button size="sm" variant="secondary" onClick={() => setDrafts(d => { const n={...d}; delete n[field.key]; return n; })}>বাতিল</Button>}
                  </div>
                </div>
              );
            })}

            {activeGroup === "__custom" && (
              <>
                <div className="pa-section-title" style={{ marginBottom: 12 }}>অপরিচিত DB কী (স্কিমায় নেই)</div>
                {customKeys.map(key => {
                  const cur = items[key];
                  const curStr = typeof cur === "string" ? cur : JSON.stringify(cur, null, 2);
                  const val = drafts[key] !== undefined ? drafts[key] : curStr;
                  const dirty = drafts[key] !== undefined && drafts[key] !== curStr;
                  return (
                    <div key={key} className={`pa-site-row${dirty ? " dirty" : ""}`}>
                      <div className="pa-site-label-row">
                        <code className="pa-site-key-code">{key}</code>
                      </div>
                      <textarea className="pa-textarea" rows={3} value={val} onChange={e => setDrafts(d => ({ ...d, [key]: e.target.value }))} />
                      <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
                        <Button size="sm" loading={saving[key]} disabled={!dirty} onClick={() => save(key, "string")}>সংরক্ষণ</Button>
                        <Button size="sm" variant="secondary" onClick={() => reset(key)}>রিসেট</Button>
                      </div>
                    </div>
                  );
                })}
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}

// ─── ANNOUNCEMENTS ─────────────────────────────────────────────────────────────
function AnnouncementsPanel() {
  const { data, loading, error } = useData(() => api.platformAnnouncements());
  const [msg, setMsg] = useState("");
  const [type, setType] = useState("info");
  const [sending, setSending] = useState(false);
  const toast = useToast();

  const anns = data?.announcements || data || [];

  async function send() {
    if (!msg.trim()) return;
    setSending(true);
    try { await api.platformSendAnnouncement({ title: msg.split("\n")[0].slice(0, 200) || msg.slice(0, 200), body: msg, type }); toast.success("পাঠানো হয়েছে"); setMsg(""); }
    catch (e) { toast.error(e.message); }
    setSending(false);
  }

  return (
    <>
      <Head title="অ্যানাউন্সমেন্ট" sub="সব ব্যবহারকারীর কাছে বার্তা পাঠান" />
      <div className="pa-card" style={{ marginBottom: 24 }}>
        <Field label="বার্তা">
          <textarea className="pa-textarea" rows={3} value={msg} onChange={e => setMsg(e.target.value)} placeholder="অ্যানাউন্সমেন্ট লিখুন…" />
        </Field>
        <Field label="ধরন">
          <select className="pa-input" value={type} onChange={e => setType(e.target.value)}>
            <option value="info">তথ্য</option>
            <option value="warning">সতর্কতা</option>
            <option value="maintenance">রক্ষণাবেক্ষণ</option>
          </select>
        </Field>
        <Button loading={sending} onClick={send} style={{ marginTop: 12 }}>পাঠান</Button>
      </div>
      {loading ? <Skeleton lines={3} /> : error ? <Notice tone="danger">{error}</Notice> : (
        <div className="pa-table-wrap">
          <table className="pa-table">
            <thead><tr><th>বার্তা</th><th>ধরন</th><th>তারিখ</th></tr></thead>
            <tbody>{anns.map((a, i) => (
              <tr key={i}>
                <td style={{ fontSize: 13 }}>{a.message}</td>
                <td><Badge tone={a.type === "warning" ? "warn" : a.type === "maintenance" ? "danger" : "info"}>{a.type}</Badge></td>
                <td className="pa-muted" style={{ fontSize: 12 }}>{dateTimeBn(a.created_at || a.sent_at)}</td>
              </tr>
            ))}</tbody>
          </table>
          {anns.length === 0 && <EmptyState title="কোনো অ্যানাউন্সমেন্ট নেই" />}
        </div>
      )}
    </>
  );
}

// ─── ROOT ─────────────────────────────────────────────────────────────────────
const PANELS = {
  "command":       CommandCenterPanel,
  "tenants":       TenantsPanel,
  "data-readiness": DataReadinessPanel,
  "ai-governance": AiGovernancePanel,
  "recom-ops":     RecommendationOpsPanel,
  "plans":         PlansPanel,
  "support":       SupportSuccessPanel,
  "security-audit": SecurityAuditPanel,
  "system-ops":    SystemOpsPanel,
  "site":          SitePanel,
  "announcements": AnnouncementsPanel,
};

const SHORTCUT_MAP = {
  "c": "command", "t": "tenants", "d": "data-readiness",
  "a": "ai-governance", "r": "recom-ops", "p": "plans",
  "s": "support", "e": "security-audit", "o": "system-ops",
  "w": "site", "n": "announcements",
};

// ─── NOTIFICATION CENTER ──────────────────────────────────────────────────────
function NotificationCenter() {
  const { notifs, clear } = useNotifications();
  const [open, setOpen] = useState(false);
  const unread = notifs.length;
  return (
    <div style={{ position: "relative" }}>
      <button className="pa-alert-bell" onClick={() => setOpen(o => !o)} title="নোটিফিকেশন">
        <Icon name="bell" size={14} />
        {unread > 0 && <span className="pa-alert-count">{unread}</span>}
      </button>
      {open && (
        <div className="pa-notif-dropdown" onClick={e => e.stopPropagation()}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 12px", borderBottom: "1px solid var(--border)" }}>
            <span style={{ fontWeight: 600, fontSize: 13 }}>নোটিফিকেশন</span>
            {notifs.length > 0 && <button className="pa-link-btn" style={{ fontSize: 12 }} onClick={() => { clear(); setOpen(false); }}>সব মুছুন</button>}
          </div>
          {notifs.length === 0 ? (
            <div className="pa-muted" style={{ padding: "16px 12px", fontSize: 13 }}>কোনো নোটিফিকেশন নেই</div>
          ) : (
            <div style={{ maxHeight: 280, overflowY: "auto" }}>
              {notifs.map(n => (
                <div key={n.id} style={{ padding: "8px 12px", borderBottom: "1px solid var(--border)", fontSize: 13 }}>
                  <div>{n.title}</div>
                  <div className="pa-muted" style={{ fontSize: 11 }}>{n.at?.toLocaleTimeString("bn-BD")}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function Platform() {
  const [params, setParams] = useSearchParams();
  const tab = ALL_TABS.some(t => t.value === params.get("tab")) ? params.get("tab") : "command";
  const Panel = PANELS[tab] || CommandCenterPanel;
  const { data: alertsData } = useData(() => api.adminSecurityAlerts("open"));
  const { data: overviewData } = useData(() => api.adminOverview());
  const openAlerts = (alertsData?.alerts || alertsData || []).length;
  const [gPressed, setGPressed] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [cmdOpen, setCmdOpen] = useState(false);
  const [hotkeyOpen, setHotkeyOpen] = useState(false);
  const { dark, toggle: toggleDark } = useDarkMode();

  const navigate = useCallback((t) => setParams({ tab: t }), [setParams]);

  useEffect(() => {
    let gTimer;
    function handler(e) {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") { e.preventDefault(); setSearchOpen(true); return; }
      if ((e.ctrlKey || e.metaKey) && e.key === "p") { e.preventDefault(); setCmdOpen(true); return; }
      if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA" || e.target.tagName === "SELECT") return;
      if (e.key === "?") { setHotkeyOpen(true); return; }
      if (e.key === "g" || e.key === "G") {
        setGPressed(true);
        clearTimeout(gTimer);
        gTimer = setTimeout(() => setGPressed(false), 1500);
        return;
      }
      if (gPressed && SHORTCUT_MAP[e.key]) {
        setParams({ tab: SHORTCUT_MAP[e.key] });
        setGPressed(false);
        clearTimeout(gTimer);
      }
    }
    window.addEventListener("keydown", handler);
    return () => { window.removeEventListener("keydown", handler); clearTimeout(gTimer); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gPressed]);

  const panelProps = tab === "command" ? { onNavigate: navigate } : {};

  return (
    <div className="platform-layout">
      <nav className="platform-sidenav">
        <div className="platform-nav-header">
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ fontWeight: 700, fontSize: 13 }}>Admin</span>
            <PlatformHealthScore overview={overviewData} />
          </div>
          <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
            <button className="pa-alert-bell" onClick={() => setCmdOpen(true)} title="কমান্ড প্যালেট (Ctrl+P)">
              <Icon name="zap" size={13} />
            </button>
            <button className="pa-alert-bell" onClick={() => setSearchOpen(true)} title="সার্চ (Ctrl+K)">
              <Icon name="search" size={13} />
            </button>
            <button className="pa-alert-bell" onClick={toggleDark} title={dark ? "লাইট মোড" : "ডার্ক মোড"}>
              <span style={{ fontSize: 12 }}>{dark ? "☀" : "☾"}</span>
            </button>
            <NotificationCenter />
            {openAlerts > 0 && (
              <button className="pa-alert-bell" onClick={() => setParams({ tab: "security-audit" })}
                title={`${openAlerts}টি খোলা অ্যালার্ট`}>
                <Icon name="bell" size={13} />
                <span className="pa-alert-count">{openAlerts}</span>
              </button>
            )}
          </div>
        </div>
        {NAV_GROUPS.map(group => (
          <div key={group.label} className="platform-nav-group">
            <div className="platform-nav-group-label">{group.label}</div>
            {group.items.map(item => (
              <button
                key={item.value}
                className={`platform-nav-btn${tab === item.value ? " active" : ""}`}
                onClick={() => setParams({ tab: item.value })}
              >
                <Icon name={item.icon} size={15} />
                <span>{item.label}</span>
                {item.value === "security-audit" && openAlerts > 0 && (
                  <span className="pa-nav-badge">{openAlerts}</span>
                )}
              </button>
            ))}
          </div>
        ))}
        <div style={{ padding: "8px 10px 4px" }}>
          <button className="pa-alert-bell" style={{ fontSize: 11 }} onClick={() => setHotkeyOpen(true)} title="কীবোর্ড শর্টকাট (?)">
            <span>⌨ শর্টকাট</span>
          </button>
        </div>
        {gPressed && <div className="pa-shortcut-hint">G + কী চাপুন…</div>}
      </nav>
      <div className="platform-content">
        <PanelBoundary key={tab}>
          <Panel {...panelProps} />
        </PanelBoundary>
      </div>
      {searchOpen && <GlobalSearch setParams={p => setParams(p)} onClose={() => setSearchOpen(false)} />}
      {cmdOpen && <CommandPalette setParams={p => setParams(p)} onClose={() => setCmdOpen(false)} />}
      {hotkeyOpen && <HotkeySheet onClose={() => setHotkeyOpen(false)} />}
    </div>
  );
}
