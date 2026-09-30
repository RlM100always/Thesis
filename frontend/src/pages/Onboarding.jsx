import { useState } from "react";
import { api } from "../api";
import { useAuth } from "../AuthContext";
import { useBusiness } from "../BusinessContext";
import { explain } from "../errors";
import { num } from "../format";
import { ROLE_LABELS } from "../PermissionContext";
import { BUSINESS_TYPES, EXPIRY_HINT, verticalOf } from "../verticals";
import { Badge, Button, Card, CopyField, Field, Notice } from "../ui/kit";
import { AuthLayout } from "./Login";

// The API wants a Latin, unique slug; the owner should never have to think about it.
const makeSlug = () => `shop-${Math.random().toString(36).slice(2, 8)}${Date.now().toString(36).slice(-3)}`;
const ROLE_ORDER = ["manager", "cashier", "accountant", "stock_keeper", "viewer"];
const STAFF_ROLE_LABEL = { manager: "ম্যানেজার", cashier: "ক্যাশিয়ার", accountant: "হিসাবরক্ষক", stock_keeper: "স্টক কিপার", viewer: "শুধু দেখার" };
const STEPS = ["ব্যবসা", "কাজ", "রসিদ", "কর্মী", "শেষ"];
const PAYMENT_CHOICES = [
  ["cash", "ক্যাশ"], ["bkash", "বিকাশ"], ["nagad", "নগদ"], ["bangla_qr", "বাংলা QR"],
  ["card", "কার্ড"], ["bank", "ব্যাংক"], ["cod", "ক্যাশ অন ডেলিভারি"],
];
const CHANNEL_CHOICES = [
  ["in_store", "দোকানে"], ["phone", "ফোন"], ["whatsapp", "WhatsApp"],
  ["facebook", "Facebook"], ["website", "ওয়েবসাইট"], ["delivery", "ডেলিভারি"],
];
function inviteLink(token) {
  return `${window.location.origin}${window.location.pathname}#/accept-invite?token=${encodeURIComponent(token)}`;
}

function Stepper({ step }) {
  return (
    <ol className="wizard-steps" aria-label="ধাপ">
      {STEPS.map((label, i) => (
        <li key={label} className={i === step ? "on" : i < step ? "done" : ""}>
          <span className="wizard-steps__dot">{i < step ? "✓" : i + 1}</span>{label}
        </li>
      ))}
    </ol>
  );
}

