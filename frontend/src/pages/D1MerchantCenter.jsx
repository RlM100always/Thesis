import { useCallback, useEffect, useMemo, useState } from "react";
import "./D1MerchantCenter.css";
import { useUi } from "../UiContext";

const BASE=(import.meta.env.VITE_D1_COMMERCE_URL || "https://bsmart-commerce-api.bcs-written-rakib.workers.dev").replace(/\/$/,"");
const fmt=n=>"৳"+Number(n||0).toLocaleString("bn-BD");
const ORDER_STATUS_BN={placed:"অর্ডার জমা হয়েছে",confirmed:"নিশ্চিত হয়েছে",processing:"প্রস্তুত হচ্ছে",ready:"পণ্য প্রস্তুত",dispatched:"পাঠানো হয়েছে",shipped:"পাঠানো হয়েছে",fulfilled:"সম্পন্ন",delivered:"ডেলিভারি সম্পন্ন",cancelled:"বাতিল হয়েছে"};
const ORDER_ACTIONS={
  placed:[{status:"confirmed",label:"নিশ্চিত করুন"},{status:"cancelled",label:"বাতিল করুন",danger:true}],
  confirmed:[{status:"processing",label:"প্রস্তুত করা শুরু করুন"},{status:"cancelled",label:"বাতিল করুন",danger:true}],
  processing:[{status:"ready",label:"পণ্য প্রস্তুত"},{status:"cancelled",label:"বাতিল করুন",danger:true}],
  ready:[{status:"dispatched",label:"কুরিয়ারে পাঠান"}],
  dispatched:[{status:"delivered",label:"ডেলিভারি সম্পন্ন"}],
  shipped:[{status:"delivered",label:"ডেলিভারি সম্পন্ন"}],
};
const ORDER_ACTION_SUCCESS={
  confirmed:"অর্ডার নিশ্চিত করা হয়েছে।",
  processing:"পণ্য প্রস্তুতের কাজ শুরু হয়েছে।",
  ready:"পণ্য প্রস্তুত হয়েছে।",
  dispatched:"অর্ডার ডেলিভারির জন্য পাঠানো হয়েছে।",
  delivered:"ডেলিভারি সম্পন্ন হয়েছে।",
  cancelled:"অর্ডার বাতিল হয়েছে এবং মজুত আগের অবস্থায় ফিরেছে।",
};
const RETURN_STATUS_BN={requested:"অনুরোধ এসেছে",approved:"অনুমোদিত",rejected:"প্রত্যাখ্যাত",received:"ফেরত পণ্য গ্রহণ",closed_demo:"পরীক্ষামূলকভাবে বন্ধ"};
const CASH_KIND_BN={receipt:"টাকা গ্রহণ",expense:"খরচ"};
const empty={email:"",access_key:""};
async function call(path,{method="GET",body,token}={}){
  const response=await fetch(BASE+path,{method,headers:{"Content-Type":"application/json",...(token?{Authorization:"Bearer "+token}:{})},...(body?{body:JSON.stringify(body)}:{})});
  const j=await response.json().catch(()=>({}));
  if(!response.ok){const e=new Error(j.detail||"অনুরোধটি সম্পন্ন করা যায়নি। আবার চেষ্টা করুন।");e.status=response.status;throw e;}
  return j;
}
const input={minHeight:43,padding:"10px 12px",border:"1px solid var(--dm-line)",background:"var(--dm-surface)",borderRadius:10,color:"var(--dm-text)",font:"inherit",width:"100%"};
const categories=["মুদি","পোশাক","ইলেকট্রনিক্স","রেস্টুরেন্ট","স্টেশনারি","বিউটি","মোবাইল","ফার্নিচার","হার্ডওয়্যার","অন্যান্য"];
function Field({label,children}){return <label className="dm-field"><strong>{label}</strong>{children}</label>;}
function Empty({children}){return <p className="dm-empty">{children}</p>;}
function Metric({title,value,tip}){return <div className="dm-stat"><small>{title}</small><strong>{value}</strong>{tip&&<span>{tip}</span>}</div>;}
export default function D1MerchantCenter(){
  const {theme,toggleTheme}=useUi();
  const [token,setToken]=useState(()=>sessionStorage.getItem("bsmart_d1_merchant")||"");
  const [form,setForm]=useState(empty),[mode,setMode]=useState("login"),[view,setView]=useState("dashboard");
  const [data,setData]=useState(null),[busy,setBusy]=useState(false),[error,setError]=useState(""),[note,setNote]=useState("");
  const [storeForm,setStoreForm]=useState({name:"",category:"মুদি",area:"",tagline:"",is_active:false});
  const [newProduct,setNewProduct]=useState({sku:"",name:"",category:"",description:"",brand:"",tags:"",compare_at_price_bdt:"",unit_label:"pcs",price_bdt:"",stock_qty:"",is_listed:true});
  const [edit,setEdit]=useState(null);
  const [posProduct,setPosProduct]=useState("");
  const [posQty,setPosQty]=useState("1");
  const [cashForm,setCashForm]=useState({kind:"expense",amount_bdt:"",description:""});
  const [returnRequests,setReturnRequests]=useState([]);
  const [chatMessages,setChatMessages]=useState([]);
  const [threadMessages,setThreadMessages]=useState([]);
  const [activeCustomerId,setActiveCustomerId]=useState("");
  const [replyText,setReplyText]=useState("");
  const [oneTimeKey,setOneTimeKey]=useState("");
  const store=data?.store;
  const load=useCallback(async tk=>{
    const latest=await call("/api/merchant/dashboard",{token:tk});
    setData(latest);
    if(latest.store)setStoreForm({name:latest.store.name,category:latest.store.category||"মুদি",area:latest.store.area||"",tagline:latest.store.tagline||"",is_active:latest.store.is_active});
    return latest;
  },[]);
  useEffect(()=>{if(!token)return;load(token).catch(e=>{setError(e.message);if(e.status===401){sessionStorage.removeItem("bsmart_d1_merchant");setToken("");}});},[token,load]);
  useEffect(()=>{
    if(!token||!store)return;
    if(view==="returns")call("/api/merchant/returns",{token}).then(x=>setReturnRequests(x.returns||[])).catch(e=>setError(e.message));
    if(view==="chat")call("/api/merchant/chat",{token}).then(x=>setChatMessages(x.messages||[])).catch(e=>setError(e.message));
  },[view,token,store?.id]);
  useEffect(()=>{
    if(view!=="chat"||!token||!activeCustomerId){setThreadMessages([]);return;}
    call("/api/merchant/chat?account_id="+encodeURIComponent(activeCustomerId),{token})
      .then(x=>setThreadMessages(x.messages||[])).catch(e=>setError(e.message));
  },[view,token,activeCustomerId,store?.id]);
  const chatThreads=useMemo(()=>{
    const by=new Map();
    for(const message of chatMessages)by.set(message.account_id,message);
    return [...by.values()].sort((a,b)=>String(b.created_at).localeCompare(String(a.created_at)));
  },[chatMessages]);
  async function run(action,success){
    setBusy(true);setError("");setNote("");
    try{
      await action();
      if(token)await load(token);
      if(token&&view==="returns"){const x=await call("/api/merchant/returns",{token});setReturnRequests(x.returns||[]);}
      if(token&&view==="chat"){
        const x=await call("/api/merchant/chat",{token});setChatMessages(x.messages||[]);
        if(activeCustomerId){const t=await call("/api/merchant/chat?account_id="+encodeURIComponent(activeCustomerId),{token});setThreadMessages(t.messages||[]);}
      }
      setNote(success||"Cloudflare D1-তে পরিবর্তন সংরক্ষিত হয়েছে।");
    } catch(e){setError(e.message||"অনুরোধটি সম্পন্ন করা যায়নি।");}
    finally{setBusy(false);}
  }
  async function authenticate(e){
    e.preventDefault();
    await run(async()=>{
      if(mode==="register"){
        const registered=await call("/api/merchant/register",{method:"POST",body:{email:form.email}});
        setOneTimeKey(registered.owner_access_key);
        setMode("login");setForm(old=>({...old,access_key:registered.owner_access_key}));return;
      }
      const result=await call("/api/merchant/login",{method:"POST",body:form});
      sessionStorage.setItem("bsmart_d1_merchant",result.token);setToken(result.token);setOneTimeKey("");setForm(empty);
    },mode==="login"?"D1 দোকান ব্যবস্থাপনায় লগইন করা হয়েছে।":"");
  }
  async function logout(){
    try{if(token)await call("/api/merchant/logout",{method:"POST",token});}catch{/* local logout even offline */}
    sessionStorage.removeItem("bsmart_d1_merchant");setToken("");setData(null);setNote("");setError("");
  }
  const products=data?.products||[],orders=data?.orders||[],stats=data?.metrics||{};
  const totalProducts=useMemo(()=>products.filter(p=>p.is_listed).length,[products]);
  return <main className="dm-page">
    <header className="dm-header"><a href="#/" className="dm-logo">B-SMART <span>দোকান পরিচালনা</span></a>
      <div className="dm-header-side"><span className="dm-d1">D1-তে তথ্য সংরক্ষিত</span><a href="#/stores">সব দোকান</a><a href="#/d1-platform-admin">Platform admin</a><button type="button" className="dm-theme-toggle" onClick={toggleTheme} aria-pressed={theme==="dark"} aria-label={theme==="dark"?"লাইট মোড চালু করুন":"ডার্ক মোড চালু করুন"} title={theme==="dark"?"লাইট মোড চালু করুন":"ডার্ক মোড চালু করুন"}>{theme==="dark"?"☀️":"🌙"}</button>{token&&<button className="dm-text-btn" onClick={logout}>লগআউট</button>}</div>
    </header>
    <div className="dm-main">
      <section className="dm-heading"><div><p className="dm-overline">Cloudflare D1 · পরীক্ষামূলক দোকান পরিচালনা</p><h1>স্টোর ম্যানেজমেন্ট</h1>
      <p>নিজের পরীক্ষামূলক দোকান, পণ্য, মজুত ও অর্ডারের তথ্য এক জায়গা থেকে পরিচালনা করুন।</p></div>
      {store&&<a className="dm-visit" href={"#/store/"+store.slug}>দোকানের প্রিভিউ দেখুন ↗</a>}</section>
      <div className="dm-warning" role="note">এটি একটি পরীক্ষামূলক দোকান পরিচালনার ব্যবস্থা। এখানে বাস্তব পেমেন্ট ও ডেলিভারি নেই। পুরোনো ব্যবসার হিসাব ও গ্রাহক অ্যাকাউন্টও এখানে যুক্ত নয়। বাস্তব গ্রাহকের তথ্য ব্যবহার করবেন না।</div>
      {error&&<p className="dm-error" role="alert">{error}</p>}{note&&<p className="dm-success" role="status">{note}</p>}
      {!token?<div className="dm-auth"><h2>{mode==="login"?"দোকান মালিকের লগইন":"নতুন দোকান মালিকের অ্যাকাউন্ট"}</h2>
        <p>এটি পুরোনো B-SMART লগইন নয়। এখানে ২৫৬-বিটের গোপন অ্যাক্সেস কী ব্যবহার করা হয়। ইমেইল যাচাই বা হারানো কী পুনরুদ্ধারের ব্যবস্থা এখনো নেই।</p>
        {oneTimeKey&&<div className="dm-warning" role="status"><strong>আপনার অ্যাক্সেস কী শুধু একবার দেখানো হবে। এখনই নিরাপদ জায়গায় সংরক্ষণ করুন।</strong>
          <p style={{overflowWrap:"anywhere",fontFamily:"monospace",userSelect:"all"}}>{oneTimeKey}</p>
          <button className="dm-secondary" type="button" onClick={()=>navigator.clipboard?.writeText(oneTimeKey)}>অ্যাক্সেস কী কপি করুন</button>
          <p>অ্যাক্সেস কী কারও সঙ্গে শেয়ার করবেন না। হারিয়ে গেলে এই অ্যাকাউন্ট পুনরুদ্ধার করা যাবে না।</p></div>}

        <form onSubmit={authenticate} className="dm-fields">
          <Field label="ইমেইল"><input style={input} type="email" autoComplete="email" required value={form.email} onChange={e=>setForm(v=>({...v,email:e.target.value}))}/></Field>
          {mode==="login"&&<Field label="মালিকের অ্যাক্সেস কী (৬৪ অক্ষর)"><input style={input} type="password" minLength={64} maxLength={64} autoComplete="off" required value={form.access_key} onChange={e=>setForm(v=>({...v,access_key:e.target.value}))}/></Field>}
          <button className="dm-btn" disabled={busy} type="submit">{busy?"প্রক্রিয়াকরণ চলছে…":mode==="login"?"লগইন করুন":"অ্যাকাউন্ট খুলুন"}</button>
        </form>
        <button className="dm-text-btn" onClick={()=>{setMode(v=>v==="login"?"register":"login");setError("");setNote("");}}>{mode==="login"?"নতুন দোকান মালিকের অ্যাকাউন্ট খুলুন":"লগইনে ফিরে যান"}</button>
      </div>:data===null?<p>Cloudflare D1 থেকে দোকানের তথ্য আনা হচ্ছে…</p>:!store?
      <section className="dm-panel"><h2>আপনার প্রথম স্টোর তৈরি করুন</h2><p className="dm-muted">শুরুতে দোকানটি শুধু আপনার জন্য দৃশ্যমান থাকবে। পরে চাইলে পরীক্ষামূলক প্রিভিউ প্রকাশ করতে পারবেন।</p>
        <form className="dm-fields" onSubmit={e=>{e.preventDefault();run(async()=>{await call("/api/merchant/store",{method:"POST",token,body:storeForm});},"নতুন পরীক্ষামূলক দোকান সংরক্ষিত হয়েছে।");}}>
        <Field label="দোকানের নাম"><input style={input} value={storeForm.name} minLength={3} required onChange={e=>setStoreForm(x=>({...x,name:e.target.value}))}/></Field>
        <Field label="বিভাগ"><select style={input} value={storeForm.category} onChange={e=>setStoreForm(x=>({...x,category:e.target.value}))}>{categories.map(c=><option key={c}>{c}</option>)}</select></Field>
        <Field label="এলাকা"><input style={input} required value={storeForm.area} onChange={e=>setStoreForm(x=>({...x,area:e.target.value}))} placeholder="যেমন: রাজশাহী"/></Field>
        <button disabled={busy} type="submit" className="dm-btn">পরীক্ষামূলক দোকান তৈরি করুন</button></form>
      </section>:
      <>
        <div className="dm-tabs">{[["dashboard","সারসংক্ষেপ"],["products","পণ্য ও মজুত"],["pos","ডেমো বিক্রি ও হিসাব"],["orders","অর্ডার"],["returns","ফেরত"],["chat","ক্রেতার বার্তা"],["store","দোকানের সেটিংস"]].map(([k,l])=><button key={k} onClick={()=>setView(k)} className={view===k?"dm-active":""}>{l}</button>)}</div>
        {view==="dashboard"&&<div className="dm-stack">
          <div className="dm-stats"><Metric title="ডেমো অর্ডার" value={Number(stats.orders||0).toLocaleString("en-BD")}/><Metric title="বাতিল হয়নি এমন নমুনা বিক্রি" value={fmt(stats.placed_total_bdt)} tip="বাস্তবে কোনো টাকা আদায় হয়নি"/><Metric title="প্রকাশিত পণ্য" value={totalProducts}/><Metric title="মজুতের পরিমাণ" value={Number(stats.inventory_units||0)}/></div>
          <div className="dm-panel"><h2>{store.name}</h2><p className="dm-muted">{store.area} · {store.category}</p><p>ডেমো দোকান প্রকাশিত: <strong>{store.is_active?"হ্যাঁ":"না"}</strong></p><p className="dm-muted">দোকানের লিংক: <code>/#/store/{store.slug}</code></p>
          <button className="dm-secondary" onClick={()=>setView("store")}>দোকানের তথ্য সম্পাদনা করুন</button></div>
          <div className="dm-panel"><h2>মজুত সংশোধনের ইতিহাস</h2>{data.stock_adjustments.length===0?<Empty>এখনো মজুত সংশোধন করা হয়নি।</Empty>:
          <div className="dm-scroll"><table><thead><tr><th>সময়</th><th>পণ্য</th><th>আগের পরিমাণ</th><th>নতুন পরিমাণ</th><th>Δ</th></tr></thead><tbody>{data.stock_adjustments.map((a,i)=><tr key={i}><td>{a.created_at}</td><td>{products.find(p=>p.id===a.product_id)?.name||a.product_id}</td><td>{a.old_quantity}</td><td>{a.new_quantity}</td><td>{a.delta}</td></tr>)}</tbody></table></div>}</div>
        </div>}
        {view==="products"&&<div className="dm-stack">
          <section className="dm-panel"><h2>নতুন পণ্য যোগ করুন</h2><form className="dm-product-form" onSubmit={e=>{e.preventDefault();run(async()=>{await call("/api/merchant/products",{method:"POST",token,body:{...newProduct,tags:newProduct.tags.split(",").map(x=>x.trim()).filter(Boolean),price_bdt:Number(newProduct.price_bdt),stock_qty:Number(newProduct.stock_qty),compare_at_price_bdt:newProduct.compare_at_price_bdt===""?null:Number(newProduct.compare_at_price_bdt)}});setNewProduct({sku:"",name:"",category:"",description:"",brand:"",tags:"",compare_at_price_bdt:"",unit_label:"pcs",price_bdt:"",stock_qty:"",is_listed:true});},"নতুন পণ্য সংরক্ষিত হয়েছে।");}}>
          {["sku","name","category","brand","unit_label","price_bdt","compare_at_price_bdt","stock_qty","tags"].map(k=><Field key={k} label={{sku:"পণ্য কোড (SKU)",name:"পণ্যের নাম",category:"বিভাগ",brand:"ব্র্যান্ড (ঐচ্ছিক)",unit_label:"একক",price_bdt:"বিক্রয়মূল্য (টাকা)",compare_at_price_bdt:"আগের/তুলনামূলক দাম (ঐচ্ছিক)",stock_qty:"মজুতের পরিমাণ",tags:"ট্যাগ (কমা দিয়ে লিখুন)"}[k]}><input style={input} value={newProduct[k]} required={["sku","name","category","price_bdt","stock_qty"].includes(k)} type={["price_bdt","stock_qty","compare_at_price_bdt"].includes(k)?"number":"text"} min={["price_bdt","stock_qty","compare_at_price_bdt"].includes(k)?0:undefined} onChange={e=>setNewProduct(v=>({...v,[k]:e.target.value}))}/></Field>)}
          <Field label="পণ্যের বিস্তারিত বিবরণ"><textarea style={{...input,minHeight:90}} maxLength={3000} value={newProduct.description} onChange={e=>setNewProduct(v=>({...v,description:e.target.value}))}/></Field>
          <label className="dm-check"><input type="checkbox" checked={newProduct.is_listed} onChange={e=>setNewProduct(v=>({...v,is_listed:e.target.checked}))}/>পণ্যটি পরীক্ষামূলক দোকানে দেখান</label><button disabled={busy} type="submit" className="dm-btn">পণ্য যোগ করুন</button></form></section>
          <section className="dm-panel"><h2>আপনার পণ্য ({products.length})</h2>
          {products.length===0?<Empty>এখনো কোনো পণ্য যোগ করা হয়নি।</Empty>:<div className="dm-product-list">{products.map(p=><article key={p.id} className="dm-product">
            <div><strong>{p.name}</strong><p className="dm-muted">{p.sku} · {p.category||"বিভাগ দেওয়া নেই"}</p><p><b>{fmt(p.price_bdt)}</b> · মজুত <b>{p.stock_qty}</b> · {p.is_listed?"প্রকাশিত":"লুকানো"}</p></div>
            <button className="dm-secondary" onClick={()=>setEdit({...p})}>সম্পাদনা</button></article>)}</div>}</section>
        </div>}
        {view==="pos"&&<div className="dm-stack">
          <section className="dm-panel"><h2>পরীক্ষামূলক কাউন্টার বিক্রি</h2><p className="dm-muted">এখানে দেওয়া বিক্রির নমুনা রেকর্ড D1-তে সংরক্ষিত হবে এবং পরীক্ষামূলক মজুত কমবে। বাস্তবে কোনো টাকা গ্রহণ করা হবে না।</p>
            <form className="dm-product-form" onSubmit={e=>{e.preventDefault();const selected=posProduct||products.find(p=>p.is_listed&&p.stock_qty>0)?.id;if(!selected){setError("বিক্রির জন্য প্রকাশিত ও মজুত থাকা কোনো পণ্য নেই।");return;}run(()=>call("/api/merchant/pos",{method:"POST",token,body:{items:[{product_id:selected,quantity:Number(posQty)}]}}),"নমুনা বিক্রি ও মজুতের পরিবর্তন সংরক্ষিত হয়েছে।");}}>
              <Field label="পণ্য"><select style={input} required value={posProduct||products.find(p=>p.is_listed&&p.stock_qty>0)?.id||""} onChange={e=>setPosProduct(e.target.value)}>{products.filter(p=>p.is_listed&&p.stock_qty>0).map(p=><option value={p.id} key={p.id}>{p.name} · {fmt(p.price_bdt)} · মজুত {p.stock_qty}</option>)}</select></Field>
              <Field label="পরিমাণ"><input style={input} type="number" min={1} max={30} value={posQty} onChange={e=>setPosQty(e.target.value)}/></Field>
              <button type="submit" className="dm-btn" disabled={busy||!products.some(p=>p.is_listed&&p.stock_qty>0)}>নমুনা বিক্রি সংরক্ষণ করুন</button>
            </form></section>
          <section className="dm-panel"><h2>পরীক্ষামূলক নগদ হিসাব</h2><p className="dm-muted">এটি পূর্ণাঙ্গ হিসাবরক্ষণ নয়। এখানে নমুনা টাকা গ্রহণ ও খরচের তথ্য রাখা যায়।</p>
            <form className="dm-product-form" onSubmit={e=>{e.preventDefault();run(async()=>{await call("/api/merchant/cashbook",{method:"POST",token,body:{...cashForm,amount_bdt:Number(cashForm.amount_bdt)}});setCashForm({kind:"expense",amount_bdt:"",description:""});},"নমুনা নগদ হিসাব সংরক্ষিত হয়েছে।");}}>
              <Field label="ধরন"><select style={input} value={cashForm.kind} onChange={e=>setCashForm(v=>({...v,kind:e.target.value}))}><option value="expense">খরচ</option><option value="receipt">টাকা গ্রহণ</option></select></Field>
              <Field label="পরিমাণ (টাকা)"><input style={input} type="number" min={1} max={500000} required value={cashForm.amount_bdt} onChange={e=>setCashForm(v=>({...v,amount_bdt:e.target.value}))}/></Field>
              <Field label="বিবরণ"><input style={input} minLength={3} required value={cashForm.description} onChange={e=>setCashForm(v=>({...v,description:e.target.value}))}/></Field>
              <button className="dm-btn" disabled={busy} type="submit">নমুনা হিসাব সংরক্ষণ করুন</button></form>
          </section>
          <section className="dm-panel"><h2>সাম্প্রতিক নগদ হিসাব</h2>
            {!(data.cashbook||[]).length?<Empty>এখনো কোনো হিসাব যোগ করা হয়নি।</Empty>:<div className="dm-scroll"><table><thead><tr><th>তারিখ</th><th>ধরন</th><th>পরিমাণ</th><th>বিবরণ</th></tr></thead>
            <tbody>{data.cashbook.map(row=><tr key={row.id}><td>{row.created_at}</td><td>{CASH_KIND_BN[row.kind]||row.kind}</td><td>{fmt(row.amount_bdt)}</td><td>{row.description}</td></tr>)}</tbody></table></div>}
          </section>
        </div>}
        {view==="orders"&&<div className="dm-panel"><h2>পরীক্ষামূলক অর্ডার ({orders.length})</h2><p className="dm-muted">অর্ডারের তথ্য Cloudflare D1-তে সংরক্ষিত থাকে। পরীক্ষামূলক অর্ডারে বাস্তব ক্রেতার পরিচয় ব্যবহার করা হয় না।</p>
          {orders.length===0?<Empty>অর্ডার আসলে এখানে দেখা যাবে।</Empty>:<div className="dm-scroll"><table><thead><tr><th>অর্ডার</th><th>তারিখ</th><th>মোট</th><th>অবস্থা</th><th>করণীয়</th></tr></thead><tbody>{orders.map(o=><tr key={o.id}><td>{o.order_number}</td><td>{o.placed_at}</td><td>{fmt(o.total_bdt)}</td><td>{ORDER_STATUS_BN[o.status]||o.status}{o.status_note&&<><br/><small>{o.status_note}</small></>}</td><td>{(ORDER_ACTIONS[o.status]||[]).length ? ORDER_ACTIONS[o.status].map(action=><button key={action.status} className={action.danger?"dm-danger":"dm-secondary"} style={{marginRight:6,marginBottom:4}} disabled={busy} onClick={()=>run(()=>call("/api/merchant/orders/"+o.id+"/status",{method:"PATCH",token,body:{status:action.status}}),ORDER_ACTION_SUCCESS[action.status])}>{action.label}</button>) : <span>—</span>}</td></tr>)}</tbody></table></div>}
        </div>}
        {view==="returns"&&<section className="dm-panel"><h2>ক্রেতার ফেরত অনুরোধ ({returnRequests.length})</h2><p className="dm-muted">ফেরত পণ্য গ্রহণ করলে পরীক্ষামূলক মজুত একবার পুনরুদ্ধার হবে। এখানে কোনো অর্থ ফেরত দেওয়া হয় না।</p>
          {returnRequests.length===0?<Empty>এখনো কোনো ফেরত অনুরোধ আসেনি।</Empty>:<div className="dm-scroll"><table><thead><tr><th>অর্ডার/ক্রেতা</th><th>কারণ</th><th>নোট</th><th>অবস্থা</th><th>করণীয়</th></tr></thead><tbody>{returnRequests.map(r=><tr key={r.id}><td>{r.order_number}<br/><small>{r.customer_name}</small></td><td>{({damaged:"ক্ষতিগ্রস্ত",wrong_item:"ভুল পণ্য",missing_item:"পণ্য অনুপস্থিত",not_as_described:"বর্ণনার সঙ্গে মিল নেই",other:"অন্যান্য"})[r.reason]||r.reason}</td><td>{r.customer_note||"—"}</td><td>{RETURN_STATUS_BN[r.status]||r.status}<br/><small>{r.merchant_note||""}</small></td><td>{r.status==="requested"?<><button className="dm-secondary" disabled={busy} onClick={()=>run(()=>call("/api/merchant/returns/"+r.id,{method:"PATCH",token,body:{status:"approved"}}),"ফেরত অনুরোধ অনুমোদন করা হয়েছে।")}>অনুমোদন</button> <button className="dm-danger" disabled={busy} onClick={()=>run(()=>call("/api/merchant/returns/"+r.id,{method:"PATCH",token,body:{status:"rejected",merchant_note:"অনুরোধটি অনুমোদন করা হয়নি"}}),"ফেরত অনুরোধ প্রত্যাখ্যান করা হয়েছে।")}>প্রত্যাখ্যান</button></>:r.status==="approved"?<button className="dm-secondary" disabled={busy} onClick={()=>run(()=>call("/api/merchant/returns/"+r.id,{method:"PATCH",token,body:{status:"received"}}),"ফেরত পণ্য গ্রহণ হয়েছে; পরীক্ষামূলক মজুত পুনরুদ্ধার হয়েছে।")}>পণ্য গ্রহণ হয়েছে</button>:r.status==="received"?<button className="dm-secondary" disabled={busy} onClick={()=>run(()=>call("/api/merchant/returns/"+r.id,{method:"PATCH",token,body:{status:"closed_demo"}}),"ফেরত প্রক্রিয়া বন্ধ হয়েছে।")}>বন্ধ করুন</button>: "—"}</td></tr>)}</tbody></table></div>}</section>}
        {view==="chat"&&<section className="dm-panel"><h2>ক্রেতার বার্তা</h2><p className="dm-muted">এই দোকানের গ্রাহকের সঙ্গে বার্তা আদান-প্রদান করুন। পরীক্ষামূলক সাপোর্ট চ্যাট।</p>
          <div style={{display:"grid",gridTemplateColumns:"minmax(170px,0.8fr) minmax(0,1.5fr)",gap:12,minHeight:330}}>
            <div style={{border:"1px solid var(--dm-line)",borderRadius:10,overflowY:"auto",maxHeight:460}}>
              {chatThreads.length===0?<Empty>এখনো কোনো বার্তা নেই।</Empty>:chatThreads.map(t=><button key={t.account_id} onClick={()=>setActiveCustomerId(t.account_id)} style={{display:"block",width:"100%",textAlign:"left",padding:10,border:0,borderBottom:"1px solid var(--dm-line)",background:activeCustomerId===t.account_id?"var(--dm-soft)":"transparent",color:"var(--dm-text)",cursor:"pointer"}}><strong>{t.customer_name||t.customer_email||"ক্রেতা"}</strong><div style={{fontSize:11,opacity:.75,marginTop:4}}>{t.message.slice(0,70)}</div><small>{t.created_at}</small></button>)}
            </div>
            <div style={{display:"flex",flexDirection:"column",gap:8,minWidth:0}}>
              {!activeCustomerId?<Empty>বার্তা পড়তে বাম পাশ থেকে একজন ক্রেতা নির্বাচন করুন।</Empty>:<>
                <div style={{flex:1,overflowY:"auto",maxHeight:360,display:"grid",alignContent:"start",gap:7}}>
                  {threadMessages.map(m=><div key={m.id} style={{justifySelf:m.sender_role==="merchant"?"end":"start",maxWidth:"90%",padding:9,borderRadius:9,background:m.sender_role==="merchant"?"var(--dm-soft)":"var(--dm-surface)",border:"1px solid var(--dm-line)"}}><div style={{fontSize:12}}>{m.message}</div><small>{m.created_at}</small></div>)}
                </div>
                <form onSubmit={e=>{e.preventDefault();if(!replyText.trim()||!activeCustomerId)return;run(async()=>{await call("/api/merchant/chat",{method:"POST",token,body:{account_id:activeCustomerId,message:replyText.trim()}});setReplyText("");const x=await call("/api/merchant/chat?account_id="+encodeURIComponent(activeCustomerId),{token});setThreadMessages(x.messages||[]);},"বার্তা পাঠানো হয়েছে।");}} style={{display:"flex",gap:6}}>
                  <input style={input} value={replyText} maxLength={2000} onChange={e=>setReplyText(e.target.value)} placeholder="উত্তর লিখুন…" required/>
                  <button className="dm-btn" disabled={busy||!replyText.trim()} type="submit">পাঠান</button>
                </form>
              </>}
            </div>
          </div>
        </section>}
        {view==="store"&&<section className="dm-panel"><h2>দোকানের সেটিংস</h2><p className="dm-muted">এই দোকান শুধু পরীক্ষামূলক হিসেবে প্রকাশ করা যাবে। এখানে বাস্তব পেমেন্ট বা ডেলিভারি চালু নেই।</p>
        <form className="dm-fields" onSubmit={e=>{e.preventDefault();run(()=>call("/api/merchant/store",{method:"PATCH",token,body:storeForm}),"দোকানের তথ্য সংরক্ষিত হয়েছে।");}}>
          <Field label="নাম"><input style={input} required minLength={3} value={storeForm.name} onChange={e=>setStoreForm(v=>({...v,name:e.target.value}))}/></Field>
          <Field label="বিভাগ"><select style={input} value={storeForm.category} onChange={e=>setStoreForm(v=>({...v,category:e.target.value}))}>{categories.map(c=><option key={c}>{c}</option>)}</select></Field>
          <Field label="এলাকা"><input style={input} required value={storeForm.area} onChange={e=>setStoreForm(v=>({...v,area:e.target.value}))}/></Field>
          <Field label="বিবরণ"><input style={input} value={storeForm.tagline} onChange={e=>setStoreForm(v=>({...v,tagline:e.target.value}))}/></Field>
          <label className="dm-check"><input type="checkbox" checked={storeForm.is_active} onChange={e=>setStoreForm(v=>({...v,is_active:e.target.checked}))}/>পরীক্ষামূলক দোকানটি সবার জন্য দেখান</label>
          <button className="dm-btn" disabled={busy} type="submit">সেটিংস সংরক্ষণ করুন</button>
        </form></section>}
        {edit&&<div className="dm-modal-bg" onClick={()=>setEdit(null)}><section role="dialog" aria-modal="true" aria-label="পণ্য সম্পাদনা" className="dm-panel dm-dialog" onClick={e=>e.stopPropagation()}><h2>পণ্য সম্পাদনা: {edit.name}</h2>
          <form className="dm-fields" onSubmit={e=>{e.preventDefault();run(async()=>{await call("/api/merchant/products/"+edit.id,{method:"PATCH",token,body:{name:edit.name,category:edit.category,description:edit.description||"",brand:edit.brand||"",tags:Array.isArray(edit.tags)?edit.tags:(()=>{try{return JSON.parse(edit.tags||"[]")}catch{return []}})(),unit_label:edit.unit_label||"pcs",compare_at_price_bdt:edit.compare_at_price_bdt===""||edit.compare_at_price_bdt==null?null:Number(edit.compare_at_price_bdt),price_bdt:Number(edit.price_bdt),stock_qty:Number(edit.stock_qty),is_listed:edit.is_listed}});setEdit(null);},"পণ্যের তথ্য সংশোধন করা হয়েছে।");}}>
          {["name","category","brand","unit_label","price_bdt","compare_at_price_bdt","stock_qty"].map(k=><Field key={k} label={{name:"পণ্যের নাম",category:"বিভাগ",brand:"ব্র্যান্ড",unit_label:"একক",price_bdt:"বিক্রয়মূল্য",compare_at_price_bdt:"তুলনামূলক দাম",stock_qty:"মজুত"}[k]||k}><input style={input} type={["price_bdt","stock_qty","compare_at_price_bdt"].includes(k)?"number":"text"} min={["price_bdt","stock_qty","compare_at_price_bdt"].includes(k)?0:undefined} required={["name","price_bdt","stock_qty"].includes(k)} value={edit[k]??""} onChange={e=>setEdit(v=>({...v,[k]:e.target.value}))}/></Field>)}<Field label="পণ্যের বিবরণ"><textarea style={{...input,minHeight:90}} maxLength={3000} value={edit.description||""} onChange={e=>setEdit(v=>({...v,description:e.target.value}))}/></Field><Field label="ট্যাগ (কমা দিয়ে লিখুন)"><input style={input} value={Array.isArray(edit.tags)?edit.tags.join(", "):(()=>{try{return JSON.parse(edit.tags||"[]").join(", ")}catch{return ""}})()} onChange={e=>setEdit(v=>({...v,tags:e.target.value.split(",").map(x=>x.trim()).filter(Boolean)}))}/></Field>
          <label className="dm-check"><input type="checkbox" checked={!!edit.is_listed} onChange={e=>setEdit(v=>({...v,is_listed:e.target.checked}))}/>প্রকাশিত</label><div className="dm-actions"><button className="dm-btn" disabled={busy} type="submit">পরিবর্তন সংরক্ষণ করুন</button><button type="button" onClick={()=>setEdit(null)} className="dm-secondary">বন্ধ করুন</button></div></form></section></div>}
      </>}
    </div>
    {token&&store&&<nav className="dm-bottom" aria-label="Owner mobile app navigation">{[["dashboard","হোম","⌂"],["products","পণ্য","▣"],["pos","বিক্রি","⊞"],["orders","অর্ডার","≡"],["returns","ফেরত","↩"],["store","সেটিংস","⚙"]].map(([k,t,icon])=><button key={k} className={view===k?"selected":""} onClick={()=>{setView(k);window.scrollTo({top:0,behavior:"smooth"});}}><span>{icon}</span>{t}</button>)}</nav>}
  </main>;
}
