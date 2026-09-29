import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import { useBusiness } from "../BusinessContext";
import { ReceiptFooter, ReceiptHeader } from "../components/ReceiptHeader";
import { explain } from "../errors";
import { dateTimeBn, money, num } from "../format";
import DataTable from "../ui/DataTable";
import Icon from "../ui/Icon";
import { Badge, Button, Card, EmptyState, Field, Modal, Notice, PageHeader, Stepper } from "../ui/kit";
import { useToast } from "../ui/Toast";
import useBranch from "../useBranch";

const METHODS = [
  ["cash", "ক্যাশ"], ["bkash", "বিকাশ"], ["nagad", "নগদ"], ["card", "কার্ড"], ["bangla_qr", "বাংলা QR"],
];
const METHOD_LABEL = Object.fromEntries(METHODS);
const SALE_ERRORS = {
  404: "পণ্য বা শাখা খুঁজে পাওয়া যায়নি। পাতাটি রিফ্রেশ করে আবার চেষ্টা করুন।",
  409: "স্টক যথেষ্ট নেই। কিছু পণ্য শেষ, অথবা যা আছে তা মেয়াদোত্তীর্ণ বা বন্ধ করা ব্যাচে।",
  422: "বিক্রির তথ্য ঠিক নেই। পরিমাণ, ছাড় ও পেমেন্ট দেখে আবার দিন।",
};

// A cart survives a refresh or a dropped connection: losing a half-built bill at a
// busy counter is the kind of thing that makes people stop trusting software.
function readDraft(key) {
  try { return JSON.parse(sessionStorage.getItem(key)) || []; } catch { return []; }
}
function writeDraft(key, cart) {
  try { sessionStorage.setItem(key, JSON.stringify(cart)); } catch { /* storage disabled */ }
}

// ── Working without internet ────────────────────────────────────────────────
// A dropped connection must never stop a sale. The bill is kept on this device with
// its own invoice number, and sent when the connection returns. The invoice number is
// the safety catch: the server refuses a second sale with the same number, so a bill
// can never be counted twice even if the first send half-worked.
const read = (key, fallback) => { try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; } };
const write = (key, value) => { try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* storage full or blocked */ } };
const isOffline = (e) => e?.status === undefined;                 // no HTTP response at all
const isAlreadySent = (e) => e?.status === 409 && /Invoice number already exists/i.test(e.message || "");

const invoiceNumber = () => {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `INV-${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}-${Date.now().toString(36).toUpperCase()}`;
};

