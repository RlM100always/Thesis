import {
  Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api, formatBDT, formatPct } from "../api";
import { ErrorBox, Loading, useApi } from "../useApi";

export default function Overview() {
  const { data, error, loading } = useApi(() => api.overview());

  if (loading) return <Loading what="overview" />;
  if (error) return <ErrorBox message={error} />;

  const chartData = data.monthly_sales.map((p) => ({
    month: p.month,
    sales: p.sales / 1e6, // chart in millions; raw BDT is unreadable on an axis
  }));

  return (
    <>
      <h2 className="page-title">Overview</h2>
      <p className="page-sub">
        Bangladeshi retail transactions, 2021–2024 · {data.total_transactions.toLocaleString()} transactions
      </p>

      <div className="kpi-grid">
        <Kpi label="Customers" value={data.total_customers.toLocaleString()} />
        <Kpi label="Total Revenue" value={formatBDT(data.total_revenue)} tone="green" />
        <Kpi label="Avg Order Value" value={formatBDT(data.avg_order_value)} />
        <Kpi label="Churn Rate" value={formatPct(data.churn_rate)} tone="red" />
        <Kpi label="Avg Satisfaction" value={`${data.avg_csat.toFixed(2)} / 5`} />
      </div>

      <div className="card">
        <h3>Monthly Net Sales</h3>
        <p className="hint">
          The annual peaks are what let a &ldquo;same month last year&rdquo; rule
          out-forecast both the LSTM and ARIMA — see the Forecast page.
        </p>
        <ResponsiveContainer width="100%" height={300}>
          <AreaChart data={chartData} margin={{ top: 6, right: 12, left: 4, bottom: 4 }}>
            <defs>
              <linearGradient id="salesFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#0A8754" stopOpacity={0.32} />
                <stop offset="100%" stopColor="#0A8754" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="month" tick={{ fontSize: 11 }} interval={5} />
            <YAxis tick={{ fontSize: 11 }} label={{
              value: "BDT (millions)", angle: -90, position: "insideLeft",
              style: { fontSize: 11, fill: "#64748b" },
            }} />
            <Tooltip
              formatter={(v) => [`৳${v.toFixed(1)}M`, "Net sales"]}
              contentStyle={{ fontSize: 13, borderRadius: 8 }}
            />
            <Area type="monotone" dataKey="sales" stroke="#0A8754"
                  strokeWidth={2} fill="url(#salesFill)" />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="callout green">
        <strong>Best forecasting model: {data.best_forecast_model}</strong>
        A trivial seasonal baseline beats both trained models on this series.
        That is reported as a result, not hidden — it is the clearest evidence
        that Bangladeshi retail demand follows a strong annual cycle.
      </div>
    </>
  );
}

function Kpi({ label, value, tone }) {
  return (
    <div className="kpi">
      <div className="label">{label}</div>
      <div className={`value ${tone || ""}`}>{value}</div>
    </div>
  );
}
