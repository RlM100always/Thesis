// Bring your own data: upload a sales CSV, map four columns, get a ranked
// list of customers to contact.
//
// Three steps in one page rather than a wizard, so the user can always see
// what they chose two steps ago. The mapping step exists because the models
// consume engineered customer-level features, not raw transactions — see the
// module docstring in upload_service.py.

import { useCallback, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, formatBDT } from "../api";
import { FeedbackBanner, useFeedback } from "../components/FeedbackBanner";
import { useWorkspace } from "../WorkspaceContext";

const ROLES = [
  { key: "customer_id", label: "কাস্টমার আইডি", hint: "কে কিনেছে — নাম, ফোন নম্বর বা কোড", required: true },
  { key: "date", label: "কেনার তারিখ", hint: "কবে বিক্রি হয়েছে", required: true },
  { key: "amount", label: "পরিশোধিত পরিমাণ", hint: "সেই বিক্রির মোট টাকা", required: true },
  { key: "quantity", label: "পরিমাণ", hint: "কতগুলো আইটেম (ঐচ্ছিক)", required: false },
  { key: "product", label: "পণ্যের নাম", hint: "কী বিক্রি হয়েছে — সেরা-বিক্রিত পণ্য দেখাবে (ঐচ্ছিক)", required: false },
];

const BAND_TONE = { High: "danger", Medium: "warn", Low: "ok" };
const BAND_LABEL = { High: "উচ্চ", Medium: "মাঝারি", Low: "কম" };

export default function Upload() {
  const [parsed, setParsed] = useState(null);
  const [mapping, setMapping] = useState({});
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [showAll, setShowAll] = useState(false);
  const fileRef = useRef(null);
  const { open: openWorkspace } = useWorkspace();

  const reset = () => {
    setParsed(null); setMapping({}); setResult(null); setError(null); setShowAll(false);
  };

  const handleFile = useCallback(async (file) => {
    if (!file) return;
    setBusy("ফাইল পড়া হচ্ছে…"); setError(null); setResult(null);
    try {
      const data = await api.uploadFile(file);
      setParsed(data);
      setMapping(data.suggested_mapping || {});
    } catch (e) {
      setError(e.message); setParsed(null);
    } finally {
      setBusy("");
    }
  }, []);

  const ready = ROLES.filter((r) => r.required).every((r) => mapping[r.key]);

  const score = async () => {
    setBusy("কাস্টমার বিশ্লেষণ করা হচ্ছে…"); setError(null);
    try {
      setResult(await api.scoreUpload(parsed.token, mapping));
      // Opening the workspace is what makes every other page switch to this
      // file — without it the upload would only ever affect this one screen.
      openWorkspace({
        token: parsed.token,
        mapping,
        filename: parsed.filename,
        rowCount: parsed.row_count,
      });
    } catch (e) {
      setError(e.message); setResult(null);
    } finally {
      setBusy("");
    }
  };

  const download = async () => {
    setBusy("ডাউনলোডের জন্য প্রস্তুত করা হচ্ছে…");
    try {
      const blob = await api.exportUpload(parsed.token, mapping);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "kader-jogajog-korben.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy("");
    }
  };

  return (
    <div className="page">
      <header className="page-head">
        <h2>নিজের বিক্রির তথ্য বিশ্লেষণ করুন</h2>
        <p className="subtitle">
          বিক্রির একটি স্প্রেডশিট আপলোড করুন এবং জানুন কোন কাস্টমার হারিয়ে যাচ্ছেন —
          যাতে বুঝতে পারেন কার সাথে আগে যোগাযোগ করতে হবে।
        </p>
      </header>

      {error && (
        <div className="callout danger">
          <strong>এগোনো যায়নি।</strong>
          <p>{error}</p>
        </div>
      )}

      <StepDropzone
        parsed={parsed}
        busy={busy}
        dragging={dragging}
        setDragging={setDragging}
        fileRef={fileRef}
        onFile={handleFile}
        onReset={reset}
      />

      {parsed && (
        <StepMapping
          parsed={parsed}
          mapping={mapping}
          setMapping={setMapping}
          ready={ready}
          busy={busy}
          onScore={score}
        />
      )}

      {result && (
        <Results
          result={result}
          showAll={showAll}
          setShowAll={setShowAll}
          onDownload={download}
          busy={busy}
          token={parsed.token}
          mapping={mapping}
        />
      )}
    </div>
  );
}

