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

// Public order-status lookup: a customer with no account checks their order
// with the access_token they were given at checkout. See
// api/order_routes.py's public_order_status.
export default function OrderStatusPage() {
  const { orgId, token } = useParams();
  const [order, setOrder] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.publicOrderStatus(orgId, token).then(setOrder).catch((e) => setError(explain(e, { 404: "এই অর্ডারটি পাওয়া যায়নি।" })));
  }, [orgId, token]);

  return (
    <div className="page stack" style={{ maxWidth: 600, margin: "0 auto" }}>
      <PageHeader title="অর্ডারের অবস্থা" subtitle="এই লিংকটি সংরক্ষণ করুন — যেকোনো সময় অর্ডারের সর্বশেষ অবস্থা দেখতে পারবেন।" />
      {error && <Notice tone="danger">{error}</Notice>}
      {!order && !error && <p className="muted">লোড হচ্ছে…</p>}
      {order && (
        <Card>
          <p><strong>{order.order_number}</strong> — <Badge tone={LABEL[order.status]?.[1] || "neutral"}>{LABEL[order.status]?.[0] || order.status}</Badge></p>
          <p className="muted">জমা হয়েছে: {dateBn(order.placed_at)}</p>
          <ul>
            {order.items.map((it, i) => <li key={i}>{it.product_name} × {num(it.quantity)} = {money(it.line_total)}</li>)}
          </ul>
          <p><strong>মোট: {money(order.total)}</strong></p>
          <p className="muted">ডেলিভারি ঠিকানা: {order.shipping_address}</p>
          <Link to={`/store/${orgId}`}>আরেকটি অর্ডার করুন</Link>
        </Card>
      )}
    </div>
  );
}
