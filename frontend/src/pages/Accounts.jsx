import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useBusiness } from "../BusinessContext";
import SettleModal, { PAY_METHODS } from "../components/SettleModal";
import { EXPENSE_CATEGORIES } from "../components/CategorySelect";
import { explain } from "../errors";
import { dateBn, money } from "../format";
import { usePermissions } from "../PermissionContext";
import DataTable from "../ui/DataTable";
import { Badge, Button, Card, EmptyState, Field, Modal, Notice, PageHeader, Segmented, Stat } from "../ui/kit";
import { useToast } from "../ui/Toast";
import AgeingCard from "../components/AgeingCard";

const METHOD_LABEL = Object.fromEntries(PAY_METHODS);
const OTHER = "__other__";
const localNow = () => {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
};

export default function AccountsPage() {
  const { active } = useBusiness();
  const { can } = usePermissions();
  const toast = useToast();
  const orgId = active?.id;
  const [tab, setTab] = useState("expenses");
  const [expenses, setExpenses] = useState(null);
  const [expenseTotal, setExpenseTotal] = useState(0);
  const [receivable, setReceivable] = useState([]);
  const [payable, setPayable] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [error, setError] = useState("");

  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ category: EXPENSE_CATEGORIES[0], custom: "", amount: "", payment_method: "cash", incurred_at: localNow(), note: "" });
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState("");
  const [settling, setSettling] = useState(null);

  const load = useCallback(async () => {
    if (!orgId) return;
    try {
      const [e, exp, rc, pay, c, s] = await Promise.all([
        api.expenses(orgId), api.ledger(orgId, "expense"), api.ledger(orgId, "receivable"),
        api.ledger(orgId, "payable"), api.customersApp(orgId), api.suppliers(orgId),
      ]);
      setExpenses(e);
      setExpenseTotal(exp.reduce((sum, r) => sum + Number(r.balance), 0));
      setReceivable(rc.filter((r) => Number(r.balance) > 0));
      setPayable(pay.filter((r) => Number(r.balance) > 0));
      setCustomers(c);
      setSuppliers(s);
      setError("");
    } catch (err) {
      setError(explain(err));
      setExpenses([]);
    }
  }, [orgId]);
  useEffect(() => { load(); }, [load]);

  const customerName = useMemo(() => Object.fromEntries(customers.map((c) => [c.id, c.display_name || c.code])), [customers]);
  const supplierName = useMemo(() => Object.fromEntries(suppliers.map((s) => [s.id, s.name])), [suppliers]);
  const owedToUs = receivable.reduce((s, r) => s + Number(r.balance), 0);
  const weOwe = payable.reduce((s, r) => s + Number(r.balance), 0);

  async function addExpense(e) {
    e.preventDefault();
    const category = form.category === OTHER ? form.custom.trim() : form.category;
    if (category.length < 2) { setFormError("খরচের ধরন লিখুন।"); return; }
    setBusy(true);
    setFormError("");
    try {
      const result = await api.createExpense(orgId, {
        category, amount: Number(form.amount).toFixed(2), payment_method: form.payment_method,
        incurred_at: new Date(form.incurred_at).toISOString(), note: form.note || null,
      });
      toast.success(result?.status === "pending_approval"
        ? `৳${form.amount}-এর বেশি খরচ — ${result.needs_role === "owner" ? "মালিকের" : "ম্যানেজারের"} অনুমোদনের অপেক্ষায় রাখা হয়েছে।`
        : "খরচ লেখা হয়েছে।");
      setAdding(false);
      setForm({ ...form, amount: "", note: "", custom: "", incurred_at: localNow() });
      load();
    } catch (err) {
      setFormError(explain(err, { 422: "খরচের ধরন ও টাকার পরিমাণ ঠিকভাবে দিন।" }));
    } finally {
      setBusy(false);
    }
  }

  const expenseColumns = [
    { key: "incurred_at", label: "তারিখ", primary: true, render: (x) => dateBn(x.incurred_at) },
    { key: "category", label: "ধরন", render: (x) => <div><strong>{x.category}</strong>{x.note && <div className="muted" style={{ fontSize: 12.5 }}>{x.note}</div>}</div> },
    { key: "payment_method", label: "মাধ্যম", render: (x) => METHOD_LABEL[x.payment_method] || x.payment_method },
    { key: "amount", label: "টাকা", align: "right", render: (x) => money(x.amount) },
  ];
  const partyColumns = (names, kind) => [
    { key: "party", label: kind === "customer" ? "কাস্টমার" : "সাপ্লায়ার", primary: true, render: (r) => <strong>{names[r.party_id] || "—"}</strong> },
    { key: "balance", label: kind === "customer" ? "আপনি পাবেন" : "আপনি দেবেন", align: "right", render: (r) => <Badge tone="warn">{money(r.balance)}</Badge> },
    ...(can(kind === "customer" ? "payments:customer" : "payments:supplier") ? [{
      key: "actions", label: "কাজ", align: "right",
      render: (r) => <Button size="sm" onClick={() => setSettling({ kind, party: { id: r.party_id, name: names[r.party_id] || "", balance: Number(r.balance) } })}>{kind === "customer" ? "বাকি আদায়" : "পেমেন্ট দিন"}</Button>,
    }] : []),
  ];

  return (
    <div className="page stack">
      <PageHeader
        title="হিসাব ও খরচ"
        subtitle="দোকানের খরচ লিখুন, আর কার কাছে কত বাকি পাবেন বা কাকে কত দেবেন তা দেখুন।"
        actions={can("expenses:write") && <Button icon="plus" onClick={() => { setFormError(""); setAdding(true); }}>নতুন খরচ</Button>}
      />
      {error && <Notice tone="danger" action={<Button size="sm" variant="secondary" onClick={load}>আবার চেষ্টা</Button>}>{error}</Notice>}
      {tab === "receivable" && orgId && <AgeingCard orgId={orgId} refreshKey={receivable.length} />}

      <div className="ui-stats">
        <Stat icon="card" label="মোট লেখা খরচ" value={money(expenseTotal)} onClick={() => setTab("expenses")} active={tab === "expenses"} />
        <Stat icon="users" label="কাস্টমারের কাছে পাবেন" tone={owedToUs > 0 ? "warn" : "success"} value={money(owedToUs)} sub={`${receivable.length} জনের কাছে`} onClick={() => setTab("receivable")} active={tab === "receivable"} />
        <Stat icon="truck" label="সাপ্লায়ারকে দেবেন" tone={weOwe > 0 ? "warn" : "success"} value={money(weOwe)} sub={`${payable.length} জনকে`} onClick={() => setTab("payable")} active={tab === "payable"} />
      </div>

      <Segmented label="হিসাবের ধরন" value={tab} onChange={setTab} options={[
        { value: "expenses", label: "খরচ", count: expenses?.length ?? 0 },
        { value: "receivable", label: "কাস্টমারের বাকি", count: receivable.length },
        { value: "payable", label: "সাপ্লায়ারের বাকি", count: payable.length },
      ]} />

      <Card pad={false}>
        {tab === "expenses" && (
          <DataTable rowKey="id" columns={expenseColumns} rows={expenses || []} loading={expenses === null} caption="খরচের তালিকা"
                     empty={<EmptyState icon="card" title="এখনো কোনো খরচ লেখা হয়নি" hint="ভাড়া, বিল, বেতন — যা খরচ হয় লিখে রাখুন, তাহলে সত্যিকারের লাভ বোঝা যাবে."
                                        action={can("expenses:write") && <Button icon="plus" onClick={() => setAdding(true)}>নতুন খরচ</Button>} />} />
        )}
        {tab === "receivable" && (
          <DataTable rowKey="party_id" columns={partyColumns(customerName, "customer")} rows={receivable}
                     empty={<EmptyState icon="check" title="কারও কাছে বাকি নেই" hint="বাকিতে বিক্রি করলে এখানে দেখা যাবে।" />} />
        )}
        {tab === "payable" && (
          <DataTable rowKey="party_id" columns={partyColumns(supplierName, "supplier")} rows={payable}
                     empty={<EmptyState icon="check" title="কাউকে বাকি দিতে হবে না" hint="মাল রিসিভ করলে সাপ্লায়ারের পাওনা এখানে জমা হবে।" />} />
        )}
      </Card>

      <Modal open={adding} title="নতুন খরচ" onClose={() => setAdding(false)}
             footer={<><Button variant="secondary" onClick={() => setAdding(false)}>বাতিল</Button><Button type="submit" form="expense-form" loading={busy}>খরচ লিখুন</Button></>}>
        <form id="expense-form" className="ui-form" onSubmit={addExpense}>
          <Field label="খরচের ধরন" required>
            <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
              {EXPENSE_CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
              <option value={OTHER}>অন্যান্য (নিজে লিখুন)</option>
            </select>
          </Field>
          {form.category === OTHER && <Field label="ধরন লিখুন" required><input value={form.custom} onChange={(e) => setForm({ ...form, custom: e.target.value })} maxLength={80} /></Field>}
          <Field label="টাকা" required><input type="number" min="0.01" step="0.01" inputMode="decimal" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} autoFocus /></Field>
          <div className="ui-form ui-form--2">
            <Field label="মাধ্যম"><select value={form.payment_method} onChange={(e) => setForm({ ...form, payment_method: e.target.value })}>{PAY_METHODS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></Field>
            <Field label="কবে"><input type="datetime-local" value={form.incurred_at} onChange={(e) => setForm({ ...form, incurred_at: e.target.value })} /></Field>
          </div>
          <Field label="নোট (ঐচ্ছিক)"><input value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} maxLength={200} /></Field>
          {formError && <Notice tone="danger">{formError}</Notice>}
        </form>
      </Modal>

      <SettleModal orgId={orgId} kind={settling?.kind} party={settling?.party} onClose={() => setSettling(null)}
                   onDone={() => { setSettling(null); load(); }} />
    </div>
  );
}
