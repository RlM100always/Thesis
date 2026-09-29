import { useEffect, useState } from "react";
import { api } from "../api";
import { money, num } from "../format";
import DataTable from "../ui/DataTable";
import { Badge, Card } from "../ui/kit";

const BUCKETS = [["d0_30", "০–৩০ দিন"], ["d31_60", "৩১–৬০ দিন"], ["d61_90", "৬১–৯০ দিন"], ["d90_plus", "৯০+ দিন"]];

// Who owes, and for how long. Payments clear the oldest baki first; nothing is predicted.
export default function AgeingCard({ orgId, refreshKey }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    api.receivablesAgeing(orgId).then(setData).catch(() => setData({ customers: [] }));
  }, [orgId, refreshKey]);
  if (!data || data.customers.length === 0) return null;
  return (
    <Card title="বাকির বয়স" subtitle="সবচেয়ে পুরোনো বাকি আগে আদায় করুন। পেমেন্ট সবসময় সবচেয়ে পুরোনো বাকি থেকে কাটা হয়।" pad={false}>
      <div className="ui-stats" style={{ padding: 16 }}>
        {BUCKETS.map(([key, label]) => (
          <div key={key} className={`ui-stat ${key === "d90_plus" && Number(data.buckets[key]) > 0 ? "ui-stat--danger" : ""}`}>
            <span className="ui-stat__label">{label}</span><strong className="ui-stat__value">{money(data.buckets[key])}</strong>
          </div>
        ))}
      </div>
      <DataTable rowKey="customer_id" rows={data.customers} caption="বাকির বয়সের তালিকা"
                 columns={[
                   { key: "name", label: "কাস্টমার", primary: true, render: (r) => <strong>{r.name || r.code}</strong> },
                   { key: "balance", label: "মোট বাকি", align: "right", render: (r) => (
                     <span>{money(r.balance)}{r.over_limit && <> <Badge tone="danger" icon="alert">সীমা ছাড়িয়েছে</Badge></>}</span>) },
                   { key: "oldest", label: "সবচেয়ে পুরোনো", align: "right", render: (r) => (r.oldest_days == null ? "—" : `${num(r.oldest_days)} দিন`) },
                   ...BUCKETS.map(([key, label]) => ({ key, label, align: "right", render: (r) => (Number(r[key]) > 0 ? money(r[key]) : "—") })),
                 ]} />
    </Card>
  );
}
