import { useEffect, useState } from "react";
import { api } from "../api";
import { useBusiness } from "../BusinessContext";
import Icon from "../ui/Icon";
import { Card, Skeleton } from "../ui/kit";

const LABELS = {
  cash: ["wallet", "ক্যাশ"], stock: ["box", "স্টক"], sales: ["trend", "বিক্রি"],
  customer: ["users", "কাস্টমার"], control: ["shield", "নিয়ন্ত্রণ"],
};

function tone(score) {
  if (score == null) return "neutral";
  if (score >= 75) return "success";
  if (score >= 50) return "warn";
  return "danger";
}

// Five explainable scores, not one vanity number — each tells you its own
// formula and window so "why is this low" is never a mystery.
export default function HealthScore() {
  const { active } = useBusiness();
  const [data, setData] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!active?.id) return;
    api.healthScore(active.id).then(setData).catch(() => setFailed(true));
  }, [active?.id]);

  if (failed) return null;
  if (!data) return <Card><Skeleton lines={2} height={18} /></Card>;

  return (
    <Card title="ব্যবসার স্বাস্থ্য" subtitle={data.overall == null ? "যথেষ্ট তথ্য জমা হয়নি" : `সামগ্রিক স্কোর ${data.overall} / ১০০`}>
      <div className="health-score-grid">
        {Object.entries(data.scores).map(([key, s]) => {
          const [icon, label] = LABELS[key] || ["info", key];
          return (
            <div key={key} className={`health-score-item tone-${tone(s.score)}`} title={s.formula}>
              <Icon name={icon} size={18} />
              <span className="health-score-label">{label}</span>
              <strong className="health-score-value">{s.score == null ? "—" : s.score}</strong>
              <small>{s.insufficient_data ? "তথ্য অপর্যাপ্ত" : `গত ${s.window_days || 0} দিন`}</small>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
