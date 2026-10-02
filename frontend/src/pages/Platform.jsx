// Platform super-admin: every tenant on this deployment, plus real control.
// suspend/delete an organization, toggle feature modules per org, impersonate
// a member for support, and edit the public marketing site's copy. Gated
// server-side by User.is_platform_admin with audited MFA-gated governance.
// this page is reachable in the UI only for an account already carrying that
// flag; every api.platform*() call returns 403 for anyone else regardless of
// what this page renders.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { useConfirm } from "../components/ConfirmDialog";
import { explain } from "../errors";
import { dateBn, dateTimeBn } from "../format";
import DataTable from "../ui/DataTable";
import Icon from "../ui/Icon";
import { Badge, Button, Card, EmptyState, Field, Modal, Notice, Skeleton, Stat } from "../ui/kit";
import { useToast } from "../ui/Toast";

const AUDIT_ACTION_LABELS = {
  "platform.organization_suspended": "ব্যবসা স্থগিত করা হয়েছে",
  "platform.organization_unsuspended": "ব্যবসা আবার সক্রিয় করা হয়েছে",
  "platform.organization_deleted": "ব্যবসা মুছে ফেলা হয়েছে",
  "platform.features_updated": "মডিউল সেটিং বদলানো হয়েছে",
  "platform.feature_rollout_updated": "সব business এর module rollout বদলানো হয়েছে",
  "platform.impersonation_started": "কাউকে ইমপার্সোনেট করা হয়েছে",
  "platform.site_content_updated": "সাইট কনটেন্ট বদলানো হয়েছে",
  "platform.site_content_reset": "সাইট কনটেন্ট রিসেট করা হয়েছে",
  "platform.backup_created": "ব্যাকআপ নেওয়া হয়েছে",
  "platform.backup_deleted": "ব্যাকআপ মুছে ফেলা হয়েছে",
  "platform.restore_drill_run": "রিস্টোর মহড়া চালানো হয়েছে",
  "platform.user_activated": "ব্যবহারকারী আবার সক্রিয় করা হয়েছে",
  "platform.user_deactivated": "ব্যবহারকারী নিষ্ক্রিয় করা হয়েছে",
  "platform.user_session_revoked": "ব্যবহারকারীর device session বাতিল করা হয়েছে",
  "platform.organization_profile_updated": "Business profile update করা হয়েছে",
  "platform.membership_updated": "Business member access বদলানো হয়েছে",
  "platform.administrator_granted": "Platform admin access দেওয়া হয়েছে",
  "platform.administrator_revoked": "Platform admin access বাতিল করা হয়েছে",
  "platform.announcement_sent": "Platform announcement পাঠানো হয়েছে",
};

const FEATURE_LABELS = {
  workforce: "উপস্থিতি, ছুটি ও পে-রোল",
  crm: "টিকেট, লিড ও ফিডব্যাক",
  fulfilment: "রিজার্ভেশন ও ডেলিভারি",
  team_chat: "টিম চ্যাট",
  bsmart: "B-SMART সুপারিশ",
  upload: "নিজের ফাইল আপলোড",
};

const ROLE_LABELS = {
  owner: "মালিক",
  manager: "ম্যানেজার",
  accountant: "হিসাবরক্ষক",
  cashier: "ক্যাশিয়ার",
  stock_keeper: "স্টক কর্মকর্তা",
  viewer: "রিড অনলি ব্যবহারকারী",
  evaluator: "মূল্যায়নকারী",
  rider: "রাইডার",
};

const TAB_DESCRIPTIONS = {
  overview: "সব tenant এর growth, risk এবং আজকের operational priority এক জায়গা থেকে দেখুন।",
  onboarding: "নতুন SME গুলো profile থেকে first sale পর্যন্ত কোথায় আছে তা real data দিয়ে অনুসরণ করুন।",
  orgs: "Business profile, team access, module, suspension এবং support action পরিচালনা করুন।",
  users: "সব account, membership, MFA এবং device session এর lifecycle নিয়ন্ত্রণ করুন।",
  features: "সব business অথবা নির্দিষ্ট tenant এর module availability নিরাপদভাবে rollout করুন।",
  security: "MFA adoption, active session এবং account risk এর বর্তমান অবস্থা পর্যবেক্ষণ করুন।",
  administrators: "MFA gated privileged access দিন এবং platform administrator team নিয়ন্ত্রণ করুন।",
  audit: "প্রতিটি sensitive administrative action এর immutable ইতিহাস filter করে দেখুন।",
  system: "Runtime, database, provider credential readiness এবং backup freshness যাচাই করুন।",
  delivery: "সব tenant এর SMS ও WhatsApp delivery status এবং provider failure দেখুন।",
  announcements: "নির্দিষ্ট business অথবা সব SME user কে audited in app notice পাঠান।",
  backups: "Database snapshot তৈরি, download, restore drill এবং retention পরিচালনা করুন।",
  site: "Public website এর প্রধান copy, FAQ এবং structured content live update করুন।",
};

const PLATFORM_NAV_GROUPS = [
  { label: "অপারেশন", items: [
    { value: "overview", label: "অপারেশন ওভারভিউ", icon: "home" },
    { value: "onboarding", label: "Onboarding pipeline", icon: "target" },
    { value: "orgs", label: "ব্যবসার তালিকা", icon: "users" },
    { value: "users", label: "ব্যবহারকারী", icon: "userCheck" },
    { value: "features", label: "ফিচার রোলআউট", icon: "sliders" },
  ] },
  { label: "নিরাপত্তা ও নিয়ন্ত্রণ", items: [
    { value: "security", label: "নিরাপত্তা কেন্দ্র", icon: "shield" },
    { value: "administrators", label: "অ্যাডমিন টিম", icon: "key" },
    { value: "audit", label: "কার্যকলাপের ইতিহাস", icon: "clock" },
  ] },
  { label: "প্ল্যাটফর্ম", items: [
    { value: "system", label: "সিস্টেম ও ইন্টিগ্রেশন", icon: "zap" },
    { value: "delivery", label: "Message delivery", icon: "mail" },
    { value: "announcements", label: "Announcement", icon: "bell" },
    { value: "backups", label: "ব্যাকআপ", icon: "download" },
    { value: "site", label: "পাবলিক সাইট কনটেন্ট", icon: "fileText" },
  ] },
  { label: "Command Center", items: [
    { value: "cmd_overview", label: "Admin Overview", icon: "home" },
    { value: "cmd_search", label: "Universal Search", icon: "search" },
    { value: "cmd_mission", label: "Mission Queue", icon: "target" },
    { value: "cmd_handover", label: "Shift Handover", icon: "repeat" },
    { value: "cmd_journal", label: "Decision Journal", icon: "book" },
  ] },
  { label: "Tenant Lifecycle", items: [
    { value: "lc_state", label: "State Machine", icon: "gitBranch" },
    { value: "lc_health", label: "Health Score", icon: "activity" },
    { value: "lc_churn", label: "Churn Risk", icon: "alertTriangle" },
  ] },
  { label: "Revenue", items: [
    { value: "rev_plans", label: "Plans & Entitlement", icon: "package" },
    { value: "rev_billing", label: "Billing Ledger", icon: "creditCard" },
    { value: "rev_usage", label: "Usage Metering", icon: "barChart2" },
    { value: "rev_reconcile", label: "Collection Reconciliation", icon: "checkSquare" },
  ] },
  { label: "Support & Success", items: [
    { value: "sup_cases", label: "Support Cases", icon: "messageSquare" },
    { value: "sup_sessions", label: "Support Sessions", icon: "eye" },
    { value: "sup_sla", label: "SLA Summary", icon: "clock" },
  ] },
  { label: "Security Governance", items: [
    { value: "sec_alerts", label: "Security Alerts", icon: "alertOctagon" },
    { value: "sec_jit", label: "JIT Access", icon: "unlock" },
    { value: "sec_cert", label: "Access Certification", icon: "checkCircle" },
    { value: "sec_emergency", label: "Emergency Containment", icon: "zap" },
  ] },
  { label: "Reliability", items: [
    { value: "rel_incidents", label: "Incident Command", icon: "alertCircle" },
    { value: "rel_jobs", label: "Job Console", icon: "cpu" },
  ] },
  { label: "Release & Integrations", items: [
    { value: "rel_rollout", label: "Progressive Rollout", icon: "sliders" },
    { value: "rel_config", label: "Config Versions", icon: "settings" },
    { value: "rel_providers", label: "Provider Credentials", icon: "key" },
    { value: "rel_webhooks", label: "Webhook Inbox", icon: "rss" },
    { value: "rel_intcert", label: "Integration Certification", icon: "shield" },
  ] },
  { label: "Data & AI Governance", items: [
    { value: "gov_inventory", label: "Data Inventory", icon: "database" },
    { value: "gov_exports", label: "Data Exports", icon: "download" },
    { value: "gov_retention", label: "Retention Policies", icon: "archive" },
    { value: "gov_privacy", label: "Privacy Requests", icon: "lock" },
    { value: "ai_registry", label: "Model Registry", icon: "box" },
    { value: "ai_budgets", label: "AI Cost Budgets", icon: "dollarSign" },
    { value: "ai_outcomes", label: "AI Outcomes", icon: "trendingUp" },
    { value: "ai_killswitch", label: "AI Kill Switch", icon: "power" },
  ] },
];
const PLATFORM_NAV = PLATFORM_NAV_GROUPS.flatMap((group) => group.items);
const PLATFORM_TABS = new Set(PLATFORM_NAV.map((item) => item.value));

const bnNumber = (value) => Number(value || 0).toLocaleString("bn-BD");
const formatBytes = (value) => {
  if (!value) return "০ বাইট";
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
};

function OrgDetailModal({ orgId, onClose, onChanged }) {
  const toast = useToast();
  const confirm = useConfirm();
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [reason, setReason] = useState("");
  const [memberBusy, setMemberBusy] = useState("");
  const [profile, setProfile] = useState({ name: "", sector: "", size_class: "", address: "", phone: "", vat_reg_no: "" });

  const load = useCallback(() => {
    api.platformOrganization(orgId).then(setDetail).catch((e) => setError(explain(e)));
  }, [orgId]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!detail) return;
    setProfile({
      name: detail.name || "", sector: detail.sector || "", size_class: detail.size_class || "",
      address: detail.address || "", phone: detail.phone || "", vat_reg_no: detail.vat_reg_no || "",
    });
  }, [detail]);

  async function saveProfile() {
    setBusy(true);
    try {
      await api.platformUpdateOrganization(orgId, {
        ...profile,
        size_class: profile.size_class || null,
        address: profile.address || null,
        phone: profile.phone || null,
        vat_reg_no: profile.vat_reg_no || null,
      });
      toast.success("Business profile update হয়েছে।");
      load(); onChanged();
    } catch (e) { toast.error(explain(e)); } finally { setBusy(false); }
  }

  async function updateMember(member, changes) {
    const next = { role: member.role, active: member.active, ...changes };
    if (changes.active === false && !(await confirm(`${member.display_name} এর এই business access বন্ধ হবে। নিশ্চিত?`))) return;
    setMemberBusy(member.membership_id);
    try {
      await api.platformUpdateMembership(orgId, member.membership_id, next);
      toast.success("Member access update হয়েছে।");
      load();
    } catch (e) { toast.error(explain(e, { 409: "Business এ অন্তত একজন সক্রিয় মালিক রাখতে হবে।" })); } finally { setMemberBusy(""); }
  }

  async function suspend() {
    if (!reason.trim()) { toast.error("কারণ লিখুন।"); return; }
    if (!(await confirm(`"${detail?.name}"-এর সব সদস্য লগইন করতে পারবেন না। ডেটা অক্ষত থাকবে এবং পরে আবার সক্রিয় করা যাবে। নিশ্চিত?`))) return;
    setBusy(true);
    try {
      await api.platformSuspend(orgId, reason.trim());
      toast.success("ব্যবসাটি স্থগিত করা হয়েছে।");
      setReason("");
      load(); onChanged();
    } catch (e) { toast.error(explain(e)); } finally { setBusy(false); }
  }

  async function unsuspend() {
    setBusy(true);
    try {
      await api.platformUnsuspend(orgId);
      toast.success("আবার সক্রিয় করা হয়েছে।");
      load(); onChanged();
    } catch (e) { toast.error(explain(e)); } finally { setBusy(false); }
  }

  async function remove() {
    if (!(await confirm(`"${detail.name}" স্থায়ীভাবে মুছে ফেলা হবে। সব বিক্রি, স্টক এবং কর্মীর তথ্যও মুছে যাবে। এটি ফিরিয়ে আনা যাবে না। নিশ্চিত?`))) return;
    setBusy(true);
    try {
      await api.platformDeleteOrganization(orgId);
      toast.success("ব্যবসাটি মুছে ফেলা হয়েছে।");
      onChanged(); onClose();
    } catch (e) { toast.error(explain(e, { 409: "আগে স্থগিত করুন, তারপর মুছুন।" })); } finally { setBusy(false); }
  }

  async function toggleFeature(key, enabled) {
    setBusy(true);
    try {
      const updated = await api.platformSetFeatures(orgId, { [key]: enabled });
      setDetail((d) => ({ ...d, feature_flags: updated.feature_flags }));
    } catch (e) { toast.error(explain(e)); } finally { setBusy(false); }
  }

  async function impersonate(userId) {
    if (!(await confirm(`এই ব্যবহারকারী হিসেবে লগইন করা হবে, সাপোর্টের জন্য। এই action audit log-এ থাকবে। চালিয়ে যাবেন?`))) return;
    try {
      await api.platformImpersonate(orgId, userId);
      window.location.hash = "#/app";
      window.location.reload();
    } catch (e) { toast.error(explain(e)); }
  }

  return (
    <Modal open title={detail?.name || "লোড হচ্ছে..."} onClose={onClose} wide>
      {error && <Notice tone="danger">{error}</Notice>}
      {!detail ? <Skeleton lines={4} height={30} /> : (
        <div className="stack">
          <div className="ui-stats">
            <Stat label="সদস্য" value={detail.member_count} />
            <Stat label="শাখা" value={detail.branch_count} />
            <Stat label="পণ্য" value={detail.product_count} />
            <Stat label="অবস্থা" value={detail.suspended_at ? "স্থগিত" : "সক্রিয়"} />
          </div>

          <Card title="Business profile" subtitle="Receipt, report এবং workspace এ ব্যবহৃত tenant তথ্য">
            <div className="platform-profile-grid">
              <Field label="Business name" required><input value={profile.name} onChange={(e) => setProfile((p) => ({ ...p, name: e.target.value }))} /></Field>
              <Field label="Sector" required><input value={profile.sector} onChange={(e) => setProfile((p) => ({ ...p, sector: e.target.value }))} /></Field>
              <Field label="Business size"><select value={profile.size_class} onChange={(e) => setProfile((p) => ({ ...p, size_class: e.target.value }))}><option value="">নির্ধারিত নয়</option><option value="micro">Micro</option><option value="small">Small</option><option value="medium">Medium</option></select></Field>
              <Field label="Phone"><input value={profile.phone} onChange={(e) => setProfile((p) => ({ ...p, phone: e.target.value }))} /></Field>
              <Field label="VAT registration"><input value={profile.vat_reg_no} onChange={(e) => setProfile((p) => ({ ...p, vat_reg_no: e.target.value }))} /></Field>
              <Field label="Address"><input value={profile.address} onChange={(e) => setProfile((p) => ({ ...p, address: e.target.value }))} /></Field>
            </div>
            <div className="platform-form-action"><small>Stable slug: {detail.slug}</small><Button size="sm" loading={busy} disabled={!profile.name.trim() || !profile.sector.trim()} onClick={saveProfile}>Profile সংরক্ষণ</Button></div>
          </Card>

          {detail.suspended_at ? (
            <Notice tone="warn" title={`স্থগিত: ${detail.suspended_reason || ""}`}
                    action={<Button size="sm" variant="secondary" loading={busy} onClick={unsuspend}>আবার সক্রিয় করুন</Button>} />
          ) : (
            <Card title="ব্যবসা স্থগিত করুন" subtitle="সব সদস্য লগইন করতে পারবেন না, ডেটা অক্ষত থাকবে।">
              <Field label="কারণ" required>
                <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="যেমন: পেমেন্ট বকেয়া" />
              </Field>
              <Button variant="danger" size="sm" loading={busy} onClick={suspend} disabled={!reason.trim()}>স্থগিত করুন</Button>
            </Card>
          )}

          <Card title="Team access management" subtitle="Role, membership status, MFA এবং support access পরিচালনা করুন">
            <div className="platform-member-list">
              {detail.members.map((member) => (
                <div key={member.membership_id} className={!member.active ? "inactive" : ""}>
                  <div className="platform-member-identity"><strong>{member.display_name}</strong><small>{member.email}</small></div>
                  <Badge tone={member.mfa_enabled ? "success" : "warn"}>MFA {member.mfa_enabled ? "চালু" : "বন্ধ"}</Badge>
                  <select aria-label={`${member.display_name} role`} value={member.role} disabled={memberBusy === member.membership_id} onChange={(e) => updateMember(member, { role: e.target.value })}>
                    {Object.entries(ROLE_LABELS).map(([value, label]) => <option value={value} key={value}>{label}</option>)}
                  </select>
                  <label className="platform-access-switch"><input type="checkbox" checked={member.active} disabled={memberBusy === member.membership_id} onChange={(e) => updateMember(member, { active: e.target.checked })} /><span>{member.active ? "Access চালু" : "Access বন্ধ"}</span></label>
                  <Button size="sm" variant="ghost" disabled={!member.active || !member.account_active} onClick={() => impersonate(member.user_id)}>Support login</Button>
                </div>
              ))}
              {detail.members.length === 0 && <EmptyState icon="users" title="কোনো member নেই" />}
            </div>
          </Card>

          <Card title="মডিউল নিয়ন্ত্রণ" subtitle="বন্ধ করা মডিউল এই ব্যবসার মেনু থেকে উধাও হয়ে যাবে।">
            <div className="stack" style={{ gap: 8 }}>
              {Object.entries(FEATURE_LABELS).map(([key, label]) => (
                <label key={key} className="ui-person" style={{ justifyContent: "space-between", cursor: "pointer" }}>
                  <span>{label}</span>
                  <input
                    type="checkbox" checked={detail.feature_flags[key] !== false}
                    disabled={busy}
                    onChange={(e) => toggleFeature(key, e.target.checked)}
                  />
                </label>
              ))}
            </div>
          </Card>

          <Card title="বিপজ্জনক অঞ্চল">
            <Button variant="danger" size="sm" loading={busy} disabled={!detail.suspended_at} onClick={remove}>
              স্থায়ীভাবে মুছে ফেলুন
            </Button>
            {!detail.suspended_at && <p className="hint">মুছতে হলে আগে স্থগিত করতে হবে।</p>}
          </Card>
        </div>
      )}
      {confirm.dialog}
    </Modal>
  );
}

function SiteContentCard() {
  const toast = useToast();
  const [content, setContent] = useState(null);
  const [heroTitle, setHeroTitle] = useState("");
  const [heroSubtitle, setHeroSubtitle] = useState("");
  const [faqItems, setFaqItems] = useState([]);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api.platformSiteContent().then((r) => {
      setContent(r.content);
      setHeroTitle(r.content.hero_title || "");
      setHeroSubtitle(r.content.hero_subtitle || "");
      setFaqItems(Array.isArray(r.content.faq_items) ? r.content.faq_items : []);
    }).catch(() => setContent({}));
  }, []);
  useEffect(() => { load(); }, [load]);

  async function saveHero() {
    setBusy(true);
    try {
      if (heroTitle.trim()) await api.platformSetSiteContent("hero_title", heroTitle.trim());
      else await api.platformResetSiteContent("hero_title");
      if (heroSubtitle.trim()) await api.platformSetSiteContent("hero_subtitle", heroSubtitle.trim());
      else await api.platformResetSiteContent("hero_subtitle");
      toast.success("হোমপেজের লেখা সংরক্ষণ করা হয়েছে।");
    } catch (e) { toast.error(explain(e)); } finally { setBusy(false); }
  }

  async function saveFaq() {
    setBusy(true);
    try {
      const cleaned = faqItems.filter(([q, a]) => q.trim() && a.trim());
      if (cleaned.length) await api.platformSetSiteContent("faq_items", cleaned);
      else await api.platformResetSiteContent("faq_items");
      setFaqItems(cleaned);
      toast.success("FAQ সংরক্ষণ করা হয়েছে।");
    } catch (e) { toast.error(explain(e)); } finally { setBusy(false); }
  }

  if (content === null) return <Skeleton lines={3} height={30} />;

  return (
    <Card title="পাবলিক হোমপেজের লেখা" subtitle="এখানে বদলালে সরাসরি /#/ পাতায় দেখাবে, কোনো deploy লাগবে না।">
      <div className="stack">
        <Field label="মূল শিরোনাম (hero title)" hint="খালি রাখলে default লেখা দেখাবে">
          <input value={heroTitle} onChange={(e) => setHeroTitle(e.target.value)} placeholder="ব্যবসার প্রতিটি সিদ্ধান্তের জন্য একটি নির্ভরযোগ্য সত্য" />
        </Field>
        <Field label="সাবটাইটেল" hint="খালি রাখলে default লেখা দেখাবে">
          <textarea rows={2} value={heroSubtitle} onChange={(e) => setHeroSubtitle(e.target.value)} />
        </Field>
        <div><Button size="sm" loading={busy} onClick={saveHero}>হোমপেজ সংরক্ষণ করুন</Button></div>

        <hr className="ui-divider" />

        <strong>FAQ (প্রশ্ন-উত্তর)</strong>
        <p className="hint">খালি রাখলে default FAQ তালিকা দেখাবে।</p>
        {faqItems.map(([q, a], i) => (
          <div key={i} className="stack" style={{ gap: 6, padding: "8px 0", borderBottom: "1px solid var(--border)" }}>
            <input value={q} placeholder="প্রশ্ন" onChange={(e) => {
              const next = [...faqItems]; next[i] = [e.target.value, next[i][1]]; setFaqItems(next);
            }} />
            <textarea rows={2} value={a} placeholder="উত্তর" onChange={(e) => {
              const next = [...faqItems]; next[i] = [next[i][0], e.target.value]; setFaqItems(next);
            }} />
            <div><Button size="sm" variant="ghost" onClick={() => setFaqItems(faqItems.filter((_, j) => j !== i))}>মুছুন</Button></div>
          </div>
        ))}
        <div className="row" style={{ gap: 8 }}>
          <Button size="sm" variant="secondary" onClick={() => setFaqItems([...faqItems, ["", ""]])}>নতুন প্রশ্ন যোগ করুন</Button>
          <Button size="sm" loading={busy} onClick={saveFaq}>FAQ সংরক্ষণ করুন</Button>
        </div>
      </div>
    </Card>
  );
}

// Every remaining homepage/feature-page content block (owner-problem cards,
// "Bangladesh ready" cards, feature-grid cards, trust cards) shares the same
// shape family: an array of objects or tuples. Rather than a bespoke form per
// block -- four more full UIs for marginal gain -- one JSON editor per key
// covers all of them, with the exact shape documented inline so an admin who
// isn't a developer can still edit it correctly without guessing the schema.
const ADVANCED_CONTENT_KEYS = [
  {
    key: "owner_problems", label: "हউমপেজ: আপনার সমস্যা थেকেই শুরু (ইংলিশ key)",
    hint: '[{"icon":"wallet","question":"...","answer":"...","path":"...","actor":"..."}]',
  },
  {
    key: "bangladesh_ready", label: "हউমপেজ: বাংলাদেশের বাস্তবতা",
    hint: '[{"icon":"wallet","title":"...","text":"..."}]',
  },
  {
    key: "core_features", label: "ফিচার পাতা: মূল ফিচার তালিকা",
    hint: '[{"icon":"cart","title":"...","text":"..."}]',
  },
  {
    key: "trust_items", label: "নিরাপত্তা পাতা: বিশ্বাসের বিষয়গুলো",
    hint: '[["shield","শিরোনাম","বিস্তারিত"], ...]',
  },
];

