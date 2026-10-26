import { useEffect, useState } from "react";

const taka = n => "৳" + Number(n||0).toLocaleString("en-BD");
const count = n => Number(n||0).toLocaleString("en-BD");
function KPI({label,value,hint}) {
  return <article className="dm-stat"><small>{label}</small><strong>{value}</strong>{hint&&<span>{hint}</span>}</article>;
}
export default function D1MerchantInsights({load,onStock}) {
  const [days,setDays]=useState(30);
  const [data,setData]=useState(null);
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(true);
  useEffect(()=>{
    let active=true;
    setBusy(true);setError("");
    load(days).then(v=>{if(active)setData(v);}).catch(e=>{if(active)setError(e.message||"Insights unavailable");}).finally(()=>{if(active)setBusy(false);});
    return ()=>{active=false;};
  },[days,load]);
  const stats=data?.summary||{};
  const maximum=Math.max(1,...(data?.daily||[]).map(row=>Number(row.booked_bdt||0)));
  return <section className="dm-stack" aria-label="Business insights">
    <div className="dm-panel dm-insight-heading">
      <div><h2>Business Insights</h2><p className="dm-muted">D1 order value, stock health and product demand. Booked values are not verified collected cash.</p></div>
      <label className="dm-field">Report window
        <select style={{padding:11,borderRadius:10,border:"1px solid var(--dm-line)",color:"var(--dm-text)",background:"var(--dm-surface)"}} value={days} onChange={e=>setDays(Number(e.target.value))}>
          <option value={7}>Last 7 days</option><option value={30}>Last 30 days</option><option value={90}>Last 90 days</option>
        </select>
      </label>
    </div>
    {busy&&<p role="status" className="dm-muted">Reading merchant analytics…</p>}
    {error&&<div role="alert" className="dm-error">{error}</div>}
    {!busy&&data&&<>
      <div className="dm-stats">
        <KPI label="Orders placed" value={count(stats.orders)}/>
        <KPI label="Booked order value" value={taka(stats.booked_bdt)} hint="Not money received"/>
        <KPI label="Completed order value" value={taka(stats.fulfilled_bdt)} hint="Not verified payment"/>
        <KPI label="Cancellation rate" value={(stats.cancellation_rate_pct||0)+"%"}/>
        <KPI label="Open orders" value={count(stats.open)}/>
        <KPI label="Average active order" value={taka(stats.avg_order_bdt)}/>
        <KPI label="Cancelled orders" value={count(stats.cancelled)}/>
        <KPI label="Low-stock SKUs" value={count(data.low_stock_count)} hint={data.low_stock_count_capped?"Showing first 50":""}/>
      </div>
      <div className="dm-panel">
        <h2>Daily order activity</h2>
        {data.daily.length===0?<p className="dm-muted">No order activity in this time range.</p>:
          <div className="dm-daily-bars" role="list" aria-label="Daily booked order values">
            {data.daily.map(row=><div className="dm-daily-bar" key={row.day} role="listitem" title={row.day+" · "+taka(row.booked_bdt)+" · "+row.orders+" orders"}>
              <div className="dm-daily-value">{taka(row.booked_bdt)}</div>
              <div className="dm-daily-track"><div className="dm-daily-fill" style={{height:Math.max(3,100*Number(row.booked_bdt||0)/maximum)+"%"}}/></div>
              <time>{row.day.slice(5)}</time>
            </div>)}
          </div>}
      </div>
      <div className="dm-insights-columns">
        <section className="dm-panel">
          <h2>Most-ordered products</h2>
          {data.top_products.length===0?<p className="dm-muted">No sold products in this period.</p>:
          <div className="dm-scroll"><table><thead><tr><th>Product</th><th>Units</th><th>Order value</th></tr></thead>
            <tbody>{data.top_products.map((p,i)=><tr key={p.product_id+"-"+i}><td>{p.product_name}</td><td>{count(p.units)}</td><td>{taka(p.amount_bdt)}</td></tr>)}</tbody>
          </table></div>}
        </section>
        <section className="dm-panel">
          <h2>Stock alerts</h2>
          <p className="dm-muted">Published products at or below their reorder threshold.</p>
          {data.low_stock.length===0?<p className="dm-muted">All published products are above their alert thresholds.</p>:<>
            <div className="dm-scroll"><table><thead><tr><th>Product</th><th>In stock</th><th>Alert at</th></tr></thead>
              <tbody>{data.low_stock.map(p=><tr key={p.id}><td>{p.name}</td><td><strong>{p.stock_qty}</strong></td><td>{p.reorder_point}</td></tr>)}</tbody>
            </table></div>
            <button type="button" className="dm-secondary" onClick={onStock}>Open inventory corrections</button>
          </>}
        </section>
      </div>
    </>}
  </section>;
}
