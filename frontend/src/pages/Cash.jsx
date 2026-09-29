import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { useBusiness } from "../BusinessContext";
import { explain } from "../errors";
import { dateBn, money, num, todayInputValue } from "../format";
import { usePermissions } from "../PermissionContext";
import DataTable from "../ui/DataTable";
import { Badge, Button, Card, EmptyState, Field, Notice, PageHeader, Skeleton } from "../ui/kit";
import { useToast } from "../ui/Toast";
import useBranch from "../useBranch";

const LINES = [
  ["cash_sales", "নগদ বিক্রি", "plus"], ["baki_collected", "বাকি আদায় (নগদ)", "plus"],
  ["expenses", "নগদ খরচ", "minus"], ["supplier_payments", "সাপ্লায়ারকে নগদ পেমেন্ট", "minus"], ["refunds", "নগদ ফেরত দেওয়া", "minus"],
];

// The end-of-day habit that catches mistakes and theft early: what the books say
// should be in the drawer, against what is actually there.
export default function CashPage() {
  const { active } = useBusiness();
  const { can } = usePermissions();
  const toast = useToast();
  const orgId = active?.id;
  const canClose = can("cash:close");
  const { branches, branch, setBranch } = useBranch(orgId);

  const [day, setDay] = useState(todayInputValue());
  const [data, setData] = useState(null);
  const [history, setHistory] = useState(null);
  const [opening, setOpening] = useState("");
  const [counted, setCounted] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!orgId || !branch) return;
    setData(null);
    try {
      const d = await api.cashDay(orgId, branch, day);
      setData(d);
      setOpening(String(d.opening_cash));
      setCounted("");
      setNote("");
      setHistory(await api.cashCloses(orgId, branch));
      setError("");
    } catch (e) {
      setError(explain(e));
      setData({ error: true });
    }
  }, [orgId, branch, day]);
  useEffect(() => { load(); }, [load]);

  const expected = data && !data.error ? Number(data.expected_cash) - Number(data.opening_cash) + Number(opening || 0) : 0;
  const variance = counted === "" ? null : Number(counted) - expected;

  async function close(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.cashClose(orgId, { branch_id: branch, business_date: day, opening_cash: Number(opening || 0).toFixed(2), counted_cash: Number(counted).toFixed(2), note: note || null });
      toast.success("দিনের হিসাব বন্ধ হয়েছে।");
      load();
    } catch (err) {
      setError(explain(err, {
        409: "এই দিনের হিসাব আগেই বন্ধ করা হয়েছে।",
        422: variance !== 0 ? "গোনা টাকা হিসাবের সাথে না মিললে কারণ লিখতে হবে।" : "তারিখ বা টাকার পরিমাণ ঠিক নেই।",
      }));
    } finally {
      setBusy(false);
    }
  }

  const closed = data?.closed;

  return (
    <div className="page stack">
      <PageHeader
        title="ক্যাশ মেলান"
        subtitle="দিন শেষে ড্রয়ারে কত টাকা থাকার কথা আর আসলে কত আছে — গরমিল হলে আজই ধরা পড়বে।"
        actions={<>
          {branches && branches.length > 1 && <Field label="শাখা"><select value={branch} onChange={(e) => setBranch(e.target.value)}>{branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}</select></Field>}
          <Field label="তারিখ"><input type="date" value={day} max={todayInputValue()} onChange={(e) => setDay(e.target.value || todayInputValue())} /></Field>
        </>}
      />
      {error && <Notice tone="danger" action={<Button size="sm" variant="secondary" onClick={load}>আবার চেষ্টা</Button>}>{error}</Notice>}

      {!data ? <Skeleton lines={5} height={22} /> : data.error ? null : (
        <div className="cash-grid">
          <Card title={`${dateBn(day)}-এর হিসাব`} subtitle="শুধু নগদ টাকা ধরা হয়েছে। বিকাশ, নগদ, কার্ড ড্রয়ারে থাকে না।">
            <ul className="cash-lines">
              <li><span>দিনের শুরুতে ড্রয়ারে ছিল</span><strong>{closed ? money(data.opening_cash) : (
                <input type="number" min="0" step="0.01" value={opening} onChange={(e) => setOpening(e.target.value)} style={{ width: 130, minHeight: 36, textAlign: "right" }} aria-label="শুরুর নগদ" />
              )}</strong></li>
              {LINES.map(([key, label, sign]) => (
                <li key={key}><span>{label}</span><strong className={Number(data[key]) ? sign : ""}>{sign === "plus" ? "+" : "−"} {money(data[key])}</strong></li>
              ))}
              <li className="total"><span>ড্রয়ারে থাকার কথা</span><span>{money(closed ? data.expected_cash : expected)}</span></li>
            </ul>
          </Card>

          <Card title={closed ? "বন্ধ করা হয়েছে" : "গুনে দেখুন"}>
            {closed ? (
              <div className="ui-form">
                <div className="summary"><div><span>গোনা টাকা</span><strong>{money(closed.counted_cash)}</strong></div></div>
                <div className={`variance ${Number(closed.variance) === 0 ? "ok" : Number(closed.variance) < 0 ? "short" : "over"}`}>
                  <span>{Number(closed.variance) === 0 ? "ঠিকঠাক মিলেছে" : Number(closed.variance) < 0 ? "কম আছে" : "বেশি আছে"}</span>
                  <span>{money(Math.abs(Number(closed.variance)))}</span>
                </div>
                {closed.note && <p className="muted" style={{ margin: 0 }}>কারণ: {closed.note}</p>}
              </div>
            ) : !canClose ? (
              <Notice tone="info">দিনের হিসাব বন্ধ করার অনুমতি আপনার নেই।</Notice>
            ) : (
              <form className="ui-form" onSubmit={close}>
                <Field label="ড্রয়ারে এখন কত টাকা আছে?" required>
                  <input type="number" min="0" step="0.01" inputMode="decimal" value={counted} onChange={(e) => setCounted(e.target.value)} autoFocus />
                </Field>
                {variance !== null && (
                  <div className={`variance ${variance === 0 ? "ok" : variance < 0 ? "short" : "over"}`}>
                    <span>{variance === 0 ? "ঠিকঠাক মিলেছে" : variance < 0 ? "কম আছে" : "বেশি আছে"}</span>
                    <span>{variance === 0 ? "✓" : money(Math.abs(variance))}</span>
                  </div>
                )}
                {variance !== null && variance !== 0 && (
                  <Field label="গরমিলের কারণ" required hint="যেমন: খুচরা দিতে নিজের পকেট থেকে দিয়েছি"><input value={note} onChange={(e) => setNote(e.target.value)} maxLength={300} /></Field>
                )}
                <Button type="submit" loading={busy} disabled={counted === "" || (variance !== 0 && !note.trim())} icon="check">দিনের হিসাব বন্ধ করুন</Button>
              </form>
            )}
          </Card>
        </div>
      )}

      <Card pad={false} title="আগের হিসাব">
        <DataTable rowKey="id" loading={history === null} rows={history || []} caption="ক্যাশ মেলানোর ইতিহাস"
                   columns={[
                     { key: "date", label: "তারিখ", primary: true, render: (r) => dateBn(r.date) },
                     { key: "expected_cash", label: "থাকার কথা", align: "right", render: (r) => money(r.expected_cash) },
                     { key: "counted_cash", label: "গোনা", align: "right", render: (r) => money(r.counted_cash) },
                     { key: "variance", label: "গরমিল", align: "right", render: (r) => (Number(r.variance) === 0 ? <Badge tone="success" icon="check">মিলেছে</Badge> : <Badge tone={Number(r.variance) < 0 ? "danger" : "warn"}>{Number(r.variance) < 0 ? "−" : "+"}{money(Math.abs(Number(r.variance)))}</Badge>) },
                     { key: "note", label: "কারণ", render: (r) => r.note || "—" },
                   ]}
                   empty={<EmptyState icon="wallet" title="এখনো কোনো দিন বন্ধ করা হয়নি" hint={`প্রতিদিন দোকান বন্ধের সময় ${num(2)} মিনিটে হিসাব মিলিয়ে নিন।`} />} />
      </Card>
    </div>
  );
}
