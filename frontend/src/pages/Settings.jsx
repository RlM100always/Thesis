import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { useBusiness } from "../BusinessContext";
import { explain } from "../errors";
import { dateBn, num } from "../format";
import { ROLE_LABELS, usePermissions } from "../PermissionContext";
import DataTable from "../ui/DataTable";
import { Badge, Button, Card, EmptyState, Field, Modal, Notice, PageHeader } from "../ui/kit";
import { useToast } from "../ui/Toast";
import { BUSINESS_TYPES } from "../verticals";

const TYPE_LABEL = Object.fromEntries(BUSINESS_TYPES);
const SALES_ROLES = [
  ["invoice_number", "চালান নম্বর"], ["date", "তারিখ"], ["sku", "পণ্য কোড (SKU)"],
  ["quantity", "পরিমাণ"], ["unit_price", "প্রতি ইউনিট দাম"],
];
const makeSlug = () => `shop-${Math.random().toString(36).slice(2, 8)}${Date.now().toString(36).slice(-3)}`;

// The owner's own past sales, kept as a durable record and usable to train a
// model. Separate from the one-off "upload and score" tool.
function ImportCard({ orgId, canImport, canExport }) {
  const toast = useToast();
  const fileRef = useRef(null);
  const [batch, setBatch] = useState(null);
  const [mapping, setMapping] = useState({});
  const [report, setReport] = useState(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  const reset = () => { setBatch(null); setMapping({}); setReport(null); setError(""); if (fileRef.current) fileRef.current.value = ""; };

  async function pick(file) {
    if (!file) return;
    setBusy("read"); setReport(null); setError("");
    try {
      const data = await api.importSalesFile(orgId, file);
      setBatch(data);
      const guess = {};
      for (const [key] of SALES_ROLES) {
        const hit = data.columns.find((c) => c.toLowerCase().replace(/[^a-z]/g, "") === key.replace(/_/g, ""));
        if (hit) guess[key] = hit;
      }
      setMapping(guess);
    } catch (e) {
      setError(explain(e, { 400: "ফাইলটি পড়া যায়নি। শুধু CSV বা Excel (.xlsx) দিন, আর ফাইলে অন্তত একটি সারি থাকতে হবে।", 413: "ফাইল খুব বড়। ২৫ MB-র মধ্যে রাখুন।" }));
      setBatch(null);
    } finally {
      setBusy("");
    }
  }

  async function validate() {
    setBusy("validate"); setError("");
    try {
      setReport(await api.validateSalesImport(orgId, batch.id, mapping));
    } catch (e) {
      setError(explain(e, { 422: "সবগুলো ঘরের জন্য ফাইলের কলাম বেছে নিন।" }));
    } finally {
      setBusy("");
    }
  }

  async function download() {
    setBusy("export");
    try {
      const blob = await api.exportSalesDataset(orgId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = "bsmart_sales_anonymized.csv"; a.click();
      URL.revokeObjectURL(url);
      toast.success("ডেটাসেট নামানো হয়েছে।");
    } catch (e) {
      toast.error(explain(e, { 403: "ডেটা নামানোর অনুমতি আপনার নেই।" }));
    } finally {
      setBusy("");
    }
  }

  const ready = SALES_ROLES.every(([key]) => mapping[key]);

  return (
    <Card title="আগের বিক্রির ইতিহাস আমদানি" subtitle="পুরোনো বিক্রির CSV বা Excel ফাইল দিন। এটি আপনার রেকর্ড হিসেবে জমা থাকবে এবং AI মডেল শেখাতে কাজে লাগবে।">
      {!canImport ? <Notice tone="info">ফাইল আমদানির অনুমতি শুধু মালিক, ম্যানেজার ও হিসাবরক্ষকের।</Notice> : !batch ? (
        <div className="ui-form">
          <input ref={fileRef} type="file" accept=".csv,.xlsx" onChange={(e) => pick(e.target.files?.[0])} aria-label="বিক্রির ফাইল বেছে নিন" />
          {busy === "read" && <p className="muted" style={{ margin: 0 }}>ফাইল পড়া হচ্ছে…</p>}
          {error && <Notice tone="danger">{error}</Notice>}
        </div>
      ) : (
        <div className="ui-form">
          <Notice tone="info"><strong>{batch.filename}</strong> · {num(batch.row_count)} সারি। ফাইলের কোন কলামে কী আছে, বেছে দিন।</Notice>
          <div className="ui-form ui-form--2">
            {SALES_ROLES.map(([key, label]) => (
              <Field key={key} label={label} required>
                <select value={mapping[key] || ""} onChange={(e) => setMapping({ ...mapping, [key]: e.target.value })}>
                  <option value="">— বেছে নিন —</option>
                  {batch.columns.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </Field>
            ))}
          </div>
          <div className="row">
            <Button disabled={!ready} loading={busy === "validate"} onClick={validate}>যাচাই করুন</Button>
            <Button variant="secondary" onClick={reset}>অন্য ফাইল</Button>
          </div>
          {error && <Notice tone="danger">{error}</Notice>}
          {report && (
            <Notice tone={report.valid ? "success" : "danger"} title={report.valid ? "যাচাই সফল" : "যাচাই ব্যর্থ"}>
              {num(report.rows)} সারি · {num(report.invoices)} চালান{report.date_from && ` · ${dateBn(report.date_from)} থেকে ${dateBn(report.date_to)}`}
              {report.errors.length > 0 && <ul>{report.errors.map((x) => <li key={x}>{x}</li>)}</ul>}
              {report.unknown_sku_count > 0 && <p style={{ margin: "6px 0 0" }}>{num(report.unknown_sku_count)}টি পণ্য কোড আপনার পণ্য তালিকায় নেই — আগে <a href="#/products">পণ্য যোগ করুন</a>।</p>}
              {report.valid && canExport && <div style={{ marginTop: 10 }}><Button variant="secondary" loading={busy === "export"} onClick={download}>ডেটাসেট নামান (CSV)</Button></div>}
            </Notice>
          )}
        </div>
      )}
    </Card>
  );
}

// Printed on every receipt. Blank fields are simply left off.
function ProfileCard({ org, canEdit, onSaved }) {
  const toast = useToast();
  const [form, setForm] = useState({ address: org.address || "", phone: org.phone || "", vat_reg_no: org.vat_reg_no || "", receipt_footer: org.receipt_footer || "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function save(e) {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      await api.updateOrganization(org.id, form);
      await onSaved();
      toast.success("দোকানের তথ্য সংরক্ষিত হয়েছে। এখন থেকে রসিদে এটি ছাপা হবে।");
    } catch (err) {
      setError(explain(err, { 403: "দোকানের তথ্য বদলানোর অনুমতি শুধু মালিকের।" }));
    } finally { setBusy(false); }
  }

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });
  return (
    <Card title="রসিদের তথ্য" subtitle="ঠিকানা, ফোন ও VAT নম্বর রসিদের মাথায় ছাপা হয়; নিচের লেখাটি রসিদের শেষে।">
      <form className="ui-form" onSubmit={save}>
        <div className="ui-form ui-form--2">
          <Field label="দোকানের ঠিকানা"><input value={form.address} onChange={set("address")} disabled={!canEdit} maxLength={300} /></Field>
          <Field label="ফোন নম্বর"><input value={form.phone} onChange={set("phone")} disabled={!canEdit} maxLength={30} inputMode="tel" /></Field>
          <Field label="VAT / BIN নম্বর" hint="না থাকলে ফাঁকা রাখুন"><input value={form.vat_reg_no} onChange={set("vat_reg_no")} disabled={!canEdit} maxLength={40} /></Field>
          <Field label="রসিদের শেষের লেখা" hint="যেমন: আবার আসবেন"><input value={form.receipt_footer} onChange={set("receipt_footer")} disabled={!canEdit} maxLength={200} /></Field>
        </div>
        {error && <Notice tone="danger">{error}</Notice>}
        {canEdit ? <div><Button type="submit" loading={busy}>সংরক্ষণ করুন</Button></div> : <Notice tone="info">এই তথ্য শুধু মালিক বদলাতে পারেন।</Notice>}
      </form>
    </Card>
  );
}

function TrainCard({ orgId, canTrain }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  async function train() {
    setBusy(true); setResult(null); setError("");
    try {
      const r = await api.trainDemandModel(orgId);
      setResult(r.forecast);
      toast.success("মডেল শেখা শেষ। এখন থেকে ‘আজকের করণীয়’-তে এই পূর্বাভাস ব্যবহার হবে।");
    } catch (e) {
      // The API explains exactly why (too little history); that reason is worth showing as-is.
      setError(e.status === 422 || e.status === 400
        ? "এখনো যথেষ্ট বিক্রির ইতিহাস নেই। মডেল শেখাতে কমপক্ষে ৯০ দিনের বিক্রি ও ৫০০+ বিক্রির লাইন লাগে। কম তথ্যে ভুয়া ফলাফল দেখানো হয় না।"
        : explain(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="নিজের তথ্য থেকে AI মডেল শেখান" subtitle="এখন পর্যন্ত লেখা সব বিক্রি থেকে একটি পূর্বাভাস মডেল তৈরি হবে। কমপক্ষে ৯০ দিনের ইতিহাস ও ৫০০+ বিক্রির লাইন লাগে।">
      {!canTrain ? <Notice tone="info">মডেল শেখানোর অনুমতি শুধু মালিক, ম্যানেজার ও হিসাবরক্ষকের।</Notice> : (
        <div className="ui-form">
          <div><Button icon="zap" loading={busy} onClick={train}>AI মডেল শেখান</Button></div>
          {error && <Notice tone="warn">{error}</Notice>}
          {result && (
            <Notice tone="success" title="মডেলের ভুলের হার (কম মানে ভালো)">
              শেখা মডেল {num((result.hist_gradient_boosting.wape * 100).toFixed(1))}% · সাধারণ হিসাব (গত সপ্তাহের পুনরাবৃত্তি) {num((result.seasonal_naive_7.wape * 100).toFixed(1))}%
            </Notice>
          )}
        </div>
      )}
    </Card>
  );
}

export default function SettingsPage() {
  const { active, organizations, select, create, refresh } = useBusiness();
  const { can, role } = usePermissions();
  const toast = useToast();
  const orgId = active?.id;

  const [branches, setBranches] = useState(null);
  const [addingBranch, setAddingBranch] = useState(false);
  const [branch, setBranch] = useState({ code: "", name: "", division: "", district: "", address: "" });
  const [addingBusiness, setAddingBusiness] = useState(false);
  const [business, setBusiness] = useState({ name: "", sector: "grocery", default_branch_name: "প্রধান শাখা" });
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState("");

  const loadBranches = useCallback(() => (orgId ? api.branches(orgId).then(setBranches).catch(() => setBranches([])) : null), [orgId]);
  useEffect(() => { loadBranches(); }, [loadBranches]);

  async function saveBranch(e) {
    e.preventDefault();
    setBusy(true); setFormError("");
    try {
      await api.createBranch(orgId, { ...branch, division: branch.division || null, district: branch.district || null, address: branch.address || null });
      toast.success("শাখা যোগ হয়েছে।");
      setAddingBranch(false);
      setBranch({ code: "", name: "", division: "", district: "", address: "" });
      loadBranches();
    } catch (err) {
      setFormError(explain(err, { 409: "এই কোড দিয়ে আগেই একটি শাখা আছে।", 403: "শাখা যোগ করার অনুমতি শুধু মালিক ও ম্যানেজারের।", 422: "কোড ও নাম দিন।" }));
    } finally { setBusy(false); }
  }

  async function saveBusiness(e) {
    e.preventDefault();
    setBusy(true); setFormError("");
    try {
      await create({ ...business, name: business.name.trim(), slug: makeSlug() });
      toast.success("নতুন ব্যবসা তৈরি হয়েছে। এখন এটিই চালু আছে।");
      setAddingBusiness(false);
      setBusiness({ name: "", sector: "grocery", default_branch_name: "প্রধান শাখা" });
    } catch (err) {
      setFormError(explain(err, { 422: "ব্যবসার নাম কমপক্ষে ২ অক্ষরের দিন।" }));
    } finally { setBusy(false); }
  }

  if (!active) return null;

  return (
    <div className="page stack">
      <PageHeader title="ব্যবসা ও শাখা" subtitle="আপনার ব্যবসার তথ্য, শাখা এবং পুরোনো তথ্য আমদানি।" />

      <Card title="আমার ব্যবসা" actions={<Button size="sm" variant="secondary" icon="plus" onClick={() => { setFormError(""); setAddingBusiness(true); }}>আরেকটি ব্যবসা যোগ করুন</Button>}>
        <div className="summary">
          <div><span>নাম</span><strong>{active.name}</strong></div>
          <div><span>ধরন</span><strong>{TYPE_LABEL[active.sector] || active.sector}</strong></div>
          <div><span>আপনার ভূমিকা</span><strong>{ROLE_LABELS[role || active.role] || active.role}</strong></div>
        </div>
        {organizations.length > 1 && (
          <div style={{ marginTop: 16 }}>
            <Field label="অন্য ব্যবসায় যান">
              <select value={active.id} onChange={(e) => select(e.target.value)}>{organizations.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}</select>
            </Field>
          </div>
        )}
      </Card>

      <Card pad={false} title="শাখা" actions={can("branches:write") && <Button size="sm" icon="plus" onClick={() => { setFormError(""); setAddingBranch(true); }}>নতুন শাখা</Button>}>
        <DataTable rowKey="id" loading={branches === null} rows={branches || []} caption="শাখার তালিকা"
                   columns={[
                     { key: "name", label: "শাখা", primary: true, render: (b) => <div><strong>{b.name}</strong><div className="muted" style={{ fontSize: 12.5 }}>{b.code}</div></div> },
                     { key: "place", label: "এলাকা", render: (b) => [b.district, b.division].filter(Boolean).join(", ") || "—" },
                     { key: "active", label: "অবস্থা", render: (b) => (b.active ? <Badge tone="success" icon="check">চালু</Badge> : <Badge>বন্ধ</Badge>) },
                   ]}
                   empty={<EmptyState icon="sliders" title="কোনো শাখা নেই" />} />
      </Card>

      <ProfileCard key={active.id} org={active} canEdit={can("settings:write")} onSaved={refresh} />

      <ImportCard orgId={orgId} canImport={can("imports:write")} canExport={can("dataset:export")} />
      <TrainCard orgId={orgId} canTrain={can("model:train")} />

      <Modal open={addingBranch} title="নতুন শাখা" onClose={() => setAddingBranch(false)}
             footer={<><Button variant="secondary" onClick={() => setAddingBranch(false)}>বাতিল</Button><Button type="submit" form="branch-form" loading={busy}>শাখা যোগ করুন</Button></>}>
        <form id="branch-form" className="ui-form" onSubmit={saveBranch}>
          <div className="ui-form ui-form--2">
            <Field label="শাখার কোড" required hint="যেমন MIRPUR"><input value={branch.code} onChange={(e) => setBranch({ ...branch, code: e.target.value })} autoComplete="off" /></Field>
            <Field label="শাখার নাম" required><input value={branch.name} onChange={(e) => setBranch({ ...branch, name: e.target.value })} minLength={2} autoComplete="off" /></Field>
            <Field label="বিভাগ"><input value={branch.division} onChange={(e) => setBranch({ ...branch, division: e.target.value })} /></Field>
            <Field label="জেলা"><input value={branch.district} onChange={(e) => setBranch({ ...branch, district: e.target.value })} /></Field>
          </div>
          <Field label="ঠিকানা"><input value={branch.address} onChange={(e) => setBranch({ ...branch, address: e.target.value })} /></Field>
          {formError && <Notice tone="danger">{formError}</Notice>}
        </form>
      </Modal>

      <Modal open={addingBusiness} title="আরেকটি ব্যবসা যোগ করুন" onClose={() => setAddingBusiness(false)}
             footer={<><Button variant="secondary" onClick={() => setAddingBusiness(false)}>বাতিল</Button><Button type="submit" form="business-form" loading={busy}>ব্যবসা তৈরি করুন</Button></>}>
        <form id="business-form" className="ui-form" onSubmit={saveBusiness}>
          <Field label="ব্যবসার নাম" required><input value={business.name} onChange={(e) => setBusiness({ ...business, name: e.target.value })} minLength={2} autoComplete="off" /></Field>
          <Field label="ধরন"><select value={business.sector} onChange={(e) => setBusiness({ ...business, sector: e.target.value })}>{BUSINESS_TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></Field>
          <Field label="প্রথম শাখার নাম"><input value={business.default_branch_name} onChange={(e) => setBusiness({ ...business, default_branch_name: e.target.value })} minLength={2} /></Field>
          {formError && <Notice tone="danger">{formError}</Notice>}
        </form>
      </Modal>
    </div>
  );
}
