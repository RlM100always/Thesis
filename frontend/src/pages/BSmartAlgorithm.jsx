// B-SMART Algorithm 1 — layers 5-8 of docs/BSMART_ARCHITECTURE.md.
//
// This is the thesis's own algorithm, so the page is built to be interrogated
// rather than admired: every action shows the evidence behind it, the
// per-constraint verdict that let it through, and the utility arithmetic.
//
// Research mode, so English/technical (the Bangla/English split is deliberate
// — see CLAUDE.md's frontend UI rules). The numbers come from the engine's own
// artifact and are never recomputed in the browser.

import { api } from "../api";
import { ErrorBox, Loading, useApi } from "../useApi";

const TYPE_LABEL = {
  reorder: "Reorder",
  expiry: "Near-expiry",
  retention: "Retention",
};

function bdt(value) {
  if (value === null || value === undefined) return "—";
  return `৳${Number(value).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

// A constraint verdict is only green when it actually passed. "BLOCKED", or
// anything that says it was capped, must not read as a clean pass.
function verdictTone(text) {
  const value = String(text ?? "").toLowerCase();
  if (value.startsWith("blocked")) return "bad";
  if (value.includes("capped") || value.includes("raised") || value.includes("pending")) return "warn";
  return "ok";
}

function ActionCard({ action, rank }) {
  const explanation = action.explanation;
  const title =
    action.type === "retention"
      ? `Contact ${action.customer_id}`
      : `${action.sku}${action.division ? ` · ${action.division}` : ""}`;

  return (
    <article className="bsmart-card">
      <header className="bsmart-card-head">
        <span className={`bsmart-type ${action.type}`}>{TYPE_LABEL[action.type] ?? action.type}</span>
        <h4>{title}</h4>
        <span className="bsmart-rank">#{rank}</span>
      </header>

      <div className="bsmart-utility">
        <span>benefit {bdt(action.benefit_bdt)}</span>
        <span>− cost {bdt(action.action_cost_bdt)}</span>
        <span>− λ·risk {bdt(action.risk_bdt)}</span>
        <strong>= U(a) {bdt(action.utility_bdt)}</strong>
      </div>

      <p className="bsmart-reason">{action.reason}</p>

      {explanation?.why && (
        <div className="bsmart-why">
          <h5>Why this quantity?</h5>
          <dl>
            {Object.entries(explanation.why).map(([key, value]) => (
              <div key={key}>
                <dt>{key.replaceAll("_", " ")}</dt>
                <dd>{String(value)}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}

      {explanation?.constraints && (
        <div className="bsmart-constraints">
          <h5>Constraint checks</h5>
          <ul>
            {Object.entries(explanation.constraints).map(([name, verdict]) => (
              <li key={name} className={verdictTone(verdict)}>
                <span className="cname">{name.replaceAll("_", " ")}</span>
                <span className="cverdict">{verdict}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <footer className="bsmart-card-foot">
        <span className={`confidence ${action.confidence}`}>confidence: {action.confidence}</span>
        {action.cold_chain_required && <span className="cold">cold chain</span>}
        <span className="cutoff">cutoff {action.cutoff}</span>
      </footer>
    </article>
  );
}

export default function BSmartAlgorithm() {
  const { data, error, loading } = useApi(() => api.bsmartLatest());

  if (loading) return <Loading what="B-SMART Algorithm 1 output" />;
  if (error) {
    return (
      <div className="page">
        <header className="page-head">
          <h2 className="page-title">B-SMART Algorithm 1</h2>
        </header>
        <div className="callout danger">
          <strong>No run found.</strong>
          <p>
            Run <code>python 13_bsmart_recommendation_engine.py</code> on the server,
            then reload this page.
          </p>
          <p className="hint">{error}</p>
        </div>
      </div>
    );
  }

  const { recommendations = [], summary = {}, assumptions = {}, cutoff } = data;
  const mix = summary.r_t_type_mix ?? {};

  return (
    <div className="page">
      <header className="page-head">
        <h2 className="page-title">B-SMART Algorithm 1 — R<sub>t</sub></h2>
        <p className="page-sub">
          The thesis's own recommendation algorithm, executed end to end at cutoff{" "}
          <strong>{cutoff}</strong>. Every number below was written by the engine; nothing
          on this page is recomputed in the browser.
        </p>
      </header>

      <div className="callout">
        <strong>Evidence tier.</strong> {data.evidence_tier}. The medicine catalogue is
        real; the transactions are synthetic. This demonstrates that the algorithm works
        — not that it has been proven on a real Bangladeshi pharmacy.
      </div>

      <section className="stat-row">
        <div className="stat"><b>{summary.total_candidates ?? "—"}</b><span>candidates generated</span></div>
        <div className="stat"><b>{(summary.reorder_feasible ?? 0) + (summary.expiry_feasible ?? 0) + (summary.retention_feasible ?? 0)}</b><span>passed all constraints</span></div>
        <div className="stat"><b>{summary.top_k_size ?? recommendations.length}</b><span>in R<sub>t</sub></span></div>
        <div className="stat"><b>{mix.reorder ?? 0}/{mix.expiry ?? 0}/{mix.retention ?? 0}</b><span>reorder / expiry / retention</span></div>
      </section>

      <div className="callout">
        <strong>R<sub>t</sub> is a balanced slate, not a leaderboard.</strong> Ranked purely
        by utility, retention dominates every slot — a customer's lifetime value dwarfs the
        margin on one cheap medicine line, which would hand the owner 15 phone calls and no
        stock actions. A per-type quota keeps the day's work usable.
      </div>

      <section className="bsmart-grid">
        {recommendations.map((action, index) => (
          <ActionCard
            key={`${action.type}-${action.sku ?? action.customer_id}-${index}`}
            action={action}
            rank={index + 1}
          />
        ))}
      </section>

      <section className="panel">
        <h3>Declared assumptions</h3>
        <p className="hint">
          These are not measured values. They are declared before any number is computed and
          printed with every run, so a reader can re-derive the arithmetic by hand.
        </p>
        <div className="assumption-grid">
          {Object.entries(assumptions).map(([key, value]) => (
            <div key={key}>
              <span className="akey">{key.replaceAll("_", " ")}</span>
              <span className="aval">
                {typeof value === "object" ? JSON.stringify(value) : String(value)}
              </span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
