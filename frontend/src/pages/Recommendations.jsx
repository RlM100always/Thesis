// B-SMART সুপারিশ — architecture layers 9 and 10, owner-facing.
// The system ranks and explains; the owner decides, and later records what
// actually happened. Nothing here changes stock or money by itself.

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useBusiness } from "../BusinessContext";
import { ConfidenceBadge } from "../components/ConfidenceBadge";
import { explain } from "../errors";
import { money, num } from "../format";
import { usePermissions } from "../PermissionContext";
import { Badge, Button, Card, EmptyState, Field, Modal, Notice, PageHeader, Segmented, Skeleton, Stat } from "../ui/kit";
import { useToast } from "../ui/Toast";

const TYPE_LABEL = { reorder: "নতুন অর্ডার", expiry: "মেয়াদ ঝুঁকি", retention: "কাস্টমার ফেরানো" };
const DECISION = {
  accept: ["গ্রহণ করা হয়েছে", "success"], reject: ["বাতিল করা হয়েছে", "danger"],
  modify: ["পরিমাণ বদলে গ্রহণ", "info"], defer: ["পরে দেখা হবে", "warn"],
};
const NOT_MEASURED = "মাপা হয়নি";
const pct = (v) => (v === null || v === undefined ? NOT_MEASURED : `${num(Math.round(v * 100))}%`);
const signed = (v, unit = "") => (v === null || v === undefined ? NOT_MEASURED : `${v > 0 ? "+" : ""}${num(v)}${unit}`);

