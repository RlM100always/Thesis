import { useCallback, useEffect, useMemo, useState } from "react";
import "./D1MerchantCenter.css";

const BASE=(import.meta.env.VITE_D1_COMMERCE_URL || "https://bsmart-commerce-api.bcs-written-rakib.workers.dev").replace(/\/$/,"");
const fmt=n=>"৳"+Number(n||0).toLocaleString("en-BD");
const empty={email:"",password:""};
async function call(path,{method="GET",body,token}={}){
  const response=await fetch(BASE+path,{method,headers:{"Content-Type":"application/json",...(token?{Authorization:"Bearer "+token}:{})},...(body?{body:JSON.stringify(body)}:{})});
  const j=await response.json().catch(()=>({}));
  if(!response.ok){const e=new Error(j.detail||"Something went wrong");e.status=response.status;throw e;}
  return j;
}
const input={minHeight:43,padding:"10px 12px",border:"1px solid var(--dm-line)",background:"var(--dm-surface)",borderRadius:10,color:"var(--dm-text)",font:"inherit",width:"100%"};
const categories=["মুদি","পোশাক","ইলেকট্রনিক্স","রেস্টুরেন্ট","স্টেশনারি","বিউটি","মোবাইল","ফার্নিচার","হার্ডওয়্যার","অন্যান্য"];
function Field({label,children}){return <label className="dm-field"><strong>{label}</strong>{children}</label>;}
function Empty({children}){return <p className="dm-empty">{children}</p>;}
function Metric({title,value,tip}){return <div className="dm-stat"><small>{title}</small><strong>{value}</strong>{tip&&<span>{tip}</span>}</div>;}
export default function D1MerchantCenter(){
  const [token,setToken]=useState(()=>sessionStorage.getItem("bsmart_d1_merchant")||"");
  const [form,setForm]=useState(empty),[mode,setMode]=useState("login"),[view,setView]=useState("dashboard");
  const [data,setData]=useState(null),[busy,setBusy]=useState(false),[error,setError]=useState(""),[note,setNote]=useState("");
  const [storeForm,setStoreForm]=useState({name:"",category:"মুদি",area:"",tagline:"",is_active:false});
  const [newProduct,setNewProduct]=useState({sku:"",name:"",category:"",price_bdt:"",stock_qty:"",is_listed:true});
  const [edit,setEdit]=useState(null);
  const load=useCallback(async tk=>{
    const latest=await call("/api/merchant/dashboard",{token:tk});
    setData(latest);
    if(latest.store)setStoreForm({name:latest.store.name,category:latest.store.category||"মুদি",area:latest.store.area||"",tagline:latest.store.tagline||"",is_active:latest.store.is_active});
    return latest;
  },[]);
  useEffect(()=>{if(!token)return;load(token).catch(e=>{setError(e.message);if(e.status===401){sessionStorage.removeItem("bsmart_d1_merchant");setToken("");}});},[token,load]);
  async function run(action,success){
    setBusy(true);setError("");setNote("");
    try{await action();if(token)await load(token);setNote(success||"Saved to Cloudflare D1");}
    catch(e){setError(e.message||"Request failed");}
    finally{setBusy(false);}
  }
  async function authenticate(e){
    e.preventDefault();
    await run(async()=>{
      if(mode==="register"){
        await call("/api/merchant/register",{method:"POST",body:form});
        setMode("login");setForm(old=>({...old,password:""}));setNote("Account created. Please sign in.");return;
      }
      const result=await call("/api/merchant/login",{method:"POST",body:form});
      sessionStorage.setItem("bsmart_d1_merchant",result.token);setToken(result.token);setForm(empty);
    },mode==="login"?"Logged in to Cloudflare D1 Owner Center":"");
  }
  async function logout(){
    try{if(token)await call("/api/merchant/logout",{method:"POST",token});}catch{/* local logout even offline */}
    sessionStorage.removeItem("bsmart_d1_merchant");setToken("");setData(null);setNote("");setError("");
  }
  const store=data?.store,products=data?.products||[],orders=data?.orders||[],stats=data?.metrics||{};
  const totalProducts=useMemo(()=>products.filter(p=>p.is_listed).length,[products]);
  return <main className="dm-page">
    <header className="dm-header"><a href="#/" className="dm-logo">B-SMART <span>Cloudflare Owner Center</span></a>
      <div className="dm-header-side"><span className="dm-d1">D1 persistent</span><a href="#/stores">সব দোকান</a>{token&&<button className="dm-text-btn" onClick={logout}>Logout</button>}</div>
    </header>
    <div className="dm-main">
      <section className="dm-heading"><div><p className="dm-overline">Business operations · Cloudflare D1</p><h1>স্টোর ম্যানেজমেন্ট</h1>
      <p>নতুন D1 account দিয়ে আপনার নিজের demo storefront, পণ্য, inventory ও order পরিচালনা করুন।</p></div>
      {store&&<a className="dm-visit" href={"#/store/"+store.slug}>Store preview ↗</a>}</section>
      <div className="dm-warning" role="note">পরীক্ষামূলক ecommerce: এখানে real payment, delivery, পুরোনো POS/accounts এবং FastAPI customer login যুক্ত নয়। বাস্তব গ্রাহকের তথ্য ব্যবহার করবেন না।</div>
      {error&&<p className="dm-error" role="alert">{error}</p>}{note&&<p className="dm-success" role="status">{note}</p>}
      {!token?<div className="dm-auth"><h2>{mode==="login"?"Store owner login":"Create D1 owner account"}</h2>
        <p>পুরোনো B-SMART business login নয়—এটি Cloudflare-এ নতুন স্বতন্ত্র account। Email verification/password reset এখনো চালু নেই।</p>
        <form onSubmit={authenticate} className="dm-fields">
          <Field label="Email"><input style={input} type="email" autoComplete="email" required value={form.email} onChange={e=>setForm(v=>({...v,email:e.target.value}))}/></Field>
          <Field label="Password"><input style={input} type="password" minLength={mode==="register"?12:1} autoComplete={mode==="register"?"new-password":"current-password"} required value={form.password} onChange={e=>setForm(v=>({...v,password:e.target.value}))}/></Field>
          <button className="dm-btn" disabled={busy} type="submit">{busy?"Processing…":mode==="login"?"Sign in":"Create account"}</button>
        </form>
        <button className="dm-text-btn" onClick={()=>{setMode(v=>v==="login"?"register":"login");setError("");setNote("");}}>{mode==="login"?"Create a new D1 owner account":"Back to login"}</button>
      </div>:data===null?<p>Cloudflare D1 থেকে আপনার store data লোড হচ্ছে…</p>:!store?
      <section className="dm-panel"><h2>আপনার প্রথম স্টোর তৈরি করুন</h2><p className="dm-muted">শুরুতে storefront private থাকবে; আপনি চাইলে পরে demo preview চালু করবেন।</p>
        <form className="dm-fields" onSubmit={e=>{e.preventDefault();run(async()=>{await call("/api/merchant/store",{method:"POST",token,body:storeForm});},"New demo store saved");}}>
        <Field label="Store name"><input style={input} value={storeForm.name} minLength={3} required onChange={e=>setStoreForm(x=>({...x,name:e.target.value}))}/></Field>
        <Field label="Category"><select style={input} value={storeForm.category} onChange={e=>setStoreForm(x=>({...x,category:e.target.value}))}>{categories.map(c=><option key={c}>{c}</option>)}</select></Field>
        <Field label="Area"><input style={input} required value={storeForm.area} onChange={e=>setStoreForm(x=>({...x,area:e.target.value}))} placeholder="e.g. Rajshahi"/></Field>
        <button disabled={busy} type="submit" className="dm-btn">Create D1 Store</button></form>
      </section>:
      <>
        <div className="dm-tabs">{[["dashboard","Overview"],["products","Products & Stock"],["orders","Orders"],["store","Store Settings"]].map(([k,l])=><button key={k} onClick={()=>setView(k)} className={view===k?"dm-active":""}>{l}</button>)}</div>
        {view==="dashboard"&&<div className="dm-stack">
          <div className="dm-stats"><Metric title="Demo orders" value={Number(stats.orders||0).toLocaleString("en-BD")}/><Metric title="Sample sales (non-cancelled)" value={fmt(stats.placed_total_bdt)} tip="Not real collected revenue"/><Metric title="Published products" value={totalProducts}/><Metric title="On-hand units" value={Number(stats.inventory_units||0)}/></div>
          <div className="dm-panel"><h2>{store.name}</h2><p className="dm-muted">{store.area} · {store.category}</p><p>Public demo visibility: <strong>{store.is_active?"On":"Off"}</strong></p><p className="dm-muted">Store URL: <code>/#/store/{store.slug}</code></p>
          <button className="dm-secondary" onClick={()=>setView("store")}>Manage store profile</button></div>
          <div className="dm-panel"><h2>Recent inventory adjustments</h2>{data.stock_adjustments.length===0?<Empty>No manual adjustments yet</Empty>:
          <div className="dm-scroll"><table><thead><tr><th>Time</th><th>Product</th><th>Before</th><th>After</th><th>Δ</th></tr></thead><tbody>{data.stock_adjustments.map((a,i)=><tr key={i}><td>{a.created_at}</td><td>{products.find(p=>p.id===a.product_id)?.name||a.product_id}</td><td>{a.old_quantity}</td><td>{a.new_quantity}</td><td>{a.delta}</td></tr>)}</tbody></table></div>}</div>
        </div>}
        {view==="products"&&<div className="dm-stack">
          <section className="dm-panel"><h2>নতুন পণ্য যোগ করুন</h2><form className="dm-product-form" onSubmit={e=>{e.preventDefault();run(async()=>{await call("/api/merchant/products",{method:"POST",token,body:{...newProduct,price_bdt:Number(newProduct.price_bdt),stock_qty:Number(newProduct.stock_qty)}});setNewProduct({sku:"",name:"",category:"",price_bdt:"",stock_qty:"",is_listed:true});},"Product created in D1");}}>
          {["sku","name","category","price_bdt","stock_qty"].map(k=><Field key={k} label={{sku:"SKU",name:"Product",category:"Category",price_bdt:"Price BDT",stock_qty:"Stock quantity"}[k]}><input style={input} value={newProduct[k]} required type={["price_bdt","stock_qty"].includes(k)?"number":"text"} min={["price_bdt","stock_qty"].includes(k)?0:undefined} onChange={e=>setNewProduct(v=>({...v,[k]:e.target.value}))}/></Field>)}
          <label className="dm-check"><input type="checkbox" checked={newProduct.is_listed} onChange={e=>setNewProduct(v=>({...v,is_listed:e.target.checked}))}/>Publish as a demo product</label><button disabled={busy} type="submit" className="dm-btn">Add product</button></form></section>
          <section className="dm-panel"><h2>আপনার পণ্য ({products.length})</h2>
          {products.length===0?<Empty>No products yet</Empty>:<div className="dm-product-list">{products.map(p=><article key={p.id} className="dm-product">
            <div><strong>{p.name}</strong><p className="dm-muted">{p.sku} · {p.category||"Uncategorised"}</p><p><b>{fmt(p.price_bdt)}</b> · Stock <b>{p.stock_qty}</b> · {p.is_listed?"Published":"Hidden"}</p></div>
            <button className="dm-secondary" onClick={()=>setEdit({...p})}>Edit</button></article>)}</div>}</section>
        </div>}
        {view==="orders"&&<div className="dm-panel"><h2>Store demo orders ({orders.length})</h2><p className="dm-muted">Orders are persisted in Cloudflare D1; demonstration customers are anonymous.</p>
          {orders.length===0?<Empty>অর্ডার আসলে এখানে দেখা যাবে।</Empty>:<div className="dm-scroll"><table><thead><tr><th>Order</th><th>Date</th><th>Total</th><th>Status</th><th>Action</th></tr></thead><tbody>{orders.map(o=><tr key={o.id}><td>{o.order_number}</td><td>{o.placed_at}</td><td>{fmt(o.total_bdt)}</td><td>{o.status}</td><td>{o.status==="placed"?<>
            <button className="dm-secondary" disabled={busy} onClick={()=>run(()=>call("/api/merchant/orders/"+o.id+"/status",{method:"PATCH",token,body:{status:"confirmed"}}),"Order confirmed")}>Confirm</button> <button className="dm-danger" disabled={busy} onClick={()=>run(()=>call("/api/merchant/orders/"+o.id+"/status",{method:"PATCH",token,body:{status:"cancelled"}}),"Order cancelled and stock restored")}>Cancel</button></>:
            o.status==="confirmed"?<><button className="dm-secondary" disabled={busy} onClick={()=>run(()=>call("/api/merchant/orders/"+o.id+"/status",{method:"PATCH",token,body:{status:"fulfilled"}}),"Demo order fulfilled")}>Fulfil demo</button> <button className="dm-danger" disabled={busy} onClick={()=>run(()=>call("/api/merchant/orders/"+o.id+"/status",{method:"PATCH",token,body:{status:"cancelled"}}),"Order cancelled")}>Cancel</button></>:<span>—</span>}</td></tr>)}</tbody></table></div>}
        </div>}
        {view==="store"&&<section className="dm-panel"><h2>Store Settings</h2><p className="dm-muted">You may publish this only as a clearly marked demo store. Real payment/delivery is disabled.</p>
        <form className="dm-fields" onSubmit={e=>{e.preventDefault();run(()=>call("/api/merchant/store",{method:"PATCH",token,body:storeForm}),"Store profile saved");}}>
          <Field label="Name"><input style={input} required minLength={3} value={storeForm.name} onChange={e=>setStoreForm(v=>({...v,name:e.target.value}))}/></Field>
          <Field label="Category"><select style={input} value={storeForm.category} onChange={e=>setStoreForm(v=>({...v,category:e.target.value}))}>{categories.map(c=><option key={c}>{c}</option>)}</select></Field>
          <Field label="Area"><input style={input} required value={storeForm.area} onChange={e=>setStoreForm(v=>({...v,area:e.target.value}))}/></Field>
          <Field label="Description"><input style={input} value={storeForm.tagline} onChange={e=>setStoreForm(v=>({...v,tagline:e.target.value}))}/></Field>
          <label className="dm-check"><input type="checkbox" checked={storeForm.is_active} onChange={e=>setStoreForm(v=>({...v,is_active:e.target.checked}))}/>Make this labelled demo storefront public</label>
          <button className="dm-btn" disabled={busy} type="submit">Save settings</button>
        </form></section>}
        {edit&&<div className="dm-modal-bg" onClick={()=>setEdit(null)}><section role="dialog" aria-modal="true" aria-label="Edit product" className="dm-panel dm-dialog" onClick={e=>e.stopPropagation()}><h2>Edit: {edit.name}</h2>
          <form className="dm-fields" onSubmit={e=>{e.preventDefault();run(async()=>{await call("/api/merchant/products/"+edit.id,{method:"PATCH",token,body:{name:edit.name,category:edit.category,price_bdt:Number(edit.price_bdt),stock_qty:Number(edit.stock_qty),is_listed:edit.is_listed}});setEdit(null);},"Product updated");}}>
          {["name","category","price_bdt","stock_qty"].map(k=><Field key={k} label={k}><input style={input} type={["price_bdt","stock_qty"].includes(k)?"number":"text"} min={["price_bdt","stock_qty"].includes(k)?0:undefined} required value={edit[k]} onChange={e=>setEdit(v=>({...v,[k]:e.target.value}))}/></Field>)}
          <label className="dm-check"><input type="checkbox" checked={!!edit.is_listed} onChange={e=>setEdit(v=>({...v,is_listed:e.target.checked}))}/>Published</label><div className="dm-actions"><button className="dm-btn" disabled={busy} type="submit">Save to D1</button><button type="button" onClick={()=>setEdit(null)} className="dm-secondary">Close</button></div></form></section></div>}
      </>}
    </div>
    {token&&store&&<nav className="dm-bottom" aria-label="Owner mobile app navigation">{[["dashboard","Home","⌂"],["products","Products","▣"],["orders","Orders","≡"],["store","Settings","⚙"]].map(([k,t,icon])=><button key={k} className={view===k?"selected":""} onClick={()=>{setView(k);window.scrollTo({top:0,behavior:"smooth"});}}><span>{icon}</span>{t}</button>)}</nav>}
  </main>;
}
