import {
  CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api } from "../api";
import { ErrorBox, Loading, useApi } from "../useApi";

const MODEL_META = {
  seasonal_naive: { label: "Seasonal-Naive", color: "#F5A623" },
  lstm: { label: "LSTM", color: "#0A8754" },
  arima: { label: "ARIMA(2,1,2)", color: "#E63946" },
};

export default function Forecast() {
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
                <th className="num">RMSE</th>
                <th className="num">MAE</th>
                <th className="num">MAPE</th>
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
