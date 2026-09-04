import {
  CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api, formatBDT } from "../api";
import { DataSourceBanner } from "../components/DataSourceBanner";
import { TermLabel } from "../components/Metric";
import { ErrorBox, Loading, useApi } from "../useApi";
import { useWorkspace } from "../WorkspaceContext";

const MODEL_META = {
  seasonal_naive: { label: "Seasonal-Naive", color: "#F5A623" },
  lstm: { label: "LSTM", color: "#0A8754" },
  arima: { label: "ARIMA(2,1,2)", color: "#E63946" },
};

export default function Forecast() {
  const { workspace, hasData } = useWorkspace();
  return hasData ? <MyForecast workspace={workspace} /> : <SampleForecast />;
}

// ── The visitor's own file ───────────────────────────────
// Only seasonal-naive runs here. The trained LSTM and ARIMA are fitted to the
// study's own 48-month series and cannot be applied to a different business —
// and since seasonal-naive is what won that comparison, the best method is also
// the only one that transfers.
function MyForecast({ workspace }) {
  const { token, mapping } = workspace;
  const { data, error, loading } = useApi(
    () => api.uploadForecast(token, mapping),
    [token],
  );

  if (loading) return <Loading what="your forecast" />;
  if (error) return <ErrorBox message={error} />;

  if (!data.available) {
    return (
      <>
        <h2 className="page-title">Sales forecast</h2>
        <p className="page-sub">Not enough history yet</p>
        <DataSourceBanner />
        <div className="callout">
          <strong>We cannot forecast from this file yet</strong>
          <p>{data.reason}</p>
          <p className="hint">
            Come back with a longer export — most accounting software can export
            several years at once.
          </p>
        </div>
      </>
    );
  }

  const chartData = [
    ...data.history.map((p) => ({ period: p.month, Actual: p.sales / 1e6 })),
    ...data.predictions.map((p) => ({ period: p.month, Predicted: p.predicted / 1e6 })),
  ];

  return (
    <>
      <h2 className="page-title">Your sales forecast</h2>
      <p className="page-sub">
        Next {data.predictions.length} months · based on {data.months_covered} months of
        your sales
      </p>

      <DataSourceBanner />

      <div className="kpi-grid">
        {data.predictions.map((p) => (
          <div className="kpi" key={p.month}>
            <div className="label">{p.month}</div>
            <div className="value">{formatBDT(p.predicted)}</div>
            <span className="sub">same as {p.basis_month}</span>
          </div>
        ))}
      </div>

      <div className="card">
        <h3>Your sales, with what comes next</h3>
        <ResponsiveContainer width="100%" height={320}>
          <LineChart data={chartData} margin={{ top: 6, right: 14, left: 4, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="period" tick={{ fontSize: 10.5 }}
                   interval={Math.max(0, Math.floor(chartData.length / 8))} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip formatter={(v) => `৳${v.toFixed(1)}M`}
                     contentStyle={{ fontSize: 13, borderRadius: 8 }} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Line type="monotone" dataKey="Actual" stroke="#0D1B2A" strokeWidth={2}
                  dot={false} connectNulls />
            <Line type="monotone" dataKey="Predicted" stroke="#F5A623" strokeWidth={2}
                  strokeDasharray="6 3" connectNulls />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="callout">
        <strong>How this forecast is made — and how far to trust it</strong>
        <p>{data.note}</p>
        {data.accuracy ? (
          <p>
            Checked against your own past: over {data.accuracy.months_tested} months this
            rule was off by about {data.accuracy.mape.toFixed(0)}% in a typical month (
            {formatBDT(data.accuracy.mae)}). Use it for planning, not for a promise.
          </p>
        ) : (
          <p>
            There is not yet enough history to measure how accurate this is on your
            business — that needs about two years. Treat these as rough guides.
          </p>
        )}
      </div>
    </>
  );
}

// ── The research dataset ─────────────────────────────────
function SampleForecast() {
  const { data, error, loading } = useApi(() => api.forecast());

  if (loading) return <Loading what="forecast" />;
  if (error) return <ErrorBox message={error} />;

  const chartData = data.points.map((p) => ({
    period: p.period,
    Actual: p.actual / 1e6,
    "Seasonal-Naive": p.seasonal_naive / 1e6,
    LSTM: p.lstm / 1e6,
    ARIMA: p.arima / 1e6,
  }));

  // Rank by RMSE so the winner is determined by the data, not hardcoded
  const ranked = Object.entries(data.metrics)
    .map(([key, m]) => ({ key, ...MODEL_META[key], ...m }))
    .sort((a, b) => a.rmse - b.rmse);

  return (
    <>
      <h2 className="page-title">Sales Forecasting</h2>
      <p className="page-sub">Six held-out months · LSTM vs ARIMA vs a seasonal-naive baseline</p>

      <DataSourceBanner />

      <div className="callout">
        <strong>The trivial baseline wins</strong>
        {data.note} An earlier version of this project reported only
        &ldquo;LSTM beats ARIMA by 21%&rdquo;, which is true but misleading —
        both lose to predicting that each month simply repeats the same month
        one year earlier.
      </div>

      <div className="card">
        <h3>Actual vs Forecast</h3>
        <ResponsiveContainer width="100%" height={330}>
          <LineChart data={chartData} margin={{ top: 6, right: 14, left: 4, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="period" tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 11 }} label={{
              value: "BDT (millions)", angle: -90, position: "insideLeft",
              style: { fontSize: 11, fill: "#64748b" },
            }} />
            <Tooltip formatter={(v) => `৳${v.toFixed(1)}M`}
                     contentStyle={{ fontSize: 13, borderRadius: 8 }} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Line type="monotone" dataKey="Actual" stroke="#0D1B2A"
                  strokeWidth={2.6} dot={{ r: 4 }} />
            <Line type="monotone" dataKey="Seasonal-Naive" stroke="#F5A623"
                  strokeWidth={2} strokeDasharray="6 3" dot={{ r: 3 }} />
            <Line type="monotone" dataKey="LSTM" stroke="#0A8754"
                  strokeWidth={2} strokeDasharray="4 4" dot={{ r: 3 }} />
            <Line type="monotone" dataKey="ARIMA" stroke="#E63946"
                  strokeWidth={2} strokeDasharray="2 3" dot={{ r: 3 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="card">
        <h3>Error Metrics</h3>
        <p className="hint">Lower is better. Ranked by RMSE.</p>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Model</th>
                <th className="num"><TermLabel termKey="rmse" /></th>
                <th className="num"><TermLabel termKey="mae" /></th>
                <th className="num"><TermLabel termKey="mape" /></th>
                <th>Verdict</th>
              </tr>
            </thead>
            <tbody>
              {ranked.map((m, i) => (
                <tr key={m.key}>
                  <td>
                    <span className="badge" style={{ background: m.color }}>{m.label}</span>
                  </td>
                  <td className="num">{(m.rmse / 1e6).toFixed(2)}M</td>
                  <td className="num">{(m.mae / 1e6).toFixed(2)}M</td>
                  <td className="num">{m.mape.toFixed(2)}%</td>
                  <td>
                    {i === 0
                      ? <span className="badge low">Best</span>
                      : <span className="badge outline">
                          +{(((m.rmse - ranked[0].rmse) / ranked[0].rmse) * 100).toFixed(0)}% worse
                        </span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="callout green">
        <strong>Why this is a positive result</strong>
        A seasonal baseline winning is direct evidence that Bangladeshi retail
        demand follows a strong annual cycle — Ramadan, Eid, Pohela Boishakh —
        which is the central claim of this thesis. On 48 monthly points
        (36 training sequences) deep learning adds complexity without accuracy.
        The practical recommendation for a small business is to start with the
        seasonal rule.
      </div>
    </>
  );
}
