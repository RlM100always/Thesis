/** Browsable 32-shop Bangladesh-context simulation explorer.
 * All metrics are computed from the new integrated generated dataset, NOT
 * observed business records; raw invoice/stock ledgers are not deployed.
 */
import { useEffect, useMemo, useState } from "react";
import { api } from "../api";

const money = (v) => new Intl.NumberFormat("en-BD", {
  style: "currency", currency: "BDT", maximumFractionDigits: 0
}).format(Number(v || 0));
const number = (v) => new Intl.NumberFormat("en-BD").format(Number(v || 0));

const panel = {
  border: "1px solid var(--border, #dae2e8)",
  borderRadius: 14,
  padding: 18,
  background: "var(--surface, var(--card-bg, #fff))"
};
const subtle = {fontSize:13,opacity:.72,margin:"4px 0"};

function Stat({ label, value, hint }) {
  return (
    <div style={panel}>
      <div style={subtle}>{label}</div>
      <div style={{fontWeight:750,fontSize:24,fontVariantNumeric:"tabular-nums"}}>{value}</div>
      {hint && <div style={subtle}>{hint}</div>}
    </div>
  );
}
function Years({ years }) {
  const max = Math.max(1,...years.map(x=>x.net_sales_bdt));
  return <div style={{display:"grid",gap:14,marginTop:16}}>
    {years.map(item=><div key={item.year}>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",gap:8,marginBottom:6,fontSize:13}}>
        <strong>{item.year}</strong>
        <span>{money(item.net_sales_bdt)} · {number(item.orders)} orders</span>
      </div>
      <div style={{height:11,background:"var(--border,#e2e8f0)",borderRadius:8,overflow:"hidden"}}>
        <div style={{height:"100%",width:`${(100*item.net_sales_bdt/max).toFixed(1)}%`,
          background:"#328c70",borderRadius:8}}/>
      </div>
    </div>)}
  </div>;
}

