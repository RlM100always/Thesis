/**
 * ResearchPortal.jsx
 * Thesis evaluation & dynamic experiment portal.
 *
 * Levels implemented:
 *   L1  — built-in datasets listed and selectable
 *   L2  — Experiment Registry (named, locked baseline, run/delete)
 *   L3  — Deep comparison table (N experiments side-by-side)
 *   L4  — Algorithm trace (B-SMART pipeline step visualization)
 *   L5  — Export for thesis (CSV download of comparison table)
 *
 * Accessible at /research — ResearchShell in App.jsx mounts this.
 * Any logged-in user can reach it; evaluator role users see a sidebar link.
 */

import { useEffect, useRef, useState } from "react";
import { api } from "../api";

// ── tiny helpers ─────────────────────────────────────────────────────────────

function pct(v) { return v != null ? `${(v * 100).toFixed(1)}%` : "—"; }
function num(v, d = 0) { return v != null ? Number(v).toFixed(d) : "—"; }
function fmt(v) {
  if (v == null) return "—";
  if (typeof v === "number") return Number(v.toFixed(4)).toLocaleString();
  return String(v);
}

const VERTICAL_EMOJI = {
  pharmacy: "💊", grocery: "🛒", clothing: "👗",
  restaurant: "🍛", electronics: "📱",
  auto_parts: "🔧", stationery: "📚", generic: "📊",
};

const STATUS_COLOR = { completed: "#0A8754", pending: "#64748B", running: "#f59e0b", failed: "#E63946" };
const STATUS_LABEL = { completed: "completed", pending: "pending", running: "⏳ running…", failed: "failed" };

// ── Tab nav ──────────────────────────────────────────────────────────────────

const TABS = [
  { id: "registry",  label: "Experiment Registry" },
  { id: "new",       label: "+ New Experiment" },
  { id: "compare",   label: "Compare" },
  { id: "trace",     label: "Algorithm Trace" },
  { id: "export",    label: "Export" },
];

// ── Main component ────────────────────────────────────────────────────────────