function AdvancedContentEditor({ entry }) {
  const toast = useToast();
  const [raw, setRaw] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.platformSiteContent().then((r) => {
      const value = r.content[entry.key];
      setRaw(value ? JSON.stringify(value, null, 2) : "");
      setLoaded(true);
    }).catch(() => setLoaded(true));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entry.key]);

  async function save() {
    setError("");
    if (!raw.trim()) {
      setBusy(true);
      try {
        await api.platformResetSiteContent(entry.key);
        toast.success("ডিফল্ট লেখায় ফিরিয়ে নেওয়া হয়েছে।");
      } catch (e) { toast.error(explain(e)); } finally { setBusy(false); }
      return;
    }
    let parsed;
    try {
      parsed = JSON.parse(raw);
    } catch {
      setError("এটা সঠিক JSON নয়। বাক্স, কমা ও কোটেশন চিহ্ন মিলিয়ে দেখুন।");
      return;
    }
    if (!Array.isArray(parsed)) {
      setError("উপরের মতো একটা লিস্ট [ ] আকারে লিখতে হবে।");
      return;
    }
    setBusy(true);
    try {
      await api.platformSetSiteContent(entry.key, parsed);
      toast.success("সংরক্ষণ করা হয়েছে।");
    } catch (e) { toast.error(explain(e)); } finally { setBusy(false); }
  }

  if (!loaded) return <Skeleton lines={2} height={24} />;

  return (
    <div className="stack" style={{ gap: 6, padding: "10px 0", borderBottom: "1px solid var(--border)" }}>
      <strong>{entry.label}</strong>
      <p className="hint">খালি রাখলে ডিফল্ট দেখাবে। আকৃতি: <code>{entry.hint}</code></p>
      <textarea rows={6} style={{ fontFamily: "monospace", fontSize: 12.5 }} value={raw} onChange={(e) => setRaw(e.target.value)} placeholder={entry.hint} />
      {error && <Notice tone="danger">{error}</Notice>}
      <div><Button size="sm" loading={busy} onClick={save}>সংরক্ষণ করুন</Button></div>
    </div>
  );
}

function AdvancedContentCard() {
  return (
    <Card title="অন্যান্য পাতার কনটেন্ট (উন্নত)" subtitle="এখানে JSON আকারে সরাসরি লেখা বদলাতে হবে। ডেভেলপার ছাড়া অন্য কেউ সতর্কতার সাথে ব্যবহার করুন।">
      <div className="stack">
        {ADVANCED_CONTENT_KEYS.map((entry) => <AdvancedContentEditor key={entry.key} entry={entry} />)}
      </div>
    </Card>
  );
}

function BackupsCard() {
  const toast = useToast();
  const confirm = useConfirm();
  const [backups, setBackups] = useState(null);
  const [error, setError] = useState("");
  const [busyAction, setBusyAction] = useState(""); // "" | "create" | filename being drilled
  const [drillResults, setDrillResults] = useState({}); // filename -> result

  const load = useCallback(() => {
    api.platformBackups().then((r) => setBackups(r.backups)).catch((e) => setError(explain(e)));
  }, []);
  useEffect(() => { load(); }, [load]);

  async function createBackup() {
    setBusyAction("create");
    try {
      await api.platformCreateBackup();
      toast.success("নতুন ব্যাকআপ নেওয়া হয়েছে।");
      load();
    } catch (e) { toast.error(explain(e)); } finally { setBusyAction(""); }
  }

  async function drill(filename) {
    if (!(await confirm(`"${filename}" ব্যাকআপ থেকে একটি আলাদা অস্থায়ী কপিতে রিস্টোর করে সারির সংখ্যা মিলিয়ে দেখা হবে। লাইভ ডেটাবেজ স্পর্শ করা হবে না। চালিয়ে যাবেন?`))) return;
    setBusyAction(filename);
    try {
      const result = await api.platformRestoreDrill(filename);
      setDrillResults((prev) => ({ ...prev, [filename]: result }));
      toast[result.reconciled ? "success" : "error"](
        result.reconciled ? "রিস্টোর মহড়া সফল। সব সারি মিলেছে।" : "গরমিল পাওয়া গেছে, বিস্তারিত নিচে দেখুন।"
      );
    } catch (e) { toast.error(explain(e)); } finally { setBusyAction(""); }
  }

  async function download(filename) {
    setBusyAction(`download:${filename}`);
    try { await api.platformDownloadBackup(filename); toast.success("Backup download শুরু হয়েছে।"); }
    catch (e) { toast.error(explain(e)); } finally { setBusyAction(""); }
  }

  async function remove(filename) {
    if (!(await confirm(`${filename} স্থায়ীভাবে মুছে যাবে। অন্তত একটি backup সবসময় রাখা হবে। নিশ্চিত?`))) return;
    setBusyAction(`delete:${filename}`);
    try { await api.platformDeleteBackup(filename); toast.success("Backup মুছে ফেলা হয়েছে।"); load(); }
    catch (e) { toast.error(explain(e, { 409: "শেষ available backup মুছে ফেলা যাবে না।" })); } finally { setBusyAction(""); }
  }

  return (
    <Card title="ডেটাবেজ ব্যাকআপ" subtitle="লাইভ অবস্থায়ই সামঞ্জস্যপূর্ণ কপি নেওয়া হয়। চলমান লেখালেখির মাঝে নিলেও ফাইল নষ্ট হবে না।">
      {error && <Notice tone="danger">{error}</Notice>}
      <div style={{ marginBottom: 12 }}>
        <Button size="sm" loading={busyAction === "create"} onClick={createBackup}>এখনই নতুন ব্যাকআপ নিন</Button>
      </div>
      {backups === null ? <Skeleton lines={3} height={28} /> : backups.length === 0 ? (
        <EmptyState icon="fileText" title="এখনো কোনো ব্যাকআপ নেই" />
      ) : (
        <div className="stack" style={{ gap: 10 }}>
          {backups.map((b) => (
            <div key={b.filename} className="stack" style={{ gap: 4, padding: "10px 0", borderBottom: "1px solid var(--border)" }}>
              <div className="ui-person" style={{ justifyContent: "space-between" }}>
                <div>
                  <strong style={{ fontSize: 13.5 }}>{b.filename}</strong>
                  <small>{(b.size_bytes / 1024 / 1024).toFixed(2)} MB · {dateTimeBn(b.modified_at)}</small>
                </div>
                <div className="platform-backup-actions">
                  <Button size="sm" variant="ghost" loading={busyAction === `download:${b.filename}`} onClick={() => download(b.filename)}>Download</Button>
                  <Button size="sm" variant="secondary" loading={busyAction === b.filename} onClick={() => drill(b.filename)}>রিস্টোর মহড়া</Button>
                  <Button size="sm" variant="danger" loading={busyAction === `delete:${b.filename}`} disabled={backups.length <= 1} onClick={() => remove(b.filename)}>মুছুন</Button>
                </div>
              </div>
              {drillResults[b.filename] && (
                <Notice tone={drillResults[b.filename].reconciled ? "success" : "warn"}>
                  {drillResults[b.filename].reconciled
                    ? "লাইভ ডেটার সাথে সব সারি-সংখ্যা মিলেছে।"
                    : `গরমিল: ${Object.keys(drillResults[b.filename].mismatches).join(", ")}`}
                </Notice>
              )}
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

function AuditLogCard() {
  const [entries, setEntries] = useState(null);
  const [error, setError] = useState("");
  const [action, setAction] = useState("");
  const [nextCursor, setNextCursor] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setEntries(null);
    api.platformAudit("", action).then((r) => { setEntries(r.entries); setNextCursor(r.next_cursor || ""); }).catch((e) => setError(explain(e)));
  }, [action]);

  async function loadMore() {
    setBusy(true);
    try {
      const result = await api.platformAudit(nextCursor, action);
      setEntries((current) => [...(current || []), ...result.entries]);
      setNextCursor(result.next_cursor || "");
    } catch (e) { setError(explain(e)); } finally { setBusy(false); }
  }

  return (
    <Card title="প্ল্যাটফর্ম কার্যকলাপের ইতিহাস" subtitle="যেকোনো admin যা করেছেন, সব এখানে। এই ইতিহাস মুছে ফেলা বা বদলানো যায় না।">
      {error && <Notice tone="danger">{error}</Notice>}
      <div className="platform-audit-toolbar">
        <Field label="Action দিয়ে filter করুন">
          <select value={action} onChange={(e) => setAction(e.target.value)}>
            <option value="">সব administrative action</option>
            {Object.entries(AUDIT_ACTION_LABELS).map(([value, label]) => <option value={value} key={value}>{label}</option>)}
          </select>
        </Field>
        <Badge tone="neutral">{bnNumber(entries?.length || 0)}টি record</Badge>
      </div>
      {entries === null ? <Skeleton lines={4} height={28} /> : entries.length === 0 ? (
        <EmptyState icon="fileText" title="এখনো কোনো কার্যকলাপ নেই" />
      ) : (
        <div className="platform-audit-list">
          {entries.map((e) => (
            <div key={e.id}>
              <div className="platform-audit-icon"><Icon name="shield" size={17} /></div>
              <div><strong>{AUDIT_ACTION_LABELS[e.action] || e.action}</strong><small>{e.actor_email || "অজানা"} · {dateTimeBn(e.created_at)}</small><small>{e.entity_type || "platform"}{e.entity_id ? ` · ${e.entity_id}` : ""}</small></div>
              {e.metadata && <details><summary>Details</summary><pre>{JSON.stringify(e.metadata, null, 2)}</pre></details>}
            </div>
          ))}
          {nextCursor && <div className="platform-load-more"><Button size="sm" variant="secondary" loading={busy} onClick={loadMore}>আরও activity দেখুন</Button></div>}
        </div>
      )}
    </Card>
  );
}

function OperationsQueue({ onNavigate }) {
  const [items, setItems] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    Promise.all([
      api.platformSecurity(), api.platformSystemHealth(), api.platformOnboarding(), api.platformIntegrationOperations(),
    ]).then(([security, system, onboarding, delivery]) => {
      const failed = (delivery.status_counts.failed || 0) + (delivery.status_counts.error || 0);
      const pendingProviders = system.provider_total - system.provider_ready_count;
      const incomplete = onboarding.count - onboarding.completed;
      const queue = [];
      if (security.mfa_missing) queue.push({ key: "mfa", icon: "shield", tone: "danger", title: `${bnNumber(security.mfa_missing)}টি active account এ MFA নেই`, text: "Identity risk কমাতে account গুলো review করুন।", tab: "security" });
      if (failed) queue.push({ key: "delivery", icon: "mail", tone: "danger", title: `${bnNumber(failed)}টি message delivery failed`, text: "Provider error ও affected business দেখুন।", tab: "delivery" });
      if (pendingProviders) queue.push({ key: "provider", icon: "zap", tone: "warn", title: `${bnNumber(pendingProviders)}টি provider setup অসম্পূর্ণ`, text: "Production credential readiness পরীক্ষা করুন।", tab: "system" });
      if (incomplete) queue.push({ key: "onboarding", icon: "target", tone: "warn", title: `${bnNumber(incomplete)}টি SME onboarding অসম্পূর্ণ`, text: "যে milestone এ আটকে আছে সেখানে সহায়তা দিন।", tab: "onboarding" });
      setItems(queue);
    }).catch((e) => setError(explain(e)));
  }, []);
  return (
    <Card title="আজকের action queue" subtitle="Security, integration এবং onboarding data থেকে live priority">
      {error && <Notice tone="danger">{error}</Notice>}
      {items === null ? <Skeleton lines={3} height={48} /> : items.length === 0 ? <EmptyState icon="check" title="কোনো জরুরি action নেই" hint="সব operational signal healthy আছে।" /> : (
        <div className="platform-action-queue">
          {items.map((item) => (
            <button type="button" key={item.key} onClick={() => onNavigate(item.tab)}>
              <span className={item.tone}><Icon name={item.icon} size={19} /></span>
              <div><strong>{item.title}</strong><small>{item.text}</small></div>
              <Icon name="chevronRight" size={18} />
            </button>
          ))}
        </div>
      )}
    </Card>
  );
}

function TrendsCard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.platformTrends(30).then((r) => setData(r.series)).catch((e) => setError(explain(e)));
  }, []);

  const chart = useMemo(() => (data || []).map((d) => ({
    ...d, label: new Date(d.date).toLocaleDateString("bn-BD", { day: "numeric", month: "short" }),
  })), [data]);

  return (
    <Card title="গত ৩০ দিনের প্রবণতা" subtitle="সব ব্যবসা মিলিয়ে নতুন সাইনআপ ও মোট বিক্রির বাস্তব হিসাব। এখানে কোনো অনুমান নেই।">
      {error && <Notice tone="danger">{error}</Notice>}
      {data === null ? <Skeleton lines={3} height={200} /> : (
        <ResponsiveContainer width="100%" height={240}>
          <AreaChart data={chart} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
            <defs>
              <linearGradient id="platformSalesFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#0a8754" stopOpacity={0.35} />
                <stop offset="100%" stopColor="#0a8754" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="label" tickLine={false} axisLine={false} interval="preserveStartEnd" minTickGap={28} />
            <YAxis tickLine={false} axisLine={false} width={60} tickFormatter={(v) => `৳${Math.round(v / 1000)}k`} />
            <Tooltip formatter={(value, name) => [name === "sales_bdt" ? `৳${Number(value).toLocaleString("bn-BD")}` : value, name === "sales_bdt" ? "বিক্রি" : "নতুন ব্যবসা"]} labelFormatter={(l) => l} />
            <Area type="monotone" dataKey="sales_bdt" stroke="#0a8754" fill="url(#platformSalesFill)" strokeWidth={2} />
          </AreaChart>
        </ResponsiveContainer>
      )}
      {data && <p className="hint">মোট নতুন ব্যবসা যোগ হয়েছে এই ৩০ দিনে: {data.reduce((s, d) => s + d.new_organizations, 0)}টা</p>}
    </Card>
  );
}

function StaleOrgsCard() {
  const [stale, setStale] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.platformStaleOrganizations(14).then((r) => setStale(r.organizations)).catch((e) => setError(explain(e)));
  }, []);

  return (
    <Card title="নিষ্ক্রিয় হয়ে যাচ্ছে এমন ব্যবসা" subtitle="১৪ দিনের বেশি কোনো বিক্রি নেই। হয়তো সেটআপে আটকে আছেন অথবা ব্যবহার বন্ধ করেছেন।">
      {error && <Notice tone="danger">{error}</Notice>}
      {stale === null ? <Skeleton lines={2} height={28} /> : stale.length === 0 ? (
        <EmptyState icon="check" title="সবাই সক্রিয় আছে" hint="১৪ দিনের মধ্যে প্রতিটা সক্রিয় ব্যবসায় বিক্রি হয়েছে।" />
      ) : (
        <div className="stack" style={{ gap: 8 }}>
          {stale.map((o) => (
            <div key={o.id} className="ui-person" style={{ justifyContent: "space-between", padding: "6px 0", borderBottom: "1px solid var(--border)" }}>
              <div><strong style={{ fontSize: 13.5 }}>{o.name}</strong><small>{o.slug}</small></div>
              <Badge tone="warn">{o.last_sale_at ? `শেষ বিক্রি ${dateBn(o.last_sale_at)}` : "কখনো বিক্রি হয়নি"}</Badge>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

const ONBOARDING_STEPS = {
  profile: "Profile",
  team: "Team",
  branch: "Branch",
  catalog: "Catalog",
  first_sale: "First sale",
};

function OnboardingPipeline({ onOpenOrg }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api.platformOnboarding().then(setData).catch((e) => setError(explain(e)));
  }, []);
  if (error) return <Notice tone="danger">{error}</Notice>;
  if (!data) return <Skeleton lines={6} height={58} />;
  const setupCount = data.count - data.completed;
  return (
    <div className="stack">
      <div className="platform-summary-strip">
        <p>Profile, team, branch, catalog এবং first sale এর actual data থেকে প্রতিটি business কোথায় আটকে আছে দেখুন।</p>
        <div className="platform-intro-badges"><Badge tone="success">{bnNumber(data.completed)}টি live</Badge><Badge tone="warn">{bnNumber(setupCount)}টি setup এ</Badge></div>
      </div>
      {data.organizations.length === 0 ? <EmptyState icon="users" title="কোনো active business নেই" /> : (
        <div className="platform-onboarding-list">
          {data.organizations.map((org) => (
            <section key={org.id}>
              <div className="platform-onboarding-head">
                <div><strong>{org.name}</strong><small>{org.sector} · {org.age_days === 0 ? "আজ তৈরি" : `${bnNumber(org.age_days)} দিন আগে তৈরি`}</small></div>
                <Badge tone={org.stage === "live" ? "success" : org.stage === "ready" ? "info" : "warn"}>{org.stage === "live" ? "Live" : org.stage === "ready" ? "Ready to sell" : "Setup চলছে"}</Badge>
                <strong>{bnNumber(org.progress_percent)}%</strong>
              </div>
              <div className="platform-progress"><i style={{ width: `${org.progress_percent}%` }} /></div>
              <div className="platform-checklist">
                {Object.entries(ONBOARDING_STEPS).map(([key, label]) => <span className={org.checklist[key] ? "done" : ""} key={key}><Icon name={org.checklist[key] ? "check" : "clock"} size={14} />{label}</span>)}
              </div>
              <Button size="sm" variant="secondary" onClick={() => onOpenOrg(org.id)}>Business পরিচালনা করুন</Button>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}

function SystemHealthPanel() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api.platformSystemHealth().then(setData).catch((e) => setError(explain(e)));
  }, []);

  if (error) return <Notice tone="danger">{error}</Notice>;
  if (!data) return <Skeleton lines={5} height={46} />;
  const backup = data.backup.latest;
  return (
    <div className="stack">
      <div className="platform-summary-strip">
        <p>Runtime, database, authentication, backup এবং external provider এর বর্তমান readiness এক জায়গায়।</p>
        <Badge tone={data.database.connected ? "success" : "danger"}>{data.database.connected ? "সিস্টেম সচল" : "সমস্যা পাওয়া গেছে"}</Badge>
      </div>

      <div className="platform-health-grid">
        <Card title="Runtime profile" subtitle="এই deployment যে configuration এ চলছে">
          <dl className="platform-kv-list">
            <div><dt>Environment</dt><dd>{data.environment}</dd></div>
            <div><dt>Authentication</dt><dd>{data.auth_mode}</dd></div>
            <div><dt>Integration mode</dt><dd>{data.integration_mode}</dd></div>
            <div><dt>Database</dt><dd><Badge tone="success">{data.database.profile} connected</Badge></dd></div>
          </dl>
        </Card>
        <Card title="Backup readiness" subtitle="সর্বশেষ recoverable database snapshot">
          {!data.backup.supported_in_panel ? (
            <Notice tone="info">PostgreSQL backup infrastructure থেকে পরিচালিত হবে।</Notice>
          ) : backup ? (
            <div className="platform-backup-state">
              <Icon name="check" size={24} />
              <div><strong>{backup.age_hours <= 24 ? "Backup সময়মতো নেওয়া হয়েছে" : "নতুন backup প্রয়োজন"}</strong><p>{dateTimeBn(backup.modified_at)} · {formatBytes(backup.size_bytes)}</p><small>{backup.filename}</small></div>
            </div>
          ) : (
            <Notice tone="warn" title="এখনো backup নেই">Backup management থেকে প্রথম snapshot নিন।</Notice>
          )}
        </Card>
      </div>

      <Card title="Provider readiness" subtitle={`${bnNumber(data.provider_ready_count)}টির মধ্যে ${bnNumber(data.provider_total)}টি service production call করার জন্য configured`}>
        <div className="platform-provider-grid">
          {data.providers.map((provider) => (
            <div className={`platform-provider ${provider.configured ? "ready" : "pending"}`} key={provider.key}>
              <div className="platform-provider-icon"><Icon name={provider.category === "payment" ? "wallet" : provider.category === "messaging" ? "mail" : "zap"} size={20} /></div>
              <div><strong>{provider.name}</strong><small>{provider.configured ? "Credential configured" : "Credential setup প্রয়োজন"}</small></div>
              <Badge tone={provider.configured ? "success" : "warn"}>{provider.configured ? "Ready" : "Pending"}</Badge>
            </div>
          ))}
        </div>
        <Notice tone="info" title="নিরাপত্তা">এই panel শুধু readiness দেখায়। API key, token এবং password কখনো browser এ পাঠানো হয় না।</Notice>
      </Card>
    </div>
  );
}

function IntegrationOperations({ onOpenOrg }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api.platformIntegrationOperations().then(setData).catch((e) => setError(explain(e)));
  }, []);
  if (error) return <Notice tone="danger">{error}</Notice>;
  if (!data) return <Skeleton lines={6} height={48} />;
  const total = Object.values(data.status_counts).reduce((sum, count) => sum + count, 0);
  const failed = (data.status_counts.failed || 0) + (data.status_counts.error || 0);
  const delivered = (data.status_counts.sent || 0) + (data.status_counts.delivered || 0) + (data.status_counts.simulated || 0);
  return (
    <div className="stack">
      <div className="platform-summary-strip">
        <p>সব tenant এর outbound message delivery status দেখুন। Message body ও সম্পূর্ণ recipient নিরাপত্তার জন্য দেখানো হয় না।</p>
        <Badge tone={failed ? "danger" : "success"}>{failed ? `${bnNumber(failed)}টি failed` : "Delivery healthy"}</Badge>
      </div>
      <div className="platform-security-stats">
        <Stat icon="mail" label="মোট message" value={bnNumber(total)} />
        <Stat icon="check" label="Sent or simulated" value={bnNumber(delivered)} />
        <Stat icon="alert" label="Failed" value={bnNumber(failed)} />
        <Stat icon="clock" label="Queued" value={bnNumber(data.status_counts.queued || 0)} />
      </div>
      <Card title="সাম্প্রতিক delivery activity" subtitle="সর্বশেষ ১০০টি outbound message">
        <DataTable loading={false} rows={data.messages} rowKey="id" caption="Outbound delivery activity" empty={<EmptyState icon="mail" title="এখনো কোনো message পাঠানো হয়নি" />} columns={[
          { key: "business", label: "Business", primary: true, render: (row) => <button type="button" className="platform-link-button" onClick={() => onOpenOrg(row.organization_id)}>{row.organization_name}</button> },
          { key: "channel", label: "Channel", render: (row) => <Badge tone="info">{row.channel === "sms" ? "SMS" : "WhatsApp"}</Badge> },
          { key: "recipient", label: "Recipient", render: (row) => row.recipient_masked },
          { key: "template", label: "Template", render: (row) => row.template },
          { key: "status", label: "Status", render: (row) => <Badge tone={["failed", "error"].includes(row.status) ? "danger" : ["sent", "delivered", "simulated"].includes(row.status) ? "success" : "warn"}>{row.status}</Badge> },
          { key: "time", label: "সময়", render: (row) => dateTimeBn(row.sent_at || row.created_at) },
          { key: "error", label: "Error", render: (row) => row.last_error || "কোনো error নেই" },
        ]} />
      </Card>
    </div>
  );
}

function AdministratorGovernance() {
  const confirm = useConfirm();
  const toast = useToast();
  const [admins, setAdmins] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [query, setQuery] = useState("");
  const [busyId, setBusyId] = useState("");
  const [error, setError] = useState("");
  const load = useCallback(() => {
    api.platformAdministrators().then((r) => setAdmins(r.administrators)).catch((e) => setError(explain(e)));
  }, []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (query.trim().length < 2) { setCandidates([]); return; }
    const timer = window.setTimeout(() => {
      api.platformUsers(query).then((r) => setCandidates(r.users.filter((user) => !user.is_platform_admin))).catch((e) => setError(explain(e)));
    }, 250);
    return () => window.clearTimeout(timer);
  }, [query]);

  async function setAdmin(user, enabled) {
    const text = enabled
      ? `${user.email} কে পুরো platform এর administrative access দেওয়া হবে। নিশ্চিত?`
      : `${user.email} এর platform administrative access বাতিল হবে। নিশ্চিত?`;
    if (!(await confirm(text))) return;
    setBusyId(user.id);
    try {
      await api.platformSetAdministrator(user.id, enabled);
      toast.success(enabled ? "Platform admin access দেওয়া হয়েছে।" : "Platform admin access বাতিল হয়েছে।");
      setQuery(""); setCandidates([]); load();
    } catch (e) { toast.error(explain(e, { 409: "Admin grant এর আগে account active এবং MFA enabled হতে হবে। নিজের access নিজে বাতিল করা যাবে না।" })); } finally { setBusyId(""); }
  }

  return (
    <div className="stack">
      <div className="platform-summary-strip">
        <p>কারা সব tenant, user, security এবং system control করতে পারবেন তা এখান থেকে পরিচালিত হয়।</p>
        <Badge tone="warn">MFA বাধ্যতামূলক</Badge>
      </div>
      {error && <Notice tone="danger">{error}</Notice>}
      <Card title="বর্তমান platform administrators" subtitle="Self removal এবং last admin removal server থেকে বন্ধ রাখা হয়েছে">
        {!admins ? <Skeleton lines={3} height={46} /> : (
          <div className="platform-admin-list">
            {admins.map((user) => (
              <div key={user.id}>
                <div className="platform-account-avatar">{(user.display_name || user.email).slice(0, 1).toUpperCase()}</div>
                <div><strong>{user.display_name || "নাম দেওয়া হয়নি"}</strong><small>{user.email}</small><small>{user.last_session_at ? `সর্বশেষ session ${dateTimeBn(user.last_session_at)}` : "কোনো session পাওয়া যায়নি"}</small></div>
                <Badge tone={user.mfa_enabled ? "success" : "danger"}>MFA {user.mfa_enabled ? "চালু" : "বন্ধ"}</Badge>
                {user.is_current ? <Badge tone="info">আপনি</Badge> : <Button size="sm" variant="danger" loading={busyId === user.id} onClick={() => setAdmin(user, false)}>Access বাতিল</Button>}
              </div>
            ))}
          </div>
        )}
      </Card>
      <Card title="নতুন administrator যোগ করুন" subtitle="Active এবং MFA enabled account কেই privileged access দেওয়া যাবে">
        <Field label="Account খুঁজুন" hint="নাম বা email এর অন্তত ২টি অক্ষর লিখুন"><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="যেমন admin@example.com" /></Field>
        {query.trim().length >= 2 && candidates.length === 0 && <p className="hint">Matching non admin account পাওয়া যায়নি।</p>}
        <div className="platform-candidate-list">
          {candidates.slice(0, 10).map((user) => (
            <div key={user.id}>
              <div><strong>{user.display_name || "নাম দেওয়া হয়নি"}</strong><small>{user.email}</small></div>
              <Badge tone={user.active ? "success" : "danger"}>{user.active ? "Active" : "Inactive"}</Badge>
              <Badge tone={user.mfa_enabled ? "success" : "warn"}>MFA {user.mfa_enabled ? "চালু" : "বন্ধ"}</Badge>
              <Button size="sm" disabled={!user.active || !user.mfa_enabled} loading={busyId === user.id} onClick={() => setAdmin(user, true)}>Admin করুন</Button>
            </div>
          ))}
        </div>
      </Card>
      {confirm.dialog}
    </div>
  );
}

function AnnouncementCenter() {
  const confirm = useConfirm();
  const toast = useToast();
  const [history, setHistory] = useState(null);
  const [orgs, setOrgs] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState({ title: "", body: "", severity: "info", audience: "owners", organization_id: "" });
  const load = useCallback(() => {
    Promise.all([api.platformAnnouncements(), api.platformOrganizations()])
      .then(([announcements, organizations]) => { setHistory(announcements.announcements); setOrgs(organizations.organizations); })
      .catch((e) => setError(explain(e)));
  }, []);
  useEffect(() => { load(); }, [load]);

  async function send() {
    const scope = form.organization_id ? orgs.find((org) => org.id === form.organization_id)?.name : "সব active business";
    if (!(await confirm(`${scope} এর নির্বাচিত audience কে এই in app announcement পাঠানো হবে। নিশ্চিত?`))) return;
    setBusy(true);
    try {
      const result = await api.platformSendAnnouncement({
        title: form.title.trim(), body: form.body.trim(), severity: form.severity,
        audience: form.audience, organization_ids: form.organization_id ? [form.organization_id] : null,
      });
      toast.success(`${bnNumber(result.recipient_count)} জনকে announcement পাঠানো হয়েছে।`);
      setForm({ title: "", body: "", severity: "info", audience: "owners", organization_id: "" });
      load();
    } catch (e) { toast.error(explain(e)); } finally { setBusy(false); }
  }

  return (
    <div className="stack">
      <div className="platform-summary-strip">
        <p>একটি business অথবা সব active SME এর owner, leadership বা পুরো team কে in app notice পাঠান।</p>
        <Badge tone="info">Audit logged</Badge>
      </div>
      {error && <Notice tone="danger">{error}</Notice>}
      <Card title="নতুন announcement" subtitle="জরুরি service notice, maintenance বা operational guidance পাঠাতে ব্যবহার করুন">
        <div className="platform-profile-grid">
          <Field label="Target business"><select value={form.organization_id} onChange={(e) => setForm((f) => ({ ...f, organization_id: e.target.value }))}><option value="">সব active business</option>{orgs.filter((org) => org.active && !org.suspended_at).map((org) => <option value={org.id} key={org.id}>{org.name}</option>)}</select></Field>
          <Field label="Audience"><select value={form.audience} onChange={(e) => setForm((f) => ({ ...f, audience: e.target.value }))}><option value="owners">শুধু owner</option><option value="leadership">Owner ও manager</option><option value="all">সব active member</option></select></Field>
          <Field label="Severity"><select value={form.severity} onChange={(e) => setForm((f) => ({ ...f, severity: e.target.value }))}><option value="info">Information</option><option value="warning">Warning</option><option value="critical">Critical</option></select></Field>
          <Field label="শিরোনাম" hint={`${form.title.length}/200`}><input maxLength={200} value={form.title} onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} placeholder="যেমন: আজ রাত ১১টায় maintenance" /></Field>
        </div>
        <Field label="বিস্তারিত message" hint={`${form.body.length}/1500`}><textarea rows={5} maxLength={1500} value={form.body} onChange={(e) => setForm((f) => ({ ...f, body: e.target.value }))} placeholder="ব্যবহারকারীর কী জানা বা করা প্রয়োজন তা পরিষ্কারভাবে লিখুন" /></Field>
        <div className="platform-form-action"><small>Recipient প্রতি একটি notification তৈরি হবে।</small><Button loading={busy} disabled={form.title.trim().length < 3 || form.body.trim().length < 3} onClick={send}>Announcement পাঠান</Button></div>
      </Card>
      <Card title="Announcement history" subtitle="সর্বশেষ ৫০টি audited broadcast">
        {history === null ? <Skeleton lines={3} height={45} /> : history.length === 0 ? <EmptyState icon="bell" title="এখনো announcement পাঠানো হয়নি" /> : (
          <div className="platform-announcement-list">
            {history.map((item) => <div key={item.id}><div><Badge tone={item.severity === "critical" ? "danger" : item.severity === "warning" ? "warn" : "info"}>{item.severity}</Badge></div><div><strong>{item.title}</strong><p>{item.body}</p><small>{item.actor_email} · {dateTimeBn(item.created_at)} · {bnNumber(item.organization_count)} business · {bnNumber(item.recipient_count)} recipient</small></div></div>)}
          </div>
        )}
      </Card>
      {confirm.dialog}
    </div>
  );
}

function SecurityCenter() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api.platformSecurity().then(setData).catch((e) => setError(explain(e)));
  }, []);

  if (error) return <Notice tone="danger">{error}</Notice>;
  if (!data) return <Skeleton lines={5} height={46} />;
  const coverageTone = data.mfa_coverage_percent >= 80 ? "success" : data.mfa_coverage_percent >= 50 ? "warn" : "danger";
  return (
    <div className="stack">
      <div className="platform-summary-strip">
        <p>Account lifecycle, MFA adoption এবং login session এর বাস্তব অবস্থা পর্যবেক্ষণ করুন।</p>
        <Badge tone={coverageTone}>MFA {bnNumber(data.mfa_coverage_percent)}%</Badge>
      </div>
      <div className="platform-security-stats">
        <Stat icon="userCheck" label="সক্রিয় account" value={bnNumber(data.users_active)} />
        <Stat icon="lock" label="MFA চালু" value={bnNumber(data.mfa_enabled)} />
        <Stat icon="shield" label="Platform admin" value={bnNumber(data.platform_admins)} />
        <Stat icon="zap" label="Active session" value={bnNumber(data.sessions_active)} />
      </div>
      <div className="platform-health-grid">
        <Card title="MFA coverage" subtitle="সক্রিয় account এর কত শতাংশ দ্বিতীয় ধাপের সুরক্ষায় আছে">
          <div className="platform-progress-head"><strong>{bnNumber(data.mfa_coverage_percent)}%</strong><span>{bnNumber(data.mfa_enabled)} of {bnNumber(data.users_active)} accounts</span></div>
          <div className="platform-progress" role="progressbar" aria-label="MFA coverage" aria-valuemin="0" aria-valuemax="100" aria-valuenow={data.mfa_coverage_percent}><i style={{ width: `${data.mfa_coverage_percent}%` }} /></div>
          {data.mfa_missing > 0 ? <Notice tone="warn">{bnNumber(data.mfa_missing)}টি সক্রিয় account এ MFA চালু নেই। User management থেকে account গুলো শনাক্ত করুন।</Notice> : <Notice tone="success">সব সক্রিয় account MFA সুরক্ষিত।</Notice>}
        </Card>
        <Card title="Session control" subtitle="বর্তমান ও বাতিল authentication session">
          <dl className="platform-kv-list">
            <div><dt>Active session</dt><dd>{bnNumber(data.sessions_active)}</dd></div>
            <div><dt>Revoked session</dt><dd>{bnNumber(data.sessions_revoked)}</dd></div>
            <div><dt>Inactive account</dt><dd>{bnNumber(data.users_inactive)}</dd></div>
            <div><dt>Platform admin</dt><dd>{bnNumber(data.platform_admins)}</dd></div>
          </dl>
          <p className="hint">কোনো account নিষ্ক্রিয় করলে তার token version বদলে যায় এবং existing access বাতিল হয়।</p>
        </Card>
      </div>
    </div>
  );
}

