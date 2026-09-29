import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useBusiness } from "../BusinessContext";
import { explain } from "../errors";
import { EXPIRY_TONE, dateBn, expiryLabel, money, num } from "../format";
import { usePermissions } from "../PermissionContext";
import DataTable from "../ui/DataTable";
import { Badge, Button, Card, EmptyState, Field, Modal, Notice, PageHeader, Segmented, Skeleton, Stat } from "../ui/kit";
import { useToast } from "../ui/Toast";
import useBranch from "../useBranch";

const STATE_LABEL = { expired: "মেয়াদ শেষ", near_expiry: "শীঘ্রই শেষ", ok: "ভালো", no_expiry: "মেয়াদ অজানা" };
const BUCKETS = [
  ["expired", "মেয়াদোত্তীর্ণ", "var(--danger)"],
  ["d30", "৩০ দিনের মধ্যে", "#e8590c"],
  ["d60", "৩১–৬০ দিন", "var(--warn)"],
  ["d90", "৬১–৯০ দিন", "#d4a017"],
  ["later", "৯০ দিনের পরে", "var(--green)"],
  ["no_expiry", "মেয়াদ অজানা", "var(--text-muted)"],
];
const REASONS = ["রিকল নোটিশ এসেছে", "ভাঙা বা নষ্ট", "কোয়ারেন্টাইন — যাচাই চলছে", "সাপ্লায়ারকে ফেরত দেওয়া হবে"];

function BucketBar({ buckets }) {
  const total = BUCKETS.reduce((s, [k]) => s + Number(buckets[k].units), 0);
  if (!total) return null;
  return (
    <div>
      <div className="expiry-bar" role="img" aria-label="মেয়াদ অনুযায়ী স্টকের ভাগ">
        {BUCKETS.map(([k, label, color]) => Number(buckets[k].units) > 0 && (
          <span key={k} style={{ width: `${(Number(buckets[k].units) / total) * 100}%`, background: color }} title={`${label}: ${num(buckets[k].units)}`} />
        ))}
      </div>
      <div className="expiry-legend">
        {BUCKETS.map(([k, label, color]) => Number(buckets[k].units) > 0 && (
          <span key={k}><i style={{ background: color }} />{label} · {num(buckets[k].units)}</span>
        ))}
      </div>
    </div>
  );
}