export default function ResearchPortal() {
  const [state,setState] = useState({loading:true,shops:[],error:null,storage:null});
  const [query,setQuery] = useState("");
  const [division,setDivision] = useState("all");
  const [selectedId,setSelectedId] = useState(null);
  const [sort,setSort] = useState("shop_id");

  useEffect(() => {
    Promise.all([api.portalShops(),api.portalStorage()])
      .then(([shops,storage]) => {
        setState({loading:false,shops:shops.shops||[],error:null,storage});
      })
      .catch(e=>setState({loading:false,shops:[],storage:null,error:String(e)}));
  }, []);

  const divisions = useMemo(()=>
    [...new Set(state.shops.map(s=>s.division))].sort(),[state.shops]);
  const filtered = useMemo(() => {
    const q=query.trim().toLocaleLowerCase();
    return state.shops
      .filter(s=> (division==="all"||s.division===division)
        && (!q||[s.shop_name,s.district,s.division,s.shop_id].join(" ").toLocaleLowerCase().includes(q)))
      .sort((a,b)=>sort==="revenue" ? b.net_sales_bdt-a.net_sales_bdt
        : sort==="orders" ? b.orders-a.orders : a.shop_id.localeCompare(b.shop_id));
  },[state.shops,query,division,sort]);
  const chosen = filtered.find(s=>s.shop_id===selectedId)
    || filtered[0] || null;
  const total = useMemo(()=>state.shops.reduce((z,s)=>({
    revenue:z.revenue+s.net_sales_bdt,
    orders:z.orders+s.orders,
    movements:z.movements+s.stock_movements,
    purchase_orders:z.purchase_orders+s.purchase_orders
  }),{revenue:0,orders:0,movements:0,purchase_orders:0}),[state.shops]);

  return <main style={{maxWidth:1240,margin:"18px auto 56px",padding:"12px 18px"}}>
    <div style={{marginBottom:12}}><a href="#/" style={{fontSize:13}}>← ওয়েবসাইটে ফিরুন</a></div>
    <header style={{display:"flex",justifyContent:"space-between",flexWrap:"wrap",alignItems:"start",gap:18,marginBottom:20}}>
      <div>
        <div style={{fontSize:12,fontWeight:700,color:"#27826a",letterSpacing:1,textTransform:"uppercase"}}>
          Research Dataset Explorer
        </div>
        <h1 style={{margin:"6px 0 8px"}}>বাংলাদেশ SME · 32 Store Explorer</h1>
        <p style={{margin:0,maxWidth:800}}>
          ২০২৩–২০২৫-এর নতুন integrated simulation dataset থেকে দোকানভিত্তিক বিক্রি,
          customer, purchase এবং stock-এর যাচাই করা summary দেখুন।
        </p>
      </div>
      <span style={{border:"1px solid #e4b575",padding:"8px 12px",borderRadius:24,
        background:"#fff7e8",color:"#794500",fontSize:12,fontWeight:700}}>
        100% SYNTHETIC · NOT REAL SHOPS
      </span>
    </header>

    {state.loading ? <p role="status">দোকানের data load হচ্ছে…</p> :
     state.error ? <div role="alert" style={panel}>
        <strong>দোকানের data load হয়নি।</strong>
        <p>{state.error}</p>
        <p>Server deploy না হয়ে থাকলে GitHub data update হওয়া সত্ত্বেও এই page ফাঁকা থাকতে পারে।</p>
      </div> : <>
      <section style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(175px,1fr))",gap:12,marginBottom:20}}>
        <Stat label="Simulated stores" value={number(state.shops.length)} hint="8 Bangladesh divisions"/>
        <Stat label="Historical sales orders" value={number(total.orders)} hint="2023–2025 · generated"/>
        <Stat label="Simulated net sales" value={money(total.revenue)} hint="Not verified market revenue"/>
        <Stat label="Stock movements" value={number(total.movements)} hint="Simulated stock ledger"/>
        <Stat label="Purchase orders" value={number(total.purchase_orders)} hint="Simulated purchasing"/>
      </section>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",flexWrap:"wrap",gap:12,marginBottom:14}}>
        <h2 style={{margin:0}}>দোকানের তালিকা <small style={{fontSize:14,opacity:.7}}>({filtered.length})</small></h2>
        <div style={{display:"flex",gap:8,flexWrap:"wrap",alignItems:"center"}}>
          <input aria-label="Search stores" placeholder="দোকান, ID, জেলা খুঁজুন"
            value={query} onChange={e=>setQuery(e.target.value)}
            style={{padding:"10px 12px",border:"1px solid #cbd5e1",borderRadius:9,minWidth:180,maxWidth:"100%"}}/>
          <select aria-label="Division" value={division} onChange={e=>setDivision(e.target.value)}
            style={{padding:"10px",borderRadius:9,border:"1px solid #cbd5e1"}}>
            <option value="all">সব বিভাগ</option>
            {divisions.map(v=><option key={v} value={v}>{v}</option>)}
          </select>
          <select aria-label="Sort stores" value={sort} onChange={e=>setSort(e.target.value)}
            style={{padding:"10px",borderRadius:9,border:"1px solid #cbd5e1"}}>
            <option value="shop_id">Store ID</option>
            <option value="revenue">Highest sales</option>
            <option value="orders">Most orders</option>
          </select>
        </div>
      </div>

      <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(min(100%, 360px),1fr))",gap:16,alignItems:"start"}}>
        <section style={{display:"grid",gridTemplateColumns:"repeat(auto-fill,minmax(230px,1fr))",gap:10}}>
          {filtered.map(s=><button type="button" key={s.shop_id} onClick={()=>setSelectedId(s.shop_id)}
            aria-pressed={chosen?.shop_id===s.shop_id}
            style={{...panel,textAlign:"left",cursor:"pointer",color:"inherit",width:"100%",
              border:chosen?.shop_id===s.shop_id?"2px solid #338d71":panel.border,
              boxShadow:chosen?.shop_id===s.shop_id?"0 0 0 2px #338d7122":"none"}}>
            <div style={{display:"flex",justifyContent:"space-between",gap:8,fontSize:12,opacity:.7}}>
              <span>{s.shop_id}</span><span>{s.division}</span>
            </div>
            <div style={{fontWeight:750,margin:"9px 0 6px",lineHeight:1.35}}>{s.shop_name}</div>
            <div style={subtle}>{s.district} · {number(s.orders)} orders</div>
            <div style={{fontWeight:700,color:"#16866a",marginTop:12}}>{money(s.net_sales_bdt)}</div>
          </button>)}
          {filtered.length===0 && <p>এই filter-এ কোনো দোকান পাওয়া যায়নি।</p>}
        </section>
        <section style={{...panel,position:"sticky",top:12,maxHeight:"calc(100vh - 28px)",overflowY:"auto"}}>
          {chosen ? <>
            <div style={{fontSize:12,opacity:.7}}>{chosen.shop_id} · {chosen.division} / {chosen.district}</div>
            <h2 style={{margin:"6px 0 12px"}}>{chosen.shop_name}</h2>
            <p style={subtle}>সম্পূর্ণ CSV থেকে গণনা করা shop-level summary; live merchant account নয়।</p>
            <div style={{display:"grid",gridTemplateColumns:"repeat(2,minmax(0,1fr))",gap:10,margin:"20px 0"}}>
              <Stat label="Sales orders" value={number(chosen.orders)}/>
              <Stat label="Buyers with ID" value={number(chosen.unique_buyers)}/>
              <Stat label="Sales lines" value={number(chosen.sales_lines)}/>
              <Stat label="Units sold" value={number(chosen.units_sold)}/>
              <Stat label="Purchases" value={number(chosen.purchase_orders)}/>
              <Stat label="Stock movement records" value={number(chosen.stock_movements)}/>
              <Stat label="Stock units (net ledger)" value={number(chosen.stock_units_end)}/>
              <Stat label="Unmet-demand simulations" value={number(chosen.unmet_events)}/>
            </div>
            <h3 style={{margin:"8px 0 5px"}}>Yearly net sales · BDT</h3>
            <Years years={chosen.years||[]}/>
            {chosen.top_sku_example && <div style={{marginTop:22}}>
              <h3>Top-selling product example</h3>
              <p style={{margin:"4px 0"}}><strong>{chosen.top_sku_example.name}</strong></p>
              <p style={subtle}>SKU: {chosen.top_sku_example.sku_id} · {number(chosen.top_sku_example.units)} units · {money(chosen.top_sku_example.revenue_bdt)} revenue</p>
            </div>}
            {chosen.recent_invoice_example && <div style={{marginTop:20}}>
              <h3>Latest invoice example</h3>
              <p style={{margin:"4px 0"}}><strong>{chosen.recent_invoice_example.order_id}</strong> · {chosen.recent_invoice_example.date}</p>
              <p style={subtle}>{money(chosen.recent_invoice_example.amount_bdt)} · {chosen.recent_invoice_example.status} · Customer ID: {chosen.recent_invoice_example.customer_id||"Walk-in"}</p>
            </div>}
          </> : <p>একটি দোকান নির্বাচন করুন।</p>}
        </section>
      </div>
      <p style={{...subtle,marginTop:25,lineHeight:1.6}}>
        <strong>Research integrity:</strong> এখানে প্রত্যেকটি দোকান ও invoice কৃত্রিম। Store summaries,
        yearly aggregates এবং sample invoice দেখানো হচ্ছে; সম্পূর্ণ ৩,৬৫,৪৪৭টি raw order
        বা পুরো inventory ledger website database-এ এখনো import হয়নি। আগের trained model
        পুনরুদ্ধার করা হয়নি।
      </p>
    </>}
  </main>;
}
