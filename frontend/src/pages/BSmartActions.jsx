// B-SMART সুপারিশ — architecture layers 9 and 10, owner-facing.
//
// গবেষণা মোড-এর /bsmart পাতাটা প্রমাণ দেখায় (ইংরেজি, read-only)। এই পাতাটা
// আলাদা: এখানে ফার্মেসির মালিক আসলে সিদ্ধান্ত নেন — accept / reject / modify /
// defer — আর সেই সিদ্ধান্ত ও ফলাফল ডেটাবেজে জমা হয়। CLAUDE.md-র নিয়ম অনুযায়ী
// ব্যবসা মোড সম্পূর্ণ বাংলা।
//
// মূল নীতি: সিস্টেম সুপারিশ করে, চূড়ান্ত সিদ্ধান্ত মালিকের।

import { useCallback, useEffect, useState } from "react";

import { api } from "../api";
import { ConfidenceBadge } from "../components/ConfidenceBadge";
import { useConfirm } from "../components/ConfirmDialog";
import { FeedbackBanner, useFeedback } from "../components/FeedbackBanner";
import { useBusiness } from "../BusinessContext";

const TYPE_LABEL = {
  reorder: "নতুন অর্ডার",
  expiry: "মেয়াদ ঝুঁকি",
  retention: "গ্রাহক ফেরানো",
};

const DECISION_LABEL = {
  accept: "গ্রহণ করা হয়েছে",
  reject: "বাতিল করা হয়েছে",
  modify: "পরিবর্তন করা হয়েছে",
  defer: "পরে দেখা হবে",
};

function taka(value) {
  if (value === null || value === undefined) return "—";
  return `৳${Number(value).toLocaleString("bn-BD", { maximumFractionDigits: 0 })}`;
}

function ActionRow({ item, onDecide, busy }) {
  const [qty, setQty] = useState(item.quantity ?? 0);
  const title =
    item.action_type === "retention"
      ? `গ্রাহক ${item.customer_id}`
      : `${item.sku}${item.division ? ` · ${item.division}` : ""}`;

  return (
    <article className={`reco-row ${item.decision ? "decided" : ""}`}>
      <div className="reco-main">
        <div className="reco-head">
          <span className={`bsmart-type ${item.action_type}`}>
            {TYPE_LABEL[item.action_type] ?? item.action_type}
          </span>
          <h4>{title}</h4>
          <ConfidenceBadge confidence={item.confidence} />
        </div>

        <p className="reco-reason">{item.reason}</p>

        {item.explanation?.why && (
          <details className="reco-why">
            <summary>কেন এই পরিমাণ?</summary>
            <dl>
              {Object.entries(item.explanation.why).map(([key, value]) => (
                <div key={key}>
                  <dt>{key.replaceAll("_", " ")}</dt>
                  <dd>{String(value)}</dd>
                </div>
              ))}
            </dl>
            {item.explanation.constraints && (
              <ul className="reco-constraints">
                {Object.entries(item.explanation.constraints).map(([name, verdict]) => (
                  <li key={name}>
                    <span>{name.replaceAll("_", " ")}</span>
                    <span>{verdict}</span>
                  </li>
                ))}
              </ul>
            )}
          </details>
        )}

        <div className="reco-utility">
          লাভ {taka(item.benefit_bdt)} − খরচ {taka(item.action_cost_bdt)} − ঝুঁকি{" "}
          {taka(item.risk_bdt)} = <strong>মোট মূল্য {taka(item.utility_bdt)}</strong>
        </div>
      </div>

      <div className="reco-actions">
        {item.decision ? (
          <span className={`reco-decided ${item.decision}`}>
            {DECISION_LABEL[item.decision] ?? item.decision}
          </span>
        ) : (
          <>
            {item.action_type !== "retention" && (
              <label className="reco-qty">
                পরিমাণ
                <input
                  type="number"
                  min="0"
                  value={qty}
                  onChange={(e) => setQty(Number(e.target.value))}
                  disabled={busy}
                />
              </label>
            )}
            <button
              type="button"
              className="btn-primary"
              disabled={busy}
              onClick={() => onDecide(item, "accept")}
            >
              গ্রহণ করুন
            </button>
            <button
              type="button"
              className="btn-secondary"
              disabled={busy || qty === item.quantity}
              onClick={() => onDecide(item, "modify", qty)}
              title={qty === item.quantity ? "পরিমাণ বদলালে তবেই সক্রিয় হবে" : ""}
            >
              পরিমাণ বদলে নিন
            </button>
            <button
              type="button"
              className="btn-secondary"
              disabled={busy}
              onClick={() => onDecide(item, "defer")}
            >
              পরে দেখব
            </button>
            <button
              type="button"
              className="btn-danger"
              disabled={busy}
              onClick={() => onDecide(item, "reject")}
            >
              বাতিল
            </button>
          </>
        )}
      </div>
    </article>
  );
}

