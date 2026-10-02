import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { useBusiness } from "../BusinessContext";
import { useConfirm } from "../components/ConfirmDialog";
import { explain } from "../errors";
import { dateTimeBn, num } from "../format";
import { usePermissions } from "../PermissionContext";
import DataTable from "../ui/DataTable";
import { Badge, Button, Card, EmptyState, Field, Notice, PageHeader } from "../ui/kit";
import { useToast } from "../ui/Toast";
import useBranch from "../useBranch";

// Snapshot what the system thinks is on the shelf, enter what's actually there,
// apply the difference as one reviewed batch — not silent one-off corrections.
// Expiry-tracked products stay out of this; "মেয়াদ ও ব্যাচ" owns those.
export default function StockCountPage() {
  const { active } = useBusiness();
  const { can } = usePermissions();
  const toast = useToast();
  const confirm = useConfirm();
  const orgId = active?.id;
  const { branches, branch, setBranch } = useBranch(orgId);
  const canAdjust = can("inventory:adjust");

  const [history, setHistory] = useState(null);
  const [open, setOpen] = useState(null); // the in-progress or just-viewed count, with lines
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState({}); // line id -> typed value

  const load = useCallback(async () => {
    if (!orgId || !branch) return;
    try {
      setHistory(await api.stockCounts(orgId, branch));
      setError("");
    } catch (e) {
      setError(explain(e));
      setHistory([]);
    }
  }, [orgId, branch]);
  useEffect(() => { load(); }, [load]);

  const openCount = (history || []).find((c) => c.status === "open");
  const loadDetail = useCallback(async (id) => {
    const detail = await api.stockCount(orgId, id);
    setOpen(detail);
    setDraft(Object.fromEntries(detail.lines.map((l) => [l.id, l.counted_qty == null ? "" : String(l.counted_qty)])));
  }, [orgId]);
  useEffect(() => { if (openCount) loadDetail(openCount.id); }, [openCount, loadDetail]);

  async function start() {
    setBusy(true); setError("");
    try {
      const detail = await api.startStockCount(orgId, { branch_id: branch });
      setOpen(detail);
      setDraft(Object.fromEntries(detail.lines.map((l) => [l.id, ""])));
      toast.success(`${num(detail.lines.length)}টি পণ্যের গণনা শুরু হয়েছে।`);
      load();
    } catch (e) {
      setError(explain(e, { 409: "এই শাখায় ইতিমধ্যে একটি গণনা চলছে।", 422: "গণনার মতো কোনো পণ্য নেই (মেয়াদবিহীন পণ্য লাগবে)।" }));
    } finally { setBusy(false); }
  }

  async function saveLine(line) {
    const value = draft[line.id];
    if (value === "" || value === undefined) return;
    try {
      const updated = await api.enterStockCount(orgId, open.id, line.id, value);
      setOpen((o) => ({ ...o, lines: o.lines.map((l) => (l.id === line.id ? { ...l, counted_qty: updated.counted_qty, variance: updated.variance } : l)) }));
    } catch (e) {
      toast.error(explain(e));
    }
  }

  async function complete() {
    const counted = open.lines.filter((l) => draft[l.id] !== "" && draft[l.id] !== undefined).length;
    const uncounted = open.lines.length - counted;
    const msg = uncounted > 0
      ? `${num(uncounted)}টি পণ্য এখনো গণনা করা হয়নি — সেগুলো অপরিবর্তিত থাকবে। বাকি ${num(counted)}টির গরমিল স্টকে যোগ হবে। নিশ্চিত?`
      : `সব গরমিল স্টকে প্রয়োগ হবে। এটি ফেরানো যায় না। নিশ্চিত?`;
    if (!(await confirm(msg))) return;
    setBusy(true);
    try {
      const result = await api.completeStockCount(orgId, open.id);
      toast.success(`গণনা শেষ। ${num(result.adjusted_lines)}টি পণ্যের স্টক ঠিক করা হয়েছে।`);
      setOpen(null);
      load();
    } catch (e) {
      toast.error(explain(e, { 409: "এই গণনা আগেই শেষ হয়ে গেছে।" }));
    } finally { setBusy(false); }
  }

  const unsavedCount = open ? open.lines.filter((l) => draft[l.id] !== "" && draft[l.id] !== undefined
    && Number(draft[l.id]) !== Number(l.counted_qty ?? NaN)).length : 0;

  return (
    <div className="page stack">
      {confirm.dialog}
      <PageHeader title="স্টক গণনা" subtitle="শেলফে আসলে কতটা আছে গুনে দেখুন — সিস্টেমের হিসাবের সাথে যা মিলবে না তা এক সাথে ঠিক হয়ে যাবে।"
                  actions={branches && branches.length > 1 && (
                    <Field label="শাখা"><select value={branch} onChange={(e) => setBranch(e.target.value)}>{branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}</select></Field>
                  )} />
      {error && <Notice tone="danger" action={<Button size="sm" variant="secondary" onClick={load}>আবার চেষ্টা</Button>}>{error}</Notice>}
      <Notice tone="info">মেয়াদ ট্র্যাক করা পণ্য (ওষুধের মতো) এখানে আসে না — সেগুলোর গরমিল "মেয়াদ ও ব্যাচ" পাতা থেকে ব্যাচ ধরে ঠিক করুন।</Notice>

      {!open && (
        <Card>
          {canAdjust ? (
            <Button icon="check" loading={busy} onClick={start}>নতুন গণনা শুরু করুন</Button>
          ) : (
            <Notice tone="info">গণনা শুরু করার অনুমতি আপনার ভূমিকায় নেই। তালিকা দেখতে পারেন।</Notice>
          )}
        </Card>
      )}

      {open && (
        <Card title="চলমান গণনা" subtitle={`শুরু ${dateTimeBn(open.started_at)} · ${open.started_by || "—"}`}
              actions={canAdjust && <Button loading={busy} onClick={complete}>গণনা শেষ করুন{unsavedCount > 0 ? ` (${num(unsavedCount)}টি অসংরক্ষিত)` : ""}</Button>}>
          <DataTable rowKey="id" rows={open.lines} caption="গণনার তালিকা"
                     columns={[
                       { key: "name", label: "পণ্য", primary: true, render: (l) => <div><strong>{l.name}</strong><div className="muted" style={{ fontSize: 12.5 }}>{l.sku}</div></div> },
                       { key: "system", label: "সিস্টেমের হিসাবে", align: "right", render: (l) => `${num(l.system_qty)} ${l.unit}` },
                       { key: "counted", label: "গুনে পেলাম", align: "right", render: (l) => (
                         canAdjust ? (
                           <div className="row" style={{ gap: 6, justifyContent: "flex-end", flexWrap: "nowrap" }}>
                             <input type="number" min="0" step="0.001" style={{ width: 90 }} value={draft[l.id] ?? ""}
                                    onChange={(e) => setDraft({ ...draft, [l.id]: e.target.value })}
                                    onBlur={() => saveLine(l)} aria-label={`${l.name} গণনা`} />
                             {l.counted_qty != null && Number(draft[l.id]) === Number(l.counted_qty) && <Badge tone="success" icon="check">সংরক্ষিত</Badge>}
                           </div>
                         ) : (l.counted_qty ?? "—")) },
                       { key: "variance", label: "গরমিল", align: "right", render: (l) => (
                         l.variance == null ? "—" : (
                           <Badge tone={Number(l.variance) === 0 ? "neutral" : Number(l.variance) < 0 ? "danger" : "success"}>
                             {Number(l.variance) > 0 ? "+" : ""}{num(l.variance)}
                           </Badge>)) },
                     ]} />
        </Card>
      )}

      <Card pad={false} title="গণনার ইতিহাস">
        <DataTable rowKey="id" loading={history === null} rows={(history || []).filter((c) => c.status === "completed")} caption="গণনার ইতিহাস"
                   columns={[
                     { key: "started_at", label: "তারিখ", primary: true, render: (c) => <div>{dateTimeBn(c.started_at)}<div className="muted" style={{ fontSize: 12.5 }}>{c.started_by}</div></div> },
                     { key: "products", label: "পণ্য", align: "right", render: (c) => num(c.products) },
                     { key: "counted", label: "গোনা হয়েছে", align: "right", render: (c) => num(c.counted) },
                     { key: "variance", label: "গরমিল", align: "right", render: (c) => (c.with_variance > 0 ? <Badge tone="warn">{num(c.with_variance)}টি</Badge> : <Badge tone="success">মিলেছে</Badge>) },
                   ]}
                   empty={<EmptyState icon="box" title="এখনো কোনো গণনা শেষ হয়নি" />} />
      </Card>
    </div>
  );
}