// ── ধাপ ১ ──────────────────────────────────────────────
function StepDropzone({ parsed, busy, dragging, setDragging, fileRef, onFile, onReset }) {
  return (
    <section className="card">
      <h3><span className="step-num">1</span> ফাইল বেছে নিন</h3>
      {!parsed ? (
        <>
          <div
            className={`dropzone ${dragging ? "dragging" : ""}`}
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault(); setDragging(false);
              onFile(e.dataTransfer.files?.[0]);
            }}
            onClick={() => fileRef.current?.click()}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === "Enter" && fileRef.current?.click()}
          >
            <div className="dropzone-icon">📄</div>
            <strong>আপনার CSV বা Excel ফাইল এখানে ছেড়ে দিন</strong>
            <span>অথবা ক্লিক করে বেছে নিন</span>
          </div>
          <input
            ref={fileRef}
            type="file"
            accept=".csv,.xlsx,.xls"
            hidden
            onChange={(e) => onFile(e.target.files?.[0])}
          />
          <p className="hint">
            প্রতিটি বিক্রির জন্য একটি সারি দরকার, যেখানে কে কিনেছে, কবে এবং কত টাকা দিয়েছে
            তার কলাম থাকবে। বাকি কলাম উপেক্ষা করা হবে।
          </p>
          {busy && <p className="hint">{busy}</p>}
        </>
      ) : (
        <div className="file-summary">
          <div>
            <strong>{parsed.filename}</strong>
            <span className="hint">
              {parsed.row_count.toLocaleString()} বিক্রি · {parsed.columns.length} কলাম
            </span>
          </div>
          <button type="button" className="btn-secondary" onClick={onReset}>
            অন্য ফাইল ব্যবহার করুন
          </button>
        </div>
      )}
    </section>
  );
}

