import { useCallback, useEffect, useMemo, useState } from "react";
import "./D1MerchantCenter.css";

const BASE=(import.meta.env.VITE_D1_COMMERCE_URL || "https://bsmart-commerce-api.bcs-written-rakib.workers.dev").replace(/\/$/,"");
const fmt=n=>"৳"+Number(n||0).toLocaleString("en-BD");
const empty={email:"",access_key:""};
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
  const [posProduct,setPosProduct]=useState("");
  const [posQty,setPosQty]=useState("1");
  const [cashForm,setCashForm]=useState({kind:"expense",amount_bdt:"",description:""});
  const [oneTimeKey,setOneTimeKey]=useState("");
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
        const registered=await call("/api/merchant/register",{method:"POST",body:{email:form.email}});
        setOneTimeKey(registered.owner_access_key);
        setMode("login");setForm(old=>({...old,access_key:registered.owner_access_key}));return;
      }
      const result=await call("/api/merchant/login",{method:"POST",body:form});
      sessionStorage.setItem("bsmart_d1_merchant",result.token);setToken(result.token);setOneTimeKey("");setForm(empty);
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
        <p>এটি পুরোনো B-SMART login নয়। এখানে ২৫৬-bit owner access key দিয়ে লগইন হয়। Email verification বা হারিয়ে যাওয়া key ফেরানোর ব্যবস্থা এখনো নেই।</p>
        {oneTimeKey&&<div className="dm-warning" role="status"><strong>আপনার access key একবারই দেখানো হচ্ছে—এখনই নিরাপদ জায়গায় সংরক্ষণ করুন।</strong>
          <p style={{overflowWrap:"anywhere",fontFamily:"monospace",userSelect:"all"}}>{oneTimeKey}</p>
          <button className="dm-secondary" type="button" onClick={()=>navigator.clipboard?.writeText(oneTimeKey)}>Copy access key</button>
          <p>এটি কারও সঙ্গে share করবেন না। হারিয়ে গেলে এই account ফিরে পাওয়ার ব্যবস্থা নেই।</p></div>}

        <form onSubmit={authenticate} className="dm-fields">
          <Field label="Email"><input style={input} type="email" autoComplete="email" required value={form.email} onChange={e=>setForm(v=>({...v,email:e.target.value}))}/></Field>
          {mode==="login"&&<Field label="Owner access key (64 hex characters)"><input style={input} type="password" minLength={64} maxLength={64} autoComplete="off" required value={form.access_key} onChange={e=>setForm(v=>({...v,access_key:e.target.value}))}/></Field>}
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
        <div className="dm-tabs">{[["dashboard","Overview"],["products","Products & Stock"],["pos","Demo POS & Cashbook"],["orders","Orders"],["store","Store Settings"]].map(([k,l])=><button key={k} onClick={()=>setView(k)} className={view===k?"dm-active":""}>{l}</button>)}</div>
        {view==="dashboard"&&<div className="dm-stack">
          <div className="dm-stats"><Metric title={store.is_demo?"Demo orders":"COD orders"} value={Number(stats.orders||0).toLocaleString("en-BD")}/><Metric title="Order value (uncollected)" value={fmt(stats.placed_total_bdt)} tip="Not real collected revenue"/><Metric title="Published products" value={totalProducts}/><Metric title="On-hand units" value={Number(stats.inventory_units||0)}/></div>
          <div className="dm-panel"><h2>{store.name}</h2><p className="dm-muted">{store.area} · {store.category}</p><p>Public visibility: <strong>{store.is_active?"On":"Off"}</strong></p><p className="dm-muted">{store.is_demo?"Demo-only store; no money or shipment":store.real_cod_approved?"Approved for gated COD checkout":"Merchant verification required before COD can be enabled"}</p><p className="dm-muted">Store URL: <code>/#/store/{store.slug}</code></p>
          <button className="dm-secondary" onClick={()=>setView("store")}>Manage store profile</button></div>
          <div className="dm-panel"><h2>Recent inventory adjustments</h2>{data.stock_adjustments.length===0?<Empty>No manual adjustments yet</Empty>:
          <div className="dm-scroll"><table><thead><tr><th>Time</th><th>Product</th><th>Before</th><th>After</th><th>Δ</th></tr></thead><tbody>{data.stock_adjustments.map((a,i)=><tr key={i}><td>{a.created_at}</td><td>{products.find(p=>p.id===a.product_id)?.name||a.product_id}</td><td>{a.old_quantity}</td><td>{a.new_quantity}</td><td>{a.delta}</td></tr>)}</tbody></table></div>}</div>
        </div>}
        {view==="products"&&<div className="dm-stack">
          <section className="dm-panel"><h2>নতুন পণ্য যোগ করুন</h2><form className="dm-product-form" onSubmit={e=>{e.preventDefault();run(async()=>{await call("/api/merchant/products",{method:"POST",token,body:{...newProduct,price_bdt:Number(newProduct.price_bdt),stock_qty:Number(newProduct.stock_qty)}});setNewProduct({sku:"",name:"",category:"",price_bdt:"",stock_qty:"",is_listed:true});},"Product created in D1");}}>
          {["sku","name","category","price_bdt","stock_qty"].map(k=><Field key={k} label={{sku:"SKU",name:"Product",category:"Category",price_bdt:"Price BDT",stock_qty:"Stock quantity"}[k]}><input style={input} value={newProduct[k]} required type={["price_bdt","stock_qty"].includes(k)?"number":"text"} min={["price_bdt","stock_qty"].includes(k)?0:undefined} onChange={e=>setNewProduct(v=>({...v,[k]:e.target.value}))}/></Field>)}
          <label className="dm-check"><input type="checkbox" checked={newProduct.is_listed} onChange={e=>setNewProduct(v=>({...v,is_listed:e.target.checked}))}/>{store.is_demo?"Publish a demo product":"Publish product listing"}</label><button disabled={busy} type="submit" className="dm-btn">Add product</button></form></section>
          <section className="dm-panel"><h2>আপনার পণ্য ({products.length})</h2>
          {products.length===0?<Empty>No products yet</Empty>:<div className="dm-product-list">{products.map(p=><article key={p.id} className="dm-product">
            <div><strong>{p.name}</strong><p className="dm-muted">{p.sku} · {p.category||"Uncategorised"}</p><p><b>{fmt(p.price_bdt)}</b> · Stock <b>{p.stock_qty}</b> · {p.is_listed?"Published":"Hidden"}</p></div>
            <button className="dm-secondary" onClick={()=>setEdit({...p})}>Edit</button></article>)}</div>}</section>
        </div>}
        {view==="pos"&&<div className="dm-stack">
          <section className="dm-panel"><h2>Demo counter POS</h2><p className="dm-muted">শুধু simulated sale: D1-তে order ও stock movement persist হবে; বাস্তব cash/payment নয়।</p>
            <form className="dm-product-form" onSubmit={e=>{e.preventDefault();const selected=posProduct||products.find(p=>p.is_listed&&p.stock_qty>0)?.id;if(!selected){setError("No available published product");return;}run(()=>call("/api/merchant/pos",{method:"POST",token,body:{items:[{product_id:selected,quantity:Number(posQty)}]}}),"Demo POS entry saved with stock reduction");}}>
              <Field label="Product"><select style={input} required value={posProduct||products.find(p=>p.is_listed&&p.stock_qty>0)?.id||""} onChange={e=>setPosProduct(e.target.value)}>{products.filter(p=>p.is_listed&&p.stock_qty>0).map(p=><option value={p.id} key={p.id}>{p.name} · {fmt(p.price_bdt)} · Stock {p.stock_qty}</option>)}</select></Field>
              <Field label="Quantity"><input style={input} type="number" min={1} max={30} value={posQty} onChange={e=>setPosQty(e.target.value)}/></Field>
              <button type="submit" className="dm-btn" disabled={busy||!products.some(p=>p.is_listed&&p.stock_qty>0)}>Record demo POS sale</button>
            </form></section>
          <section className="dm-panel"><h2>Cashbook entry (demo)</h2><p className="dm-muted">এটি পূর্ণ double-entry accounting নয়। হাতে দেওয়া receipt/expense-এর নমুনা হিসাব।</p>
            <form className="dm-product-form" onSubmit={e=>{e.preventDefault();run(async()=>{await call("/api/merchant/cashbook",{method:"POST",token,body:{...cashForm,amount_bdt:Number(cashForm.amount_bdt)}});setCashForm({kind:"expense",amount_bdt:"",description:""});},"Cashbook entry saved in D1");}}>
              <Field label="Type"><select style={input} value={cashForm.kind} onChange={e=>setCashForm(v=>({...v,kind:e.target.value}))}><option value="expense">Expense</option><option value="receipt">Receipt</option></select></Field>
              <Field label="Amount BDT"><input style={input} type="number" min={1} max={500000} required value={cashForm.amount_bdt} onChange={e=>setCashForm(v=>({...v,amount_bdt:e.target.value}))}/></Field>
              <Field label="Note"><input style={input} minLength={3} required value={cashForm.description} onChange={e=>setCashForm(v=>({...v,description:e.target.value}))}/></Field>
              <button className="dm-btn" disabled={busy} type="submit">Save demo cashbook</button></form>
          </section>
          <section className="dm-panel"><h2>Recent cashbook entries</h2>
            {!(data.cashbook||[]).length?<Empty>No entries yet</Empty>:<div className="dm-scroll"><table><thead><tr><th>Date</th><th>Kind</th><th>Amount</th><th>Description</th></tr></thead>
            <tbody>{data.cashbook.map(row=><tr key={row.id}><td>{row.created_at}</td><td>{row.kind}</td><td>{fmt(row.amount_bdt)}</td><td>{row.description}</td></tr>)}</tbody></table></div>}
          </section>
        </div>}
        {view==="orders"&&<div className="dm-panel"><h2>{store.is_demo?"Store demo orders":"Cash-on-delivery orders"} ({orders.length})</h2><p className="dm-muted">{store.is_demo?"Orders are persistent but demo customers are anonymous.":"Only a merchant may see delivery details. The website does not process or confirm COD cash payments."}</p>
          {orders.length===0?<Empty>অর্ডার আসলে এখানে দেখা যাবে।</Empty>:<div className="dm-scroll"><table><thead><tr><th>Order</th><th>Date</th><th>Customer / Delivery</th><th>Total</th><th>Status</th><th>Action</th></tr></thead><tbody>{orders.map(o=><tr key={o.id}><td>{o.order_number}</td><td>{o.placed_at}</td><td>{store.is_demo?"Demo customer":<div><strong>{o.shipping_name||"—"}</strong><div><a href={"tel:"+o.shipping_phone}>{o.shipping_phone}</a></div><span style={{whiteSpace:"pre-wrap"}}>{o.shipping_address}</span></div>}</td><td>{fmt(o.total_bdt)}</td><td>{o.status}</td><td>{o.status==="placed"?<>
            <button className="dm-secondary" disabled={busy} onClick={()=>run(()=>call("/api/merchant/orders/"+o.id+"/status",{method:"PATCH",token,body:{status:"confirmed"}}),"Order confirmed")}>Confirm</button> <button className="dm-danger" disabled={busy} onClick={()=>run(()=>call("/api/merchant/orders/"+o.id+"/status",{method:"PATCH",token,body:{status:"cancelled"}}),"Order cancelled and stock restored")}>Cancel</button></>:
            o.status==="confirmed"?<><button className="dm-secondary" disabled={busy} onClick={()=>run(()=>call("/api/merchant/orders/"+o.id+"/status",{method:"PATCH",token,body:{status:store.is_demo?"fulfilled":"shipped"}}),store.is_demo?"Demo order fulfilled":"Shipment marked dispatched (not carrier verified)")}>{store.is_demo?"Fulfil demo":"Mark shipped"}</button> <button className="dm-danger" disabled={busy} onClick={()=>run(()=>call("/api/merchant/orders/"+o.id+"/status",{method:"PATCH",token,body:{status:"cancelled"}}),"Order cancelled")}>Cancel</button></>:o.status==="shipped"?<button className="dm-secondary" disabled={busy} onClick={()=>run(()=>call("/api/merchant/orders/"+o.id+"/status",{method:"PATCH",token,body:{status:"fulfilled"}}),"Order marked fulfilled; cash collection not verified")}>Mark fulfilled</button>:<span>—</span>}</td></tr>)}</tbody></table></div>}
        </div>}
        {view==="store"&&<section className="dm-panel"><h2>Store Settings</h2><p className="dm-muted">{store.is_demo?"Demo stores cannot collect money or ship goods.":"Real COD is enabled only after operator verification, D1 backup, release switch and security review. Advance payments are never accepted."}</p>
        <form className="dm-fields" onSubmit={e=>{e.preventDefault();run(()=>call("/api/merchant/store",{method:"PATCH",token,body:storeForm}),"Store profile saved");}}>
          <Field label="Name"><input style={input} required minLength={3} value={storeForm.name} onChange={e=>setStoreForm(v=>({...v,name:e.target.value}))}/></Field>
          <Field label="Category"><select style={input} value={storeForm.category} onChange={e=>setStoreForm(v=>({...v,category:e.target.value}))}>{categories.map(c=><option key={c}>{c}</option>)}</select></Field>
          <Field label="Area"><input style={input} required value={storeForm.area} onChange={e=>setStoreForm(v=>({...v,area:e.target.value}))}/></Field>
          <Field label="Description"><input style={input} value={storeForm.tagline} onChange={e=>setStoreForm(v=>({...v,tagline:e.target.value}))}/></Field>
          <label className="dm-check"><input type="checkbox" checked={storeForm.is_active} onChange={e=>setStoreForm(v=>({...v,is_active:e.target.checked}))}/>{store.is_demo?"Make this labelled demo storefront public":"Make approved storefront public"}</label>
          <button className="dm-btn" disabled={busy} type="submit">Save settings</button>
        </form></section>}
        {edit&&<div className="dm-modal-bg" onClick={()=>setEdit(null)}><section role="dialog" aria-modal="true" aria-label="Edit product" className="dm-panel dm-dialog" onClick={e=>e.stopPropagation()}><h2>Edit: {edit.name}</h2>
          <form className="dm-fields" onSubmit={e=>{e.preventDefault();run(async()=>{await call("/api/merchant/products/"+edit.id,{method:"PATCH",token,body:{name:edit.name,category:edit.category,price_bdt:Number(edit.price_bdt),stock_qty:Number(edit.stock_qty),is_listed:edit.is_listed}});setEdit(null);},"Product updated");}}>
          {["name","category","price_bdt","stock_qty"].map(k=><Field key={k} label={k}><input style={input} type={["price_bdt","stock_qty"].includes(k)?"number":"text"} min={["price_bdt","stock_qty"].includes(k)?0:undefined} required value={edit[k]} onChange={e=>setEdit(v=>({...v,[k]:e.target.value}))}/></Field>)}
          <label className="dm-check"><input type="checkbox" checked={!!edit.is_listed} onChange={e=>setEdit(v=>({...v,is_listed:e.target.checked}))}/>Published</label><div className="dm-actions"><button className="dm-btn" disabled={busy} type="submit">Save to D1</button><button type="button" onClick={()=>setEdit(null)} className="dm-secondary">Close</button></div></form></section></div>}
      </>}
    </div>
    {token&&store&&<nav className="dm-bottom" aria-label="Owner mobile app navigation">{[["dashboard","Home","⌂"],["products","Products","▣"],["pos","POS","⊞"],["orders","Orders","≡"],["store","Settings","⚙"]].map(([k,t,icon])=><button key={k} className={view===k?"selected":""} onClick={()=>{setView(k);window.scrollTo({top:0,behavior:"smooth"});}}><span>{icon}</span>{t}</button>)}</nav>}
  </main>;
}
