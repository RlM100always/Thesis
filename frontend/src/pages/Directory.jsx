import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useBusiness } from "../BusinessContext";
import { CustomerDetail, SupplierDetail } from "../components/PartyDetail";
import SettleModal from "../components/SettleModal";
import { explain } from "../errors";
import { money, num } from "../format";
import { usePermissions } from "../PermissionContext";
import DataTable from "../ui/DataTable";
import { Badge, Button, Card, EmptyState, Field, Modal, Notice, PageHeader, Segmented } from "../ui/kit";
import { useToast } from "../ui/Toast";
import { EditCustomerModal } from "../components/EditModals";

const BLANK_CUSTOMER = { code: "", display_name: "", phone: "", marketing_consent: false };
const BLANK_SUPPLIER = { code: "", name: "", typical_lead_days: "7" };

export default function DirectoryPage() {
  const { active } = useBusiness();
  const { can } = usePermissions();
  const toast = useToast();
  const orgId = active?.id;
  const [tab, setTab] = useState("customers");
  const [query, setQuery] = useState("");
  const [customers, setCustomers] = useState(null);
  const [suppliers, setSuppliers] = useState(null);
  const [owedByCustomer, setOwedByCustomer] = useState({});
  const [owedToSupplier, setOwedToSupplier] = useState({});
  const [error, setError] = useState("");

  const [adding, setAdding] = useState(null); // "customer" | "supplier"
  const [customer, setCustomer] = useState(BLANK_CUSTOMER);
  const [supplier, setSupplier] = useState(BLANK_SUPPLIER);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState("");
  const [settling, setSettling] = useState(null); // { kind, party }
  const [viewing, setViewing] = useState(null); // { kind, id }
  const [editingCustomer, setEditingCustomer] = useState(null);

  const load = useCallback(async () => {
    if (!orgId) return;
    try {
      const [c, s] = await Promise.all([api.customersApp(orgId), api.suppliers(orgId).catch(() => [])]);
      setCustomers(c);
      setSuppliers(s);
      setError("");
    } catch (e) {
      setError(explain(e));
      setCustomers([]);
      setSuppliers([]);
    }
    if (can("ledger:read")) {
      api.ledger(orgId, "receivable").then((r) => setOwedByCustomer(Object.fromEntries(r.map((x) => [x.party_id, Number(x.balance)])))).catch(() => {});
      api.ledger(orgId, "payable").then((r) => setOwedToSupplier(Object.fromEntries(r.map((x) => [x.party_id, Number(x.balance)])))).catch(() => {});
    }
  }, [orgId, can]);
  useEffect(() => { load(); }, [load]);

  const q = query.trim().toLowerCase();
  const shownCustomers = useMemo(() => (customers || []).filter((c) => !q || c.code.toLowerCase().includes(q) || (c.display_name || "").toLowerCase().includes(q)), [customers, q]);
  const shownSuppliers = useMemo(() => (suppliers || []).filter((s) => !q || s.code.toLowerCase().includes(q) || s.name.toLowerCase().includes(q)), [suppliers, q]);
  const totalOwedToUs = Object.values(owedByCustomer).reduce((a, b) => a + b, 0);
  const totalWeOwe = Object.values(owedToSupplier).reduce((a, b) => a + b, 0);

  async function saveCustomer(e) {
    e.preventDefault();
    setBusy(true);
    setFormError("");
    try {
      await api.createCustomer(orgId, { ...customer, phone: customer.phone || null, display_name: customer.display_name || null });
      toast.success("কাস্টমার যোগ হয়েছে।");
      setAdding(null);
      setCustomer(BLANK_CUSTOMER);
      load();
    } catch (err) {
      setFormError(explain(err, { 409: "এই কোড দিয়ে আগেই একজন কাস্টমার আছে।", 422: "ফোন নম্বর ১১টি সংখ্যার হতে হবে (যেমন 01712345678)।" }));
    } finally {
      setBusy(false);
    }
  }
  async function saveSupplier(e) {
    e.preventDefault();
    setBusy(true);
    setFormError("");
    try {
      await api.createSupplier(orgId, { ...supplier, typical_lead_days: Number(supplier.typical_lead_days || 0) });
      toast.success("সাপ্লায়ার যোগ হয়েছে।");
      setAdding(null);
      setSupplier(BLANK_SUPPLIER);
      load();
    } catch (err) {
      setFormError(explain(err, { 409: "এই কোড দিয়ে আগেই একজন সাপ্লায়ার আছে।", 403: "সাপ্লায়ার যোগ করার অনুমতি আপনার নেই।" }));
    } finally {
      setBusy(false);
    }
  }

  const customerColumns = [
    { key: "name", label: "কাস্টমার", primary: true, render: (c) => <div><button type="button" className="link-btn" style={{ font: "inherit", fontWeight: 700, textAlign: "left" }} onClick={() => setViewing({ kind: "customer", id: c.id })}>{c.display_name || c.code}</button><div className="muted" style={{ fontSize: 12.5 }}>{c.code}</div></div> },
    { key: "consent", label: "প্রচারের সম্মতি", render: (c) => (c.marketing_consent ? <Badge tone="success" icon="check">আছে</Badge> : <Badge>নেই</Badge>) },
    { key: "due", label: "বাকি (আপনি পাবেন)", align: "right", render: (c) => (owedByCustomer[c.id] > 0 ? <Badge tone="warn">{money(owedByCustomer[c.id])}</Badge> : "—") },
  ];
  customerColumns.splice(2, 0, { key: "terms", label: "শর্ত", render: (c) => (
    <span>{c.price_tier === "wholesale" && <Badge tone="info">পাইকারি</Badge>}{c.credit_limit != null && <div className="muted" style={{ fontSize: 12.5 }}>সীমা {money(c.credit_limit)}</div>}{c.price_tier !== "wholesale" && c.credit_limit == null && "—"}</span>) });
  if (can("customers:write")) {
    customerColumns.push({ key: "edit", label: "", align: "right", render: (c) => <Button size="sm" variant="secondary" icon="edit" onClick={() => setEditingCustomer(c)} aria-label={`${c.display_name || c.code} সম্পাদনা`}>সম্পাদনা</Button> });
  }
  if (can("payments:customer")) {
    customerColumns.push({
      key: "actions", label: "কাজ", align: "right",
      render: (c) => owedByCustomer[c.id] > 0 && (
        <Button size="sm" onClick={() => setSettling({ kind: "customer", party: { id: c.id, name: c.display_name || c.code, balance: owedByCustomer[c.id] } })}>বাকি আদায়</Button>
      ),
    });
  }
  const supplierColumns = [
    { key: "name", label: "সাপ্লায়ার", primary: true, render: (s) => <div><button type="button" className="link-btn" style={{ font: "inherit", fontWeight: 700, textAlign: "left" }} onClick={() => setViewing({ kind: "supplier", id: s.id })}>{s.name}</button><div className="muted" style={{ fontSize: 12.5 }}>{s.code}</div></div> },
    { key: "lead", label: "ডেলিভারি সময়", render: (s) => (s.typical_lead_days ? `${num(s.typical_lead_days)} দিন` : "—") },
    { key: "due", label: "বাকি (আপনি দেবেন)", align: "right", render: (s) => (owedToSupplier[s.id] > 0 ? <Badge tone="warn">{money(owedToSupplier[s.id])}</Badge> : "—") },
  ];
  if (can("payments:supplier")) {
    supplierColumns.push({
      key: "actions", label: "কাজ", align: "right",
      render: (s) => owedToSupplier[s.id] > 0 && (
        <Button size="sm" onClick={() => setSettling({ kind: "supplier", party: { id: s.id, name: s.name, balance: owedToSupplier[s.id] } })}>পেমেন্ট দিন</Button>
      ),
    });
  }

  const isCustomers = tab === "customers";

  return (
    <div className="page stack">
      <PageHeader
        title="কাস্টমার ও সাপ্লায়ার"
        subtitle="কার কাছে কত বাকি পাবেন, কাকে কত দেবেন। বাকি আদায় ও পেমেন্ট এখান থেকেই।"
        actions={<>
          {can("customers:write") && <Button icon="plus" variant={isCustomers ? "primary" : "secondary"} onClick={() => { setFormError(""); setAdding("customer"); }}>নতুন কাস্টমার</Button>}
          {can("suppliers:write") && <Button icon="plus" variant={isCustomers ? "secondary" : "primary"} onClick={() => { setFormError(""); setAdding("supplier"); }}>নতুন সাপ্লায়ার</Button>}
        </>}
      />
      {error && <Notice tone="danger" action={<Button size="sm" variant="secondary" onClick={load}>আবার চেষ্টা</Button>}>{error}</Notice>}

      {can("ledger:read") && (totalOwedToUs > 0 || totalWeOwe > 0) && (
        <div className="ui-stats">
          <div className="ui-stat ui-stat--warn"><span className="ui-stat__label">মোট বাকি পাবেন</span><strong className="ui-stat__value">{money(totalOwedToUs)}</strong></div>
          <div className="ui-stat"><span className="ui-stat__label">মোট বাকি দেবেন</span><strong className="ui-stat__value">{money(totalWeOwe)}</strong></div>
        </div>
      )}

      <div className="toolbar">
        <Segmented label="তালিকা" value={tab} onChange={(v) => { setTab(v); setQuery(""); }} options={[
          { value: "customers", label: "কাস্টমার", count: customers?.length ?? 0 },
          { value: "suppliers", label: "সাপ্লায়ার", count: suppliers?.length ?? 0 },
        ]} />
        <Field label="খুঁজুন"><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="নাম বা কোড" /></Field>
      </div>

      <Card pad={false}>
        <DataTable
          rowKey="id" loading={(isCustomers ? customers : suppliers) === null}
          columns={isCustomers ? customerColumns : supplierColumns}
          rows={isCustomers ? shownCustomers : shownSuppliers}
          caption={isCustomers ? "কাস্টমারের তালিকা" : "সাপ্লায়ারের তালিকা"}
          empty={<EmptyState icon="users" title={query ? "কিছু মেলেনি" : isCustomers ? "এখনো কোনো কাস্টমার নেই" : "এখনো কোনো সাপ্লায়ার নেই"}
                             hint={query ? "অন্য নাম বা কোড দিয়ে খুঁজুন।" : isCustomers ? "বাকিতে বিক্রি বা রিফিল মনে করানোর জন্য কাস্টমার যোগ করুন।" : "মাল কিনতে সাপ্লায়ার লাগবে।"} />}
        />
      </Card>

      <Modal open={adding === "customer"} title="নতুন কাস্টমার" onClose={() => setAdding(null)}
             footer={<><Button variant="secondary" onClick={() => setAdding(null)}>বাতিল</Button><Button type="submit" form="customer-form" loading={busy}>যোগ করুন</Button></>}>
        <form id="customer-form" className="ui-form" onSubmit={saveCustomer}>
          <Field label="কোড" required hint="যেমন C-101 বা মোবাইলের শেষ ৪ সংখ্যা"><input value={customer.code} onChange={(e) => setCustomer({ ...customer, code: e.target.value })} autoComplete="off" /></Field>
          <Field label="নাম"><input value={customer.display_name} onChange={(e) => setCustomer({ ...customer, display_name: e.target.value })} autoComplete="off" /></Field>
          <Field label="মোবাইল নম্বর" hint="নম্বরটি সরাসরি সংরক্ষণ হয় না — শুধু একটি গোপন চিহ্ন (হ্যাশ) রাখা হয়"><input inputMode="tel" value={customer.phone} onChange={(e) => setCustomer({ ...customer, phone: e.target.value })} placeholder="01712345678" /></Field>
          <label className="checkbox" style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
            <input type="checkbox" checked={customer.marketing_consent} onChange={(e) => setCustomer({ ...customer, marketing_consent: e.target.checked })} style={{ width: 20, height: 20, marginTop: 2 }} />
            <span><strong>বার্তা পাঠানোর সম্মতি আছে</strong><br /><span className="muted">কাস্টমার নিজে রাজি হলেই টিক দিন। সম্মতি ছাড়া কাউকে প্রচারের বার্তা পাঠানো হবে না।</span></span>
          </label>
          {formError && <Notice tone="danger">{formError}</Notice>}
        </form>
      </Modal>

      <Modal open={adding === "supplier"} title="নতুন সাপ্লায়ার" onClose={() => setAdding(null)}
             footer={<><Button variant="secondary" onClick={() => setAdding(null)}>বাতিল</Button><Button type="submit" form="supplier-form" loading={busy}>যোগ করুন</Button></>}>
        <form id="supplier-form" className="ui-form" onSubmit={saveSupplier}>
          <Field label="কোড" required><input value={supplier.code} onChange={(e) => setSupplier({ ...supplier, code: e.target.value })} autoComplete="off" /></Field>
          <Field label="নাম" required><input value={supplier.name} onChange={(e) => setSupplier({ ...supplier, name: e.target.value })} minLength={2} autoComplete="off" /></Field>
          <Field label="সাধারণত কত দিনে মাল আসে?" hint="এর ভিত্তিতে কখন অর্ডার দিতে হবে তার হিসাব হয়"><input type="number" min="0" max="365" value={supplier.typical_lead_days} onChange={(e) => setSupplier({ ...supplier, typical_lead_days: e.target.value })} /></Field>
          {formError && <Notice tone="danger">{formError}</Notice>}
        </form>
      </Modal>

      <EditCustomerModal orgId={orgId} customer={editingCustomer} onClose={() => setEditingCustomer(null)} onSaved={() => { setEditingCustomer(null); load(); }} />
      <CustomerDetail customerId={viewing?.kind === "customer" ? viewing.id : null} onClose={() => setViewing(null)}
                      onCollect={can("payments:customer") ? (d) => { setViewing(null); setSettling({ kind: "customer", party: { id: d.customer_id, name: d.name, balance: Number(d.due) } }); } : undefined} />
      <SupplierDetail supplierId={viewing?.kind === "supplier" ? viewing.id : null} onClose={() => setViewing(null)}
                      onPay={can("payments:supplier") ? (d) => { setViewing(null); setSettling({ kind: "supplier", party: { id: d.supplier_id, name: d.name, balance: Number(d.we_owe) } }); } : undefined} />
      <SettleModal orgId={orgId} kind={settling?.kind} party={settling?.party} onClose={() => setSettling(null)}
                   onDone={() => { setSettling(null); load(); }} />
    </div>
  );
}
