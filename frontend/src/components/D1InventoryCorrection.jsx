import { useEffect, useState } from "react";

export default function D1InventoryCorrection({products,busy,onSave}) {
  const [product,setProduct]=useState("");
  const [delta,setDelta]=useState("");
  const [reason,setReason]=useState("restock");
  const [note,setNote]=useState("");
  useEffect(()=>{if(!products.some(p=>p.id===product))setProduct(products[0]?.id||"");},[products,product]);
  const selected=products.find(p=>p.id===product);
  const deltaNum=Number(delta);
  const projected=(selected?.stock_qty||0)+deltaNum;
  const valid=delta.trim()!==""&&Number.isInteger(deltaNum)&&deltaNum!==0&&Math.abs(deltaNum)<=10000&&projected>=0&&projected<=1000000;
  async function submit(e) {
    e.preventDefault();
    if(!valid)return;
    const ok=await onSave({product_id:product,delta:deltaNum,reason,note});
    if(ok){setDelta("");setNote("");}
  }
  return <section className="dm-panel" aria-label="Inventory correction">
    <h2>Audited stock adjustments</h2>
    <p className="dm-muted">Add stock deliveries or subtract damaged/missing units. Every adjustment is recorded by D1 with the actual before/after quantity. No purchase or payment is created.</p>
    {products.length===0?<p className="dm-muted">Add a product before correcting stock.</p>:
    <form className="dm-product-form" onSubmit={submit}>
      <label className="dm-field"><strong>Product</strong>
        <select required value={product} onChange={e=>setProduct(e.target.value)} className="dm-input">
          {products.map(p=><option key={p.id} value={p.id}>{p.name} · {p.sku} ({p.stock_qty} units)</option>)}
        </select>
      </label>
      <label className="dm-field"><strong>Quantity change (+ / −)</strong>
        <input className="dm-input" required type="number" min={-10000} max={10000} step="1" value={delta} onChange={e=>setDelta(e.target.value)} placeholder="+10 or -2"/>
      </label>
      <label className="dm-field"><strong>Reason</strong>
        <select className="dm-input" value={reason} onChange={e=>setReason(e.target.value)}>
          <option value="restock">Restock / received</option>
          <option value="damage">Damage / loss</option>
          <option value="stocktake">Stocktake correction</option>
          <option value="return">Return to stock</option>
          <option value="other">Other</option>
        </select>
      </label>
      <label className="dm-field"><strong>Internal note (optional)</strong>
        <input className="dm-input" maxLength={120} value={note} onChange={e=>setNote(e.target.value)} placeholder="Invoice/reference or explanation"/>
      </label>
      <div className="dm-correction-submit"><span className="dm-muted">Current: <strong>{selected?.stock_qty??0}</strong> · After: <strong>{valid?projected:"—"}</strong></span>
        <button type="submit" className="dm-btn" disabled={busy||!valid}>Record stock change</button>
      </div>
    </form>}
  </section>;
}
