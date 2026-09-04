import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { useBusiness } from "../BusinessContext";
import { FeedbackBanner, useFeedback } from "../components/FeedbackBanner";

const SALES_ROLES = [
  { key: "invoice_number", label: "চালান নম্বর" },
  { key: "date", label: "তারিখ" },
  { key: "sku", label: "পণ্য কোড (SKU)" },
  { key: "quantity", label: "পরিমাণ" },
  { key: "unit_price", label: "প্রতি ইউনিট দাম" },
];

// Feeds the organization's own POS history into the durable import schema
// (api/data_import_routes.py) for provenance + eventual ml/real_pipeline.py
// training — separate from the quick one-off scoring on the Upload page.
function ImportSalesSection({ orgId }) {
  const [batch, setBatch] = useState(null);
  const [mapping, setMapping] = useState({});
  const [report, setReport] = useState(null);
  const [busy, setBusy] = useState("");
  const [feedback, showFeedback] = useFeedback();
  const fileRef = useRef(null);

  const reset = () => { setBatch(null); setMapping({}); setReport(null); };

  const pickFile = async (file) => {
    if (!file || !orgId) return;
    setBusy("ফাইল পড়া হচ্ছে…"); setReport(null);
    try {
      const data = await api.importSalesFile(orgId, file);
      setBatch(data);
      const guess = {};
      for (const role of SALES_ROLES) {
        const hit = data.columns.find((c) => c.toLowerCase().replace(/[^a-z]/g, "") === role.key.replace(/_/g, ""));
        if (hit) guess[role.key] = hit;
      }
      setMapping(guess);
    } catch (e) {
      showFeedback("error", e.message);
      setBatch(null);
    } finally {
      setBusy("");
    }
  };

  const ready = SALES_ROLES.every((r) => mapping[r.key]);

  const validate = async () => {
    setBusy("যাচাই হচ্ছে…");
    try {
      setReport(await api.validateSalesImport(orgId, batch.id, mapping));
    } catch (e) {
      showFeedback("error", e.message);
    } finally {
      setBusy("");
    }
  };

  const exportDataset = async () => {
    setBusy("তৈরি হচ্ছে…");
    try {
      const blob = await api.exportSalesDataset(orgId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = "bsmart_sales_anonymized.csv"; a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      showFeedback("error", e.message);
    } finally {
      setBusy("");
    }
  };

  return (
    <section className="card">
      <h3>প্রকৃত বিক্রয় ইতিহাস আমদানি</h3>
      <p className="hint">
        আগের বিক্রয়ের CSV/Excel ফাইল আপলোড করুন — এটি আপনার ব্যবসার রেকর্ড হিসেবে
        সংরক্ষিত হবে এবং AI মডেল প্রশিক্ষণে ব্যবহার করা যাবে।
      </p>
      <FeedbackBanner feedback={feedback} />
      {!batch ? (
        <>
          <input
            ref={fileRef} type="file" accept=".csv,.xlsx"
            onChange={(e) => pickFile(e.target.files?.[0])}
          />
          {busy && <p className="hint">{busy}</p>}
        </>
      ) : (
        <>
          <p><strong>{batch.filename}</strong> · {batch.row_count.toLocaleString()} সারি · অবস্থা: {batch.status}</p>
          <div className="mapping-grid">
            {SALES_ROLES.map((role) => (
              <label key={role.key} className="mapping-row">
                <span className="mapping-label">{role.label}</span>
                <select
                  value={mapping[role.key] || ""}
                  onChange={(e) => setMapping({ ...mapping, [role.key]: e.target.value })}
                >
                  <option value="">— নির্বাচন করুন —</option>
                  {batch.columns.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </label>
            ))}
          </div>
          <button type="button" className="btn-primary" disabled={!ready || !!busy} onClick={validate}>
            {busy || "যাচাই করুন"}
          </button>
          <button type="button" className="btn-secondary" onClick={reset}>অন্য ফাইল</button>
          {report && (
            <div className={`callout ${report.valid ? "green" : "danger"}`}>
              <strong>{report.valid ? "যাচাই সফল" : "যাচাই ব্যর্থ"}</strong>
              <p>
                {report.rows.toLocaleString()} সারি · {report.invoices.toLocaleString()} চালান
                {report.date_from && ` · ${report.date_from} থেকে ${report.date_to}`}
              </p>
              {report.errors.length > 0 && <ul>{report.errors.map((e) => <li key={e}>{e}</li>)}</ul>}
              {report.unknown_sku_count > 0 && (
                <p className="hint">{report.unknown_sku_count}টি SKU পণ্য তালিকায় নেই — আগে পণ্য যোগ করুন।</p>
              )}
              {report.valid && (
                <button type="button" className="btn-secondary" onClick={exportDataset} disabled={!!busy}>
                  {busy || "ডেটাসেট ডাউনলোড করুন (CSV)"}
                </button>
              )}
            </div>
          )}
        </>
      )}
    </section>
  );
}

// The one remaining manual step from the dynamic data flow: turning an
// organization's own recorded sales into a trained model that
// /api/app/recommendations then serves automatically. No CLI, no file
// export/import round-trip — one button.
function TrainModelSection({ orgId }) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [feedback, showFeedback] = useFeedback();

  const train = async () => {
    setBusy(true); setResult(null);
    try {
      const r = await api.trainDemandModel(orgId);
      setResult(r.forecast);
      showFeedback("success", "মডেল প্রশিক্ষণ সম্পন্ন হয়েছে — এখন থেকে 'আজকের করণীয়' পাতায় এই পূর্বাভাস ব্যবহৃত হবে।");
    } catch (e) {
      showFeedback("error", e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="card">
      <h3>নিজের ডেটা দিয়ে AI মডেল প্রশিক্ষণ</h3>
      <p className="hint">
        আপনার ব্যবসার এখন পর্যন্ত রেকর্ড করা সব বিক্রি ব্যবহার করে একটি পূর্বাভাস মডেল
        তৈরি হবে। কমপক্ষে ৯০ দিনের ইতিহাস ও ৫০০+ বিক্রির লাইন থাকলে এটি কাজ করবে —
        কম থাকলে স্পষ্ট কারণ জানানো হবে, কখনো ভুয়া ফলাফল দেখানো হবে না।
      </p>
      <FeedbackBanner feedback={feedback} />
      <button type="button" className="btn-primary" onClick={train} disabled={busy}>
        {busy ? "প্রশিক্ষণ চলছে…" : "AI মডেল ট্রেন করুন"}
      </button>
      {result && (
        <div className="callout green">
          <strong>মডেলের নির্ভুলতা (WAPE, কম মানে ভালো)</strong>
          <p>
            প্রশিক্ষিত মডেল: {(result.hist_gradient_boosting.wape * 100).toFixed(1)}%
            {" · "}সাধারণ হিসাব (গত সপ্তাহের পুনরাবৃত্তি): {(result.seasonal_naive_7.wape * 100).toFixed(1)}%
          </p>
        </div>
      )}
    </section>
  );
}

export default function BusinessSetup() {
  const { active, organizations, select, loading, error, create } = useBusiness();
  const [form, setForm] = useState({ name: "", slug: "", sector: "retail", size_class: "small", default_branch_name: "প্রধান শাখা" });
  const [saving, setSaving] = useState(false);
  const [feedback, showFeedback] = useFeedback();
  const [branches, setBranches] = useState([]);
  const [branch, setBranch] = useState({ code: "", name: "", division: "", district: "", address: "" });
  const activeId = active?.id;

  useEffect(() => { if (activeId) api.branches(activeId).then(setBranches); }, [activeId]);

  const change = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await create(form);
      showFeedback("success", "ব্যবসা সফলভাবে তৈরি হয়েছে।");
    } catch (err) {
      showFeedback("error", err.message);
    } finally {
      setSaving(false);
    }
  };

  const addBranch = async (e) => {
    e.preventDefault();
    try {
      await api.createBranch(active.id, {
        ...branch, division: branch.division || null, district: branch.district || null, address: branch.address || null,
      });
      setBranches(await api.branches(active.id));
      setBranch({ code: "", name: "", division: "", district: "", address: "" });
      showFeedback("success", "শাখা যোগ হয়েছে।");
    } catch (err) {
      showFeedback("error", err.message);
    }
  };

  if (loading) return <div className="page"><p>লোড হচ্ছে…</p></div>;

  return (
    <div className="page">
      <header className="page-head">
        <h2>ব্যবসা সেটআপ</h2>
        <p className="subtitle">বাংলাদেশি SME-এর দৈনিক কার্যক্রম এখান থেকে শুরু করুন।</p>
      </header>
      <FeedbackBanner feedback={feedback} />
      {error && <div className="error-box">{error}</div>}

      {active && (
        <>
          <div className="card">
            <h3>বর্তমান ব্যবসা</h3>
            <label>
              আপনার ব্যবসাসমূহ
              <select value={active.id} onChange={(e) => select(e.target.value)}>
                {organizations.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
              </select>
            </label>
            <p><strong>{active.name}</strong> · {active.sector} · {active.role}</p>
          </div>

          <form className="card form-grid" onSubmit={addBranch}>
            <h3>শাখা ব্যবস্থাপনা</h3>
            <label>শাখা কোড<input value={branch.code} onChange={(e) => setBranch({ ...branch, code: e.target.value })} required /></label>
            <label>শাখার নাম<input value={branch.name} onChange={(e) => setBranch({ ...branch, name: e.target.value })} required /></label>
            <label>বিভাগ<input value={branch.division} onChange={(e) => setBranch({ ...branch, division: e.target.value })} /></label>
            <label>জেলা<input value={branch.district} onChange={(e) => setBranch({ ...branch, district: e.target.value })} /></label>
            <button className="btn-primary">শাখা যোগ করুন</button>
            <p>{branches.map((b) => `${b.name} (${b.code})`).join(" · ")}</p>
          </form>

          <ImportSalesSection orgId={active.id} />
          <TrainModelSection orgId={active.id} />
        </>
      )}

      <form className="card form-grid" onSubmit={submit}>
        <h3>নতুন ব্যবসা</h3>
        <label>ব্যবসার নাম<input value={form.name} onChange={change("name")} required /></label>
        <label>ইউনিক কোড<input value={form.slug} onChange={change("slug")} pattern="[a-z0-9]+(?:-[a-z0-9]+)*" placeholder="rakib-store" required /></label>
        <label>
          খাত
          <select value={form.sector} onChange={change("sector")}>
            <option value="retail">রিটেইল</option>
            <option value="ecommerce">ই-কমার্স</option>
            <option value="service">সেবা</option>
          </select>
        </label>
        <label>
          SME শ্রেণি
          <select value={form.size_class} onChange={change("size_class")}>
            <option value="cottage">কুটির</option>
            <option value="micro">মাইক্রো</option>
            <option value="small">ক্ষুদ্র</option>
            <option value="medium">মাঝারি</option>
          </select>
        </label>
        <label>প্রধান শাখার নাম<input value={form.default_branch_name} onChange={change("default_branch_name")} required /></label>
        <button className="btn-primary" disabled={saving}>{saving ? "তৈরি হচ্ছে…" : "ব্যবসা তৈরি করুন"}</button>
      </form>
    </div>
  );
}
