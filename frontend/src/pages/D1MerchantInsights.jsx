import { useEffect, useMemo, useState } from "react";

const BASE=(import.meta.env.VITE_D1_COMMERCE_URL || "https://bsmart-commerce-api.bcs-written-rakib.workers.dev").replace(/\/$/,"");
const money=n=>"৳"+Number(n||0).toLocaleString("bn-BD");
const dateDhaka=()=>new Date(Date.now()+6*60*60*1000).toISOString().slice(0,10);
const shift=(date,days)=>{const d=new Date(date+"T00:00:00Z");d.setUTCDate(d.getUTCDate()+days);return d.toISOString().slice(0,10);};
async function call(path,token){
 const response=await fetch(BASE+path,{headers:{Authorization:"Bearer "+token}});
 const data=await response.json().catch(()=>({}));
 if(!response.ok)throw new Error(data.detail||"তথ্য আনা যায়নি।");
 return data;
}
function Metric({label,value,tip}){
 return <div className="dm-stat"><small>{label}</small><strong>{value}</strong>{tip&&<span>{tip}</span>}</div>;
}
function Table({headers,rows,empty}){
 return <div className="dm-scroll">{!rows?.length?<p className="dm-muted">{empty||"কোনো তথ্য নেই।"}</p>:<table><thead><tr>{headers.map(h=><th key={h}>{h}</th>)}</tr></thead><tbody>{rows}</tbody></table>}</div>;
}
export default function D1MerchantInsights({token,mode="analytics"}){
 const today=dateDhaka();
 const [from,setFrom]=useState(()=>shift(today,-29));
 const [to,setTo]=useState(today);
 const [data,setData]=useState(null);
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState("");
 useEffect(()=>{
  let live=true;
  if(!token)return;
  setBusy(true);setError("");
  const path=mode==="alerts"?"/api/merchant/inventory-alerts":"/api/merchant/analytics?from="+encodeURIComponent(from)+"&to="+encodeURIComponent(to);
  call(path,token).then(value=>{if(live)setData(value);}).catch(e=>{if(live){setData(null);setError(e.message);}}).finally(()=>{if(live)setBusy(false);});
  return ()=>{live=false;};
 },[token,mode,from,to]);
 const daily=data?.daily||[];
 const maxSales=useMemo(()=>Math.max(1,...daily.map(x=>Number(x.order_value_bdt||0))),[daily]);
 if(mode==="alerts"){
  const summary=data?.summary||{};
  const alerts=data?.alerts||[];
  return <div className="dm-stack">
   <section className="dm-panel"><h2>মজুত সতর্কতা</h2><p className="dm-muted">পণ্যের বর্তমান মজুত ও নির্ধারিত reorder level Cloudflare D1 থেকে সরাসরি দেখানো হচ্ছে।</p>
    {error&&<p className="dm-error" role="alert">{error}</p>}
    {busy&&!data&&<p className="dm-muted">মজুত তথ্য আনা হচ্ছে…</p>}
    <div className="dm-stats">
     <Metric label="প্রকাশিত পণ্য" value={summary.listed_products||0}/>
     <Metric label="মোট ইউনিট" value={Number(summary.stock_units||0).toLocaleString("en-BD")}/>
     <Metric label="কম স্টক" value={summary.low_stock_count||0}/>
     <Metric label="স্টক শেষ" value={summary.out_of_stock_count||0}/>
    </div>
   </section>
   <section className="dm-panel"><h2>পুনরায় সংগ্রহ প্রয়োজন ({alerts.length})</h2>
    <Table headers={["পণ্য","SKU","বর্তমান মজুত","সতর্কতার সীমা","অবস্থা"]} rows={alerts.map(p=><tr key={p.id}><td><strong>{p.name}</strong><div className="dm-muted">{p.category||"—"}</div></td><td>{p.sku}</td><td>{p.stock_qty} {p.unit_label||"pcs"}</td><td>{p.reorder_level}</td><td><strong>{p.alert_type==="out_of_stock"?"স্টক শেষ":"কম স্টক"}</strong></td></tr>)} empty="কোনো কম-স্টক পণ্য নেই।"/>
   </section>
   <section className="dm-panel"><h2>সাম্প্রতিক স্টক মুভমেন্ট</h2>
    <Table headers={["সময়","পণ্য","পরিবর্তন","কারণ"]} rows={(data?.movements||[]).map(m=><tr key={m.id}><td>{m.created_at}</td><td>{m.product_name||m.product_id}</td><td>{Number(m.quantity_change)>0?"+":""}{m.quantity_change}</td><td>{m.reason||"—"}</td></tr>)} empty="এখনো কোনো stock movement নেই."/>
   </section>
   <section className="dm-panel"><h2>ম্যানুয়াল স্টক সংশোধন</h2>
    <Table headers={["সময়","পণ্য","আগে","পরে","পরিবর্তন","কারণ"]} rows={(data?.adjustments||[]).map(m=><tr key={m.id}><td>{m.created_at}</td><td>{m.product_name||m.product_id}</td><td>{m.old_quantity}</td><td>{m.new_quantity}</td><td>{m.delta>0?"+":""}{m.delta}</td><td>{m.reason||"—"}</td></tr>)} empty="এখনো কোনো ম্যানুয়াল সংশোধন নেই."/>
   </section>
  </div>;
 }
 const summary=data?.summary||{};
 const categories=data?.categories||[];
 const top=data?.top_products||[];
 return <div className="dm-stack">
  <section className="dm-panel"><h2>বিক্রয় বিশ্লেষণ</h2><p className="dm-muted">সময়কাল নির্বাচন করুন। অর্ডারের তারিখ বাংলাদেশ সময় (Asia/Dhaka) অনুযায়ী গণনা করা হয়। বাতিল অর্ডার বিক্রয়মূল্য থেকে বাদ থাকে।</p>
   <div className="dm-fields" style={{gridTemplateColumns:"repeat(auto-fit,minmax(180px,1fr))"}}>
    <label className="dm-field"><strong>শুরুর তারিখ</strong><input type="date" value={from} max={to} onChange={e=>setFrom(e.target.value)}/></label>
    <label className="dm-field"><strong>শেষ তারিখ</strong><input type="date" value={to} min={from} max={today} onChange={e=>setTo(e.target.value)}/></label>
   </div>
   {error&&<p className="dm-error" role="alert">{error}</p>}
   {busy&&!data&&<p className="dm-muted">বিশ্লেষণ তৈরি হচ্ছে…</p>}
   <div className="dm-stats">
    <Metric label="মোট অর্ডার" value={summary.orders_total||0}/>
    <Metric label="অর্ডার মূল্য" value={money(summary.order_value_bdt)} tip="বাতিল অর্ডার বাদ"/>
    <Metric label="আদায় নিশ্চিত" value={money(summary.collected_bdt)} tip="merchant-confirmed collection"/>
    <Metric label="COD আদায় বাকি" value={money(summary.pending_cod_bdt)}/>
    <Metric label="গড় অর্ডার মূল্য" value={money(summary.average_order_bdt)}/>
    <Metric label="স্বতন্ত্র ক্রেতা" value={summary.customers||0}/>
    <Metric label="পুনরায় অর্ডারকারী" value={summary.repeat_customers||0}/>
    <Metric label="বাতিল অর্ডার" value={summary.cancelled_orders||0}/>
   </div>
  </section>
  <section className="dm-panel"><h2>দিনভিত্তিক বিক্রয়</h2>
   {!daily.length?<p className="dm-muted">এই সময়কালে কোনো সম্পন্ন অর্ডার নেই।</p>:<div style={{display:"grid",gap:9}}>
    {daily.map(row=><div key={row.day} style={{display:"grid",gridTemplateColumns:"92px minmax(0,1fr) auto",gap:10,alignItems:"center",fontSize:12}}>
     <span>{row.day}</span>
     <div style={{height:12,background:"var(--dm-soft)",borderRadius:20,overflow:"hidden"}}><div style={{height:"100%",width:(Number(row.order_value_bdt||0)/maxSales*100)+"%",background:"var(--dm-accent,#087e59)",borderRadius:20,minWidth:row.order_value_bdt?3:0}}/></div>
     <strong>{money(row.order_value_bdt)}</strong>
    </div>)}
   </div>}
  </section>
  <section className="dm-panel"><h2>সেরা বিক্রিত পণ্য</h2>
   <Table headers={["পণ্য","বিক্রিত ইউনিট","বিক্রয় মূল্য"]} rows={top.map(p=><tr key={p.product_id}><td>{p.name}</td><td>{p.units_sold}</td><td>{money(p.sales_bdt)}</td></tr>)} empty="এই সময়ে পণ্য বিক্রি হয়নি."/>
  </section>
  <section className="dm-panel"><h2>বিভাগভিত্তিক বিক্রয়</h2>
   <Table headers={["বিভাগ","বিক্রিত ইউনিট","বিক্রয় মূল্য"]} rows={categories.map((p,i)=><tr key={p.category||i}><td>{p.category||"অন্যান্য"}</td><td>{p.units_sold}</td><td>{money(p.sales_bdt)}</td></tr>)} empty="বিভাগভিত্তিক বিক্রয়ের তথ্য নেই."/>
  </section>
  <section className="dm-panel"><h2>বর্তমান মজুতের মূল্য</h2>
   <div className="dm-stats"><Metric label="প্রকাশিত পণ্য" value={data?.inventory?.listed_products||0}/><Metric label="মজুত ইউনিট" value={data?.inventory?.stock_units||0}/><Metric label="কম স্টক" value={data?.inventory?.low_stock_count||0}/><Metric label="মজুতের সম্ভাব্য বিক্রয়মূল্য" value={money(data?.inventory?.stock_retail_value_bdt)}/></div>
  </section>
 </div>;
}