// ── ধাপ ২ ──────────────────────────────────────────────
function StepMapping({ parsed, mapping, setMapping, ready, busy, onScore }) {
  const guessed = useMemo(
    () => ROLES.filter((r) => parsed.suggested_mapping?.[r.key]).length,
    [parsed],
  );

  return (
    <section className="card">
      <h3><span className="step-num">2</span> কোন কলাম কী, তা বলুন</h3>
      <p className="hint">
        {guessed > 0
          ? `আমরা স্বয়ংক্রিয়ভাবে আপনার ${guessed}টি কলাম চিনেছি। ঠিক আছে কিনা দেখুন, ভুল থাকলে বদলান।`
          : "নিচের প্রতিটি আইটেমের জন্য আপনার ফাইল থেকে মিলে যাওয়া কলাম বেছে নিন।"}
      </p>

      <div className="mapping-grid">
        {ROLES.map((role) => (
          <label key={role.key} className="mapping-row">
            <span className="mapping-label">
              {role.label}
              {role.required && <em className="req"> আবশ্যক</em>}
              <span className="hint">{role.hint}</span>
            </span>
            <select
              value={mapping[role.key] || ""}
              onChange={(e) =>
                setMapping({ ...mapping, [role.key]: e.target.value || null })
              }
            >
              <option value="">— আমার ফাইলে নেই —</option>
              {parsed.columns.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </label>
        ))}
      </div>

      <details className="preview">
        <summary>আপনার ফাইলের প্রথম কয়েকটি সারি দেখুন</summary>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>{parsed.columns.map((c) => <th key={c}>{c}</th>)}</tr>
            </thead>
            <tbody>
              {parsed.sample_rows.map((row, i) => (
                <tr key={i}>
                  {parsed.columns.map((c) => <td key={c}>{String(row[c] ?? "")}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>

      <button type="button" className="btn-primary" disabled={!ready || !!busy} onClick={onScore}>
        {busy || "আমার কাস্টমার বিশ্লেষণ করুন"}
      </button>
      {!ready && <p className="hint">এগোতে প্রতিটি আবশ্যক আইটেমের জন্য একটি কলাম বেছে নিন।</p>}
    </section>
  );
}

// ── ধাপ ৩ ──────────────────────────────────────────────
function Results({ result, showAll, setShowAll, onDownload, busy, token, mapping }) {
  const s = result.summary;
  const rows = showAll ? result.rows : result.rows.slice(0, 25);
  const pctLapsed = s.total_customers ? Math.round((s.lapsed_count / s.total_customers) * 100) : 0;

  return (
    <section className="card">
      <h3><span className="step-num">3</span> যা পাওয়া গেছে</h3>

      <div className="callout green">
        <strong>আপনার ড্যাশবোর্ড প্রস্তুত</strong>
        <p>
          এখন থেকে সব পাতা নমুনা তথ্যের বদলে এই ফাইল দেখাবে।{" "}
          <Link to="/">এই সপ্তাহের করণীয় দেখুন</Link>, অথবা{" "}
          <Link to="/forecast">বিক্রির পূর্বাভাস</Link> ও{" "}
          <Link to="/segments">কাস্টমার গ্রুপ</Link> দেখুন।
        </p>
      </div>

      <div className="kpi-grid">
        <div className="kpi">
          <span className="label">ফাইলে কাস্টমার সংখ্যা</span>
          <strong className="value">{s.total_customers.toLocaleString()}</strong>
        </div>
        <div className="kpi danger">
          <span className="label">{s.threshold_days}+ দিন কেনেননি</span>
          <strong className="value">{s.lapsed_count.toLocaleString()}</strong>
          <span className="sub">আপনার {pctLapsed}% কাস্টমার</span>
        </div>
        <div className="kpi">
          <span className="label">তাদের এখন পর্যন্ত ব্যয়</span>
          <strong className="value">{formatBDT(s.revenue_at_risk)}</strong>
          <span className="sub">যে ব্যবসা হারাতে পারেন</span>
        </div>
        <div className="kpi">
          <span className="label">গড় অর্ডার</span>
          <strong className="value">{formatBDT(s.avg_order_value)}</strong>
        </div>
      </div>

      <div className="callout">
        <strong>এই তালিকা কীভাবে পড়বেন</strong>
        <p>{result.domain_warning}</p>
        <p className="hint">
          {s.source_rows.toLocaleString()} সারি থেকে তৈরি
          {s.dropped_rows > 0 && ` (${s.dropped_rows.toLocaleString()}টি পড়া যায়নি বলে বাদ)`}
          {" · "}সর্বশেষ বিক্রি {s.as_of}
          {" · "}মডেল: {s.churn_model}
        </p>
      </div>

      <div className="results-head">
        <h4>প্রথমে কার সাথে যোগাযোগ করবেন</h4>
        <button type="button" className="btn-secondary" onClick={onDownload} disabled={!!busy}>
          {busy || "পূর্ণ তালিকা ডাউনলোড করুন (CSV)"}
        </button>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>কাস্টমার</th>
              <th>শেষ কেনা</th>
              <th>মোট ব্যয়</th>
              <th>অর্ডার</th>
              <th>ঝুঁকি</th>
              <th>করণীয়</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.customer_id} className={r.already_lapsed ? "row-flag" : ""}>
                <td>{r.customer_id}</td>
                <td>
                  {r.inactive_days} দিন আগে
                  {r.already_lapsed && <span className="pill danger">নিষ্ক্রিয়</span>}
                </td>
                <td>{formatBDT(r.monetary)}</td>
                <td>{r.txn_count}</td>
                <td><span className={`pill ${BAND_TONE[r.risk_band] || ""}`}>{BAND_LABEL[r.risk_band] || r.risk_band}</span></td>
                <td className="action-cell">{r.action}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {result.rows.length > 25 && (
        <button type="button" className="btn-secondary" onClick={() => setShowAll((v) => !v)}>
          {showAll ? "শুধু শীর্ষ ২৫টি দেখান" : `সব ${result.rows.length.toLocaleString()} জন কাস্টমার দেখান`}
        </button>
      )}

      <DynamicChurnTraining token={token} mapping={mapping} />
    </section>
  );
}

// ── ধাপ ৪ (ঐচ্ছিক) ────────────────────────────────────
// The score above uses the fixed churn_model.pkl trained on the synthetic
// thesis dataset — accurate on this project's own data, but not calibrated
// for a stranger's business. This trains a brand-new model from scratch on
// nothing but the uploaded rows and reports its own held-out performance —
// genuinely dynamic, not a rescoring of the same fixed model.
function DynamicChurnTraining({ token, mapping }) {
  const [busy, setBusy] = useState(false);
  const [metrics, setMetrics] = useState(null);
  const [feedback, showFeedback] = useFeedback();

  const train = async () => {
    setBusy(true); setMetrics(null);
    try {
      const r = await api.trainUploadChurn(token, mapping);
      const winner = r.models[r.winner_by_brier];
      setMetrics({ name: r.winner_by_brier, ...winner, rows: r.train_rows + r.test_rows });
      showFeedback("success", "নতুন মডেল প্রশিক্ষণ সম্পন্ন — এটা সম্পূর্ণ আপনার নিজের ফাইলের উপর তৈরি।");
    } catch (e) {
      showFeedback("error", e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="card">
      <h3>নিজের ডেটা দিয়ে নতুন মডেল ট্রেন করুন</h3>
      <p className="hint">
        উপরের স্কোর একটি স্থির মডেল দিয়ে হিসাব করা (গবেষণার সিন্থেটিক ডেটায় প্রশিক্ষিত)।
        এখানে সম্পূর্ণ নতুন একটি মডেল তৈরি হবে — শুধু আপনার এই ফাইলের সারি দিয়ে, এবং তার
        সঠিকতা আপনার নিজের ডেটায় পরিমাপ করে দেখানো হবে। কমপক্ষে ৩০০+ ব্যবহারযোগ্য নমুনা
        (যথেষ্ট দিনের ইতিহাস ও পুনরাবৃত্ত কাস্টমার) দরকার — কম থাকলে স্পষ্ট কারণ জানানো হবে।
      </p>
      <FeedbackBanner feedback={feedback} />
      <button type="button" className="btn-primary" onClick={train} disabled={busy}>
        {busy ? "প্রশিক্ষণ চলছে…" : "নতুন মডেল ট্রেন করুন"}
      </button>
      {metrics && (
        <div className="callout green">
          <strong>নিজের ডেটায় তৈরি মডেলের সঠিকতা</strong>
          <p>
            {metrics.rows.toLocaleString()} নমুনা দিয়ে প্রশিক্ষিত ও পরীক্ষিত ({metrics.name}) ·
            {" "}ROC-AUC {(metrics.roc_auc * 100).toFixed(1)}% ·
            {" "}PR-AUC {(metrics.pr_auc * 100).toFixed(1)}% ·
            {" "}শীর্ষ ১০%-এ লিফট {metrics.lift_at_10.toFixed(2)}×
          </p>
          <p className="hint">
            এই সংখ্যাগুলো সম্পূর্ণভাবে আপনার নিজের ফাইল থেকে, chronological hold-out টেস্টে
            পরিমাপ করা — কোনো fabricate করা ফলাফল নয়।
          </p>
        </div>
      )}
    </section>
  );
}
