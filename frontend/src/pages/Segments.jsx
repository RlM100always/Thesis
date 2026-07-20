import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api, formatBDT, formatPct, SEGMENT_COLORS } from "../api";
import { ErrorBox, Loading, useApi } from "../useApi";

export default function Segments() {
  const { data, error, loading } = useApi(() => api.segments());

  if (loading) return <Loading what="segments" />;
  if (error) return <ErrorBox message={error} />;

  const profiles = data.supervised_profiles;
  const pieData = profiles.map((p) => ({ name: p.segment, value: p.count }));
  const barData = profiles.map((p) => ({
    segment: p.segment.replace("-", "\n"),
    monetary: p.avg_monetary / 1e6,
    churn: p.churn_rate * 100,
  }));

  return (
    <>
      <h2 className="page-title">Customer Segments</h2>
      <p className="page-sub">
        Four business tiers, with the K-Means clustering used as an independent check
      </p>

      <div className="grid-2">
        <div className="card">
          <h3>Distribution</h3>
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie data={pieData} dataKey="value" nameKey="name"
                   cx="50%" cy="50%" outerRadius={92} label={(e) => e.name}>
                {pieData.map((entry) => (
                  <Cell key={entry.name} fill={SEGMENT_COLORS[entry.name] || "#64748B"} />
                ))}
              </Pie>
              <Tooltip formatter={(v) => [`${v.toLocaleString()} customers`, ""]}
                       contentStyle={{ fontSize: 13, borderRadius: 8 }} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <h3>Average Spend vs Churn Rate</h3>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={barData} margin={{ top: 6, right: 10, left: 0, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="segment" tick={{ fontSize: 10 }} />
              <YAxis yAxisId="left" tick={{ fontSize: 11 }} />
              <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11 }} />
              <Tooltip contentStyle={{ fontSize: 13, borderRadius: 8 }} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar yAxisId="left" dataKey="monetary" name="Avg spend (৳M)" fill="#0A8754" />
              <Bar yAxisId="right" dataKey="churn" name="Churn (%)" fill="#E63946" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="card">
        <h3>Segment Profiles</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Segment</th>
                <th className="num">Customers</th>
                <th className="num">Share</th>
                <th className="num">Avg Recency</th>
                <th className="num">Avg Frequency</th>
                <th className="num">Avg Spend</th>
                <th className="num">Churn Rate</th>
              </tr>
            </thead>
            <tbody>
              {profiles.map((p) => (
                <tr key={p.segment}>
                  <td>
                    <span className="badge" style={{ background: SEGMENT_COLORS[p.segment] }}>
                      {p.segment}
                    </span>
                  </td>
                  <td className="num">{p.count.toLocaleString()}</td>
                  <td className="num">{formatPct(p.share)}</td>
                  <td className="num">{p.avg_recency.toFixed(0)} d</td>
                  <td className="num">{p.avg_frequency.toFixed(1)}</td>
                  <td className="num">{formatBDT(p.avg_monetary)}</td>
                  <td className="num">{formatPct(p.churn_rate)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="callout">
        <strong>K-Means silhouette score: 0.1725 — weak</strong>
        Above 0.5 is normally considered well-separated, so these four groups
        overlap considerably. Customer behaviour here is closer to a continuum
        than to four natural kinds; the four-way split is a business convenience
        the data tolerates rather than one it demands. Silhouette in fact peaks
        at K=2 (0.2837), so K=4 is a deliberate business choice, not the
        metric&rsquo;s pick.
      </div>
    </>
  );
}
