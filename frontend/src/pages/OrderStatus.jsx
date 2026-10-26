import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../api";
import { explain } from "../errors";
import { dateBn, money, num } from "../format";
import { Badge, Card, Notice, PageHeader } from "../ui/kit";
import "./OrderStatus.css";

const LABEL = {
  placed: ["অর্ডারটি গ্রহণ করা হয়েছে", "warn"],
  confirmed: ["দোকান অর্ডারটি নিশ্চিত করেছে", "info"],
  ready: ["অর্ডার প্রস্তুত করা হচ্ছে", "warn"],
  dispatched: ["ডেলিভারির জন্য পাঠানো হয়েছে", "info"],
  delivered: ["ডেলিভারি সম্পন্ন হয়েছে", "success"],
  cancelled: ["অর্ডার বাতিল হয়েছে", "danger"],
};

const STEPS = ["placed", "confirmed", "ready", "dispatched", "delivered"];

function StatusTimeline({ status }) {
  const currentIdx = STEPS.indexOf(status);
  if (status === "cancelled") return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "12px 0", color: "var(--order-danger)", fontWeight: 600, fontSize: 13 }}>
      ❌ অর্ডার বাতিল হয়েছে
    </div>
  );
  return (
    <div className="order-status-timeline" style={{ display: "flex", alignItems: "center", gap: 0, margin: "16px 0", overflowX: "auto" }}>
      {STEPS.map((s, i) => {
        const done = i <= currentIdx;
        const active = i === currentIdx;
        return (
          <div key={s} style={{ display: "flex", alignItems: "center", flex: 1, minWidth: 105 }}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", flex: 1 }}>
              <div style={{
                width: 28, height: 28, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center",
                background: done ? "var(--order-success)" : "var(--surface)", border: `2px solid ${done ? "var(--order-success)" : "var(--border)"}`,
                color: done ? "var(--order-success-text)" : "var(--text-muted)", fontSize: 13, fontWeight: 700,
                boxShadow: active ? "0 0 0 3px var(--order-focus)" : "none",
              }}>
                {done ? "✓" : i + 1}
              </div>
              <div style={{ fontSize: 10, color: done ? "var(--order-link)" : "var(--text-muted)", marginTop: 4, textAlign: "center", whiteSpace: "normal", lineHeight: 1.45, overflowWrap: "anywhere" }}>
                {LABEL[s]?.[0]?.split(",")[0] || s}
              </div>
            </div>
            {i < STEPS.length - 1 && (
              <div style={{ height: 2, flex: 1, background: i < currentIdx ? "var(--order-success)" : "var(--border)", marginBottom: 16 }} />
            )}
          </div>
        );
      })}
    </div>
  );
}