export default function ResearchPortal() {
  const [tab, setTab]           = useState("registry");
  const [experiments, setExps]  = useState([]);
  const [datasets, setDatasets] = useState([]);
  const [schema, setSchema]     = useState({});
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState(null);

  function reload(silent = false) {
    if (!silent) setLoading(true);
    Promise.all([
      api.portalExperiments(),
      api.portalDatasets(),
      api.portalSchema(),
    ])
      .then(([e, d, s]) => {
        setExps(e.experiments || []);
        setDatasets(d.datasets || []);
        setSchema(s || {});
        setError(null);
      })
      .catch(err => { if (!silent) setError(err.message); })
      .finally(() => { if (!silent) setLoading(false); });
  }

  useEffect(() => { reload(); }, []);

  if (loading) return <div className="rp-loading">লোড হচ্ছে…</div>;
  if (error)   return <div className="rp-error">Error: {error}</div>;

  const completed = experiments.filter(e => e.status === "completed");

  return (
    <div className="rp-root">
      <div className="rp-header">
        <h1>B-SMART গবেষণা পোর্টাল</h1>
        <p className="rp-subtitle">
          Dynamic experiment registry — upload any SME dataset, run the full
          B-SMART pipeline, compare performance across verticals and configurations.
        </p>
      </div>

      <div className="rp-tabs" role="tablist">
        {TABS.map(t => (
          <button key={t.id} type="button" role="tab"
            className={`rp-tab${tab === t.id ? " active" : ""}`}
            onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </div>

      <div className="rp-body">
        {tab === "registry"  && <RegistryTab experiments={experiments} onReload={reload} setTab={setTab} />}
        {tab === "new"       && <NewExpTab datasets={datasets} schema={schema} onCreated={() => { reload(); setTab("registry"); }} />}
        {tab === "compare"   && <CompareTab completed={completed} />}
        {tab === "trace"     && <TraceTab experiments={experiments} />}
        {tab === "export"    && <ExportTab completed={completed} />}
      </div>
    </div>
  );
}

// ── L2: Experiment Registry ───────────────────────────────────────────────────

function RegistryTab({ experiments, onReload, setTab }) {
  const [starting, setStarting] = useState(null);
  const pollRef = useRef({});

  // Poll status for any experiment that is currently "running"
  useEffect(() => {
    const running = experiments.filter(e => e.status === "running");
    running.forEach(exp => {
      if (pollRef.current[exp.id]) return;  // already polling
      pollRef.current[exp.id] = setInterval(async () => {
        try {
          const s = await api.portalStatus(exp.id);
          if (s.status !== "running") {
            clearInterval(pollRef.current[exp.id]);
            delete pollRef.current[exp.id];
            onReload();          // full reload when done/failed
          } else {
            onReload(true);      // silent refresh — no spinner, just updates state
          }
        } catch {
          clearInterval(pollRef.current[exp.id]);
          delete pollRef.current[exp.id];
        }
      }, 3000);
    });
    // Clean up intervals for experiments no longer running
    Object.keys(pollRef.current).forEach(id => {
      if (!running.find(e => e.id === id)) {
        clearInterval(pollRef.current[id]);
        delete pollRef.current[id];
      }
    });
  }, [experiments.map(e => e.id + e.status).join(",")]);

  useEffect(() => () => Object.values(pollRef.current).forEach(clearInterval), []);

  async function runExp(id) {
    setStarting(id);
    try {
      await api.portalRunExp(id);
      onReload();
    } catch (e) {
      alert(`Error: ${e.message}`);
    } finally {
      setStarting(null);
    }
  }

  async function deleteExp(id, name) {
    if (!window.confirm(`"${name}" মুছে ফেলবেন?`)) return;
    try { await api.portalDeleteExp(id); onReload(); }
    catch (e) { alert(`Error: ${e.message}`); }
  }

  if (!experiments.length) return (
    <div className="rp-empty">
      কোনো experiment নেই।{" "}
      <button type="button" className="rp-link" onClick={() => setTab("new")}>
        নতুন তৈরি করুন →
      </button>
    </div>
  );

  return (
    <div className="rp-section">
      <div className="rp-section-header">
        <h2>Experiment Registry</h2>
        <button type="button" className="rp-btn-primary" onClick={() => setTab("new")}>
          + New Experiment
        </button>
      </div>

      <div className="rp-exp-list">
        {experiments.map(exp => (
          <div key={exp.id} className={`rp-exp-card${exp.locked ? " locked" : ""}`}>
            <div className="rp-exp-meta">
              <span className="rp-exp-id">{exp.id}</span>
              {exp.locked && <span className="rp-badge locked">🔒 Locked</span>}
              <span className="rp-badge" style={{ background: STATUS_COLOR[exp.status] }}>
                {exp.status}
              </span>
              <span className="rp-badge vertical">
                {VERTICAL_EMOJI[exp.vertical] || "📊"} {exp.vertical}
              </span>
            </div>
            <div className="rp-exp-name">{exp.name}</div>
            {exp.config && (
              <div className="rp-exp-config-hint">
                {exp.config.run_churn !== false && <span>Churn</span>}
                {exp.config.run_segments !== false && <span>Segments K={exp.config.segment_k || 4}</span>}
                {exp.config.run_forecast && <span>Forecast</span>}
                <span>Seed={exp.config.random_seed ?? 42}</span>
                <span>Churn≥{exp.config.churn_threshold_days ?? 90}d</span>
              </div>
            )}
            {exp.status === "running" && exp.progress?.length > 0 && (
              <div className="rp-progress-row">
                {exp.progress.map(p => (
                  <span key={p.step}
                    className={`rp-progress-chip ${p.status === "done" ? "done" : p.status.startsWith("fail") ? "fail" : "running"}`}>
                    {p.step === "churn" ? "Churn" :
                     p.step === "segmentation" ? "Segments" :
                     p.step === "forecast" ? "Forecast" : p.step}
                    {" "}{p.status === "done" ? "✓" : p.status.startsWith("fail") ? "✗" : "…"}
                  </span>
                ))}
              </div>
            )}
            <div className="rp-exp-actions">
              {exp.status === "running" ? (
                <span className="rp-running-badge">⏳ Running…</span>
              ) : (
                <>
                  {exp.status !== "completed" && (
                    <button type="button" className="rp-btn-run"
                      disabled={starting === exp.id}
                      onClick={() => runExp(exp.id)}>
                      {starting === exp.id ? "Starting…" : "▶ Run"}
                    </button>
                  )}
                  {exp.status === "completed" && !exp.locked && (
                    <button type="button" className="rp-btn-run"
                      disabled={starting === exp.id}
                      onClick={() => runExp(exp.id)}>
                      {starting === exp.id ? "Starting…" : "↺ Re-run"}
                    </button>
                  )}
                  {exp.status === "failed" && (
                    <button type="button" className="rp-btn-run"
                      disabled={starting === exp.id}
                      onClick={() => runExp(exp.id)}>
                      {starting === exp.id ? "Starting…" : "↺ Retry"}
                    </button>
                  )}
                </>
              )}
              {!exp.locked && exp.status !== "running" && (
                <button type="button" className="rp-btn-del"
                  onClick={() => deleteExp(exp.id, exp.name)}>
                  ✕
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      {experiments.some(e => e.status === "completed") && (
        <ResultsPanel experiments={experiments} />
      )}
    </div>
  );
}

function ResultsPanel({ experiments }) {
  const [open, setOpen] = useState(null);
  const completed = experiments.filter(e => e.status === "completed");

  if (!completed.length) return null;

  return (
    <div className="rp-results-panel">
      <h3>Results</h3>
      <div className="rp-results-select">
        {completed.map(e => (
          <button key={e.id} type="button"
            className={`rp-result-btn${open === e.id ? " active" : ""}`}
            onClick={() => setOpen(open === e.id ? null : e.id)}>
            {e.id}
          </button>
        ))}
      </div>
      {open && <ExpResultDetail expId={open} />}
    </div>
  );
}

function ExpResultDetail({ expId }) {
  const [exp, setExp] = useState(null);
  useEffect(() => {
    api.portalGetExp(expId).then(setExp).catch(() => {});
  }, [expId]);

  if (exp?.status === "failed") return <div className="rp-error">Run failed: {exp.error || "unknown error"}</div>;
  if (!exp?.results) return <div className="rp-loading">লোড হচ্ছে…</div>;

  const u = exp.results.universal || {};
  const v = exp.results.vertical_specific || {};

  return (
    <div className="rp-result-detail">
      <div className="rp-metric-grid">
        <MetricCard title="Dataset" value={num(u.dataset_summary?.rows)} unit="rows"
          sub={`${num(u.dataset_summary?.customers)} customers · ${u.dataset_summary?.vertical}`} />
        <MetricCard title="Churn Rate" value={pct(u.churn?.churn_rate)} unit=""
          sub={`>${u.churn?.threshold_days} days inactive`} />
        <MetricCard title="Avg Recency" value={num(u.rfm?.recency_mean)} unit="days"
          sub={`Freq: ${num(u.rfm?.frequency_mean, 1)} txns`} />
        <MetricCard title="Seasonal-Naive WAPE" value={u.forecast?.seasonal_naive_wape != null ? pct(u.forecast.seasonal_naive_wape) : "n/a"} unit=""
          sub="monthly forecast baseline" />
      </div>

      {u.segmentation?.segments && (
        <div className="rp-seg-row">
          {Object.entries(u.segmentation.segments).map(([seg, cnt]) => (
            <div key={seg} className="rp-seg-chip">
              <strong>{seg}</strong><span>{cnt}</span>
            </div>
          ))}
        </div>
      )}

      {u.abc_analysis && (
        <div className="rp-abc">
          <strong>ABC Analysis:</strong>{" "}
          A={u.abc_analysis.A_products} products (80% revenue),{" "}
          B={u.abc_analysis.B_products}, C={u.abc_analysis.C_products}
          {u.abc_analysis.top_5?.length > 0 && (
            <> &nbsp;|&nbsp; Top: {u.abc_analysis.top_5.map(p => p.name).join(", ")}</>
          )}
        </div>
      )}

      {Object.keys(v).length > 0 && (
        <div className="rp-vertical-results">
          <h4>Vertical-specific ({exp.results.detected_vertical})</h4>
          <pre className="rp-json">{JSON.stringify(v, null, 2)}</pre>
        </div>
      )}

      <MLMetricsPanel ml={exp.results.ml_models} />
    </div>
  );
}

function MLMetricsPanel({ ml }) {
  if (!ml || Object.keys(ml).length === 0) return null;

  const churn   = ml.churn_model   || {};
  const seg     = ml.segments_model || {};
  const fc      = ml.forecast_model || {};

  const churnModels = churn.models || {};
  const winner      = churn.winner_by_brier;

  return (
    <div className="rp-ml-panel">
      <h4>ML Model Results</h4>

      {/* Churn / Future-repeat */}
      {churn.error ? (
        <div className="rp-ml-section">
          <strong>Churn Model:</strong> <span className="rp-ml-err">{churn.error}</span>
        </div>
      ) : Object.keys(churnModels).length > 0 ? (
        <div className="rp-ml-section">
          <div className="rp-ml-section-title">Future-Repeat (Churn) Models</div>
          <div className="rp-metric-grid">
            {Object.entries(churnModels).map(([name, m]) => (
              <div key={name} className={`rp-metric-card${winner === name ? " highlight" : ""}`}>
                <div className="rp-metric-title">{name}{winner === name ? " ★" : ""}</div>
                <div className="rp-ml-stat-row">
                  <span>ROC-AUC</span><strong>{num(m.roc_auc, 4)}</strong>
                </div>
                <div className="rp-ml-stat-row">
                  <span>PR-AUC</span><strong>{num(m.pr_auc, 4)}</strong>
                </div>
                <div className="rp-ml-stat-row">
                  <span>Brier</span><strong>{num(m.brier, 4)}</strong>
                </div>
                <div className="rp-ml-stat-row">
                  <span>Lift@10%</span><strong>{num(m.lift_at_10, 2)}x</strong>
                </div>
              </div>
            ))}
          </div>
          <div className="rp-ml-note">
            Test positive rate: {pct(churn.positive_rate)} · {churn.train_rows} train / {churn.test_rows} test snapshots
          </div>
        </div>
      ) : null}

      {/* Segmentation */}
      {seg.error ? (
        <div className="rp-ml-section">
          <strong>Segmentation:</strong> <span className="rp-ml-err">{seg.error}</span>
        </div>
      ) : seg.profile ? (
        <div className="rp-ml-section">
          <div className="rp-ml-section-title">
            K-Means Segmentation (K={seg.k}, silhouette={num(seg.silhouette, 4)})
          </div>
          <div className="rp-seg-row">
            {Object.entries(seg.profile).map(([tier, p]) => (
              <div key={tier} className="rp-seg-chip">
                <strong>{tier}</strong>
                <span>{p.count} customers</span>
                <small>৳{num(p.avg_monetary, 0)} avg · {num(p.avg_recency_days, 0)}d recency</small>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {/* Forecast */}
      {fc.error ? (
        <div className="rp-ml-section">
          <strong>Demand Forecast:</strong> <span className="rp-ml-err">{fc.error}</span>
        </div>
      ) : fc.hist_gradient_boosting ? (
        <div className="rp-ml-section">
          <div className="rp-ml-section-title">Demand Forecast (HistGradientBoosting vs Seasonal-Naive-7)</div>
          <div className="rp-metric-grid">
            <div className="rp-metric-card">
              <div className="rp-metric-title">HistGradientBoosting</div>
              <div className="rp-ml-stat-row"><span>WAPE</span><strong>{pct(fc.hist_gradient_boosting.wape)}</strong></div>
              <div className="rp-ml-stat-row"><span>MAE</span><strong>{num(fc.hist_gradient_boosting.mae, 2)}</strong></div>
            </div>
            <div className="rp-metric-card">
              <div className="rp-metric-title">Seasonal-Naive (7d)</div>
              <div className="rp-ml-stat-row"><span>WAPE</span><strong>{pct(fc.seasonal_naive_7?.wape)}</strong></div>
              <div className="rp-ml-stat-row"><span>MAE</span><strong>{num(fc.seasonal_naive_7?.mae, 2)}</strong></div>
            </div>
          </div>
          <div className="rp-ml-note">
            {fc.train_rows} train rows · {fc.test_rows} test rows · split at {fc.split_date?.slice(0,10)}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function MetricCard({ title, value, unit, sub }) {
  return (
    <div className="rp-metric-card">
      <div className="rp-metric-title">{title}</div>
      <div className="rp-metric-value">{value}<span className="rp-metric-unit">{unit}</span></div>
      {sub && <div className="rp-metric-sub">{sub}</div>}
    </div>
  );
}

// ── L1 + new experiment form ──────────────────────────────────────────────────

const VERTICALS = ["pharmacy","grocery","clothing","restaurant","electronics","auto_parts","stationery","generic"];

function NewExpTab({ datasets, schema, onCreated }) {
  const [name,        setName]       = useState("");
  const [desc,        setDesc]       = useState("");
  const [vertical,    setVertical]   = useState("pharmacy");
  const [source,      setSource]     = useState("built-in");
  const [uploadFile,  setUploadFile] = useState(null);
  const [uploadInfo,  setUploadInfo] = useState(null);
  const [uploadPath,  setUploadPath] = useState(null);
  const [config,      setConfig]     = useState({
    train_ratio: 0.70, val_ratio: 0.15, test_ratio: 0.15,
    cv_folds: 5, random_seed: 42, churn_threshold_days: 90, stratified: true,
    run_churn: true, run_segments: true, run_forecast: false,
    segment_k: 4,
  });
  const [saving,   setSaving]   = useState(false);
  const [uploading,setUploading]= useState(false);
  const fileRef = useRef();

  async function handleUpload(file) {
    if (!file) return;
    setUploadFile(file);
    setUploading(true);
    try {
      const info = await api.portalUpload(file);
      setUploadInfo(info);
      setUploadPath(info.upload_path);
      if (info.detected_vertical && info.detected_vertical !== "generic") {
        setVertical(info.detected_vertical);
      }
    } catch (e) {
      alert(`Upload error: ${e.message}`);
    } finally {
      setUploading(false);
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    try {
      const body = {
        name: name.trim(), description: desc.trim(),
        vertical,
        dataset_source: source,
        dataset_id:     source === "built-in" ? `builtin_${vertical}` : undefined,
        upload_path:    source === "upload" ? uploadPath : undefined,
        config,
      };
      await api.portalCreateExp(body);
      onCreated();
    } catch (err) {
      alert(`Error: ${err.message}`);
    } finally {
      setSaving(false);
    }
  }

  const selSchema = schema[vertical] || {};

  return (
    <div className="rp-section">
      <h2>New Experiment</h2>
      <form className="rp-form" onSubmit={handleSubmit}>

        <label className="rp-label">Experiment Name *
          <input className="rp-input" value={name} onChange={e => setName(e.target.value)}
            placeholder="e.g. Grocery — 80/20 split" required />
        </label>

        <label className="rp-label">Description
          <input className="rp-input" value={desc} onChange={e => setDesc(e.target.value)}
            placeholder="optional notes" />
        </label>

        <label className="rp-label">Dataset Source
          <select className="rp-select" value={source} onChange={e => setSource(e.target.value)}>
            <option value="built-in">Built-in Bangladesh SME Dataset</option>
            <option value="upload">Upload Custom CSV</option>
          </select>
        </label>

        {source === "built-in" && (
          <>
            <label className="rp-label">Business Vertical
              <select className="rp-select" value={vertical} onChange={e => setVertical(e.target.value)}>
                {VERTICALS.map(v => (
                  <option key={v} value={v}>
                    {VERTICAL_EMOJI[v]} {v.charAt(0).toUpperCase() + v.slice(1)} — {(schema[v]?.description) || ""}
                  </option>
                ))}
              </select>
            </label>
            {selSchema.vertical_columns && Object.keys(selSchema.vertical_columns).length > 0 && (
              <div className="rp-schema-hint">
                <strong>Vertical-specific columns detected:</strong>{" "}
                {Object.entries(selSchema.vertical_columns).map(([col, desc]) => (
                  <span key={col} className="rp-col-chip" title={desc}>{col}</span>
                ))}
                <br /><em>Additional analysis: {selSchema.vertical_analyses?.join(", ")}</em>
              </div>
            )}
          </>
        )}

        {source === "upload" && (
          <div className="rp-upload-zone"
            onClick={() => fileRef.current?.click()}
            onDragOver={e => e.preventDefault()}
            onDrop={e => { e.preventDefault(); handleUpload(e.dataTransfer.files[0]); }}>
            <input ref={fileRef} type="file" accept=".csv,.xlsx" style={{ display: "none" }}
              onChange={e => handleUpload(e.target.files[0])} />
            {uploading ? "Uploading…" :
              uploadInfo ? (
                <div className="rp-upload-info">
                  <div>✓ {uploadInfo.filename} — {uploadInfo.rows} rows</div>
                  <div>Detected: {VERTICAL_EMOJI[uploadInfo.detected_vertical]} <strong>{uploadInfo.detected_vertical}</strong></div>
                  {uploadInfo.missing_required?.length > 0 && (
                    <div className="rp-upload-warn">
                      ⚠ Missing required columns: {uploadInfo.missing_required.join(", ")}
                    </div>
                  )}
                  {uploadInfo.valid && <div className="rp-upload-ok">✓ Schema valid</div>}
                </div>
              ) : (
                <div>CSV বা XLSX ফাইল drag করুন অথবা click করে বেছে নিন</div>
              )
            }
          </div>
        )}

        <div className="rp-config-section">
          <h3>Split Configuration</h3>
          <div className="rp-config-grid">
            <label className="rp-label">Train Ratio
              <select className="rp-select-sm" value={config.train_ratio}
                onChange={e => setConfig(c => ({...c, train_ratio: +e.target.value}))}>
                <option value={0.70}>70%</option>
                <option value={0.80}>80%</option>
                <option value={0.60}>60%</option>
              </select>
            </label>
            <label className="rp-label">Val Ratio
              <select className="rp-select-sm" value={config.val_ratio}
                onChange={e => setConfig(c => ({...c, val_ratio: +e.target.value}))}>
                <option value={0.15}>15%</option>
                <option value={0.10}>10%</option>
                <option value={0.20}>20%</option>
              </select>
            </label>
            <label className="rp-label">Test Ratio
              <input className="rp-input-sm" readOnly
                value={`${Math.round((1 - config.train_ratio - config.val_ratio) * 100)}%`} />
            </label>
            <label className="rp-label">CV Folds
              <select className="rp-select-sm" value={config.cv_folds}
                onChange={e => setConfig(c => ({...c, cv_folds: +e.target.value}))}>
                <option value={3}>3</option>
                <option value={5}>5</option>
                <option value={10}>10</option>
              </select>
            </label>
            <label className="rp-label">Random Seed
              <input className="rp-input-sm" type="number" value={config.random_seed}
                onChange={e => setConfig(c => ({...c, random_seed: +e.target.value}))} />
            </label>
            <label className="rp-label">Churn Threshold (days)
              <input className="rp-input-sm" type="number" value={config.churn_threshold_days}
                onChange={e => setConfig(c => ({...c, churn_threshold_days: +e.target.value}))} />
            </label>
          </div>
          <div className="rp-split-preview">
            Split preview:{" "}
            <strong>Train {Math.round(config.train_ratio * 100)}%</strong> /
            Val {Math.round(config.val_ratio * 100)}% /
            Test {Math.round((1 - config.train_ratio - config.val_ratio) * 100)}%
            &nbsp;·&nbsp; {config.cv_folds}-fold CV · seed={config.random_seed}
          </div>
          <div className="rp-split-note">
            ⚠ Forecasting always uses chronological split (not random shuffle).
            Return prediction always uses Customer_ID group-disjoint split.
          </div>
        </div>

        <div className="rp-config-section">
          <h3>ML Models to Train</h3>
          <div className="rp-model-checks">
            <label className="rp-check-item">
              <input type="checkbox" checked={config.run_churn}
                onChange={e => setConfig(c => ({...c, run_churn: e.target.checked}))} />
              <span>
                <strong>Future-Repeat / Churn Model</strong>
                <em> — Logistic + Random Forest, ROC-AUC / PR-AUC / Lift@10%</em>
              </span>
            </label>
            <label className="rp-check-item">
              <input type="checkbox" checked={config.run_segments}
                onChange={e => setConfig(c => ({...c, run_segments: e.target.checked}))} />
              <span>
                <strong>Customer Segmentation (K-Means)</strong>
                <em> — Silhouette score + tier profiles</em>
              </span>
            </label>
            {config.run_segments && (
              <div className="rp-model-sub">
                <label className="rp-label">Number of Clusters (K)
                  <select className="rp-select-sm" value={config.segment_k}
                    onChange={e => setConfig(c => ({...c, segment_k: +e.target.value}))}>
                    {[2,3,4,5,6,7,8].map(k => <option key={k} value={k}>{k}</option>)}
                  </select>
                </label>
              </div>
            )}
            <label className="rp-check-item">
              <input type="checkbox" checked={config.run_forecast}
                onChange={e => setConfig(c => ({...c, run_forecast: e.target.checked}))} />
              <span>
                <strong>Demand Forecast (HistGradientBoosting)</strong>
                <em> — Needs dense per-SKU time series (≥90 days, ≥500 SKU-day rows). Slow.</em>
              </span>
            </label>
          </div>
          <div className="rp-split-note">
            Churn + Segmentation: ~1–3 min for 30k rows.
            Demand Forecast: ~3–5 min additional (only enable for dense transaction data).
          </div>
        </div>

        <button type="submit" className="rp-btn-primary" disabled={saving ||
          (source === "upload" && (!uploadPath || !uploadInfo?.valid))}>
          {saving ? "Creating…" : "Create Experiment"}
        </button>
      </form>
    </div>
  );
}

// ── L3: Compare ───────────────────────────────────────────────────────────────

const COMPARE_COLS = [
  { key: "vertical",           label: "Vertical" },
  { key: "rows",               label: "Rows" },
  { key: "customers",          label: "Customers" },
  { key: "churn_rate",         label: "Churn Rate (descriptive)", fmt: pct },
  { key: "recency_mean",       label: "Avg Recency (days)",       fmt: v => num(v, 1) },
  { key: "frequency_mean",     label: "Avg Frequency",            fmt: v => num(v, 2) },
  { key: "monetary_mean",      label: "Avg Spend (BDT)",          fmt: v => num(v, 0) },
  { key: "seasonal_naive_wape",label: "Seasonal-Naive WAPE",      fmt: pct },
  { key: "top_segment",        label: "Largest Segment" },
  { key: "churn_roc_auc",      label: "Churn ROC-AUC (ML)",       fmt: v => num(v, 4) },
  { key: "churn_pr_auc",       label: "Churn PR-AUC (ML)",        fmt: v => num(v, 4) },
  { key: "seg_silhouette",     label: "Segmentation Silhouette",  fmt: v => num(v, 4) },
  { key: "seg_customers",      label: "Segmented Customers" },
  { key: "forecast_wape",      label: "Forecast WAPE (ML model)", fmt: pct },
];

function CompareTab({ completed }) {
  const [selected, setSelected] = useState([]);
  const [result,   setResult]   = useState(null);
  const [running,  setRunning]  = useState(false);
  const [err,      setErr]      = useState(null);

  function toggle(id) {
    setSelected(s => s.includes(id) ? s.filter(x => x !== id) : [...s, id]);
    setResult(null);
  }

  async function compare() {
    if (selected.length < 2) return;
    setRunning(true); setErr(null);
    try {
      const r = await api.portalCompare(selected);
      setResult(r.comparison);
    } catch (e) {
      setErr(e.message);
    } finally {
      setRunning(false);
    }
  }

  if (!completed.length) return (
    <div className="rp-empty">Completed experiment নেই। আগে run করুন।</div>
  );

  return (
    <div className="rp-section">
      <h2>Compare Experiments</h2>
      <p className="rp-hint">কমপক্ষে ২টি select করুন → Compare</p>

      <div className="rp-compare-select">
        {completed.map(e => (
          <label key={e.id} className="rp-check-item">
            <input type="checkbox" checked={selected.includes(e.id)}
              onChange={() => toggle(e.id)} />
            <span>{VERTICAL_EMOJI[e.vertical] || "📊"} {e.id} — {e.name}</span>
          </label>
        ))}
      </div>

      <button type="button" className="rp-btn-primary"
        disabled={selected.length < 2 || running}
        onClick={compare}>
        {running ? "Comparing…" : "Compare →"}
      </button>

      {err && <div className="rp-error">{err}</div>}

      {result && (
        <div className="rp-compare-table-wrap">
          <table className="rp-compare-table">
            <thead>
              <tr>
                <th>Metric</th>
                {result.map(r => (
                  <th key={r.id}>{r.id}<br /><small>{r.name}</small></th>
                ))}
              </tr>
            </thead>
            <tbody>
              {COMPARE_COLS.map(col => (
                <tr key={col.key}>
                  <td className="rp-col-label">{col.label}</td>
                  {result.map(r => {
                    const v = r[col.key];
                    return <td key={r.id}>{col.fmt ? col.fmt(v) : fmt(v)}</td>;
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── L4: Algorithm Trace ───────────────────────────────────────────────────────

const PIPELINE_STEPS = [
  { id: "ingest",    label: "Dataset Ingestion",      icon: "📂",
    desc: "CSV/XLSX loaded → schema validated → vertical auto-detected" },
  { id: "features",  label: "Feature Engineering",    icon: "⚙️",
    desc: "RFM computed (Recency, Frequency, Monetary) · CRM tier derived · seasonal flags added" },
  { id: "split",     label: "Train / Val / Test Split", icon: "✂️",
    desc: "Stratified random for classification & churn · Chronological for forecasting · Group-disjoint for returns" },
  { id: "classify",  label: "Classification (CRM Tier)", icon: "🏷️",
    desc: "XGBoost / Random Forest / Logistic Regression · 5-fold CV · Bootstrap CI · McNemar test" },
  { id: "cluster",   label: "Customer Segmentation",  icon: "🔵",
    desc: "K-Means K=2..10 · Elbow + Silhouette · OPTIMAL_K=4 (business choice, not metric peak)" },
  { id: "forecast",  label: "Sales Forecasting",      icon: "📈",
    desc: "Seasonal-naive · ARIMA(2,1,2) · LSTM (look-back 6) · Rolling-origin CV · WAPE metric" },
  { id: "churn",     label: "Churn Prediction",       icon: "⚠️",
    desc: "Random Forest · GroupShuffleSplit on Customer_ID · ROC-AUC + PR-AUC + Lift@10%" },
  { id: "bsmart",    label: "B-SMART Algorithm 1",    icon: "🎯",
    desc: "Candidates → Model Gate (EWMA vs baseline) → U(a) = benefit − cost − λ·risk → 13 constraints → R_t" },
  { id: "output",    label: "Recommendations (R_t)",  icon: "✅",
    desc: "Top-K actions (reorder / near-expiry / retention) · Each carries confidence & feasibility verdict" },
];

function TraceTab({ experiments }) {
  const [activeStep, setActiveStep] = useState(null);
  const completed = experiments.filter(e => e.status === "completed");
  const [selectedExp, setSelectedExp] = useState(null);
  const [expData, setExpData] = useState(null);

  useEffect(() => {
    if (!selectedExp) { setExpData(null); return; }
    api.portalGetExp(selectedExp).then(setExpData).catch(() => {});
  }, [selectedExp]);

  return (
    <div className="rp-section">
      <h2>Algorithm Trace</h2>
      <p className="rp-hint">B-SMART pipeline এর প্রতিটা step visualized — click করলে বিস্তারিত দেখবে।</p>

      {completed.length > 0 && (
        <label className="rp-label">Experiment select করুন (optional)
          <select className="rp-select" value={selectedExp || ""}
            onChange={e => setSelectedExp(e.target.value || null)}>
            <option value="">— শুধু pipeline দেখান —</option>
            {completed.map(e => (
              <option key={e.id} value={e.id}>{e.id} — {e.name}</option>
            ))}
          </select>
        </label>
      )}

      <div className="rp-pipeline">
        {PIPELINE_STEPS.map((step, i) => (
          <div key={step.id} className="rp-pipeline-step-wrap">
            <div className={`rp-pipeline-step${activeStep === step.id ? " active" : ""}`}
              onClick={() => setActiveStep(activeStep === step.id ? null : step.id)}>
              <span className="rp-step-icon">{step.icon}</span>
              <span className="rp-step-label">{step.label}</span>
            </div>
            {i < PIPELINE_STEPS.length - 1 && <div className="rp-pipeline-arrow">↓</div>}
          </div>
        ))}
      </div>

      {activeStep && (
        <div className="rp-step-detail">
          {(() => {
            const s = PIPELINE_STEPS.find(x => x.id === activeStep);
            return (
              <>
                <h3>{s.icon} {s.label}</h3>
                <p>{s.desc}</p>
                {expData && <StepData step={activeStep} expData={expData} />}
              </>
            );
          })()}
        </div>
      )}
    </div>
  );
}

function StepData({ step, expData }) {
  const u = expData?.results?.universal || {};
  const v = expData?.results?.vertical_specific || {};

  if (step === "ingest") return (
    <div className="rp-step-data">
      <div>Rows: <strong>{u.dataset_summary?.rows}</strong></div>
      <div>Customers: <strong>{u.dataset_summary?.customers}</strong></div>
      <div>Vertical detected: <strong>{u.dataset_summary?.vertical}</strong></div>
      <div>Date range: {u.dataset_summary?.date_range?.[0]} → {u.dataset_summary?.date_range?.[1]}</div>
    </div>
  );
  if (step === "features") return (
    <div className="rp-step-data">
      <div>Avg Recency: <strong>{num(u.rfm?.recency_mean, 1)} days</strong></div>
      <div>Avg Frequency: <strong>{num(u.rfm?.frequency_mean, 2)} transactions</strong></div>
      <div>Avg Monetary: <strong>৳{num(u.rfm?.monetary_mean, 0)}</strong></div>
    </div>
  );
  if (step === "cluster") return (
    <div className="rp-step-data">
      {Object.entries(u.segmentation?.segments || {}).map(([seg, cnt]) => (
        <div key={seg}>{seg}: <strong>{cnt} customers</strong></div>
      ))}
    </div>
  );
  if (step === "forecast") return (
    <div className="rp-step-data">
      <div>Monthly data points: <strong>{u.forecast?.monthly_points}</strong></div>
      <div>Seasonal-naive WAPE: <strong>{pct(u.forecast?.seasonal_naive_wape)}</strong></div>
    </div>
  );
  if (step === "churn") return (
    <div className="rp-step-data">
      <div>Churn rate ({u.churn?.threshold_days}+ days): <strong>{pct(u.churn?.churn_rate)}</strong></div>
      <div>Churned: <strong>{u.churn?.churned_count}</strong> | Active: <strong>{u.churn?.active_count}</strong></div>
    </div>
  );
  return <div className="rp-step-data">Experiment run করলে এখানে live data দেখাবে।</div>;
}

// ── L5: Export ────────────────────────────────────────────────────────────────

function ExportTab({ completed }) {
  const [selected, setSelected] = useState([]);
  const [result,   setResult]   = useState(null);
  const [running,  setRunning]  = useState(false);

  function toggle(id) { setSelected(s => s.includes(id) ? s.filter(x => x !== id) : [...s, id]); }

  async function buildExport() {
    if (!selected.length) return;
    setRunning(true);
    try {
      const r = await api.portalCompare(selected);
      setResult(r.comparison);
    } catch (e) {
      alert(e.message);
    } finally {
      setRunning(false);
    }
  }

  function downloadCSV() {
    if (!result) return;
    const header = ["Experiment", "Name", ...COMPARE_COLS.map(c => c.label)];
    const rows = result.map(r => [
      r.id, r.name,
      ...COMPARE_COLS.map(c => {
        const v = r[c.key];
        return c.fmt ? c.fmt(v) : fmt(v);
      }),
    ]);
    const csv = [header, ...rows].map(row => row.map(cell => `"${String(cell ?? "").replace(/"/g, '""')}"`).join(",")).join("\n");
    const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = "bsmart_comparison.csv"; a.click();
    URL.revokeObjectURL(url);
  }

  function copyMarkdown() {
    if (!result) return;
    const header = ["| Metric |", ...result.map(r => ` ${r.id} |`)].join("");
    const sep    = ["| --- |", ...result.map(() => " --- |")].join("");
    const rows   = COMPARE_COLS.map(col => {
      const cells = result.map(r => {
        const v = r[col.key];
        return ` ${col.fmt ? col.fmt(v) : fmt(v)} |`;
      });
      return `| ${col.label} |` + cells.join("");
    });
    navigator.clipboard.writeText([header, sep, ...rows].join("\n"));
    alert("Markdown table copied!");
  }

  if (!completed.length) return (
    <div className="rp-empty">Export করার মতো completed experiment নেই।</div>
  );

  return (
    <div className="rp-section">
      <h2>Export for Thesis</h2>

      <div className="rp-compare-select">
        {completed.map(e => (
          <label key={e.id} className="rp-check-item">
            <input type="checkbox" checked={selected.includes(e.id)} onChange={() => toggle(e.id)} />
            <span>{e.id} — {e.name}</span>
          </label>
        ))}
      </div>

      <button type="button" className="rp-btn-primary"
        disabled={!selected.length || running} onClick={buildExport}>
        {running ? "Building…" : "Generate Table →"}
      </button>

      {result && (
        <>
          <div className="rp-export-actions">
            <button type="button" className="rp-btn-secondary" onClick={downloadCSV}>
              ⬇ Download CSV
            </button>
            <button type="button" className="rp-btn-secondary" onClick={copyMarkdown}>
              📋 Copy Markdown Table
            </button>
          </div>

          <div className="rp-compare-table-wrap">
            <table className="rp-compare-table">
              <thead>
                <tr>
                  <th>Metric</th>
                  {result.map(r => <th key={r.id}>{r.id}<br /><small>{r.name}</small></th>)}
                </tr>
              </thead>
              <tbody>
                {COMPARE_COLS.map(col => (
                  <tr key={col.key}>
                    <td className="rp-col-label">{col.label}</td>
                    {result.map(r => {
                      const v = r[col.key];
                      return <td key={r.id}>{col.fmt ? col.fmt(v) : fmt(v)}</td>;
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
