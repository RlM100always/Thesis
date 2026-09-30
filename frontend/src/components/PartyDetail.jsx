import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { useBusiness } from "../BusinessContext";
import { explain } from "../errors";
import { dateTimeBn, money, num } from "../format";
import DataTable from "../ui/DataTable";
import { Badge, Button, Modal, Notice, Skeleton, Stat } from "../ui/kit";
import { useToast } from "../ui/Toast";

function useDetail(load, id) {
  const [state, setState] = useState({ data: null, error: "" });
  // The loader is a fresh arrow function on every render; keeping it in a ref means the
  // effect runs when the *id* changes, not on every render (which would never settle).
  const loader = useRef(load);
  loader.current = load;
  useEffect(() => {
    if (!id) return undefined;
    let current = true;
    setState({ data: null, error: "" });
    loader.current(id).then((data) => current && setState({ data, error: "" })).catch((e) => current && setState({ data: null, error: explain(e) }));
    return () => { current = false; };
  }, [id]);
  return state;
}

const since = (days) => (days === null || days === undefined ? "কখনো কেনেননি" : days === 0 ? "আজ" : `${num(days)} দিন আগে`);

// Everything about one customer in one place, and a ready polite reminder for baki.
export function CustomerDetail({ customerId, onClose, onCollect }) {
  const { active } = useBusiness();
  const toast = useToast();
  const { data, error } = useDetail((id) => api.customerSummary(active.id, id), customerId);
  const { data: loyalty } = useDetail((id) => api.customerLoyalty(active.id, id), customerId);

  const reminder = data && Number(data.due) > 0
    ? `আসসালামু আলাইকুম ${data.name}, ${active.name} থেকে জানাচ্ছি — আপনার ${money(data.due)} বাকি আছে। সুবিধামতো পরিশোধ করলে ভালো হয়। ধন্যবাদ।`
    : "";

  async function copy() {
    try { await navigator.clipboard.writeText(reminder); toast.success("বার্তা কপি হয়েছে। এখন WhatsApp বা SMS-এ পাঠান।"); } catch { toast.error("কপি করা যায়নি।"); }
  }

  return (
    <Modal wide open={Boolean(customerId)} title={data ? data.name : "কাস্টমার"} onClose={onClose}>
      {error && <Notice tone="danger">{error}</Notice>}
      {!data && !error && <Skeleton lines={5} height={18} />}
      {data && (
        <div className="customer-360">
          <div className="row" style={{ gap: 8 }}>
            <Badge>{data.code}</Badge>
            {data.marketing_consent ? <Badge tone="success" icon="check">বার্তা পাঠানোর সম্মতি আছে</Badge> : <Badge>সম্মতি নেই</Badge>}
          </div>
          <div className="ui-stats">
            <Stat label="মোট কিনেছেন" value={money(data.total_spent)} sub={`${num(data.orders)}টি চালান`} />
            <Stat label="গড় চালান" value={data.average_order === null ? "—" : money(data.average_order)} />
            <Stat label="শেষ কেনা" value={since(data.days_since_last_purchase)} sub={data.last_purchase_at ? dateTimeBn(data.last_purchase_at) : undefined}
                  tone={data.days_since_last_purchase > 60 ? "warn" : "neutral"} />
            <Stat label="বাকি আছে" value={money(data.due)} tone={Number(data.due) > 0 ? "warn" : "success"} />
            {loyalty?.active && <Stat label="লয়্যালটি পয়েন্ট" value={num(loyalty.balance)} sub="বিক্রির সময় ছাড় হিসেবে ভাঙানো যাবে" />}
          </div>

          {Number(data.due) > 0 && (
            <div>
              <strong>বাকি মনে করানোর বার্তা</strong>
              <p className="muted" style={{ margin: "4px 0 8px", fontSize: 13 }}>ভদ্রভাবে লেখা। আপনি নিজে পাঠান — ফোন নম্বর আমরা সংরক্ষণ করি না।</p>
              <div className="reminder">{reminder}</div>
              <div className="row" style={{ marginTop: 10 }}>
                <Button size="sm" variant="secondary" icon="copy" onClick={copy}>কপি করুন</Button>
                <a className="ui-btn ui-btn--secondary ui-btn--sm" href={`https://wa.me/?text=${encodeURIComponent(reminder)}`} target="_blank" rel="noreferrer">WhatsApp</a>
                {onCollect && <Button size="sm" onClick={() => onCollect(data)}>বাকি আদায় করুন</Button>}
              </div>
            </div>
          )}

          {data.top_products.length > 0 && (
            <div>
              <strong>যা সবচেয়ে বেশি কেনেন</strong>
              <div className="row" style={{ marginTop: 8 }}>{data.top_products.map((p) => <Badge key={p.name} tone="info">{p.name} · {num(p.quantity)}</Badge>)}</div>
            </div>
          )}
          <DataTable rowKey="invoice" rows={data.recent} caption="সাম্প্রতিক চালান" columns={[
            { key: "invoice", label: "চালান", primary: true }, { key: "sold_at", label: "সময়", render: (r) => dateTimeBn(r.sold_at) },
            { key: "total", label: "মোট", align: "right", render: (r) => money(r.total) },
          ]} />
        </div>
      )}
    </Modal>
  );
}