export default function BSmartActions() {
  const { active } = useBusiness();
  const organizationId = active?.id ?? null;
  const [feedback, showFeedback] = useFeedback();
  const confirm = useConfirm();

  const [items, setItems] = useState([]);
  const [monitoring, setMonitoring] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    if (!organizationId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const [recos, mon] = await Promise.all([
        api.bsmartRecommendations(organizationId),
        api.bsmartMonitoring(organizationId),
      ]);
      setItems(recos.recommendations ?? []);
      setMonitoring(mon);
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [organizationId]);

  useEffect(() => {
    load();
  }, [load]);

  async function importRun() {
    setBusy(true);
    try {
      const res = await api.bsmartImportRun(organizationId);
      showFeedback(
        "success",
        res.status === "already_imported"
          ? `এই তারিখের (${res.cutoff}) সুপারিশ আগেই আনা হয়েছে — ${res.recommendations}টি।`
          : `${res.recommendations}টি সুপারিশ আনা হয়েছে (কাট-অফ ${res.cutoff})।`,
      );
      await load();
    } catch (e) {
      showFeedback("error", `সুপারিশ আনা যায়নি: ${e.message}`);
    } finally {
      setBusy(false);
    }
  }

  // স্টক ও টাকার সিদ্ধান্ত — তাই গ্রহণ/বাতিলের আগে একবার নিশ্চিত করা হয়।
  async function decide(item, decision, modifiedQuantity) {
    const name = item.sku ?? item.customer_id;
    const prompts = {
      accept: `"${name}" — এই সুপারিশ গ্রহণ করবেন?`,
      reject: `"${name}" — এই সুপারিশ বাতিল করবেন?`,
      modify: `"${name}" — পরিমাণ ${modifiedQuantity} ধরে নেবেন?`,
      defer: `"${name}" — পরে দেখার জন্য রাখবেন?`,
    };
    if (!(await confirm(prompts[decision]))) return;

    setBusy(true);
    try {
      await api.bsmartDecision(organizationId, item.id, {
        decision,
        ...(decision === "modify" ? { modified_quantity: modifiedQuantity } : {}),
      });
      showFeedback("success", `সিদ্ধান্ত রাখা হয়েছে: ${DECISION_LABEL[decision]}।`);
      await load();
    } catch (e) {
      showFeedback("error", `সিদ্ধান্ত রাখা যায়নি: ${e.message}`);
    } finally {
      setBusy(false);
    }
  }

  if (!organizationId) {
    return (
      <div className="page">
        <header className="page-head">
          <h2 className="page-title">B-SMART সুপারিশ</h2>
        </header>
        <div className="callout">
          <strong>আগে ব্যবসা তৈরি করুন।</strong>
          <p>“ব্যবসা ও শাখা” পাতা থেকে ব্যবসা যোগ করলে এখানে সুপারিশ দেখা যাবে।</p>
        </div>
      </div>
    );
  }

  const pending = items.filter((i) => !i.decision);
  const decided = items.filter((i) => i.decision);

  return (
    <div className="page">
      {confirm.dialog}
      <header className="page-head">
        <h2 className="page-title">B-SMART সুপারিশ</h2>
        <p className="page-sub">
          সিস্টেম প্রতিটি কাজের লাভ, খরচ ও ঝুঁকি হিসাব করে সাজিয়ে দেয় — চূড়ান্ত
          সিদ্ধান্ত আপনার।
        </p>
      </header>

      <FeedbackBanner feedback={feedback} />

      <div className="toolbar-row">
        <button type="button" className="btn-primary" onClick={importRun} disabled={busy}>
          নতুন সুপারিশ আনুন
        </button>
        <span className="hint">
          সর্বশেষ চালানো B-SMART অ্যালগরিদমের ফলাফল আপনার ব্যবসায় যোগ হবে।
        </span>
      </div>

      {error && (
        <div className="callout danger">
          <strong>সমস্যা হয়েছে।</strong>
          <p className="hint">{error}</p>
        </div>
      )}

      {monitoring && (
        <section className="panel">
          <h3>ফলাফল পর্যবেক্ষণ</h3>
          <div className="stat-row">
            <div className="stat">
              <b>{monitoring.recommendations_total ?? 0}</b>
              <span>মোট সুপারিশ</span>
            </div>
            <div className="stat">
              <b>{monitoring.decisions_recorded ?? 0}</b>
              <span>সিদ্ধান্ত নেওয়া হয়েছে</span>
            </div>
            <div className="stat">
              <b>
                {monitoring.acceptance_rate === null || monitoring.acceptance_rate === undefined
                  ? "—"
                  : `${Math.round(monitoring.acceptance_rate * 100)}%`}
              </b>
              <span>গ্রহণের হার</span>
            </div>
            <div className="stat">
              <b>{monitoring.outcomes_logged ?? 0}</b>
              <span>ফলাফল লেখা হয়েছে</span>
            </div>
          </div>
          <p className="hint">
            যেখানে এখনো কিছু পর্যবেক্ষণ করা হয়নি সেখানে “—” দেখানো হয়, শূন্য নয় —
            না-মাপা ফলাফলকে মাপা শূন্য হিসেবে দেখানো হয় না।
          </p>
        </section>
      )}

      {loading ? (
        <p className="hint">লোড হচ্ছে…</p>
      ) : items.length === 0 ? (
        <div className="callout">
          <strong>এখনো কোনো সুপারিশ নেই।</strong>
          <p>উপরের “নতুন সুপারিশ আনুন” বোতামে চাপ দিন।</p>
        </div>
      ) : (
        <>
          <h3 className="section-title">সিদ্ধান্ত বাকি ({pending.length})</h3>
          {pending.map((item) => (
            <ActionRow key={item.id} item={item} onDecide={decide} busy={busy} />
          ))}

          {decided.length > 0 && (
            <>
              <h3 className="section-title">সিদ্ধান্ত হয়ে গেছে ({decided.length})</h3>
              {decided.map((item) => (
                <ActionRow key={item.id} item={item} onDecide={decide} busy={busy} />
              ))}
            </>
          )}
        </>
      )}
    </div>
  );
}
