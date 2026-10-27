import { useCallback, useState } from "react";

const BASE=(import.meta.env.VITE_D1_COMMERCE_URL || "https://bsmart-commerce-api.bcs-written-rakib.workers.dev").replace(/\/$/,"");
const money=n=>"৳"+Number(n||0).toLocaleString("bn-BD");
const STATUS={placed:"অর্ডার জমা",confirmed:"নিশ্চিত",processing:"প্রস্তুত হচ্ছে",ready:"পণ্য প্রস্তুত",dispatched:"পাঠানো হয়েছে",shipped:"পাঠানো হয়েছে",fulfilled:"সম্পন্ন",delivered:"ডেলিভারি সম্পন্ন",cancelled:"বাতিল"};
const ORDER_ACTIONS={
  placed:[{status:"confirmed",label:"নিশ্চিত"},{status:"cancelled",label:"বাতিল",danger:true}],
  confirmed:[{status:"processing",label:"প্রস্তুতি শুরু"},{status:"cancelled",label:"বাতিল",danger:true}],
  processing:[{status:"ready",label:"প্রস্তুত"},{status:"cancelled",label:"বাতিল",danger:true}],
  ready:[{status:"dispatched",label:"পাঠানো হয়েছে"}],
  dispatched:[{status:"delivered",label:"ডেলিভারি সম্পন্ন"}],
  shipped:[{status:"delivered",label:"ডেলিভারি সম্পন্ন"}],
};
const RETURN={requested:"অনুরোধ এসেছে",approved:"অনুমোদিত",rejected:"প্রত্যাখ্যাত",received:"পণ্য গ্রহণ",closed_demo:"বন্ধ"};
const style={
  page:{minHeight:"100vh",background:"var(--bg,#f6f8f7)",color:"var(--text,#14251d)",padding:"24px 16px 48px",fontFamily:"inherit"},
  shell:{maxWidth:1320,margin:"0 auto"},
  panel:{background:"var(--surface,#fff)",border:"1px solid var(--border,#dfe7e2)",borderRadius:16,padding:18,marginBottom:14},
  input:{width:"100%",boxSizing:"border-box",padding:"11px 12px",borderRadius:10,border:"1px solid var(--border,#dfe7e2)",background:"var(--bg,#fff)",color:"var(--text,#14251d)",font:"inherit"},
  button:{padding:"9px 13px",borderRadius:9,border:"1px solid var(--border,#dfe7e2)",background:"var(--surface,#fff)",color:"var(--text,#14251d)",font:"inherit",fontWeight:700,cursor:"pointer"},
  primary:{padding:"10px 14px",borderRadius:9,border:0,background:"#087e59",color:"#fff",font:"inherit",fontWeight:750,cursor:"pointer"},
  table:{width:"100%",borderCollapse:"collapse",fontSize:12,minWidth:680},
  cell:{padding:"10px 8px",borderBottom:"1px solid var(--border,#dfe7e2)",textAlign:"left",verticalAlign:"top"},
};
async function call(path,key,{method="GET",body}={}) {
  const response=await fetch(BASE+path,{method,headers:{"Content-Type":"application/json",Authorization:"Bearer "+key},...(body!==undefined?{body:JSON.stringify(body)}:{})});
  const data=await response.json().catch(()=>({}));
  if(!response.ok)throw new Error(data.detail||"অনুরোধটি সম্পন্ন করা যায়নি");
  return data;
}
function Table({columns,rows,empty="কোনো তথ্য পাওয়া যায়নি"}) {
  return <div style={{overflowX:"auto"}}>{!rows.length?<p style={{color:"var(--text-muted,#65736b)",padding:16}}>{empty}</p>:<table style={style.table}><thead><tr>{columns.map(c=><th key={c.label} style={{...style.cell,fontWeight:800,background:"var(--bg,#f6f8f7)"}}>{c.label}</th>)}</tr></thead><tbody>{rows.map((row,i)=><tr key={row.id||row.slug||row.order_number||i}>{columns.map(c=><td key={c.label} style={style.cell}>{c.render?c.render(row):row[c.key]??"—"}</td>)}</tr>)}</tbody></table>}</div>;
}
export default function D1PlatformAdmin() {
  const [secret,setSecret]=useState("");
  const [ready,setReady]=useState(false);
  const [busy,setBusy]=useState(false);
  const [tab,setTab]=useState("overview");
  const [error,setError]=useState("");
  const [notice,setNotice]=useState("");
  const [overview,setOverview]=useState(null);
  const [stores,setStores]=useState([]);
  const [orders,setOrders]=useState([]);
  const [customers,setCustomers]=useState([]);
  const [returns,setReturns]=useState([]);
  const [audit,setAudit]=useState([]);
  const refresh=useCallback(async key=>{
    const [a,b,c,d,e,f]=await Promise.all([
      call("/api/platform-admin/overview",key),call("/api/platform-admin/stores",key),
      call("/api/platform-admin/orders",key),call("/api/platform-admin/customers",key),
      call("/api/platform-admin/returns",key),call("/api/platform-admin/audit",key),
    ]);
    setOverview(a);setStores(b.stores||[]);setOrders(c.orders||[]);
    setCustomers(d.customers||[]);setReturns(e.returns||[]);setAudit(f.audit||[]);
    setReady(true);
  },[]);
  async function connect(event) {
    event?.preventDefault();setBusy(true);setError("");setNotice("");
    try { await refresh(secret);setNotice("D1 platform admin authenticated. The key remains in memory only."); }
    catch(e){setReady(false);setError(e.message);}
    finally{setBusy(false);}
  }
  async function run(action,message) {
    setBusy(true);setError("");setNotice("");
    try { await action();await refresh(secret);setNotice(message); }
    catch(e){setError(e.message);}
    finally{setBusy(false);}
  }
  const metrics=overview?.metrics||{};
  return <main style={style.page}><div style={style.shell}>
    <header style={{display:"flex",alignItems:"center",justifyContent:"space-between",gap:12,flexWrap:"wrap",marginBottom:18}}>
      <div><div style={{fontSize:11,letterSpacing:2,textTransform:"uppercase",fontWeight:800,color:"#087e59"}}>B-SMART · PRIVILEGED CONTROL</div><h1 style={{margin:"5px 0",fontSize:28}}>D1 Platform Admin</h1><p style={{margin:0,fontSize:13,color:"var(--text-muted,#65736b)"}}>Cloudflare D1 storefront, customer ও order পরিচালনা; অনুমোদিত দোকানে COD/manual delivery।</p></div>
      <div style={{display:"flex",gap:8,flexWrap:"wrap"}}><a href="#/stores" style={{...style.button,textDecoration:"none"}}>দোকান ডিরেক্টরি</a>{ready&&<button style={style.button} disabled={busy} onClick={()=>run(()=>refresh(secret),"সর্বশেষ তথ্য লোড হয়েছে")}>↻ রিফ্রেশ</button>}</div>
    </header>
    <div style={{...style.panel,borderColor:"#e7b55b",background:"color-mix(in srgb,#f59e0b 7%,var(--surface,#fff))"}}>
      <strong>নিরাপত্তা ও সীমাবদ্ধতা</strong><p style={{fontSize:12,lineHeight:1.7,margin:"5px 0 0"}}>Admin key Cloudflare Worker-এর <code>PLATFORM_ADMIN_KEY</code> secret-এর সঙ্গে মিলতে হবে। এই পেজে key URL বা local storage-এ রাখা হয় না। ডেমো order value বাস্তব আয় নয়; payment/refund বা delivery provider সংযুক্ত নয়।</p>
    </div>
    {!ready?<section style={style.panel}><h2 style={{fontSize:18,marginTop:0}}>Platform admin authentication</h2><form onSubmit={connect} style={{display:"grid",gap:12,maxWidth:560}}><label style={{fontSize:12,fontWeight:750}}>Worker secret key<input style={{...style.input,marginTop:6}} type="password" autoComplete="off" value={secret} onChange={e=>setSecret(e.target.value)} required minLength={32} placeholder="Cloudflare PLATFORM_ADMIN_KEY"/></label><button style={style.primary} disabled={busy||secret.length<32}>{busy?"যাচাই হচ্ছে…":"নিরাপদভাবে প্রবেশ করুন"}</button></form></section>:
      <>
        <div style={{display:"flex",gap:6,overflowX:"auto",paddingBottom:12,marginBottom:4}}>{[["overview","সারসংক্ষেপ"],["stores","দোকান"],["orders","অর্ডার"],["customers","ক্রেতা"],["returns","ফেরত"],["audit","Audit log"]].map(([id,label])=><button key={id} style={{...style.button,whiteSpace:"nowrap",background:tab===id?"#087e59":"var(--surface,#fff)",color:tab===id?"#fff":"var(--text,#14251d)",borderColor:tab===id?"#087e59":undefined}} onClick={()=>setTab(id)}>{label}</button>)}</div>
        {tab==="overview"&&<section style={style.panel}><h2 style={{marginTop:0,fontSize:18}}>D1 commerce overview</h2><div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(160px,1fr))",gap:10}}>{[
          ["সক্রিয় দোকান",metrics.stores_active,"মোট "+(metrics.stores_total||0)+"টি"],
          ["প্রকাশিত পণ্য",metrics.products_listed,"মোট "+(metrics.products_total||0)+"টি"],
          ["Customer accounts",metrics.customers_total,"D1-তে সংরক্ষিত"],
          ["মোট অর্ডার",metrics.orders_total,"বাতিল "+(metrics.orders_cancelled||0)+"টি"],
          ["Demo order value",money(metrics.demo_order_value_bdt),"বাস্তব আয় নয়"],
          ["Open returns",metrics.returns_open,"অনুমোদনের অপেক্ষায়"],
          ["Unread messages",metrics.unread_customer_messages,"Merchant inbox"],
        ].map(([label,value,tip])=><div key={label} style={{border:"1px solid var(--border,#dfe7e2)",borderRadius:12,padding:14}}><div style={{fontSize:11,color:"var(--text-muted,#65736b)"}}>{label}</div><strong style={{display:"block",fontSize:23,margin:"6px 0"}}>{value??0}</strong><div style={{fontSize:10,color:"var(--text-muted,#65736b)"}}>{tip}</div></div>)}</div></section>}
        {tab==="stores"&&<section style={style.panel}><h2 style={{marginTop:0,fontSize:18}}>Store moderation</h2><Table rows={stores} columns={[
          {label:"দোকান",render:r=><><strong>{r.name}</strong><div style={{fontSize:11,opacity:.7}}>{r.slug}</div><div style={{fontSize:10,opacity:.7}}>{r.owner_email||"Seeded/demo store"}</div></>},
          {label:"Catalogue",render:r=><>{r.products_count} products<br/>{r.orders_count} orders</>},
          {label:"ধরন",render:r=>r.is_demo?"Demo":"Operational"},
          {label:"অবস্থা",render:r=><strong style={{color:r.is_active?"#15803d":"#dc2626"}}>{r.is_active?"Active":"Suspended"}</strong>},
          {label:"করণীয়",render:r=><div style={{display:"flex",gap:5,flexWrap:"wrap"}}><button style={style.button} disabled={busy} onClick={()=>run(()=>call("/api/platform-admin/stores/"+encodeURIComponent(r.id),secret,{method:"PATCH",body:{is_active:!r.is_active,reason:"Changed through D1 platform admin"}}),r.is_active?"দোকান স্থগিত করা হয়েছে":"দোকান সক্রিয় করা হয়েছে")}>{r.is_active?"স্থগিত করুন":"সক্রিয় করুন"}</button>{r.owner_email&&<button style={{...style.button,color:r.is_demo?"#087e59":"#b91c1c"}} disabled={busy} onClick={()=>{const promote=!!r.is_demo;if(!window.confirm(promote?"এই merchant-owned দোকানে COD checkout চালু ও দোকান প্রকাশ করবেন? অনলাইন পেমেন্ট/কুরিয়ার সংযুক্ত নয়।":"এই দোকানকে আবার demo-only করবেন?"))return;run(()=>call("/api/platform-admin/stores/"+encodeURIComponent(r.id),secret,{method:"PATCH",body:promote?{is_demo:false,is_active:true,confirm_production:"ENABLE COD CHECKOUT",reason:"Admin approved manual COD fulfilment"}:{is_demo:true,reason:"Returned to demo mode"}}),promote?"COD checkout চালু ও দোকান প্রকাশ হয়েছে":"দোকান demo-only করা হয়েছে");}}>{r.is_demo?"COD চালু ও প্রকাশ":"Demo-তে ফেরত"}</button>}</div>},
        ]}/></section>}
        {tab==="orders"&&<section style={style.panel}><h2 style={{marginTop:0,fontSize:18}}>Order oversight</h2><p style={{fontSize:12,color:"var(--text-muted,#65736b)"}}>সব অর্ডারের মূল্য নমুনা হিসাব। Cancel করলে D1 trigger সংশ্লিষ্ট demo stock ফিরিয়ে দেয়।</p><Table rows={orders} columns={[
          {label:"অর্ডার",render:r=><><strong>{r.order_number}</strong><div style={{fontSize:11,opacity:.7}}>{r.store_name}</div><div style={{fontSize:10,opacity:.7}}>{r.customer_name||"Guest"}</div></>},
          {label:"তারিখ",key:"placed_at"},
          {label:"মূল্য",render:r=>money(r.total_bdt)},
          {label:"অবস্থা",render:r=><>{STATUS[r.status]||r.status}{r.status_note&&<div style={{fontSize:10,opacity:.75,marginTop:4}}>{r.status_note}</div>}{r.cancellation_reason&&r.status==="cancelled"&&<div style={{fontSize:10,opacity:.75,marginTop:4}}>কারণ: {r.cancellation_reason}</div>}</>},
          {label:"করণীয়",render:r=>(ORDER_ACTIONS[r.status]||[]).length?<div style={{display:"flex",gap:5,flexWrap:"wrap"}}>{ORDER_ACTIONS[r.status].map(action=><button key={action.status} style={{...style.button,...(action.danger?{color:"#b91c1c"}:{})}} disabled={busy} onClick={()=>run(()=>call("/api/platform-admin/orders/"+encodeURIComponent(r.id),secret,{method:"PATCH",body:{status:action.status,reason:action.status==="cancelled"?"Platform admin cancellation":"Platform admin status update"}}),action.status==="cancelled"?"অর্ডার বাতিল হয়েছে":(STATUS[action.status]||action.status)+" হয়েছে")}>{action.label}</button>)}</div>:"—"},
        ]}/></section>}
        {tab==="customers"&&<section style={style.panel}><h2 style={{marginTop:0,fontSize:18}}>Customer accounts</h2><Table rows={customers} columns={[
          {label:"ক্রেতা",render:r=><><strong>{r.display_name}</strong><div style={{fontSize:11,opacity:.7}}>{r.email||"ইমেইল নেই"}</div><div style={{fontSize:11,opacity:.7}}>{r.phone||"ফোন নেই"}</div></>},
          {label:"অ্যাকাউন্ট তৈরি",key:"created_at"},
          {label:"অর্ডার",key:"orders_count"},
          {label:"বার্তা",key:"messages_count"},
        ]}/></section>}
        {tab==="returns"&&<section style={style.panel}><h2 style={{marginTop:0,fontSize:18}}>Return oversight</h2><Table rows={returns} columns={[
          {label:"অর্ডার / দোকান",render:r=><><strong>{r.order_number}</strong><div style={{fontSize:11,opacity:.7}}>{r.store_name}</div></>},
          {label:"ক্রেতা",render:r=><>{r.customer_name}<div style={{fontSize:10,opacity:.7}}>{r.customer_email}</div></>},
          {label:"কারণ",key:"reason"},
          {label:"অবস্থা",render:r=>RETURN[r.status]||r.status},
          {label:"নোট",render:r=>r.merchant_note||r.customer_note||"—"},
        ]}/></section>}
        {tab==="audit"&&<section style={style.panel}><h2 style={{marginTop:0,fontSize:18}}>Platform audit log</h2><Table rows={audit} columns={[
          {label:"সময়",key:"created_at"},{label:"Action",key:"action"},{label:"Target",render:r=><>{r.target_type}<div style={{fontSize:10,opacity:.7}}>{r.target_id}</div></>},{label:"Details",render:r=><code style={{whiteSpace:"pre-wrap",overflowWrap:"anywhere"}}>{r.details}</code>},
        ]}/></section>}
      </>
    }
    {error&&<div role="alert" style={{...style.panel,color:"#b91c1c",borderColor:"#fecaca",marginTop:12}}>{error}</div>}
    {notice&&<div role="status" style={{...style.panel,color:"#15803d",marginTop:12}}>{notice}</div>}
    <footer style={{fontSize:11,color:"var(--text-muted,#65736b)",padding:"12px 2px"}}>D1 Platform Admin · Sensitive customer data is visible only after secret authentication. Do not use demo order value as revenue.</footer>
  </div></main>;
}
