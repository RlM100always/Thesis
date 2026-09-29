import { useState } from "react";
import { api } from "../api";
import { useBusiness } from "../BusinessContext";
import { explain } from "../errors";
import { dateBn, money, num, todayInputValue } from "../format";
import { Button, Card, Field, Notice, PageHeader } from "../ui/kit";
import { useToast } from "../ui/Toast";
import useBranch from "../useBranch";

// Excel opens a CSV correctly only with the byte-order mark; Bangla text needs it.
function downloadCsv(filename, header, rows) {
  const esc = (v) => `"${String(v ?? "").replaceAll('"', '""')}"`;
  const body = [header, ...rows].map((r) => r.map(esc).join(",")).join("\r\n");
  const url = URL.createObjectURL(new Blob(["﻿", body], { type: "text/csv;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
const stamp = () => todayInputValue();

export default function ReportsPage() {
  const { active, features } = useBusiness();
  const toast = useToast();
  const orgId = active?.id;
  const { branch } = useBranch(orgId);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [busy, setBusy] = useState("");
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState("");

  async function run(key, job) {
    setBusy(key);
    setError("");
    try {
      await job();
    } catch (e) {
      setError(explain(e, { 403: "এই রিপোর্ট দেখার অনুমতি আপনার নেই।" }));
    } finally {
      setBusy("");
    }
  }
  const done = (name, n) => toast.success(`${name}: ${num(n)}টি সারি নামানো হয়েছে।`);

  const REPORTS = [
    {
      key: "sales", title: "বিক্রির রিপোর্ট", note: "প্রতিটি চালানের প্রতিটি পণ্য। ওপরের তারিখ ফিল্টার কাজ করে।", needsDates: true,
      job: async () => {
        const sales = await api.salesSearch(orgId, { from, to, limit: 500 });
        const rows = sales.flatMap((s) => s.items.map((i) => [s.invoice_number, s.sold_at, i.sku, i.product_name, i.quantity, i.unit_price, i.line_total, s.total, s.paid, s.due]));
        downloadCsv(`sales-${stamp()}.csv`, ["চালান", "সময়", "SKU", "পণ্য", "পরিমাণ", "একক দাম", "লাইন মোট", "চালান মোট", "পরিশোধ", "বাকি"], rows);
        done("বিক্রি", rows.length);
      },
    },
    {
      key: "expenses", title: "খরচের রিপোর্ট", note: "সব লেখা খরচ ধরন ও মাধ্যমসহ।",
      job: async () => {
        const list = await api.expenses(orgId);
        downloadCsv(`expenses-${stamp()}.csv`, ["তারিখ", "ধরন", "মাধ্যম", "টাকা", "নোট"], list.map((e) => [e.incurred_at, e.category, e.payment_method, e.amount, e.note]));
        done("খরচ", list.length);
      },
    },
    {
      key: "stock", title: "স্টকের রিপোর্ট", note: "এই মুহূর্তে কোন পণ্য কতটা আছে (নির্বাচিত শাখা)।",
      job: async () => {
        const inv = await api.inventoryApp(orgId, branch);
        downloadCsv(`stock-${stamp()}.csv`, ["SKU", "পণ্য", "স্টক", "পুনঃঅর্ডার সীমা", "অবস্থা"], inv.map((r) => [r.sku, r.product_name, r.quantity, r.reorder_level, Number(r.quantity) <= 0 ? "শেষ" : r.low_stock ? "কম" : "পর্যাপ্ত"]));
        done("স্টক", inv.length);
      },
    },
    {
      key: "products", title: "পণ্যের তালিকা", note: "দাম, ক্রয়মূল্য ও লাভের হারসহ।",
      job: async () => {
        const list = await api.productsApp(orgId);
        downloadCsv(`products-${stamp()}.csv`, ["SKU", "নাম", "ক্যাটাগরি", "একক", "বিক্রয়মূল্য", "ক্রয়মূল্য", "লাভ %", "মেয়াদ ট্র্যাক"],
          list.map((p) => [p.sku, p.name, p.category, p.unit, p.selling_price, p.cost_price, Number(p.cost_price) > 0 ? Math.round(((p.selling_price - p.cost_price) / p.selling_price) * 100) : "অজানা", p.track_expiry ? "হ্যাঁ" : "না"]));
        done("পণ্য", list.length);
      },
    },
    {
      key: "baki", title: "বাকির রিপোর্ট", note: "কার কাছে কত পাবেন, কাকে কত দেবেন।",
      job: async () => {
        const [rc, pay, customers, suppliers] = await Promise.all([api.ledger(orgId, "receivable"), api.ledger(orgId, "payable"), api.customersApp(orgId), api.suppliers(orgId)]);
        const cn = Object.fromEntries(customers.map((c) => [c.id, c.display_name || c.code]));
        const sn = Object.fromEntries(suppliers.map((s) => [s.id, s.name]));
        const rows = [
          ...rc.filter((r) => Number(r.balance) > 0).map((r) => ["কাস্টমার (আপনি পাবেন)", cn[r.party_id] || "—", r.balance]),
          ...pay.filter((r) => Number(r.balance) > 0).map((r) => ["সাপ্লায়ার (আপনি দেবেন)", sn[r.party_id] || "—", r.balance]),
        ];
        downloadCsv(`baki-${stamp()}.csv`, ["ধরন", "নাম", "টাকা"], rows);
        done("বাকি", rows.length);
      },
    },
    {
      key: "purchases", title: "ক্রয়ের রিপোর্ট", note: "সব ক্রয় অর্ডার ও কতটা রিসিভ হয়েছে।",
      job: async () => {
        const list = await api.purchases(orgId);
        const rows = list.flatMap((o) => o.items.map((i) => [o.order_number, o.ordered_at, o.supplier_name, o.status, i.sku, i.product_name, i.quantity, i.received_quantity, i.unit_cost]));
        downloadCsv(`purchases-${stamp()}.csv`, ["অর্ডার", "তারিখ", "সাপ্লায়ার", "অবস্থা", "SKU", "পণ্য", "অর্ডার", "রিসিভ", "ক্রয়মূল্য"], rows);
        done("ক্রয়", rows.length);
      },
    },
    ...(features.expiry ? [{
      key: "batches", title: "মেয়াদ ও ব্যাচের রিপোর্ট", note: "প্রতিটি ব্যাচ, মেয়াদ ও আটকে থাকা টাকা।",
      job: async () => {
        const list = await api.batches(orgId, branch);
        downloadCsv(`batches-${stamp()}.csv`, ["SKU", "পণ্য", "ব্যাচ", "মেয়াদ", "বাকি দিন", "পরিমাণ", "মূল্য", "অবস্থা"],
          list.map((b) => [b.sku, b.product_name, b.batch_no, b.expiry_date, b.days_to_expiry, b.quantity, b.value ?? "ক্রয়মূল্য অজানা", b.blocked ? "বন্ধ" : b.state]));
        done("ব্যাচ", list.length);
      },
    }] : []),
  ];

  return (
    <div className="page stack">
      <PageHeader title="রিপোর্ট" subtitle="যেকোনো হিসাব Excel-এ নামিয়ে নিন, অথবা মাসের সারাংশ প্রিন্ট করুন।" />
      {error && <Notice tone="danger">{error}</Notice>}

      <Card title="মাসের সারাংশ" subtitle="গত ৩০ দিন — প্রিন্ট করে হিসাবরক্ষক বা ব্যাংকে দেখাতে পারেন।"
            actions={<Button variant="secondary" loading={busy === "summary"} onClick={() => run("summary", async () => setSummary(await api.dashboardApp(orgId)))}>সারাংশ তৈরি করুন</Button>}>
        {summary ? (
          <div className="receipt-print">
            <div className="summary">
              <div><span>নিট বিক্রি</span><strong>{money(summary.net_sales)}</strong></div>
              <div><span>চালান</span><strong>{num(summary.orders)}টি</strong></div>
              <div><span>মুনাফা (ক্রয়মূল্য জানা বিক্রিতে)</span><strong>{money(summary.gross_profit_known)}</strong></div>
              <div><span>ক্রয়মূল্য জানা বিক্রি</span><strong>{summary.cost_coverage === null ? "—" : `${num(Math.round(summary.cost_coverage * 100))}%`}</strong></div>
              <div><span>খরচ</span><strong>{money(summary.expenses)}</strong></div>
              <div><span>ফেরত</span><strong>{money(summary.returns)}</strong></div>
              <div><span>বাকি পাবেন</span><strong>{money(summary.receivable)}</strong></div>
              <div><span>বাকি দেবেন</span><strong>{money(summary.payable)}</strong></div>
            </div>
            <p className="muted" style={{ marginTop: 12 }}>{active.name} · {dateBn(new Date().toISOString())} পর্যন্ত গত {num(summary.period_days)} দিনের হিসাব।</p>
            <Button variant="secondary" icon="printer" onClick={() => window.print()}>প্রিন্ট করুন</Button>
          </div>
        ) : <p className="muted" style={{ margin: 0 }}>‘সারাংশ তৈরি করুন’ চাপলে এখানে দেখাবে।</p>}
      </Card>

      <div className="toolbar" style={{ alignItems: "flex-end" }}>
        <Field label="বিক্রির রিপোর্টের জন্য: থেকে"><input type="date" value={from} max={to || todayInputValue()} onChange={(e) => setFrom(e.target.value)} /></Field>
        <Field label="পর্যন্ত"><input type="date" value={to} min={from} max={todayInputValue()} onChange={(e) => setTo(e.target.value)} /></Field>
      </div>

      <div className="report-grid">
        {REPORTS.map((r) => (
          <Card key={r.key} title={r.title} subtitle={r.note}
                actions={<Button size="sm" icon="download" loading={busy === r.key} onClick={() => run(r.key, r.job)}>Excel (CSV)</Button>} />
        ))}
      </div>
    </div>
  );
}
