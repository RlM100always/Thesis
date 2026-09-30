import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { useBusiness } from "../BusinessContext";
import { explain } from "../errors";
import { money, todayInputValue } from "../format";
import DataTable from "../ui/DataTable";
import { Badge, Card, Field, Notice, PageHeader, Segmented, Stat } from "../ui/kit";

const TYPE_LABEL = { asset: "সম্পদ", liability: "দায়", equity: "মূলধন", revenue: "আয়", expense: "খরচ" };
// The account's own name (api/accounting.py's DEFAULT_ACCOUNTS) is English —
// bookkeeping-conventional and useful if this data is ever exported. A shop
// owner reading it on screen needs Bangla, per code (never the raw name).
const ACCOUNT_NAME_BN = {
  "1000": "নগদ", "1010": "মোবাইল ব্যাংকিং (বিকাশ/নগদ)", "1020": "ব্যাংক",
  "1100": "পাওনা (কাস্টমারের বাকি)", "1200": "স্টকের মূল্য",
  "2000": "দেনা (সাপ্লায়ারের বাকি)", "2100": "ভ্যাট বাকি", "3000": "মালিকের মূলধন",
  "4000": "বিক্রয় আয়", "4100": "বিক্রয় ফেরত",
  "5000": "বিক্রিত পণ্যের ক্রয়মূল্য", "5900": "পরিচালন খরচ",
  "5910": "স্টক গরমিলের সমন্বয়", "5950": "ক্যাশ গরমিল",
};
const accountName = (a) => ACCOUNT_NAME_BN[a.code] || a.name;
const monthAgo = () => { const d = new Date(); d.setDate(d.getDate() - 30); return d.toISOString().slice(0, 10); };

// The real double-entry books: every taka the shop posted, and where it sits.
// Read straight off the journal — never re-derived by hand, so it can't drift
// from what "Trial Balance" or "P&L" actually mean.
export default function AccountingPage() {
  const { active } = useBusiness();
  const orgId = active?.id;
  const [tab, setTab] = useState("trial");
  const [asOf, setAsOf] = useState(todayInputValue());
  const [from, setFrom] = useState(monthAgo());
  const [to, setTo] = useState(todayInputValue());
  const [trial, setTrial] = useState(null);
  const [pnl, setPnl] = useState(null);
  const [error, setError] = useState("");

  const loadTrial = useCallback(() => {
    if (!orgId) return;
    api.trialBalance(orgId, asOf).then(setTrial).catch((e) => setError(explain(e)));
  }, [orgId, asOf]);
  const loadPnl = useCallback(() => {
    if (!orgId) return;
    api.profitAndLoss(orgId, from, to).then(setPnl).catch((e) => setError(explain(e)));
  }, [orgId, from, to]);
  useEffect(() => { if (tab === "trial") loadTrial(); else loadPnl(); }, [tab, loadTrial, loadPnl]);

  return (
    <div className="page stack">
      <PageHeader title="আর্থিক প্রতিবেদন" subtitle="প্রতিটি সংখ্যা দোকানের নিজের জার্নাল থেকে — হিসাব করে আলাদা বের করা নয়।" />
      {error && <Notice tone="danger">{error}</Notice>}

      <div className="toolbar">
        <Segmented label="প্রতিবেদন" value={tab} onChange={setTab} options={[
          { value: "trial", label: "ট্রায়াল ব্যালেন্স" },
          { value: "pnl", label: "লাভ-ক্ষতি (P&L)" },
        ]} />
        {tab === "trial"
          ? <Field label="তারিখ পর্যন্ত"><input type="date" value={asOf} onChange={(e) => setAsOf(e.target.value)} max={todayInputValue()} /></Field>
          : <>
              <Field label="থেকে"><input type="date" value={from} max={to} onChange={(e) => setFrom(e.target.value)} /></Field>
              <Field label="পর্যন্ত"><input type="date" value={to} min={from} max={todayInputValue()} onChange={(e) => setTo(e.target.value)} /></Field>
            </>}
      </div>

      {tab === "trial" && trial && (
        <>
          <Notice tone={trial.balanced ? "success" : "danger"}>
            মোট ডেবিট {money(trial.total_debit)} = মোট ক্রেডিট {money(trial.total_credit)}
            {trial.balanced ? " — হিসাব মিলেছে।" : " — হিসাব মেলেনি, এটি একটি বাগ, দয়া করে জানান।"}
          </Notice>
          <Card pad={false}>
            <DataTable rowKey="code" rows={trial.accounts.filter((a) => Number(a.debit) || Number(a.credit))} caption="ট্রায়াল ব্যালেন্স"
                       columns={[
                         { key: "name", label: "হিসাব", primary: true, render: (a) => <div><strong>{accountName(a)}</strong><div className="muted" style={{ fontSize: 12.5 }}>{a.code} · {TYPE_LABEL[a.type]}</div></div> },
                         { key: "debit", label: "ডেবিট", align: "right", render: (a) => money(a.debit) },
                         { key: "credit", label: "ক্রেডিট", align: "right", render: (a) => money(a.credit) },
                         { key: "balance", label: "উদ্বৃত্ত", align: "right", render: (a) => (
                           <span>{money(a.balance)}{a.balance < 0 && <> <Badge tone="warn">বিপরীত</Badge></>}</span>) },
                       ]} />
          </Card>
        </>
      )}

      {tab === "pnl" && pnl && (
        <>
          <div className="ui-stats">
            <Stat label="মোট আয়" value={money(pnl.revenue)} icon="trend" />
            <Stat label="বিক্রিত পণ্যের ক্রয়মূল্য (COGS)" value={money(pnl.cogs)} icon="box" />
            <Stat label="গ্রস প্রফিট" value={money(pnl.gross_profit)} tone={pnl.gross_profit >= 0 ? "success" : "danger"} icon="wallet" />
            <Stat label="পরিচালন ব্যয়" value={money(pnl.operating_expenses)} icon="card" />
            <Stat label="নিট মুনাফা" value={money(pnl.net_profit)} tone={pnl.net_profit >= 0 ? "success" : "danger"} icon="check" />
          </div>
          <Card title="আয়ের উৎস">
            <DataTable rowKey="code" rows={pnl.revenue_lines} caption="আয়ের হিসাব"
                       columns={[{ key: "name", label: "হিসাব", primary: true, render: accountName }, { key: "amount", label: "পরিমাণ", align: "right", render: (r) => money(r.amount) }]} />
          </Card>
          <Card title="খরচের খাত">
            <DataTable rowKey="code" rows={pnl.expense_lines} caption="খরচের হিসাব"
                       columns={[{ key: "name", label: "হিসাব", primary: true, render: accountName }, { key: "amount", label: "পরিমাণ", align: "right", render: (r) => money(r.amount) }]} />
          </Card>
        </>
      )}
    </div>
  );
}
