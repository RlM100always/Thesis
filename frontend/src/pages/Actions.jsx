// The landing page once a file is uploaded: what to do this week.
//
// Everything here already exists in the scored response and the overview — this
// page is assembly, not new computation. It exists because a risk score that
// stops at a number leaves the owner to work out the action themselves, which
// is exactly the step a non-technical user cannot take.

import { Link } from "react-router-dom";
import { api, formatBDT } from "../api";
import { DataSourceBanner } from "../components/DataSourceBanner";
import { ErrorBox, Loading, useApi } from "../useApi";
import { useWorkspace } from "../WorkspaceContext";

export default function Actions() {
  const { workspace, hasData } = useWorkspace();

  if (!hasData) return <NoData />;

  return <ActionsFor workspace={workspace} />;
}

function NoData() {
  return (
    <div className="page">
      <header className="page-head">
        <h2>Your business at a glance</h2>
        <p className="subtitle">
          Upload a file of your sales and this page will tell you who to contact this
          week, which customers matter most, and how sales are moving.
        </p>
      </header>
      <DataSourceBanner />
      <section className="card empty-cta">
        <div className="dropzone-icon">📂</div>
        <h3>No sales file yet</h3>
        <p className="hint">
          You need one row per sale, with columns for who bought, when, and how much
          they paid. A spreadsheet exported from your POS or accounts book is enough.
        </p>
        <Link to="/upload" className="btn-primary">Upload your sales file</Link>
      </section>
    </div>
  );
}

function ActionsFor({ workspace }) {
  const { token, mapping } = workspace;

  const scored = useApi(() => api.scoreUpload(token, mapping), [token]);
  const overview = useApi(() => api.uploadOverview(token, mapping), [token]);

  if (scored.loading || overview.loading) return <Loading what="your business" />;
  if (scored.error) return <ErrorBox message={scored.error} />;
  if (overview.error) return <ErrorBox message={overview.error} />;

  const rows = scored.data.rows;
  const s = scored.data.summary;
  const o = overview.data;

  const toCall = rows.filter((r) => r.already_lapsed).slice(0, 10);
  const best = [...rows].sort((a, b) => b.monetary - a.monetary).slice(0, 5);
  const change = o.change;

  return (
    <div className="page">
      <header className="page-head">
        <h2>What to do this week</h2>
        <p className="subtitle">
          {o.date_from} to {o.date_to} · {o.total_customers.toLocaleString()} customers ·{" "}
          {o.total_orders.toLocaleString()} sales
        </p>
      </header>

      <DataSourceBanner />

      <div className="kpi-grid">
        <div className="kpi">
          <span className="label">Sales in this file</span>
          <strong className="value">{formatBDT(o.total_revenue)}</strong>
          <span className="sub">across {o.months_covered} months</span>
        </div>
        {change && (
          <div className={`kpi ${change.pct < 0 ? "danger" : ""}`}>
            <span className="label">Last month vs the one before</span>
            <strong className="value">
              {change.pct == null
                ? "—"
                : `${change.pct > 0 ? "+" : ""}${(change.pct * 100).toFixed(0)}%`}
            </strong>
            <span className="sub">
              {formatBDT(change.latest_sales)} in {change.latest_month}
            </span>
          </div>
        )}
        <div className="kpi danger">
          <span className="label">Customers gone quiet</span>
          <strong className="value">{s.lapsed_count.toLocaleString()}</strong>
          <span className="sub">no purchase in {s.threshold_days}+ days</span>
        </div>
        <div className="kpi">
          <span className="label">Customers who came back</span>
          <strong className="value">{(o.repeat_customer_rate * 100).toFixed(0)}%</strong>
          <span className="sub">bought more than once</span>
        </div>
      </div>

      <div className="grid-2">
        <section className="card">
          <h3>Call these customers first</h3>
          <p className="hint">
            They spent the most among those who have stopped buying, so winning one back
            is worth the most.
          </p>
          {toCall.length === 0 ? (
            <p>Nobody has gone quiet — every customer has bought recently.</p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Customer</th>
                    <th className="num">Last bought</th>
                    <th className="num">Spent with you</th>
                  </tr>
                </thead>
                <tbody>
                  {[...toCall]
                    .sort((a, b) => b.monetary - a.monetary)
                    .map((r) => (
                      <tr key={r.customer_id}>
                        <td>{r.customer_id}</td>
                        <td className="num">{r.inactive_days} days ago</td>
                        <td className="num">{formatBDT(r.monetary)}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          )}
          <Link to="/upload" className="btn-secondary">See the full list</Link>
        </section>

        <section className="card">
          <h3>Your best customers</h3>
          <p className="hint">Worth protecting — a small thank-you goes further here.</p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Customer</th>
                  <th className="num">Orders</th>
                  <th className="num">Spent</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {best.map((r) => (
                  <tr key={r.customer_id}>
                    <td>{r.customer_id}</td>
                    <td className="num">{r.txn_count}</td>
                    <td className="num">{formatBDT(r.monetary)}</td>
                    <td>
                      <span className={`pill ${r.already_lapsed ? "danger" : "ok"}`}>
                        {r.already_lapsed ? "gone quiet" : "active"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      {o.best_month && (
        <section className="card">
          <h3>Your busiest and quietest months</h3>
          <p>
            Your strongest month was <strong>{o.best_month.month}</strong> at{" "}
            {formatBDT(o.best_month.sales)}, and the quietest was{" "}
            <strong>{o.worst_month.month}</strong> at {formatBDT(o.worst_month.sales)}.
            If that pattern repeats each year, plan stock and staff around it — the{" "}
            <Link to="/forecast">sales forecast</Link> uses exactly this repetition.
          </p>
        </section>
      )}
    </div>
  );
}
