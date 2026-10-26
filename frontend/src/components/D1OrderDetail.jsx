import { useEffect, useState } from "react";

const taka=n=>"৳"+Number(n||0).toLocaleString("en-BD");
const labels={placed:"Order placed",confirmed:"Merchant confirmed",shipped:"Marked dispatched",fulfilled:"Marked fulfilled",cancelled:"Cancelled"};
export default function D1OrderDetail({id,load,onClose}) {
  const [detail,setDetail]=useState(null);
  const [error,setError]=useState("");
  useEffect(()=>{
    let active=true;setDetail(null);setError("");
    load(id).then(x=>{if(active)setDetail(x);}).catch(e=>{if(active)setError(e.message||"Unable to read order");});
    return ()=>{active=false;};
  },[id,load]);
  return <div className="dm-modal-bg" onClick={onClose}>
    <section role="dialog" aria-modal="true" aria-label="Order details and timeline" className="dm-panel dm-dialog dm-order-dialog" onClick={e=>e.stopPropagation()}>
      <div className="dm-order-top"><h2>Order & history</h2><button type="button" className="dm-secondary" onClick={onClose} aria-label="Close details">Close</button></div>
      {error&&<div className="dm-error" role="alert">{error}</div>}
      {!detail&&!error&&<p role="status" className="dm-muted">Loading order timeline…</p>}
      {detail&&<>
        <p><strong>{detail.order.order_number}</strong> · {taka(detail.order.total_bdt)} · <strong>{detail.order.status}</strong></p>
        <p className="dm-muted">Ordered: {detail.order.placed_at} · Payment: {detail.order.payment_method} (payment not verified)</p>
        {detail.order.shipping_phone&&<div className="dm-order-address"><strong>{detail.order.shipping_name}</strong>
          <a href={"tel:"+detail.order.shipping_phone}>{detail.order.shipping_phone}</a>
          <p>{detail.order.shipping_address}</p></div>}
        <h3>Items</h3>
        <div className="dm-scroll"><table><thead><tr><th>Product</th><th>Quantity</th><th>Total</th></tr></thead>
          <tbody>{detail.items.map((p,i)=><tr key={p.product_id+"-"+i}><td>{p.product_name}</td><td>{p.quantity}</td><td>{taka(p.line_total_bdt)}</td></tr>)}</tbody>
        </table></div>
        <h3>Recorded status events</h3>
        {detail.events.length===0?<p className="dm-muted">No event history.</p>:
        <ol className="dm-event-list">
          {detail.events.map((ev,i)=><li key={ev.created_at+"-"+i}><strong>{labels[ev.new_status]||ev.new_status}</strong>
            <time>{ev.created_at}</time>
            {ev.old_status&&<small>From {ev.old_status}</small>}
          </li>)}
        </ol>}
        <p className="dm-muted">These events record actions in this system, not carrier delivery confirmation or received cash.</p>
      </>}
    </section>
  </div>;
}
