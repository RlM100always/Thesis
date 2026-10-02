import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useBusiness } from "../BusinessContext";
import { explain } from "../errors";
import { dateTimeBn, money, num } from "../format";
import { usePermissions } from "../PermissionContext";
import DataTable from "../ui/DataTable";
import { Badge, Button, Card, EmptyState, Field, Modal, Notice, PageHeader, Segmented, Stat } from "../ui/kit";
import { useToast } from "../ui/Toast";
import useBranch from "../useBranch";

const STATUS = {
  submitted: ["দাবি পাঠানো", "warn"], dispatched: ["মাল ফেরত গেছে", "info"],
  settled: ["ক্রেডিট নোট হয়েছে", "success"], rejected: ["বাতিল", "danger"],
};
const TYPES = [
  ["damaged", "নষ্ট/ভাঙা"], ["expired", "মেয়াদ সমস্যা"], ["wrong_item", "ভুল পণ্য"],
  ["quality", "মানগত সমস্যা"], ["short_shipment", "কম ডেলিভারি"], ["other", "অন্যান্য"],
];
const claimNo = () => `PR-${Date.now().toString(36).toUpperCase()}`;

export default function PurchaseReturnsPage() {
  const { active } = useBusiness();
  const { can } = usePermissions();
  const toast = useToast();
  const orgId = active?.id;
  const { branch } = useBranch(orgId);
  const [claims, setClaims] = useState(null);
  const [purchases, setPurchases] = useState([]);
  const [batches, setBatches] = useState([]);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("all");
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ purchase_order_id: "", return_number: "", claim_type: "damaged", reason: "" });
  const [quantities, setQuantities] = useState({});
  const [crediting, setCrediting] = useState(null);
  const [credit, setCredit] = useState({ credit_note_number: "", supplier_note: "" });
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState("");

  const load = useCallback(async () => {
    if (!orgId || !branch) return;
    try {
      const [returns, orders, shelf] = await Promise.all([
        api.purchaseReturns(orgId), api.purchases(orgId), api.batches(orgId, branch).catch(() => []),
      ]);
      setClaims(returns); setPurchases(orders); setBatches(shelf); setError("");
    } catch (err) {
      setClaims([]); setError(explain(err));
    }
  }, [orgId, branch]);
  useEffect(() => { load(); }, [load]);

  const eligible = useMemo(() => purchases.filter((order) => order.branch_id === branch
    && order.items.some((line) => Number(line.received_quantity) > 0)), [purchases, branch]);
  const order = useMemo(() => eligible.find((row) => row.id === form.purchase_order_id), [eligible, form.purchase_order_id]);
  const claimed = useMemo(() => {
    const used = {};
    for (const claim of claims || []) if (claim.status !== "rejected") {
      for (const item of claim.items) used[item.purchase_order_item_id] = (used[item.purchase_order_item_id] || 0) + Number(item.quantity);
    }
    return used;
  }, [claims]);
  const allocations = useMemo(() => {
    if (!order) return [];
    return order.items.flatMap((line) => {
      if (!line.track_expiry) return [{ key: `${line.id}:none`, line, batch: null }];
      return batches.filter((batch) => batch.product_id === line.product_id)
        .map((batch) => ({ key: `${line.id}:${batch.batch_id}`, line, batch }));
    });
  }, [order, batches]);
  const shown = useMemo(() => (claims || []).filter((claim) => filter === "all" || claim.status === filter), [claims, filter]);
  const count = (status) => status === "all" ? (claims || []).length : (claims || []).filter((c) => c.status === status).length;
  const pendingValue = (claims || []).filter((c) => c.status === "submitted" || c.status === "dispatched")
    .reduce((sum, c) => sum + Number(c.total), 0);

  function startCreate() {
    setForm({ purchase_order_id: eligible[0]?.id || "", return_number: claimNo(), claim_type: "damaged", reason: "" });
    setQuantities({}); setFormError(""); setCreating(true);
  }

  async function createClaim(event) {
    event.preventDefault();
    const items = allocations.filter((row) => Number(quantities[row.key]) > 0).map((row) => ({
      purchase_order_item_id: row.line.id, quantity: String(quantities[row.key]),
      ...(row.batch ? { batch_id: row.batch.batch_id } : {}),
    }));
    if (!items.length) { setFormError("কমপক্ষে একটি পণ্যের ফেরত পরিমাণ লিখুন।"); return; }
    setBusy(true); setFormError("");
    try {
      await api.createPurchaseReturn(orgId, { ...form, submitted_at: new Date().toISOString(), items });
      toast.success("Supplier claim তৈরি হয়েছে। Dispatch না করা পর্যন্ত stock বদলাবে না।");
      setCreating(false); load();
    } catch (err) {
      setFormError(explain(err, {
        409: "আগের claim-সহ পরিমাণ রিসিভ করা মালের চেয়ে বেশি, অথবা claim নম্বরটি আগে ব্যবহৃত।",
        422: "Batch-ভিত্তিক পণ্যের সঠিক batch ও পরিমাণ দিন।",
      }));
    } finally { setBusy(false); }
  }

  async function dispatch(claim) {
    setBusy(true);
    try {
      await api.dispatchPurchaseReturn(orgId, claim.id, { dispatched_at: new Date().toISOString() });
      toast.success("মাল supplier-এর কাছে dispatch হয়েছে; stock ও Supplier Claims account আপডেট হয়েছে।"); load();
    } catch (err) { toast.error(explain(err, { 409: "বর্তমান stock/batch-এ ফেরত দেওয়ার মতো পরিমাণ নেই, অথবা claim আগেই dispatch হয়েছে।" })); }
    finally { setBusy(false); }
  }

  function startCredit(claim) {
    setCrediting(claim); setCredit({ credit_note_number: "", supplier_note: "" }); setFormError("");
  }
  async function settle(event) {
    event.preventDefault(); setBusy(true); setFormError("");
    try {
      await api.creditPurchaseReturn(orgId, crediting.id, { ...credit, accepted_at: new Date().toISOString() });
      toast.success("Credit note গ্রহণ হয়েছে এবং supplier payable কমেছে।"); setCrediting(null); load();
    } catch (err) { setFormError(explain(err, { 409: "Credit note নম্বরটি আগে ব্যবহৃত, অথবা claim এখন settlement-এর অবস্থায় নেই।" })); }
    finally { setBusy(false); }
  }

  const columns = [
    { key: "return_number", label: "ক্লেইম", primary: true, render: (c) => <div><strong>{c.return_number}</strong><div className="muted" style={{ fontSize: 12 }}>{c.purchase_order_number}</div></div> },
    { key: "supplier_name", label: "সাপ্লায়ার" },
    { key: "items", label: "পণ্য", render: (c) => c.items.map((i) => `${i.product_name}${i.batch_no ? ` · ${i.batch_no}` : ""} × ${num(i.quantity)}`).join(", ") },
    { key: "submitted_at", label: "তারিখ", render: (c) => dateTimeBn(c.submitted_at) },
    { key: "total", label: "দাবি", align: "right", render: (c) => money(c.total) },
    { key: "status", label: "অবস্থা", render: (c) => <Badge tone={STATUS[c.status]?.[1]}>{STATUS[c.status]?.[0] || c.status}</Badge> },
    { key: "action", label: "কাজ", align: "right", render: (c) => <>
      {c.status === "submitted" && can("purchase_returns:dispatch") && <Button size="sm" icon="truck" loading={busy} onClick={() => dispatch(c)}>পাঠানো হয়েছে লিখুন</Button>}
      {c.status === "dispatched" && can("purchase_returns:settle") && <Button size="sm" icon="check" onClick={() => startCredit(c)}>ক্রেডিট নোট নিন</Button>}
      {c.status === "settled" && <span className="muted">{c.credit_note_number}</span>}
    </> },
  ];

  return (
    <div className="page stack">
      <PageHeader title="সাপ্লায়ার ক্লেইম ও ক্রয় ফেরত"
        subtitle="রিসিভ করা নষ্ট, ভুল বা মেয়াদ-সমস্যার মাল ফেরত পাঠান; credit note এলে supplier-এর দেনা স্বয়ংক্রিয়ভাবে কমবে।"
        actions={can("purchase_returns:create") && <Button icon="plus" onClick={startCreate} disabled={!eligible.length}>নতুন ক্লেইম</Button>} />
      {error && <Notice tone="danger" action={<Button size="sm" variant="secondary" onClick={load}>আবার চেষ্টা</Button>}>{error}</Notice>}
      <div className="stats-grid">
        <Stat icon="clock" label="অপেক্ষায়" value={count("submitted")} sub="এখনও dispatch হয়নি" tone="warn" />
        <Stat icon="truck" label="Supplier-এর কাছে" value={count("dispatched")} sub="Credit note বাকি" tone="info" />
        <Stat icon="card" label="খোলা দাবির মূল্য" value={money(pendingValue)} sub="Claim asset" />
        <Stat icon="check" label="মিটেছে" value={count("settled")} sub="Payable সমন্বয় হয়েছে" tone="success" />
      </div>
      {!eligible.length && claims && <Notice tone="info" title="ক্লেইমের আগে মাল রিসিভ করুন">ক্রয় অর্ডারে রিসিভ করা পণ্য থাকলেই supplier claim করা যাবে।</Notice>}
      <Segmented label="ক্লেইমের অবস্থা" value={filter} onChange={setFilter} options={[
        { value: "all", label: "সব", count: count("all") }, { value: "submitted", label: "দাবি পাঠানো", count: count("submitted") },
        { value: "dispatched", label: "Dispatch", count: count("dispatched") }, { value: "settled", label: "মিটেছে", count: count("settled") },
      ]} />
      <Card pad={false}><DataTable rows={shown} columns={columns} loading={claims === null} caption="সাপ্লায়ার ক্লেইমের তালিকা"
        empty={<EmptyState icon="undo" title="কোনো supplier claim নেই" hint="নষ্ট বা ভুল মাল ফেরত দিতে নতুন claim তৈরি করুন।" />} /></Card>

      <Modal wide open={creating} title="নতুন supplier claim" onClose={() => setCreating(false)}
        footer={<><Button variant="secondary" onClick={() => setCreating(false)}>বাতিল</Button><Button form="purchase-return-form" type="submit" loading={busy}>ক্লেইম পাঠান</Button></>}>
        <form id="purchase-return-form" className="ui-form" onSubmit={createClaim}>
          <div className="ui-form ui-form--2">
            <Field label="কোন ক্রয় থেকে?" required><select value={form.purchase_order_id} onChange={(e) => { setForm({ ...form, purchase_order_id: e.target.value }); setQuantities({}); }}>
              {eligible.map((p) => <option key={p.id} value={p.id}>{p.order_number} · {p.supplier_name}</option>)}
            </select></Field>
            <Field label="ক্লেইম নম্বর" required><input value={form.return_number} onChange={(e) => setForm({ ...form, return_number: e.target.value })} /></Field>
            <Field label="সমস্যার ধরন" required><select value={form.claim_type} onChange={(e) => setForm({ ...form, claim_type: e.target.value })}>{TYPES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></Field>
            <Field label="বিস্তারিত কারণ" required><input minLength="2" value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} placeholder="যেমন: ২টি carton ভেজা ও seal ভাঙা" /></Field>
          </div>
          <div className="stack">
            {allocations.map(({ key, line, batch }) => {
              const available = batch ? Number(batch.quantity) : Math.max(0, Number(line.received_quantity) - (claimed[line.id] || 0));
              return <Card key={key} title={line.product_name} subtitle={`${line.sku}${batch ? ` · Batch ${batch.batch_no} · stock ${num(batch.quantity)}` : ` · রিসিভ ${num(line.received_quantity)}`} · ${money(line.unit_cost)}`}>
                <Field label="ফেরত পরিমাণ"><input type="number" min="0" max={available} step="0.001" value={quantities[key] || ""} onChange={(e) => setQuantities({ ...quantities, [key]: e.target.value })} /></Field>
              </Card>;
            })}
          </div>
          <Notice tone="info">ক্লেইম তৈরি করলে স্টক কমবে না। মাল সত্যিই পাঠানোর পরে <strong>পাঠানো হয়েছে লিখুন</strong> চাপলে স্টক কমবে।</Notice>
          {formError && <Notice tone="danger">{formError}</Notice>}
        </form>
      </Modal>

      <Modal open={Boolean(crediting)} title="Supplier credit note গ্রহণ" onClose={() => setCrediting(null)}
        footer={<><Button variant="secondary" onClick={() => setCrediting(null)}>বাতিল</Button><Button type="submit" form="credit-note-form" loading={busy}>গ্রহণ ও দেনা সমন্বয়</Button></>}>
        {crediting && <form id="credit-note-form" className="ui-form" onSubmit={settle}>
          <Notice tone="success" title={`${crediting.return_number} · ${money(crediting.total)}`}>Credit note গ্রহণ করলে supplier payable এই পরিমাণ কমবে এবং claim account বন্ধ হবে।</Notice>
          <Field label="Credit note নম্বর" required><input autoFocus value={credit.credit_note_number} onChange={(e) => setCredit({ ...credit, credit_note_number: e.target.value })} /></Field>
          <Field label="Supplier-এর নোট"><textarea rows="3" value={credit.supplier_note} onChange={(e) => setCredit({ ...credit, supplier_note: e.target.value })} /></Field>
          {formError && <Notice tone="danger">{formError}</Notice>}
        </form>}
      </Modal>
    </div>
  );
}
