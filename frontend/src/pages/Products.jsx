import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useBusiness } from "../BusinessContext";
import { EXPIRY_HINT } from "../verticals";
import { useConfirm } from "../components/ConfirmDialog";
import { explain } from "../errors";
import { money, num } from "../format";
import { usePermissions } from "../PermissionContext";
import DataTable from "../ui/DataTable";
import { Badge, Button, Card, EmptyState, Field, Modal, Notice, PageHeader, Segmented } from "../ui/kit";
import { useToast } from "../ui/Toast";
import { EditProductModal } from "../components/EditModals";

const BLANK = { sku: "", name: "", category: "", unit: "pcs", selling_price: "", cost_price: "", reorder_level: "0", track_expiry: false };
const UNITS = [["pcs", "পিস"], ["strip", "স্ট্রিপ"], ["box", "বক্স"], ["bottle", "বোতল"], ["packet", "প্যাকেট"], ["kg", "কেজি"], ["litre", "লিটার"], ["meter", "মিটার"], ["dozen", "ডজন"], ["set", "সেট"]];

export default function ProductsPage() {
  const { active, vertical, refresh } = useBusiness();
  const { can } = usePermissions();
  const toast = useToast();
  const confirm = useConfirm();
  const orgId = active?.id;
  const canWrite = can("catalog:write");
  const canTrack = can("inventory:adjust");

  const [rows, setRows] = useState(null);
  const [loadError, setLoadError] = useState("");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ ...BLANK, track_expiry: vertical.expiry });
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState("");
  const [editing, setEditing] = useState(null);

  const load = useCallback(async () => {
    if (!orgId) return;
    try {
      setRows(await api.productsApp(orgId));
      setLoadError("");
    } catch (e) {
      setLoadError(explain(e));
      setRows([]);
    }
  }, [orgId]);
  useEffect(() => { load(); }, [load]);

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (rows || []).filter((p) => {
      if (filter === "tracked" && !p.track_expiry) return false;
      if (filter === "untracked" && p.track_expiry) return false;
      if (filter === "nocost" && Number(p.cost_price) > 0) return false;
      return !q || p.name.toLowerCase().includes(q) || p.sku.toLowerCase().includes(q) || (p.barcode || "").toLowerCase().includes(q);
    });
  }, [rows, query, filter]);

  const counts = useMemo(() => ({
    all: rows?.length ?? 0,
    tracked: (rows || []).filter((p) => p.track_expiry).length,
    untracked: (rows || []).filter((p) => !p.track_expiry).length,
    nocost: (rows || []).filter((p) => Number(p.cost_price) <= 0).length,
  }), [rows]);

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.type === "checkbox" ? e.target.checked : e.target.value });

  async function create(e) {
    e.preventDefault();
    setBusy(true);
    setFormError("");
    try {
      await api.createProduct(orgId, {
        ...form, category: form.category || null, cost_price: form.cost_price || "0",
      });
      toast.success(`${form.name} যোগ হয়েছে।`);
      if (form.track_expiry) refresh(); // the expiry screens appear once anything tracks it
      setOpen(false);
      setForm({ ...BLANK, track_expiry: vertical.expiry });
      load();
    } catch (err) {
      setFormError(explain(err, { 409: "এই SKU দিয়ে আগেই একটি পণ্য আছে। অন্য SKU দিন।", 422: "নাম, SKU ও বিক্রয়মূল্য ঠিকভাবে দিন।" }));
    } finally {
      setBusy(false);
    }
  }

  async function enableTracking(product) {
    const ok = await confirm(
      `${product.name}-এর মেয়াদ ট্র্যাকিং চালু হবে। এখনকার স্টক "OPENING" নামের একটি ব্যাচে যাবে (মেয়াদ অজানা)। এরপর থেকে প্রতিটি ক্রয়ে ব্যাচ নম্বর ও মেয়াদ দিতে হবে, আর বিক্রি হবে আগে-মেয়াদ-শেষ-হওয়া-আগে নিয়মে। এটি ফেরানো যাবে না। চালু করবেন?`,
    );
    if (!ok) return;
    try {
      const result = await api.enableExpiryTracking(orgId, product.id);
      toast.success(`মেয়াদ ট্র্যাকিং চালু হয়েছে। ${num(result.opening_units)} ইউনিট OPENING ব্যাচে গেছে।`);
      refresh();
      load();
    } catch (err) {
      toast.error(explain(err, { 409: "এই পণ্যে মেয়াদ ট্র্যাকিং আগেই চালু আছে।" }));
    }
  }

  const columns = [
    { key: "name", label: "পণ্য", primary: true, render: (p) => <div><strong>{p.name}</strong><div className="muted" style={{ fontSize: 12.5 }}>{p.sku}{p.category ? ` · ${p.category}` : ""}</div></div> },
    { key: "selling_price", label: "বিক্রয়মূল্য", align: "right", render: (p) => money(p.selling_price) },
    {
      key: "cost_price", label: "ক্রয়মূল্য", align: "right",
      render: (p) => Number(p.cost_price) > 0
        ? <span>{money(p.cost_price)}<div className="muted" style={{ fontSize: 12 }}>লাভ {num(Math.round(((p.selling_price - p.cost_price) / p.selling_price) * 100))}%</div></span>
        : <Badge tone="warn" icon="alert">দেওয়া নেই</Badge>,
    },
    { key: "wholesale", label: "পাইকারি", align: "right", render: (p) => (p.wholesale_price == null ? "—" : money(p.wholesale_price)) },
    { key: "reorder_level", label: "পুনঃঅর্ডার", align: "right", render: (p) => num(p.reorder_level) },
    {
      key: "track", label: "মেয়াদ", align: "right",
      render: (p) => p.track_expiry
        ? <Badge tone="success" icon="clock">ট্র্যাক হচ্ছে</Badge>
        : canTrack ? <Button size="sm" variant="secondary" icon="clock" onClick={() => enableTracking(p)}>চালু করুন</Button> : <Badge>বন্ধ</Badge>,
    },
  ];

  if (canWrite) columns.push({ key: "edit", label: "", align: "right", render: (p) => <Button size="sm" variant="secondary" icon="edit" onClick={() => setEditing(p)} aria-label={`${p.name} সম্পাদনা`}>সম্পাদনা</Button> });

  return (
    <div className="page stack">
      {confirm.dialog}
      <EditProductModal orgId={orgId} product={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }} />
      <PageHeader
        title="পণ্য ও মূল্য"
        subtitle="কোন পণ্য কত দামে বিক্রি হয়, কত দামে কেনা। ক্রয়মূল্য না দিলে লাভের হিসাব ঠিক হয় না।"
        actions={canWrite && <Button icon="plus" onClick={() => setOpen(true)}>নতুন পণ্য</Button>}
      />
      {loadError && <Notice tone="danger" action={<Button size="sm" variant="secondary" onClick={load}>আবার চেষ্টা</Button>}>{loadError}</Notice>}
      {counts.nocost > 0 && rows && (
        <Notice tone="warn" title={`${num(counts.nocost)}টি পণ্যের ক্রয়মূল্য নেই`}>
          এগুলোর লাভ হিসাব করা যাচ্ছে না, তাই আপনার মোট লাভ বাস্তবের চেয়ে বেশি দেখাতে পারে।
        </Notice>
      )}

      <div className="toolbar">
        <Segmented label="পণ্য ফিল্টার" value={filter} onChange={setFilter} options={[
          { value: "all", label: "সব", count: counts.all },
          { value: "tracked", label: "মেয়াদ ট্র্যাক", count: counts.tracked },
          { value: "untracked", label: "ট্র্যাক করা হয়নি", count: counts.untracked },
          { value: "nocost", label: "ক্রয়মূল্য নেই", count: counts.nocost },
        ]} />
        <Field label="খুঁজুন"><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="নাম, SKU বা বারকোড" /></Field>
      </div>

      <Card pad={false}>
        <DataTable
          columns={columns} rows={shown} loading={rows === null} caption="পণ্যের তালিকা"
          empty={<EmptyState icon="tag" title={query || filter !== "all" ? "কিছু মেলেনি" : "এখনো কোনো পণ্য নেই"}
                             hint={query || filter !== "all" ? "ফিল্টার বা খোঁজা বদলে দেখুন।" : "প্রথম পণ্য যোগ করে শুরু করুন।"}
                             action={canWrite && !query && filter === "all" && <Button icon="plus" onClick={() => setOpen(true)}>নতুন পণ্য</Button>} />}
        />
      </Card>

      <Modal open={open} title="নতুন পণ্য" onClose={() => { setOpen(false); setFormError(""); }}
             footer={<>
               <Button variant="secondary" onClick={() => setOpen(false)}>বাতিল</Button>
               <Button type="submit" form="product-form" loading={busy}>পণ্য যোগ করুন</Button>
             </>}>
        <form id="product-form" className="ui-form ui-form--2" onSubmit={create}>
          <Field label="পণ্যের নাম" required><input value={form.name} onChange={set("name")} autoComplete="off" /></Field>
          <Field label="SKU / কোড" required hint="প্রতিটি পণ্যের আলাদা কোড"><input value={form.sku} onChange={set("sku")} autoComplete="off" /></Field>
          <Field label="ক্যাটাগরি"><input value={form.category} onChange={set("category")} placeholder="যেমন: ব্যথানাশক" /></Field>
          <Field label="একক"><select value={form.unit} onChange={set("unit")}>{UNITS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></Field>
          <Field label="বিক্রয়মূল্য (৳)" required><input type="number" min="0" step="0.01" inputMode="decimal" value={form.selling_price} onChange={set("selling_price")} /></Field>
          <Field label="ক্রয়মূল্য (৳)" hint="লাভ হিসাবের জন্য দিন"><input type="number" min="0" step="0.01" inputMode="decimal" value={form.cost_price} onChange={set("cost_price")} /></Field>
          <Field label="পুনঃঅর্ডার সীমা" hint="এর নিচে নামলে ‘কম স্টক’ দেখাবে"><input type="number" min="0" step="0.001" value={form.reorder_level} onChange={set("reorder_level")} /></Field>
          <div className="ui-span">
            <label className="checkbox" style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
              <input type="checkbox" checked={form.track_expiry} onChange={set("track_expiry")} style={{ width: 20, height: 20, marginTop: 2 }} />
              <span><strong>মেয়াদ ট্র্যাক করুন</strong><br /><span className="muted">যে পণ্যের মেয়াদ থাকে (খাবার, ওষুধ, প্রসাধনী)। ব্যাচ নম্বর ও মেয়াদ লেখা হবে, আর আগে মেয়াদ শেষ হবে এমনটাই আগে বিক্রি হবে। {vertical.expiry ? EXPIRY_HINT.on : "না থাকলে টিক দেবেন না।"}</span></span>
            </label>
          </div>
          {formError && <div className="ui-span"><Notice tone="danger">{formError}</Notice></div>}
        </form>
      </Modal>
    </div>
  );
}
