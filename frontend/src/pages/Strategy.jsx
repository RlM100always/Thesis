import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useBusiness } from "../BusinessContext";
import { ConfidenceBadge } from "../components/ConfidenceBadge";
import { explain } from "../errors";
import { money, num } from "../format";
import { Badge, Button, Card, EmptyState, Notice, PageHeader, Segmented, Skeleton } from "../ui/kit";

const MODEL_STATUS = {
  model: ["success", "আপনার নিজের বিক্রির তথ্য থেকে শেখা মডেল ব্যবহৃত হচ্ছে"],
  mixed: ["info", "কিছু পণ্যে শেখা মডেল, বাকিগুলোতে সাধারণ হিসাব"],
  baseline: ["warn", "এখনো মডেল শেখেনি — সাধারণ হিসাব ব্যবহৃত হচ্ছে"],
};
const TYPE_LABEL = { reorder: "মাল কিনতে হবে", retention: "কাস্টমারের সাথে যোগাযোগ", anomaly: "অস্বাভাবিকতা", expiry: "মেয়াদ" };

export default function StrategyPage() {
  const { active } = useBusiness();
  const orgId = active?.id;
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [type, setType] = useState("all");

  const load = useCallback(async () => {
    if (!orgId) return;
    setData(null);
    try {
      setData(await api.recommendationsApp(orgId));
      setError("");
    } catch (e) {
      setError(explain(e));
      setData({ actions: [], model_status: "baseline" });
    }
  }, [orgId]);
  useEffect(() => { load(); }, [load]);

  const actions = useMemo(() => data?.actions || [], [data]);
  const types = useMemo(() => [...new Set(actions.map((a) => a.type))], [actions]);
  const shown = actions.filter((a) => type === "all" || a.type === type);
  const [tone, statusText] = MODEL_STATUS[data?.model_status] || ["info", data?.model_status];

  return (
    <div className="page stack">
      <PageHeader title="আজকের করণীয়" subtitle="আপনার বিক্রি, স্টক ও কাস্টমারের তথ্য দেখে কোন কাজগুলো আগে করা উচিত — লাভের হিসাবসহ।" />
      {error && <Notice tone="danger" action={<Button size="sm" variant="secondary" onClick={load}>আবার চেষ্টা</Button>}>{error}</Notice>}

      {!data ? <Skeleton lines={4} height={22} /> : (
        <>
          <Notice tone={tone} title={statusText}>{data.model_note_bn}</Notice>
          {data.anomaly && <Notice tone="danger" title={data.anomaly.message_bn}>{data.anomaly.date} · অস্বাভাবিকতার মাত্রা {data.anomaly.z_score}</Notice>}

          {types.length > 1 && (
            <Segmented label="করণীয়ের ধরন" value={type} onChange={setType} options={[
              { value: "all", label: "সব", count: actions.length },
              ...types.map((t) => ({ value: t, label: TYPE_LABEL[t] || t, count: actions.filter((a) => a.type === t).length })),
            ]} />
          )}

          {shown.length === 0 ? (
            <Card><EmptyState icon="zap" title="এখন কোনো জরুরি করণীয় নেই"
                              hint="আরও বিক্রি ও স্টকের তথ্য জমলে এখানে সুপারিশ আসবে। সাধারণত কয়েক সপ্তাহের বিক্রি লাগে।"
                              action={<a className="ui-btn ui-btn--secondary" href="#/sales">বিক্রি করুন</a>} /></Card>
          ) : (
            <div className="reco-list">
              {shown.map((a, i) => (
                <Card key={`${a.type}-${a.entity_id}-${i}`}>
                  <div className="reco">
                    <div className="reco__main">
                      <div className="row" style={{ gap: 8 }}>
                        <Badge tone={a.priority === "high" ? "danger" : "warn"} icon="alert">{a.priority === "high" ? "জরুরি" : "মাঝারি"}</Badge>
                        <Badge>{TYPE_LABEL[a.type] || a.type}</Badge>
                        <ConfidenceBadge confidence={a.confidence} />
                      </div>
                      <h4>{a.title_bn}</h4>
                      <p>{a.explanation_bn}</p>
                    </div>
                    <div className="reco__side">
                      {a.recommended_quantity ? <div><span>পরিমাণ</span><strong>{num(a.recommended_quantity)} ইউনিট</strong></div> : null}
                      <div><span>সম্ভাব্য লাভ</span><strong>{money(a.utility_bdt)}</strong></div>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          )}

          {data.contact_without_consent_excluded > 0 && (
            <Notice tone="info">সম্মতি না থাকায় {num(data.contact_without_consent_excluded)} জন কাস্টমারকে এই তালিকা থেকে বাদ দেওয়া হয়েছে। কাস্টমারের অনুমতি ছাড়া বার্তা পাঠানো হয় না।</Notice>
          )}
        </>
      )}
    </div>
  );
}