export default function ExpiryPage() {
  const { active, vertical } = useBusiness();
  const { can } = usePermissions();
  const toast = useToast();
  const orgId = active?.id;
  const canChange = can("inventory:adjust");
  const { branches, branch, setBranch } = useBranch(orgId);

  const [summary, setSummary] = useState(null);
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("all");
  const [blocking, setBlocking] = useState(null); // batch being blocked
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [check, setCheck] = useState({ state: "idle", result: null });

  const load = useCallback(async () => {
    if (!orgId || !branch) return;
    try {
      const [s, r] = await Promise.all([api.expirySummary(orgId, branch), api.batches(orgId, branch)]);
      setSummary(s);
      setRows(r);
      setError("");
    } catch (e) {
      setError(explain(e));
      setRows([]);
    }
  }, [orgId, branch]);
  useEffect(() => { setSummary(null); setRows(null); setCheck({ state: "idle", result: null }); load(); }, [load]);

  const counts = useMemo(() => {
    const list = rows || [];
    return {
      all: list.length,
      expired: list.filter((b) => b.state === "expired").length,
      near_expiry: list.filter((b) => b.state === "near_expiry").length,
      no_expiry: list.filter((b) => b.state === "no_expiry").length,
      blocked: list.filter((b) => b.blocked).length,
    };
  }, [rows]);

  const shown = useMemo(() => (rows || []).filter((b) => (
    filter === "all" ? true : filter === "blocked" ? b.blocked : b.state === filter
  )), [rows, filter]);

  async function submitBlock(e) {
    e.preventDefault();
    setBusy(true);
    try {
      await api.setBatchStatus(orgId, blocking.batch_id, { status: "blocked", reason });
      toast.success(`ব্যাচ ${blocking.batch_no} বন্ধ করা হয়েছে। এটি আর বিক্রি হবে না।`);
      setBlocking(null);
      setReason("");
      load();
    } catch (err) {
      toast.error(explain(err, { 422: "বন্ধ করার কারণ লিখুন (কমপক্ষে ২ অক্ষর)।" }));
    } finally {
      setBusy(false);
    }
  }

  async function release(batch) {
    try {
      await api.setBatchStatus(orgId, batch.batch_id, { status: "active" });
      toast.success(`ব্যাচ ${batch.batch_no} আবার বিক্রির জন্য চালু হয়েছে।`);
      load();
    } catch (err) {
      toast.error(explain(err));
    }
  }

  async function runCheck() {
    setCheck({ state: "running", result: null });
    try {
      setCheck({ state: "done", result: await api.reconciliation(orgId, branch) });
    } catch (err) {
      setCheck({ state: "error", result: explain(err) });
    }
  }

  const columns = [
    { key: "product", label: "পণ্য", primary: true, render: (b) => <div><strong>{b.product_name}</strong><div className="muted" style={{ fontSize: 12.5 }}>{b.sku}</div></div> },
    { key: "batch_no", label: "ব্যাচ", render: (b) => b.batch_no },
    {
      key: "expiry", label: "মেয়াদ",
      render: (b) => (
        <div>
          <div>{b.expiry_date ? dateBn(b.expiry_date) : "—"}</div>
          <Badge tone={EXPIRY_TONE[b.state]}>{expiryLabel(b.days_to_expiry)}</Badge>
        </div>
      ),
    },
    { key: "quantity", label: "পরিমাণ", align: "right", render: (b) => num(b.quantity) },
    { key: "value", label: "মূল্য", align: "right", render: (b) => (b.value === null ? <span className="muted">ক্রয়মূল্য অজানা</span> : money(b.value)) },
    {
      key: "status", label: "অবস্থা",
      render: (b) => b.blocked
        ? <div><Badge tone="danger" icon="ban">বন্ধ</Badge><div className="muted" style={{ fontSize: 12 }}>{b.status_reason}</div></div>
        : <Badge tone={EXPIRY_TONE[b.state]}>{STATE_LABEL[b.state]}</Badge>,
    },
  ];
  if (canChange) {
    columns.push({
      key: "actions", label: "কাজ", align: "right",
      render: (b) => b.blocked
        ? <Button size="sm" variant="secondary" onClick={() => release(b)}>চালু করুন</Button>
        : <Button size="sm" variant="danger" icon="ban" onClick={() => { setBlocking(b); setReason(""); }}>বন্ধ করুন</Button>,
    });
  }

  return (
    <div className="page stack">
      <PageHeader
        title="মেয়াদ ও ব্যাচ"
        subtitle={`কোন ${vertical.item} কবে শেষ হবে, আর কত টাকা আটকে আছে। মেয়াদ পেরোনো বা বন্ধ ব্যাচ কখনো বিক্রি হয় না।`}
        actions={branches && branches.length > 1 && (
          <Field label="শাখা"><select value={branch} onChange={(e) => setBranch(e.target.value)}>
            {branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select></Field>
        )}
      />
      {error && <Notice tone="danger" action={<Button size="sm" variant="secondary" onClick={load}>আবার চেষ্টা</Button>}>{error}</Notice>}

      {summary === null ? <Skeleton lines={2} height={70} /> : (
        <>
          <div className="ui-stats">
            <Stat icon="alert" tone={Number(summary.at_risk_value) > 0 ? "danger" : "success"} label="আটকে থাকা টাকা"
                  value={money(summary.at_risk_value)}
                  sub={Number(summary.at_risk_unknown_cost_units) > 0
                    ? `+ ক্রয়মূল্য অজানা ${num(summary.at_risk_unknown_cost_units)} ইউনিট`
                    : "মেয়াদোত্তীর্ণ বা ৯০ দিনের মধ্যে শেষ হবে এমন স্টক"} />
            <Stat label="মেয়াদোত্তীর্ণ" tone={counts.expired ? "danger" : "neutral"} value={num(summary.buckets.expired.units)}
                  sub={`${num(counts.expired)}টি ব্যাচ · ${money(summary.buckets.expired.value)}`}
                  onClick={() => setFilter("expired")} active={filter === "expired"} />
            <Stat label="৩০ দিনের মধ্যে" tone={Number(summary.buckets.d30.units) ? "warn" : "neutral"} value={num(summary.buckets.d30.units)}
                  sub={money(summary.buckets.d30.value)} onClick={() => setFilter("near_expiry")} active={filter === "near_expiry"} />
            <Stat label="৩১–৯০ দিন" value={num(Number(summary.buckets.d60.units) + Number(summary.buckets.d90.units))}
                  sub={money(Number(summary.buckets.d60.value) + Number(summary.buckets.d90.value))} />
            <Stat label="বন্ধ করা ব্যাচ" tone={counts.blocked ? "warn" : "neutral"} value={num(counts.blocked)}
                  sub={`${num(summary.blocked.units)} ইউনিট`} onClick={() => setFilter("blocked")} active={filter === "blocked"} />
          </div>
          <Card><BucketBar buckets={summary.buckets} /></Card>
        </>
      )}

      <Segmented label="ব্যাচ ফিল্টার" value={filter} onChange={setFilter} options={[
        { value: "all", label: "সব", count: counts.all },
        { value: "expired", label: "মেয়াদ শেষ", count: counts.expired },
        { value: "near_expiry", label: "শীঘ্রই শেষ", count: counts.near_expiry },
        { value: "no_expiry", label: "মেয়াদ অজানা", count: counts.no_expiry },
        { value: "blocked", label: "বন্ধ", count: counts.blocked },
      ]} />

      <Card pad={false}>
        <DataTable
          columns={columns} rows={shown} rowKey="batch_id" loading={rows === null} caption="ব্যাচের তালিকা"
          empty={<EmptyState icon="clock"
                             title={rows?.length ? "এই ফিল্টারে কোনো ব্যাচ নেই" : "মেয়াদ ট্র্যাক করা কোনো স্টক নেই"}
                             hint={rows?.length ? "অন্য ফিল্টার বেছে দেখুন।" : "পণ্য পাতা থেকে কোনো পণ্যে ‘মেয়াদ ট্র্যাক’ চালু করুন, তারপর ক্রয়ের সময় ব্যাচ ও মেয়াদ দিন।"}
                             action={!rows?.length && <a className="ui-btn ui-btn--secondary" href="#/products">পণ্য পাতায় যান</a>} />}
        />
      </Card>

      <Card title="হিসাব মিলিয়ে দেখুন" subtitle="স্টকের সংখ্যা, স্টকের লেনদেনের খাতা ও ব্যাচের যোগফল — তিনটি একে অপরের সাথে মেলে কিনা।"
            actions={<Button variant="secondary" icon="refresh" loading={check.state === "running"} onClick={runCheck}>এখনই যাচাই করুন</Button>}>
        {check.state === "idle" && <p className="muted" style={{ margin: 0 }}>‘যাচাই করুন’ চাপলে এই শাখার সব পণ্য মেলানো হবে। গরমিল থাকলে এখানে দেখাবে; কিছু নিজে থেকে ঠিক করা হয় না।</p>}
        {check.state === "error" && <Notice tone="danger">{check.result}</Notice>}
        {check.state === "done" && (check.result.mismatched === 0
          ? <Notice tone="success" title="সব মিলেছে">{num(check.result.checked)}টি পণ্য যাচাই করা হয়েছে, কোনো গরমিল নেই।</Notice>
          : (
            <>
              <Notice tone="warn" title={`${num(check.result.mismatched)}টি পণ্যে গরমিল আছে`}>
                স্টকের সংখ্যা খাতার সাথে মিলছে না। সাধারণত খাতার বাইরে স্টক বদলানো হলে এমন হয়। ভুল ধরা না পড়া পর্যন্ত এই পণ্যগুলোর স্টক পুরোপুরি বিশ্বাস করবেন না।
              </Notice>
              <div style={{ marginTop: 12 }}>
                <DataTable
                  rowKey="product_id" rows={check.result.items}
                  columns={[
                    { key: "product_name", label: "পণ্য", primary: true },
                    { key: "balance", label: "স্টক", align: "right", render: (i) => num(i.balance) },
                    { key: "ledger_sum", label: "খাতার যোগফল", align: "right", render: (i) => num(i.ledger_sum) },
                    { key: "ledger_residual", label: "গরমিল (খাতা)", align: "right", render: (i) => <Badge tone={Number(i.ledger_residual) === 0 ? "success" : "danger"}>{num(i.ledger_residual)}</Badge> },
                    { key: "batch_residual", label: "গরমিল (ব্যাচ)", align: "right", render: (i) => (i.batch_residual === null ? "—" : <Badge tone={Number(i.batch_residual) === 0 ? "success" : "danger"}>{num(i.batch_residual)}</Badge>) },
                  ]}
                />
              </div>
            </>
          ))}
      </Card>

      <Modal open={Boolean(blocking)} title="ব্যাচ বন্ধ করুন" onClose={() => setBlocking(null)}
             footer={<>
               <Button variant="secondary" onClick={() => setBlocking(null)}>বাতিল</Button>
               <Button type="submit" form="block-form" variant="danger" loading={busy}>বন্ধ করুন</Button>
             </>}>
        {blocking && (
          <form id="block-form" className="ui-form" onSubmit={submitBlock}>
            <Notice tone="warn">
              {blocking.product_name} — ব্যাচ {blocking.batch_no} ({num(blocking.quantity)} ইউনিট) বন্ধ করলে এটি আর বিক্রি হবে না, যতক্ষণ না আপনি চালু করেন।
            </Notice>
            <Field label="কেন বন্ধ করছেন?" required>
              <input value={reason} onChange={(e) => setReason(e.target.value)} minLength={2} maxLength={160} autoFocus />
            </Field>
            <div className="pos-quick" style={{ marginTop: -6 }}>
              {REASONS.map((r) => <button key={r} type="button" onClick={() => setReason(r)}>{r}</button>)}
            </div>
          </form>
        )}
      </Modal>
    </div>
  );
}
