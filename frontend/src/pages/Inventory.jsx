import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useBusiness } from "../BusinessContext";
import { useConfirm } from "../components/ConfirmDialog";
import { explain } from "../errors";
import { dateBn, expiryLabel, num, todayInputValue } from "../format";
import { usePermissions } from "../PermissionContext";
import DataTable from "../ui/DataTable";
import { Badge, Button, Card, EmptyState, Field, Modal, Notice, PageHeader, Segmented, Stat } from "../ui/kit";
import { useToast } from "../ui/Toast";
import useBranch from "../useBranch";

const REASONS_OUT = ["মেয়াদ শেষ — ফেলে দেওয়া হয়েছে", "ভাঙা বা নষ্ট", "গণনায় কম পাওয়া গেছে", "নমুনা বা উপহার"];
const REASONS_IN = ["প্রারম্ভিক স্টক", "গণনায় বেশি পাওয়া গেছে", "ফেরত পাওয়া"];
const NEW_BATCH = "__new__";

export default function InventoryPage() {
  const { active } = useBusiness();
  const { can } = usePermissions();
  const toast = useToast();
  const confirm = useConfirm();
  const orgId = active?.id;
  const canAdjust = can("inventory:adjust");
  const canTransfer = can("inventory:transfer");
  const canOrder = can("purchases:create");
  const { branches, branch, setBranch } = useBranch(orgId);

  const [rows, setRows] = useState(null);
  const [products, setProducts] = useState({});
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("all");
  const [query, setQuery] = useState("");

  const [target, setTarget] = useState(null); // row being adjusted
  const [direction, setDirection] = useState("out");
  const [qty, setQty] = useState("");
  const [reason, setReason] = useState("");
  const [batches, setBatches] = useState([]);
  const [batchId, setBatchId] = useState("");
  const [newBatch, setNewBatch] = useState({ batch_no: "", expiry_date: "" });
  const [formError, setFormError] = useState("");
  const [busy, setBusy] = useState(false);
  const [moving, setMoving] = useState(null); // row being transferred
  const [moveTo, setMoveTo] = useState("");
  const [moveQty, setMoveQty] = useState("");
  const [moveError, setMoveError] = useState("");

  const load = useCallback(async () => {
    if (!orgId || !branch) return;
    try {
      const [inv, prods] = await Promise.all([api.inventoryApp(orgId, branch), api.productsApp(orgId)]);
      setRows(inv);
      setProducts(Object.fromEntries(prods.map((p) => [p.id, p])));
      setError("");
    } catch (e) {
      setError(explain(e));
      setRows([]);
    }
  }, [orgId, branch]);
  useEffect(() => { setRows(null); load(); }, [load]);

  const counts = useMemo(() => {
    const list = rows || [];
    return {
      all: list.length,
      low: list.filter((r) => r.low_stock && Number(r.quantity) > 0).length,
      out: list.filter((r) => Number(r.quantity) <= 0).length,
    };
  }, [rows]);

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (rows || []).filter((r) => {
      if (filter === "low" && !(r.low_stock && Number(r.quantity) > 0)) return false;
      if (filter === "out" && Number(r.quantity) > 0) return false;
      return !q || r.product_name.toLowerCase().includes(q) || r.sku.toLowerCase().includes(q);
    });
  }, [rows, filter, query]);

  const tracked = target ? products[target.product_id]?.track_expiry : false;

  async function openAdjust(row) {
    setTarget(row);
    setDirection("out");
    setQty("");
    setReason("");
    setBatchId("");
    setNewBatch({ batch_no: "", expiry_date: "" });
    setFormError("");
    setBatches([]);
    if (products[row.product_id]?.track_expiry) {
      try { setBatches(await api.batches(orgId, branch, { productId: row.product_id })); } catch { /* the form still works; the batch list is a convenience */ }
    }
  }

  async function submit(e) {
    e.preventDefault();
    const amount = Number(qty);
    if (!(amount > 0)) { setFormError("পরিমাণ ০-র বেশি হতে হবে।"); return; }
    if (direction === "out") {
      const ok = await confirm(`${target.product_name}-এর স্টক থেকে ${num(amount)} ইউনিট বাদ যাবে। নিশ্চিত?`);
      if (!ok) return;
    }
    const body = {
      branch_id: branch, product_id: target.product_id,
      quantity_delta: String(direction === "out" ? -amount : amount), reason,
    };
    if (tracked) {
      if (direction === "out" || (batchId && batchId !== NEW_BATCH)) body.batch_id = batchId;
      else { body.batch_no = newBatch.batch_no; body.expiry_date = newBatch.expiry_date; }
    }
    setBusy(true);
    setFormError("");
    try {
      await api.adjustStock(orgId, body);
      toast.success("স্টক আপডেট হয়েছে।");
      setTarget(null);
      load();
    } catch (err) {
      setFormError(explain(err, {
        409: direction === "out" ? "এত ইউনিট নেই। স্টক বা ব্যাচের পরিমাণ দেখে আবার দিন।" : "এই ব্যাচ নম্বর আগেই অন্য মেয়াদে আছে।",
        422: tracked ? "ব্যাচ বেছে নিন, অথবা নতুন ব্যাচের নম্বর ও মেয়াদ দিন।" : "পরিমাণ ও কারণ ঠিকভাবে দিন।",
      }));
    } finally {
      setBusy(false);
    }
  }

  function startMove(row) {
    setMoving(row);
    setMoveTo((branches || []).find((b) => b.id !== branch)?.id || "");
    setMoveQty("");
    setMoveError("");
  }

  async function submitMove(e) {
    e.preventDefault();
    setBusy(true);
    setMoveError("");
    try {
      await api.transferStock(orgId, { from_branch_id: branch, to_branch_id: moveTo, product_id: moving.product_id, quantity: String(moveQty) });
      toast.success(`${num(moveQty)} ইউনিট ${moving.product_name} অন্য শাখায় গেছে।`);
      setMoving(null);
      load();
    } catch (err) {
      setMoveError(explain(err, {
        409: "এই শাখায় এত ইউনিট বিক্রির মতো অবস্থায় নেই। (মেয়াদোত্তীর্ণ বা বন্ধ ব্যাচ স্থানান্তর হয় না।)",
        422: "দুটি আলাদা শাখা বেছে নিন এবং পরিমাণ দিন।",
      }));
    } finally {
      setBusy(false);
    }
  }

  const columns = [
    { key: "product_name", label: "পণ্য", primary: true, render: (r) => <div><strong>{r.product_name}</strong><div className="muted" style={{ fontSize: 12.5 }}>{r.sku}</div></div> },
    { key: "quantity", label: "স্টক", align: "right", render: (r) => <strong>{num(r.quantity)}</strong> },
    { key: "reorder_level", label: "পুনঃঅর্ডার", align: "right", render: (r) => num(r.reorder_level) },
    {
      key: "status", label: "অবস্থা",
      render: (r) => Number(r.quantity) <= 0 ? <Badge tone="danger" icon="alert">স্টক নেই</Badge>
        : r.low_stock ? <Badge tone="warn" icon="alert">কম</Badge> : <Badge tone="success" icon="check">পর্যাপ্ত</Badge>,
    },
    { key: "track", label: "মেয়াদ", render: (r) => (products[r.product_id]?.track_expiry ? <a href="#/expiry"><Badge tone="info" icon="clock">ট্র্যাক হচ্ছে</Badge></a> : <span className="muted">—</span>) },
  ];
  if (canAdjust || canTransfer || canOrder) {
    columns.push({
      key: "actions", label: "কাজ", align: "right",
      render: (r) => (
        <div className="row-actions">
          {canOrder && (r.low_stock || Number(r.quantity) <= 0) && (
            <a className="ui-btn ui-btn--sm ui-btn--secondary" href={`#/purchases?product=${r.product_id}`}>অর্ডার দিন</a>
          )}
          {canTransfer && branches && branches.length > 1 && Number(r.quantity) > 0 && (
            <Button size="sm" variant="secondary" icon="truck" onClick={() => startMove(r)}>স্থানান্তর</Button>
          )}
          {canAdjust && <Button size="sm" variant="secondary" icon="edit" onClick={() => openAdjust(r)}>সমন্বয়</Button>}
        </div>
      ),
    });
  }

  const reasons = direction === "out" ? REASONS_OUT : REASONS_IN;
  const selectableBatches = direction === "out" ? batches : batches.filter((b) => !b.blocked);

  return (
    <div className="page stack">
      {confirm.dialog}
      <PageHeader
        title="স্টক"
        subtitle="কোন পণ্য কতটা আছে, কোনটা কমে এসেছে। গণনায় গরমিল পেলে এখান থেকে সমন্বয় করুন।"
        actions={branches && branches.length > 1 && (
          <Field label="শাখা"><select value={branch} onChange={(e) => setBranch(e.target.value)}>
            {branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select></Field>
        )}
      />
      {error && <Notice tone="danger" action={<Button size="sm" variant="secondary" onClick={load}>আবার চেষ্টা</Button>}>{error}</Notice>}

      <div className="ui-stats">
        <Stat label="মোট পণ্য" value={num(counts.all)} icon="box" />
        <Stat label="কম স্টক" tone={counts.low ? "warn" : "success"} value={num(counts.low)} sub="পুনঃঅর্ডার সীমার নিচে" onClick={() => setFilter("low")} active={filter === "low"} />
        <Stat label="স্টক নেই" tone={counts.out ? "danger" : "success"} value={num(counts.out)} sub="বিক্রি করা যাবে না" onClick={() => setFilter("out")} active={filter === "out"} />
      </div>

      <div className="toolbar">
        <Segmented label="স্টক ফিল্টার" value={filter} onChange={setFilter} options={[
          { value: "all", label: "সব", count: counts.all }, { value: "low", label: "কম স্টক", count: counts.low }, { value: "out", label: "স্টক নেই", count: counts.out },
        ]} />
        <Field label="খুঁজুন"><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="নাম বা SKU" /></Field>
      </div>

      <Card pad={false}>
        <DataTable columns={columns} rows={shown} rowKey="product_id" loading={rows === null} caption="স্টকের তালিকা"
                   empty={<EmptyState icon="box" title={query || filter !== "all" ? "কিছু মেলেনি" : "এই শাখায় এখনো কোনো পণ্য নেই"}
                                      hint={query || filter !== "all" ? "ফিল্টার বদলে দেখুন।" : "পণ্য যোগ করে ক্রয়ের মাধ্যমে স্টক তুলুন।"} />} />
      </Card>

      <Modal open={Boolean(moving)} title={moving ? `অন্য শাখায় পাঠান — ${moving.product_name}` : ""} onClose={() => setMoving(null)}
             footer={<><Button variant="secondary" onClick={() => setMoving(null)}>বাতিল</Button><Button type="submit" form="move-form" loading={busy}>স্থানান্তর করুন</Button></>}>
        {moving && (
          <form id="move-form" className="ui-form" onSubmit={submitMove}>
            <p className="muted" style={{ margin: 0 }}>এই শাখায় আছে: <strong>{num(moving.quantity)}</strong></p>
            <Field label="কোন শাখায় পাঠাবেন?" required>
              <select value={moveTo} onChange={(e) => setMoveTo(e.target.value)}>
                {(branches || []).filter((b) => b.id !== branch).map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
              </select>
            </Field>
            <Field label="কত ইউনিট?" required hint={products[moving.product_id]?.track_expiry ? "মেয়াদ ট্র্যাক করা পণ্য — আগে মেয়াদ শেষ হবে এমন ব্যাচ আগে যাবে, মেয়াদসহ।" : undefined}>
              <input type="number" min="0.001" max={moving.quantity} step="0.001" inputMode="decimal" value={moveQty} onChange={(e) => setMoveQty(e.target.value)} autoFocus />
            </Field>
            {moveError && <Notice tone="danger">{moveError}</Notice>}
          </form>
        )}
      </Modal>

      <Modal open={Boolean(target)} title={target ? `স্টক সমন্বয় — ${target.product_name}` : ""} onClose={() => setTarget(null)}
             footer={<>
               <Button variant="secondary" onClick={() => setTarget(null)}>বাতিল</Button>
               <Button type="submit" form="adjust-form" loading={busy}>সংরক্ষণ করুন</Button>
             </>}>
        {target && (
          <form id="adjust-form" className="ui-form" onSubmit={submit}>
            <p className="muted" style={{ margin: 0 }}>এখন স্টকে আছে: <strong>{num(target.quantity)}</strong></p>
            <Segmented label="যোগ না বাদ" value={direction} onChange={(v) => { setDirection(v); setReason(""); setBatchId(""); }}
                       options={[{ value: "out", label: "স্টক থেকে বাদ" }, { value: "in", label: "স্টকে যোগ" }]} />
            <Field label="কত ইউনিট?" required><input type="number" min="0.001" step="0.001" inputMode="decimal" value={qty} onChange={(e) => setQty(e.target.value)} autoFocus /></Field>
            <Field label="কারণ" required>
              <input value={reason} onChange={(e) => setReason(e.target.value)} minLength={2} maxLength={120} list="reasons" />
            </Field>
            <datalist id="reasons">{reasons.map((r) => <option key={r} value={r} />)}</datalist>

            {tracked && (
              direction === "out" ? (
                <Field label="কোন ব্যাচ থেকে?" required hint="মেয়াদ ট্র্যাক করা পণ্যে কোন ব্যাচ থেকে বাদ যাচ্ছে তা বলতে হয়।">
                  <select value={batchId} onChange={(e) => setBatchId(e.target.value)}>
                    <option value="">— ব্যাচ বেছে নিন —</option>
                    {selectableBatches.map((b) => (
                      <option key={b.batch_id} value={b.batch_id}>
                        {b.batch_no} · {num(b.quantity)} ইউনিট · {b.expiry_date ? dateBn(b.expiry_date) : "মেয়াদ অজানা"} ({expiryLabel(b.days_to_expiry)})
                      </option>
                    ))}
                  </select>
                </Field>
              ) : (
                <>
                  <Field label="কোন ব্যাচে যোগ হবে?" required>
                    <select value={batchId || NEW_BATCH} onChange={(e) => setBatchId(e.target.value)}>
                      <option value={NEW_BATCH}>নতুন ব্যাচ</option>
                      {selectableBatches.map((b) => <option key={b.batch_id} value={b.batch_id}>{b.batch_no} · {b.expiry_date ? dateBn(b.expiry_date) : "মেয়াদ অজানা"}</option>)}
                    </select>
                  </Field>
                  {(!batchId || batchId === NEW_BATCH) && (
                    <div className="ui-form ui-form--2">
                      <Field label="ব্যাচ নম্বর" required><input value={newBatch.batch_no} onChange={(e) => setNewBatch({ ...newBatch, batch_no: e.target.value })} /></Field>
                      <Field label="মেয়াদ শেষের তারিখ" required><input type="date" min={todayInputValue()} value={newBatch.expiry_date} onChange={(e) => setNewBatch({ ...newBatch, expiry_date: e.target.value })} /></Field>
                    </div>
                  )}
                </>
              )
            )}
            {formError && <Notice tone="danger">{formError}</Notice>}
          </form>
        )}
      </Modal>
    </div>
  );
}