function FeatureRolloutPanel({ onOpenOrg }) {
  const confirm = useConfirm();
  const toast = useToast();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [busyKey, setBusyKey] = useState("");
  const load = useCallback(() => {
    api.platformFeatureRollout().then(setData).catch((e) => setError(explain(e)));
  }, []);
  useEffect(() => { load(); }, [load]);

  async function rollout(feature, enabled) {
    const label = FEATURE_LABELS[feature.key] || feature.key;
    const message = enabled
      ? `সব সক্রিয় ব্যবসার জন্য ${label} চালু হবে। নিশ্চিত?`
      : `সব সক্রিয় ব্যবসার জন্য ${label} বন্ধ হবে। ব্যবহারকারীরা এই module আর দেখতে পাবেন না। নিশ্চিত?`;
    if (!(await confirm(message))) return;
    setBusyKey(feature.key);
    try {
      const result = await api.platformSetFeatureRollout(feature.key, enabled);
      toast.success(`${bnNumber(result.updated_count)}টি ব্যবসার module access update হয়েছে।`);
      load();
    } catch (e) { toast.error(explain(e)); } finally { setBusyKey(""); }
  }

  if (error) return <Notice tone="danger">{error}</Notice>;
  if (!data) return <Skeleton lines={6} height={58} />;
  return (
    <div className="stack">
      <div className="platform-summary-strip">
        <p>{bnNumber(data.active_organizations)}টি সক্রিয় business এ module availability, exception এবং bulk rollout পরিচালনা করুন।</p>
        <Badge tone="info">{bnNumber(data.features.length)}টি module</Badge>
      </div>
      <div className="platform-rollout-list">
        {data.features.map((feature) => (
          <section className="platform-rollout-item" key={feature.key}>
            <div className="platform-rollout-main">
              <div className="platform-rollout-icon"><Icon name="sliders" size={20} /></div>
              <div><h3>{FEATURE_LABELS[feature.key] || feature.key}</h3><p>{bnNumber(feature.enabled_count)}টি চালু · {bnNumber(feature.disabled_count)}টি বন্ধ</p></div>
              <strong>{bnNumber(feature.coverage_percent)}%</strong>
            </div>
            <div className="platform-progress"><i style={{ width: `${feature.coverage_percent}%` }} /></div>
            {feature.disabled_organizations.length > 0 && (
              <div className="platform-exceptions">
                <span>বন্ধ আছে</span>
                {feature.disabled_organizations.slice(0, 6).map((org) => <button type="button" key={org.id} onClick={() => onOpenOrg(org.id)}>{org.name}</button>)}
                {feature.disabled_organizations.length > 6 && <small>আরও {bnNumber(feature.disabled_organizations.length - 6)}টি</small>}
              </div>
            )}
            <div className="platform-rollout-actions">
              <Button size="sm" variant="secondary" loading={busyKey === feature.key} onClick={() => rollout(feature, true)}>সব business এ চালু</Button>
              <Button size="sm" variant="ghost" disabled={busyKey === feature.key} onClick={() => rollout(feature, false)}>সব business এ বন্ধ</Button>
            </div>
          </section>
        ))}
      </div>
      {confirm.dialog}
    </div>
  );
}

function PlatformUserModal({ userId, onClose, onOpenOrg }) {
  const confirm = useConfirm();
  const toast = useToast();
  const [user, setUser] = useState(null);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState("");
  const load = useCallback(() => {
    api.platformUser(userId).then(setUser).catch((e) => setError(explain(e)));
  }, [userId]);
  useEffect(() => { load(); }, [load]);

  async function revoke(session) {
    if (!(await confirm(`${session.device_label} session টি এখনই revoke হবে। নিশ্চিত?`))) return;
    setBusyId(session.id);
    try {
      await api.platformRevokeUserSession(userId, session.id);
      toast.success("Device session revoke হয়েছে।");
      load();
    } catch (e) { toast.error(explain(e)); } finally { setBusyId(""); }
  }

  return (
    <Modal open wide title={user?.display_name || user?.email || "Account detail"} onClose={onClose}>
      {error && <Notice tone="danger">{error}</Notice>}
      {!user ? <Skeleton lines={6} height={38} /> : (
        <div className="stack">
          <div className="platform-account-hero">
            <div className="platform-account-avatar">{(user.display_name || user.email).slice(0, 1).toUpperCase()}</div>
            <div><h3>{user.display_name || "নাম দেওয়া হয়নি"}</h3><p>{user.email}</p><small>Account তৈরি {dateBn(user.created_at)}</small></div>
            <div className="platform-account-badges"><Badge tone={user.active ? "success" : "danger"}>{user.active ? "সক্রিয়" : "নিষ্ক্রিয়"}</Badge><Badge tone={user.mfa_enabled ? "success" : "warn"}>MFA {user.mfa_enabled ? "চালু" : "বন্ধ"}</Badge>{user.is_platform_admin && <Badge tone="info">Platform admin</Badge>}</div>
          </div>

          <Card title="Business access" subtitle={`${bnNumber(user.memberships.length)}টি business membership`}>
            {user.memberships.length === 0 ? <EmptyState icon="users" title="কোনো business access নেই" /> : (
              <div className="platform-membership-list">
                {user.memberships.map((membership) => (
                  <button type="button" key={membership.id} onClick={() => onOpenOrg(membership.organization_id)}>
                    <div><strong>{membership.organization_name}</strong><small>{membership.organization_slug}</small></div>
                    <div><Badge tone={membership.active && !membership.organization_suspended ? "success" : "warn"}>{ROLE_LABELS[membership.role] || membership.role}</Badge><Icon name="chevronRight" size={17} /></div>
                  </button>
                ))}
              </div>
            )}
          </Card>

          <Card title="Device sessions" subtitle="সন্দেহজনক device আলাদাভাবে sign out করুন">
            {user.sessions.length === 0 ? <EmptyState icon="lock" title="কোনো session নেই" /> : (
              <div className="platform-session-list">
                {user.sessions.map((session) => (
                  <div key={session.id}>
                    <div className="platform-session-icon"><Icon name={session.active ? "zap" : "ban"} size={18} /></div>
                    <div><strong>{session.device_label}</strong><small>{session.ip_address || "IP পাওয়া যায়নি"} · সর্বশেষ {dateTimeBn(session.last_used_at)}</small></div>
                    {session.active ? <Button size="sm" variant="danger" loading={busyId === session.id} onClick={() => revoke(session)}>Revoke</Button> : <Badge tone="neutral">Revoked</Badge>}
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      )}
      {confirm.dialog}
    </Modal>
  );
}

function UserDirectoryCard({ onOpenOrg }) {
  const confirm = useConfirm();
  const toast = useToast();
  const [users, setUsers] = useState(null);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [hasNext, setHasNext] = useState(false);
  const [busyId, setBusyId] = useState("");
  const [openUserId, setOpenUserId] = useState("");
  const load = useCallback(() => api.platformUsers(query, filter, page).then((r) => { setUsers(r.users); setTotal(r.count); setHasNext(r.has_next); }).catch((e) => toast.error(explain(e))), [query, filter, page, toast]);
  useEffect(() => { const timer = window.setTimeout(load, 200); return () => window.clearTimeout(timer); }, [load]);
  async function setAccess(user) {
    const active = !user.active;
    if (!(await confirm(active ? `${user.email} আবার লগইন করতে পারবেন। চালিয়ে যাবেন?` : `${user.email} এর সব active session বন্ধ হবে এবং লগইন বন্ধ হবে। চালিয়ে যাবেন?`))) return;
    setBusyId(user.id);
    try { await api.platformSetUserAccess(user.id, active); toast.success(active ? "ব্যবহারকারী সক্রিয় করা হয়েছে।" : "ব্যবহারকারী নিষ্ক্রিয় করা হয়েছে।"); load(); } catch (e) { toast.error(explain(e)); } finally { setBusyId(""); }
  }
  return <Card title="সব ব্যবহারকারী" subtitle="Global account access, MFA এবং business membership দেখুন ও নিয়ন্ত্রণ করুন।">
    <div className="platform-filterbar">
      <Field label="ব্যবহারকারী খুঁজুন"><input value={query} onChange={(e) => { setQuery(e.target.value); setPage(1); }} placeholder="নাম বা ইমেইল" /></Field>
      <Field label="Security filter"><select value={filter} onChange={(e) => { setFilter(e.target.value); setPage(1); }}><option value="all">সব account</option><option value="mfa">MFA ছাড়া active</option><option value="inactive">Inactive account</option><option value="admin">Platform admin</option></select></Field>
      <Badge tone={filter === "mfa" ? "warn" : "neutral"}>{bnNumber(total)}টি result</Badge>
    </div>
    <DataTable loading={users === null} rows={users || []} rowKey="id" caption="সব ব্যবহারকারী" empty={<EmptyState icon="users" title="এই filter এ কোনো ব্যবহারকারী নেই" />} columns={[
      { key: "user", label: "ব্যবহারকারী", primary: true, render: (u) => <div><strong>{u.display_name || "নাম দেওয়া হয়নি"}</strong><div className="muted">{u.email}</div></div> },
      { key: "memberships", label: "ব্যবসা", align: "right", render: (u) => u.membership_count },
      { key: "mfa", label: "MFA", render: (u) => <Badge tone={u.mfa_enabled ? "success" : "warn"}>{u.mfa_enabled ? "চালু" : "চালু নয়"}</Badge> },
      { key: "status", label: "অবস্থা", render: (u) => <Badge tone={u.active ? "success" : "danger"}>{u.active ? "সক্রিয়" : "নিষ্ক্রিয়"}</Badge> },
      { key: "action", label: "", render: (u) => <div className="platform-table-actions"><Button size="sm" variant="secondary" onClick={() => setOpenUserId(u.id)}>বিস্তারিত</Button><Button size="sm" variant={u.active ? "danger" : "secondary"} loading={busyId === u.id} onClick={() => setAccess(u)}>{u.active ? "নিষ্ক্রিয়" : "সক্রিয়"}</Button></div> },
    ]} />
    {total > 50 && <div className="platform-pagination"><Button size="sm" variant="secondary" disabled={page === 1} onClick={() => { setUsers(null); setPage((value) => value - 1); }}>আগের পাতা</Button><span>পৃষ্ঠা {bnNumber(page)} · মোট {bnNumber(total)}</span><Button size="sm" variant="secondary" disabled={!hasNext} onClick={() => { setUsers(null); setPage((value) => value + 1); }}>পরের পাতা</Button></div>}
    {openUserId && <PlatformUserModal userId={openUserId} onClose={() => setOpenUserId("")} onOpenOrg={(id) => { setOpenUserId(""); onOpenOrg(id); }} />}
    {confirm.dialog}
  </Card>;
}

export default function PlatformPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedTab = searchParams.get("tab") || "overview";
  const tab = PLATFORM_TABS.has(requestedTab) ? requestedTab : "overview";
  const setTab = useCallback((nextTab) => {
    const next = new URLSearchParams(searchParams);
    if (nextTab === "overview") next.delete("tab");
    else next.set("tab", nextTab);
    setSearchParams(next);
  }, [searchParams, setSearchParams]);
  const [summary, setSummary] = useState(null);
  const [orgs, setOrgs] = useState(null);
  const [error, setError] = useState("");
  const [openOrgId, setOpenOrgId] = useState(null);
  const [search, setSearch] = useState("");
  const [orgStatus, setOrgStatus] = useState("all");
  const [orgSector, setOrgSector] = useState("all");
  const [globalQuery, setGlobalQuery] = useState("");
  const [globalUsers, setGlobalUsers] = useState([]);
  const [globalOpenUserId, setGlobalOpenUserId] = useState("");
  const [lastUpdated, setLastUpdated] = useState(null);

  const load = useCallback(() => {
    Promise.all([api.platformSummary(), api.platformOrganizations()])
      .then(([s, o]) => { setSummary(s); setOrgs(o.organizations); setLastUpdated(new Date()); setError(""); })
      .catch((e) => setError(explain(e)));
  }, []);
  useEffect(() => {
    load();
    const timer = window.setInterval(load, 60000);
    return () => window.clearInterval(timer);
  }, [load]);

  const filteredOrgs = useMemo(() => {
    if (!orgs) return orgs;
    const q = search.trim().toLowerCase();
    return orgs.filter((o) => {
      const matchesQuery = !q || o.name.toLowerCase().includes(q) || o.slug.toLowerCase().includes(q) || o.sector.toLowerCase().includes(q);
      const matchesStatus = orgStatus === "all" || (orgStatus === "active" && o.active && !o.suspended_at) || (orgStatus === "suspended" && o.suspended_at) || (orgStatus === "inactive" && !o.active);
      return matchesQuery && matchesStatus && (orgSector === "all" || o.sector === orgSector);
    });
  }, [orgs, search, orgStatus, orgSector]);
  const sectors = useMemo(() => [...new Set((orgs || []).map((org) => org.sector))].sort(), [orgs]);
  const globalOrgResults = useMemo(() => {
    const q = globalQuery.trim().toLowerCase();
    if (q.length < 2) return [];
    return (orgs || []).filter((org) => org.name.toLowerCase().includes(q) || org.slug.toLowerCase().includes(q)).slice(0, 5);
  }, [globalQuery, orgs]);
  useEffect(() => {
    if (globalQuery.trim().length < 2) { setGlobalUsers([]); return; }
    const timer = window.setTimeout(() => api.platformUsers(globalQuery).then((result) => setGlobalUsers(result.users.slice(0, 5))).catch(() => setGlobalUsers([])), 250);
    return () => window.clearTimeout(timer);
  }, [globalQuery]);

  return (
    <div className="platform-layout">
      <nav className="platform-sidenav" aria-label="প্ল্যাটফর্ম বিভাগ">
        {PLATFORM_NAV_GROUPS.map((group) => (
          <div className="platform-nav-group" key={group.label}>
            <strong>{group.label}</strong>
            {group.items.map((n) => (
              <button key={n.value} type="button" className={tab === n.value ? "active" : ""} aria-current={tab === n.value ? "page" : undefined} onClick={() => setTab(n.value)}>
                <Icon name={n.icon} size={17} /><span>{n.label}</span>
              </button>
            ))}
          </div>
        ))}
      </nav>

      <div className="platform-content stack">
        <section className={`platform-command-head${tab === "overview" ? "" : " compact"}`}>
          <div><span>CONTROL CENTER</span><h1>{PLATFORM_NAV.find((n) => n.value === tab)?.label || "প্ল্যাটফর্ম"}</h1><p>{TAB_DESCRIPTIONS[tab] || "Platform operation একটি live command center থেকে পরিচালনা করুন।"}</p></div>
          <div className="platform-command-tools">
            <div className="platform-global-search">
              <Icon name="search" size={17} />
              <input value={globalQuery} onChange={(e) => setGlobalQuery(e.target.value)} onKeyDown={(e) => { if (e.key === "Escape") { setGlobalQuery(""); e.currentTarget.blur(); } }} placeholder="Business বা user খুঁজুন" aria-label="সব business ও user খুঁজুন" aria-expanded={globalQuery.trim().length >= 2} aria-controls="platform-search-results" />
              {globalQuery.trim().length >= 2 && <div className="platform-search-results" id="platform-search-results" role="region" aria-live="polite" aria-label="Search results">
                {globalOrgResults.map((org) => <button type="button" key={org.id} onClick={() => { setOpenOrgId(org.id); setGlobalQuery(""); }}><Icon name="users" size={16} /><div><strong>{org.name}</strong><small>Business · {org.slug}</small></div></button>)}
                {globalUsers.map((user) => <button type="button" key={user.id} onClick={() => { setGlobalOpenUserId(user.id); setGlobalQuery(""); }}><Icon name="userCheck" size={16} /><div><strong>{user.display_name || user.email}</strong><small>User · {user.email}</small></div></button>)}
                {globalOrgResults.length === 0 && globalUsers.length === 0 && <p>কোনো result পাওয়া যায়নি</p>}
              </div>}
            </div>
            <button type="button" className="platform-live" onClick={load} aria-label="ডেটা refresh করুন"><i /><span>লাইভ ডেটা</span><small>{summary ? `${summary.organizations_active}টি সক্রিয় ব্যবসা · ${lastUpdated?.toLocaleTimeString("bn-BD", { hour: "2-digit", minute: "2-digit" }) || "এখন"}` : "সংযোগ হচ্ছে"}</small></button>
          </div>
        </section>
        {error && <Notice tone="danger">{error}</Notice>}

        {tab === "overview" && (!summary ? <Skeleton lines={2} height={60} /> : (
          <div className="platform-metrics">
            <Stat icon="users" label="মোট ব্যবসা" value={summary.organizations_total} />
            <Stat icon="check" label="সক্রিয় ব্যবসা" value={summary.organizations_active} />
            <Stat icon="userCheck" label="মোট ব্যবহারকারী" value={summary.users_total} />
            <Stat icon="cart" label="মোট বিক্রির চালান" value={summary.sales_orders_total} />
          </div>
        ))}

        {tab === "overview" && (
          <>
            <Notice tone="info" title="অ্যাডমিনের কাজের অগ্রাধিকার">
              আগে নিষ্ক্রিয় ব্যবসাগুলো দেখুন, তারপর tenant details থেকে সাপোর্ট, module access অথবা suspension সিদ্ধান্ত নিন। প্রতিটি গুরুত্বপূর্ণ action audit history তে লেখা থাকবে।
            </Notice>
            <OperationsQueue onNavigate={setTab} />
            <TrendsCard />
            <StaleOrgsCard />
          </>
        )}

        {tab === "orgs" && (
          <>
            <div className="platform-filterbar">
              <Field label="Business খুঁজুন" hint={orgs ? `${filteredOrgs.length} / ${orgs.length} ব্যবসা দেখাচ্ছে` : undefined}><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="নাম, slug বা sector" /></Field>
              <Field label="Status"><select value={orgStatus} onChange={(e) => setOrgStatus(e.target.value)}><option value="all">সব status</option><option value="active">Active</option><option value="suspended">Suspended</option><option value="inactive">Inactive</option></select></Field>
              <Field label="Sector"><select value={orgSector} onChange={(e) => setOrgSector(e.target.value)}><option value="all">সব sector</option>{sectors.map((sector) => <option value={sector} key={sector}>{sector}</option>)}</select></Field>
            </div>
            <DataTable
            rowKey="id" loading={orgs === null} rows={filteredOrgs || []} caption="ব্যবসার তালিকা"
            empty={<EmptyState icon="search" title="কিছু পাওয়া যায়নি" hint="অন্য শব্দ দিয়ে খুঁজে দেখুন।" />}
            columns={[
              { key: "name", label: "ব্যবসা", primary: true, render: (o) => <div><strong>{o.name}</strong><div className="muted" style={{ fontSize: 12.5 }}>{o.slug} · {o.sector}</div></div> },
              { key: "active", label: "অবস্থা", render: (o) => (o.suspended_at ? <Badge tone="warn">স্থগিত</Badge> : o.active ? <Badge tone="success">সক্রিয়</Badge> : <Badge tone="neutral">বন্ধ</Badge>) },
              { key: "members", label: "সদস্য", align: "right", render: (o) => o.member_count },
              { key: "branches", label: "শাখা", align: "right", render: (o) => o.branch_count },
              { key: "products", label: "পণ্য", align: "right", render: (o) => o.product_count },
              { key: "last_sale", label: "শেষ বিক্রি", render: (o) => (o.last_sale_at ? dateBn(o.last_sale_at) : "কখনো না") },
              { key: "created", label: "তৈরি হয়েছে", render: (o) => dateBn(o.created_at) },
              { key: "actions", label: "", align: "right", render: (o) => <Button size="sm" variant="secondary" onClick={() => setOpenOrgId(o.id)}>বিস্তারিত</Button> },
            ]}
            />
          </>
        )}
        {tab === "onboarding" && <OnboardingPipeline onOpenOrg={setOpenOrgId} />}
        {tab === "users" && <UserDirectoryCard onOpenOrg={setOpenOrgId} />}
        {tab === "features" && <FeatureRolloutPanel onOpenOrg={setOpenOrgId} />}
        {tab === "security" && <SecurityCenter />}
        {tab === "administrators" && <AdministratorGovernance />}
        {tab === "system" && <SystemHealthPanel />}
        {tab === "delivery" && <IntegrationOperations onOpenOrg={setOpenOrgId} />}
        {tab === "announcements" && <AnnouncementCenter />}
        {tab === "site" && (<><SiteContentCard /><AdvancedContentCard /></>)}
        {tab === "backups" && <BackupsCard />}
        {tab === "audit" && <AuditLogCard />}

        {/* ── New 50-capability admin tabs ── */}
        {tab === "cmd_overview" && <AdminOverviewPanel />}
        {tab === "cmd_search" && <UniversalSearchPanel />}
        {tab === "cmd_mission" && <MissionQueuePanel />}
        {tab === "cmd_handover" && <ShiftHandoverPanel />}
        {tab === "cmd_journal" && <DecisionJournalPanel />}
        {tab === "lc_state" && <TenantStateMachinePanel />}
        {tab === "lc_health" && <TenantHealthPanel />}
        {tab === "lc_churn" && <ChurnRiskPanel />}
        {tab === "rev_plans" && <PlansPanel />}
        {tab === "rev_billing" && <BillingLedgerPanel />}
        {tab === "rev_usage" && <UsageMeteringPanel />}
        {tab === "rev_reconcile" && <ReconciliationPanel />}
        {tab === "sup_cases" && <SupportCasesPanel />}
        {tab === "sup_sessions" && <SupportSessionsPanel />}
        {tab === "sup_sla" && <SlaSummaryPanel />}
        {tab === "sec_alerts" && <SecurityAlertsPanel />}
        {tab === "sec_jit" && <JitAccessPanel />}
        {tab === "sec_cert" && <AccessCertificationPanel />}
        {tab === "sec_emergency" && <EmergencyContainmentPanel />}
        {tab === "rel_incidents" && <IncidentPanel />}
        {tab === "rel_jobs" && <JobConsolePanel />}
        {tab === "rel_rollout" && <RolloutPanel />}
        {tab === "rel_config" && <ConfigVersionPanel />}
        {tab === "rel_providers" && <ProviderCredentialPanel />}
        {tab === "rel_webhooks" && <WebhookInboxPanel />}
        {tab === "rel_intcert" && <IntegrationCertPanel />}
        {tab === "gov_inventory" && <DataInventoryPanel />}
        {tab === "gov_exports" && <DataExportsPanel />}
        {tab === "gov_retention" && <RetentionPoliciesPanel />}
        {tab === "gov_privacy" && <PrivacyRequestsPanel />}
        {tab === "ai_registry" && <ModelRegistryPanel />}
        {tab === "ai_budgets" && <AiBudgetPanel />}
        {tab === "ai_outcomes" && <AiOutcomesPanel />}
        {tab === "ai_killswitch" && <AiKillSwitchPanel />}

        {openOrgId && <OrgDetailModal orgId={openOrgId} onClose={() => setOpenOrgId(null)} onChanged={load} />}
        {globalOpenUserId && <PlatformUserModal userId={globalOpenUserId} onClose={() => setGlobalOpenUserId("")} onOpenOrg={(id) => { setGlobalOpenUserId(""); setOpenOrgId(id); }} />}
      </div>
    </div>
  );
}

// ════════════════════════════════════════════════════════════════════════════
// ADMIN PANEL SHARED UTILITIES
// ════════════════════════════════════════════════════════════════════════════

function useAdminFetch(fn, deps = []) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = useCallback(() => {
    setLoading(true);
    fn().then(setData).catch((e) => setError(e?.message || "Error")).finally(() => setLoading(false));
  }, deps); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, [load]);
  return { data, loading, error, reload: load };
}

// Live SLA countdown — re-renders every 10s
function useSlaCountdown(dueAt) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 10_000);
    return () => clearInterval(id);
  }, []);
  if (!dueAt) return null;
  return new Date(dueAt).getTime() - now;
}

