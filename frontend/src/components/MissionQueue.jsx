import { useEffect, useState } from "react";
import { api } from "../api";
import { useBusiness } from "../BusinessContext";
import Icon from "../ui/Icon";
import { Card, EmptyState, Skeleton } from "../ui/kit";

const TYPE_META = {
  approval: ["check", "danger", "#/approvals"],
  ticket: ["info", "warn", "#/crm/tickets"],
  leave: ["userCheck", "info", "#/workforce/leave"],
  low_stock: ["box", "warn", "#/inventory"],
  overdue_receivable: ["wallet", "danger", "#/directory"],
};

// Priority-ordered "what needs attention now" — pulled live from the same
// tables every other panel reads, so it can never show a task that isn't real.
export default function MissionQueue({ limit = 8 }) {
  const { active } = useBusiness();
  const [data, setData] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!active?.id) return;
    api.missionQueue(active.id, limit).then(setData).catch(() => setFailed(true));
  }, [active?.id, limit]);

  if (failed) return null;
  if (!data) return <Card><Skeleton lines={3} height={18} /></Card>;

  return (
    <Card title="এখন করুন" subtitle="গুরুত্ব অনুযায়ী সাজানো — সব module থেকে একসাথে">
      {data.items.length === 0 ? (
        <EmptyState icon="check" title="এই মুহূর্তে কিছু অপেক্ষায় নেই" hint="ভালো! সব পরিষ্কার।" />
      ) : (
        <div className="mission-queue-list">
          {data.items.map((item, i) => {
            const [icon, , href] = TYPE_META[item.type] || ["info", "info", "#/app"];
            return (
              <a key={`${item.type}-${item.link_id}-${i}`} className="mission-queue-item" href={href}>
                <span className="mission-queue-item__icon"><Icon name={icon} size={16} /></span>
                <span className="mission-queue-item__body">
                  <strong>{item.title}</strong>
                  <small>{item.age_days != null ? `${item.age_days} দিন আগে থেকে` : "এখনই দেখুন"}</small>
                </span>
                <Icon name="chevronRight" size={16} />
              </a>
            );
          })}
        </div>
      )}
    </Card>
  );
}
