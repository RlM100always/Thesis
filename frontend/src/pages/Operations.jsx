import { useCallback, useEffect, useMemo, useState } from "react";
import { api, formatBDT } from "../api";
import { useBusiness } from "../BusinessContext";
import { CategorySelect } from "../components/CategorySelect";
import { useConfirm } from "../components/ConfirmDialog";
import { FeedbackBanner, useFeedback } from "../components/FeedbackBanner";

function Shell({ title, children }) {
  const { active } = useBusiness();
  if (!active) {
    return (
      <div className="page">
        <h2>আগে ব্যবসা সেটআপ করুন</h2>
        <a className="btn-primary" href="#/setup">সেটআপে যান</a>
      </div>
    );
  }
  return (
    <div className="page">
      <header className="page-head">
        <h2>{title}</h2>
        <p className="subtitle">{active.name}</p>
      </header>
      {children}
    </div>
  );
}

export function ProductsPage() {
  const { active } = useBusiness();
  const id = active?.id;
  const [rows, setRows] = useState([]);
  const [feedback, showFeedback] = useFeedback();
  const [form, setForm] = useState({
    sku: "", name: "", category: "", unit: "pcs",
    selling_price: "", cost_price: "0", reorder_level: "0",
  });

  const load = useCallback(
    () => id && api.productsApp(id).then(setRows).catch((e) => showFeedback("error", e.message)),
    [id, showFeedback],
  );
  useEffect(() => { load(); }, [load]);

  const submit = async (e) => {
    e.preventDefault();
    try {
      await api.createProduct(id, form);
      setForm({ ...form, sku: "", name: "", selling_price: "" });
      load();
      showFeedback("success", "পণ্য যোগ হয়েছে।");
    } catch (x) {
      showFeedback("error", x.message);
    }
  };

  return (
    <Shell title="পণ্য ও মূল্য">
      <FeedbackBanner feedback={feedback} />
      <form className="card inline-form" onSubmit={submit}>
        <input placeholder="SKU" value={form.sku} onChange={(e) => setForm({ ...form, sku: e.target.value })} required />
        <input placeholder="পণ্যের নাম" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
        <input placeholder="ক্যাটাগরি" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} />
        <input type="number" min="0" step="0.01" placeholder="বিক্রয়মূল্য" value={form.selling_price} onChange={(e) => setForm({ ...form, selling_price: e.target.value })} required />
        <input type="number" min="0" step="0.01" placeholder="ক্রয়মূল্য" value={form.cost_price} onChange={(e) => setForm({ ...form, cost_price: e.target.value })} />
        <input type="number" min="0" step="0.001" placeholder="পুনঃঅর্ডার সীমা" value={form.reorder_level} onChange={(e) => setForm({ ...form, reorder_level: e.target.value })} />
        <button className="btn-primary">যোগ করুন</button>
      </form>
      <div className="card table-wrap">
        <table>
          <thead>
            <tr>
              <th>SKU</th><th>পণ্য</th><th>ক্যাটাগরি</th>
              <th className="num">বিক্রয়মূল্য</th><th className="num">ক্রয়মূল্য</th><th className="num">পুনঃঅর্ডার</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>{r.sku}</td>
                <td>{r.name}</td>
                <td>{r.category || "—"}</td>
                <td className="num">{formatBDT(Number(r.selling_price))}</td>
                <td className="num">{formatBDT(Number(r.cost_price))}</td>
                <td className="num">{r.reorder_level}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length && <p className="hint">এখনো কোনো পণ্য যোগ হয়নি।</p>}
      </div>
    </Shell>
  );
}

