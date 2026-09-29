import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useBusiness } from "../BusinessContext";
import { ReceiptFooter, ReceiptHeader } from "../components/ReceiptHeader";
import { explain } from "../errors";
import { dateTimeBn, money, num, todayInputValue } from "../format";
import { usePermissions } from "../PermissionContext";
import DataTable from "../ui/DataTable";
import { Badge, Button, Card, EmptyState, Field, Modal, Notice, PageHeader } from "../ui/kit";
import { useToast } from "../ui/Toast";
import useBranch from "../useBranch";

// Every invoice, searchable, with the receipt one tap away (and printable again).
export default function SalesHistoryPage() {
  const { active } = useBusiness();
  const { can } = usePermissions();
  const orgId = active?.id;
  const { branches, branch, setBranch, current } = useBranch(orgId);

  const [q, setQ] = useState("");
  const [customer, setCustomer] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [customers, setCustomers] = useState([]);
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");
  const [open, setOpen] = useState(null);
  const toast = useToast();
  const [voiding, setVoiding] = useState(false);
  const [reason, setReason] = useState("");
  const [voidBusy, setVoidBusy] = useState(false);
  const [voidError, setVoidError] = useState("");

  async function voidIt() {
    setVoidBusy(true); setVoidError("");
    try {
      await api.voidSale(orgId, open.id, { reason: reason.trim() });
      toast.success(`চালান ${open.invoice_number} বাতিল হয়েছে। মাল স্টকে ফিরেছে, টাকা ফেরত/বাকি কাটা হয়েছে।`);
      setVoiding(false); setReason(""); setOpen(null); load();
    } catch (e) {
      setVoidError(explain(e, { 403: "চালান বাতিলের অনুমতি শুধু মালিক ও ম্যানেজারের।", 409: "এই চালানে আগে রিটার্ন হয়েছে বা আগেই বাতিল হয়েছে। বাকি অংশ রিটার্ন পাতা থেকে ফেরত নিন।", 422: "বাতিলের কারণ লিখুন (কমপক্ষে ২ অক্ষর)।" }));
    } finally { setVoidBusy(false); }
  }

  useEffect(() => { if (orgId && can("customers:read")) api.customersApp(orgId).then(setCustomers).catch(() => {}); }, [orgId, can]);

  const load = useCallback(async () => {
    if (!orgId) return;
    setRows(null);
    try {
      setRows(await api.salesSearch(orgId, { branch, q: q.trim(), customer, from, to, limit: 200 }));
      setError("");
    } catch (e) {
      setError(explain(e));
      setRows([]);
    }
  }, [orgId, branch, q, customer, from, to]);

  // Typing in the search box searches after a short pause, not on every keystroke.
  useEffect(() => {
    const timer = setTimeout(load, 250);
    return () => clearTimeout(timer);
  }, [load]);

  const customerName = useMemo(() => Object.fromEntries(customers.map((c) => [c.id, c.display_name || c.code])), [customers]);
  const totals = useMemo(() => ({ count: rows?.length ?? 0, sum: (rows || []).reduce((s, r) => s + Number(r.total), 0), due: (rows || []).reduce((s, r) => s + Number(r.due), 0) }), [rows]);
  const filtered = Boolean(q || customer || from || to);

  return (
    <div className="page stack">
      <PageHeader title="বিক্রির ইতিহাস" subtitle="যেকোনো চালান খুঁজুন, রসিদ আবার দেখুন বা প্রিন্ট করুন।" />
      <div className="toolbar" style={{ alignItems: "flex-end" }}>
        <Field label="চালান নম্বর"><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="INV-…" /></Field>
        {customers.length > 0 && <Field label="কাস্টমার"><select value={customer} onChange={(e) => setCustomer(e.target.value)}><option value="">সবাই</option>{customers.map((c) => <option key={c.id} value={c.id}>{c.display_name || c.code}</option>)}</select></Field>}
        <Field label="থেকে"><input type="date" value={from} max={to || todayInputValue()} onChange={(e) => setFrom(e.target.value)} /></Field>
        <Field label="পর্যন্ত"><input type="date" value={to} min={from} max={todayInputValue()} onChange={(e) => setTo(e.target.value)} /></Field>
        {branches && branches.length > 1 && <Field label="শাখা"><select value={branch} onChange={(e) => setBranch(e.target.value)}>{branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}</select></Field>}
        {filtered && <Button variant="ghost" onClick={() => { setQ(""); setCustomer(""); setFrom(""); setTo(""); }}>ফিল্টার মুছুন</Button>}
      </div>
      {error && <Notice tone="danger" action={<Button size="sm" variant="secondary" onClick={load}>আবার চেষ্টা</Button>}>{error}</Notice>}

      {rows && rows.length > 0 && (
        <div className="ui-stats">
          <div className="ui-stat"><span className="ui-stat__label">চালান</span><strong className="ui-stat__value">{num(totals.count)}</strong></div>
          <div className="ui-stat ui-stat--success"><span className="ui-stat__label">মোট বিক্রি</span><strong className="ui-stat__value">{money(totals.sum)}</strong></div>
          <div className={`ui-stat ${totals.due > 0 ? "ui-stat--warn" : ""}`}><span className="ui-stat__label">এর মধ্যে বাকি</span><strong className="ui-stat__value">{money(totals.due)}</strong></div>
        </div>
      )}

      <Card pad={false}>
        <DataTable rowKey="id" loading={rows === null} rows={rows || []} caption="বিক্রির তালিকা"
                   columns={[
                     { key: "invoice_number", label: "চালান", primary: true, render: (r) => <span><button type="button" className="link-btn" style={{ font: "inherit", fontWeight: 700 }} onClick={() => setOpen(r)}>{r.invoice_number}</button>{r.status === "voided" && <> <Badge tone="danger">বাতিল</Badge></>}</span> },
                     { key: "sold_at", label: "সময়", render: (r) => dateTimeBn(r.sold_at) },
                     { key: "customer", label: "কাস্টমার", render: (r) => (r.customer_id ? customerName[r.customer_id] || "—" : "সাধারণ ক্রেতা") },
                     { key: "items", label: "পণ্য", render: (r) => r.items.map((i) => `${i.product_name} × ${num(i.quantity)}`).join(", ") },
                     { key: "total", label: "মোট", align: "right", render: (r) => money(r.total) },
                     { key: "due", label: "বাকি", align: "right", render: (r) => (Number(r.due) > 0 ? <Badge tone="warn">{money(r.due)}</Badge> : "—") },
                   ]}
                   empty={<EmptyState icon="search" title={filtered ? "কিছু মেলেনি" : "এখনো কোনো বিক্রি নেই"} hint={filtered ? "ফিল্টার বদলে দেখুন।" : "প্রথম বিক্রি করলে এখানে দেখা যাবে।"} />} />
      </Card>

      <Modal open={Boolean(open)} title={open ? `চালান ${open.invoice_number}` : ""} onClose={() => setOpen(null)}
             footer={<>
               {can("sales:void") && open?.status !== "voided" && <Button variant="danger" icon="ban" onClick={() => { setVoidError(""); setVoiding(true); }}>চালান বাতিল</Button>}
               {can("returns:create") && <a className="ui-btn ui-btn--secondary" href="#/returns">রিটার্ন নিন</a>}
               <Button variant="secondary" icon="printer" onClick={() => window.print()}>প্রিন্ট</Button>
               <Button onClick={() => setOpen(null)}>বন্ধ করুন</Button>
             </>}>
        {open && (
          <div className="receipt receipt-print">
            <ReceiptHeader shop={active} branch={current?.name} />
            {open.status === "voided" && <p style={{ color: "var(--danger, #c0392b)", fontWeight: 700 }}>*** বাতিল করা চালান ***</p>}
            <p>{open.invoice_number} · {dateTimeBn(open.sold_at)}</p>
            {open.customer_id && <p>কাস্টমার: {customerName[open.customer_id] || "—"}</p>}
            <table><tbody>
              {open.items.map((l) => (
                <tr key={l.id}><td>{l.product_name} × {num(l.quantity)}{Number(l.returned_quantity) > 0 ? ` (ফেরত ${num(l.returned_quantity)})` : ""}</td><td>{money(l.line_total)}</td></tr>
              ))}
            </tbody></table>
            {Number(open.discount_amount) > 0 && <div className="tot"><span>ছাড়</span><span>− {money(open.discount_amount)}</span></div>}
            <div className="tot"><span>মোট</span><span>{money(open.total)}</span></div>
            <div className="tot"><span>পরিশোধ</span><span>{money(open.paid)}</span></div>
            {Number(open.due) > 0 && <div className="tot"><span>বাকি</span><span>{money(open.due)}</span></div>}
            <ReceiptFooter shop={active} />
          </div>
        )}
      </Modal>

      <Modal open={voiding} title={open ? `চালান ${open.invoice_number} বাতিল করবেন?` : ""} onClose={() => setVoiding(false)}
             footer={<><Button variant="secondary" onClick={() => setVoiding(false)}>ফিরে যান</Button><Button variant="danger" loading={voidBusy} disabled={reason.trim().length < 2} onClick={voidIt}>হ্যাঁ, বাতিল করুন</Button></>}>
        <div className="ui-form">
          <Notice tone="warn">সব পণ্য স্টকে ফিরে যাবে, দেওয়া টাকা ফেরত দেখানো হবে এবং বাকি থাকলে তা কাটা যাবে। এটি ফেরানো যায় না।</Notice>
          <Field label="বাতিলের কারণ" required><input value={reason} onChange={(e) => setReason(e.target.value)} maxLength={140} placeholder="যেমন: ভুল পণ্য স্ক্যান হয়েছিল" autoComplete="off" /></Field>
          {voidError && <Notice tone="danger">{voidError}</Notice>}
        </div>
      </Modal>
    </div>
  );
}
