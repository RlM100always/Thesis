// Live churn calculator: drag a slider, watch the risk move.
//
// The four sliders are the levers a business owner actually recognises. Every
// other feature the model expects is sent at a neutral value, and the page says
// so rather than implying a full profile was supplied.

import { useEffect, useMemo, useState } from "react";
import { api, formatBDT } from "../api";
import { useUi } from "../UiContext";

const LEVERS = [
  { key: "Txn_Count", label: "Orders placed so far", min: 1, max: 40, step: 1, def: 6,
    fmt: (v) => `${v} orders` },
  { key: "Monetary", label: "Total spent", min: 5000, max: 3000000, step: 5000, def: 250000,
    fmt: formatBDT },
  { key: "Purchase_Rate", label: "Orders per month", min: 0.1, max: 8, step: 0.1, def: 1.5,
    fmt: (v) => `${v.toFixed(1)} / month` },
  { key: "Tenure_Days", label: "How long a customer", min: 0, max: 1400, step: 10, def: 400,
    fmt: (v) => `${Math.round(v / 30)} months` },
];

const BAND_TONE = { High: "danger", Medium: "warn", Low: "ok" };

export default function WhatIf() {
  const { simple } = useUi();
  const [vals, setVals] = useState(() =>
    Object.fromEntries(LEVERS.map((l) => [l.key, l.def])),
  );
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [pending, setPending] = useState(false);

  // Derived so the two stay consistent — a customer's average order is their
  // total divided by their order count, not an independent dial.
  const features = useMemo(
    () => ({
      ...vals,
      Frequency: vals.Purchase_Rate,
      Avg_Order_Value: vals.Monetary / Math.max(1, vals.Txn_Count),
      Max_Order_Value: vals.Monetary / Math.max(1, vals.Txn_Count),
    }),
    [vals],
  );

  // Debounced so dragging a slider does not fire a request per pixel.
  useEffect(() => {
    setPending(true);
    const id = setTimeout(async () => {
      try {
        setResult(await api.predictChurn(features));
        setError(null);
      } catch (e) {
        setError(e.message);
      } finally {
        setPending(false);
      }
    }, 250);
    return () => clearTimeout(id);
  }, [features]);

  const pct = result ? Math.round(result.churn_probability * 100) : 0;
  const tone = result ? BAND_TONE[result.risk_band] : "";

  return (
    <div className="page">
      <header className="page-head">
        <h2>{simple ? "Risk calculator" : "Churn model — interactive inference"}</h2>
        <p className="subtitle">
          Move the sliders to describe a customer and see how likely they are to stop
          buying. Useful for understanding what the model reacts to.
        </p>
      </header>

      {error && <div className="callout danger"><p>{error}</p></div>}

      <div className="grid-2">
        <section className="card">
          <h3>Describe the customer</h3>
          {LEVERS.map((l) => (
            <label key={l.key} className="slider-row">
              <span className="slider-head">
                <span>{l.label}</span>
                <strong>{l.fmt(vals[l.key])}</strong>
              </span>
              <input
                type="range"
                min={l.min}
                max={l.max}
                step={l.step}
                value={vals[l.key]}
                onChange={(e) =>
                  setVals((v) => ({ ...v, [l.key]: Number(e.target.value) }))
                }
              />
            </label>
          ))}
          <button
            type="button"
            className="btn-secondary"
            onClick={() => setVals(Object.fromEntries(LEVERS.map((l) => [l.key, l.def])))}
          >
            Reset
          </button>
        </section>

        <section className={`card risk-panel ${tone}`}>
          <h3>Risk of losing this customer</h3>
          <div className={`risk-dial ${pending ? "pending" : ""}`}>
            <span className="risk-pct">{pct}%</span>
            <span className={`pill ${tone}`}>{result?.risk_band ?? "…"} risk</span>
          </div>

          <p className="risk-advice">
            {result?.risk_band === "High" &&
              "Reach out this week. A discount or loyalty reward is worth the cost here."}
            {result?.risk_band === "Medium" &&
              "Worth a follow-up message or a seasonal offer before the gap widens."}
            {result?.risk_band === "Low" &&
              "This customer looks steady. Keep them on the regular newsletter."}
          </p>

          {result && (
            <div className="callout">
              <p className="hint">
                {simple ? (
                  <>
                    Based on {LEVERS.length} details you set. The model normally uses{" "}
                    {result.missing_fields.length + LEVERS.length + 3} pieces of information —
                    the rest are left at typical values, so treat this as a guide to what
                    moves the needle rather than a verdict on a real person.
                  </>
                ) : (
                  <>
                    {result.model} · churn defined as recency &gt; {result.threshold_days} days ·{" "}
                    {result.missing_fields.length} of the model's features defaulted.
                  </>
                )}
              </p>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
