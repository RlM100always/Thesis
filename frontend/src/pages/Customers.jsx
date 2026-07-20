import { useState } from "react";
import { api, formatBDT, SEGMENT_COLORS } from "../api";
import { ErrorBox, Loading, useApi } from "../useApi";

export default function Customers() {
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState(null);

  const { data, error, loading } = useApi(
    () => api.customers(query, page, 20),
    [query, page]
  );

  if (error) return <ErrorBox message={error} />;

  const totalPages = data ? Math.ceil(data.total / data.page_size) : 1;

  return (
    <>
      <h2 className="page-title">Customers</h2>
      <p className="page-sub">
        Search a customer to see its predicted segment, churn risk, and the
        features that drove the prediction
      </p>

      <div className="card">
        <div className="row" style={{ marginBottom: 14 }}>
          <input
            type="text"
            placeholder="Search by ID, e.g. CUST-BD-00042"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setPage(1); // a new query invalidates the current page number
            }}
          />
          {data && (
            <span style={{ color: "var(--text-muted)", fontSize: 13 }}>
              {data.total.toLocaleString()} customers
            </span>
          )}
        </div>

        {loading ? (
          <Loading what="customers" />
        ) : (
          <>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Customer ID</th>
                    <th>Segment</th>
                    <th className="num">Recency</th>
                    <th className="num">Frequency</th>
                    <th className="num">Total Spend</th>
                    <th className="num">Orders</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {data.customers.map((c) => (
                    <tr
                      key={c.customer_id}
                      className={`clickable ${selected === c.customer_id ? "selected" : ""}`}
                      onClick={() => setSelected(c.customer_id)}
                    >
                      <td><strong>{c.customer_id}</strong></td>
                      <td>
                        <span className="badge" style={{ background: SEGMENT_COLORS[c.segment] }}>
                          {c.segment}
                        </span>
                      </td>
                      <td className="num">{c.recency} d</td>
                      <td className="num">{c.frequency.toFixed(1)}</td>
                      <td className="num">{formatBDT(c.monetary)}</td>
                      <td className="num">{c.txn_count}</td>
                      <td>
                        <span className={`badge ${c.churned ? "high" : "low"}`}>
                          {c.churned ? "Churned" : "Active"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="row" style={{ marginTop: 14, justifyContent: "space-between" }}>
              <span style={{ fontSize: 13, color: "var(--text-muted)" }}>
                Page {page} of {totalPages.toLocaleString()}
              </span>
              <div className="row">
                <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                  ← Previous
                </button>
                <button disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
                  Next →
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {selected && <CustomerDetail customerId={selected} onClose={() => setSelected(null)} />}
    </>
  );
}

function CustomerDetail({ customerId, onClose }) {
  const { data, error, loading } = useApi(() => api.customer(customerId), [customerId]);

  if (loading) return <div className="card"><Loading what={customerId} /></div>;
  if (error) return <div className="card"><ErrorBox message={error} /></div>;

  const pred = data.predicted_segment;
  const churn = data.churn;
  const agrees = pred.segment === data.actual_segment;

  return (
    <div className="card">
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 14 }}>
        <h3 style={{ margin: 0 }}>{data.customer_id}</h3>
        <button onClick={onClose}>Close</button>
      </div>

      <div className="kpi-grid">
        <div className="kpi">
          <div className="label">Predicted Segment</div>
          <div className="value" style={{ fontSize: 18, color: SEGMENT_COLORS[pred.segment] }}>
            {pred.segment}
          </div>
          <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 3 }}>
            {(pred.confidence * 100).toFixed(1)}% confidence
          </div>
        </div>
        <div className="kpi">
          <div className="label">Actual Segment</div>
          <div className="value" style={{ fontSize: 18 }}>{data.actual_segment}</div>
          <div style={{ fontSize: 12, marginTop: 3 }}>
            <span className={`badge ${agrees ? "low" : "high"}`}>
              {agrees ? "Model agrees" : "Model disagrees"}
            </span>
          </div>
        </div>
        <div className="kpi">
          <div className="label">Churn Risk</div>
          <div className="value" style={{ fontSize: 18 }}>
            <span className={`badge ${churn.risk_band.toLowerCase()}`}>{churn.risk_band}</span>
          </div>
          <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 3 }}>
            {(churn.churn_probability * 100).toFixed(1)}% probability
          </div>
        </div>
        <div className="kpi">
          <div className="label">Total Spend</div>
          <div className="value" style={{ fontSize: 18 }}>{formatBDT(data.profile.monetary)}</div>
        </div>
      </div>

      <div className="grid-2">
        <div>
          <h3>Profile</h3>
          <div className="table-wrap">
            <table>
              <tbody>
                <ProfileRow label="Recency" value={`${data.profile.recency} days`} />
                <ProfileRow label="Frequency" value={data.profile.frequency.toFixed(1)} />
                <ProfileRow label="Orders" value={data.profile.txn_count} />
                <ProfileRow label="Avg order value" value={formatBDT(data.profile.avg_order_value)} />
                <ProfileRow label="Total profit" value={formatBDT(data.profile.total_profit)} />
                <ProfileRow label="Avg discount" value={`${data.profile.avg_discount.toFixed(1)}%`} />
                <ProfileRow label="Satisfaction" value={`${data.profile.avg_csat.toFixed(2)} / 5`} />
                <ProfileRow label="Return rate" value={`${(data.profile.return_rate * 100).toFixed(1)}%`} />
                <ProfileRow label="Tenure" value={`${data.profile.tenure_days} days`} />
                <ProfileRow label="Age" value={data.profile.age} />
              </tbody>
            </table>
          </div>
        </div>

        <div>
          <h3>Why this prediction?</h3>
          <p className="hint">
            SHAP contributions for this specific customer. Green pushed the model
            towards <strong>{pred.segment}</strong>; red pushed away from it.
          </p>
          {data.explanation ? (
            <ShapBars contributions={data.explanation} />
          ) : (
            <p style={{ color: "var(--text-muted)", fontSize: 13 }}>
              Explanation unavailable (the shap package is not installed).
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function ProfileRow({ label, value }) {
  return (
    <tr>
      <td style={{ color: "var(--text-muted)" }}>{label}</td>
      <td className="num"><strong>{value}</strong></td>
    </tr>
  );
}

function ShapBars({ contributions }) {
  // Scale every bar against the strongest contribution so the widths stay
  // comparable regardless of the absolute SHAP magnitudes.
  const max = Math.max(...contributions.map((c) => Math.abs(c.contribution)));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
      {contributions.map((c) => {
        const width = max ? (Math.abs(c.contribution) / max) * 100 : 0;
        const positive = c.contribution > 0;
        return (
          <div key={c.feature}>
            <div style={{
              display: "flex", justifyContent: "space-between",
              fontSize: 12, marginBottom: 2,
            }}>
              <span>{c.feature}</span>
              <span style={{ color: "var(--text-muted)", fontVariantNumeric: "tabular-nums" }}>
                {c.contribution > 0 ? "+" : ""}{c.contribution.toFixed(3)}
              </span>
            </div>
            <div style={{ background: "#eef2f6", borderRadius: 4, height: 9 }}>
              <div style={{
                width: `${width}%`, height: "100%", borderRadius: 4,
                background: positive ? "var(--green)" : "var(--red)",
              }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
