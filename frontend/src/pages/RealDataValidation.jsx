// Real-data validation study — supplements, never replaces, the synthetic
// thesis pipeline's results on Model Report. No public dataset combining
// Bangladeshi origin + real transactions + customer-level records exists
// (searched exhaustively — see docs/REAL_DATA_SOURCES.md), so this runs the
// SAME leak-free training code on two real datasets, each honestly labelled
// for what it can and cannot support, rather than overclaiming either one.

import { api } from "../api";
import { ErrorBox, Loading, useApi } from "../useApi";

export default function RealDataValidation() {
  const { data, error, loading } = useApi(() => api.realDataValidation());

  if (loading) return <Loading what="real-data validation study" />;
  if (error) {
    return (
      <div className="page">
        <header className="page-head">
          <h2 className="page-title">Real-data validation</h2>
        </header>
        <div className="callout danger">
          <strong>Not generated yet.</strong>
          <p>
            Run <code>python -m ml.real_data_validation</code> on the server, then reload
            this page.
          </p>
          <p className="hint">{error}</p>
        </div>
      </div>
    );
  }

  const or2 = data.datasets.online_retail_ii;
  const bd = data.datasets.bd_retailer_demand;

  return (
    <div className="page">
      <header className="page-head">
        <h2 className="page-title">Real-data validation</h2>
        <p className="page-sub">
          The synthetic pipeline's ablation (Model Report) stays as the thesis's leakage
          case study. This page is different: it runs the identical leak-free training
          code on real, publicly-available datasets — not a replacement for the synthetic
          results, a supplement.
        </p>
      </header>

      <div className="callout">
        <strong>Why two datasets, and why neither is Bangladeshi customer data</strong>
        <p>
          An exhaustive search (Kaggle, Mendeley/Data in Brief, IEEE DataPort, UCI, and
          Bangladeshi platform data releases) found no public dataset combining Bangladeshi
          origin, real observed transactions, and customer-level records. The closest
          Bangladeshi candidate (a Mendeley retail-network dataset) reports algorithmic
          sales targets, not actual sales, and has no customer field. So two real datasets
          are used instead, each labelled for exactly what it proves — never blended into
          one number, and never presented as Bangladeshi customer-level evidence.
        </p>
      </div>

      {or2 && <OnlineRetailCard result={or2} />}
      {bd && <BdRetailerCard result={bd} />}
    </div>
  );
}

function Metric({ label, value }) {
  return (
    <div className="kpi">
      <span className="label">{label}</span>
      <strong className="value">{value}</strong>
    </div>
  );
}

function OnlineRetailCard({ result }) {
  if (result.available === false) {
    return (
      <section className="card">
        <h3>UCI Online Retail II</h3>
        <p className="hint">Not available: {result.reason}</p>
      </section>
    );
  }

  const forecast = result.forecast;
  const churn = result.future_repeat;

  return (
    <section className="card">
      <h3>
        UCI Online Retail II <span className="badge outline">non-Bangladeshi</span>
      </h3>
      <p className="hint">
        Real invoice-level transactions from a UK gift retailer, {result.date_from} to{" "}
        {result.date_to}. {result.rows_used.toLocaleString()} lines used after dropping{" "}
        {result.cancelled_rows_dropped?.toLocaleString()} cancelled/returned lines —
        {" "}{result.distinct_customers.toLocaleString()} customers,{" "}
        {result.distinct_skus.toLocaleString()} SKUs. Real transactions, genuinely
        customer-level — just not from Bangladesh, so read this as a validation of the
        modelling method, not a claim about Bangladeshi buying behaviour.
      </p>

      {forecast?.available ? (
        <>
          <h4>Demand forecast (held-out WAPE, lower is better)</h4>
          <div className="kpi-grid">
            <Metric label="Gradient boosting" value={`${(forecast.hist_gradient_boosting.wape * 100).toFixed(1)}%`} />
            <Metric label="Seasonal-naive (baseline)" value={`${(forecast.seasonal_naive_7.wape * 100).toFixed(1)}%`} />
          </div>
        </>
      ) : (
        <p className="hint">Forecast: {forecast?.reason}</p>
      )}

      {churn?.available ? (
        <>
          <h4>Future-repeat / churn model (held-out, chronological split)</h4>
          <div className="kpi-grid">
            <Metric label="Winner" value={churn.winner_by_brier} />
            <Metric label="ROC-AUC" value={`${(churn.models[churn.winner_by_brier].roc_auc * 100).toFixed(1)}%`} />
            <Metric label="PR-AUC" value={`${(churn.models[churn.winner_by_brier].pr_auc * 100).toFixed(1)}%`} />
            <Metric label="Lift @10%" value={`${churn.models[churn.winner_by_brier].lift_at_10.toFixed(2)}×`} />
          </div>
        </>
      ) : (
        <p className="hint">Future-repeat model: {churn?.reason}</p>
      )}
    </section>
  );
}

function BdRetailerCard({ result }) {
  if (result.available === false) {
    return (
      <section className="card">
        <h3>Bangladeshi retailer demand series</h3>
        <p className="hint">Not available: {result.reason}</p>
      </section>
    );
  }

  const forecast = result.forecast;

  return (
    <section className="card">
      <h3>
        Bangladeshi retailer demand series <span className="badge low">real Bangladeshi data</span>
      </h3>
      <p className="hint">
        Mendeley DOI 10.17632/xwmbk7n3c8.1 — real daily sales for one product from an
        actual Bangladeshi retailer (Khulna University of Engineering and Technology),
        {" "}{result.date_from} to {result.date_to} ({result.rows_used.toLocaleString()} days).
        {" "}{result.note} No revenue or customer figure is derived from this dataset —
        only demand (quantity), which is the one field it genuinely reports.
      </p>

      {forecast?.available ? (
        <div className="kpi-grid">
          <Metric label="Gradient boosting" value={`${(forecast.hist_gradient_boosting.wape * 100).toFixed(1)}%`} />
          <Metric label="Seasonal-naive (baseline)" value={`${(forecast.seasonal_naive_7.wape * 100).toFixed(1)}%`} />
        </div>
      ) : (
        <p className="hint">Forecast: {forecast?.reason}</p>
      )}
    </section>
  );
}
