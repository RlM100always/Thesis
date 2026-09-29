import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useBusiness } from "../BusinessContext";
import { useConfirm } from "../components/ConfirmDialog";
import { explain } from "../errors";
import { money, num } from "../format";
import { usePermissions } from "../PermissionContext";
import DataTable from "../ui/DataTable";
import { Badge, Button, Card, EmptyState, Field, Notice, PageHeader, Segmented, Stat } from "../ui/kit";
import { useToast } from "../ui/Toast";
import useBranch from "../useBranch";

const COVER = [{ value: 7, label: "৭ দিন" }, { value: 14, label: "১৪ দিন" }, { value: 30, label: "৩০ দিন" }];

// "কী কিনবেন": every suggestion shows the arithmetic behind it, so the owner can
// overrule a number instead of taking it on trust. Ordering creates one purchase
// order per supplier; nothing is bought until the owner presses the button.
export default function ReorderPlanPage() {
  const { active } = useBusiness();
  const { can } = usePermissions();
  const toast = useToast();
  const confirm = useConfirm();
  const orgId = active?.id;
  const { branches, branch, setBranch } = useBranch(orgId);
  const canOrder = can("purchases:create");

  const [cover, setCover] = useState(14);
  const [plan, setPlan] = useState(null);
  const [suppliers, setSuppliers] = useState([]);
  const [rows, setRows] = useState({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(null);

  const load = useCallback(async () => {
    if (!orgId || !branch) return;
    setPlan(null); setError("");
    try {
      const [p, s] = await Promise.all([api.reorderPlan(orgId, branch, cover), api.suppliers(orgId).catch(() => [])]);
      setPlan(p); setSuppliers(s);
      setRows(Object.fromEntries(p.items.map((i) => [i.product_id, {
        on: true, qty: String(Number(i.suggested_qty)), cost: i.unit_cost == null ? "" : String(Number(i.unit_cost)), supplier: i.supplier_id || "",
      }])));
    } catch (e) {
      setError(explain(e, { 403: "কী কিনবেন তা দেখার অনুমতি আপনার ভূমিকায় নেই।" }));
      setPlan({ items: [] });
    }
  }, [orgId, branch, cover]);
  useEffect(() => { load(); }, [load]);

  const set = (id, patch) => setRows((r) => ({ ...r, [id]: { ...r[id], ...patch } }));
  const picked = useMemo(() => (plan?.items || []).filter((i) => rows[i.product_id]?.on), [plan, rows]);
  const total = picked.reduce((sum, i) => sum + Number(rows[i.product_id].qty || 0) * Number(rows[i.product_id].cost || 0), 0);
  const problems = picked.filter((i) => {
    const r = rows[i.product_id];
    return !(Number(r.qty) > 0) || r.cost === "" || Number(r.cost) < 0 || !r.supplier;
  });
  const urgent = (plan?.items || []).filter((i) => i.urgent).length;

  async function order() {
    const bySupplier = {};
    for (const i of picked) {
      const r = rows[i.product_id];
      (bySupplier[r.supplier] ||= []).push({ product_id: i.product_id, quantity: String(Number(r.qty)), unit_cost: String(Number(r.cost)) });
    }
    const orders = Object.entries(bySupplier).map(([supplier_id, items]) => ({ supplier_id, items }));
    if (!(await confirm(`${num(orders.length)}টি সাপ্লায়ারকে মোট ${money(total)} টাকার ক্রয়ের অর্ডার তৈরি হবে। এগিয়ে যাবেন?`))) return;
    setBusy(true); setError("");
    try {
      const r = await api.createPlanOrders(orgId, { branch_id: branch, orders });
      setDone(r.created);
      toast.success(`${num(r.created.length)}টি ক্রয়ের অর্ডার তৈরি হয়েছে।`);
      load();
    } catch (e) {
      setError(explain(e, { 403: "ক্রয়ের অর্ডার তৈরির অনুমতি আপনার ভূমিকায় নেই।", 404: "কোনো পণ্য বা সাপ্লায়ার পাওয়া যায়নি। পাতাটি নতুন করে খুলুন।" }));
    } finally { setBusy(false); }
  }

  return (
    <div className="page stack">
      <PageHeader title="কী কিনবেন" subtitle="গত ২৮ দিনের বিক্রি, বর্তমান মজুত ও পথে থাকা মাল দেখে হিসাব করা। প্রতিটি সংখ্যার হিসাব নিচে দেখানো আছে — আপনি বদলাতে পারেন।" />
      {confirm.dialog}

      <Card>
        <div className="row" style={{ justifyContent: "space-between" }}>
          <Field label="শাখা">
            <select value={branch} onChange={(e) => setBranch(e.target.value)}>{(branches || []).map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}</select>
          </Field>
          <div>
            <span className="muted" style={{ display: "block", fontSize: 13, marginBottom: 6 }}>কত দিনের মাল হাতে রাখতে চান</span>
            <Segmented label="মজুতের দিন" value={cover} onChange={setCover} options={COVER} />
          </div>
        </div>
      </Card>

      {error && <Notice tone="danger">{error}</Notice>}

      {plan && plan.items.length > 0 && (
        <div className="ui-stats">
          <Stat label="কেনার তালিকায়" value={`${num(plan.items.length)}টি পণ্য`} icon="box" />
          <Stat label="জরুরি (সাপ্লায়ারের মাল আসার আগেই ফুরাবে)" value={num(urgent)} tone={urgent ? "danger" : "neutral"} icon="alert" />
          <Stat label="নির্বাচিত অর্ডারের আনুমানিক মূল্য" value={money(total)} icon="wallet" />
        </div>
      )}

      {done && (
        <Notice tone="success" title="অর্ডার তৈরি হয়েছে">
          {done.map((d) => <div key={d.id}>{d.supplier} — {d.order_number} · {money(d.total)} · {num(d.lines)}টি পণ্য</div>)}
          <div style={{ marginTop: 6 }}><a href="#/purchases">ক্রয়ের পাতায় যান →</a></div>
        </Notice>
      )}

      <Card pad={false}>
        <DataTable rowKey="product_id" loading={plan === null} rows={plan?.items || []} caption="কেনার সুপারিশ"
                   empty={<EmptyState icon="check" title="এখন কিছু কেনার দরকার নেই" hint="আপনার মজুত ও বিক্রির হিসাবে সব পণ্যের যথেষ্ট মাল আছে।" />}
                   columns={[
                     { key: "on", label: "নিন", render: (i) => <input type="checkbox" checked={rows[i.product_id]?.on || false} disabled={!canOrder} onChange={(e) => set(i.product_id, { on: e.target.checked })} aria-label={`${i.name} অর্ডারে নিন`} /> },
                     { key: "name", label: "পণ্য", primary: true, render: (i) => (
                       <div>
                         <strong>{i.name}</strong> {i.urgent && <Badge tone="danger" icon="alert">জরুরি</Badge>}
                         <div className="muted" style={{ fontSize: 12.5 }}>{i.sku}</div>
                       </div>) },
                     { key: "stock", label: "মজুত", render: (i) => (
                       <div>{num(i.sellable)}{Number(i.unsellable) > 0 && <div className="muted" style={{ fontSize: 12 }}>+ {num(i.unsellable)} বিক্রির অযোগ্য</div>}
                         {Number(i.incoming) > 0 && <div className="muted" style={{ fontSize: 12 }}>পথে {num(i.incoming)}</div>}</div>) },
                     { key: "cover", label: "কতদিন চলবে", render: (i) => (i.days_of_cover == null ? "—" : `${num(i.days_of_cover)} দিন`) },
                     { key: "why", label: "হিসাব", render: (i) => (
                       <span className="muted" style={{ fontSize: 12.5 }}>
                         {i.reason === "sales"
                           ? `দৈনিক ${num(i.daily_rate)} × (${num(i.lead_days)} + ${num(i.cover_days)}) দিন = ${num(i.target)}, মজুত ও পথের মাল বাদ`
                           : "গত ২৮ দিনে বিক্রি নেই; ন্যূনতম স্টকের নিচে নেমে গেছে"}
                       </span>) },
                     { key: "qty", label: "পরিমাণ", render: (i) => (
                       <input type="number" min="1" style={{ width: 84 }} disabled={!canOrder} value={rows[i.product_id]?.qty ?? ""} onChange={(e) => set(i.product_id, { qty: e.target.value })} aria-label={`${i.name} কত কিনবেন`} />) },
                     { key: "cost", label: "দাম (প্রতি)", render: (i) => (
                       <input type="number" min="0" step="0.01" style={{ width: 92 }} disabled={!canOrder} value={rows[i.product_id]?.cost ?? ""} onChange={(e) => set(i.product_id, { cost: e.target.value })} aria-label={`${i.name} কেনা দাম`} />) },
                     { key: "supplier", label: "সাপ্লায়ার", render: (i) => (
                       <select disabled={!canOrder} value={rows[i.product_id]?.supplier || ""} onChange={(e) => set(i.product_id, { supplier: e.target.value })} aria-label={`${i.name} সাপ্লায়ার`}>
                         <option value="">— বেছে নিন —</option>
                         {suppliers.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                       </select>) },
                   ]} />
      </Card>

      {plan && plan.items.length > 0 && (
        !canOrder ? <Notice tone="info">অর্ডার তৈরির অনুমতি শুধু মালিক, ম্যানেজার ও হিসাবরক্ষকের। আপনি তালিকাটি দেখতে পারেন।</Notice> : (
          <div className="stack">
            {suppliers.length === 0 && <Notice tone="warn">আগে একজন সাপ্লায়ার যোগ করুন — <a href="#/directory">কাস্টমার ও সাপ্লায়ার</a> পাতায়।</Notice>}
            {picked.length > 0 && problems.length > 0 && <Notice tone="warn">{num(problems.length)}টি নির্বাচিত পণ্যে পরিমাণ, দাম বা সাপ্লায়ার বাকি আছে।</Notice>}
            <div className="row">
              <Button icon="truck" disabled={picked.length === 0 || problems.length > 0} loading={busy} onClick={order}>
                {num(picked.length)}টি পণ্যের অর্ডার দিন
              </Button>
              <span className="muted">সাপ্লায়ার অনুযায়ী আলাদা আলাদা অর্ডার তৈরি হবে।</span>
            </div>
          </div>
        )
      )}
    </div>
  );
}
