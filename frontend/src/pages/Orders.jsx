import { useCallback, useMemo, useState, useEffect } from "react";
import { api } from "../api";
import { useBusiness } from "../BusinessContext";
import { usePermissions } from "../PermissionContext";
import useBranch from "../useBranch";
import { dateBn, money, num, todayInputValue } from "../format";
import { explain } from "../errors";
import DataTable from "../ui/DataTable";
import { Badge, Button, Card, EmptyState, Field, Modal, Notice, PageHeader, Segmented } from "../ui/kit";
import { useToast } from "../ui/Toast";

const LABEL = {
  draft: ["খসড়া", "neutral"], sent: ["পাঠানো", "info"], accepted: ["গৃহীত", "success"], rejected: ["বাতিল", "danger"], converted: ["অর্ডার হয়েছে", "success"],
  confirmed: ["নিশ্চিত", "info"], ready: ["প্রস্তুত", "warn"], dispatched: ["পাঠানো হয়েছে", "info"], delivered: ["ডেলিভারি", "success"], invoiced: ["ইনভয়েস হয়েছে", "success"], cancelled: ["বাতিল", "danger"],
};
const NEXT = { confirmed: "ready", ready: "dispatched", dispatched: "delivered" };
const NEXT_LABEL = { ready: "প্রস্তুত করুন", dispatched: "পাঠিয়ে দিন", delivered: "ডেলিভারি হয়েছে" };
const number = (prefix) => `${prefix}-${new Date().toISOString().slice(0, 10).replaceAll("-", "")}-${Date.now().toString(36).toUpperCase()}`;
const line = () => ({ key: Math.random().toString(36).slice(2), product_id: "", quantity: "1", unit_price: "", discount_amount: "0" });