// Shown right after signup, through org creation and the first few things a
// shop actually needs: receipt details, and — if there is staff already —
// getting them invited before the owner even opens the dashboard. Every step
// past the first is skippable; nothing here can't be done later from Settings
// or Staff.
export default function Onboarding() {
  const { create, refresh, setWizardActive } = useBusiness();
  const { user, signOut } = useAuth();
  const [step, setStep] = useState(0);
  const [orgId, setOrgId] = useState(null);
  const [orgName, setOrgName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const [business, setBusiness] = useState({ name: "", sector: "grocery", default_branch_name: "প্রধান শাখা" });
  const [operations, setOperations] = useState({ business_mode: "products", payment_methods: ["cash"], sales_channels: ["in_store"] });
  const [profile, setProfile] = useState({ address: "", phone: "", vat_reg_no: "", receipt_footer: "" });
  const [staffForm, setStaffForm] = useState({ display_name: "", email: "", role: "cashier" });
  const [invited, setInvited] = useState([]); // [{ display_name, role, link? }]

  async function submitBusiness(e) {
    e.preventDefault();
    setBusy(true); setError("");
    setWizardActive(true);
    try {
      const created = await create({ ...business, name: business.name.trim(), slug: makeSlug() });
      setOrgId(created.id);
      setOrgName(created.name);
      // Receipt/profile remains the first post-creation task. Operational
      // methods have safe defaults and stay editable in Settings; putting an
      // extra mandatory screen here broke the established 8-minute signup
      // path and hid the address/staff controls users expected next.
      setStep(2);
    } catch (err) {
      setError(explain(err, { 409: "কোনো কারণে ব্যবসাটি তৈরি হয়নি। আবার চেষ্টা করুন।", 422: "ব্যবসার নাম কমপক্ষে ২ অক্ষরের দিন।" }));
    } finally { setBusy(false); }
  }

  const toggleChoice = (field, value) => setOperations((current) => ({
    ...current,
    [field]: current[field].includes(value) ? current[field].filter((item) => item !== value) : [...current[field], value],
  }));

  async function submitOperations(e) {
    e.preventDefault();
    if (!operations.payment_methods.length || !operations.sales_channels.length) {
      setError("কমপক্ষে একটি পেমেন্ট মাধ্যম ও একটি বিক্রির মাধ্যম বেছে নিন।"); return;
    }
    setBusy(true); setError("");
    try {
      await api.updateOrganizationOperations(orgId, operations);
      await refresh();
      setStep(2);
    } catch (err) { setError(explain(err)); }
    finally { setBusy(false); }
  }

  async function submitProfile(e) {
    e.preventDefault();
    const filled = Object.fromEntries(Object.entries(profile).filter(([, v]) => v.trim()));
    if (Object.keys(filled).length === 0) { setStep(3); return; }
    setBusy(true); setError("");
    try {
      await api.updateOrganization(orgId, filled);
      await refresh();   // the wizard called the API directly; the cached org needs the fresh fields too
      setStep(3);
    } catch (err) {
      setError(explain(err));
    } finally { setBusy(false); }
  }

  async function addStaff(e) {
    e.preventDefault();
    if (staffForm.display_name.trim().length < 2 || !staffForm.email.trim()) {
      setError("নাম ও সঠিক ইমেইল দিন।");
      return;
    }
    setBusy(true); setError("");
    try {
      const result = await api.inviteStaff(orgId, staffForm);
      setInvited((all) => [...all, {
        display_name: result.display_name, role: result.role,
        link: result.setup_token ? inviteLink(result.setup_token) : null,
      }]);
      setStaffForm({ display_name: "", email: "", role: "cashier" });
    } catch (err) {
      setError(explain(err, { 409: "এই ইমেইল আগেই যোগ করা আছে।", 422: "নাম ও সঠিক ইমেইল দিন।" }));
    } finally { setBusy(false); }
  }

  function finish() {
    setWizardActive(false);
    window.location.hash = "#/";
  }

  return (
    <AuthLayout
      title={step === 0 ? `স্বাগতম${user ? `, ${user.display_name.split(" ")[0]}` : ""}!` : orgName}
      subtitle={[
        "আপনার ব্যবসার তথ্য দিন। পরে সবকিছু বদলানো যাবে।",
        "আপনি কী বিক্রি করেন এবং কীভাবে টাকা নেন—কাজের জায়গা সেই অনুযায়ী সাজবে।",
        "রসিদে কী ছাপা হবে? এড়িয়ে গেলে পরে সেটিংস থেকে দেওয়া যাবে।",
        "কোনো কর্মী থাকলে এখনই যোগ করুন, বা পরে করুন।",
        "প্রস্তুত! এখন থেকে ব্যবসা চালানো শুরু করুন।",
      ][step]}
    >
      <Stepper step={step} />
      <Card>
        {step === 0 && (
          <form className="ui-form" onSubmit={submitBusiness}>
            <Field label="ব্যবসার নাম" required hint="যেমন: রহমান স্টোর, করিম ফার্মেসি, নূর ফ্যাশন">
              <input value={business.name} onChange={(e) => setBusiness({ ...business, name: e.target.value })} minLength={2} maxLength={160} autoComplete="organization" autoFocus />
            </Field>
            <Field label="কী ধরনের ব্যবসা?" required hint={verticalOf(business.sector).expiry ? EXPIRY_HINT.on : EXPIRY_HINT.off}>
              <select value={business.sector} onChange={(e) => setBusiness({ ...business, sector: e.target.value })}>
                {BUSINESS_TYPES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </Field>
            <Field label="প্রথম শাখার নাম" required hint="একটাই দোকান হলে ‘প্রধান শাখা’ই থাক">
              <input value={business.default_branch_name} onChange={(e) => setBusiness({ ...business, default_branch_name: e.target.value })} minLength={2} maxLength={120} />
            </Field>
            {error && <Notice tone="danger">{error}</Notice>}
            <Button type="submit" block loading={busy}>ব্যবসা তৈরি করুন</Button>
          </form>
        )}

        {step === 1 && (
          <form className="ui-form" onSubmit={submitOperations}>
            <Field label="আপনার ব্যবসায় কী বিক্রি হয়?" required>
              <div className="choice-grid choice-grid--3">
                {[["products", "পণ্য"], ["services", "সেবা"], ["both", "পণ্য ও সেবা"]].map(([value, label]) => (
                  <button type="button" key={value} className={`choice-tile ${operations.business_mode === value ? "on" : ""}`}
                          onClick={() => setOperations({ ...operations, business_mode: value })}><strong>{label}</strong></button>
                ))}
              </div>
            </Field>
            <Field label="কীভাবে পেমেন্ট নেন?" required hint="POS-এ শুধু বাছাই করা মাধ্যমগুলো দেখা যাবে।">
              <div className="choice-grid">
                {PAYMENT_CHOICES.map(([value, label]) => (
                  <label key={value} className={`choice-check ${operations.payment_methods.includes(value) ? "on" : ""}`}>
                    <input type="checkbox" checked={operations.payment_methods.includes(value)} onChange={() => toggleChoice("payment_methods", value)} />{label}
                  </label>
                ))}
              </div>
            </Field>
            <Field label="কোথা থেকে অর্ডার আসে?" required>
              <div className="choice-grid">
                {CHANNEL_CHOICES.map(([value, label]) => (
                  <label key={value} className={`choice-check ${operations.sales_channels.includes(value) ? "on" : ""}`}>
                    <input type="checkbox" checked={operations.sales_channels.includes(value)} onChange={() => toggleChoice("sales_channels", value)} />{label}
                  </label>
                ))}
              </div>
            </Field>
            {error && <Notice tone="danger">{error}</Notice>}
            <Button type="submit" block loading={busy}>কাজের ধরন সংরক্ষণ করুন</Button>
          </form>
        )}

        {step === 2 && (
          <form className="ui-form" onSubmit={submitProfile}>
            <Field label="দোকানের ঠিকানা"><input value={profile.address} onChange={(e) => setProfile({ ...profile, address: e.target.value })} maxLength={300} /></Field>
            <Field label="ফোন নম্বর"><input value={profile.phone} onChange={(e) => setProfile({ ...profile, phone: e.target.value })} maxLength={30} inputMode="tel" /></Field>
            <Field label="VAT / BIN নম্বর" hint="না থাকলে ফাঁকা রাখুন"><input value={profile.vat_reg_no} onChange={(e) => setProfile({ ...profile, vat_reg_no: e.target.value })} maxLength={40} /></Field>
            <Field label="রসিদের শেষের লেখা" hint="যেমন: আবার আসবেন"><input value={profile.receipt_footer} onChange={(e) => setProfile({ ...profile, receipt_footer: e.target.value })} maxLength={200} /></Field>
            {error && <Notice tone="danger">{error}</Notice>}
            <div className="row">
              <Button type="submit" loading={busy}>সংরক্ষণ করে এগিয়ে যান</Button>
              <Button type="button" variant="ghost" onClick={() => setStep(3)}>এড়িয়ে যান</Button>
            </div>
          </form>
        )}

        {step === 3 && (
          <div className="ui-form">
            {invited.length > 0 && (
              <div className="ui-form" style={{ gap: 8 }}>
                {invited.map((p, i) => (
                  <Notice key={i} tone="success" title={`${p.display_name} — ${STAFF_ROLE_LABEL[p.role] || ROLE_LABELS[p.role] || p.role}`}>
                    {p.link ? <CopyField value={p.link} label="পাসওয়ার্ড লিংক" /> : "এই ইমেইলের অ্যাকাউন্ট আগে থেকেই আছে — তাঁর আগের পাসওয়ার্ডই কাজ করবে।"}
                  </Notice>
                ))}
              </div>
            )}
            <form className="ui-form" onSubmit={addStaff}>
              <div className="ui-form ui-form--2">
                <Field label="নাম"><input value={staffForm.display_name} onChange={(e) => setStaffForm({ ...staffForm, display_name: e.target.value })} minLength={2} maxLength={120} /></Field>
                <Field label="ইমেইল"><input type="email" value={staffForm.email} onChange={(e) => setStaffForm({ ...staffForm, email: e.target.value })} maxLength={254} /></Field>
              </div>
              <Field label="ভূমিকা">
                <select value={staffForm.role} onChange={(e) => setStaffForm({ ...staffForm, role: e.target.value })}>
                  {ROLE_ORDER.map((r) => <option key={r} value={r}>{STAFF_ROLE_LABEL[r]}</option>)}
                </select>
              </Field>
              {error && <Notice tone="danger">{error}</Notice>}
              <Button type="submit" variant="secondary" loading={busy}>কর্মী যোগ করুন</Button>
            </form>
            <div className="row">
              <Button onClick={() => setStep(4)}>{invited.length > 0 ? "শেষ ধাপে যান" : "এড়িয়ে যান"}</Button>
            </div>
          </div>
        )}

        {step === 4 && (
          <div className="ui-form">
            <Notice tone="success" title="প্রস্তুত!">
              {orgName} তৈরি হয়ে গেছে। {invited.length > 0 && <>{num(invited.length)} জন কর্মী যোগ হয়েছে। </>}
              যেকোনো কিছু পরে সেটিংস বা কর্মী পাতা থেকে বদলাতে পারবেন।
            </Notice>
            {invited.length > 0 && <Badge tone="success" icon="check">{invited.map((p) => p.display_name).join(", ")}</Badge>}
            <Button block onClick={finish}>ব্যবসা ব্যবহার শুরু করুন</Button>
          </div>
        )}
      </Card>
      {step === 0 && (
        <p className="auth-switch">
          অন্য কারও ব্যবসায় যোগ দিতে এসেছেন? মালিকের পাঠানো লিংকটি খুলুন।
          {" "}<button type="button" className="link-btn" onClick={signOut}>লগআউট করুন</button>
        </p>
      )}
    </AuthLayout>
  );
}
