import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useBusiness } from "../BusinessContext";
import { explain } from "../errors";
import { dateTimeBn, money, num } from "../format";
import { usePermissions } from "../PermissionContext";
import DataTable from "../ui/DataTable";
import { Badge, Button, Card, EmptyState, Field, Modal, Notice, PageHeader } from "../ui/kit";
import { useToast } from "../ui/Toast";

const REASONS = ["কাস্টমার ফেরত দিয়েছেন", "ভুল পণ্য দেওয়া হয়েছে", "নষ্ট বা ভাঙা", "মেয়াদ নিয়ে সমস্যা"];
const REFUNDS = [["cash", "ক্যাশ ফেরত"], ["bkash", "বিকাশে ফেরত"], ["nagad", "নগদে ফেরত"], ["", "বাকি থেকে বাদ (টাকা ফেরত নয়)"]];
const returnNumber = () => `RET-${Date.now().toString(36).toUpperCase()}`;

export default function ReturnsPage() {
  const { active } = useBusiness();
  const { can } = usePermissions();
  const toast = useToast();
  const orgId = active?.id;
  const canReturn = can("returns:create");

  const [sales, setSales] = useState(null);
  const [history, setHistory] = useState(null);
  const [error, setError] = useState("");
  const [open, setOpen] = useState(false);
  const [saleId, setSaleId] = useState("");
  const [lines, setLines] = useState({}); // line id -> { qty, restock }
  const [reason, setReason] = useState(REASONS[0]);
  const [refund, setRefund] = useState("cash");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState("");

  const load = useCallback(async () => {
    if (!orgId) return;
    try {
      const [s, h] = await Promise.all([api.salesApp(orgId), api.returns(orgId)]);
      setSales(s);
      setHistory(h);
      setError("");
    } catch (e) {
      setError(explain(e));
      setSales([]);
      setHistory([]);
    }
  }, [orgId]);
  useEffect(() => { load(); }, [load]);

  const sale = useMemo(() => (sales || []).find((s) => s.id === saleId), [sales, saleId]);
  const returnable = (line) => Number(line.quantity) - Number(line.returned_quantity);
  const eligibleSales = useMemo(() => (sales || []).filter((s) => s.items.some((l) => returnable(l) > 0)), [sales]);

  function start() {
    setSaleId(eligibleSales[0]?.id || "");
    setLines({});
    setReason(REASONS[0]);
    setRefund("cash");
    setFormError("");
    setOpen(true);
  }
  const setLine = (id, patch) => setLines((all) => ({ ...all, [id]: { qty: "", restock: true, ...all[id], ...patch } }));

  async function submit(e) {
    e.preventDefault();
    const items = Object.entries(lines)
      .filter(([, v]) => Number(v.qty) > 0)
      .map(([id, v]) => ({ sales_order_item_id: id, quantity: String(v.qty), restock: v.restock !== false }));
    if (!items.length) { setFormError("কোন পণ্য কত ফেরত এসেছে তা লিখুন।"); return; }
    setBusy(true);
    setFormError("");
    try {
      await api.createReturn(orgId, saleId, {
        return_number: returnNumber(), reason, returned_at: new Date().toISOString(), items, refund_method: refund || null,
      });
      toast.success("রিটার্ন সম্পন্ন হয়েছে।");
      setOpen(false);
      load();
    } catch (err) {
      setFormError(explain(err, {
        409: "ফেরতের পরিমাণ বিক্রির পরিমাণের চেয়ে বেশি।",
        422: "চালানের সব টাকা আগেই পরিশোধ করা থাকলে টাকা ফেরতের মাধ্যম (ক্যাশ/বিকাশ/নগদ) বেছে নিতে হবে।",
      }));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page stack">
      <PageHeader
        title="বিক্রয় রিটার্ন"
        subtitle="কাস্টমার পণ্য ফেরত দিলে এখান থেকে লিখুন। ফেরত মাল আগের ব্যাচেই স্টকে ফিরে যায়।"
        actions={canReturn && <Button icon="undo" onClick={start} disabled={!eligibleSales.length}>নতুন রিটার্ন</Button>}
      />
      {error && <Notice tone="danger" action={<Button size="sm" variant="secondary" onClick={load}>আবার চেষ্টা</Button>}>{error}</Notice>}
      {sales && !eligibleSales.length && (history?.length ?? 0) === 0 && <Notice tone="info">ফেরত নেওয়ার মতো কোনো বিক্রি এখনো নেই।</Notice>}

      <Card pad={false} title="রিটার্নের ইতিহাস">
        <DataTable rowKey="id" loading={history === null} rows={history || []} caption="রিটার্নের তালিকা"
                   columns={[
                     { key: "return_number", label: "রিটার্ন নং", primary: true },
                     { key: "invoice_number", label: "চালান" },
                     { key: "returned_at", label: "সময়", render: (r) => dateTimeBn(r.returned_at) },
                     { key: "reason", label: "কারণ" },
                     { key: "total", label: "ফেরতের মূল্য", align: "right", render: (r) => money(r.total) },
                   ]}
                   empty={<EmptyState icon="undo" title="এখনো কোনো রিটার্ন নেই" hint="কাস্টমার পণ্য ফেরত দিলে এখানে জমা হবে।" />} />
      </Card>

      <Modal wide open={open} title="নতুন রিটার্ন" onClose={() => setOpen(false)}
             footer={<><Button variant="secondary" onClick={() => setOpen(false)}>বাতিল</Button><Button type="submit" form="return-form" loading={busy}>রিটার্ন নিশ্চিত করুন</Button></>}>
        <form id="return-form" className="ui-form" onSubmit={submit}>
          <Field label="কোন চালানের রিটার্ন?" required>
            <select value={saleId} onChange={(e) => { setSaleId(e.target.value); setLines({}); }}>
              {eligibleSales.map((s) => <option key={s.id} value={s.id}>{s.invoice_number} · {dateTimeBn(s.sold_at)} · {money(s.total)}</option>)}
            </select>
          </Field>
          {sale && sale.items.map((line) => {
            const max = returnable(line);
            if (max <= 0) return null;
            const state = lines[line.id] || { qty: "", restock: true };
            return (
              <Card key={line.id} title={line.product_name} subtitle={`বিক্রি হয়েছিল ${num(line.quantity)} · ফেরতযোগ্য ${num(max)} · দাম ${money(line.unit_price)}`}>
                <div className="field-inline">
                  <Field label="কত ফেরত এসেছে?"><input type="number" min="0" max={max} step="0.001" value={state.qty} onChange={(e) => setLine(line.id, { qty: e.target.value })} /></Field>
                  <label className="checkbox" style={{ display: "flex", gap: 8, alignItems: "center" }}>
                    <input type="checkbox" checked={state.restock !== false} onChange={(e) => setLine(line.id, { restock: e.target.checked })} style={{ width: 20, height: 20 }} />
                    <span>বিক্রিযোগ্য স্টকে ফেরত দিন</span>
                  </label>
                </div>
                {state.restock === false && <Badge tone="warn" icon="alert">নষ্ট বা অবিক্রয়যোগ্য মাল স্টকে ফিরবে না</Badge>}
              </Card>
            );
          })}
          <div className="ui-form ui-form--2">
            <Field label="কারণ" required><input value={reason} onChange={(e) => setReason(e.target.value)} list="return-reasons" minLength={2} /></Field>
            <Field label="টাকা কীভাবে ফেরত?">
              <select value={refund} onChange={(e) => setRefund(e.target.value)}>{REFUNDS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
            </Field>
          </div>
          <datalist id="return-reasons">{REASONS.map((r) => <option key={r} value={r} />)}</datalist>
          {formError && <Notice tone="danger">{formError}</Notice>}
        </form>
      </Modal>
    </div>
  );
}