// Public order-status lookup: a customer with no account checks their order
// with the access_token they were given at checkout.
export default function OrderStatusPage() {
  const { orgId, token } = useParams();
  const [order, setOrder] = useState(null);
  const [error, setError] = useState("");
  const [cancelling, setCancelling] = useState(false);
  const [screenshot, setScreenshot] = useState(null);
  const [uploadingScreenshot, setUploadingScreenshot] = useState(false);

  function load() {
    api.publicOrderStatus(orgId, token).then(setOrder).catch((e) => setError(explain(e, { 404: "অর্ডারটি পাওয়া যায়নি। লিংকটি সঠিক কি না দেখে আবার চেষ্টা করুন।" })));
  }

  useEffect(() => { load(); }, [orgId, token]);

  async function cancelOrder() {
    if (!window.confirm("এই অর্ডারটি বাতিল করতে চান?")) return;
    setCancelling(true);
    try {
      const updated = await api.publicCancelOrder(orgId, token);
      setOrder(updated);
    } catch (e) { setError(explain(e)); }
    finally { setCancelling(false); }
  }

  async function uploadScreenshot() {
    if (!screenshot) return;
    setUploadingScreenshot(true);
    try {
      const updated = await api.publicUploadPaymentScreenshot(orgId, token, { screenshot });
      setOrder(updated);
      setScreenshot(null);
    } catch (e) { setError(explain(e)); }
    finally { setUploadingScreenshot(false); }
  }

  return (
    <div className="page stack public-order-status" style={{ maxWidth: 660, margin: "0 auto" }}>
      <PageHeader title="অর্ডারের সর্বশেষ অবস্থা" subtitle="এই লিংকটি সংরক্ষণ করুন। এখান থেকে অর্ডারের অগ্রগতি দেখতে পারবেন।" />
      {error && <Notice tone="danger">{error}</Notice>}
      {!order && !error && <p className="muted">লোড হচ্ছে…</p>}
      {order && (
        <Card>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
            <strong style={{ fontSize: 16 }}>#{order.order_number}</strong>
            <Badge tone={LABEL[order.status]?.[1] || "neutral"}>{LABEL[order.status]?.[0] || order.status}</Badge>
          </div>
          <p className="muted" style={{ fontSize: 13, marginBottom: 4 }}>অর্ডার করা হয়েছে: {dateBn(order.placed_at)}</p>
          {order.expected_delivery_at && (
            <p className="muted" style={{ fontSize: 13 }}>আনুমানিক ডেলিভারি: {dateBn(order.expected_delivery_at)}</p>
          )}

          <StatusTimeline status={order.status} />

          {order.status_note && (
            <div style={{ padding: "10px 14px", background: "color-mix(in srgb, #3b82f6 10%, transparent)", borderRadius: 8, border: "1px solid #3b82f640", fontSize: 13, marginBottom: 12 }}>
              💬 অর্ডার সম্পর্কে তথ্য: <strong>{order.status_note}</strong>
            </div>
          )}

          <ul style={{ padding: 0, listStyle: "none", margin: "0 0 10px" }}>
            {order.items.map((it, i) => (
              <li key={i} style={{ display: "flex", justifyContent: "space-between", padding: "4px 0", fontSize: 13, borderBottom: i < order.items.length - 1 ? "1px solid var(--border)" : "none" }}>
                <span>{it.product_name} × {num(it.quantity)}</span>
                <span>{money(it.line_total)}</span>
              </li>
            ))}
          </ul>
          {Number(order.delivery_fee) > 0 && (
            <p style={{ fontSize: 13, color: "var(--text-muted)" }}>ডেলিভারি চার্জ: {money(order.delivery_fee)}</p>
          )}
          <p><strong>অর্ডারের মোট মূল্য: {money(order.total)}</strong></p>
          <p className="muted" style={{ fontSize: 13 }}>ডেলিভারির ঠিকানা: {order.shipping_address}</p>

          {/* Payment screenshot upload */}
          {order.payment_status === "pending" && order.status !== "cancelled" && (
            <div style={{ marginTop: 14, padding: "12px 14px", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 10 }}>
              <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 8 }}>📤 পেমেন্টের স্ক্রিনশট যুক্ত করুন</div>
              <input type="file" accept="image/*" onChange={async e => {
                const file = e.target.files[0]; if (!file) return;
                const reader = new FileReader();
                reader.onload = ev => setScreenshot(ev.target.result);
                reader.readAsDataURL(file);
              }} style={{ display: "block", marginBottom: 8 }} />
              {screenshot && (
                <button disabled={uploadingScreenshot} onClick={uploadScreenshot}
                  className="order-status-upload-btn">
                  {uploadingScreenshot ? "পাঠানো হচ্ছে…" : "স্ক্রিনশট জমা দিন"}
                </button>
              )}
            </div>
          )}

          {/* Cancel button */}
          {order.status === "placed" && (
            <button disabled={cancelling} onClick={cancelOrder}
              className="order-status-cancel-btn">
              {cancelling ? "বাতিল হচ্ছে…" : "✕ অর্ডার বাতিল করুন"}
            </button>
          )}

          <div style={{ marginTop: 16 }}>
            <Link to={`/store/${order.organization_id || orgId}`} className="order-status-return">দোকানে ফিরে যান →</Link>
          </div>
        </Card>
      )}
    </div>
  );
}
