import {
  Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api, formatPct } from "../api";
import { ErrorBox, Loading, useApi } from "../useApi";

export default function ModelReport() {
  const { data, error, loading } = useApi(() => api.modelMetrics());

  if (loading) return <Loading what="model report" />;
  if (error) return <ErrorBox message={error} />;

  const { segment, ablation, churn, returns } = data;
  const models = Object.entries(segment.models);

  const ablationChart = ablation.map((a) => ({
    name: a.variant.replace(/ \(.*\)/, ""),
    accuracy: a.accuracy * 100,
    honest: a.variant.includes("honest"),
  }));

  return (
    <>
      <h2 className="page-title">Model Report</h2>
      <p className="page-sub">
        Validated performance, and the data leakage that had to be removed to measure it
      </p>

      <div className="callout">
        <strong>Why accuracy fell from 94.81% to {formatPct(segment.models.XGBoost.accuracy, 2)}</strong>
        The original pipeline leaked the answer into the features in two ways.
        The lower number is the honest one; the drop is the main finding of this
        project, not a regression.
      </div>

      <div className="card">
        <h3>Leakage Ablation</h3>
        <p className="hint">
          Same task, same split strategy — only the leaks differ.
        </p>
        <ResponsiveContainer width="100%" height={230}>
          <BarChart data={ablationChart} margin={{ top: 6, right: 12, left: 0, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="name" tick={{ fontSize: 10.5 }} />
            <YAxis domain={[0, 100]} tick={{ fontSize: 11 }}
                   label={{ value: "Accuracy (%)", angle: -90, position: "insideLeft",
                            style: { fontSize: 11, fill: "#64748b" } }} />
            <Tooltip formatter={(v) => `${v.toFixed(2)}%`}
                     contentStyle={{ fontSize: 13, borderRadius: 8 }} />
            <Bar dataKey="accuracy" name="Accuracy">
              {ablationChart.map((e, i) => (
                <Cell key={i} fill={e.honest ? "#0A8754" : "#E63946"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>

        <div className="table-wrap" style={{ marginTop: 12 }}>
          <table>
            <thead>
              <tr>
                <th>Variant</th>
                <th className="num">Accuracy</th>
                <th className="num">McNemar p</th>
                <th>Interpretation</th>
              </tr>
            </thead>
            <tbody>
              {ablation.map((a) => (
                <tr key={a.variant}>
                  <td>{a.variant}</td>
                  <td className="num"><strong>{formatPct(a.accuracy, 2)}</strong></td>
                  <td className="num">{a.mcnemar_p == null ? "—" : a.mcnemar_p.toFixed(4)}</td>
                  <td style={{ fontSize: 12.5, color: "var(--text-muted)" }}>
                    {a.mcnemar_p == null
                      ? "Both leaks present"
                      : a.mcnemar_p >= 0.05
                        ? "Model choice is meaningless — one feature decides everything"
                        : "Model choice finally matters"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="callout green" style={{ marginTop: 16, marginBottom: 0 }}>
          <strong>The subtler finding</strong>
          With the CLV feature present, McNemar&rsquo;s test says XGBoost and
          Random Forest are indistinguishable (p = 0.52). Only after removing it
          does the difference become significant (p = 0.01). A leak does not just
          inflate a score — it erases the model comparison the thesis rests on.
        </div>
      </div>

      <div className="card">
        <h3>Segment Classification — leak-free</h3>
        <p className="hint">
          {segment.n_test} held-out customers · {segment.n_features} features ·
          95% CIs from 2,000 bootstrap resamples
        </p>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Model</th>
                <th className="num">Accuracy</th>
                <th className="num">95% CI</th>
                <th className="num">F1-macro</th>
                <th className="num">5-fold CV</th>
              </tr>
            </thead>
            <tbody>
              {models
                .sort((a, b) => b[1].accuracy - a[1].accuracy)
                .map(([name, m]) => (
                  <tr key={name}>
                    <td><strong>{name}</strong></td>
                    <td className="num">{formatPct(m.accuracy, 2)}</td>
                    <td className="num" style={{ color: "var(--text-muted)" }}>
                      [{formatPct(m.ci_low, 1)}, {formatPct(m.ci_high, 1)}]
                    </td>
                    <td className="num">{formatPct(m.f1_macro, 2)}</td>
                    <td className="num">
                      {formatPct(m.cv_mean, 2)} ± {(m.cv_std * 100).toFixed(2)}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
        <p style={{ fontSize: 13, marginTop: 12, marginBottom: 0 }}>
          <strong>McNemar (XGBoost vs Random Forest):</strong>{" "}
          p = {segment.mcnemar.pvalue.toFixed(4)} — {segment.mcnemar.verdict}
        </p>
      </div>

      <div className="grid-2">
        <BinaryModelCard
          title="Churn Prediction"
          subtitle={`Churn = inactive > ${churn.threshold_days} days · base rate ${formatPct(churn.churn_rate)}`}
          results={churn.models}
          best={churn.best_model}
          verdict="ROC-AUC 0.71 with 2.48x lift in the top 10% — usable to prioritise a retention campaign."
          tone="green"
        />
        <BinaryModelCard
          title="Return Prediction"
          subtitle="Predicting returns from pre-dispatch information only"
          results={returns.models}
          best={returns.best_model}
          verdict="ROC-AUC 0.58 — a weak signal. Reported as a negative result: returns are close to random with respect to what is knowable before dispatch."
          tone="amber"
        />
      </div>
    </>
  );
}

function BinaryModelCard({ title, subtitle, results, best, verdict, tone }) {
  return (
    <div className="card">
      <h3>{title}</h3>
      <p className="hint">{subtitle}</p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Model</th>
              <th className="num">PR-AUC</th>
              <th className="num">ROC-AUC</th>
              <th className="num">Lift@10%</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(results).map(([name, r]) => (
              <tr key={name}>
                <td>
                  {name === best ? <strong>{name}</strong> : name}
                  {name === best && <span className="badge low" style={{ marginLeft: 7 }}>Best</span>}
                </td>
                <td className="num">{r.pr_auc.toFixed(4)}</td>
                <td className="num">{r.roc_auc.toFixed(4)}</td>
                <td className="num">{r.lift_10.toFixed(2)}x</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className={`callout ${tone === "green" ? "green" : ""}`}
           style={{ marginTop: 14, marginBottom: 0 }}>
        {verdict}
      </div>
    </div>
  );
}
