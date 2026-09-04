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
import { useWorkspace } from "../WorkspaceContext";

const ROLES = [
  { key: "customer_id", label: "Customer ID", hint: "Who bought — a name, phone number or code", required: true },
  { key: "date", label: "Purchase date", hint: "When the sale happened", required: true },
  { key: "amount", label: "Amount paid", hint: "Total for that sale, in taka", required: true },
  { key: "quantity", label: "Quantity", hint: "How many items (optional)", required: false },
  { key: "product", label: "Product name", hint: "What was sold — unlocks best-sellers (optional)", required: false },
];

const BAND_TONE = { High: "danger", Medium: "warn", Low: "ok" };

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
    setBusy("Reading your file…"); setError(null); setResult(null);
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
    setBusy("Analysing your customers…"); setError(null);
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
    setBusy("Preparing download…");
    try {
      const blob = await api.exportUpload(parsed.token, mapping);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "customers-to-contact.csv";
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
        <h2>Analyse your own sales data</h2>
        <p className="subtitle">
          Upload a spreadsheet of your sales and find out which customers are drifting
          away — so you know who to contact first.
        </p>
      </header>

      {error && (
        <div className="callout danger">
          <strong>Could not continue.</strong>
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
        />
      )}
    </div>
  );
}

// ── Step 1 ──────────────────────────────────────────────
function StepDropzone({ parsed, busy, dragging, setDragging, fileRef, onFile, onReset }) {
  return (
    <section className="card">
      <h3><span className="step-num">1</span> Choose your file</h3>
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
            <strong>Drop your CSV or Excel file here</strong>
            <span>or click to browse</span>
          </div>
          <input
            ref={fileRef}
            type="file"
            accept=".csv,.xlsx,.xls"
            hidden
            onChange={(e) => onFile(e.target.files?.[0])}
          />
          <p className="hint">
            The file needs one row per sale, with columns for who bought, when, and
            how much they paid. Anything else in the file is ignored.
          </p>
          {busy && <p className="hint">{busy}</p>}
        </>
      ) : (
        <div className="file-summary">
          <div>
            <strong>{parsed.filename}</strong>
            <span className="hint">
              {parsed.row_count.toLocaleString()} sales · {parsed.columns.length} columns
            </span>
          </div>
          <button type="button" className="btn-secondary" onClick={onReset}>
            Use a different file
          </button>
        </div>
      )}
    </section>
  );
}

// ── Step 2 ──────────────────────────────────────────────
function StepMapping({ parsed, mapping, setMapping, ready, busy, onScore }) {
  const guessed = useMemo(
    () => ROLES.filter((r) => parsed.suggested_mapping?.[r.key]).length,
    [parsed],
  );

  return (
    <section className="card">
      <h3><span className="step-num">2</span> Tell us which column is which</h3>
      <p className="hint">
        {guessed > 0
          ? `We recognised ${guessed} of your columns automatically. Check they look right and change any that don't.`
          : "Pick the matching column from your file for each item below."}
      </p>

      <div className="mapping-grid">
        {ROLES.map((role) => (
          <label key={role.key} className="mapping-row">
            <span className="mapping-label">
              {role.label}
              {role.required && <em className="req"> required</em>}
              <span className="hint">{role.hint}</span>
            </span>
            <select
              value={mapping[role.key] || ""}
              onChange={(e) =>
                setMapping({ ...mapping, [role.key]: e.target.value || null })
              }
            >
              <option value="">— not in my file —</option>
              {parsed.columns.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </label>
        ))}
      </div>

      <details className="preview">
        <summary>Preview the first few rows of your file</summary>
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
        {busy || "Analyse my customers"}
      </button>
      {!ready && <p className="hint">Choose a column for each required item to continue.</p>}
    </section>
  );
}

// ── Step 3 ──────────────────────────────────────────────
function Results({ result, showAll, setShowAll, onDownload, busy }) {
  const s = result.summary;
  const rows = showAll ? result.rows : result.rows.slice(0, 25);
  const pctLapsed = s.total_customers ? Math.round((s.lapsed_count / s.total_customers) * 100) : 0;

  return (
    <section className="card">
      <h3><span className="step-num">3</span> What we found</h3>

      <div className="callout green">
        <strong>Your dashboard is ready</strong>
        <p>
          Every page now shows this file instead of the sample data.{" "}
          <Link to="/">See what to do this week</Link>, or check your{" "}
          <Link to="/forecast">sales forecast</Link> and{" "}
          <Link to="/segments">customer groups</Link>.
        </p>
      </div>

      <div className="kpi-grid">
        <div className="kpi">
          <span className="label">Customers in your file</span>
          <strong className="value">{s.total_customers.toLocaleString()}</strong>
        </div>
        <div className="kpi danger">
          <span className="label">Haven't bought in {s.threshold_days}+ days</span>
          <strong className="value">{s.lapsed_count.toLocaleString()}</strong>
          <span className="sub">{pctLapsed}% of your customers</span>
        </div>
        <div className="kpi">
          <span className="label">Their spending so far</span>
          <strong className="value">{formatBDT(s.revenue_at_risk)}</strong>
          <span className="sub">business you could lose</span>
        </div>
        <div className="kpi">
          <span className="label">Average order</span>
          <strong className="value">{formatBDT(s.avg_order_value)}</strong>
        </div>
      </div>

      <div className="callout">
        <strong>How to read this list</strong>
        <p>{result.domain_warning}</p>
        <p className="hint">
          Built from {s.source_rows.toLocaleString()} rows
          {s.dropped_rows > 0 && ` (${s.dropped_rows.toLocaleString()} skipped as unreadable)`}
          {" · "}most recent sale {s.as_of}
          {" · "}model: {s.churn_model}
        </p>
      </div>

      <div className="results-head">
        <h4>Who to contact first</h4>
        <button type="button" className="btn-secondary" onClick={onDownload} disabled={!!busy}>
          {busy || "Download full list (CSV)"}
        </button>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Customer</th>
              <th>Last bought</th>
              <th>Total spent</th>
              <th>Orders</th>
              <th>Risk</th>
              <th>What to do</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.customer_id} className={r.already_lapsed ? "row-flag" : ""}>
                <td>{r.customer_id}</td>
                <td>
                  {r.inactive_days} days ago
                  {r.already_lapsed && <span className="pill danger">inactive</span>}
                </td>
                <td>{formatBDT(r.monetary)}</td>
                <td>{r.txn_count}</td>
                <td><span className={`pill ${BAND_TONE[r.risk_band] || ""}`}>{r.risk_band}</span></td>
                <td className="action-cell">{r.action}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {result.rows.length > 25 && (
        <button type="button" className="btn-secondary" onClick={() => setShowAll((v) => !v)}>
          {showAll ? "Show top 25 only" : `Show all ${result.rows.length.toLocaleString()} customers`}
        </button>
      )}
    </section>
  );
}