// How the supplier really performs, from your own orders — not what they promise.
export function SupplierDetail({ supplierId, onClose, onPay }) {
  const { active } = useBusiness();
  const { data, error } = useDetail((id) => api.supplierStats(active.id, id), supplierId);
  return (
    <Modal wide open={Boolean(supplierId)} title={data ? data.name : "সাপ্লায়ার"} onClose={onClose}>
      {error && <Notice tone="danger">{error}</Notice>}
      {!data && !error && <Skeleton lines={5} height={18} />}
      {data && (
        <div className="customer-360">
          <div className="ui-stats">
            <Stat label="গড় ডেলিভারি সময়" value={data.average_lead_days === null ? "মাপা হয়নি" : `${num(data.average_lead_days)} দিন`}
                  sub={data.declared_lead_days ? `বলা আছে ${num(data.declared_lead_days)} দিন` : "বলা সময় দেওয়া নেই"}
                  tone={data.average_lead_days !== null && data.declared_lead_days && data.average_lead_days > data.declared_lead_days ? "warn" : "neutral"} />
            <Stat label="সময়মতো মাল আসা" value={data.on_time_rate === null ? "মাপা হয়নি" : `${num(Math.round(data.on_time_rate * 100))}%`}
                  sub={`${num(data.delivered_orders)}/${num(data.orders)}টি অর্ডার রিসিভ হয়েছে`} tone={data.on_time_rate !== null && data.on_time_rate < 0.7 ? "danger" : "neutral"} />
            <Stat label="মোট কিনেছেন" value={money(data.total_purchased)} />
            <Stat label="বাকি দেবেন" value={money(data.we_owe)} tone={Number(data.we_owe) > 0 ? "warn" : "success"} />
          </div>
          {data.delivered_orders === 0 && <Notice tone="info">এখনো কোনো অর্ডারের মাল রিসিভ হয়নি, তাই ডেলিভারি সময় মাপা যায়নি। আন্দাজ করে কিছু দেখানো হয় না।</Notice>}
          {data.price_movement.length > 0 && (
            <div>
              <strong>ক্রয়মূল্যের পরিবর্তন</strong>
              <DataTable rowKey="product" rows={data.price_movement} caption="দামের পরিবর্তন" columns={[
                { key: "product", label: "পণ্য", primary: true },
                { key: "previous_cost", label: "আগে", align: "right", render: (r) => (r.previous_cost === null ? "—" : money(r.previous_cost)) },
                { key: "last_cost", label: "এখন", align: "right", render: (r) => money(r.last_cost) },
                { key: "change_pct", label: "বদল", align: "right", render: (r) => (r.change_pct === null ? "প্রথম অর্ডার" : <Badge tone={r.change_pct > 0 ? "danger" : r.change_pct < 0 ? "success" : "neutral"}>{r.change_pct > 0 ? "▲" : r.change_pct < 0 ? "▼" : ""} {num(Math.abs(r.change_pct).toFixed(1))}%</Badge>) },
              ]} />
            </div>
          )}
          <div className="row">
            <a className="ui-btn ui-btn--secondary" href="#/purchases">অর্ডার দিন</a>
            {onPay && Number(data.we_owe) > 0 && <Button onClick={() => onPay(data)}>পেমেন্ট দিন</Button>}
          </div>
        </div>
      )}
    </Modal>
  );
}