function SlaTimer({ dueAt, small }) {
  const diff = useSlaCountdown(dueAt);
  if (diff === null) return null;
  const breached = diff <= 0;
  const abs = Math.abs(diff);
  const h = Math.floor(abs / 3600000);
  const m = Math.floor((abs % 3600000) / 60000);
  const color = breached ? "#E63946" : diff < 3_600_000 ? "#f59e0b" : "#0A8754";
  const txt = breached ? `+${h}h ${m}m breached` : h > 0 ? `${h}h ${m}m left` : `${m}m left`;
  return <span style={{ color, fontWeight: 700, fontSize: small ? 11 : 13 }}>{txt}</span>;
}

function SlaBar({ createdAt, dueAt }) {
  const total = new Date(dueAt) - new Date(createdAt);
  const elapsed = Date.now() - new Date(createdAt);
  const pct = Math.min(100, Math.max(0, (elapsed / total) * 100));
  const bg = pct > 90 ? "#E63946" : pct > 70 ? "#f59e0b" : "#0A8754";
  return (
    <div style={{ background: "var(--color-border, #e5e7eb)", borderRadius: 3, height: 5, width: "100%", overflow: "hidden" }}>
      <div style={{ width: `${pct}%`, height: "100%", background: bg, transition: "width 2s" }} />
    </div>
  );
}

// Vertical event timeline
function Timeline({ events, emptyText }) {
  if (!events?.length) return <p style={{ color: "var(--color-muted)", fontSize: 13 }}>{emptyText || "No events yet."}</p>;
  return (
    <div style={{ position: "relative", paddingLeft: 22 }}>
      <div style={{ position: "absolute", left: 7, top: 4, bottom: 4, width: 2, background: "var(--color-border, #e5e7eb)" }} />
      {events.map((e, i) => (
        <div key={e.id || i} style={{ position: "relative", marginBottom: 14 }}>
          <div style={{
            position: "absolute", left: -19, top: 3, width: 10, height: 10,
            borderRadius: "50%", background: "var(--color-primary, #0D1B2A)",
            border: "2px solid var(--color-bg, white)",
          }} />
          <div style={{ fontSize: 11, color: "var(--color-muted)", marginBottom: 2 }}>
            {dateTimeBn(e.created_at)}
            {e.event_type && <Badge tone="info" style={{ marginLeft: 6, fontSize: 10 }}>{e.event_type.replace(/_/g, " ")}</Badge>}
          </div>
          <div style={{ fontSize: 13, lineHeight: 1.4 }}>{e.body || e.message || e.description}</div>
        </div>
      ))}
    </div>
  );
}

// Rollout stage pipeline bar
const ROLLOUT_STAGES = ["internal", "pilot", "5pct", "20pct", "50pct", "all"];
const STAGE_LBL = { internal: "Internal", pilot: "Pilot", "5pct": "5%", "20pct": "20%", "50pct": "50%", all: "All" };
function StagePipeline({ currentStage }) {
  const ci = ROLLOUT_STAGES.indexOf(currentStage);
  return (
    <div style={{ display: "flex", alignItems: "center" }}>
      {ROLLOUT_STAGES.map((s, i) => {
        const done = i < ci; const cur = i === ci;
        return (
          <div key={s} style={{ display: "flex", alignItems: "center" }}>
            <div style={{
              padding: "3px 9px", borderRadius: 4, fontSize: 11, fontWeight: cur ? 700 : 400,
              background: done ? "#0A8754" : cur ? "#0D1B2A" : "var(--color-border, #e5e7eb)",
              color: (done || cur) ? "white" : "var(--color-muted)",
              outline: cur ? "2px solid #0A8754" : "none", outlineOffset: 2,
            }}>{STAGE_LBL[s]}</div>
            {i < ROLLOUT_STAGES.length - 1 && (
              <div style={{ width: 14, height: 2, background: done ? "#0A8754" : "var(--color-border, #e5e7eb)" }} />
            )}
          </div>
        );
      })}
    </div>
  );
}

// Health score ring — colored number
function HealthScore({ score, risk }) {
  const color = risk === "high" ? "#E63946" : risk === "medium" ? "#f59e0b" : "#0A8754";
  return (
    <div style={{
      width: 56, height: 56, borderRadius: "50%",
      border: `4px solid ${color}`, display: "flex", alignItems: "center",
      justifyContent: "center", flexShrink: 0,
    }}>
      <span style={{ fontSize: 18, fontWeight: 800, color }}>{score}</span>
    </div>
  );
}

function priorityColor(p) {
  return p >= 70 ? "#E63946" : p >= 40 ? "#f59e0b" : "#64748B";
}

function PriorityPill({ priority }) {
  const c = priorityColor(priority);
  return <span style={{ background: c + "22", color: c, borderRadius: 12, padding: "1px 8px", fontSize: 11, fontWeight: 700 }}>P{priority}</span>;
}

// Mini inline stat
function KpiCard({ label, value, sub, color }) {
  return (
    <Card style={{ padding: "12px 16px", flex: 1, minWidth: 0 }}>
      <div style={{ fontSize: 26, fontWeight: 800, color: color || "var(--color-text)" }}>{value}</div>
      <div style={{ fontSize: 12, fontWeight: 600, color: "var(--color-muted)" }}>{label}</div>
      {sub && <div style={{ fontSize: 11, color: "var(--color-muted)", marginTop: 2 }}>{sub}</div>}
    </Card>
  );
}

