import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid,
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
const STATE_TONE = { active: "success", trial: "info", suspended: "danger", churned: "neutral", onboarding: "warn" };

// ─── 1. COMMAND CENTER ────────────────────────────────────────────────────────
function CommandCenterPanel() {
  const { data: overview, loading: ol, error: oe } = useData(() => api.adminOverview());
  const { data: mq, loading: ml, error: me } = useData(() => api.adminMissionQueue("open"));
  const { data: alerts, loading: al, error: ae } = useData(() => api.adminSecurityAlerts("open"));
  const { data: trends, loading: tl } = useData(() => api.platformTrends(30));
  const toast = useToast();
  const o = overview || {};

  async function generateQueue() {
    try { await api.adminGenerateMissionQueue(); toast.success("Queue রিফ্রেশ হয়েছে"); }
    catch (e) { toast.error(e.message); }
  }

  const series = trends?.series || [];
  const items = mq?.items || mq || [];
  const alertList = alerts?.alerts || alerts || [];

  return (
    <>
      <Head title="কমান্ড সেন্টার" sub="আজকের সবচেয়ে গুরুত্বপূর্ণ ইস্যু এবং প্ল্যাটফর্মের সামগ্রিক অবস্থা" />

      {/* KPI row */}
      {ol ? <Skeleton lines={2} /> : oe ? <Notice tone="danger">{oe}</Notice> : (
        <div className="pa-stats-grid" style={{ marginBottom: 24 }}>
          <Stat label="মিশন কিউ (খোলা)"   value={fmt(o.mission_queue?.open)}          tone={o.mission_queue?.open > 10 ? "danger" : "warn"} />
          <Stat label="ইনসিডেন্ট (খোলা)"  value={fmt(o.incidents?.open)}              tone={o.incidents?.open > 0 ? "danger" : "success"} />
          <Stat label="সিকিউরিটি অ্যালার্ট" value={fmt(o.security?.open_alerts)}      tone={o.security?.open_alerts > 0 ? "danger" : "success"} />
          <Stat label="চার্ন রিস্ক (উচ্চ)" value={fmt(o.churn_risk?.high)}            tone={o.churn_risk?.high > 0 ? "warn" : "success"} />
          <Stat label="ব্যর্থ জব"          value={fmt(o.jobs?.failed)}                tone={o.jobs?.failed > 0 ? "danger" : "success"} />
          <Stat label="খোলা সাপোর্ট কেস"  value={fmt(o.support?.open_cases)}          tone="neutral" />
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

      {/* Sales trend */}
      <div className="pa-section-title">গত ৩০ দিনের বিক্রয় ট্রেন্ড (৳)</div>
      {!tl && (
        <div className="pa-chart-box">
          <ResponsiveContainer width="100%" height={160}>
            <AreaChart data={series} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
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
    </>
  );
}

// ─── 2. TENANTS ───────────────────────────────────────────────────────────────
function Tenant360Drawer({ org, onClose }) {
  const { data: health } = useData(() => api.adminTenantHealthScore(org.id), [org.id]);
  const { data: sub }    = useData(() => api.adminOrgSubscription(org.id), [org.id]);
  const { data: cases }  = useData(() => api.adminSupportCases("open"), []);
  const tenantCases = (cases?.cases || cases || []).filter(c => c.organization_id === org.id);

  return (
    <div className="pa-drawer-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="pa-drawer">
        <div className="pa-drawer-head">
          <div>
            <div style={{ fontWeight: 700, fontSize: 16 }}>{org.name}</div>
            <div className="pa-muted" style={{ fontSize: 13 }}>{org.slug} · {org.id}</div>
          </div>
          <button className="pa-drawer-close" onClick={onClose}><Icon name="x" size={18} /></button>
        </div>

        <div className="pa-section-title" style={{ marginTop: 16 }}>স্বাস্থ্য স্কোর</div>
        {health ? (
          <div className="pa-stats-grid">
            <Stat label="স্কোর" value={health.score != null ? health.score.toFixed(1) : "—"} tone={health.score >= 70 ? "success" : health.score >= 40 ? "warn" : "danger"} />
            <Stat label="ডেটা অ্যাক্টিভিটি" value={health.data_activity_score != null ? health.data_activity_score.toFixed(1) : "—"} />
            <Stat label="রেকমেন্ডেশন এনগেজমেন্ট" value={health.recommendation_engagement_score != null ? health.recommendation_engagement_score.toFixed(1) : "—"} />
          </div>
        ) : <Skeleton lines={1} />}

        <div className="pa-section-title" style={{ marginTop: 16 }}>প্ল্যান ও সাবস্ক্রিপশন</div>
        {sub ? (
          <div className="pa-kv-list">
            <div className="pa-kv-row"><span>প্ল্যান</span><strong>{sub.plan_name || sub.plan_id || "—"}</strong></div>
            <div className="pa-kv-row"><span>অবস্থা</span><Badge tone={STATE_TONE[sub.status] || "neutral"}>{sub.status}</Badge></div>
            <div className="pa-kv-row"><span>শুরু</span><span>{dateBn(sub.starts_at)}</span></div>
            <div className="pa-kv-row"><span>শেষ</span><span>{dateBn(sub.ends_at)}</span></div>
          </div>
        ) : <Skeleton lines={2} />}

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
          <div className="pa-kv-row"><span>অবস্থা</span><Badge tone={STATE_TONE[org.state] || "neutral"}>{org.state}</Badge></div>
          <div className="pa-kv-row"><span>তৈরি</span><span>{dateBn(org.created_at)}</span></div>
          <div className="pa-kv-row"><span>ইমেইল</span><span>{org.contact_email || "—"}</span></div>
        </div>
      </div>
    </div>
  );
}

function TenantsPanel() {
  const { data, loading, error, reload } = useData(() => api.platformOrganizations());
  const [selected, setSelected] = useState(null);
  const [q, setQ] = useState("");
  const toast = useToast();
  const confirm = useConfirm();

  const orgs = (data?.organizations || data || []).filter(o =>
    !q || o.name?.toLowerCase().includes(q.toLowerCase()) || o.slug?.includes(q)
  );

  async function suspend(org) {
    const reason = window.prompt("স্থগিতের কারণ লিখুন:");
    if (!reason) return;
    if (!await confirm(`"${org.name}" স্থগিত করবেন?`)) return;
    try { await api.platformSuspend(org.id, reason); toast.success("স্থগিত হয়েছে"); reload(); }
    catch (e) { toast.error(e.message); }
  }

  async function unsuspend(org) {
    if (!await confirm(`"${org.name}" পুনরায় সক্রিয় করবেন?`)) return;
    try { await api.platformUnsuspend(org.id); toast.success("সক্রিয় হয়েছে"); reload(); }
    catch (e) { toast.error(e.message); }
  }

  return (
    <>
      <Head title="ব্যবসা তালিকা" sub="সব ব্যবসার তালিকা, স্বাস্থ্য এবং ৩৬০° বিশদ" />
      <div style={{ marginBottom: 16 }}>
        <input className="pa-search" placeholder="নাম বা slug খুঁজুন…" value={q} onChange={e => setQ(e.target.value)} />
      </div>
      {loading ? <Skeleton lines={6} /> : error ? <Notice tone="danger">{error}</Notice> : (
        <div className="pa-table-wrap">
          <table className="pa-table">
            <thead><tr><th>নাম</th><th>Slug</th><th>অবস্থা</th><th>তৈরি</th><th>অ্যাকশন</th></tr></thead>
            <tbody>{orgs.map(o => (
              <tr key={o.id}>
                <td><button className="pa-link-btn" onClick={() => setSelected(o)}>{o.name}</button></td>
                <td className="pa-muted" style={{ fontFamily: "monospace", fontSize: 12 }}>{o.slug}</td>
                <td><Badge tone={STATE_TONE[o.state] || "neutral"}>{o.state}</Badge></td>
                <td className="pa-muted" style={{ fontSize: 12 }}>{dateBn(o.created_at)}</td>
                <td>
                  <div className="pa-row-actions">
                    <Button size="sm" variant="secondary" onClick={() => setSelected(o)}>৩৬০°</Button>
                    {o.state === "suspended"
                      ? <Button size="sm" variant="secondary" onClick={() => unsuspend(o)}>সক্রিয় করুন</Button>
                      : <Button size="sm" variant="danger" onClick={() => suspend(o)}>স্থগিত</Button>}
                  </div>
                </td>
              </tr>
            ))}</tbody>
          </table>
          {orgs.length === 0 && <EmptyState title="কোনো ব্যবসা পাওয়া যায়নি" />}
        </div>
      )}
      {selected && <Tenant360Drawer org={selected} onClose={() => setSelected(null)} />}
      {confirm.dialog}
    </>
  );
}

// ─── 3. DATA READINESS ────────────────────────────────────────────────────────
function DataReadinessPanel() {
  const { data: orgsData, loading: ol } = useData(() => api.platformOrganizations());
  const orgs = orgsData?.organizations || orgsData || [];

  // Derive readiness from real org fields: active state + has_sales_data indicator
  function readinessScore(org) {
    if (org.state !== "active") return 10;
    const base = org.has_sales_data ? 65 : 30;
    // Bump score when org has multiple branches or uses expiry tracking (more data depth)
    const extra = (org.uses_expiry ? 15 : 0) + (org.sector === "pharmacy" ? 10 : 0);
    return Math.min(100, base + extra);
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
            <Stat label="উন্নতি প্রয়োজন" value={fmt(orgs.filter(o => o.state !== "active").length)} tone="warn" />
          </div>
          <div className="pa-table-wrap">
            <table className="pa-table">
              <thead><tr><th>ব্যবসা</th><th>অবস্থা</th><th>AI স্কোর</th><th>প্রয়োজনীয় পদক্ষেপ</th></tr></thead>
              <tbody>{orgs.map(o => {
                const score = readinessScore(o);
                const issues = [];
                if (o.state !== "active") issues.push("ব্যবসা সক্রিয় নয়");
                if (score < 40) issues.push("বিক্রয় ডেটা অপর্যাপ্ত");
                if (score < 70) issues.push("হিস্টোরিক্যাল ডেটা বাড়ান");
                return (
                  <tr key={o.id}>
                    <td style={{ fontWeight: 500 }}>{o.name}</td>
                    <td><Badge tone={STATE_TONE[o.state] || "neutral"}>{o.state}</Badge></td>
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
      await api.adminSetKillSwitch({ feature: sw.feature, killed: !sw.killed, reason: sw.killed ? "Restored" : "Admin kill" });
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
  const [newPlan, setNewPlan]   = useState({ name: "", max_users: 5, max_branches: 1, price_bdt: 0 });
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
          <Field label="নাম"><input className="pa-input" value={newPlan.name} onChange={e => setNewPlan(p => ({ ...p, name: e.target.value }))} /></Field>
          <Field label="মূল্য (৳/মাস)"><input className="pa-input" type="number" value={newPlan.price_bdt} onChange={e => setNewPlan(p => ({ ...p, price_bdt: +e.target.value }))} /></Field>
          <Field label="সর্বোচ্চ ব্যবহারকারী"><input className="pa-input" type="number" value={newPlan.max_users} onChange={e => setNewPlan(p => ({ ...p, max_users: +e.target.value }))} /></Field>
          <Field label="সর্বোচ্চ শাখা"><input className="pa-input" type="number" value={newPlan.max_branches} onChange={e => setNewPlan(p => ({ ...p, max_branches: +e.target.value }))} /></Field>
          <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
            <Button onClick={createPlan}>তৈরি করুন</Button>
            <Button variant="secondary" onClick={() => setCreating(false)}>বাতিল</Button>
          </div>
        </Modal>
      )}
    </>
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
  const [newCase, setNewCase] = useState({ title: "", priority: "medium", organization_id: "" });

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
                <thead><tr><th>বিষয়</th><th>প্রাধান্য</th><th>অবস্থা</th><th>তৈরি</th></tr></thead>
                <tbody>{cases.map(c => (
                  <tr key={c.id}>
                    <td style={{ fontSize: 13 }}>{c.title || c.subject}</td>
                    <td><Badge tone={TONE_MAP[c.priority] || "neutral"}>{c.priority}</Badge></td>
                    <td><Badge tone={c.status === "resolved" ? "success" : "warn"}>{c.status}</Badge></td>
                    <td className="pa-muted" style={{ fontSize: 12 }}>{dateBn(c.created_at)}</td>
                  </tr>
                ))}</tbody>
              </table>
              {cases.length === 0 && <EmptyState title="কোনো খোলা কেস নেই" />}
            </div>
          )}
          {creating && (
            <Modal title="নতুন সাপোর্ট কেস" onClose={() => setCreating(false)}>
              <Field label="বিষয়"><input className="pa-input" value={newCase.title} onChange={e => setNewCase(p => ({ ...p, title: e.target.value }))} /></Field>
              <Field label="প্রাধান্য">
                <select className="pa-input" value={newCase.priority} onChange={e => setNewCase(p => ({ ...p, priority: e.target.value }))}>
                  <option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="critical">Critical</option>
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

// ─── 8. SECURITY & AUDIT ─────────────────────────────────────────────────────
function SecurityAuditPanel() {
  const [subTab, setSubTab] = useState("alerts");
  const { data: alertsData, loading: al, error: ae, reload: aReload } = useData(() => api.adminSecurityAlerts("open"));
  const { data: jitData, loading: jl } = useData(() => api.adminJitGrants(true));
  const { data: auditData, loading: auditL } = useData(() => api.platformAudit());
  const { data: adminsData, loading: adminL, reload: adminReload } = useData(() => api.platformAdministrators());
  const toast = useToast();
  const confirm = useConfirm();

  const alerts = alertsData?.alerts || alertsData || [];
  const jit = jitData?.grants || jitData || [];
  const audit = auditData?.entries || [];
  const admins = adminsData?.administrators || [];

  async function resolveAlert(a) {
    const resolution = window.prompt("সমাধানের বিবরণ:");
    if (!resolution) return;
    try { await api.adminResolveAlert(a.id, { resolution }); toast.success("সমাধান হয়েছে"); aReload(); }
    catch (e) { toast.error(e.message); }
  }

  async function grantJit() {
    const target = window.prompt("User ID:");
    if (!target) return;
    const reason = window.prompt("JIT কারণ:");
    if (!reason) return;
    try { await api.adminGrantJit({ target_user_id: target, reason, duration_hours: 4 }); toast.success("JIT অ্যাক্সেস দেওয়া হয়েছে"); }
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
            <Button size="sm" onClick={grantJit}>JIT অ্যাক্সেস দিন</Button>
          </div>
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
        <>
          {auditL ? <Skeleton lines={5} /> : (
            <div className="pa-table-wrap">
              <table className="pa-table">
                <thead><tr><th>অ্যাকশন</th><th>অ্যাক্টর</th><th>টার্গেট</th><th>সময়</th></tr></thead>
                <tbody>{audit.slice(0, 50).map((e, i) => (
                  <tr key={i}>
                    <td style={{ fontFamily: "monospace", fontSize: 12 }}>{e.action}</td>
                    <td style={{ fontSize: 12 }}>{e.actor_email || "system"}</td>
                    <td style={{ fontSize: 12 }} className="pa-muted">{e.entity_type} {e.entity_id?.slice(0, 8)}</td>
                    <td className="pa-muted" style={{ fontSize: 12 }}>{dateTimeBn(e.created_at)}</td>
                  </tr>
                ))}</tbody>
              </table>
              {audit.length === 0 && <EmptyState title="কোনো লগ নেই" />}
            </div>
          )}
        </>
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

  const h = health || {};
  const jobs = jobsData?.jobs || jobsData || [];
  const incidents = inciData?.incidents || inciData || [];
  const rollouts = rolloutData?.configs || rolloutData || [];
  const backups = backupsData?.backups || [];

  async function retryJob(job) {
    try { await api.adminRetryJob(job.id); toast.success("পুনরায় চেষ্টা শুরু হয়েছে"); jReload(); }
    catch (e) { toast.error(e.message); }
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
            <div className="pa-table-wrap">
              <table className="pa-table">
                <thead><tr><th>জব টাইপ</th><th>অবস্থা</th><th>ত্রুটি</th><th>সময়</th><th>অ্যাকশন</th></tr></thead>
                <tbody>{jobs.map(j => (
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
          )}
        </>
      )}

      {subTab === "incidents" && (
        <>
          {il ? <Skeleton lines={4} /> : (
            <div className="pa-table-wrap">
              <table className="pa-table">
                <thead><tr><th>শিরোনাম</th><th>তীব্রতা</th><th>অবস্থা</th><th>শুরু</th></tr></thead>
                <tbody>{incidents.map(inc => (
                  <tr key={inc.id}>
                    <td style={{ fontWeight: 500 }}>{inc.title}</td>
                    <td><Badge tone={TONE_MAP[inc.severity] || "neutral"}>{inc.severity}</Badge></td>
                    <td><Badge tone={inc.status === "resolved" ? "success" : "warn"}>{inc.status}</Badge></td>
                    <td className="pa-muted" style={{ fontSize: 12 }}>{dateTimeBn(inc.started_at)}</td>
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
    try { await api.platformSendAnnouncement({ message: msg, type }); toast.success("পাঠানো হয়েছে"); setMsg(""); }
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

export default function Platform() {
  const [params, setParams] = useSearchParams();
  const tab = ALL_TABS.some(t => t.value === params.get("tab")) ? params.get("tab") : "command";
  const Panel = PANELS[tab] || CommandCenterPanel;
  return (
    <div className="platform-layout">
      <nav className="platform-sidenav">
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
              </button>
            ))}
          </div>
        ))}
      </nav>
      <div className="platform-content"><Panel /></div>
    </div>
  );
}