export default function SalesPage() {
  const { active } = useBusiness();
  const orgId = active?.id;
  const toast = useToast();
  const { branches, branch, setBranch, current: branchInfo } = useBranch(orgId);
  const searchRef = useRef(null);

  const [products, setProducts] = useState(null);
  const [customers, setCustomers] = useState([]);
  const [stock, setStock] = useState({});
  const [history, setHistory] = useState(null);
  const [loadError, setLoadError] = useState("");

  const draftKey = `pos.cart.${orgId}.${branch}`;
  const [cart, setCart] = useState([]);
  const [query, setQuery] = useState("");
  const [customerId, setCustomerId] = useState("");
  const [method, setMethod] = useState("cash");
  const [received, setReceived] = useState(null); // null = "exactly the total"
  const [busy, setBusy] = useState(false);
  const [saleError, setSaleError] = useState("");
  const [receipt, setReceipt] = useState(null);
  const queueKey = `pos.queue.${orgId}`;
  const cacheKey = `pos.cache.${orgId}.${branch}`;
  const [queue, setQueue] = useState([]);
  const [rejected, setRejected] = useState([]);
  const [usingCache, setUsingCache] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const heldKey = `pos.held.${orgId}`;
  const [held, setHeld] = useState([]);
  useEffect(() => { setHeld(read(heldKey, [])); }, [heldKey]);

  const load = useCallback(async () => {
    if (!orgId || !branch) return;
    try {
      const [p, c, inv, h] = await Promise.all([
        api.productsApp(orgId), api.customersApp(orgId), api.inventoryApp(orgId, branch), api.salesApp(orgId, branch),
      ]);
      const stockMap = Object.fromEntries(inv.map((r) => [r.product_id, Number(r.quantity)]));
      setProducts(p);
      setCustomers(c);
      setStock(stockMap);
      setHistory(h.slice(0, 15));
      setLoadError("");
      setUsingCache(false);
      write(cacheKey, { p, c, stock: stockMap, h: h.slice(0, 15) });
    } catch (e) {
      const cached = isOffline(e) ? read(cacheKey, null) : null;
      if (cached) {
        // No connection: keep selling from the last known catalogue and stock.
        setProducts(cached.p); setCustomers(cached.c); setStock(cached.stock); setHistory(cached.h);
        setUsingCache(true);
        setLoadError("");
      } else {
        setLoadError(explain(e));
        setProducts([]);
      }
    }
  }, [orgId, branch, cacheKey]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { if (orgId) setQueue(read(queueKey, [])); }, [orgId, queueKey]);

  // Send whatever is waiting. Called on reconnect, on a timer while anything waits, and by hand.
  const flush = useCallback(async () => {
    const waiting = read(queueKey, []);
    if (!waiting.length) return;
    setSyncing(true);
    let remaining = [];
    let sent = 0;
    for (const item of waiting) {
      try {
        await api.createSale(orgId, item.payload);
        sent += 1;
      } catch (e) {
        if (isAlreadySent(e)) sent += 1;                                   // it had already gone through
        else if (isOffline(e)) remaining = [...remaining, item];           // still no connection: keep it
        else setRejected((r) => [...r, { ...item, reason: explain(e, SALE_ERRORS) }]); // the shop must decide
      }
    }
    write(queueKey, remaining);
    setQueue(remaining);
    setSyncing(false);
    if (sent) { toast.success(`${num(sent)}টি জমা থাকা বিক্রি পাঠানো হয়েছে।`); load(); }
  }, [orgId, queueKey, toast, load]);

  useEffect(() => {
    if (!orgId) return undefined;
    flush();
    window.addEventListener("online", flush);
    const timer = setInterval(flush, 20000);
    return () => { window.removeEventListener("online", flush); clearInterval(timer); };
  }, [orgId, flush]);
  useEffect(() => { setCart(readDraft(draftKey)); }, [draftKey]);
  useEffect(() => { if (orgId && branch) writeDraft(draftKey, cart); }, [cart, draftKey, orgId, branch]);

  // "/" jumps to the search box from anywhere on the page.
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "/" && !["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement?.tagName)) {
        e.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = products || [];
    if (!q) return list.slice(0, 24);
    return list.filter((p) =>
      p.name.toLowerCase().includes(q) || p.sku.toLowerCase().includes(q) || (p.barcode || "").toLowerCase().includes(q),
    ).slice(0, 24);
  }, [products, query]);

  const totals = useMemo(() => {
    const subtotal = cart.reduce((s, l) => s + l.price * Number(l.qty || 0), 0);
    const discount = cart.reduce((s, l) => s + Number(l.discount || 0), 0);
    const total = Math.max(0, subtotal - discount);
    const got = received === null ? total : Number(received || 0);
    return { subtotal, discount, total, got, change: Math.max(0, got - total), due: Math.max(0, total - got), paid: Math.min(got, total) };
  }, [cart, received]);

  const customer = customers.find((c) => c.id === customerId);
  const wholesale = customer?.price_tier === "wholesale";
  const priceFor = (p) => (wholesale && p.wholesale_price != null ? Number(p.wholesale_price) : Number(p.selling_price));
  // Choosing a wholesale customer reprices the bill; going back to a walk-in customer restores retail.
  useEffect(() => {
    setCart((lines) => lines.map((l) => {
      const p = (products || []).find((x) => x.id === l.product_id);
      return p ? { ...l, price: priceFor(p) } : l;
    }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [customerId, products]);

  function holdBill() {
    const next = [...held, { id: Date.now().toString(36), at: new Date().toISOString(), cart, customerId }];
    write(heldKey, next); setHeld(next);
    setCart([]); setReceived(null); setCustomerId("");
    toast.info("বিলটি ধরে রাখা হয়েছে। উপরের ‘ধরে রাখা বিল’ থেকে আবার খুলতে পারবেন।");
  }
  function resumeBill(bill) {
    const others = held.filter((h) => h.id !== bill.id);
    const next = cart.length > 0 ? [...others, { id: Date.now().toString(36), at: new Date().toISOString(), cart, customerId }] : others;
    write(heldKey, next); setHeld(next);
    setCart(bill.cart); setCustomerId(bill.customerId || ""); setReceived(null);
  }
  function dropBill(bill) {
    const next = held.filter((h) => h.id !== bill.id);
    write(heldKey, next); setHeld(next);
  }

  function add(product) {
    const available = stock[product.id] ?? 0;
    setSaleError("");
    setCart((lines) => {
      const existing = lines.find((l) => l.product_id === product.id);
      if (existing) {
        if (Number(existing.qty) + 1 > available) { toast.error(`${product.name}: স্টকে মাত্র ${num(available)} আছে।`); return lines; }
        return lines.map((l) => (l.product_id === product.id ? { ...l, qty: Number(l.qty) + 1 } : l));
      }
      if (available <= 0) { toast.error(`${product.name}: স্টক নেই।`); return lines; }
      return [...lines, {
        product_id: product.id, name: product.name, sku: product.sku, price: priceFor(product),
        qty: 1, discount: 0, tracked: product.track_expiry,
      }];
    });
    setQuery("");
    searchRef.current?.focus();
  }

  function onSearchKey(e) {
    if (e.key !== "Enter") return;
    e.preventDefault();
    const q = query.trim().toLowerCase();
    // A scanner types the barcode then Enter: an exact barcode or SKU wins over a name match.
    const exact = (products || []).find((p) => (p.barcode || "").toLowerCase() === q || p.sku.toLowerCase() === q);
    const pick = exact || matches[0];
    if (pick) add(pick);
  }

  const updateLine = (id, patch) => setCart((lines) => lines.map((l) => (l.product_id === id ? { ...l, ...patch } : l)));
  const removeLine = (id) => setCart((lines) => lines.filter((l) => l.product_id !== id));

  const needsCustomer = totals.due > 0 && !customerId;
  const overStock = cart.some((l) => Number(l.qty) > (stock[l.product_id] ?? 0));
  const overLimit = Boolean(customer && customer.credit_limit != null && totals.due > 0
    && Number(customer.balance || 0) + totals.due > Number(customer.credit_limit));
  const canSell = cart.length > 0 && !busy && !needsCustomer && !overStock && !overLimit && cart.every((l) => Number(l.qty) > 0);

  async function sell() {
    setBusy(true);
    setSaleError("");
    const soldAt = new Date();
    const payload = {
      branch_id: branch, customer_id: customerId || null, invoice_number: invoiceNumber(),
      sold_at: soldAt.toISOString(),
      items: cart.map((l) => ({
        product_id: l.product_id, quantity: String(l.qty), discount_amount: Number(l.discount || 0).toFixed(2),
      })),
      payments: totals.paid > 0 ? [{ method, amount: totals.paid.toFixed(2) }] : [],
    };
    try {
      const result = await api.createSale(orgId, payload);
      setReceipt({
        invoice: result.invoice_number, at: soldAt.toISOString(), lines: cart, total: Number(result.total),
        paid: Number(result.paid), due: Number(result.due), change: totals.change, method,
        customer: customers.find((c) => c.id === customerId),
      });
      setCart([]);
      setReceived(null);
      setCustomerId("");
      load();
    } catch (e) {
      if (isOffline(e)) {
        // Keep the bill on this device and carry on selling.
        const next = [...read(queueKey, []), { payload, at: soldAt.toISOString(), total: totals.total }];
        write(queueKey, next);
        setQueue(next);
        setStock((s) => {
          const after = { ...s };
          for (const l of cart) after[l.product_id] = Math.max(0, (after[l.product_id] ?? 0) - Number(l.qty));
          return after;
        });
        setReceipt({
          invoice: payload.invoice_number, at: soldAt.toISOString(), lines: cart, total: totals.total, paid: totals.paid,
          due: totals.due, change: totals.change, method, customer: customers.find((c) => c.id === customerId), offline: true,
        });
        setCart([]); setReceived(null); setCustomerId("");
        toast.info("ইন্টারনেট নেই — বিক্রিটি এই ডিভাইসে জমা হয়েছে। সংযোগ ফিরলে নিজে পাঠানো হবে।");
      } else {
        setSaleError(/Credit limit/i.test(e.message || "") ? "বাকির সীমা ছাড়িয়ে যাবে। কিছু বাকি আদায় করুন বা বেশি টাকা নিন।" : explain(e, SALE_ERRORS));
      }
    } finally {
      setBusy(false);
    }
  }

  if (!active) {
    return <div className="page"><EmptyState icon="sliders" title="আগে ব্যবসা সেটআপ করুন" action={<a className="ui-btn ui-btn--primary" href="#/setup">সেটআপে যান</a>} /></div>;
  }

  return (
    <div className="page stack">
      <PageHeader
        title="বিক্রি"
        subtitle={branchInfo ? `${active.name} · ${branchInfo.name}` : active.name}
        actions={branches && branches.length > 1 && (
          <Field label="শাখা"><select value={branch} onChange={(e) => setBranch(e.target.value)}>
            {branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select></Field>
        )}
      />
      {usingCache && <Notice tone="warn" title="ইন্টারনেট নেই">সর্বশেষ জানা পণ্য ও স্টক দেখানো হচ্ছে। বিক্রি চালিয়ে যেতে পারবেন — সংযোগ ফিরলে সব পাঠানো হবে।</Notice>}
      {queue.length > 0 && (
        <div className="offline-bar" role="status">
          <Icon name="refresh" size={18} />
          <span style={{ flex: 1 }}>{num(queue.length)}টি বিক্রি পাঠানোর অপেক্ষায় আছে ({money(queue.reduce((s, q) => s + q.total, 0))})। সংযোগ পেলে নিজে থেকেই যাবে।</span>
          <Button size="sm" variant="secondary" loading={syncing} onClick={flush}>এখনই পাঠান</Button>
        </div>
      )}
      {rejected.map((r) => (
        <Notice key={r.payload.invoice_number} tone="danger" title={`বিক্রি ${r.payload.invoice_number} গ্রহণ হয়নি`}
                action={<Button size="sm" variant="secondary" onClick={() => setRejected((all) => all.filter((x) => x !== r))}>বুঝেছি</Button>}>
          {r.reason} এই বিক্রিটি সার্ভারে যায়নি — হাতে ঠিক করে আবার লিখুন।
        </Notice>
      ))}
      {loadError && <Notice tone="danger" action={<Button size="sm" variant="secondary" onClick={load}>আবার চেষ্টা</Button>}>{loadError}</Notice>}
      {held.length > 0 && (
        <div className="offline-bar" role="status" aria-label="ধরে রাখা বিল">
          <strong>ধরে রাখা বিল ({num(held.length)})</strong>
          {held.map((h) => (
            <span key={h.id} className="row" style={{ gap: 4, flexWrap: "nowrap" }}>
              <Button size="sm" variant="secondary" onClick={() => resumeBill(h)}>{dateTimeBn(h.at).split(",").pop().trim()} · {num(h.cart.length)}টি পণ্য</Button>
              <Button size="sm" variant="ghost" icon="x" onClick={() => dropBill(h)} aria-label="ধরে রাখা বিল মুছুন" />
            </span>
          ))}
        </div>
      )}

      <div className="pos">
        <div>
          <div className="pos-search">
            <Icon name="search" size={20} />
            <input ref={searchRef} value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={onSearchKey}
                   placeholder="পণ্যের নাম, SKU বা বারকোড লিখুন…" aria-label="পণ্য খুঁজুন" autoFocus autoComplete="off" />
          </div>
          <p className="pos-hint">বারকোড স্ক্যান করে Enter চাপুন · <kbd>/</kbd> চেপে যেকোনো সময় খুঁজুন</p>

          {products === null ? (
            <div className="pos-grid">{[0, 1, 2, 3, 4, 5].map((i) => <div key={i} className="ui-skeleton"><span style={{ height: 96 }} /></div>)}</div>
          ) : matches.length === 0 ? (
            <EmptyState icon="search" title={query ? "কিছু মেলেনি" : "এখনো কোনো পণ্য নেই"}
                        hint={query ? "অন্য নাম বা SKU দিয়ে খুঁজুন।" : "আগে পণ্য পাতায় গিয়ে পণ্য যোগ করুন।"}
                        action={!query && <a className="ui-btn ui-btn--secondary" href="#/products">পণ্য যোগ করুন</a>} />
          ) : (
            <div className="pos-grid">
              {matches.map((p) => {
                const qty = stock[p.id] ?? 0;
                return (
                  <button key={p.id} type="button" className="pos-item" onClick={() => add(p)} disabled={qty <= 0}
                          aria-label={`${p.name}, ${money(p.selling_price)}, স্টক ${num(qty)}`}>
                    <strong>{p.name}</strong>
                    <span className="price">{money(p.selling_price)}</span>
                    <span className="meta">
                      {qty <= 0 ? <Badge tone="danger">স্টক নেই</Badge>
                        : <span>স্টক {num(qty)}{qty <= Number(p.reorder_level) ? " · কম" : ""}</span>}
                      {p.track_expiry && <Badge tone="info" icon="clock">মেয়াদ</Badge>}
                    </span>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        <aside className="pos-cart">
          <Card title={`বিল${cart.length ? ` (${num(cart.length)})` : ""}`}
                actions={cart.length > 0 && <Button size="sm" variant="ghost" icon="trash" onClick={() => setCart([])}>খালি করুন</Button>}>
            {cart.length === 0 ? (
              <div className="pos-empty">
                <Icon name="cart" size={30} />
                <p>পণ্য বেছে নিলে এখানে বিল তৈরি হবে।</p>
              </div>
            ) : (
              <ul className="pos-lines">
                {cart.map((l) => (
                  <li key={l.product_id} className="pos-line">
                    <div className="pos-line__name">{l.name}<small>{money(l.price)} × {num(l.qty)}{l.tracked ? " · মেয়াদ অনুযায়ী আগে যাবে" : ""}</small></div>
                    <div className="pos-line__total">{money(l.price * Number(l.qty || 0) - Number(l.discount || 0))}</div>
                    <div className="pos-line__controls">
                      <Stepper value={l.qty} min={0.001} step={1} max={stock[l.product_id]} label={`${l.name}-এর পরিমাণ`}
                               onChange={(v) => updateLine(l.product_id, { qty: v })} />
                      <label className="grow" style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}>
                        ছাড় ৳
                        <input type="number" min="0" step="0.01" value={l.discount || ""} placeholder="০"
                               onChange={(e) => updateLine(l.product_id, { discount: e.target.value })} style={{ minHeight: 40, width: 90 }}
                               aria-label={`${l.name}-এর ছাড়`} />
                      </label>
                      <Button variant="ghost" size="sm" icon="trash" onClick={() => removeLine(l.product_id)} aria-label={`${l.name} বাদ দিন`} />
                    </div>
                  </li>
                ))}
              </ul>
            )}

            {cart.length > 0 && (
              <>
                <div className="pos-totals">
                  {totals.discount > 0 && <div><span>মোট</span><span>{money(totals.subtotal)}</span></div>}
                  {totals.discount > 0 && <div><span>ছাড়</span><span>− {money(totals.discount)}</span></div>}
                  <div className="grand"><span>পরিশোধযোগ্য</span><span>{money(totals.total)}</span></div>
                </div>

                <div className="ui-form" style={{ marginTop: 16 }}>
                  <div><Button size="sm" variant="secondary" icon="clock" onClick={holdBill}>বিল ধরে রাখুন</Button></div>
                  {wholesale && <Notice tone="info">পাইকারি কাস্টমার — যেসব পণ্যে পাইকারি দাম দেওয়া আছে সেগুলোতে সেই দাম ধরা হয়েছে।</Notice>}
                  {overLimit && <Notice tone="danger" title="বাকির সীমা ছাড়িয়ে যাবে">{customer.display_name || customer.code}-এর আগের বাকি {money(customer.balance || 0)}, সীমা {money(customer.credit_limit)}। বেশি টাকা নিন বা আগের বাকি আদায় করুন।</Notice>}
                  <Field label="কাস্টমার" hint={needsCustomer ? undefined : "বাকি রাখলে কাস্টমার বেছে নিতে হবে"}>
                    <select value={customerId} onChange={(e) => setCustomerId(e.target.value)}>
                      <option value="">সাধারণ ক্রেতা</option>
                      {customers.map((c) => <option key={c.id} value={c.id}>{c.display_name || c.code}</option>)}
                    </select>
                  </Field>
                  <div>
                    <div className="pay-methods" role="radiogroup" aria-label="পেমেন্টের মাধ্যম">
                      {METHODS.map(([value, label]) => (
                        <button key={value} type="button" role="radio" aria-checked={method === value}
                                className={method === value ? "on" : ""} onClick={() => setMethod(value)}>{label}</button>
                      ))}
                    </div>
                  </div>
                  <Field label="ক্রেতা দিয়েছেন (৳)">
                    <input type="number" min="0" step="0.01" inputMode="decimal"
                           value={received === null ? String(totals.total) : received}
                           onChange={(e) => setReceived(e.target.value)} />
                  </Field>
                  <div className="pos-quick" style={{ marginTop: -8 }}>
                    <button type="button" onClick={() => setReceived(null)}>পুরো টাকা</button>
                    {[500, 1000, 2000].filter((v) => v > totals.total).slice(0, 2).map((v) => (
                      <button key={v} type="button" onClick={() => setReceived(String(v))}>{money(v)}</button>
                    ))}
                    <button type="button" onClick={() => setReceived("0")}>সবটা বাকি</button>
                  </div>
                  {totals.change > 0 && <div className="pos-result change"><span>ফেরত দিন</span><span>{money(totals.change)}</span></div>}
                  {totals.due > 0 && <div className="pos-result due"><span>বাকি থাকবে</span><span>{money(totals.due)}</span></div>}
                  {needsCustomer && <Notice tone="warn">বাকি রাখতে ওপরে কাস্টমার বেছে নিন।</Notice>}
                  {overStock && <Notice tone="warn">কোনো পণ্যের পরিমাণ স্টকের চেয়ে বেশি। পরিমাণ কমান।</Notice>}
                  {saleError && <Notice tone="danger">{saleError}</Notice>}
                  <Button block loading={busy} disabled={!canSell} icon="check" onClick={sell}>
                    বিক্রি সম্পন্ন করুন · {money(totals.total)}
                  </Button>
                </div>
              </>
            )}
          </Card>
        </aside>
      </div>

      <Card pad={false} title="সাম্প্রতিক বিক্রি">
        <DataTable
          loading={history === null}
          rows={history || []}
          columns={[
            { key: "invoice_number", label: "চালান", primary: true },
            { key: "sold_at", label: "সময়", render: (r) => dateTimeBn(r.sold_at) },
            { key: "items", label: "পণ্য", render: (r) => r.items.map((x) => `${x.product_name} × ${num(x.quantity)}`).join(", ") },
            { key: "total", label: "মোট", align: "right", render: (r) => money(r.total) },
            { key: "due", label: "বাকি", align: "right", render: (r) => (Number(r.due) > 0 ? <Badge tone="warn">{money(r.due)}</Badge> : "—") },
          ]}
          empty={<EmptyState icon="cart" title="এখনো কোনো বিক্রি নেই" hint="প্রথম বিক্রি করলে এখানে দেখা যাবে।" />}
        />
      </Card>

      <Modal open={Boolean(receipt)} title="বিক্রি সম্পন্ন হয়েছে" onClose={() => { setReceipt(null); searchRef.current?.focus(); }}
             footer={<>
               <Button variant="secondary" icon="printer" onClick={() => window.print()}>রসিদ প্রিন্ট</Button>
               <Button onClick={() => { setReceipt(null); searchRef.current?.focus(); }}>নতুন বিক্রি</Button>
             </>}>
        {receipt && (
          <div className="receipt receipt-print">
            <ReceiptHeader shop={active} branch={branchInfo?.name} />
            <p>{receipt.invoice} · {dateTimeBn(receipt.at)}</p>
            {receipt.offline && <p>(অফলাইনে জমা — পরে পাঠানো হবে)</p>}
            {receipt.customer && <p>কাস্টমার: {receipt.customer.display_name || receipt.customer.code}</p>}
            <table>
              <tbody>
                {receipt.lines.map((l) => (
                  <tr key={l.product_id}>
                    <td>{l.name} × {num(l.qty)}</td>
                    <td>{money(l.price * Number(l.qty) - Number(l.discount || 0))}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="tot"><span>মোট</span><span>{money(receipt.total)}</span></div>
            <div className="tot"><span>পরিশোধ ({METHOD_LABEL[receipt.method]})</span><span>{money(receipt.paid)}</span></div>
            {receipt.due > 0 && <div className="tot"><span>বাকি</span><span>{money(receipt.due)}</span></div>}
            {receipt.change > 0 && <div className="tot"><span>ফেরত</span><span>{money(receipt.change)}</span></div>}
            <ReceiptFooter shop={active} />
          </div>
        )}
      </Modal>
    </div>
  );
}
