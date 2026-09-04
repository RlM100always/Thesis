import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api, formatBDT, formatPct, SEGMENT_COLORS } from "../api";
import { DataSourceBanner } from "../components/DataSourceBanner";
import { useUi } from "../UiContext";
import { ErrorBox, Loading, useApi } from "../useApi";
import { useWorkspace } from "../WorkspaceContext";

// Cluster quality, read from the API rather than typed in. The silhouette used
// to be a string literal here and would have gone stale the moment the
// clustering step was rerun; predict._clustering_quality() recomputes it.
function ClusterQuality({ quality }) {
  const { simple } = useUi();
  if (!quality?.chosen_k) return null;

  const { chosen_k, chosen_silhouette, best_k, best_silhouette } = quality;
  const metricDisagrees = best_k !== chosen_k;

  return (
    <div className="callout">
      {simple ? (
        <>
          <strong>These groups overlap — treat them as a rough guide</strong>
          <p>
            The four groups are not sharply separated: plenty of customers sit near the
            boundary and could reasonably belong to either side. Customer behaviour here
            is more of a smooth range than four distinct kinds.
          </p>
          {metricDisagrees && (
            <p>
              Splitting into {best_k} groups would actually separate the data more cleanly.
              We use {chosen_k} because it maps onto how the business already thinks about
              its customers — a deliberate choice, not what the maths preferred.
            </p>
          )}
        </>
      ) : (
        <>
          <strong>
            K-Means silhouette: {chosen_silhouette.toFixed(4)} at K={chosen_k} — weak
          </strong>
          <p>
            Above 0.5 is normally considered well-separated, so these groups overlap
            considerably. Customer behaviour here is closer to a continuum than to
            distinct kinds; the split is a business convenience the data tolerates
            rather than one it demands.
          </p>
          {metricDisagrees && (
            <p>
              Silhouette peaks at K={best_k} ({best_silhouette.toFixed(4)}), so K={chosen_k}{" "}
              is a deliberate business choice, not the metric&rsquo;s pick.
            </p>
          )}
        </>
      )}
    </div>
  );
}

export default function Segments() {
  const { workspace, hasData } = useWorkspace();
  return hasData ? <MyGroups workspace={workspace} /> : <SampleSegments />;
}

// ── The visitor's own file ───────────────────────────────
// K-Means is re-fitted on their customers rather than reusing the study's four
// tiers. Clustering is unsupervised, so there is no label to leak — and the
// study's tiers are defined by its own CLV bands, which mean nothing here.
function MyGroups({ workspace }) {
  const { token, mapping } = workspace;
  const { data, error, loading } = useApi(
    () => api.uploadSegments(token, mapping),
    [token],
  );

  if (loading) return <Loading what="your customer groups" />;
  if (error) return <ErrorBox message={error} />;

  if (!data.available) {
    return (
      <>
        <h2 className="page-title">Your customer groups</h2>
        <DataSourceBanner />
        <div className="callout"><p>{data.reason}</p></div>
      </>
    );
  }

  const pieData = data.groups.map((g) => ({ name: g.name, value: g.count }));

  return (
    <>
      <h2 className="page-title">Your customer groups</h2>
      <p className="page-sub">
        {data.k} groups found in your own sales — not carried over from the research data
      </p>

      <DataSourceBanner />

      <div className="grid-2">
        <div className="card">
          <h3>How your customers split</h3>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie data={pieData} dataKey="value" nameKey="name" outerRadius={92} label>
                {pieData.map((_, i) => (
                  <Cell key={i} fill={Object.values(SEGMENT_COLORS)[i % 4]} />
                ))}
              </Pie>
              <Tooltip formatter={(v) => `${v.toLocaleString()} customers`} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <h3>What each group looks like</h3>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Group</th>
                  <th className="num">Customers</th>
                  <th className="num">Avg spend</th>
                  <th className="num">Last bought</th>
                  <th className="num">Share of sales</th>
                </tr>
              </thead>
              <tbody>
                {data.groups.map((g) => (
                  <tr key={g.cluster}>
                    <td><strong>{g.name}</strong></td>
                    <td className="num">{g.count.toLocaleString()}</td>
                    <td className="num">{formatBDT(g.avg_spend)}</td>
                    <td className="num">{g.avg_days_since_purchase.toFixed(0)} d ago</td>
                    <td className="num">{formatBDT(g.total_revenue)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div className="callout">
        <strong>
          Group separation: {data.separation}
          {data.separation === "weak" && " — treat these as a rough guide"}
        </strong>
        <p>{data.note}</p>
      </div>
    </>
  );
}

// ── The research dataset ─────────────────────────────────
function SampleSegments() {
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

      <DataSourceBanner />

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

      <ClusterQuality quality={data.clustering_quality} />
    </>
  );
}
