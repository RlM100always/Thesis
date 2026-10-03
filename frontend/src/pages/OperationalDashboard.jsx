import { useEffect, useRef, useState } from "react";
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
      <AdminInbox />
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

function AdminInbox() {
  const [open, setOpen] = useState(false);
  const [unread, setUnread] = useState(0);
  const [thread, setThread] = useState(null);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const bottomRef = useRef(null);

  // Poll unread count every 30s
  useEffect(() => {
    let alive = true;
    async function poll() {
      try { const d = await api.getAdminMessagesUnread(); if (alive) setUnread(d.unread || 0); }
      catch (_) {}
    }
    poll();
    const t = setInterval(poll, 30000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  async function openInbox() {
    setOpen(true);
    try {
      const d = await api.getAdminMessages();
      setThread(d);
      setUnread(0);
    } catch (_) {}
  }

  useEffect(() => { if (open) bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [open, thread?.messages?.length]);

  async function send() {
    if (!text.trim()) return;
    setSending(true);
    try {
      const msg = await api.replyToAdmin(text.trim());
      setThread(prev => prev ? { ...prev, messages: [...(prev.messages || []), msg] } : prev);
      setText("");
    } catch (_) {}
    setSending(false);
  }

  return (
    <>
      <button
        onClick={openInbox}
        style={{
          position: "fixed", bottom: 24, right: 24, zIndex: 1000,
          background: "var(--green, #0a8754)", color: "#fff",
          border: "none", borderRadius: 50, width: 52, height: 52,
          display: "flex", alignItems: "center", justifyContent: "center",
          cursor: "pointer", boxShadow: "0 4px 16px rgba(0,0,0,0.18)", fontSize: 22,
        }}
        title="Admin বার্তা"
      >
        💬
        {unread > 0 && (
          <span style={{
            position: "absolute", top: 2, right: 2, background: "#e63946",
            borderRadius: 99, minWidth: 18, height: 18, fontSize: 11,
            display: "flex", alignItems: "center", justifyContent: "center",
            fontWeight: 700, color: "#fff", padding: "0 4px",
          }}>{unread}</span>
        )}
      </button>

      {open && (
        <div style={{
          position: "fixed", bottom: 88, right: 24, zIndex: 1001,
          width: 340, maxHeight: 480, background: "var(--bg-card, #fff)",
          borderRadius: 14, boxShadow: "0 8px 32px rgba(0,0,0,0.18)",
          display: "flex", flexDirection: "column", border: "1px solid var(--border)",
        }}>
          <div style={{ padding: "10px 16px", borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontWeight: 700, fontSize: 14 }}>Admin বার্তা</span>
            <button onClick={() => setOpen(false)} style={{ background: "none", border: "none", cursor: "pointer", fontSize: 18, lineHeight: 1 }}>×</button>
          </div>
          <div style={{ flex: 1, overflowY: "auto", padding: 12, display: "flex", flexDirection: "column", gap: 8 }}>
            {!thread ? <div style={{ color: "var(--muted)", fontSize: 13, textAlign: "center", padding: 16 }}>লোড হচ্ছে…</div>
              : thread.messages?.length === 0 ? <div style={{ color: "var(--muted)", fontSize: 13, textAlign: "center", padding: 16 }}>কোনো বার্তা নেই</div>
              : thread.messages.map(m => (
                <div key={m.id} style={{ alignSelf: m.sender_type === "business" ? "flex-end" : "flex-start", maxWidth: "80%" }}>
                  <div style={{
                    background: m.sender_type === "business" ? "var(--green, #0a8754)" : "var(--bg-subtle, #f1f5f9)",
                    color: m.sender_type === "business" ? "#fff" : "inherit",
                    borderRadius: 10, padding: "7px 12px", fontSize: 13, lineHeight: 1.5,
                  }}>{m.content}</div>
                  <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 2, textAlign: m.sender_type === "business" ? "right" : "left" }}>
                    {m.sender_type === "admin" ? "Platform Admin" : "আপনি"} · {new Date(m.created_at).toLocaleTimeString("bn-BD", { hour: "2-digit", minute: "2-digit" })}
                  </div>
                </div>
              ))
            }
            <div ref={bottomRef} />
          </div>
          <div style={{ padding: "8px 10px", borderTop: "1px solid var(--border)", display: "flex", gap: 6 }}>
            <textarea
              style={{ flex: 1, resize: "none", border: "1px solid var(--border)", borderRadius: 8, padding: "6px 10px", fontSize: 13, fontFamily: "inherit" }}
              rows={2}
              value={text}
              onChange={e => setText(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
              placeholder="উত্তর দিন…"
            />
            <button
              onClick={send}
              disabled={sending || !text.trim()}
              style={{ background: "var(--green, #0a8754)", color: "#fff", border: "none", borderRadius: 8, padding: "0 14px", cursor: "pointer", fontSize: 13 }}
            >পাঠান</button>
          </div>
        </div>
      )}
    </>
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
