import { useEffect, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, formatBDT } from "../api";
import { useBusiness } from "../BusinessContext";
import { Loading } from "../useApi";

export default function OperationalDashboard() {
  const { active } = useBusiness();
  const [data, setData] = useState(null);
  const [branches, setBranches] = useState([]);
  const [branch, setBranch] = useState("");
  const [error, setError] = useState("");
  const activeId = active?.id;

  useEffect(() => {
    if (!activeId) return;
    api.branches(activeId).then(setBranches).catch((e) => setError(e.message));
  }, [activeId]);

  useEffect(() => {
    if (!activeId) return;
    setData(null);
    api.dashboardApp(activeId, branch).then(setData).catch((e) => setError(e.message));
  }, [activeId, branch]);

  if (!active) return <EmptyBusiness />;

  return (
    <div className="page">
      <header className="page-head row">
        <div>
          <h2>ব্যবসার ড্যাশবোর্ড</h2>
          <p className="subtitle">গত ৩০ দিনের প্রকৃত হিসাব</p>
        </div>
        <label>
          শাখা
          <select value={branch} onChange={(e) => setBranch(e.target.value)}>
            <option value="">সব শাখা</option>
            {branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select>
        </label>
      </header>

      {error && <div className="error-box">{error}</div>}

      {!data ? (
        <Loading what="ড্যাশবোর্ড" />
      ) : (
        <>
          <div className="kpi-grid">
            <Metric label="নিট বিক্রি" value={formatBDT(data.net_sales)} sub={`${data.orders}টি চালান`} />
            <Metric label="মোট মুনাফা" value={formatBDT(data.gross_profit_before_expenses)} />
            <Metric
              label="খরচের পর ফলাফল"
              value={formatBDT(data.estimated_operating_result)}
              danger={data.estimated_operating_result < 0}
            />
            <Metric label="বাকি পাবেন" value={formatBDT(data.receivable)} />
            <Metric label="বাকি দেবেন" value={formatBDT(data.payable)} danger={data.payable > 0} />
            <Metric
              label="কম স্টক"
              value={`${data.low_stock_products} / ${data.product_count}`}
              danger={data.low_stock_products > 0}
            />
          </div>

          <section className="card chart-card">
            <h3>দৈনিক বিক্রি</h3>
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={data.daily_sales}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" tickFormatter={(x) => x.slice(5)} />
                <YAxis tickFormatter={(x) => `৳${Math.round(x / 1000)}k`} />
                <Tooltip formatter={(v) => formatBDT(Number(v))} />
                <Line type="monotone" dataKey="sales" stroke="#0a8754" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </section>

          <div className="grid-2">
            <section className="card">
              <h3>কাজের সারাংশ</h3>
              <p>গড় চালান: <strong>{formatBDT(data.average_order_value)}</strong></p>
              <p>ফেরত: <strong>{formatBDT(data.returns)}</strong></p>
              <p>খরচ: <strong>{formatBDT(data.expenses)}</strong></p>
            </section>
            <section className="card">
              <h3>ব্যবসার পরিধি</h3>
              <p>{data.customer_count} কাস্টমার &middot; {data.supplier_count} সাপ্লায়ার</p>
              <p>ক্রয়মূল্যে বর্তমান স্টকের মূল্য: <strong>{formatBDT(data.stock_value_at_cost)}</strong></p>
              <a className="btn-primary" href="#/strategy">আজকের করণীয় দেখুন</a>
            </section>
          </div>
        </>
      )}
    </div>
  );
}

function Metric({ label, value, sub, danger }) {
  return (
    <div className={`kpi ${danger ? "danger" : ""}`}>
      <span className="label">{label}</span>
      <strong className="value">{value}</strong>
      {sub && <span className="sub">{sub}</span>}
    </div>
  );
}

function EmptyBusiness() {
  return (
    <div className="page">
      <h2>আপনার ব্যবসা সেটআপ করুন</h2>
      <p>পণ্য, স্টক ও বিক্রি যোগ করার আগে একটি ব্যবসা তৈরি করা দরকার।</p>
      <a className="btn-primary" href="#/setup">সেটআপে যান</a>
    </div>
  );
}
