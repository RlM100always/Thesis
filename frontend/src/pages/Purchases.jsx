import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api";
import { useBusiness } from "../BusinessContext";
import { explain } from "../errors";
import { dateBn, money, num, todayInputValue } from "../format";
import { usePermissions } from "../PermissionContext";
import DataTable from "../ui/DataTable";
import { Badge, Button, Card, EmptyState, Field, Modal, Notice, PageHeader, Segmented } from "../ui/kit";
import { useToast } from "../ui/Toast";
import useBranch from "../useBranch";

const STATUS = { ordered: ["অপেক্ষায়", "warn"], partial: ["আংশিক পেয়েছি", "info"], received: ["সব পেয়েছি", "success"] };
const poNumber = () => {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `PO-${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}-${Math.floor(Math.random() * 9000 + 1000)}`;
};
const blankLine = () => ({ key: Math.random().toString(36).slice(2), product_id: "", quantity: "1", unit_cost: "" });

export default function PurchasesPage() {
  const { active } = useBusiness();
  const { can } = usePermissions();
  const toast = useToast();
  const orgId = active?.id;
  const { branches, branch, setBranch } = useBranch(orgId);
  const canCreate = can("purchases:create");
  const canReceive = can("purchases:receive");

  const [orders, setOrders] = useState(null);
  const [products, setProducts] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("all");

  const [creating, setCreating] = useState(false);
  const [po, setPo] = useState({ supplier_id: "", order_number: "", expected_at: "" });
  const [lines, setLines] = useState([blankLine()]);
  const [poError, setPoError] = useState("");
  const [busy, setBusy] = useState(false);

  const [receiving, setReceiving] = useState(null);
  const [entries, setEntries] = useState({}); // line id -> [{qty, batch_no, expiry_date}]
  const [receiveError, setReceiveError] = useState("");
  const [params, setParams] = useSearchParams();

  const load = useCallback(async () => {
    if (!orgId) return;
    try {
      const [o, p, s] = await Promise.all([api.purchases(orgId), api.productsApp(orgId), api.suppliers(orgId).catch(() => [])]);
      setOrders(o);
      setProducts(p);
      setSuppliers(s);
      setError("");
    } catch (e) {
      setError(explain(e));
      setOrders([]);
    }
  }, [orgId]);
  useEffect(() => { load(); }, [load]);

  const productById = useMemo(() => Object.fromEntries(products.map((p) => [p.id, p])), [products]);
  const shown = useMemo(() => (orders || []).filter((o) => filter === "all" || o.status === filter), [orders, filter]);
  const counts = useMemo(() => ({
    all: orders?.length ?? 0,
    ordered: (orders || []).filter((o) => o.status === "ordered").length,
    partial: (orders || []).filter((o) => o.status === "partial").length,
    received: (orders || []).filter((o) => o.status === "received").length,
  }), [orders]);

  function startCreate() {
    setPo({ supplier_id: suppliers[0]?.id || "", order_number: poNumber(), expected_at: "" });
    setLines([blankLine()]);
    setPoError("");
    setCreating(true);
  }
  const setLine = (key, patch) => setLines((ls) => ls.map((l) => (l.key === key ? { ...l, ...patch } : l)));
  const lineTotal = lines.reduce((s, l) => s + Number(l.quantity || 0) * Number(l.unit_cost || 0), 0);

  async function createPo(e) {
    e.preventDefault();
    const valid = lines.filter((l) => l.product_id && Number(l.quantity) > 0);
    if (!valid.length) { setPoError("কমপক্ষে একটি পণ্য ও পরিমাণ দিন।"); return; }
    setBusy(true);
    setPoError("");
    try {
      const result = await api.createPurchase(orgId, {
        branch_id: branch, supplier_id: po.supplier_id, order_number: po.order_number,
        ordered_at: new Date().toISOString(),
        expected_at: po.expected_at ? new Date(po.expected_at).toISOString() : null,
        items: valid.map((l) => ({ product_id: l.product_id, quantity: String(l.quantity), unit_cost: String(l.unit_cost || 0) })),
      });
      toast.success(result?.status === "pending_approval"
        ? `৳${lineTotal.toFixed(0)}-এর অর্ডার — ${result.needs_role === "owner" ? "মালিকের" : "ম্যানেজারের"} অনুমোদনের অপেক্ষায় রাখা হয়েছে।`
        : `অর্ডার ${po.order_number} তৈরি হয়েছে।`);
      setCreating(false);
      load();
    } catch (err) {
      setPoError(explain(err, { 409: "এই অর্ডার নম্বর আগেই ব্যবহার হয়েছে। অন্য নম্বর দিন।", 404: "শাখা, সাপ্লায়ার বা পণ্য পাওয়া যায়নি।" }));
    } finally {
      setBusy(false);
    }
  }

  // "অর্ডার দিন" on a low-stock row lands here with the product already chosen.
  const wanted = params.get("product");
  useEffect(() => {
    if (!wanted || !canCreate || products.length === 0 || suppliers.length === 0) return;
    const product = products.find((p) => p.id === wanted);
    if (product) {
      setPo({ supplier_id: suppliers[0]?.id || "", order_number: poNumber(), expected_at: "" });
      setLines([{ ...blankLine(), product_id: product.id, unit_cost: Number(product.cost_price) > 0 ? product.cost_price : "" }]);
      setPoError("");
      setCreating(true);
    }
    setParams({}, { replace: true });
  }, [wanted, canCreate, products, suppliers, setParams]);

  function startReceive(order) {
    const initial = {};
    for (const item of order.items) {
      const remaining = Number(item.quantity) - Number(item.received_quantity);
      if (remaining > 0) initial[item.id] = [{ qty: String(remaining), batch_no: "", expiry_date: "" }];
    }
    setEntries(initial);
    setReceiveError("");
    setReceiving(order);
  }
  const setEntry = (lineId, index, patch) => setEntries((all) => ({
    ...all, [lineId]: all[lineId].map((en, i) => (i === index ? { ...en, ...patch } : en)),
  }));
  const addEntry = (lineId) => setEntries((all) => ({ ...all, [lineId]: [...all[lineId], { qty: "", batch_no: "", expiry_date: "" }] }));
  const removeEntry = (lineId, index) => setEntries((all) => ({ ...all, [lineId]: all[lineId].filter((_, i) => i !== index) }));

  async function receive(e) {
    e.preventDefault();
    const items = [];
    for (const line of receiving.items) {
      const list = entries[line.id] || [];
      const remaining = Number(line.quantity) - Number(line.received_quantity);
      const total = list.reduce((s, en) => s + Number(en.qty || 0), 0);
      if (total > remaining) { setReceiveError(`${line.product_name}: বাকি আছে ${num(remaining)}, কিন্তু ${num(total)} লেখা হয়েছে।`); return; }
      for (const en of list) {
        if (!(Number(en.qty) > 0)) continue;
        if (line.track_expiry && (!en.batch_no.trim() || !en.expiry_date)) {
          setReceiveError(`${line.product_name}: প্রতিটি ব্যাচের নম্বর ও মেয়াদ দিন।`);
          return;
        }
        items.push({
          purchase_order_item_id: line.id, quantity: String(en.qty),
          ...(line.track_expiry ? { batch_no: en.batch_no.trim(), expiry_date: en.expiry_date } : {}),
        });
      }
    }
    if (!items.length) { setReceiveError("কমপক্ষে একটি লাইনে পরিমাণ দিন।"); return; }
    setBusy(true);
    setReceiveError("");
    try {
      await api.receivePurchase(orgId, receiving.id, { received_at: new Date().toISOString(), items });
      toast.success("মাল রিসিভ হয়েছে। স্টক বেড়েছে।");
      setReceiving(null);
      load();
    } catch (err) {
      setReceiveError(explain(err, {
        409: "এই ব্যাচ আগেই অন্য মেয়াদে আছে, অথবা পরিমাণ অর্ডারের চেয়ে বেশি।",
        422: "ব্যাচ নম্বর ও মেয়াদ ঠিকভাবে দিন। মেয়াদ পেরিয়ে যাওয়া মাল রিসিভ করা যায় না — সাপ্লায়ারকে ফেরত দিন।",
      }));
    } finally {
      setBusy(false);
    }
  }

  const columns = [
    { key: "order_number", label: "অর্ডার", primary: true, render: (o) => <div><strong>{o.order_number}</strong><div className="muted" style={{ fontSize: 12.5 }}>{o.supplier_name}</div></div> },
    { key: "ordered_at", label: "তারিখ", render: (o) => dateBn(o.ordered_at) },
    { key: "items", label: "পণ্য", render: (o) => o.items.map((i) => `${i.product_name} × ${num(i.quantity)}`).join(", ") },
    { key: "total", label: "মোট", align: "right", render: (o) => money(o.total) },
    { key: "status", label: "অবস্থা", render: (o) => <Badge tone={STATUS[o.status]?.[1] || "neutral"}>{STATUS[o.status]?.[0] || o.status}</Badge> },
  ];
  if (canReceive) {
    columns.push({
      key: "actions", label: "কাজ", align: "right",
      render: (o) => o.status !== "received" && <Button size="sm" icon="truck" onClick={() => startReceive(o)}>মাল রিসিভ</Button>,
    });
  }

  return (
    <div className="page stack">
      <PageHeader
        title="ক্রয়"
        subtitle="সাপ্লায়ারকে অর্ডার দিন, মাল এলে রিসিভ করুন। ওষুধের ক্ষেত্রে ব্যাচ নম্বর ও মেয়াদ এখানেই লেখা হয়।"
        actions={<>
          {branches && branches.length > 1 && <Field label="শাখা"><select value={branch} onChange={(e) => setBranch(e.target.value)}>{branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}</select></Field>}
          {canCreate && <Button icon="plus" onClick={startCreate}>নতুন ক্রয় অর্ডার</Button>}
        </>}
      />
      {error && <Notice tone="danger" action={<Button size="sm" variant="secondary" onClick={load}>আবার চেষ্টা</Button>}>{error}</Notice>}
      {canCreate && suppliers.length === 0 && orders && (
        <Notice tone="info" title="আগে একজন সাপ্লায়ার যোগ করুন">অর্ডার দিতে সাপ্লায়ার লাগবে। <a href="#/directory">কাস্টমার ও সাপ্লায়ার পাতায়</a> গিয়ে যোগ করুন।</Notice>
      )}

      <Segmented label="অর্ডারের অবস্থা" value={filter} onChange={setFilter} options={[
        { value: "all", label: "সব", count: counts.all }, { value: "ordered", label: "অপেক্ষায়", count: counts.ordered },
        { value: "partial", label: "আংশিক", count: counts.partial }, { value: "received", label: "সব পেয়েছি", count: counts.received },
      ]} />

      <Card pad={false}>
        <DataTable columns={columns} rows={shown} loading={orders === null} caption="ক্রয় অর্ডারের তালিকা"
                   empty={<EmptyState icon="truck" title="কোনো অর্ডার নেই" hint="প্রথম ক্রয় অর্ডার তৈরি করুন।"
                                      action={canCreate && suppliers.length > 0 && <Button icon="plus" onClick={startCreate}>নতুন ক্রয় অর্ডার</Button>} />} />
      </Card>

      <Modal wide open={creating} title="নতুন ক্রয় অর্ডার" onClose={() => setCreating(false)}
             footer={<>
               <span className="muted" style={{ marginRight: "auto", alignSelf: "center" }}>মোট: <strong>{money(lineTotal)}</strong></span>
               <Button variant="secondary" onClick={() => setCreating(false)}>বাতিল</Button>
               <Button type="submit" form="po-form" loading={busy}>অর্ডার দিন</Button>
             </>}>
        <form id="po-form" className="ui-form" onSubmit={createPo}>
          <div className="ui-form ui-form--2">
            <Field label="সাপ্লায়ার" required>
              <select value={po.supplier_id} onChange={(e) => setPo({ ...po, supplier_id: e.target.value })}>
                <option value="">— বেছে নিন —</option>
                {suppliers.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </Field>
            <Field label="অর্ডার নম্বর" required><input value={po.order_number} onChange={(e) => setPo({ ...po, order_number: e.target.value })} /></Field>
            <Field label="কবে পাওয়ার কথা"><input type="date" min={todayInputValue()} value={po.expected_at} onChange={(e) => setPo({ ...po, expected_at: e.target.value })} /></Field>
          </div>
          <div>
            <strong>পণ্য</strong>
            {lines.map((l) => (
              <div key={l.key} className="batch-inputs" style={{ gridTemplateColumns: "2fr 1fr 1fr auto" }}>
                <Field label="পণ্য">
                  <select value={l.product_id} onChange={(e) => setLine(l.key, { product_id: e.target.value, unit_cost: Number(productById[e.target.value]?.cost_price) > 0 ? productById[e.target.value].cost_price : l.unit_cost })}>
                    <option value="">— বেছে নিন —</option>
                    {products.map((p) => <option key={p.id} value={p.id}>{p.name}{p.track_expiry ? " (মেয়াদ)" : ""}</option>)}
                  </select>
                </Field>
                <Field label="পরিমাণ"><input type="number" min="0.001" step="0.001" value={l.quantity} onChange={(e) => setLine(l.key, { quantity: e.target.value })} /></Field>
                <Field label="ক্রয়মূল্য (৳)"><input type="number" min="0" step="0.01" value={l.unit_cost} onChange={(e) => setLine(l.key, { unit_cost: e.target.value })} /></Field>
                <Button variant="ghost" size="sm" icon="trash" onClick={() => setLines((ls) => (ls.length > 1 ? ls.filter((x) => x.key !== l.key) : ls))} aria-label="লাইন বাদ দিন" />
              </div>
            ))}
            <div style={{ marginTop: 10 }}><Button variant="secondary" size="sm" icon="plus" onClick={() => setLines((ls) => [...ls, blankLine()])}>আরেকটি পণ্য</Button></div>
          </div>
          {poError && <Notice tone="danger">{poError}</Notice>}
        </form>
      </Modal>

      <Modal wide open={Boolean(receiving)} title={receiving ? `মাল রিসিভ — ${receiving.order_number}` : ""} onClose={() => setReceiving(null)}
             footer={<>
               <Button variant="secondary" onClick={() => setReceiving(null)}>বাতিল</Button>
               <Button type="submit" form="receive-form" loading={busy} icon="check">রিসিভ নিশ্চিত করুন</Button>
             </>}>
        {receiving && (
          <form id="receive-form" className="ui-form" onSubmit={receive}>
            <p className="muted" style={{ margin: 0 }}>সাপ্লায়ার: {receiving.supplier_name}। যা এসেছে তাই লিখুন — সবটা না এলে কম লিখুন, বাকিটা পরে রিসিভ করা যাবে।</p>
            {receiving.items.filter((i) => Number(i.quantity) - Number(i.received_quantity) > 0).map((line) => {
              const remaining = Number(line.quantity) - Number(line.received_quantity);
              return (
                <Card key={line.id} title={line.product_name} subtitle={`বাকি ${num(remaining)} · ক্রয়মূল্য ${money(line.unit_cost)}${line.track_expiry ? " · মেয়াদ ট্র্যাক হয়" : ""}`}>
                  {(entries[line.id] || []).map((en, index) => (
                    <div key={index} className="batch-inputs" style={line.track_expiry ? undefined : { gridTemplateColumns: "1fr auto" }}>
                      <Field label="কত এসেছে"><input type="number" min="0" step="0.001" value={en.qty} onChange={(e) => setEntry(line.id, index, { qty: e.target.value })} /></Field>
                      {line.track_expiry && <>
                        <Field label="ব্যাচ নম্বর" required><input value={en.batch_no} onChange={(e) => setEntry(line.id, index, { batch_no: e.target.value })} placeholder="প্যাকে লেখা" /></Field>
                        <Field label="মেয়াদ শেষ" required><input type="date" min={todayInputValue()} value={en.expiry_date} onChange={(e) => setEntry(line.id, index, { expiry_date: e.target.value })} /></Field>
                      </>}
                      {(entries[line.id] || []).length > 1 && <Button variant="ghost" size="sm" icon="trash" onClick={() => removeEntry(line.id, index)} aria-label="বাদ দিন" />}
                    </div>
                  ))}
                  {line.track_expiry && <div style={{ marginTop: 8 }}><Button variant="secondary" size="sm" icon="plus" onClick={() => addEntry(line.id)}>আরেকটি ব্যাচ (ভিন্ন মেয়াদ)</Button></div>}
                </Card>
              );
            })}
            {receiveError && <Notice tone="danger">{receiveError}</Notice>}
          </form>
        )}
      </Modal>
    </div>
  );
}