export function InventoryPage() {
  const { active } = useBusiness();
  const id = active?.id;
  const [branches, setBranches] = useState([]);
  const [branch, setBranch] = useState("");
  const [rows, setRows] = useState([]);
  const [delta, setDelta] = useState({ product_id: "", quantity_delta: "", reason: "প্রারম্ভিক স্টক" });
  const [feedback, showFeedback] = useFeedback();
  const confirm = useConfirm();

  useEffect(() => {
    if (id) api.branches(id).then((x) => { setBranches(x); setBranch((b) => b || x[0]?.id || ""); });
  }, [id]);

  const load = useCallback(
    () => branch && id && api.inventoryApp(id, branch).then(setRows).catch((e) => showFeedback("error", e.message)),
    [branch, id, showFeedback],
  );
  useEffect(() => { load(); }, [load]);

  const submit = async (e) => {
    e.preventDefault();
    const product = rows.find((r) => r.product_id === delta.product_id);
    const qty = Number(delta.quantity_delta);
    if (product && qty < 0) {
      const ok = await confirm(
        `${product.product_name}-এর স্টক থেকে ${Math.abs(qty)} ইউনিট বাদ যাবে। নিশ্চিত?`,
      );
      if (!ok) return;
    }
    try {
      await api.adjustStock(id, { branch_id: branch, ...delta });
      load();
      showFeedback("success", "স্টক আপডেট হয়েছে।");
    } catch (x) {
      showFeedback("error", x.message);
    }
  };

  return (
    <Shell title="স্টক">
      {confirm.dialog}
      <FeedbackBanner feedback={feedback} />
      <div className="card">
        <label>
          শাখা
          <select value={branch} onChange={(e) => setBranch(e.target.value)}>
            {branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select>
        </label>
      </div>
      <form className="card inline-form" onSubmit={submit}>
        <select value={delta.product_id} onChange={(e) => setDelta({ ...delta, product_id: e.target.value })} required>
          <option value="">পণ্য নির্বাচন</option>
          {rows.map((r) => <option key={r.product_id} value={r.product_id}>{r.product_name}</option>)}
        </select>
        <input type="number" step="0.001" placeholder="পরিমাণ (+/-)" value={delta.quantity_delta} onChange={(e) => setDelta({ ...delta, quantity_delta: e.target.value })} required />
        <input value={delta.reason} onChange={(e) => setDelta({ ...delta, reason: e.target.value })} />
        <button className="btn-primary">স্টক সমন্বয়</button>
      </form>
      <div className="card table-wrap">
        <table>
          <thead><tr><th>পণ্য</th><th className="num">স্টক</th><th>অবস্থা</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.product_id}>
                <td>{r.product_name}</td>
                <td className="num">{r.quantity}</td>
                <td><span className={`pill ${r.low_stock ? "danger" : "ok"}`}>{r.low_stock ? "কম" : "পর্যাপ্ত"}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length && <p className="hint">এই শাখায় এখনো কোনো পণ্য নেই।</p>}
      </div>
    </Shell>
  );
}

