import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../api";
import { explain } from "../errors";
import { dateBn, money, num } from "../format";
import { Badge, Card, Notice, PageHeader } from "../ui/kit";

const LABEL = {
  placed: ["অর্ডার জমা হয়েছে, দোকান দেখছে", "warn"],
  confirmed: ["দোকান নিশ্চিত করেছে", "info"],
  ready: ["পণ্য প্রস্তুত হচ্ছে", "warn"],
  dispatched: ["ডেলিভারির জন্য পাঠানো হয়েছে", "info"],
  delivered: ["ডেলিভারি সম্পন্ন", "success"],
  cancelled: ["অর্ডার বাতিল হয়েছে", "danger"],
};

const STEPS = ["placed", "confirmed", "ready", "dispatched", "delivered"];

function StatusTimeline({ status }) {
  const currentIdx = STEPS.indexOf(status);
  if (status === "cancelled") return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "12px 0", color: "#ef4444", fontWeight: 600, fontSize: 13 }}>
      ❌ অর্ডার বাতিল হয়েছে
    </div>
  );
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 0, margin: "16px 0", overflowX: "auto" }}>
      {STEPS.map((s, i) => {
        const done = i <= currentIdx;
        const active = i === currentIdx;
        return (
          <div key={s} style={{ display: "flex", alignItems: "center", flex: 1, minWidth: 0 }}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", flex: 1 }}>
              <div style={{
                width: 28, height: 28, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center",
                background: done ? "#0a8752" : "var(--surface)", border: `2px solid ${done ? "#0a8752" : "var(--border)"}`,
                color: done ? "#fff" : "var(--text-muted)", fontSize: 13, fontWeight: 700,
                boxShadow: active ? "0 0 0 3px #0a875240" : "none",
              }}>
                {done ? "✓" : i + 1}
              </div>
              <div style={{ fontSize: 10, color: done ? "#0a8752" : "var(--text-muted)", marginTop: 4, textAlign: "center", whiteSpace: "nowrap" }}>
                {LABEL[s]?.[0]?.split(",")[0] || s}
              </div>
            </div>
            {i < STEPS.length - 1 && (
              <div style={{ height: 2, flex: 1, background: i < currentIdx ? "#0a8752" : "var(--border)", marginBottom: 16 }} />
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
    api.publicOrderStatus(orgId, token).then(setOrder).catch((e) => setError(explain(e, { 404: "এই অর্ডারটি পাওয়া যায়নি।" })));
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
    <div className="page stack" style={{ maxWidth: 600, margin: "0 auto" }}>
      <PageHeader title="অর্ডারের অবস্থা" subtitle="এই লিংকটি সংরক্ষণ করুন — যেকোনো সময় অর্ডারের সর্বশেষ অবস্থা দেখতে পারবেন।" />
      {error && <Notice tone="danger">{error}</Notice>}
      {!order && !error && <p className="muted">লোড হচ্ছে…</p>}
      {order && (
        <Card>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
            <strong style={{ fontSize: 16 }}>#{order.order_number}</strong>
            <Badge tone={LABEL[order.status]?.[1] || "neutral"}>{LABEL[order.status]?.[0] || order.status}</Badge>
          </div>
          <p className="muted" style={{ fontSize: 13, marginBottom: 4 }}>জমা হয়েছে: {dateBn(order.placed_at)}</p>
          {order.expected_delivery_at && (
            <p className="muted" style={{ fontSize: 13 }}>আনুমানিক ডেলিভারি: {dateBn(order.expected_delivery_at)}</p>
          )}

          <StatusTimeline status={order.status} />

          {order.status_note && (
            <div style={{ padding: "10px 14px", background: "color-mix(in srgb, #3b82f6 10%, transparent)", borderRadius: 8, border: "1px solid #3b82f640", fontSize: 13, marginBottom: 12 }}>
              💬 দোকান থেকে বার্তা: <strong>{order.status_note}</strong>
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
          <p><strong>মোট: {money(order.total)}</strong></p>
          <p className="muted" style={{ fontSize: 13 }}>ডেলিভারি ঠিকানা: {order.shipping_address}</p>

          {/* Payment screenshot upload */}
          {order.payment_status === "pending" && order.status !== "cancelled" && (
            <div style={{ marginTop: 14, padding: "12px 14px", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 10 }}>
              <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 8 }}>📤 পেমেন্ট স্ক্রিনশট পাঠান</div>
              <input type="file" accept="image/*" onChange={async e => {
                const file = e.target.files[0]; if (!file) return;
                const reader = new FileReader();
                reader.onload = ev => setScreenshot(ev.target.result);
                reader.readAsDataURL(file);
              }} style={{ display: "block", marginBottom: 8 }} />
              {screenshot && (
                <button disabled={uploadingScreenshot} onClick={uploadScreenshot}
                  style={{ padding: "7px 16px", borderRadius: 8, border: "1px solid #0a875240", background: "#0a875112", color: "#0a8752", fontSize: 13, cursor: "pointer", fontWeight: 600 }}>
                  {uploadingScreenshot ? "পাঠানো হচ্ছে…" : "✓ স্ক্রিনশট পাঠান"}
                </button>
              )}
            </div>
          )}

          {/* Cancel button */}
          {order.status === "placed" && (
            <button disabled={cancelling} onClick={cancelOrder}
              style={{ marginTop: 14, width: "100%", padding: "10px 0", borderRadius: 10, border: "2px solid #ef4444", background: "transparent", color: "#ef4444", fontWeight: 700, fontSize: 14, cursor: "pointer" }}>
              {cancelling ? "বাতিল হচ্ছে…" : "✕ অর্ডার বাতিল করুন"}
            </button>
          )}

          <div style={{ marginTop: 16 }}>
            <Link to={`/store/${order.organization_id || orgId}`} style={{ color: "var(--green, #0a8752)", fontSize: 13 }}>আরেকটি অর্ডার করুন →</Link>
          </div>
        </Card>
      )}
    </div>
  );
}
