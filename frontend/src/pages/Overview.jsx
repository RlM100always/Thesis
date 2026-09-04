// Dual-source: the uploaded file when a workspace is open, the research
// dataset otherwise. The two share a chart and KPI grid but not their prose —
// "seasonal-naive beat the LSTM" is a finding about the study's data, not a
// claim about the visitor's business.

import {
  Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api, formatBDT, formatPct } from "../api";
import { DataSourceBanner } from "../components/DataSourceBanner";
import { ErrorBox, Loading, useApi } from "../useApi";
import { useWorkspace } from "../WorkspaceContext";

export default function Overview() {
  const { workspace, hasData } = useWorkspace();
  return hasData ? <MyOverview workspace={workspace} /> : <SampleOverview />;
}

// ── The visitor's own file ───────────────────────────────
function MyOverview({ workspace }) {
  const { token, mapping } = workspace;
  const { data, error, loading } = useApi(
    () => api.uploadOverview(token, mapping),
    [token],
  );

  if (loading) return <Loading what="your sales" />;
  if (error) return <ErrorBox message={error} />;

  const change = data.change;

  return (
    <>
      <h2 className="page-title">Your business</h2>
      <p className="page-sub">
        {data.date_from} to {data.date_to} · {data.total_orders.toLocaleString()} sales ·{" "}
        {data.months_covered} months
      </p>

      <DataSourceBanner />

      <div className="kpi-grid">
        <Kpi label="Total sales" value={formatBDT(data.total_revenue)} tone="green" />
        <Kpi label="Customers" value={data.total_customers.toLocaleString()} />
        <Kpi label="Average order" value={formatBDT(data.avg_order_value)} />
        <Kpi
          label="Bought more than once"
          value={formatPct(data.repeat_customer_rate, 0)}
        />
        {change && (
          <Kpi
            label={`${change.latest_month} vs the month before`}
            value={
              change.pct == null
                ? "—"
                : `${change.pct > 0 ? "+" : ""}${(change.pct * 100).toFixed(0)}%`
            }
            tone={change.pct < 0 ? "red" : "green"}
          />
        )}
      </div>

      <SalesChart points={data.monthly_sales} title="Your monthly sales" />

      {data.best_month && (
        <div className="callout">
          <strong>
            Busiest month: {data.best_month.month} · Quietest: {data.worst_month.month}
          </strong>
          <p>
            {formatBDT(data.best_month.sales)} against{" "}
            {formatBDT(data.worst_month.sales)} — a{" "}
            {(data.best_month.sales / Math.max(1, data.worst_month.sales)).toFixed(1)}x
            difference. If this repeats yearly, it is worth planning stock and staffing
            around.
          </p>
        </div>
      )}
    </>
  );
}

// ── The research dataset ─────────────────────────────────
function SampleOverview() {
  const { data, error, loading } = useApi(() => api.overview());

  if (loading) return <Loading what="overview" />;
  if (error) return <ErrorBox message={error} />;

  return (
    <>
      <h2 className="page-title">Overview</h2>
      <p className="page-sub">
        Bangladeshi retail transactions, 2021–2024 ·{" "}
        {data.total_transactions.toLocaleString()} transactions
      </p>

      <DataSourceBanner />

      <div className="kpi-grid">
        <Kpi label="Customers" value={data.total_customers.toLocaleString()} />
        <Kpi label="Total Revenue" value={formatBDT(data.total_revenue)} tone="green" />
        <Kpi label="Avg Order Value" value={formatBDT(data.avg_order_value)} />
        <Kpi label="Churn Rate" value={formatPct(data.churn_rate)} tone="red" />
        <Kpi label="Avg Satisfaction" value={`${data.avg_csat.toFixed(2)} / 5`} />
      </div>

      <SalesChart
        points={data.monthly_sales}
        title="Monthly Net Sales"
        hint="The annual peaks are what let a “same month last year” rule out-forecast both the LSTM and ARIMA — see the Forecast page."
      />

      <div className="callout green">
        <strong>Best forecasting model: {data.best_forecast_model}</strong>
        A trivial seasonal baseline beats both trained models on this series. That is
        reported as a result, not hidden — it is the clearest evidence that Bangladeshi
        retail demand follows a strong annual cycle.
      </div>
    </>
  );
}

function SalesChart({ points, title, hint }) {
  const chartData = points.map((p) => ({
    month: p.month,
    sales: p.sales / 1e6, // chart in millions; raw BDT is unreadable on an axis
  }));

  return (
    <div className="card">
      <h3>{title}</h3>
      {hint && <p className="hint">{hint}</p>}
      <ResponsiveContainer width="100%" height={300}>
        <AreaChart data={chartData} margin={{ top: 6, right: 12, left: 4, bottom: 4 }}>
          <defs>
            <linearGradient id="salesFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#0A8754" stopOpacity={0.32} />
              <stop offset="100%" stopColor="#0A8754" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="month" tick={{ fontSize: 11 }}
                 interval={Math.max(0, Math.floor(chartData.length / 8))} />
          <YAxis tick={{ fontSize: 11 }} label={{
            value: "BDT (millions)", angle: -90, position: "insideLeft",
            style: { fontSize: 11, fill: "var(--text-muted)" },
          }} />
          <Tooltip formatter={(v) => [`৳${v.toFixed(1)}M`, "Sales"]}
                   contentStyle={{ fontSize: 13, borderRadius: 8 }} />
          <Area type="monotone" dataKey="sales" stroke="#0A8754"
                strokeWidth={2} fill="url(#salesFill)" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
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