// ── Admin Overview ────────────────────────────────────────────────────────────
function AdminOverviewPanel() {
  const { data, loading, error, reload } = useAdminFetch(() => api.adminOverview());
  const { data: missions } = useAdminFetch(() => api.adminMissionQueue("open"));
  const { data: alerts } = useAdminFetch(() => api.adminSecurityAlerts("open"));
  const { data: incidents } = useAdminFetch(() => api.adminIncidents("open"));
  const toast = useToast();

  async function generateMissions() {
    try {
      const r = await api.adminGenerateMissionQueue();
      toast.success(r.message);
      reload();
    } catch (e) { toast.error(e?.message || "Error"); }
  }

  if (loading) return <Skeleton lines={6} />;
  if (error) return <Notice tone="danger">{error}</Notice>;

  const topMissions = (missions?.items || []).slice(0, 5);
  const topAlerts = (alerts?.alerts || []).slice(0, 4);
  const openIncidents = (incidents?.incidents || []).filter(i => i.severity === "p1" || i.severity === "p2");

  return (
    <div className="stack" style={{ gap: 16 }}>
      {/* P1/P2 incidents banner */}
      {openIncidents.map(inc => (
        <Notice key={inc.id} tone="danger">
          🚨 <strong>{inc.severity.toUpperCase()} Incident:</strong> {inc.title} — {inc.affected_org_count ?? 0} tenants affected
        </Notice>
      ))}
      {data?.ai_kill_switches?.disabled_count > 0 && (
        <Notice tone="warning">⚠ {data.ai_kill_switches.disabled_count}টি AI feature kill switch active</Notice>
      )}

      {/* KPI row */}
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        <KpiCard label="Open Missions" value={data?.mission_queue?.open ?? 0} color={data?.mission_queue?.open > 0 ? "#f59e0b" : "#0A8754"} />
        <KpiCard label="Support Cases" value={data?.support?.open_cases ?? 0} sub={data?.support?.breached_sla > 0 ? `${data.support.breached_sla} SLA breached` : "All on time"} color={data?.support?.breached_sla > 0 ? "#E63946" : undefined} />
        <KpiCard label="Open Incidents" value={data?.incidents?.open ?? 0} color={data?.incidents?.open > 0 ? "#E63946" : "#0A8754"} />
        <KpiCard label="Security Alerts" value={data?.security?.open_alerts ?? 0} color={data?.security?.open_alerts > 0 ? "#E63946" : "#0A8754"} />
        <KpiCard label="High Churn Risk" value={data?.churn_risk?.high ?? 0} color={data?.churn_risk?.high > 0 ? "#f59e0b" : "#0A8754"} />
        <KpiCard label="Failed Jobs" value={data?.jobs?.failed ?? 0} color={data?.jobs?.failed > 0 ? "#E63946" : "#0A8754"} />
        <KpiCard label="Active JIT Grants" value={data?.jit_access?.active ?? 0} />
        <KpiCard label="Privacy Requests" value={data?.privacy_requests?.pending ?? 0} color={data?.privacy_requests?.pending > 0 ? "#f59e0b" : undefined} />
      </div>

      {/* Two-column: missions + alerts */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
        {/* Mission queue */}
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <strong>Priority Missions</strong>
            <Button size="sm" variant="ghost" onClick={generateMissions}>⟳ Generate</Button>
          </div>
          <div className="stack" style={{ gap: 6 }}>
            {topMissions.length === 0 && <EmptyState icon="check" title="কোনো mission নেই" />}
            {topMissions.map(m => (
              <div key={m.id} style={{
                borderLeft: `4px solid ${priorityColor(m.priority)}`,
                padding: "8px 10px", background: "var(--color-surface)", borderRadius: "0 6px 6px 0",
              }}>
                <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                  <PriorityPill priority={m.priority} />
                  {m.affected_org_name && <Badge tone="info" style={{ fontSize: 10 }}>{m.affected_org_name}</Badge>}
                </div>
                <div style={{ fontSize: 13, fontWeight: 600, marginTop: 3 }}>{m.title}</div>
                {m.recommended_action && <div style={{ fontSize: 11, color: "var(--color-muted)", marginTop: 2 }}>→ {m.recommended_action}</div>}
              </div>
            ))}
          </div>
        </div>

        {/* Security alert feed */}
        <div>
          <strong>Security Alert Feed</strong>
          <div className="stack" style={{ gap: 6, marginTop: 8 }}>
            {topAlerts.length === 0 && <EmptyState icon="shield" title="কোনো alert নেই" />}
            {topAlerts.map(a => (
              <div key={a.id} style={{
                display: "flex", gap: 8, alignItems: "flex-start",
                padding: "8px 10px", background: "var(--color-surface)", borderRadius: 6,
                borderLeft: `4px solid ${a.severity === "critical" || a.severity === "high" ? "#E63946" : "#f59e0b"}`,
              }}>
                <div style={{ flex: 1 }}>
                  <Badge tone={a.severity === "critical" ? "danger" : "warning"} style={{ fontSize: 10 }}>{a.severity}</Badge>
                  <div style={{ fontSize: 12, fontWeight: 600, marginTop: 2 }}>{a.alert_type?.replace(/_/g, " ")}</div>
                  {a.org_name && <div style={{ fontSize: 11, color: "var(--color-muted)" }}>{a.org_name}</div>}
                </div>
                <div style={{ fontSize: 11, color: "var(--color-muted)", flexShrink: 0 }}>{dateBn(a.created_at)}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Universal Search ──────────────────────────────────────────────────────────
function UniversalSearchPanel() {
  const [q, setQ] = useState("");
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const toast = useToast();

  async function doSearch(e) {
    e.preventDefault();
    if (q.trim().length < 2) return;
    setLoading(true);
    try {
      const r = await api.adminSearch(q.trim());
      setResults(r);
    } catch (err) { toast.error(err?.message || "Error"); } finally { setLoading(false); }
  }

  return (
    <div className="stack">
      <h3>Universal Command Search</h3>
      <form onSubmit={doSearch} style={{ display: "flex", gap: 8 }}>
        <input className="field-input" style={{ flex: 1 }} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Tenant, user, case, incident..." />
        <Button type="submit" loading={loading}>খুঁজুন</Button>
      </form>
      {results && (
        <div className="stack">
          <p>{results.count}টি ফলাফল পাওয়া গেছে।</p>
          {results.results.map((r) => (
            <Card key={r.id} style={{ padding: "8px 12px", display: "flex", gap: 12, alignItems: "center" }}>
              <Badge tone={r.type === "organization" ? "info" : r.type === "user" ? "success" : "warning"}>{r.type}</Badge>
              <span><strong>{r.label}</strong> — {r.sub}</span>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Mission Queue ─────────────────────────────────────────────────────────────
function MissionQueuePanel() {
  const [statusTab, setStatusTab] = useState("open");
  const { data, loading, reload } = useAdminFetch(() => api.adminMissionQueue(statusTab), [statusTab]);
  const [expanded, setExpanded] = useState(null);
  const [addOpen, setAddOpen] = useState(false);
  const [form, setForm] = useState({ kind: "manual", priority: 50, title: "", description: "", recommended_action: "" });
  const toast = useToast();

  async function setStatus(id, s) {
    try {
      await api.adminUpdateMissionItem(id, { status: s });
      toast.success(`Mission → ${s}`);
      setExpanded(null); reload();
    } catch (e) { toast.error(e?.message || "Error"); }
  }

  async function generate() {
    try {
      const r = await api.adminGenerateMissionQueue();
      toast.success(r.message);
      reload();
    } catch (e) { toast.error(e?.message || "Error"); }
  }

  async function create() {
    try {
      await api.adminCreateMissionItem(form);
      toast.success("Mission তৈরি হয়েছে।");
      setAddOpen(false);
      setForm({ kind: "manual", priority: 50, title: "", description: "", recommended_action: "" });
      reload();
    } catch (e) { toast.error(e?.message || "Error"); }
  }

  if (loading) return <Skeleton lines={5} />;
  return (
    <div className="stack">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3>Admin Mission Queue</h3>
        <div style={{ display: "flex", gap: 6 }}>
          <Button size="sm" variant="ghost" onClick={generate}>⟳ Auto-Generate</Button>
          <Button size="sm" onClick={() => setAddOpen(true)}>+ Mission</Button>
        </div>
      </div>

      {/* Status tabs */}
      <div style={{ display: "flex", gap: 4, borderBottom: "1px solid var(--color-border)", paddingBottom: 8 }}>
        {["open", "in_progress", "resolved", "dismissed"].map(s => (
          <button key={s} onClick={() => setStatusTab(s)} style={{
            padding: "4px 12px", borderRadius: 20, border: "none", cursor: "pointer", fontSize: 12, fontWeight: 600,
            background: statusTab === s ? "#0D1B2A" : "transparent",
            color: statusTab === s ? "white" : "var(--color-muted)",
          }}>{s.replace("_", " ")}</button>
        ))}
        <Badge tone="warning" style={{ marginLeft: "auto" }}>{data?.count ?? 0}</Badge>
      </div>

      {data?.items?.length === 0 && <EmptyState icon="check" title="কোনো মিশন নেই" body="এই status এ কোনো item নেই।" />}

      {data?.items?.map(item => (
        <div key={item.id} style={{
          borderLeft: `4px solid ${priorityColor(item.priority)}`,
          background: "var(--color-surface)",
          borderRadius: "0 8px 8px 0",
          overflow: "hidden",
        }}>
          {/* Card header — always visible */}
          <div
            style={{ padding: "10px 14px", cursor: "pointer", display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}
            onClick={() => setExpanded(expanded === item.id ? null : item.id)}
          >
            <div style={{ flex: 1 }}>
              <div style={{ display: "flex", gap: 6, alignItems: "center", marginBottom: 4 }}>
                <PriorityPill priority={item.priority} />
                <Badge tone="neutral" style={{ fontSize: 10 }}>{item.kind.replace(/_/g, " ")}</Badge>
                {item.affected_org_name && <Badge tone="info" style={{ fontSize: 10 }}>{item.affected_org_name}</Badge>}
              </div>
              <div style={{ fontSize: 14, fontWeight: 600 }}>{item.title}</div>
            </div>
            <div style={{ display: "flex", gap: 6, alignItems: "center", flexShrink: 0 }}>
              {item.deadline_at && (
                <span style={{ fontSize: 11, color: new Date(item.deadline_at) < new Date() ? "#E63946" : "#f59e0b" }}>
                  ⏰ {dateBn(item.deadline_at)}
                </span>
              )}
              <Icon name={expanded === item.id ? "chevronUp" : "chevronDown"} size={14} />
            </div>
          </div>

          {/* Expanded detail */}
          {expanded === item.id && (
            <div style={{ padding: "0 14px 14px", borderTop: "1px solid var(--color-border)" }}>
              {item.description && <p style={{ fontSize: 13, marginTop: 10 }}>{item.description}</p>}
              {item.estimated_impact && (
                <div style={{ fontSize: 12, marginTop: 6 }}>
                  <strong>Impact:</strong> <span style={{ color: "var(--color-muted)" }}>{item.estimated_impact}</span>
                </div>
              )}
              {item.recommended_action && (
                <div style={{
                  background: "var(--color-primary, #0D1B2A)22",
                  borderRadius: 6, padding: "8px 12px", marginTop: 8,
                  fontSize: 13, fontStyle: "italic"
                }}>
                  → {item.recommended_action}
                </div>
              )}
              <div style={{ display: "flex", gap: 6, marginTop: 12 }}>
                {item.status === "open" && <Button size="sm" onClick={() => setStatus(item.id, "in_progress")}>Start Working</Button>}
                {item.status === "in_progress" && <Button size="sm" onClick={() => setStatus(item.id, "resolved")}>✓ Resolve</Button>}
                {item.status !== "resolved" && <Button size="sm" variant="ghost" onClick={() => setStatus(item.id, "dismissed")}>Dismiss</Button>}
              </div>
            </div>
          )}
        </div>
      ))}

      {addOpen && (
        <Modal title="নতুন Mission Item" onClose={() => setAddOpen(false)}>
          <div className="stack">
            <Field label="Title"><input className="field-input" value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} /></Field>
            <Field label="Description"><textarea className="field-input" rows={3} value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} /></Field>
            <Field label="Recommended Action"><input className="field-input" value={form.recommended_action} onChange={e => setForm(f => ({ ...f, recommended_action: e.target.value }))} /></Field>
            <Field label="Priority (1-100)">
              <input type="range" min={1} max={100} value={form.priority} onChange={e => setForm(f => ({ ...f, priority: parseInt(e.target.value) }))} style={{ width: "100%" }} />
              <PriorityPill priority={form.priority} />
            </Field>
            <Button onClick={create}>তৈরি করুন</Button>
          </div>
        </Modal>
      )}
    </div>
  );
}

// ── Shift Handover ────────────────────────────────────────────────────────────
function ShiftHandoverPanel() {
  const { data, loading, error, reload } = useAdminFetch(() => api.adminShiftHandovers());
  const [summary, setSummary] = useState("");
  const toast = useToast();

  async function create() {
    if (!summary.trim()) return;
    try {
      await api.adminCreateShiftHandover({ summary, open_incidents: 0, pending_approvals: 0 });
      toast.success("Handover তৈরি হয়েছে।");
      setSummary(""); reload();
    } catch (e) { toast.error(e?.message || "Error"); }
  }

  async function ack(id) {
    try {
      await api.adminAcknowledgeHandover(id);
      toast.success("Acknowledged.");
      reload();
    } catch (e) { toast.error(e?.message || "Error"); }
  }

  if (loading) return <Skeleton lines={3} />;
  return (
    <div className="stack">
      <h3>Shift Handover System</h3>
      <Card>
        <Field label="Handover Summary">
          <textarea className="field-input" rows={3} value={summary} onChange={(e) => setSummary(e.target.value)} placeholder="আজকের অসম্পন্ন কাজ, incidents, priority tenants..." />
        </Field>
        <Button onClick={create}>Handover তৈরি করুন</Button>
      </Card>
      {data?.handovers?.map((h) => (
        <Card key={h.id}>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <div>
              <p><strong>{h.from_admin}</strong> → {h.to_admin || "পরবর্তী অ্যাডমিন"}</p>
              <p style={{ fontSize: 13 }}>{h.summary}</p>
              <p style={{ fontSize: 12, color: "var(--color-muted)" }}>{dateTimeBn(h.created_at)}</p>
            </div>
            {!h.acknowledged_at
              ? <Button size="sm" onClick={() => ack(h.id)}>Acknowledge</Button>
              : <Badge tone="success">Acknowledged</Badge>
            }
          </div>
        </Card>
      ))}
    </div>
  );
}

// ── Decision Journal ──────────────────────────────────────────────────────────
function DecisionJournalPanel() {
  const { data, loading, error, reload } = useAdminFetch(() => api.adminDecisionJournal());
  const [form, setForm] = useState({ action_kind: "", decision_reason: "", expected_outcome: "" });
  const toast = useToast();

  async function save() {
    try {
      await api.adminCreateDecision(form);
      toast.success("Decision লিপিবদ্ধ হয়েছে।");
      setForm({ action_kind: "", decision_reason: "", expected_outcome: "" });
      reload();
    } catch (e) { toast.error(e?.message || "Error"); }
  }

  if (loading) return <Skeleton lines={3} />;
  return (
    <div className="stack">
      <h3>Decision Journal</h3>
      <Card>
        <Field label="Action Kind"><input className="field-input" value={form.action_kind} onChange={(e) => setForm((f) => ({ ...f, action_kind: e.target.value }))} placeholder="e.g. tenant_suspension" /></Field>
        <Field label="সিদ্ধান্তের কারণ"><textarea className="field-input" rows={3} value={form.decision_reason} onChange={(e) => setForm((f) => ({ ...f, decision_reason: e.target.value }))} /></Field>
        <Field label="প্রত্যাশিত ফলাফল"><input className="field-input" value={form.expected_outcome} onChange={(e) => setForm((f) => ({ ...f, expected_outcome: e.target.value }))} /></Field>
        <Button onClick={save}>সংরক্ষণ করুন</Button>
      </Card>
      <DataTable
        rows={data?.entries || []}
        columns={[
          { key: "action_kind", label: "Action" },
          { key: "actor", label: "Actor" },
          { key: "decision_reason", label: "কারণ" },
          { key: "created_at", label: "সময়", render: (v) => dateBn(v) },
        ]}
      />
    </div>
  );
}

// ── Tenant State Machine ──────────────────────────────────────────────────────
const LIFECYCLE_STATES = ["lead", "trial", "onboarding", "live", "at_risk", "grace_period", "suspended", "offboarded"];
const STATE_CFG = {
  lead: { color: "#64748B", icon: "👤", label: "Lead" },
  trial: { color: "#0D1B2A", icon: "🔬", label: "Trial" },
  onboarding: { color: "#f59e0b", icon: "⚙", label: "Onboarding" },
  live: { color: "#0A8754", icon: "✅", label: "Live" },
  at_risk: { color: "#eab308", icon: "⚠", label: "At Risk" },
  grace_period: { color: "#f97316", icon: "⏰", label: "Grace Period" },
  suspended: { color: "#E63946", icon: "🚫", label: "Suspended" },
  offboarded: { color: "#94a3b8", icon: "🏁", label: "Offboarded" },
};
const VALID_TRANSITIONS = {
  lead: ["trial"],
  trial: ["onboarding", "offboarded"],
  onboarding: ["live", "suspended", "offboarded"],
  live: ["at_risk", "suspended", "offboarded"],
  at_risk: ["live", "grace_period", "suspended"],
  grace_period: ["live", "suspended"],
  suspended: ["live", "offboarded"],
  offboarded: [],
};

function TenantStateMachinePanel() {
  const { data: orgsData } = useAdminFetch(() => api.platformOrganizations());
  const [selectedOrg, setSelectedOrg] = useState("");
  const [history, setHistory] = useState(null);
  const [toState, setToState] = useState("");
  const [reason, setReason] = useState("");
  const toast = useToast();
  const confirm = useConfirm();

  async function loadHistory(orgId) {
    setSelectedOrg(orgId);
    setHistory(null);
    if (!orgId) return;
    try {
      const h = await api.adminTenantStateHistory(orgId);
      setHistory(h);
    } catch {}
  }

  async function doTransition() {
    if (!toState || !reason.trim()) return;
    if (!await confirm(`"${selectedOrgName}" → ${STATE_CFG[toState]?.label}?\n\nReason: ${reason}`)) return;
    try {
      await api.adminTransitionTenantState(selectedOrg, { to_state: toState, reason });
      toast.success(`State → ${toState}`);
      setToState(""); setReason("");
      await loadHistory(selectedOrg);
    } catch (e) { toast.error(e?.message || "Error"); }
  }

  const orgs = orgsData?.organizations || [];
  const selectedOrgName = orgs.find(o => o.id === selectedOrg)?.name;
  const currentState = history?.events?.length > 0 ? history.events[history.events.length - 1]?.to_state : "lead";
  const validNextStates = VALID_TRANSITIONS[currentState] || [];

  return (
    <div className="stack">
      <h3>Tenant Lifecycle State Machine</h3>
      <Field label="Business বেছে নিন">
        <select className="field-input" value={selectedOrg} onChange={e => loadHistory(e.target.value)}>
          <option value="">-- বেছে নিন --</option>
          {orgs.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
        </select>
      </Field>

      {selectedOrg && history && (
        <>
          {/* Current state badge */}
          <Card style={{ padding: "14px 16px" }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: "var(--color-muted)", marginBottom: 8 }}>CURRENT STATE</div>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div style={{
                fontSize: 32, width: 56, height: 56, borderRadius: "50%",
                border: `3px solid ${STATE_CFG[currentState]?.color || "#64748B"}`,
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>
                {STATE_CFG[currentState]?.icon}
              </div>
              <div>
                <div style={{ fontWeight: 700, fontSize: 18, color: STATE_CFG[currentState]?.color }}>{STATE_CFG[currentState]?.label}</div>
                <div style={{ fontSize: 12, color: "var(--color-muted)" }}>{selectedOrgName}</div>
              </div>
            </div>
          </Card>

          {/* State flow visualization */}
          <Card style={{ padding: "12px 16px" }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: "var(--color-muted)", marginBottom: 8 }}>LIFECYCLE FLOW</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {LIFECYCLE_STATES.map(s => {
                const cfg = STATE_CFG[s];
                const isCurrent = s === currentState;
                const isPast = history.events.some(e => e.to_state === s);
                const isValidNext = validNextStates.includes(s);
                return (
                  <div key={s} style={{
                    padding: "6px 12px", borderRadius: 20, fontSize: 12, fontWeight: isCurrent ? 700 : 400,
                    background: isCurrent ? cfg.color : isPast ? cfg.color + "33" : "var(--color-border)",
                    color: isCurrent ? "white" : isPast ? cfg.color : "var(--color-muted)",
                    border: isValidNext ? `2px dashed ${cfg.color}` : "2px solid transparent",
                    cursor: isValidNext ? "pointer" : "default",
                    transform: isCurrent ? "scale(1.05)" : "scale(1)",
                  }} onClick={() => isValidNext && setToState(s)}>
                    {cfg.icon} {cfg.label}
                  </div>
                );
              })}
            </div>
            <div style={{ fontSize: 11, color: "var(--color-muted)", marginTop: 6 }}>Dashed border = valid next state (click to select)</div>
          </Card>

          {/* Transition form */}
          {validNextStates.length > 0 && (
            <Card style={{ padding: "12px 16px" }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: "var(--color-muted)", marginBottom: 8 }}>TRANSITION</div>
              <Field label="New State">
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  {validNextStates.map(s => (
                    <button key={s} onClick={() => setToState(toState === s ? "" : s)} style={{
                      padding: "6px 14px", borderRadius: 20, border: `2px solid ${STATE_CFG[s]?.color}`,
                      background: toState === s ? STATE_CFG[s]?.color : "transparent",
                      color: toState === s ? "white" : STATE_CFG[s]?.color,
                      cursor: "pointer", fontWeight: 600, fontSize: 13,
                    }}>
                      {STATE_CFG[s]?.icon} {STATE_CFG[s]?.label}
                    </button>
                  ))}
                </div>
              </Field>
              {toState && (
                <>
                  <Field label="Reason">
                    <textarea className="field-input" rows={2} value={reason} onChange={e => setReason(e.target.value)} placeholder={`কেন ${STATE_CFG[toState]?.label} state এ নিচ্ছেন...`} />
                  </Field>
                  <Button onClick={doTransition} disabled={!reason.trim()} variant={toState === "suspended" || toState === "offboarded" ? "danger" : "primary"}>
                    Transition → {STATE_CFG[toState]?.label}
                  </Button>
                </>
              )}
            </Card>
          )}

          {/* Transition history */}
          <div>
            <div style={{ fontSize: 12, fontWeight: 700, color: "var(--color-muted)", marginBottom: 6 }}>HISTORY</div>
            <Timeline events={history.events?.map(e => ({
              ...e, body: `→ ${STATE_CFG[e.to_state]?.label || e.to_state}${e.reason ? ` — ${e.reason}` : ""}`,
            }))} emptyText="No state changes recorded." />
          </div>
        </>
      )}
    </div>
  );
}

// ── Tenant Health Score ───────────────────────────────────────────────────────
function TenantHealthPanel() {
  const { data: orgs, loading: orgsLoading } = useAdminFetch(() => api.platformOrganizations());
  const [scores, setScores] = useState({}); // orgId → health data
  const [loadingOrg, setLoadingOrg] = useState(null);
  const [expanded, setExpanded] = useState(null);
  const [sortBy, setSortBy] = useState("score"); // score | name
  const toast = useToast();

  async function loadAll() {
    if (!orgs?.organizations) return;
    for (const org of orgs.organizations.slice(0, 20)) {
      setLoadingOrg(org.id);
      try {
        const h = await api.adminTenantHealthScore(org.id);
        setScores(s => ({ ...s, [org.id]: { ...h, org_name: org.name, org_id: org.id } }));
      } catch {}
    }
    setLoadingOrg(null);
  }

  const orgList = orgs?.organizations || [];
  const scored = orgList.map(o => scores[o.id] || { org_id: o.id, org_name: o.name, score: null }).filter(x => x.score !== null);
  const sorted = [...scored].sort((a, b) => sortBy === "score" ? a.score - b.score : a.org_name.localeCompare(b.org_name));

  if (orgsLoading) return <Skeleton lines={4} />;
  return (
    <div className="stack">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3>Tenant Health Matrix</h3>
        <div style={{ display: "flex", gap: 6 }}>
          <Button size="sm" variant="ghost" onClick={() => setSortBy(sortBy === "score" ? "name" : "score")}>
            Sort: {sortBy === "score" ? "↑ Worst first" : "A-Z"}
          </Button>
          <Button size="sm" onClick={loadAll} disabled={!!loadingOrg}>
            {loadingOrg ? "Loading..." : "Load All Scores"}
          </Button>
        </div>
      </div>

      {scored.length === 0 && (
        <EmptyState icon="activity" title="Score লোড করুন" body="'Load All Scores' click করে সব tenant এর health score দেখুন।" />
      )}

      {/* Health summary bar */}
      {scored.length > 0 && (
        <div style={{ display: "flex", gap: 8 }}>
          <KpiCard label="High Risk" value={scored.filter(s => s.risk_level === "high").length} color="#E63946" />
          <KpiCard label="Medium Risk" value={scored.filter(s => s.risk_level === "medium").length} color="#f59e0b" />
          <KpiCard label="Low Risk" value={scored.filter(s => s.risk_level === "low").length} color="#0A8754" />
          <KpiCard label="Avg Score" value={Math.round(scored.reduce((a, b) => a + (b.score || 0), 0) / scored.length)} />
        </div>
      )}

      {/* Health grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 10 }}>
        {sorted.map(h => (
          <div key={h.org_id} style={{
            background: "var(--color-surface)", borderRadius: 8, padding: "12px 14px",
            border: `1px solid ${h.risk_level === "high" ? "#E6394644" : h.risk_level === "medium" ? "#f59e0b44" : "var(--color-border)"}`,
            cursor: "pointer",
          }} onClick={() => setExpanded(expanded === h.org_id ? null : h.org_id)}>
            <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
              <HealthScore score={h.score} risk={h.risk_level} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 600, fontSize: 13, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{h.org_name}</div>
                <Badge tone={h.risk_level === "high" ? "danger" : h.risk_level === "medium" ? "warning" : "success"} style={{ marginTop: 4 }}>
                  {h.risk_level?.toUpperCase()} RISK
                </Badge>
              </div>
            </div>

            {/* Factor mini bars */}
            {expanded === h.org_id && h.factors && (
              <div style={{ marginTop: 10, borderTop: "1px solid var(--color-border)", paddingTop: 8 }}>
                {Object.entries(h.factors).map(([k, v]) => (
                  <div key={k} style={{ marginBottom: 5 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, marginBottom: 2 }}>
                      <span>{k.replace(/_/g, " ")}</span>
                      <span style={{ fontWeight: 700, color: v < 0 ? "#E63946" : "#0A8754" }}>{v > 0 ? "+" : ""}{v}</span>
                    </div>
                    <div style={{ background: "var(--color-border)", borderRadius: 3, height: 4, overflow: "hidden" }}>
                      <div style={{
                        width: `${Math.min(100, Math.abs(v) * 10)}%`, height: "100%",
                        background: v < 0 ? "#E63946" : "#0A8754",
                      }} />
                    </div>
                  </div>
                ))}
                {h.recommendation && (
                  <div style={{ marginTop: 8, fontSize: 12, fontStyle: "italic", color: "var(--color-muted)", borderTop: "1px solid var(--color-border)", paddingTop: 6 }}>
                    💡 {h.recommendation}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}

        {/* Unloaded orgs */}
        {orgList.filter(o => !scores[o.id]).map(o => (
          <div key={o.id} style={{
            background: "var(--color-surface)", borderRadius: 8, padding: "12px 14px",
            border: "1px solid var(--color-border)", opacity: 0.5,
          }}>
            <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
              <div style={{ width: 56, height: 56, borderRadius: "50%", border: "4px solid var(--color-border)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                {loadingOrg === o.id ? "..." : "?"}
              </div>
              <div style={{ fontWeight: 600, fontSize: 13 }}>{o.name}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Churn Risk ────────────────────────────────────────────────────────────────
function ChurnRiskPanel() {
  const { data, loading, reload } = useAdminFetch(() => api.adminChurnRisk());
  const [computing, setComputing] = useState(false);
  const toast = useToast();

  async function compute() {
    setComputing(true);
    try {
      const r = await api.adminComputeChurnRisk();
      toast.success(`${r.updated} tenants updated.`);
      reload();
    } catch (e) { toast.error(e?.message || "Error"); } finally { setComputing(false); }
  }

  if (loading) return <Skeleton lines={4} />;

  const risks = data?.risks || [];
  const high = risks.filter(r => r.risk_level === "high");
  const medium = risks.filter(r => r.risk_level === "medium");
  const low = risks.filter(r => r.risk_level === "low");

  // Bar chart data for risk distribution
  const distData = [
    { name: "High", count: high.length, fill: "#E63946" },
    { name: "Medium", count: medium.length, fill: "#f59e0b" },
    { name: "Low", count: low.length, fill: "#0A8754" },
  ];

  return (
    <div className="stack">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3>Tenant Churn Risk</h3>
        <Button size="sm" loading={computing} onClick={compute}>⟳ Recompute All</Button>
      </div>

      {risks.length > 0 && (
        <div style={{ display: "flex", gap: 12, alignItems: "stretch" }}>
          <div style={{ display: "flex", gap: 8, flex: 1 }}>
            <KpiCard label="High Risk" value={high.length} color="#E63946" sub="Immediate action needed" />
            <KpiCard label="Medium Risk" value={medium.length} color="#f59e0b" sub="Monitor closely" />
            <KpiCard label="Low Risk" value={low.length} color="#0A8754" sub="Healthy" />
          </div>
          <Card style={{ width: 200 }}>
            <div style={{ height: 100 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={distData} barSize={30}>
                  <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                  <Tooltip />
                  <Bar dataKey="count" radius={[3, 3, 0, 0]}>
                    {distData.map((d, i) => <Cell key={i} fill={d.fill} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </div>
      )}

      {risks.length === 0 && <EmptyState icon="activity" title="Risk score নেই" body="'Recompute All' চালান।" />}

      {/* High risk tenants first */}
      {[...high, ...medium, ...low].map(r => (
        <div key={r.id || r.org_id} style={{
          display: "flex", alignItems: "center", gap: 12,
          padding: "10px 14px", background: "var(--color-surface)", borderRadius: 8,
          borderLeft: `4px solid ${r.risk_level === "high" ? "#E63946" : r.risk_level === "medium" ? "#f59e0b" : "#0A8754"}`,
        }}>
          {/* Score ring */}
          <div style={{
            width: 44, height: 44, borderRadius: "50%",
            border: `3px solid ${r.risk_level === "high" ? "#E63946" : r.risk_level === "medium" ? "#f59e0b" : "#0A8754"}`,
            display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
          }}>
            <span style={{ fontSize: 14, fontWeight: 800, color: r.risk_level === "high" ? "#E63946" : r.risk_level === "medium" ? "#f59e0b" : "#0A8754" }}>
              {r.score}%
            </span>
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 600, fontSize: 13 }}>{r.org_name}</div>
            <div style={{ fontSize: 11, color: "var(--color-muted)", marginTop: 2 }}>
              Computed {dateBn(r.computed_at)}
            </div>
          </div>
          <Badge tone={r.risk_level === "high" ? "danger" : r.risk_level === "medium" ? "warning" : "success"}>
            {r.risk_level.toUpperCase()}
          </Badge>
        </div>
      ))}
    </div>
  );
}

// ── Plans ─────────────────────────────────────────────────────────────────────
function PlansPanel() {
  const { data, loading, reload } = useAdminFetch(() => api.adminPlans());
  const [form, setForm] = useState({ code: "", name: "", price_bdt: 0, billing_cycle: "monthly", support_tier: "standard" });
  const toast = useToast();

  async function createPlan() {
    try {
      await api.adminCreatePlan({ ...form, price_bdt: parseFloat(form.price_bdt) });
      toast.success("Plan তৈরি হয়েছে।");
      setForm({ code: "", name: "", price_bdt: 0, billing_cycle: "monthly", support_tier: "standard" });
      reload();
    } catch (e) { toast.error(e?.message || "Error"); }
  }

  if (loading) return <Skeleton lines={3} />;
  return (
    <div className="stack">
      <h3>Plans & Entitlement Engine</h3>
      <Card>
        <h4>নতুন Plan</h4>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
          <Field label="Code"><input className="field-input" value={form.code} onChange={(e) => setForm((f) => ({ ...f, code: e.target.value }))} /></Field>
          <Field label="Name"><input className="field-input" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} /></Field>
          <Field label="Price (BDT)"><input type="number" className="field-input" value={form.price_bdt} onChange={(e) => setForm((f) => ({ ...f, price_bdt: e.target.value }))} /></Field>
          <Field label="Billing Cycle">
            <select className="field-input" value={form.billing_cycle} onChange={(e) => setForm((f) => ({ ...f, billing_cycle: e.target.value }))}>
              <option value="monthly">Monthly</option>
              <option value="quarterly">Quarterly</option>
              <option value="annual">Annual</option>
            </select>
          </Field>
        </div>
        <Button onClick={createPlan}>Plan তৈরি করুন</Button>
      </Card>
      <DataTable
        rows={data?.plans || []}
        columns={[
          { key: "code", label: "Code" },
          { key: "name", label: "Name" },
          { key: "price_bdt", label: "Price (BDT)", render: (v) => `৳${v}` },
          { key: "billing_cycle", label: "Cycle" },
          { key: "support_tier", label: "Support" },
          { key: "active", label: "Status", render: (v) => <Badge tone={v ? "success" : "neutral"}>{v ? "Active" : "Inactive"}</Badge> },
        ]}
      />
    </div>
  );
}

// ── Billing Ledger ────────────────────────────────────────────────────────────
const ENTRY_ICON = { invoice: "📄", payment: "💰", credit_note: "📝", refund: "↩", overage: "⚠" };

function BillingLedgerPanel() {
  const { data: orgs } = useAdminFetch(() => api.platformOrganizations());
  const [selectedOrg, setSelectedOrg] = useState("");
  const [ledger, setLedger] = useState(null);
  const [entryOpen, setEntryOpen] = useState(false);
  const [form, setForm] = useState({ entry_type: "invoice", amount_bdt: "", description: "", period_month: "" });
  const toast = useToast();

  async function loadLedger(orgId) {
    setSelectedOrg(orgId);
    if (!orgId) { setLedger(null); return; }
    const r = await api.adminBillingLedger(orgId);
    setLedger(r);
  }

  async function addEntry() {
    try {
      await api.adminAddBillingEntry(selectedOrg, { ...form, amount_bdt: parseFloat(form.amount_bdt) });
      toast.success("Entry added.");
      setEntryOpen(false);
      setForm({ entry_type: "invoice", amount_bdt: "", description: "", period_month: "" });
      await loadLedger(selectedOrg);
    } catch (e) { toast.error(e?.message || "Error"); }
  }

  // Build monthly chart data from entries
  const chartData = useMemo(() => {
    if (!ledger?.entries) return [];
    const byMonth = {};
    for (const e of ledger.entries) {
      const m = e.created_at?.slice(0, 7) || "?";
      if (!byMonth[m]) byMonth[m] = { month: m, invoiced: 0, paid: 0 };
      if (e.entry_type === "invoice" || e.entry_type === "overage") byMonth[m].invoiced += e.amount_bdt;
      if (e.entry_type === "payment") byMonth[m].paid += e.amount_bdt;
    }
    return Object.values(byMonth).sort((a, b) => a.month.localeCompare(b.month)).slice(-6);
  }, [ledger]);

  return (
    <div className="stack">
      <h3>Billing Ledger</h3>
      <Field label="Business বেছে নিন">
        <select className="field-input" value={selectedOrg} onChange={e => loadLedger(e.target.value)}>
          <option value="">-- বেছে নিন --</option>
          {orgs?.organizations?.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
        </select>
      </Field>

      {ledger && (
        <>
          {/* Outstanding + summary */}
          <div style={{ display: "flex", gap: 10 }}>
            <KpiCard label="Outstanding (BDT)" value={`৳${ledger.outstanding_bdt?.toLocaleString()}`} color={ledger.outstanding_bdt > 0 ? "#E63946" : "#0A8754"} />
            <KpiCard label="Total Invoiced" value={`৳${ledger.entries?.filter(e => e.entry_type === "invoice").reduce((a, b) => a + b.amount_bdt, 0).toLocaleString()}`} />
            <KpiCard label="Total Paid" value={`৳${ledger.entries?.filter(e => e.entry_type === "payment").reduce((a, b) => a + b.amount_bdt, 0).toLocaleString()}`} color="#0A8754" />
          </div>

          {/* Revenue chart */}
          {chartData.length > 0 && (
            <Card>
              <div style={{ fontSize: 12, fontWeight: 700, color: "var(--color-muted)", marginBottom: 8 }}>INVOICED vs PAID (last 6 months)</div>
              <div style={{ height: 160 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData} barSize={20}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip formatter={v => `৳${v?.toLocaleString()}`} />
                    <Bar dataKey="invoiced" name="Invoiced" fill="#0D1B2A" radius={[3, 3, 0, 0]} />
                    <Bar dataKey="paid" name="Paid" fill="#0A8754" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
          )}

          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <Button size="sm" onClick={() => setEntryOpen(true)}>+ New Entry</Button>
          </div>

          {/* Ledger table */}
          {ledger.entries?.map(e => (
            <div key={e.id} style={{
              display: "flex", gap: 10, alignItems: "center",
              padding: "8px 12px", background: "var(--color-surface)", borderRadius: 6,
              borderLeft: `3px solid ${e.entry_type === "invoice" ? "#0D1B2A" : e.entry_type === "payment" ? "#0A8754" : e.entry_type === "refund" ? "#f59e0b" : "#64748B"}`,
            }}>
              <span style={{ fontSize: 18 }}>{ENTRY_ICON[e.entry_type]}</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, fontSize: 13 }}>{e.description || e.entry_type}</div>
                <div style={{ fontSize: 11, color: "var(--color-muted)" }}>{e.period_month} · {dateBn(e.created_at)}</div>
              </div>
              <div style={{ fontWeight: 700, fontSize: 15, color: e.entry_type === "payment" ? "#0A8754" : e.entry_type === "invoice" ? "#E63946" : "var(--color-text)" }}>
                {e.entry_type === "payment" ? "-" : "+"}৳{e.amount_bdt?.toLocaleString()}
              </div>
              <Badge tone={e.status === "paid" ? "success" : "warning"}>{e.status}</Badge>
            </div>
          ))}
        </>
      )}

      {entryOpen && (
        <Modal title="নতুন Billing Entry" onClose={() => setEntryOpen(false)}>
          <div className="stack">
            <Field label="Entry Type">
              <select className="field-input" value={form.entry_type} onChange={e => setForm(f => ({ ...f, entry_type: e.target.value }))}>
                {["invoice", "payment", "credit_note", "refund", "overage"].map(t => <option key={t} value={t}>{ENTRY_ICON[t]} {t}</option>)}
              </select>
            </Field>
            <Field label="Amount (BDT)"><input type="number" className="field-input" value={form.amount_bdt} onChange={e => setForm(f => ({ ...f, amount_bdt: e.target.value }))} /></Field>
            <Field label="Period Month (YYYY-MM)"><input className="field-input" value={form.period_month} onChange={e => setForm(f => ({ ...f, period_month: e.target.value }))} placeholder="2026-10" /></Field>
            <Field label="Description"><input className="field-input" value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} /></Field>
            <Button onClick={addEntry} disabled={!form.amount_bdt}>Add Entry</Button>
          </div>
        </Modal>
      )}
    </div>
  );
}

// ── Usage Metering ────────────────────────────────────────────────────────────
function UsageMeteringPanel() {
  const { data, loading } = useAdminFetch(() => api.adminUsage());
  if (loading) return <Skeleton lines={4} />;
  return (
    <div className="stack">
      <h3>Usage Metering — {data?.period_month}</h3>
      <DataTable
        rows={data?.tenants?.flatMap((t) => Object.entries(t.metrics).map(([metric, total]) => ({ org_name: t.org_name, metric, total }))) || []}
        columns={[
          { key: "org_name", label: "Business" },
          { key: "metric", label: "Metric" },
          { key: "total", label: "Total" },
        ]}
      />
    </div>
  );
}

// ── Reconciliation ────────────────────────────────────────────────────────────
function ReconciliationPanel() {
  const { data, loading, reload } = useAdminFetch(() => api.adminReconciliation("unmatched"));
  const toast = useToast();

  async function match(id) {
    const inv = prompt("Invoice ID:");
    if (!inv) return;
    try {
      await api.adminMatchCollection(id, { matched_invoice_id: inv });
      toast.success("Matched.");
      reload();
    } catch (e) { toast.error(e?.message || "Error"); }
  }

  if (loading) return <Skeleton lines={4} />;
  return (
    <div className="stack">
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <h3>Collection & Reconciliation</h3>
        <Badge tone="warning">{data?.count ?? 0} unmatched</Badge>
      </div>
      <DataTable
        rows={data?.statements || []}
        columns={[
          { key: "provider", label: "Provider" },
          { key: "reference", label: "Reference" },
          { key: "amount_bdt", label: "Amount", render: (v) => `৳${v}` },
          { key: "received_at", label: "Received", render: (v) => dateBn(v) },
          { key: "status", label: "Status", render: (v) => <Badge tone={v === "matched" ? "success" : "warning"}>{v}</Badge> },
          { key: "id", label: "", render: (_, row) => row.status === "unmatched" ? <Button size="sm" onClick={() => match(row.id)}>Match</Button> : null },
        ]}
      />
    </div>
  );
}

// ── Support Cases ─────────────────────────────────────────────────────────────
function SupportCasesPanel() {
  const [statusTab, setStatusTab] = useState("open");
  const { data: sla } = useAdminFetch(() => api.adminSlaSummary());
  const { data, loading, reload } = useAdminFetch(() => api.adminSupportCases(statusTab), [statusTab]);
  const [expanded, setExpanded] = useState(null);
  const [events, setEvents] = useState({});
  const [noteText, setNoteText] = useState("");
  const [newCaseOpen, setNewCaseOpen] = useState(false);
  const [form, setForm] = useState({ subject: "", priority: "normal", source: "manual", description: "" });
  const toast = useToast();

  async function loadEvents(caseId) {
    if (events[caseId]) return;
    const r = await api.adminCaseEvents(caseId);
    setEvents(ev => ({ ...ev, [caseId]: r.events }));
  }

  async function toggleExpand(c) {
    const next = expanded === c.id ? null : c.id;
    setExpanded(next);
    if (next) await loadEvents(c.id);
  }

  async function addNote(caseId) {
    if (!noteText.trim()) return;
    try {
      await api.adminUpdateSupportCase(caseId, { status: "open", comment: noteText });
      toast.success("Note added.");
      setNoteText("");
      const r = await api.adminCaseEvents(caseId);
      setEvents(ev => ({ ...ev, [caseId]: r.events }));
    } catch (e) { toast.error(e?.message || "Error"); }
  }

  async function changeStatus(caseId, s) {
    try {
      await api.adminUpdateSupportCase(caseId, { status: s });
      toast.success(`Case → ${s}`);
      setExpanded(null); reload();
    } catch (e) { toast.error(e?.message || "Error"); }
  }

  async function createCase() {
    try {
      await api.adminCreateSupportCase(form);
      toast.success("Case তৈরি হয়েছে।");
      setNewCaseOpen(false);
      setForm({ subject: "", priority: "normal", source: "manual", description: "" });
      reload();
    } catch (e) { toast.error(e?.message || "Error"); }
  }

  const PRIORITY_COLOR = { urgent: "#E63946", high: "#f59e0b", normal: "#64748B", low: "#94a3b8" };

  if (loading) return <Skeleton lines={5} />;
  return (
    <div className="stack">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3>Support Case Management</h3>
        <Button size="sm" onClick={() => setNewCaseOpen(true)}>+ New Case</Button>
      </div>

      {/* SLA summary cards */}
      {sla && (
        <div style={{ display: "flex", gap: 8 }}>
          <KpiCard label="Total Open" value={sla.total_open ?? 0} />
          <KpiCard label="Response Breached" value={sla.response_breached ?? 0} color={sla.response_breached > 0 ? "#E63946" : undefined} />
          <KpiCard label="Resolution Breached" value={sla.resolution_breached ?? 0} color={sla.resolution_breached > 0 ? "#E63946" : undefined} />
          <KpiCard label="At Risk (<2h)" value={sla.at_risk_response ?? 0} color={sla.at_risk_response > 0 ? "#f59e0b" : undefined} />
        </div>
      )}

      {/* Status tabs */}
      <div style={{ display: "flex", gap: 4, borderBottom: "1px solid var(--color-border)", paddingBottom: 6 }}>
        {["open", "pending", "resolved", "closed"].map(s => (
          <button key={s} onClick={() => { setStatusTab(s); setExpanded(null); }} style={{
            padding: "4px 14px", borderRadius: 20, border: "none", cursor: "pointer", fontSize: 12, fontWeight: 600,
            background: statusTab === s ? "#0D1B2A" : "transparent",
            color: statusTab === s ? "white" : "var(--color-muted)",
          }}>{s}</button>
        ))}
        <span style={{ marginLeft: "auto", fontSize: 12, color: "var(--color-muted)", lineHeight: "26px" }}>{data?.count ?? 0} cases</span>
      </div>

      {data?.cases?.length === 0 && <EmptyState icon="messageSquare" title="কোনো case নেই" />}

      {data?.cases?.map(c => (
        <div key={c.id} style={{
          borderRadius: 8, overflow: "hidden", border: "1px solid var(--color-border)",
          borderLeft: `4px solid ${PRIORITY_COLOR[c.priority] || "#64748B"}`,
        }}>
          {/* Case header */}
          <div style={{ padding: "10px 14px", cursor: "pointer", display: "flex", gap: 12 }} onClick={() => toggleExpand(c)}>
            <div style={{ flex: 1 }}>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 4 }}>
                <Badge tone={c.priority === "urgent" || c.priority === "high" ? "danger" : "info"}>{c.priority}</Badge>
                {c.org_name && <Badge tone="neutral">{c.org_name}</Badge>}
                {c.affected_feature && <Badge tone="warning" style={{ fontSize: 10 }}>{c.affected_feature}</Badge>}
              </div>
              <div style={{ fontWeight: 600, fontSize: 14 }}>{c.subject}</div>
              {/* SLA bar */}
              {c.sla_response_due_at && statusTab === "open" && (
                <div style={{ marginTop: 6 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
                    <span style={{ fontSize: 11, color: "var(--color-muted)" }}>Response SLA</span>
                    <SlaTimer dueAt={c.sla_response_due_at} small />
                  </div>
                  <SlaBar createdAt={c.created_at} dueAt={c.sla_response_due_at} />
                </div>
              )}
              {c.sla_resolution_due_at && statusTab === "open" && (
                <div style={{ marginTop: 5 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
                    <span style={{ fontSize: 11, color: "var(--color-muted)" }}>Resolution SLA</span>
                    <SlaTimer dueAt={c.sla_resolution_due_at} small />
                  </div>
                  <SlaBar createdAt={c.created_at} dueAt={c.sla_resolution_due_at} />
                </div>
              )}
            </div>
            <div style={{ flexShrink: 0, display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
              <span style={{ fontSize: 11, color: "var(--color-muted)" }}>{dateBn(c.created_at)}</span>
              <Icon name={expanded === c.id ? "chevronUp" : "chevronDown"} size={14} />
            </div>
          </div>

          {/* Expanded: event timeline + actions */}
          {expanded === c.id && (
            <div style={{ padding: "0 14px 14px", borderTop: "1px solid var(--color-border)", background: "var(--color-surface-2, var(--color-surface))" }}>
              <div style={{ marginTop: 10, marginBottom: 8, fontSize: 12, fontWeight: 700, color: "var(--color-muted)" }}>HISTORY</div>
              {events[c.id]
                ? <Timeline events={events[c.id]} emptyText="No events yet." />
                : <Skeleton lines={2} />
              }
              {/* Add note */}
              {statusTab !== "resolved" && statusTab !== "closed" && (
                <div style={{ marginTop: 12 }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: "var(--color-muted)", marginBottom: 6 }}>ADD NOTE / UPDATE</div>
                  <div style={{ display: "flex", gap: 6 }}>
                    <input className="field-input" style={{ flex: 1 }} value={noteText} onChange={e => setNoteText(e.target.value)} placeholder="Note লিখুন..." />
                    <Button size="sm" onClick={() => addNote(c.id)}>Add</Button>
                  </div>
                  <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
                    {c.status !== "pending" && <Button size="sm" variant="ghost" onClick={() => changeStatus(c.id, "pending")}>Mark Pending</Button>}
                    {c.status !== "resolved" && <Button size="sm" onClick={() => changeStatus(c.id, "resolved")}>✓ Resolve</Button>}
                    {c.status !== "closed" && <Button size="sm" variant="ghost" onClick={() => changeStatus(c.id, "closed")}>Close</Button>}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      ))}

      {newCaseOpen && (
        <Modal title="নতুন Support Case" onClose={() => setNewCaseOpen(false)}>
          <div className="stack">
            <Field label="Subject"><input className="field-input" value={form.subject} onChange={e => setForm(f => ({ ...f, subject: e.target.value }))} /></Field>
            <Field label="Description"><textarea className="field-input" rows={3} value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} /></Field>
            <div style={{ display: "flex", gap: 8 }}>
              <Field label="Priority" style={{ flex: 1 }}>
                <select className="field-input" value={form.priority} onChange={e => setForm(f => ({ ...f, priority: e.target.value }))}>
                  {["low", "normal", "high", "urgent"].map(p => <option key={p} value={p}>{p}</option>)}
                </select>
              </Field>
              <Field label="Source" style={{ flex: 1 }}>
                <select className="field-input" value={form.source} onChange={e => setForm(f => ({ ...f, source: e.target.value }))}>
                  {["manual", "call", "email", "whatsapp", "in_app"].map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </Field>
            </div>
            <Button onClick={createCase}>Case তৈরি করুন</Button>
          </div>
        </Modal>
      )}
    </div>
  );
}

// ── Support Sessions ──────────────────────────────────────────────────────────
function SupportSessionsPanel() {
  const { data, loading, reload } = useAdminFetch(() => api.adminSupportSessions());
  const { data: orgs } = useAdminFetch(() => api.platformOrganizations());
  const [form, setForm] = useState({ organization_id: "", purpose: "", duration_minutes: 60 });
  const toast = useToast();

  async function create() {
    try {
      await api.adminCreateSupportSession(form);
      toast.success("Session তৈরি হয়েছে।");
      reload();
    } catch (e) { toast.error(e?.message || "Error"); }
  }

  async function end(id) {
    try {
      await api.adminEndSupportSession(id);
      toast.success("Session ended.");
      reload();
    } catch (e) { toast.error(e?.message || "Error"); }
  }

  if (loading) return <Skeleton lines={3} />;
  return (
    <div className="stack">
      <h3>Consented Support Sessions</h3>
      <Card>
        <div style={{ display: "flex", gap: 8 }}>
          <select className="field-input" value={form.organization_id} onChange={(e) => setForm((f) => ({ ...f, organization_id: e.target.value }))}>
            <option value="">-- Business --</option>
            {orgs?.organizations?.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
          </select>
          <input className="field-input" style={{ flex: 2 }} placeholder="Purpose / reason" value={form.purpose} onChange={(e) => setForm((f) => ({ ...f, purpose: e.target.value }))} />
          <input type="number" className="field-input" style={{ width: 80 }} value={form.duration_minutes} onChange={(e) => setForm((f) => ({ ...f, duration_minutes: parseInt(e.target.value) }))} />
          <Button onClick={create}>Start</Button>
        </div>
      </Card>
      {data?.sessions?.map((s) => (
        <Card key={s.id} style={{ display: "flex", justifyContent: "space-between" }}>
          <div>
            <strong>{s.org_name}</strong> — {s.purpose}
            <p style={{ fontSize: 12, color: "var(--color-muted)" }}>Expires: {dateTimeBn(s.expires_at)}</p>
          </div>
          {!s.ended_at && <Button size="sm" variant="danger" onClick={() => end(s.id)}>End</Button>}
        </Card>
      ))}
    </div>
  );
}

// ── SLA Summary ───────────────────────────────────────────────────────────────
function SlaSummaryPanel() {
  const { data, loading } = useAdminFetch(() => api.adminSlaSummary());
  if (loading) return <Skeleton lines={2} />;

  const pieData = [
    { name: "Response Breached", value: data?.response_breached ?? 0, color: "#E63946" },
    { name: "Resolution Breached", value: data?.resolution_breached ?? 0, color: "#f59e0b" },
    { name: "At Risk", value: data?.at_risk_response ?? 0, color: "#eab308" },
    { name: "Healthy", value: Math.max(0, (data?.total_open ?? 0) - (data?.response_breached ?? 0) - (data?.resolution_breached ?? 0) - (data?.at_risk_response ?? 0)), color: "#0A8754" },
  ].filter(d => d.value > 0);

  return (
    <div className="stack">
      <h3>SLA Health Dashboard</h3>
      <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
        <KpiCard label="Total Open" value={data?.total_open ?? 0} />
        <KpiCard label="Response Breached" value={data?.response_breached ?? 0} color={data?.response_breached > 0 ? "#E63946" : undefined} />
        <KpiCard label="Resolution Breached" value={data?.resolution_breached ?? 0} color={data?.resolution_breached > 0 ? "#E63946" : undefined} />
        <KpiCard label="At Risk (<2h)" value={data?.at_risk_response ?? 0} color={data?.at_risk_response > 0 ? "#f59e0b" : undefined} />
      </div>
      {pieData.length > 0 && (
        <Card>
          <strong style={{ fontSize: 13 }}>Status breakdown</strong>
          <div style={{ height: 200 }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={pieData} cx="50%" cy="50%" innerRadius={50} outerRadius={80} dataKey="value" label={({ name, value }) => `${name}: ${value}`} labelLine>
                  {pieData.map((d, i) => <Cell key={i} fill={d.color} />)}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </Card>
      )}
    </div>
  );
}

// ── Security Alerts ───────────────────────────────────────────────────────────
function SecurityAlertsPanel() {
  const [statusTab, setStatusTab] = useState("open");
  const { data, loading, reload } = useAdminFetch(() => api.adminSecurityAlerts(statusTab), [statusTab]);
  const [resolveModal, setResolveModal] = useState(null); // alert being resolved
  const [responseAction, setResponseAction] = useState("");
  const [expanded, setExpanded] = useState(null);
  const toast = useToast();

  async function doResolve() {
    if (!responseAction.trim()) return;
    try {
      await api.adminResolveAlert(resolveModal.id, { response_action: responseAction });
      toast.success("Alert resolved.");
      setResolveModal(null); setResponseAction(""); reload();
    } catch (e) { toast.error(e?.message || "Error"); }
  }

  const SEV_ORDER = ["critical", "high", "medium", "low"];
  const SEV_COLOR = { critical: "#E63946", high: "#f59e0b", medium: "#eab308", low: "#64748B" };

  if (loading) return <Skeleton lines={4} />;

  // Group by severity
  const grouped = SEV_ORDER.reduce((acc, s) => {
    const items = (data?.alerts || []).filter(a => a.severity === s);
    if (items.length) acc.push({ sev: s, items });
    return acc;
  }, []);

  // Severity bar chart
  const sevCounts = SEV_ORDER.map(s => ({
    name: s, count: (data?.alerts || []).filter(a => a.severity === s).length,
    fill: SEV_COLOR[s],
  })).filter(d => d.count > 0);

  return (
    <div className="stack">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3>Security Risk Inbox</h3>
        <div style={{ display: "flex", gap: 4 }}>
          {["open", "resolved"].map(s => (
            <button key={s} onClick={() => setStatusTab(s)} style={{
              padding: "4px 12px", borderRadius: 20, border: "none", cursor: "pointer", fontSize: 12, fontWeight: 600,
              background: statusTab === s ? "#0D1B2A" : "transparent",
              color: statusTab === s ? "white" : "var(--color-muted)",
            }}>{s}</button>
          ))}
        </div>
      </div>

      {/* Severity distribution bar */}
      {sevCounts.length > 0 && (
        <Card style={{ padding: "10px 14px" }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: "var(--color-muted)", marginBottom: 8 }}>SEVERITY DISTRIBUTION</div>
          <div style={{ height: 80 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={sevCounts} layout="vertical">
                <XAxis type="number" hide />
                <YAxis type="category" dataKey="name" width={60} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                  {sevCounts.map((d, i) => <Cell key={i} fill={d.fill} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      )}

      {data?.alerts?.length === 0 && <EmptyState icon="shield" title="কোনো security alert নেই" />}

      {/* Grouped by severity */}
      {grouped.map(({ sev, items }) => (
        <div key={sev}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, margin: "8px 0 4px" }}>
            <div style={{ height: 2, flex: 1, background: SEV_COLOR[sev] + "66" }} />
            <Badge tone={sev === "critical" || sev === "high" ? "danger" : "warning"} style={{ fontSize: 11 }}>{sev.toUpperCase()} ({items.length})</Badge>
            <div style={{ height: 2, flex: 1, background: SEV_COLOR[sev] + "66" }} />
          </div>
          {items.map(a => (
            <div key={a.id} style={{
              background: "var(--color-surface)", borderRadius: 8,
              borderLeft: `4px solid ${SEV_COLOR[a.severity]}`,
              marginBottom: 6, overflow: "hidden",
            }}>
              <div style={{ padding: "10px 14px", display: "flex", gap: 10, cursor: "pointer" }} onClick={() => setExpanded(expanded === a.id ? null : a.id)}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>{a.alert_type?.replace(/_/g, " ")}</div>
                  {a.org_name && <div style={{ fontSize: 12, color: "var(--color-muted)" }}>{a.org_name}</div>}
                </div>
                <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
                  <span style={{ fontSize: 11, color: "var(--color-muted)" }}>{dateTimeBn(a.created_at)}</span>
                  {a.status === "open" && (
                    <Button size="sm" variant="danger" onClick={e => { e.stopPropagation(); setResolveModal(a); }}>Resolve</Button>
                  )}
                </div>
              </div>
              {expanded === a.id && a.details && (
                <div style={{ padding: "0 14px 10px", borderTop: "1px solid var(--color-border)", fontSize: 12 }}>
                  {JSON.stringify(a.details, null, 2)}
                </div>
              )}
            </div>
          ))}
        </div>
      ))}

      {resolveModal && (
        <Modal title={`Resolve: ${resolveModal.alert_type}`} onClose={() => { setResolveModal(null); setResponseAction(""); }}>
          <div className="stack">
            <Notice tone="warning">Alert severity: <strong>{resolveModal.severity}</strong> — org: {resolveModal.org_name || "global"}</Notice>
            <Field label="Response Action (কী করা হলো)">
              <textarea className="field-input" rows={4} value={responseAction} onChange={e => setResponseAction(e.target.value)} placeholder="e.g. Blocked IP range, notified tenant, revoked session..." />
            </Field>
            <Button variant="danger" onClick={doResolve} disabled={!responseAction.trim()}>Confirm Resolve</Button>
          </div>
        </Modal>
      )}
    </div>
  );
}

// ── JIT Access ────────────────────────────────────────────────────────────────
function JitCountdown({ expiresAt, revokedAt }) {
  const diff = useSlaCountdown(revokedAt ? null : expiresAt);
  if (revokedAt) return <Badge tone="neutral">Revoked</Badge>;
  if (diff === null) return null;
  if (diff <= 0) return <Badge tone="danger">Expired</Badge>;
  const color = diff < 600_000 ? "#E63946" : diff < 1_800_000 ? "#f59e0b" : "#0A8754";
  const h = Math.floor(diff / 3600000);
  const m = Math.floor((diff % 3600000) / 60000);
  const s = Math.floor((diff % 60000) / 1000);
  const txt = h > 0 ? `${h}h ${m}m` : `${m}m ${s}s`;
  return <span style={{ fontFamily: "monospace", fontWeight: 700, fontSize: 13, color }}>{txt} left</span>;
}

function JitAccessPanel() {
  const { data, loading, reload } = useAdminFetch(() => api.adminJitGrants());
  const [grantOpen, setGrantOpen] = useState(false);
  const [form, setForm] = useState({ grantee_id: "", permission: "platform_admin", reason: "", duration_minutes: 60 });
  const confirm = useConfirm();
  const toast = useToast();

  const DURATIONS = [
    { label: "15 min", value: 15 },
    { label: "30 min", value: 30 },
    { label: "1 hour", value: 60 },
    { label: "4 hours", value: 240 },
    { label: "8 hours", value: 480 },
  ];

  const PERMISSIONS = ["platform_admin", "tenant_read", "billing_override", "impersonate", "data_export", "ai_disable"];

  async function grant() {
    if (!await confirm(`JIT access grant করা হবে:\nPermission: ${form.permission}\nDuration: ${form.duration_minutes}min\n\nনিশ্চিত?`)) return;
    try {
      await api.adminGrantJit({ ...form, duration_minutes: parseInt(form.duration_minutes) });
      toast.success("JIT access granted.");
      setGrantOpen(false);
      setForm({ grantee_id: "", permission: "platform_admin", reason: "", duration_minutes: 60 });
      reload();
    } catch (e) { toast.error(e?.message || "Error"); }
  }

  async function revoke(id, email) {
    if (!await confirm(`${email} এর JIT access revoke করা হবে?`)) return;
    try {
      await api.adminRevokeJit(id);
      toast.success("Revoked.");
      reload();
    } catch (e) { toast.error(e?.message || "Error"); }
  }

  if (loading) return <Skeleton lines={3} />;

  const active = (data?.grants || []).filter(g => !g.revoked_at && new Date(g.expires_at) > new Date());
  const expired = (data?.grants || []).filter(g => g.revoked_at || new Date(g.expires_at) <= new Date());

  return (
    <div className="stack">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3>Just-in-Time Access</h3>
        <Button size="sm" onClick={() => setGrantOpen(true)}>+ Grant JIT Access</Button>
      </div>

      {active.length === 0 && <Notice tone="success">কোনো active JIT grant নেই — privileged access clear।</Notice>}

      {active.length > 0 && (
        <div>
          <div style={{ fontSize: 12, fontWeight: 700, color: "#E63946", marginBottom: 6 }}>ACTIVE GRANTS ({active.length})</div>
          {active.map(g => (
            <Card key={g.id} style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 8, borderLeft: "4px solid #f59e0b" }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600 }}>{g.grantee_email || g.grantee_id}</div>
                <div style={{ display: "flex", gap: 6, marginTop: 3 }}>
                  <Badge tone="warning">{g.permission}</Badge>
                  <JitCountdown expiresAt={g.expires_at} revokedAt={g.revoked_at} />
                </div>
                <div style={{ fontSize: 12, color: "var(--color-muted)", marginTop: 4 }}>Reason: {g.reason}</div>
              </div>
              <Button size="sm" variant="danger" onClick={() => revoke(g.id, g.grantee_email)}>Revoke</Button>
            </Card>
          ))}
        </div>
      )}

      {expired.length > 0 && (
        <details>
          <summary style={{ fontSize: 12, color: "var(--color-muted)", cursor: "pointer", padding: "4px 0" }}>
            Expired / revoked grants ({expired.length})
          </summary>
          <div style={{ marginTop: 6 }}>
            {expired.slice(0, 10).map(g => (
              <div key={g.id} style={{ display: "flex", gap: 8, padding: "6px 0", fontSize: 12, borderBottom: "1px solid var(--color-border)" }}>
                <span style={{ flex: 1, color: "var(--color-muted)" }}>{g.grantee_email || g.grantee_id}</span>
                <Badge tone="neutral">{g.permission}</Badge>
                <JitCountdown expiresAt={g.expires_at} revokedAt={g.revoked_at} />
                <span style={{ color: "var(--color-muted)" }}>{dateBn(g.expires_at)}</span>
              </div>
            ))}
          </div>
        </details>
      )}

      {grantOpen && (
        <Modal title="JIT Access Grant করুন" onClose={() => setGrantOpen(false)}>
          <div className="stack">
            <Notice tone="warning">JIT access দেওয়া একটি privileged action — সব access audit log এ record হয়।</Notice>
            <Field label="Grantee User ID"><input className="field-input" value={form.grantee_id} onChange={e => setForm(f => ({ ...f, grantee_id: e.target.value }))} /></Field>
            <Field label="Permission">
              <select className="field-input" value={form.permission} onChange={e => setForm(f => ({ ...f, permission: e.target.value }))}>
                {PERMISSIONS.map(p => <option key={p} value={p}>{p}</option>)}
              </select>
            </Field>
            <Field label="Duration">
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {DURATIONS.map(d => (
                  <button key={d.value} onClick={() => setForm(f => ({ ...f, duration_minutes: d.value }))} style={{
                    padding: "5px 12px", borderRadius: 20, border: "1px solid var(--color-border)",
                    background: form.duration_minutes === d.value ? "#0D1B2A" : "transparent",
                    color: form.duration_minutes === d.value ? "white" : "var(--color-text)",
                    cursor: "pointer", fontSize: 12,
                  }}>{d.label}</button>
                ))}
              </div>
            </Field>
            <Field label="Reason (required)"><textarea className="field-input" rows={3} value={form.reason} onChange={e => setForm(f => ({ ...f, reason: e.target.value }))} placeholder="কেন এই access দরকার..." /></Field>
            <Button onClick={grant} disabled={!form.grantee_id || !form.reason.trim()}>Grant Access</Button>
          </div>
        </Modal>
      )}
    </div>
  );
}

// ── Access Certification ──────────────────────────────────────────────────────
function AccessCertificationPanel() {
  const { data, loading, reload } = useAdminFetch(() => api.adminCertCycles());
  const [title, setTitle] = useState("");
  const toast = useToast();

  async function create() {
    try {
      const r = await api.adminCreateCertCycle({ title, due_days: 14 });
      toast.success(`Cycle created with ${r.item_count} items.`);
      setTitle(""); reload();
    } catch (e) { toast.error(e?.message || "Error"); }
  }

  if (loading) return <Skeleton lines={3} />;
  return (
    <div className="stack">
      <h3>Access Certification</h3>
      <Card>
        <div style={{ display: "flex", gap: 8 }}>
          <input className="field-input" style={{ flex: 1 }} placeholder="Cycle title" value={title} onChange={(e) => setTitle(e.target.value)} />
          <Button onClick={create}>New Cycle</Button>
        </div>
      </Card>
      <DataTable
        rows={data?.cycles || []}
        columns={[
          { key: "title", label: "Title" },
          { key: "status", label: "Status", render: (v) => <Badge tone={v === "completed" ? "success" : "info"}>{v}</Badge> },
          { key: "due_at", label: "Due", render: (v) => dateBn(v) },
          { key: "completed_at", label: "Completed", render: (v) => v ? dateBn(v) : "—" },
        ]}
      />
    </div>
  );
}

// ── Emergency Containment ─────────────────────────────────────────────────────
function EmergencyContainmentPanel() {
  const { data: orgs } = useAdminFetch(() => api.platformOrganizations());
  const [form, setForm] = useState({ organization_id: "", reason: "", actions: [] });
  const toast = useToast();
  const confirm = useConfirm();

  function toggleAction(action) {
    setForm((f) => ({
      ...f,
      actions: f.actions.includes(action) ? f.actions.filter((a) => a !== action) : [...f.actions, action],
    }));
  }

  async function execute() {
    if (!await confirm(`⚠ EMERGENCY CONTAINMENT: ${form.actions.join(", ")}. Reason: ${form.reason}. নিশ্চিত?`)) return;
    try {
      const r = await api.adminEmergencyContain({ ...form, organization_id: form.organization_id || null });
      toast.success(`Actions taken: ${r.actions_taken.join(", ")}`);
      setForm({ organization_id: "", reason: "", actions: [] });
    } catch (e) { toast.error(e?.message || "Error"); }
  }

  const ACTIONS = ["freeze_logins", "revoke_sessions", "disable_api_keys", "halt_messaging"];
  return (
    <div className="stack">
      <Notice tone="danger" title="⚠ Emergency Containment">এই action গুলো ব্যবহার করুন শুধুমাত্র real security incident বা severe system abuse এর ক্ষেত্রে।</Notice>
      <Card>
        <Field label="Affected Business (optional)">
          <select className="field-input" value={form.organization_id} onChange={(e) => setForm((f) => ({ ...f, organization_id: e.target.value }))}>
            <option value="">-- সব business (global) --</option>
            {orgs?.organizations?.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
          </select>
        </Field>
        <Field label="Reason"><input className="field-input" value={form.reason} onChange={(e) => setForm((f) => ({ ...f, reason: e.target.value }))} /></Field>
        <Field label="Actions">
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {ACTIONS.map((a) => (
              <label key={a} style={{ display: "flex", alignItems: "center", gap: 4, cursor: "pointer" }}>
                <input type="checkbox" checked={form.actions.includes(a)} onChange={() => toggleAction(a)} />
                {a.replace(/_/g, " ")}
              </label>
            ))}
          </div>
        </Field>
        <Button variant="danger" onClick={execute} disabled={!form.reason || form.actions.length === 0}>EXECUTE CONTAINMENT</Button>
      </Card>
    </div>
  );
}

// ── Incident Command ──────────────────────────────────────────────────────────
function IncidentPanel() {
  const [statusTab, setStatusTab] = useState("open");
  const { data, loading, reload } = useAdminFetch(() => api.adminIncidents(statusTab), [statusTab]);
  const [expanded, setExpanded] = useState(null);
  const [incTimelines, setIncTimelines] = useState({});
  const [updateText, setUpdateText] = useState("");
  const [newOpen, setNewOpen] = useState(false);
  const [form, setForm] = useState({ title: "", severity: "p2", affected_org_count: 0, description: "" });
  const toast = useToast();

  const SEV_COLOR = { p1: "#E63946", p2: "#f59e0b", p3: "#64748B", p4: "#94a3b8" };
  const SEV_LABEL = { p1: "P1 Critical", p2: "P2 Major", p3: "P3 Minor", p4: "P4 Low" };

  async function toggleExpand(inc) {
    const next = expanded === inc.id ? null : inc.id;
    setExpanded(next);
    if (next && !incTimelines[next]) {
      try {
        const r = await api.adminIncidentTimeline(next);
        setIncTimelines(t => ({ ...t, [next]: r.events || [] }));
      } catch {}
    }
  }

  async function addUpdate(incId, currentStatus) {
    if (!updateText.trim()) return;
    try {
      await api.adminUpdateIncident(incId, { status: currentStatus, update_message: updateText });
      toast.success("Update posted.");
      setUpdateText("");
      const r = await api.adminIncidentTimeline(incId);
      setIncTimelines(t => ({ ...t, [incId]: r.events || [] }));
    } catch (e) { toast.error(e?.message || "Error"); }
  }

  async function changeStatus(incId, s) {
    try {
      await api.adminUpdateIncident(incId, { status: s });
      toast.success(`Incident → ${s}`);
      setExpanded(null); reload();
    } catch (e) { toast.error(e?.message || "Error"); }
  }

  async function create() {
    try {
      await api.adminCreateIncident(form);
      toast.success("Incident opened.");
      setNewOpen(false);
      setForm({ title: "", severity: "p2", affected_org_count: 0, description: "" });
      reload();
    } catch (e) { toast.error(e?.message || "Error"); }
  }

  if (loading) return <Skeleton lines={4} />;

  const p1p2 = (data?.incidents || []).filter(i => i.severity === "p1" || i.severity === "p2");

  return (
    <div className="stack">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3>Incident Command Center</h3>
        <Button size="sm" variant="danger" onClick={() => setNewOpen(true)}>⚡ Declare Incident</Button>
      </div>

      {/* P1/P2 banner */}
      {p1p2.map(inc => (
        <div key={inc.id} style={{
          background: SEV_COLOR[inc.severity] + "22", borderRadius: 8,
          border: `2px solid ${SEV_COLOR[inc.severity]}`,
          padding: "10px 14px", display: "flex", gap: 10, alignItems: "center",
        }}>
          <Badge tone="danger">{SEV_LABEL[inc.severity]}</Badge>
          <strong style={{ flex: 1 }}>{inc.title}</strong>
          <span style={{ fontSize: 12 }}>{inc.affected_org_count ?? 0} tenants affected</span>
          <Button size="sm" onClick={() => toggleExpand(inc)}>Manage ▼</Button>
        </div>
      ))}

      {/* Status tabs */}
      <div style={{ display: "flex", gap: 4, borderBottom: "1px solid var(--color-border)", paddingBottom: 6 }}>
        {["open", "mitigated", "resolved"].map(s => (
          <button key={s} onClick={() => { setStatusTab(s); setExpanded(null); }} style={{
            padding: "4px 14px", borderRadius: 20, border: "none", cursor: "pointer", fontSize: 12, fontWeight: 600,
            background: statusTab === s ? "#0D1B2A" : "transparent",
            color: statusTab === s ? "white" : "var(--color-muted)",
          }}>{s}</button>
        ))}
      </div>

      {data?.incidents?.length === 0 && <EmptyState icon="checkCircle" title="No active incidents" />}

      {data?.incidents?.map(inc => (
        <div key={inc.id} style={{
          borderRadius: 8, overflow: "hidden",
          border: `1px solid ${SEV_COLOR[inc.severity]}44`,
          borderLeft: `5px solid ${SEV_COLOR[inc.severity]}`,
        }}>
          <div style={{ padding: "10px 14px", display: "flex", gap: 10, cursor: "pointer" }} onClick={() => toggleExpand(inc)}>
            <div style={{ flex: 1 }}>
              <div style={{ display: "flex", gap: 6, marginBottom: 4 }}>
                <Badge tone={inc.severity === "p1" ? "danger" : inc.severity === "p2" ? "warning" : "neutral"}>{SEV_LABEL[inc.severity]}</Badge>
                <Badge tone="info">{inc.status}</Badge>
                {inc.affected_org_count > 0 && <span style={{ fontSize: 12, color: "var(--color-muted)" }}>{inc.affected_org_count} tenants</span>}
              </div>
              <div style={{ fontWeight: 600, fontSize: 14 }}>{inc.title}</div>
              <div style={{ fontSize: 11, color: "var(--color-muted)", marginTop: 3 }}>Opened {dateTimeBn(inc.created_at)}</div>
            </div>
            <Icon name={expanded === inc.id ? "chevronUp" : "chevronDown"} size={14} style={{ flexShrink: 0, marginTop: 4 }} />
          </div>

          {expanded === inc.id && (
            <div style={{ padding: "0 14px 14px", borderTop: "1px solid var(--color-border)", background: "var(--color-surface-2, var(--color-surface))" }}>
              <div style={{ marginTop: 10, marginBottom: 8, fontSize: 12, fontWeight: 700, color: "var(--color-muted)" }}>INCIDENT TIMELINE</div>
              {incTimelines[inc.id]
                ? <Timeline events={incTimelines[inc.id]} emptyText="No updates posted yet." />
                : <Skeleton lines={2} />
              }
              {/* Post update */}
              <div style={{ marginTop: 12, padding: "10px", background: "var(--color-surface)", borderRadius: 6 }}>
                <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 6 }}>POST UPDATE</div>
                <div style={{ display: "flex", gap: 6 }}>
                  <input className="field-input" style={{ flex: 1 }} value={updateText} onChange={e => setUpdateText(e.target.value)} placeholder="Status update, mitigation steps..." />
                  <Button size="sm" onClick={() => addUpdate(inc.id, inc.status)}>Post</Button>
                </div>
                <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
                  {inc.status === "open" && <Button size="sm" variant="ghost" onClick={() => changeStatus(inc.id, "mitigated")}>Mark Mitigated</Button>}
                  {inc.status !== "resolved" && <Button size="sm" onClick={() => changeStatus(inc.id, "resolved")}>✓ Resolve</Button>}
                </div>
              </div>
            </div>
          )}
        </div>
      ))}

      {newOpen && (
        <Modal title="Incident Declare করুন" onClose={() => setNewOpen(false)}>
          <div className="stack">
            <Field label="Severity">
              <div style={{ display: "flex", gap: 6 }}>
                {["p1", "p2", "p3", "p4"].map(s => (
                  <button key={s} onClick={() => setForm(f => ({ ...f, severity: s }))} style={{
                    flex: 1, padding: "8px 0", borderRadius: 6, border: `2px solid ${form.severity === s ? SEV_COLOR[s] : "var(--color-border)"}`,
                    background: form.severity === s ? SEV_COLOR[s] + "22" : "transparent",
                    fontWeight: 700, fontSize: 13, cursor: "pointer", color: SEV_COLOR[s],
                  }}>{SEV_LABEL[s]}</button>
                ))}
              </div>
            </Field>
            <Field label="Title"><input className="field-input" value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} /></Field>
            <Field label="Description"><textarea className="field-input" rows={3} value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} /></Field>
            <Field label="Affected Tenant Count"><input type="number" className="field-input" value={form.affected_org_count} onChange={e => setForm(f => ({ ...f, affected_org_count: parseInt(e.target.value) || 0 }))} /></Field>
            <Button variant="danger" onClick={create} disabled={!form.title}>Declare Incident</Button>
          </div>
        </Modal>
      )}
    </div>
  );
}

// ── Job Console ───────────────────────────────────────────────────────────────
function JobConsolePanel() {
  const [status, setStatus] = useState("failed");
  const { data, loading, reload } = useAdminFetch(() => api.adminJobs(status), [status]);
  const toast = useToast();

  async function retry(id) {
    try {
      await api.adminRetryJob(id);
      toast.success("Job re-queued.");
      reload();
    } catch (e) { toast.error(e?.message || "Error"); }
  }

  if (loading) return <Skeleton lines={4} />;
  return (
    <div className="stack">
      <h3>Background Job Console</h3>
      <div style={{ display: "flex", gap: 4 }}>
        {["pending", "running", "failed", "dead"].map((s) => <Button key={s} size="sm" variant={status === s ? "primary" : "ghost"} onClick={() => setStatus(s)}>{s}</Button>)}
      </div>
      <DataTable
        rows={data?.jobs || []}
        columns={[
          { key: "job_type", label: "Type" },
          { key: "status", label: "Status", render: (v) => <Badge tone={v === "failed" || v === "dead" ? "danger" : "info"}>{v}</Badge> },
          { key: "attempt_count", label: "Attempts" },
          { key: "error", label: "Error", render: (v) => v ? <span style={{ color: "#E63946", fontSize: 12 }}>{v.slice(0, 60)}</span> : null },
          { key: "created_at", label: "Created", render: (v) => dateBn(v) },
          { key: "id", label: "", render: (_, row) => (row.status === "failed" || row.status === "dead") ? <Button size="sm" onClick={() => retry(row.id)}>Retry</Button> : null },
        ]}
      />
    </div>
  );
}

// ── Rollout ───────────────────────────────────────────────────────────────────
function RolloutPanel() {
  const { data, loading, reload } = useAdminFetch(() => api.adminRolloutConfigs());
  const [newOpen, setNewOpen] = useState(false);
  const [form, setForm] = useState({ feature_key: "", auto_rollback_enabled: true });
  const confirm = useConfirm();
  const toast = useToast();

  async function create() {
    try {
      await api.adminCreateRollout({ ...form, stages: ROLLOUT_STAGES });
      toast.success("Rollout config created.");
      setNewOpen(false);
      setForm({ feature_key: "", auto_rollback_enabled: true });
      reload();
    } catch (e) { toast.error(e?.message || "Error"); }
  }

  async function advance(c) {
    const ci = ROLLOUT_STAGES.indexOf(c.current_stage);
    const next = ROLLOUT_STAGES[ci + 1];
    if (!next) return toast.error("Already at final stage.");
    if (!await confirm(`"${c.feature_key}" → ${STAGE_LBL[next]} stage এ advance করা হবে। নিশ্চিত?`)) return;
    try {
      await api.adminAdvanceRollout(c.id, {});
      toast.success(`Advanced → ${next}`);
      reload();
    } catch (e) { toast.error(e?.message || "Error"); }
  }

  async function rollback(c) {
    if (!await confirm(`"${c.feature_key}" rollback করা হবে। নিশ্চিত?`)) return;
    try {
      await api.adminRollbackRollout(c.id);
      toast.success("Rolled back.");
      reload();
    } catch (e) { toast.error(e?.message || "Error"); }
  }

  if (loading) return <Skeleton lines={3} />;
  return (
    <div className="stack">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3>Progressive Feature Rollout</h3>
        <Button size="sm" onClick={() => setNewOpen(true)}>+ New Rollout</Button>
      </div>

      {data?.configs?.length === 0 && <EmptyState icon="gitBranch" title="কোনো rollout config নেই" />}

      {data?.configs?.map(c => {
        const ci = ROLLOUT_STAGES.indexOf(c.current_stage);
        const atFinal = ci === ROLLOUT_STAGES.length - 1;
        return (
          <Card key={c.id} style={{ padding: "14px 16px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 10 }}>
              <div>
                <strong style={{ fontSize: 15 }}>{c.feature_key}</strong>
                {c.rollback_count > 0 && <Badge tone="warning" style={{ marginLeft: 8 }}>↩ {c.rollback_count} rollbacks</Badge>}
                {atFinal && <Badge tone="success" style={{ marginLeft: 8 }}>✓ Fully Rolled Out</Badge>}
              </div>
              <div style={{ display: "flex", gap: 4 }}>
                {!atFinal && <Button size="sm" onClick={() => advance(c)}>Advance ▶</Button>}
                {ci > 0 && <Button size="sm" variant="ghost" onClick={() => rollback(c)}>◀ Rollback</Button>}
              </div>
            </div>
            <StagePipeline currentStage={c.current_stage} />
            {c.auto_rollback_enabled && (
              <div style={{ fontSize: 11, color: "var(--color-muted)", marginTop: 6 }}>⚙ Auto-rollback enabled</div>
            )}
          </Card>
        );
      })}

      {newOpen && (
        <Modal title="New Rollout Config" onClose={() => setNewOpen(false)}>
          <div className="stack">
            <Field label="Feature Key (unique)">
              <input className="field-input" value={form.feature_key} onChange={e => setForm(f => ({ ...f, feature_key: e.target.value }))} placeholder="e.g. ai_demand_forecast_v2" />
            </Field>
            <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
              <input type="checkbox" checked={form.auto_rollback_enabled} onChange={e => setForm(f => ({ ...f, auto_rollback_enabled: e.target.checked }))} />
              Error rate বেশি হলে auto-rollback করুন
            </label>
            <div style={{ fontSize: 12, color: "var(--color-muted)" }}>
              Stages: {ROLLOUT_STAGES.map(s => STAGE_LBL[s]).join(" → ")}
            </div>
            <Button onClick={create} disabled={!form.feature_key}>Create</Button>
          </div>
        </Modal>
      )}
    </div>
  );
}

// ── Config Versions ───────────────────────────────────────────────────────────
function ConfigVersionPanel() {
  const { data, loading, reload } = useAdminFetch(() => api.adminConfigVersions());
  const [form, setForm] = useState({ config_key: "", value_json: "", diff_summary: "" });
  const toast = useToast();

  async function save() {
    try {
      await api.adminSaveConfig(form);
      toast.success("Config version saved.");
      setForm({ config_key: "", value_json: "", diff_summary: "" });
      reload();
    } catch (e) { toast.error(e?.message || "Error"); }
  }

  if (loading) return <Skeleton lines={3} />;
  return (
    <div className="stack">
      <h3>Configuration Versioning</h3>
      <Card>
        <Field label="Config Key"><input className="field-input" value={form.config_key} onChange={(e) => setForm((f) => ({ ...f, config_key: e.target.value }))} /></Field>
        <Field label="Value (JSON)"><textarea className="field-input" rows={3} value={form.value_json} onChange={(e) => setForm((f) => ({ ...f, value_json: e.target.value }))} /></Field>
        <Field label="Change Summary"><input className="field-input" value={form.diff_summary} onChange={(e) => setForm((f) => ({ ...f, diff_summary: e.target.value }))} /></Field>
        <Button onClick={save}>Save Version</Button>
      </Card>
      <DataTable
        rows={data?.versions || []}
        columns={[
          { key: "config_key", label: "Key" },
          { key: "version", label: "v" },
          { key: "diff_summary", label: "Changes" },
          { key: "deployed_at", label: "Deployed", render: (v) => v ? dateBn(v) : "—" },
          { key: "created_at", label: "Saved", render: (v) => dateBn(v) },
        ]}
      />
    </div>
  );
}

// ── Provider Credentials ──────────────────────────────────────────────────────
function ProviderCredentialPanel() {
  const { data, loading, reload } = useAdminFetch(() => api.adminProviderCredentials());
  const [form, setForm] = useState({ provider: "", credential_name: "", status: "active" });
  const toast = useToast();

  async function add() {
    try {
      await api.adminAddCredential(form);
      toast.success("Credential added.");
      setForm({ provider: "", credential_name: "", status: "active" });
      reload();
    } catch (e) { toast.error(e?.message || "Error"); }
  }

  async function rotate(id) {
    try {
      await api.adminRotateCredential(id);
      toast.success("Rotated.");
      reload();
    } catch (e) { toast.error(e?.message || "Error"); }
  }

  if (loading) return <Skeleton lines={3} />;
  return (
    <div className="stack">
      <h3>Provider Credential Lifecycle</h3>
      <Card>
        <div style={{ display: "flex", gap: 8 }}>
          <input className="field-input" placeholder="Provider (e.g. bkash)" value={form.provider} onChange={(e) => setForm((f) => ({ ...f, provider: e.target.value }))} />
          <input className="field-input" placeholder="Credential name" value={form.credential_name} onChange={(e) => setForm((f) => ({ ...f, credential_name: e.target.value }))} />
          <Button onClick={add}>Add</Button>
        </div>
      </Card>
      <DataTable
        rows={data?.credentials || []}
        columns={[
          { key: "provider", label: "Provider" },
          { key: "credential_name", label: "Name" },
          { key: "status", label: "Status", render: (v) => <Badge tone={v === "active" ? "success" : v === "expiring" ? "warning" : "danger"}>{v}</Badge> },
          { key: "expiring_soon", label: "", render: (v) => v ? <Badge tone="warning">⚠ Expiring</Badge> : null },
          { key: "last_rotated_at", label: "Last Rotated", render: (v) => v ? dateBn(v) : "Never" },
          { key: "id", label: "", render: (_, row) => <Button size="sm" onClick={() => rotate(row.id)}>Rotate</Button> },
        ]}
      />
    </div>
  );
}

// ── Webhook Inbox ─────────────────────────────────────────────────────────────
function WebhookInboxPanel() {
  const [status, setStatus] = useState("failed");
  const { data, loading, reload } = useAdminFetch(() => api.adminWebhooks(status), [status]);
  const toast = useToast();

  async function replay(id) {
    try {
      await api.adminReplayWebhook(id);
      toast.success("Replayed.");
      reload();
    } catch (e) { toast.error(e?.message || "Error"); }
  }

  if (loading) return <Skeleton lines={4} />;
  return (
    <div className="stack">
      <h3>Webhook Inbox</h3>
      <div style={{ display: "flex", gap: 4 }}>
        {["pending", "processed", "failed"].map((s) => <Button key={s} size="sm" variant={status === s ? "primary" : "ghost"} onClick={() => setStatus(s)}>{s}</Button>)}
      </div>
      <DataTable
        rows={data?.events || []}
        columns={[
          { key: "provider", label: "Provider" },
          { key: "event_type", label: "Event Type" },
          { key: "signature_valid", label: "Sig", render: (v) => <Badge tone={v ? "success" : "danger"}>{v ? "✓" : "✗"}</Badge> },
          { key: "processing_status", label: "Status" },
          { key: "replay_count", label: "Replays" },
          { key: "received_at", label: "Received", render: (v) => dateBn(v) },
          { key: "id", label: "", render: (_, row) => row.processing_status === "failed" ? <Button size="sm" onClick={() => replay(row.id)}>Replay</Button> : null },
        ]}
      />
    </div>
  );
}

// ── Integration Certification ─────────────────────────────────────────────────
function IntegrationCertPanel() {
  const { data: orgs } = useAdminFetch(() => api.platformOrganizations());
  const [selectedOrg, setSelectedOrg] = useState("");
  const [certs, setCerts] = useState(null);
  const [form, setForm] = useState({ integration: "bkash", sandbox_tested: false, callback_validated: false, refund_tested: false, credential_verified: false });
  const toast = useToast();

  async function load(orgId) {
    setSelectedOrg(orgId);
    if (!orgId) return;
    const r = await api.adminIntegrationCerts(orgId);
    setCerts(r);
  }

  async function save() {
    try {
      await api.adminUpdateIntegrationCert(selectedOrg, form);
      toast.success("Certification updated.");
      load(selectedOrg);
    } catch (e) { toast.error(e?.message || "Error"); }
  }

  return (
    <div className="stack">
      <h3>Integration Certification</h3>
      <Field label="Business বেছে নিন">
        <select className="field-input" value={selectedOrg} onChange={(e) => load(e.target.value)}>
          <option value="">-- বেছে নিন --</option>
          {orgs?.organizations?.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
        </select>
      </Field>
      {certs && (
        <>
          <Card>
            <Field label="Integration">
              <select className="field-input" value={form.integration} onChange={(e) => setForm((f) => ({ ...f, integration: e.target.value }))}>
                {["bkash", "nagad", "whatsapp", "sms"].map((i) => <option key={i} value={i}>{i}</option>)}
              </select>
            </Field>
            <div style={{ display: "flex", gap: 16, flexWrap: "wrap", margin: "8px 0" }}>
              {["sandbox_tested", "callback_validated", "refund_tested", "credential_verified"].map((field) => (
                <label key={field} style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  <input type="checkbox" checked={form[field]} onChange={(e) => setForm((f) => ({ ...f, [field]: e.target.checked }))} />
                  {field.replace(/_/g, " ")}
                </label>
              ))}
            </div>
            <Button onClick={save}>Save Certification</Button>
          </Card>
          <DataTable
            rows={certs.certifications}
            columns={[
              { key: "integration", label: "Integration" },
              { key: "sandbox_tested", label: "Sandbox", render: (v) => <Badge tone={v ? "success" : "neutral"}>{v ? "✓" : "✗"}</Badge> },
              { key: "callback_validated", label: "Callback", render: (v) => <Badge tone={v ? "success" : "neutral"}>{v ? "✓" : "✗"}</Badge> },
              { key: "certified_at", label: "Certified", render: (v) => v ? dateBn(v) : "Not yet" },
            ]}
          />
        </>
      )}
    </div>
  );
}

// ── Data Inventory ────────────────────────────────────────────────────────────
function DataInventoryPanel() {
  const { data, loading, reload } = useAdminFetch(() => api.adminDataInventory());
  const [form, setForm] = useState({ module: "", data_category: "", description: "", table_name: "" });
  const toast = useToast();

  async function add() {
    try {
      await api.adminAddDataInventory(form);
      toast.success("Added.");
      setForm({ module: "", data_category: "", description: "", table_name: "" });
      reload();
    } catch (e) { toast.error(e?.message || "Error"); }
  }

  if (loading) return <Skeleton lines={4} />;
  return (
    <div className="stack">
      <h3>Data Inventory Catalogue</h3>
      <Card>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
          <Field label="Module"><input className="field-input" value={form.module} onChange={(e) => setForm((f) => ({ ...f, module: e.target.value }))} /></Field>
          <Field label="Category"><input className="field-input" value={form.data_category} onChange={(e) => setForm((f) => ({ ...f, data_category: e.target.value }))} /></Field>
          <Field label="Description" style={{ gridColumn: "1/-1" }}><input className="field-input" value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} /></Field>
          <Field label="Table Name"><input className="field-input" value={form.table_name} onChange={(e) => setForm((f) => ({ ...f, table_name: e.target.value }))} /></Field>
        </div>
        <Button onClick={add}>Add to Inventory</Button>
      </Card>
      <DataTable
        rows={data?.items || []}
        columns={[
          { key: "module", label: "Module" },
          { key: "data_category", label: "Category" },
          { key: "description", label: "Description" },
          { key: "table_name", label: "Table" },
          { key: "retention_days", label: "Retention", render: (v) => v ? `${v}d` : "—" },
        ]}
      />
    </div>
  );
}

// ── Data Exports ──────────────────────────────────────────────────────────────
function DataExportsPanel() {
  const { data, loading, reload } = useAdminFetch(() => api.adminDataExports());
  const { data: orgs } = useAdminFetch(() => api.platformOrganizations());
  const [selectedOrg, setSelectedOrg] = useState("");
  const toast = useToast();

  async function create() {
    if (!selectedOrg) return;
    try {
      await api.adminCreateDataExport({ organization_id: selectedOrg, scope: ["sales", "customers", "products"] });
      toast.success("Export requested.");
      reload();
    } catch (e) { toast.error(e?.message || "Error"); }
  }

  async function complete(id) {
    try {
      await api.adminCompleteDataExport(id);
      toast.success("Marked as ready.");
      reload();
    } catch (e) { toast.error(e?.message || "Error"); }
  }

  if (loading) return <Skeleton lines={3} />;
  return (
    <div className="stack">
      <h3>Tenant Data Exports</h3>
      <Card>
        <div style={{ display: "flex", gap: 8 }}>
          <select className="field-input" style={{ flex: 1 }} value={selectedOrg} onChange={(e) => setSelectedOrg(e.target.value)}>
            <option value="">-- Business --</option>
            {orgs?.organizations?.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
          </select>
          <Button onClick={create}>Request Export</Button>
        </div>
      </Card>
      <DataTable
        rows={data?.exports || []}
        columns={[
          { key: "org_name", label: "Business" },
          { key: "status", label: "Status", render: (v) => <Badge tone={v === "ready" ? "success" : v === "pending" ? "warning" : "info"}>{v}</Badge> },
          { key: "created_at", label: "Requested", render: (v) => dateBn(v) },
          { key: "expires_at", label: "Expires", render: (v) => v ? dateBn(v) : "—" },
          { key: "id", label: "", render: (_, row) => row.status === "pending" ? <Button size="sm" onClick={() => complete(row.id)}>Mark Ready</Button> : null },
        ]}
      />
    </div>
  );
}

// ── Retention Policies ────────────────────────────────────────────────────────
function RetentionPoliciesPanel() {
  const { data, loading, reload } = useAdminFetch(() => api.adminRetentionPolicies());
  const [form, setForm] = useState({ data_category: "", retention_days: 365, action_on_expiry: "archive" });
  const toast = useToast();

  async function upsert() {
    try {
      await api.adminUpsertRetentionPolicy(form);
      toast.success("Policy saved.");
      reload();
    } catch (e) { toast.error(e?.message || "Error"); }
  }

  if (loading) return <Skeleton lines={3} />;
  return (
    <div className="stack">
      <h3>Data Retention Policies</h3>
      <Card>
        <div style={{ display: "flex", gap: 8 }}>
          <input className="field-input" placeholder="Data category (e.g. invoice, logs)" value={form.data_category} onChange={(e) => setForm((f) => ({ ...f, data_category: e.target.value }))} />
          <input type="number" className="field-input" style={{ width: 100 }} value={form.retention_days} onChange={(e) => setForm((f) => ({ ...f, retention_days: parseInt(e.target.value) }))} />
          <select className="field-input" value={form.action_on_expiry} onChange={(e) => setForm((f) => ({ ...f, action_on_expiry: e.target.value }))}>
            {["archive", "purge", "review"].map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
          <Button onClick={upsert}>Save</Button>
        </div>
      </Card>
      <DataTable
        rows={data?.policies || []}
        columns={[
          { key: "data_category", label: "Category" },
          { key: "retention_days", label: "Retain (days)" },
          { key: "action_on_expiry", label: "On Expiry" },
          { key: "requires_approval", label: "Approval", render: (v) => v ? "✓" : "—" },
          { key: "legal_hold_override", label: "Legal Hold", render: (v) => v ? <Badge tone="danger">Active</Badge> : "—" },
        ]}
      />
    </div>
  );
}

// ── Privacy Requests ──────────────────────────────────────────────────────────
function PrivacyRequestsPanel() {
  const [status, setStatus] = useState("pending");
  const { data, loading, reload } = useAdminFetch(() => api.adminPrivacyRequests(status), [status]);
  const [form, setForm] = useState({ request_type: "access", subject_email: "", description: "" });
  const toast = useToast();

  async function create() {
    try {
      await api.adminCreatePrivacyRequest(form);
      toast.success("Request created.");
      setForm({ request_type: "access", subject_email: "", description: "" });
      reload();
    } catch (e) { toast.error(e?.message || "Error"); }
  }

  async function complete(id) {
    try {
      await api.adminUpdatePrivacyRequest(id, { status: "completed", verification_completed: true });
      toast.success("Completed.");
      reload();
    } catch (e) { toast.error(e?.message || "Error"); }
  }

  if (loading) return <Skeleton lines={3} />;
  return (
    <div className="stack">
      <h3>Privacy Request Workflow</h3>
      <div style={{ display: "flex", gap: 4 }}>
        {["pending", "in_progress", "completed"].map((s) => <Button key={s} size="sm" variant={status === s ? "primary" : "ghost"} onClick={() => setStatus(s)}>{s}</Button>)}
      </div>
      <Card>
        <div style={{ display: "flex", gap: 8 }}>
          <select className="field-input" value={form.request_type} onChange={(e) => setForm((f) => ({ ...f, request_type: e.target.value }))}>
            {["access", "correction", "portability", "deletion"].map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          <input className="field-input" style={{ flex: 1 }} placeholder="Subject email" value={form.subject_email} onChange={(e) => setForm((f) => ({ ...f, subject_email: e.target.value }))} />
          <Button onClick={create}>Create</Button>
        </div>
      </Card>
      <DataTable
        rows={data?.requests || []}
        columns={[
          { key: "request_type", label: "Type" },
          { key: "subject_email", label: "Subject" },
          { key: "status", label: "Status", render: (v) => <Badge tone={v === "completed" ? "success" : "warning"}>{v}</Badge> },
          { key: "due_at", label: "Due", render: (v) => v ? dateBn(v) : "—" },
          { key: "id", label: "", render: (_, row) => row.status !== "completed" ? <Button size="sm" onClick={() => complete(row.id)}>Complete</Button> : null },
        ]}
      />
    </div>
  );
}

// ── Model Registry ────────────────────────────────────────────────────────────
function ModelRegistryPanel() {
  const { data, loading, reload } = useAdminFetch(() => api.adminModelRegistry());
  const [form, setForm] = useState({ feature: "", model_id: "", prompt_version: "" });
  const toast = useToast();

  async function register() {
    try {
      await api.adminRegisterModel(form);
      toast.success(`Model registered for ${form.feature}.`);
      setForm({ feature: "", model_id: "", prompt_version: "" });
      reload();
    } catch (e) { toast.error(e?.message || "Error"); }
  }

  if (loading) return <Skeleton lines={3} />;
  return (
    <div className="stack">
      <h3>AI Model & Prompt Registry</h3>
      <Card>
        <div style={{ display: "flex", gap: 8 }}>
          <input className="field-input" placeholder="Feature (e.g. recommendations)" value={form.feature} onChange={(e) => setForm((f) => ({ ...f, feature: e.target.value }))} />
          <input className="field-input" placeholder="Model ID (e.g. claude-sonnet-5)" value={form.model_id} onChange={(e) => setForm((f) => ({ ...f, model_id: e.target.value }))} />
          <input className="field-input" placeholder="Prompt v" value={form.prompt_version} onChange={(e) => setForm((f) => ({ ...f, prompt_version: e.target.value }))} style={{ width: 80 }} />
          <Button onClick={register}>Register</Button>
        </div>
      </Card>
      <DataTable
        rows={data?.entries || []}
        columns={[
          { key: "feature", label: "Feature" },
          { key: "model_id", label: "Model" },
          { key: "prompt_version", label: "Prompt v" },
          { key: "is_active", label: "Active", render: (v) => <Badge tone={v ? "success" : "neutral"}>{v ? "Active" : "Deprecated"}</Badge> },
          { key: "deployed_at", label: "Deployed", render: (v) => v ? dateBn(v) : "—" },
        ]}
      />
    </div>
  );
}

// ── AI Cost Budgets ───────────────────────────────────────────────────────────
function AiBudgetPanel() {
  const { data, loading, reload } = useAdminFetch(() => api.adminAiBudgets());
  const [form, setForm] = useState({ feature: "", monthly_token_limit: "", on_breach: "downgrade" });
  const toast = useToast();

  async function save() {
    try {
      await api.adminSetAiBudget({ ...form, monthly_token_limit: form.monthly_token_limit ? parseInt(form.monthly_token_limit) : null });
      toast.success("Budget saved.");
      setForm({ feature: "", monthly_token_limit: "", on_breach: "downgrade" });
      reload();
    } catch (e) { toast.error(e?.message || "Error"); }
  }

  if (loading) return <Skeleton lines={3} />;
  return (
    <div className="stack">
      <h3>AI Cost Control & Budgets</h3>
      <Card>
        <div style={{ display: "flex", gap: 8 }}>
          <input className="field-input" placeholder="Feature" value={form.feature} onChange={(e) => setForm((f) => ({ ...f, feature: e.target.value }))} />
          <input type="number" className="field-input" placeholder="Monthly token limit" value={form.monthly_token_limit} onChange={(e) => setForm((f) => ({ ...f, monthly_token_limit: e.target.value }))} />
          <select className="field-input" value={form.on_breach} onChange={(e) => setForm((f) => ({ ...f, on_breach: e.target.value }))}>
            {["downgrade", "manual_mode", "require_approval", "block"].map((b) => <option key={b} value={b}>{b}</option>)}
          </select>
          <Button onClick={save}>Save</Button>
        </div>
      </Card>
      <DataTable
        rows={data?.budgets || []}
        columns={[
          { key: "feature", label: "Feature" },
          { key: "monthly_token_limit", label: "Token Limit" },
          { key: "monthly_cost_limit_bdt", label: "Cost Limit (BDT)" },
          { key: "on_breach", label: "On Breach" },
        ]}
      />
    </div>
  );
}

// ── AI Outcomes ───────────────────────────────────────────────────────────────
function AiOutcomesPanel() {
  const { data, loading } = useAdminFetch(() => api.adminModelOutcomes());
  if (loading) return <Skeleton lines={4} />;
  return (
    <div className="stack">
      <h3>AI Model Outcome Monitoring</h3>
      <div className="platform-metrics">
        <Stat icon="trendingUp" label="Total Records" value={data?.total ?? 0} />
        <Stat icon="checkCircle" label="Accepted" value={data?.accepted ?? 0} />
        <Stat icon="percent" label="Acceptance Rate" value={`${data?.acceptance_rate ?? 0}%`} />
        <Stat icon="dollarSign" label="Financial Impact (BDT)" value={`৳${data?.total_financial_impact_bdt ?? 0}`} />
      </div>
      <DataTable
        rows={data?.records || []}
        columns={[
          { key: "feature", label: "Feature" },
          { key: "vertical", label: "Vertical" },
          { key: "outcome", label: "Outcome", render: (v) => <Badge tone={v === "correct" ? "success" : v === "incorrect" ? "danger" : "warning"}>{v}</Badge> },
          { key: "accepted", label: "Accepted", render: (v) => v === null ? "—" : v ? "✓" : "✗" },
          { key: "recorded_at", label: "Date", render: (v) => dateBn(v) },
        ]}
      />
    </div>
  );
}

// ── AI Kill Switch ────────────────────────────────────────────────────────────
const AI_FEATURES = [
  { key: "auto_reorder", label: "Auto Reorder Suggestions", description: "AI-generated SKU reorder recommendations" },
  { key: "churn_prediction", label: "Churn Prediction", description: "Customer inactivity risk scoring" },
  { key: "demand_forecast", label: "Demand Forecasting", description: "ML-based sales demand forecast" },
  { key: "price_recommendations", label: "Pricing Recommendations", description: "Dynamic pricing suggestions" },
  { key: "assistant", label: "Business Assistant (LLM)", description: "AI chat assistant for owners" },
  { key: "sentiment_analysis", label: "Customer Sentiment Analysis", description: "AI-based feedback analysis" },
];

function AiKillSwitchPanel() {
  const { data, loading, reload } = useAdminFetch(() => api.adminKillSwitches());
  const [editFeature, setEditFeature] = useState(null);
  const [reason, setReason] = useState("");
  const confirm = useConfirm();
  const toast = useToast();

  async function toggle(feature, currentlyDisabled) {
    const disabling = !currentlyDisabled;
    if (disabling) {
      if (!await confirm(`⚠ "${feature}" AI feature সব tenants এর জন্য DISABLE করা হবে।\n\nEmeregncy situation ছাড়া এটি করবেন না।\n\nনিশ্চিত?`)) return;
      if (!reason.trim()) { toast.error("Reason required before disabling."); return; }
    }
    try {
      await api.adminSetKillSwitch({ feature, disabled: disabling, reason: reason || `Re-enabled by admin` });
      toast.success(disabling ? `🔴 ${feature} disabled.` : `🟢 ${feature} re-enabled.`);
      setEditFeature(null); setReason("");
      reload();
    } catch (e) { toast.error(e?.message || "Error"); }
  }

  if (loading) return <Skeleton lines={3} />;

  const switchMap = {};
  (data?.switches || []).forEach(s => { switchMap[s.feature] = s; });

  const disabledCount = (data?.switches || []).filter(s => s.disabled).length;

  return (
    <div className="stack">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3>AI Kill Switch & Feature Gates</h3>
        {disabledCount > 0 && <Badge tone="danger">⚠ {disabledCount} features disabled</Badge>}
      </div>

      <Notice tone="warning">
        Kill switch activate করলে <strong>সব tenants</strong> এর জন্য সেই AI feature বন্ধ হয়ে যাবে। Manual review পর্যন্ত feature টি হিউম্যান fallback এ চলবে।
      </Notice>

      <div className="stack" style={{ gap: 8 }}>
        {AI_FEATURES.map(feat => {
          const sw = switchMap[feat.key];
          const isDisabled = sw?.disabled === true;
          const isEdit = editFeature === feat.key;

          return (
            <div key={feat.key} style={{
              borderRadius: 10, border: `1px solid ${isDisabled ? "#E63946" : "var(--color-border)"}`,
              background: isDisabled ? "#E6394611" : "var(--color-surface)",
              overflow: "hidden",
            }}>
              <div style={{ padding: "12px 16px", display: "flex", gap: 12, alignItems: "center" }}>
                {/* Status indicator */}
                <div style={{
                  width: 12, height: 12, borderRadius: "50%", flexShrink: 0,
                  background: isDisabled ? "#E63946" : "#0A8754",
                  boxShadow: isDisabled ? "0 0 0 3px #E6394622" : "0 0 0 3px #0A875422",
                }} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: 14 }}>{feat.label}</div>
                  <div style={{ fontSize: 12, color: "var(--color-muted)" }}>{feat.description}</div>
                  {isDisabled && sw.disabled_at && (
                    <div style={{ fontSize: 11, color: "#E63946", marginTop: 3 }}>
                      Disabled {dateTimeBn(sw.disabled_at)} — {sw.reason}
                    </div>
                  )}
                </div>
                <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                  <Badge tone={isDisabled ? "danger" : "success"}>{isDisabled ? "🔴 OFF" : "🟢 ON"}</Badge>
                  <Button
                    size="sm"
                    variant={isDisabled ? "ghost" : "danger"}
                    onClick={() => { setEditFeature(isEdit ? null : feat.key); setReason(""); }}
                  >
                    {isDisabled ? "Re-enable" : "Disable"}
                  </Button>
                </div>
              </div>

              {/* Inline reason + confirm */}
              {isEdit && (
                <div style={{ padding: "0 16px 14px", borderTop: "1px solid var(--color-border)" }}>
                  {!isDisabled && (
                    <Field label="Disable reason (required)">
                      <textarea className="field-input" rows={2} value={reason} onChange={e => setReason(e.target.value)} placeholder="e.g. Accuracy degradation detected, disabling pending investigation..." />
                    </Field>
                  )}
                  <Button
                    size="sm"
                    variant={isDisabled ? "primary" : "danger"}
                    onClick={() => toggle(feat.key, isDisabled)}
                    disabled={!isDisabled && !reason.trim()}
                  >
                    {isDisabled ? "✓ Re-enable feature" : "⛔ Confirm Disable"}
                  </Button>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Custom feature kill switch */}
      <details style={{ marginTop: 4 }}>
        <summary style={{ fontSize: 12, color: "var(--color-muted)", cursor: "pointer" }}>Custom feature kill switch...</summary>
        <Card style={{ marginTop: 8 }}>
          <div style={{ display: "flex", gap: 8 }}>
            <input className="field-input" style={{ flex: 1 }} placeholder="Feature key" id="custom-kill-key" />
            <textarea className="field-input" style={{ flex: 2, height: 36 }} placeholder="Reason" id="custom-kill-reason" />
            <Button size="sm" variant="danger" onClick={async () => {
              const k = document.getElementById("custom-kill-key").value;
              const r = document.getElementById("custom-kill-reason").value;
              if (!k || !r) return;
              await api.adminSetKillSwitch({ feature: k, disabled: true, reason: r });
              toast.success(`${k} disabled.`); reload();
            }}>Kill</Button>
          </div>
        </Card>
      </details>
    </div>
  );
}