export function SalesPage() {
  const { active } = useBusiness();
  const id = active?.id;
  const [branches, setBranches] = useState([]);
  const [products, setProducts] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [history, setHistory] = useState([]);
  const [feedback, showFeedback] = useFeedback();
  const [form, setForm] = useState({
    branch_id: "", product_id: "", customer_id: "", quantity: "1", method: "cash", paid_amount: "",
  });

  const load = useCallback(() => {
    if (!id) return;
    Promise.all([api.branches(id), api.productsApp(id), api.customersApp(id), api.salesApp(id)])
      .then(([b, p, c, h]) => {
        setBranches(b); setProducts(p); setCustomers(c); setHistory(h);
        setForm((f) => ({ ...f, branch_id: f.branch_id || b[0]?.id || "", product_id: f.product_id || p[0]?.id || "" }));
      })
      .catch((e) => showFeedback("error", e.message));
  }, [id, showFeedback]);
  useEffect(() => { load(); }, [load]);

  const selected = useMemo(() => products.find((p) => p.id === form.product_id), [products, form.product_id]);
  const total = Number(selected?.selling_price || 0) * Number(form.quantity);

  const submit = async (e) => {
    e.preventDefault();
    const paid = form.paid_amount === "" ? total : Number(form.paid_amount);
    if (paid < total && !form.customer_id) {
      showFeedback("error", "বাকি বিক্রির জন্য কাস্টমার নির্বাচন করুন।");
      return;
    }
    try {
      const payments = paid > 0 ? [{ method: form.method, amount: paid.toFixed(2) }] : [];
      const r = await api.createSale(id, {
        branch_id: form.branch_id, customer_id: form.customer_id || null,
        invoice_number: `INV-${Date.now()}`, sold_at: new Date().toISOString(),
        items: [{ product_id: form.product_id, quantity: form.quantity }], payments,
      });
      showFeedback("success", `বিক্রি সম্পন্ন: ${r.invoice_number} · ${formatBDT(Number(r.total))}`);
      setForm((f) => ({ ...f, paid_amount: "" }));
      load();
    } catch (x) {
      showFeedback("error", x.message);
    }
  };

  return (
    <Shell title="দ্রুত বিক্রি">
      <FeedbackBanner feedback={feedback} />
      <form className="card form-grid" onSubmit={submit}>
        <label>
          শাখা
          <select value={form.branch_id} onChange={(e) => setForm({ ...form, branch_id: e.target.value })}>
            {branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select>
        </label>
        <label>
          কাস্টমার (বাকি হলে আবশ্যক)
          <select value={form.customer_id} onChange={(e) => setForm({ ...form, customer_id: e.target.value })}>
            <option value="">সাধারণ ক্রেতা</option>
            {customers.map((c) => <option key={c.id} value={c.id}>{c.display_name || c.code}</option>)}
          </select>
        </label>
        <label>
          পণ্য
          <select value={form.product_id} onChange={(e) => setForm({ ...form, product_id: e.target.value })}>
            {products.map((p) => <option key={p.id} value={p.id}>{p.name} — {formatBDT(Number(p.selling_price))}</option>)}
          </select>
        </label>
        <label>
          পরিমাণ
          <input type="number" min="0.001" step="0.001" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} />
        </label>
        <label>
          পেমেন্ট
          <select value={form.method} onChange={(e) => setForm({ ...form, method: e.target.value })}>
            <option value="cash">ক্যাশ</option>
            <option value="bkash">বিকাশ</option>
            <option value="nagad">নগদ</option>
            <option value="bangla_qr">বাংলা QR</option>
            <option value="card">কার্ড</option>
          </select>
        </label>
        <label>
          এখন পরিশোধ (খালি রাখলে পুরোটা)
          <input type="number" min="0" step=".01" value={form.paid_amount} onChange={(e) => setForm({ ...form, paid_amount: e.target.value })} />
        </label>
        <p className="sale-total">মোট: {formatBDT(total)}</p>
        <button className="btn-primary" disabled={!selected}>বিক্রি সম্পন্ন করুন</button>
      </form>
      <div className="card table-wrap">
        <h3>সাম্প্রতিক বিক্রি</h3>
        <table>
          <thead><tr><th>চালান</th><th>সময়</th><th>পণ্য</th><th className="num">মোট</th><th className="num">বাকি</th></tr></thead>
          <tbody>
            {history.map((r) => (
              <tr key={r.id}>
                <td>{r.invoice_number}</td>
                <td>{new Date(r.sold_at).toLocaleString("bn-BD")}</td>
                <td>{r.items.map((x) => `${x.product_name} × ${x.quantity}`).join(", ")}</td>
                <td className="num">{formatBDT(Number(r.total))}</td>
                <td className="num">{formatBDT(Number(r.due))}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!history.length && <p className="hint">এখনো কোনো বিক্রি নেই।</p>}
      </div>
    </Shell>
  );
}

export function AccountsPage() {
  const { active } = useBusiness();
  const id = active?.id;
  const [rows, setRows] = useState([]);
  const [expenses, setExpenses] = useState([]);
  const [payable, setPayable] = useState([]);
  const [receivable, setReceivable] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [feedback, showFeedback] = useFeedback();
  const [form, setForm] = useState({
    category: "দোকান ভাড়া", amount: "", payment_method: "cash",
    incurred_at: new Date().toISOString().slice(0, 16),
  });
  const [settle, setSettle] = useState({ type: "receivable", party_id: "", amount: "", payment_method: "cash" });

  const load = useCallback(() => {
    if (!id) return;
    Promise.all([
      api.ledger(id, "expense"), api.expenses(id), api.ledger(id, "payable"),
      api.ledger(id, "receivable"), api.customersApp(id), api.suppliers(id),
    ])
      .then(([r, e, p, rc, c, s]) => {
        setRows(r); setExpenses(e); setPayable(p); setReceivable(rc); setCustomers(c); setSuppliers(s);
        setSettle((v) => ({ ...v, party_id: v.party_id || (v.type === "receivable" ? c[0]?.id : s[0]?.id) || "" }));
      })
      .catch((e) => showFeedback("error", e.message));
  }, [id, showFeedback]);
  useEffect(() => { load(); }, [load]);

  const submit = async (e) => {
    e.preventDefault();
    try {
      await api.createExpense(id, { ...form, incurred_at: new Date(form.incurred_at).toISOString() });
      setForm({ ...form, amount: "" });
      load();
      showFeedback("success", "খরচ সংরক্ষিত হয়েছে।");
    } catch (x) {
      showFeedback("error", x.message);
    }
  };

  const settlePayment = async (e) => {
    e.preventDefault();
    try {
      const body = { amount: settle.amount, payment_method: settle.payment_method, occurred_at: new Date().toISOString(), note: null };
      if (settle.type === "receivable") await api.receiveCustomerPayment(id, settle.party_id, body);
      else await api.paySupplier(id, settle.party_id, body);
      setSettle({ ...settle, amount: "" });
      showFeedback("success", "বাকি হিসাব সমন্বয় হয়েছে।");
      load();
    } catch (x) {
      showFeedback("error", x.message);
    }
  };

  const parties = settle.type === "receivable" ? customers : suppliers;
  const total = rows.reduce((s, r) => s + Number(r.balance), 0);
  const due = (list) => list.reduce((s, r) => s + Number(r.balance), 0);

  return (
    <Shell title="হিসাব ও খরচ">
      <FeedbackBanner feedback={feedback} />
      <div className="kpi-grid">
        <div className="kpi"><span className="label">মোট নথিভুক্ত খরচ</span><strong className="value">{formatBDT(total)}</strong></div>
        <div className="kpi"><span className="label">সাপ্লায়ারকে দেবেন</span><strong className="value">{formatBDT(due(payable))}</strong></div>
        <div className="kpi"><span className="label">কাস্টমারের কাছে পাবেন</span><strong className="value">{formatBDT(due(receivable))}</strong></div>
      </div>
      <div className="grid-2">
        <form className="card inline-form" onSubmit={submit}>
          <h3>নতুন খরচ</h3>
          <CategorySelect value={form.category} onChange={(category) => setForm({ ...form, category })} />
          <input type="number" min="0.01" step="0.01" placeholder="টাকার পরিমাণ" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} required />
          <select value={form.payment_method} onChange={(e) => setForm({ ...form, payment_method: e.target.value })}>
            <option value="cash">ক্যাশ</option>
            <option value="bkash">বিকাশ</option>
            <option value="nagad">নগদ</option>
            <option value="bank">ব্যাংক</option>
          </select>
          <input type="datetime-local" value={form.incurred_at} onChange={(e) => setForm({ ...form, incurred_at: e.target.value })} />
          <button className="btn-primary">খরচ যোগ করুন</button>
        </form>
        <form className="card inline-form" onSubmit={settlePayment}>
          <h3>বাকি পরিশোধ</h3>
          <select
            value={settle.type}
            onChange={(e) => {
              const type = e.target.value;
              setSettle({ ...settle, type, party_id: (type === "receivable" ? customers[0]?.id : suppliers[0]?.id) || "" });
            }}
          >
            <option value="receivable">কাস্টমার থেকে গ্রহণ</option>
            <option value="payable">সাপ্লায়ারকে প্রদান</option>
          </select>
          <select value={settle.party_id} onChange={(e) => setSettle({ ...settle, party_id: e.target.value })}>
            {parties.map((x) => <option key={x.id} value={x.id}>{x.display_name || x.name || x.code}</option>)}
          </select>
          <input type="number" min=".01" step=".01" placeholder="পরিমাণ" value={settle.amount} onChange={(e) => setSettle({ ...settle, amount: e.target.value })} required />
          <select value={settle.payment_method} onChange={(e) => setSettle({ ...settle, payment_method: e.target.value })}>
            <option value="cash">ক্যাশ</option>
            <option value="bkash">বিকাশ</option>
            <option value="nagad">নগদ</option>
            <option value="bank">ব্যাংক</option>
          </select>
          <button className="btn-primary" disabled={!settle.party_id}>সমন্বয় করুন</button>
        </form>
      </div>
      <div className="card table-wrap">
        <h3>সাম্প্রতিক খরচ</h3>
        <table>
          <thead><tr><th>সময়</th><th>ক্যাটাগরি</th><th>পেমেন্ট</th><th className="num">পরিমাণ</th></tr></thead>
          <tbody>
            {expenses.map((x) => (
              <tr key={x.id}>
                <td>{new Date(x.incurred_at).toLocaleDateString("bn-BD")}</td>
                <td>{x.category}</td>
                <td>{x.payment_method}</td>
                <td className="num">{formatBDT(Number(x.amount))}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!expenses.length && <p className="hint">এখনো কোনো খরচ নেই।</p>}
      </div>
    </Shell>
  );
}