export default function OrdersPage() {
  const { active } = useBusiness(); const orgId = active?.id;
  const { branch } = useBranch(orgId); const { can } = usePermissions(); const toast = useToast();
  const [type, setType] = useState("quotation"); const [rows, setRows] = useState(null);
  const [products, setProducts] = useState([]); const [customers, setCustomers] = useState([]);
  const [creating, setCreating] = useState(false); const [form, setForm] = useState({ customer_id: "", valid_until: "", expected_delivery_at: "", notes: "" });
  const [lines, setLines] = useState([line()]); const [busy, setBusy] = useState(false); const [error, setError] = useState(""); const [invoicing, setInvoicing] = useState(null);
  const canCreate = can("orders:create"); const canFulfill = can("orders:fulfill");
  const load = useCallback(async () => {
    if (!orgId) return;
    try { const [documents, p, c] = await Promise.all([api.salesDocuments(orgId), api.productsApp(orgId), api.customersApp(orgId)]); setRows(documents); setProducts(p); setCustomers(c); setError(""); }
    catch (e) { setRows([]); setError(explain(e)); }
  }, [orgId]);
  useEffect(() => { load(); }, [load]);
  const shown = useMemo(() => (rows || []).filter((r) => r.document_type === type), [rows, type]);
  const productMap = useMemo(() => Object.fromEntries(products.map((p) => [p.id, p])), [products]);
  const total = lines.reduce((sum, item) => sum + Number(item.quantity || 0) * Number(item.unit_price || productMap[item.product_id]?.selling_price || 0) - Number(item.discount_amount || 0), 0);
  const patchLine = (key, patch) => setLines((all) => all.map((item) => item.key === key ? { ...item, ...patch } : item));
  function openCreate() { setForm({ customer_id: "", valid_until: "", expected_delivery_at: "", notes: "" }); setLines([line()]); setError(""); setCreating(true); }
  async function create(e) {
    e.preventDefault(); const valid = lines.filter((item) => item.product_id && Number(item.quantity) > 0);
    if (!valid.length) { setError("কমপক্ষে একটি পণ্য দিন।"); return; }
    setBusy(true); setError("");
    try {
      await api.createSalesDocument(orgId, { document_type: type, document_number: number(type === "quotation" ? "QT" : "SO"), branch_id: branch, customer_id: form.customer_id || null, issued_at: new Date().toISOString(), valid_until: form.valid_until || null, expected_delivery_at: form.expected_delivery_at ? new Date(form.expected_delivery_at).toISOString() : null, notes: form.notes || null, items: valid.map(({ product_id, quantity, unit_price, discount_amount }) => ({ product_id, quantity, unit_price: unit_price || null, discount_amount: discount_amount || "0" })) });
      toast.success(type === "quotation" ? "কোটেশন তৈরি হয়েছে।" : "অর্ডার তৈরি হয়েছে।"); setCreating(false); load();
    } catch (err) { setError(explain(err)); } finally { setBusy(false); }
  }
  async function status(row, next) { setBusy(true); try { await api.salesDocumentStatus(orgId, row.id, next); toast.success("অবস্থা বদলেছে।"); load(); } catch (e) { toast.error(explain(e)); } finally { setBusy(false); } }
  async function convert(row) { setBusy(true); try { await api.convertQuote(orgId, row.id, { order_number: number("SO") }); toast.success("কোটেশন থেকে অর্ডার তৈরি হয়েছে।"); setType("order"); load(); } catch (e) { toast.error(explain(e)); } finally { setBusy(false); } }
  async function invoice(e) {
    e.preventDefault(); setBusy(true);
    try { await api.invoiceSalesOrder(orgId, invoicing.id, { invoice_number: number("INV"), sold_at: new Date().toISOString(), payments: invoicing.paid > 0 ? [{ method: invoicing.method, amount: String(invoicing.paid) }] : [] }); toast.success("ইনভয়েস তৈরি হয়েছে; স্টক ও হিসাব আপডেট হয়েছে।"); setInvoicing(null); load(); }
    catch (err) { setError(explain(err, { 409: "স্টক যথেষ্ট নেই অথবা অর্ডারটি আর ইনভয়েস করা যাবে না।" })); } finally { setBusy(false); }
  }
  const columns = [
    { key: "document_number", label: type === "quotation" ? "কোটেশন" : "অর্ডার", primary: true, render: (r) => <div><strong>{r.document_number}</strong><div className="muted">{r.customer_name || "সাধারণ ক্রেতা"}</div></div> },
    { key: "issued_at", label: "তারিখ", render: (r) => dateBn(r.issued_at) },
    { key: "items", label: "পণ্য", render: (r) => r.items.map((i) => `${i.product_name} × ${num(i.quantity)}`).join(", ") },
    { key: "total", label: "মোট", align: "right", render: (r) => money(r.total) },
    { key: "status", label: "অবস্থা", render: (r) => <Badge tone={LABEL[r.status]?.[1]}>{LABEL[r.status]?.[0] || r.status}</Badge> },
    { key: "action", label: "কাজ", align: "right", render: (r) => <div className="row-actions">
      {type === "quotation" && canCreate && !["converted", "rejected"].includes(r.status) && <Button size="sm" onClick={() => convert(r)}>অর্ডার করুন</Button>}
      {type === "order" && canFulfill && NEXT[r.status] && <Button size="sm" variant="secondary" onClick={() => status(r, NEXT[r.status])}>{NEXT_LABEL[NEXT[r.status]]}</Button>}
      {type === "order" && canFulfill && !["cancelled", "invoiced"].includes(r.status) && <Button size="sm" onClick={() => { setError(""); setInvoicing({ ...r, method: "cash", paid: Number(r.total) }); }}>ইনভয়েস</Button>}
    </div> },
  ];
  return <div className="page stack">
    <PageHeader title="কোটেশন ও অর্ডার" subtitle="কোটেশন থেকে অর্ডার, ডেলিভারি এবং একবারে হিসাব-স্টকসহ ইনভয়েস।" actions={canCreate && <Button icon="plus" onClick={openCreate}>{type === "quotation" ? "নতুন কোটেশন" : "নতুন অর্ডার"}</Button>} />
    {error && !creating && !invoicing && <Notice tone="danger">{error}</Notice>}
    <Segmented label="নথির ধরন" value={type} onChange={setType} options={[{ value: "quotation", label: "কোটেশন", count: (rows || []).filter((r) => r.document_type === "quotation").length }, { value: "order", label: "অর্ডার ও ডেলিভারি", count: (rows || []).filter((r) => r.document_type === "order").length }]} />
    <Card pad={false}><DataTable rows={shown} columns={columns} loading={rows === null} caption="কোটেশন ও অর্ডারের তালিকা" empty={<EmptyState icon="fileText" title="এখনো কিছু নেই" hint="প্রথম কোটেশন বা অর্ডার তৈরি করুন।" />} /></Card>
    <Modal wide open={creating} title={type === "quotation" ? "নতুন কোটেশন" : "নতুন অর্ডার"} onClose={() => setCreating(false)} footer={<><span className="muted" style={{ marginRight: "auto" }}>মোট <strong>{money(total)}</strong></span><Button variant="secondary" onClick={() => setCreating(false)}>বাতিল</Button><Button type="submit" form="sales-doc-form" loading={busy}>সংরক্ষণ</Button></>}>
      <form id="sales-doc-form" className="ui-form" onSubmit={create}><div className="ui-form ui-form--2"><Field label="কাস্টমার"><select value={form.customer_id} onChange={(e) => setForm({ ...form, customer_id: e.target.value })}><option value="">সাধারণ ক্রেতা</option>{customers.map((c) => <option key={c.id} value={c.id}>{c.display_name || c.code}</option>)}</select></Field>{type === "quotation" ? <Field label="কতদিন বৈধ"><input type="date" min={todayInputValue()} value={form.valid_until} onChange={(e) => setForm({ ...form, valid_until: e.target.value })} /></Field> : <Field label="ডেলিভারির তারিখ"><input type="datetime-local" value={form.expected_delivery_at} onChange={(e) => setForm({ ...form, expected_delivery_at: e.target.value })} /></Field>}</div>
        {lines.map((item) => <div className="batch-inputs" key={item.key} style={{ gridTemplateColumns: "2fr 1fr 1fr 1fr auto" }}><Field label="পণ্য"><select value={item.product_id} onChange={(e) => patchLine(item.key, { product_id: e.target.value, unit_price: productMap[e.target.value]?.selling_price || "" })}><option value="">— পণ্য —</option>{products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></Field><Field label="পরিমাণ"><input type="number" min="0.001" step="0.001" value={item.quantity} onChange={(e) => patchLine(item.key, { quantity: e.target.value })} /></Field><Field label="দাম"><input type="number" min="0" step="0.01" value={item.unit_price} onChange={(e) => patchLine(item.key, { unit_price: e.target.value })} /></Field><Field label="ছাড়"><input type="number" min="0" step="0.01" value={item.discount_amount} onChange={(e) => patchLine(item.key, { discount_amount: e.target.value })} /></Field><Button variant="ghost" icon="trash" onClick={() => setLines((all) => all.length > 1 ? all.filter((x) => x.key !== item.key) : all)} /></div>)}
        <Button variant="secondary" size="sm" icon="plus" onClick={() => setLines((all) => [...all, line()])}>আরেকটি পণ্য</Button><Field label="নোট"><textarea rows="2" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></Field>{error && <Notice tone="danger">{error}</Notice>}</form>
    </Modal>
    <Modal open={Boolean(invoicing)} title="অর্ডার থেকে ইনভয়েস" onClose={() => setInvoicing(null)} footer={<><Button variant="secondary" onClick={() => setInvoicing(null)}>বাতিল</Button><Button type="submit" form="invoice-order-form" loading={busy}>ইনভয়েস তৈরি</Button></>}>
      {invoicing && <form id="invoice-order-form" className="ui-form" onSubmit={invoice}><Notice tone="info">{invoicing.document_number} · মোট {money(invoicing.total)}। বাকি রাখলে কাস্টমার থাকা আবশ্যক।</Notice><Field label="পেমেন্ট মাধ্যম"><select value={invoicing.method} onChange={(e) => setInvoicing({ ...invoicing, method: e.target.value })}>{(active.payment_methods || ["cash"]).map((m) => <option key={m} value={m}>{m}</option>)}</select></Field><Field label="এখন পরিশোধ"><input type="number" min="0" max={Number(invoicing.total)} value={invoicing.paid} onChange={(e) => setInvoicing({ ...invoicing, paid: Number(e.target.value) })} /></Field>{error && <Notice tone="danger">{error}</Notice>}</form>}
    </Modal>
  </div>;
}