export default function RecommendationsPage() {
  const { active } = useBusiness();
  const { can } = usePermissions();
  const toast = useToast();
  const orgId = active?.id;
  const canDecide = can("bsmart:decide");
  const canOutcome = can("bsmart:outcome");
  const canImport = can("bsmart:import");

  const [items, setItems] = useState(null);
  const [monitoring, setMonitoring] = useState(null);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("pending");
  const [busy, setBusy] = useState(false);
  const [explanations, setExplanations] = useState({}); // { [reco.id]: { loading, text, source, verified, error } }

  const [deciding, setDeciding] = useState(null); // { item, decision }
  const [qty, setQty] = useState("");
  const [note, setNote] = useState("");
  const [until, setUntil] = useState("");
  const [decisionError, setDecisionError] = useState("");

  const [outcomeFor, setOutcomeFor] = useState(null);
  const [outcome, setOutcome] = useState({});
  const [outcomeError, setOutcomeError] = useState("");

  const load = useCallback(async () => {
    if (!orgId) return;
    try {
      const [recos, mon] = await Promise.all([api.bsmartRecommendations(orgId), can("monitoring:read") ? api.bsmartMonitoring(orgId) : Promise.resolve(null)]);
      setItems(recos.recommendations ?? []);
      setMonitoring(mon);
      setError("");
    } catch (e) {
      setError(explain(e));
      setItems([]);
    }
  }, [orgId, can]);
  useEffect(() => { load(); }, [load]);

  const pending = useMemo(() => (items || []).filter((i) => !i.decision), [items]);
  const decided = useMemo(() => (items || []).filter((i) => i.decision), [items]);
  const shown = filter === "pending" ? pending : filter === "decided" ? decided : items || [];

  async function importRun() {
    setBusy(true);
    try {
      const res = await api.bsmartImportRun(orgId);
      toast.success(res.status === "already_imported"
        ? `এই তারিখের (${res.cutoff}) গবেষণা-ডেটার সুপারিশ আগেই আনা হয়েছে।`
        : `${num(res.recommendations)}টি সুপারিশ আনা হয়েছে (গবেষণা ডেটাসেট)।`);
      await load();
    } catch (e) {
      toast.error(explain(e, { 404: "এখনো কোনো B-SMART রান পাওয়া যায়নি। আগে গবেষণা ডেটায় অ্যালগরিদম চালাতে হবে।" }));
    } finally {
      setBusy(false);
    }
  }

  async function runLive() {
    setBusy(true);
    try {
      const res = await api.bsmartRunLive(orgId);
      toast.success(res.status === "already_imported"
        ? `আজকের (${res.cutoff}) লাইভ সুপারিশ আগেই তৈরি হয়েছে।`
        : `আপনার নিজের ব্যবসার ডেটা থেকে ${num(res.recommendations)}টি সুপারিশ তৈরি হয়েছে।`);
      await load();
    } catch (e) {
      toast.error(explain(e, { 422: "প্রথমে অন্তত একটি শাখা যোগ করুন।" }));
    } finally {
      setBusy(false);
    }
  }

  async function fetchExplanation(item) {
    setExplanations((cur) => ({ ...cur, [item.id]: { loading: true } }));
    try {
      const res = await api.bsmartExplain(orgId, item.id);
      setExplanations((cur) => ({ ...cur, [item.id]: { loading: false, ...res } }));
    } catch (e) {
      setExplanations((cur) => ({ ...cur, [item.id]: { loading: false, error: explain(e) } }));
    }
  }

  function startDecision(item, decision) {
    setDeciding({ item, decision });
    setQty(String(item.quantity ?? 0));
    setNote("");
    setUntil("");
    setDecisionError("");
  }

  async function submitDecision(e) {
    e.preventDefault();
    const { item, decision } = deciding;
    setBusy(true);
    setDecisionError("");
    try {
      await api.bsmartDecision(orgId, item.id, {
        decision, note: note || null,
        ...(decision === "modify" ? { modified_quantity: Number(qty) } : {}),
        ...(decision === "defer" && until ? { defer_until: until } : {}),
      });
      toast.success(`সিদ্ধান্ত রাখা হয়েছে: ${DECISION[decision][0]}।`);
      setDeciding(null);
      await load();
    } catch (err) {
      setDecisionError(explain(err, { 403: "সিদ্ধান্ত নেওয়ার অনুমতি শুধু মালিক ও ম্যানেজারের।", 422: "পরিমাণ ঠিকভাবে দিন।" }));
    } finally {
      setBusy(false);
    }
  }

  async function measureOutcome(item) {
    setBusy(true);
    try {
      const res = await api.bsmartMeasure(orgId, item.id);
      toast.success("লেজার থেকে ফলাফল স্বয়ংক্রিয়ভাবে মাপা হয়েছে।");
      await load();
    } catch (e) {
      toast.error(explain(e, { 422: "এই সুপারিশের জন্য স্বয়ংক্রিয় মাপা সম্ভব নয়।" }));
    } finally {
      setBusy(false);
    }
  }

  function startOutcome(item) {
    setOutcomeFor(item);
    setOutcome({ observation_window_days: "30" });
    setOutcomeError("");
  }
  const setO = (key) => (e) => setOutcome({ ...outcome, [key]: e.target.value });

  async function submitOutcome(e) {
    e.preventDefault();
    const num_ = (v) => (v === undefined || v === "" ? null : Number(v));
    const flag = (v) => (v === undefined || v === "" ? null : v === "yes");
    setBusy(true);
    setOutcomeError("");
    try {
      await api.bsmartOutcome(orgId, outcomeFor.id, {
        action_taken: flag(outcome.action_taken), observation_window_days: Number(outcome.observation_window_days || 30),
        stockout_days_before: num_(outcome.stockout_days_before), stockout_days_after: num_(outcome.stockout_days_after),
        holding_cost_before_bdt: num_(outcome.holding_cost_before_bdt), holding_cost_after_bdt: num_(outcome.holding_cost_after_bdt),
        expired_value_bdt: num_(outcome.expired_value_bdt), customer_responded: flag(outcome.customer_responded),
        predicted_quantity: num_(outcome.predicted_quantity), realised_quantity: num_(outcome.realised_quantity),
        realised_benefit_bdt: num_(outcome.realised_benefit_bdt), note: outcome.note || null,
      });
      toast.success("ফলাফল লেখা হয়েছে। যা লেখেননি তা ‘মাপা হয়নি’ হিসেবেই থাকবে।");
      setOutcomeFor(null);
      await load();
    } catch (err) {
      setOutcomeError(explain(err, { 422: "সংখ্যাগুলো ০ বা তার বেশি হতে হবে।" }));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page stack">
      <PageHeader
        title="B-SMART সুপারিশ"
        subtitle="সিস্টেম প্রতিটি কাজের লাভ, খরচ ও ঝুঁকি হিসাব করে সাজিয়ে দেয়। চূড়ান্ত সিদ্ধান্ত সবসময় আপনার।"
        actions={canImport && <>
          <Button icon="zap" loading={busy && !deciding && !outcomeFor} onClick={runLive}>নিজের ব্যবসার ডেটা থেকে রান করুন</Button>
          <Button icon="refresh" variant="secondary" loading={busy && !deciding && !outcomeFor} onClick={importRun}>গবেষণা ডেটাসেটের নমুনা আনুন</Button>
        </>}
      />
      {error && <Notice tone="danger" action={<Button size="sm" variant="secondary" onClick={load}>আবার চেষ্টা</Button>}>{error}</Notice>}

      {monitoring && (
        <Card title="ফলাফল পর্যবেক্ষণ" subtitle="যা এখনো মাপা হয়নি তা ‘মাপা হয়নি’ লেখা থাকে — শূন্য নয়। না-মাপা জিনিসকে মাপা শূন্য ভাবা ভুল হবে।">
          <div className="ui-stats">
            <Stat label="মোট সুপারিশ" value={num(monitoring.recommendations_total)} />
            <Stat label="সিদ্ধান্ত হয়েছে" value={num(monitoring.decisions_recorded)} sub={Object.entries(monitoring.decision_breakdown || {}).map(([k, v]) => `${DECISION[k]?.[0] || k}: ${num(v)}`).join(" · ") || undefined} />
            <Stat label="গ্রহণের হার" value={pct(monitoring.acceptance_rate)} />
            <Stat label="ফলাফল লেখা হয়েছে" value={num(monitoring.outcomes_logged)} />
            <Stat label="স্টকআউট দিন বদল" value={signed(monitoring.mean_stockout_days_change, " দিন")} sub="ঋণাত্মক মানে কমেছে" />
            <Stat label="স্টক রাখার খরচ বদল" value={monitoring.mean_holding_cost_change_bdt === null ? NOT_MEASURED : `${monitoring.mean_holding_cost_change_bdt > 0 ? "+" : ""}${money(monitoring.mean_holding_cost_change_bdt)}`} />
            <Stat label="পূর্বাভাসের গড় ভুল" value={monitoring.mean_forecast_abs_error_units === null ? NOT_MEASURED : `${num(monitoring.mean_forecast_abs_error_units)} ইউনিট`} />
            <Stat label="কাস্টমার সাড়া" value={pct(monitoring.customer_response_rate)} />
            <Stat label="মডেল সরে যাওয়ার সংকেত" tone={monitoring.drift_flags ? "warn" : "neutral"} value={num(monitoring.drift_flags)} />
          </div>
        </Card>
      )}

      <Segmented label="সুপারিশ ফিল্টার" value={filter} onChange={setFilter} options={[
        { value: "pending", label: "সিদ্ধান্ত বাকি", count: pending.length },
        { value: "decided", label: "সিদ্ধান্ত হয়েছে", count: decided.length },
        { value: "all", label: "সব", count: items?.length ?? 0 },
      ]} />

      {items === null ? <Skeleton lines={4} height={22} /> : shown.length === 0 ? (
        <Card><EmptyState icon="target" title={items.length ? "এই তালিকায় কিছু নেই" : "এখনো কোনো সুপারিশ নেই"}
                          hint={items.length ? "অন্য ফিল্টার দেখুন।" : "‘নতুন সুপারিশ আনুন’ চাপলে সর্বশেষ B-SMART ফলাফল আপনার ব্যবসায় যোগ হবে।"} /></Card>
      ) : (
        <div className="reco-list">
          {shown.map((item) => {
            const title = item.action_type === "retention" ? `কাস্টমার ${item.customer_id}` : `${item.sku}${item.division ? ` · ${item.division}` : ""}`;
            const d = item.decision && DECISION[item.decision];
            return (
              <Card key={item.id}>
                <div className="reco">
                  <div className="reco__main">
                    <div className="row" style={{ gap: 8 }}>
                      <Badge tone="info">{TYPE_LABEL[item.action_type] ?? item.action_type}</Badge>
                      <ConfidenceBadge confidence={item.confidence} />
                      <Badge tone={item.source === "live" ? "success" : "neutral"}>
                        {item.source === "live" ? "নিজের ডেটা" : "গবেষণা নমুনা"}
                      </Badge>
                      {d && <Badge tone={d[1]}>{d[0]}</Badge>}
                    </div>
                    <h4>{title}{item.quantity ? ` — ${num(item.quantity)} ইউনিট` : ""}</h4>
                    <p>{item.reason}</p>
                    <p className="reco__math">লাভ {money(item.benefit_bdt)} − খরচ {money(item.action_cost_bdt)} − ঝুঁকি {money(item.risk_bdt)} = <strong>মোট মূল্য {money(item.utility_bdt)}</strong></p>
                    {item.explanation?.why && (
                      <details className="reco-why">
                        <summary>কেন এই সুপারিশ? (হিসাবের উপাদান)</summary>
                        <dl>{Object.entries(item.explanation.why).map(([k, v]) => <div key={k}><dt>{k.replaceAll("_", " ")}</dt><dd>{String(v)}</dd></div>)}</dl>
                        {item.explanation.constraints && (
                          <ul className="reco-constraints">
                            {Object.entries(item.explanation.constraints).map(([k, v]) => <li key={k}><span>{k.replaceAll("_", " ")}</span><span>{String(v)}</span></li>)}
                          </ul>
                        )}
                      </details>
                    )}
                    {explanations[item.id]?.text ? (
                      <div className="reco-ai-explain">
                        <Badge tone={explanations[item.id].source === "llm" ? "success" : "neutral"}>
                          {explanations[item.id].source === "llm" ? "AI ব্যাখ্যা (যাচাই করা)" : "সংক্ষিপ্ত ব্যাখ্যা"}
                        </Badge>
                        <p>{explanations[item.id].text}</p>
                      </div>
                    ) : explanations[item.id]?.error ? (
                      <Notice tone="danger">{explanations[item.id].error}</Notice>
                    ) : (
                      <Button size="sm" variant="ghost" icon="zap" loading={explanations[item.id]?.loading}
                              onClick={() => fetchExplanation(item)}>
                        সহজ ভাষায় ব্যাখ্যা শুনুন
                      </Button>
                    )}
                  </div>
                  <div className="reco__buttons">
                    {!item.decision && canDecide && <>
                      <Button icon="check" onClick={() => startDecision(item, "accept")}>গ্রহণ করুন</Button>
                      {item.action_type !== "retention" && <Button variant="secondary" onClick={() => startDecision(item, "modify")}>পরিমাণ বদলে নিন</Button>}
                      <Button variant="secondary" onClick={() => startDecision(item, "defer")}>পরে দেখব</Button>
                      <Button variant="danger" onClick={() => startDecision(item, "reject")}>বাতিল</Button>
                    </>}
                    {item.decision && (item.outcome_logged
                      ? <Badge tone="success" icon="check">
                          {item.outcome_measured_by === "ledger_auto" ? "ফলাফল লেজার থেকে মাপা হয়েছে" : "ফলাফল লেখা হয়েছে"}
                        </Badge>
                      : canOutcome && <>
                          {item.source === "live" && (
                            <Button variant="secondary" icon="zap" loading={busy} onClick={() => measureOutcome(item)}>
                              স্বয়ংক্রিয়ভাবে মাপুন
                            </Button>
                          )}
                          <Button variant="secondary" icon="edit" onClick={() => startOutcome(item)}>নিজে লিখুন</Button>
                        </>)}
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      <Modal open={Boolean(deciding)} title={deciding ? `${DECISION[deciding.decision][0].replace(" হয়েছে", "")} — সিদ্ধান্ত` : ""} onClose={() => setDeciding(null)}
             footer={<><Button variant="secondary" onClick={() => setDeciding(null)}>ফিরে যান</Button><Button type="submit" form="decision-form" loading={busy} variant={deciding?.decision === "reject" ? "danger" : "primary"}>সিদ্ধান্ত নিশ্চিত করুন</Button></>}>
        {deciding && (
          <form id="decision-form" className="ui-form" onSubmit={submitDecision}>
            <Notice tone="info">{deciding.item.sku || `কাস্টমার ${deciding.item.customer_id}`} — {deciding.item.reason}</Notice>
            {deciding.decision === "modify" && <Field label="আপনি কত ইউনিট চান?" required hint={`সিস্টেম বলেছিল ${num(deciding.item.quantity)}। আপনার আর সিস্টেমের ফারাক নিজেই একটি শেখার তথ্য।`}><input type="number" min="0" value={qty} onChange={(e) => setQty(e.target.value)} autoFocus /></Field>}
            {deciding.decision === "defer" && <Field label="কবে আবার দেখবেন? (ঐচ্ছিক)"><input type="date" value={until} onChange={(e) => setUntil(e.target.value)} /></Field>}
            <Field label={deciding.decision === "reject" ? "কেন বাতিল করছেন? (ঐচ্ছিক, কিন্তু মূল্যবান)" : "নোট (ঐচ্ছিক)"}><input value={note} onChange={(e) => setNote(e.target.value)} maxLength={300} /></Field>
            <p className="muted" style={{ margin: 0, fontSize: 13 }}>এই সিদ্ধান্ত লিখে রাখা হয়, মুছে ফেলা যায় না। মত বদলালে নতুন করে আরেকটি সিদ্ধান্ত যোগ হয়।</p>
            {decisionError && <Notice tone="danger">{decisionError}</Notice>}
          </form>
        )}
      </Modal>

      <Modal wide open={Boolean(outcomeFor)} title="ফলাফল লিখুন" onClose={() => setOutcomeFor(null)}
             footer={<><Button variant="secondary" onClick={() => setOutcomeFor(null)}>বাতিল</Button><Button type="submit" form="outcome-form" loading={busy}>ফলাফল রাখুন</Button></>}>
        {outcomeFor && (
          <form id="outcome-form" className="ui-form" onSubmit={submitOutcome}>
            <Notice tone="info">যা জানেন শুধু তাই লিখুন। খালি রাখা ঘর ‘মাপা হয়নি’ থাকবে — আন্দাজে ভরবেন না।</Notice>
            <div className="ui-form ui-form--2">
              <Field label="কাজটি কি সত্যিই করেছেন?"><select value={outcome.action_taken || ""} onChange={setO("action_taken")}><option value="">— জানি না —</option><option value="yes">হ্যাঁ</option><option value="no">না</option></select></Field>
              <Field label="কত দিন পর্যবেক্ষণ করেছেন?"><input type="number" min="1" max="365" value={outcome.observation_window_days || ""} onChange={setO("observation_window_days")} /></Field>
              {outcomeFor.action_type !== "retention" && <>
                <Field label="স্টক ছিল না — আগে কত দিন?"><input type="number" min="0" value={outcome.stockout_days_before || ""} onChange={setO("stockout_days_before")} /></Field>
                <Field label="স্টক ছিল না — পরে কত দিন?"><input type="number" min="0" value={outcome.stockout_days_after || ""} onChange={setO("stockout_days_after")} /></Field>
                <Field label="স্টকে আটকে থাকা টাকা — আগে (৳)"><input type="number" min="0" value={outcome.holding_cost_before_bdt || ""} onChange={setO("holding_cost_before_bdt")} /></Field>
                <Field label="স্টকে আটকে থাকা টাকা — পরে (৳)"><input type="number" min="0" value={outcome.holding_cost_after_bdt || ""} onChange={setO("holding_cost_after_bdt")} /></Field>
                <Field label="মেয়াদ পেরিয়ে নষ্ট হওয়া মাল (৳)"><input type="number" min="0" value={outcome.expired_value_bdt || ""} onChange={setO("expired_value_bdt")} /></Field>
                <Field label="সিস্টেম কত বিক্রির কথা বলেছিল?"><input type="number" min="0" value={outcome.predicted_quantity || ""} onChange={setO("predicted_quantity")} /></Field>
                <Field label="আসলে কত বিক্রি হলো?"><input type="number" min="0" value={outcome.realised_quantity || ""} onChange={setO("realised_quantity")} /></Field>
              </>}
              {outcomeFor.action_type === "retention" && (
                <Field label="কাস্টমার কি সাড়া দিয়েছেন?"><select value={outcome.customer_responded || ""} onChange={setO("customer_responded")}><option value="">— জানি না —</option><option value="yes">হ্যাঁ</option><option value="no">না</option></select></Field>
              )}
              <Field label="আসল লাভ/ক্ষতি (৳)"><input type="number" value={outcome.realised_benefit_bdt || ""} onChange={setO("realised_benefit_bdt")} /></Field>
            </div>
            <Field label="নোট"><input value={outcome.note || ""} onChange={setO("note")} maxLength={300} /></Field>
            {outcomeError && <Notice tone="danger">{outcomeError}</Notice>}
          </form>
        )}
      </Modal>
    </div>
  );
}
