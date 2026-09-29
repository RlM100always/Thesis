import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useBusiness } from "../BusinessContext";
import { explain } from "../errors";
import { money, num } from "../format";
import { usePermissions } from "../PermissionContext";
import DataTable from "../ui/DataTable";
import { Badge, Card, EmptyState, Field, Notice, PageHeader, Segmented } from "../ui/kit";

const ABC_LABEL = { A: "A — প্রধান আয়ের উৎস", B: "B — মাঝারি", C: "C — কম অবদান", null: "বিক্রি নেই" };
const XYZ_LABEL = { X: "স্থির চাহিদা", Y: "উঠানামা করে", Z: "অনিয়মিত", null: "যথেষ্ট তথ্য নেই" };
const DAYS_OPTIONS = [{ value: 28, label: "৪ সপ্তাহ" }, { value: 90, label: "৩ মাস" }, { value: 180, label: "৬ মাস" }];

function AbcBadge({ cls }) {
  if (!cls) return <span className="muted">—</span>;
  return <span className={`abc-badge abc-badge--${cls}`} title={ABC_LABEL[cls]}>{cls}</span>;
}

// Which products actually earn their shelf space (ABC by revenue, XYZ by how steady
// demand is), which are quietly dead, and whose purchase price just moved.
export default function InsightsPage() {
  const { active } = useBusiness();
  const { can } = usePermissions();
  const orgId = active?.id;
  const seesAbc = can("sales:read");
  const [tab, setTab] = useState(seesAbc ? "abc" : "price");
  const [days, setDays] = useState(90);
  const [abc, setAbc] = useState(null);
  const [price, setPrice] = useState(null);
  const [filter, setFilter] = useState("all");
  const [error, setError] = useState("");

  const load = useCallback(() => {
    if (!orgId) return;
    setError("");
    if (seesAbc) api.abcXyz(orgId, days).then((r) => setAbc(r.items)).catch((e) => { setError(explain(e)); setAbc([]); });
    api.priceWatch(orgId).then((r) => setPrice(r.items)).catch(() => setPrice([]));
  }, [orgId, days, seesAbc]);
  useEffect(() => { load(); }, [load]);

  const shownAbc = useMemo(() => {
    if (!abc) return [];
    if (filter === "dead") return abc.filter((r) => r.dead_stock);
    if (filter === "noSale") return abc.filter((r) => r.abc === null);
    return abc;
  }, [abc, filter]);
  const deadCount = (abc || []).filter((r) => r.dead_stock).length;
  const noSaleCount = (abc || []).filter((r) => r.abc === null).length;

  return (
    <div className="page stack">
      <PageHeader title="ইনসাইটস" subtitle="কোন পণ্য আসলে ব্যবসা চালাচ্ছে, কোনটা শুধু জায়গা দখল করে আছে, আর কোথায় কেনা দাম বদলেছে।" />
      {error && <Notice tone="danger">{error}</Notice>}

      <div className="toolbar">
        <Segmented label="বিভাগ" value={tab} onChange={setTab} options={[
          ...(seesAbc ? [{ value: "abc", label: "পণ্যের গুরুত্ব (ABC-XYZ)" }] : []),
          { value: "price", label: "দামের পরিবর্তন", count: price?.length ?? 0 },
        ]} />
        {tab === "abc" && seesAbc && <Field label="সময়কাল"><Segmented label="সময়কাল" value={days} onChange={setDays} options={DAYS_OPTIONS} /></Field>}
      </div>

      {tab === "abc" && seesAbc && (
        <>
          <div className="toolbar">
            <Segmented label="ফিল্টার" value={filter} onChange={setFilter} options={[
              { value: "all", label: "সব", count: abc?.length ?? 0 },
              { value: "dead", label: "অবিক্রীত পুরোনো স্টক", count: deadCount },
              { value: "noSale", label: "এই সময়ে বিক্রি নেই", count: noSaleCount },
            ]} />
          </div>
          <Card pad={false}>
            <DataTable rowKey="product_id" loading={abc === null} rows={shownAbc} caption="পণ্যের ABC-XYZ তালিকা"
                       empty={<EmptyState icon="pie" title="কিছু নেই" hint="ফিল্টার বদলে দেখুন।" />}
                       columns={[
                         { key: "name", label: "পণ্য", primary: true, render: (r) => (
                           <div><strong>{r.name}</strong><div className="muted" style={{ fontSize: 12.5 }}>{r.sku}</div></div>) },
                         { key: "abc", label: "গুরুত্ব", render: (r) => <AbcBadge cls={r.abc} /> },
                         { key: "xyz", label: "চাহিদার ধরন", render: (r) => (r.xyz ? XYZ_LABEL[r.xyz] : <span className="muted">তথ্য অপর্যাপ্ত</span>) },
                         { key: "revenue", label: "আয়", align: "right", render: (r) => money(r.revenue) },
                         { key: "share", label: "আয়ের ভাগ", align: "right", render: (r) => `${num((r.revenue_share * 100).toFixed(1))}%` },
                         { key: "stock", label: "স্টকের মূল্য", align: "right", render: (r) => (
                           <span>{money(r.stock_value)}{r.dead_stock && <> <Badge tone="warn" icon="alert">অবিক্রীত</Badge></>}</span>) },
                       ]} />
          </Card>
        </>
      )}

      {tab === "price" && (
        <Card pad={false}>
          <DataTable rowKey="product_id" loading={price === null} rows={price || []} caption="দামের পরিবর্তনের তালিকা"
                     empty={<EmptyState icon="trend" title="দামের বড় কোনো পরিবর্তন নেই" hint="শেষ দুইটি ক্রয়ের মধ্যে ৫%-র বেশি দাম বদলালে এখানে দেখাবে।" />}
                     columns={[
                       { key: "name", label: "পণ্য", primary: true, render: (r) => (
                         <div><strong>{r.name}</strong><div className="muted" style={{ fontSize: 12.5 }}>{r.sku} · {r.supplier_name}</div></div>) },
                       { key: "previous", label: "আগের দাম", align: "right", render: (r) => money(r.previous_cost) },
                       { key: "latest", label: "সর্বশেষ দাম", align: "right", render: (r) => money(r.latest_cost) },
                       { key: "change", label: "পরিবর্তন", align: "right", render: (r) => (
                         <Badge tone={r.change > 0 ? "danger" : "success"}>{r.change > 0 ? "+" : ""}{num((r.change * 100).toFixed(1))}%</Badge>) },
                     ]} />
        </Card>
      )}
    </div>
  );
}
