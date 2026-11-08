import { useCallback, useEffect, useMemo, useState } from "react";
import "./D1MerchantCenter.css";
import { useUi } from "../UiContext";
import D1MerchantInsights from "./D1MerchantInsights";
import D1StaffManagement from "./D1StaffManagement";

const BASE=(import.meta.env.VITE_D1_COMMERCE_URL || "https://bsmart-commerce-api.bcs-written-rakib.workers.dev").replace(/\/$/,"");
const fmt=n=>"৳"+Number(n||0).toLocaleString("bn-BD");
const ORDER_STATUS_BN={placed:"অর্ডার জমা হয়েছে",confirmed:"নিশ্চিত হয়েছে",processing:"প্রস্তুত হচ্ছে",ready:"পণ্য প্রস্তুত",dispatched:"পাঠানো হয়েছে",shipped:"পাঠানো হয়েছে",fulfilled:"সম্পন্ন",delivered:"ডেলিভারি সম্পন্ন",cancelled:"বাতিল হয়েছে"};
const ORDER_ACTIONS={
  placed:[{status:"confirmed",label:"নিশ্চিত করুন"},{status:"cancelled",label:"বাতিল করুন",danger:true}],
  confirmed:[{status:"processing",label:"প্রস্তুত করা শুরু করুন"},{status:"cancelled",label:"বাতিল করুন",danger:true}],
  processing:[{status:"ready",label:"পণ্য প্রস্তুত"},{status:"cancelled",label:"বাতিল করুন",danger:true}],
  ready:[{status:"dispatched",label:"ডেলিভারি শুরু করুন"}],
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
const PAYMENT_STATUS_BN={demo_no_payment:"ডেমো—পেমেন্ট নেই",pending_cod:"COD—টাকা গ্রহণ বাকি",paid:"টাকা গ্রহণ নিশ্চিত",cancelled_no_payment:"বাতিল—টাকা নেওয়া হয়নি",unpaid:"পেমেন্ট বাকি"};
const RETURN_STATUS_BN={requested:"অনুরোধ এসেছে",approved:"অনুমোদিত",rejected:"প্রত্যাখ্যাত",received:"ফেরত পণ্য গ্রহণ",closed_demo:"প্রক্রিয়া বন্ধ"};
const CASH_KIND_BN={receipt:"টাকা গ্রহণ",expense:"খরচ"};
const empty={email:"",password:""};
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
  const [recoveryToken,setRecoveryToken]=useState("");
  const [inviteToken,setInviteToken]=useState("");
  const [inviteName,setInviteName]=useState("");
  const [data,setData]=useState(null),[busy,setBusy]=useState(false),[error,setError]=useState(""),[note,setNote]=useState("");
  const [storeForm,setStoreForm]=useState({name:"",category:"মুদি",area:"",tagline:""});
  const [newProduct,setNewProduct]=useState({sku:"",name:"",category:"",description:"",brand:"",tags:"",compare_at_price_bdt:"",unit_label:"pcs",price_bdt:"",stock_qty:"",reorder_level:"5",is_listed:true});
  const [edit,setEdit]=useState(null);
  const [posProduct,setPosProduct]=useState("");
  const [posQty,setPosQty]=useState("1");
  const [cashForm,setCashForm]=useState({kind:"expense",amount_bdt:"",description:""});
  const [returnRequests,setReturnRequests]=useState([]);
  const [chatMessages,setChatMessages]=useState([]);
  const [threadMessages,setThreadMessages]=useState([]);
  const [activeCustomerId,setActiveCustomerId]=useState("");
  const [replyText,setReplyText]=useState("");
  const [assistantQuestion,setAssistantQuestion]=useState("");
  const [assistantMessages,setAssistantMessages]=useState([]);
  const [assistantBusy,setAssistantBusy]=useState(false);
  const [assistantError,setAssistantError]=useState("");
  const [assistantAiEnabled,setAssistantAiEnabled]=useState(false);
  const emptyCoupon={code:"",discount_type:"percent",discount_value:"10",min_order_bdt:"0",max_discount_bdt:"",usage_limit:"",per_customer_limit:"1",starts_at:"",ends_at:""};
  const [coupons,setCoupons]=useState([]);
  const [couponForm,setCouponForm]=useState(emptyCoupon);
  const [couponEditId,setCouponEditId]=useState("");
  
  useEffect(()=>{
    const hash=window.location.hash||"";
    const query=hash.includes("?")?hash.slice(hash.indexOf("?")+1):"";
    const params=new URLSearchParams(query);
    const verify=params.get("verify"),reset=params.get("reset");
    const ownerInvite=params.get("owner_invite"),staffInvite=params.get("staff_invite");
    if(ownerInvite||staffInvite){
      sessionStorage.removeItem("bsmart_d1_merchant");
      setToken("");setData(null);
      setInviteToken(ownerInvite||staffInvite);
      setMode(ownerInvite?"owner_invite":"staff_invite");
    }
    if(verify){
      call("/api/merchant/verify-email",{method:"POST",body:{token:verify}})
        .then(()=>{setNote("ইমেইল যাচাই সম্পন্ন হয়েছে। এখন লগইন করুন।");setError("");window.history.replaceState(null,"",window.location.pathname+"#/d1-owner");})
        .catch(e=>setError(e.message||"ইমেইল যাচাই করা যায়নি।"));
    }
    if(reset){setRecoveryToken(reset);setMode("reset");}
  },[]);
  const store=data?.store;
  const inventoryOnly=data?.account?.is_staff&&data?.account?.staff_role==="inventory";
  const load=useCallback(async tk=>{
    const latest=await call("/api/merchant/dashboard",{token:tk});
    setData(latest);
    if(latest.store)setStoreForm({name:latest.store.name,category:latest.store.category||"মুদি",area:latest.store.area||"",tagline:latest.store.tagline||""});
    return latest;
  },[]);
  useEffect(()=>{if(!token)return;load(token).catch(e=>{setError(e.message);if(e.status===401){sessionStorage.removeItem("bsmart_d1_merchant");setToken("");}});},[token,load]);
  useEffect(()=>{
    if(!token||!store)return;
    if(view==="returns")call("/api/merchant/returns",{token}).then(x=>setReturnRequests(x.returns||[])).catch(e=>setError(e.message));
    if(view==="chat")call("/api/merchant/chat",{token}).then(x=>setChatMessages(x.messages||[])).catch(e=>setError(e.message));
    if(view==="coupons")call("/api/merchant/coupons",{token}).then(x=>setCoupons(x.coupons||[])).catch(e=>setError(e.message));
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
    if(mode==="owner_invite"||mode==="staff_invite"){
      setBusy(true);setError("");setNote("");
      try{
        const endpoint=mode==="owner_invite"?"/api/merchant/accept-owner-invite":"/api/merchant/staff/accept-invite";
        const result=await call(endpoint,{method:"POST",body:{token:inviteToken,display_name:inviteName,password:form.password}});
        sessionStorage.setItem("bsmart_d1_merchant",result.token);
        setToken(result.token);setForm(empty);setInviteToken("");setInviteName("");setMode("login");
        window.history.replaceState(null,"",window.location.pathname+"#/d1-owner");
        setNote(mode==="owner_invite"?"মালিকের অ্যাকাউন্ট তৈরি হয়েছে। দোকানটি Platform Admin অনুমোদন না দেওয়া পর্যন্ত ব্যক্তিগত থাকবে।":"কর্মী অ্যাকাউন্ট তৈরি হয়েছে। আপনার নির্ধারিত ভূমিকা অনুযায়ী প্রবেশাধিকার চালু হয়েছে।");
      }catch(e){setError(e.message||"আমন্ত্রণ গ্রহণ করা যায়নি।");}
      finally{setBusy(false);}
      return;
    }
    await run(async()=>{
      if(mode==="register"){
        await call("/api/merchant/register",{method:"POST",body:{email:form.email,password:form.password}});
        setMode("login");setForm({email:form.email,password:""});
        return;
      }
      if(mode==="forgot"){
        await call("/api/merchant/forgot-password",{method:"POST",body:{email:form.email}});
        setMode("login");setForm({email:form.email,password:""});
        return;
      }
      if(mode==="reset"){
        await call("/api/merchant/reset-password",{method:"POST",body:{token:recoveryToken,password:form.password}});
        setRecoveryToken("");setMode("login");setForm(empty);
        window.history.replaceState(null,"",window.location.pathname+"#/d1-owner");
        return;
      }
      const result=await call("/api/merchant/login",{method:"POST",body:{email:form.email,password:form.password}});
      sessionStorage.setItem("bsmart_d1_merchant",result.token);setToken(result.token);setForm(empty);
    },mode==="login"?"দোকান ব্যবস্থাপনায় লগইন করা হয়েছে।":mode==="register"?"অ্যাকাউন্ট তৈরি হয়েছে। ইমেইলে পাঠানো লিংক দিয়ে যাচাই করে লগইন করুন।":mode==="forgot"?"অ্যাকাউন্ট থাকলে পাসওয়ার্ড রিসেটের লিংক ইমেইলে পাঠানো হয়েছে।":"পাসওয়ার্ড পরিবর্তন হয়েছে। নতুন পাসওয়ার্ড দিয়ে লগইন করুন।");
  }
  async function resendVerification(){
    if(!form.email.trim()){setError("আগে আপনার ইমেইল লিখুন।");return;}
    await run(()=>call("/api/merchant/resend-verification",{method:"POST",body:{email:form.email}}),"যাচাইয়ের প্রয়োজন থাকলে ইমেইলে নতুন লিংক পাঠানো হয়েছে।");
  }
  async function sendOwnerQuestion(value){
    const question=String(value||"").trim();
    if(!question||assistantBusy)return;
    const history=assistantMessages.slice(-6).map(m=>({role:m.role,content:m.content}));
    setAssistantMessages(current=>[...current,{role:"user",content:question}]);
    setAssistantQuestion("");setAssistantError("");setAssistantBusy(true);
    try{
      const result=await call("/api/merchant/assistant",{method:"POST",token,body:{question,history}});
      setAssistantAiEnabled(!!result.ai_enabled);
      setAssistantMessages(current=>[...current,{role:"assistant",content:result.text||"এখন উত্তর পাওয়া যায়নি।",metrics:result.metrics,low_stock_products:result.low_stock_products||[],top_products:result.top_products||[]}]);
    }catch(e){setAssistantError(e.message||"সহকারী এখন উত্তর দিতে পারছে না।");}
    finally{setAssistantBusy(false);}
  }
  function askOwnerAssistant(e){e.preventDefault();sendOwnerQuestion(assistantQuestion);}
  function couponDateValue(value){
    if(!value)return "";
    const d=new Date(value);if(Number.isNaN(d.getTime()))return "";
    return new Date(d.getTime()-d.getTimezoneOffset()*60000).toISOString().slice(0,16);
  }
  async function saveCoupon(e){
    e.preventDefault();
    await run(async()=>{
      const payload={...couponForm,code:couponForm.code.toUpperCase(),discount_value:Number(couponForm.discount_value),min_order_bdt:Number(couponForm.min_order_bdt||0),
        max_discount_bdt:couponForm.max_discount_bdt===""?null:Number(couponForm.max_discount_bdt),
        usage_limit:couponForm.usage_limit===""?null:Number(couponForm.usage_limit),
        per_customer_limit:couponForm.per_customer_limit===""?null:Number(couponForm.per_customer_limit),
        starts_at:couponForm.starts_at?new Date(couponForm.starts_at).toISOString():null,
        ends_at:couponForm.ends_at?new Date(couponForm.ends_at).toISOString():null};
      await call(couponEditId?"/api/merchant/coupons/"+encodeURIComponent(couponEditId):"/api/merchant/coupons",{method:couponEditId?"PATCH":"POST",token,body:payload});
      const result=await call("/api/merchant/coupons",{token});setCoupons(result.coupons||[]);
      setCouponEditId("");setCouponForm(emptyCoupon);
    },couponEditId?"কুপন আপডেট হয়েছে।":"নতুন কুপন তৈরি হয়েছে।");
  }
  async function deactivateCoupon(id){
    await run(async()=>{
      await call("/api/merchant/coupons/"+encodeURIComponent(id),{method:"DELETE",token});
      const result=await call("/api/merchant/coupons",{token});setCoupons(result.coupons||[]);
    },"কুপন নিষ্ক্রিয় করা হয়েছে।");
  }
  function editCoupon(coupon){
    setCouponEditId(coupon.id);
    setCouponForm({code:coupon.code,discount_type:coupon.discount_type,discount_value:String(coupon.discount_value),min_order_bdt:String(coupon.min_order_bdt||0),
      max_discount_bdt:coupon.max_discount_bdt==null?"":String(coupon.max_discount_bdt),usage_limit:coupon.usage_limit==null?"":String(coupon.usage_limit),
      per_customer_limit:coupon.per_customer_limit==null?"":String(coupon.per_customer_limit),starts_at:couponDateValue(coupon.starts_at),ends_at:couponDateValue(coupon.ends_at)});
    setView("coupons");
  }

  async function logout(){
    try{if(token)await call("/api/merchant/logout",{method:"POST",token});}catch{/* local logout even offline */}
    sessionStorage.removeItem("bsmart_d1_merchant");setToken("");setData(null);setNote("");setError("");
  }
  const products=data?.products||[],orders=data?.orders||[],stats=data?.metrics||{};
  const totalProducts=useMemo(()=>products.filter(p=>p.is_listed).length,[products]);
  const lowStockProducts=useMemo(()=>products.filter(p=>p.is_listed&&Number(p.stock_qty)<=Number(p.reorder_level??5)),[products]);
  return <main className="dm-page">
    <header className="dm-header"><a href="#/" className="dm-logo">B-SMART <span>দোকান পরিচালনা</span></a>
      <div className="dm-header-side"><span className="dm-d1">D1-তে তথ্য সংরক্ষিত</span><a href="#/stores">সব দোকান</a><a href="#/d1-platform-admin">Platform admin</a><button type="button" className="dm-theme-toggle" onClick={toggleTheme} aria-pressed={theme==="dark"} aria-label={theme==="dark"?"লাইট মোড চালু করুন":"ডার্ক মোড চালু করুন"} title={theme==="dark"?"লাইট মোড চালু করুন":"ডার্ক মোড চালু করুন"}>{theme==="dark"?"☀️":"🌙"}</button>{token&&<button className="dm-text-btn" onClick={logout}>লগআউট</button>}</div>
    </header>
    <div className="dm-main">
      <section className="dm-heading"><div><p className="dm-overline">Cloudflare D1 · {store?.is_demo===false?"COD দোকান পরিচালনা":"পরীক্ষামূলক দোকান পরিচালনা"}</p><h1>স্টোর ম্যানেজমেন্ট</h1>
      <p>{store?.is_demo===false?"পণ্য, মজুত, COD অর্ডার এবং হাতে পাওয়া পেমেন্টের তথ্য পরিচালনা করুন।":"নিজের পরীক্ষামূলক দোকান, পণ্য, মজুত ও অর্ডারের তথ্য এক জায়গা থেকে পরিচালনা করুন।"}</p></div>
      {store&&<a className="dm-visit" href={"#/store/"+store.slug}>দোকানের প্রিভিউ দেখুন ↗</a>}</section>
      {store&&<div className="dm-warning" role="note">{store.is_demo ? "এটি একটি পরীক্ষামূলক দোকান। এখানে বাস্তব অর্ডার বা টাকা গ্রহণ করা হয় না।" : !store.is_active ? "আপনার দোকানটি যাচাইয়ের অপেক্ষায় আছে। পণ্য ও মজুত প্রস্তুত করুন; অনুমোদনের পর দোকানটি প্রকাশিত হবে।" : "আপনার দোকানে Cash on Delivery চালু। অর্ডার, মজুত ও পেমেন্টের অবস্থা Cloudflare D1-তে সংরক্ষিত হয়।"}</div>}
      {error&&<p className="dm-error" role="alert">{error}</p>}{note&&<p className="dm-success" role="status">{note}</p>}
      {!token?<div className="dm-auth"><h2>{mode==="login"?"দোকান মালিক / কর্মীর লগইন":mode==="register"?"নতুন দোকান মালিকের অ্যাকাউন্ট":mode==="forgot"?"পাসওয়ার্ড পুনরুদ্ধার":mode==="owner_invite"?"দোকান মালিকের অ্যাকাউন্ট চালু করুন":mode==="staff_invite"?"কর্মী অ্যাকাউন্ট চালু করুন":"নতুন পাসওয়ার্ড সেট করুন"}</h2>
        <p>{mode==="register"?"ইমেইল যাচাইয়ের পর দোকান পরিচালনার অ্যাকাউন্ট চালু হবে।":mode==="forgot"?"আপনার অ্যাকাউন্টের ইমেইল লিখুন। রিসেট লিংক পাঠানো হবে।":mode==="reset"?"নতুন শক্তিশালী পাসওয়ার্ড লিখুন। লিংকটি ৬০ মিনিটের মধ্যে ব্যবহার করতে হবে।":mode==="owner_invite"?"আপনার নাম ও নতুন পাসওয়ার্ড সেট করুন। এই লিংকটি একবার ব্যবহার করা যাবে।":mode==="staff_invite"?"আপনার নাম ও নতুন পাসওয়ার্ড সেট করুন। আপনার স্টোর মালিক নির্ধারিত ভূমিকা অনুযায়ী অনুমতি পাবেন।":"যাচাইকৃত ইমেইল ও পাসওয়ার্ড দিয়ে Cloudflare Primary স্টোর পরিচালনা করুন।"}</p>
        <form onSubmit={authenticate} className="dm-fields">
          {mode!=="reset"&&mode!=="owner_invite"&&mode!=="staff_invite"&&<Field label="ইমেইল"><input style={input} type="email" autoComplete="email" required value={form.email} onChange={e=>setForm(v=>({...v,email:e.target.value}))}/></Field>}
          {(mode==="owner_invite"||mode==="staff_invite")&&<Field label="আপনার নাম"><input style={input} required minLength={2} maxLength={120} value={inviteName} onChange={e=>setInviteName(e.target.value)}/></Field>}
          {(mode==="login"||mode==="register"||mode==="reset"||mode==="owner_invite"||mode==="staff_invite")&&<Field label={mode==="login"?"পাসওয়ার্ড":"নতুন পাসওয়ার্ড (কমপক্ষে ১২ অক্ষর)"}><input style={input} type="password" autoComplete={mode==="login"?"current-password":"new-password"} minLength={12} maxLength={128} required value={form.password} onChange={e=>setForm(v=>({...v,password:e.target.value}))}/></Field>}
          <button className="dm-btn" disabled={busy} type="submit">{busy?"প্রক্রিয়াকরণ চলছে…":mode==="login"?"লগইন করুন":mode==="register"?"অ্যাকাউন্ট তৈরি করুন":mode==="forgot"?"রিসেট লিংক পাঠান":mode==="owner_invite"||mode==="staff_invite"?"অ্যাকাউন্ট চালু করুন":"পাসওয়ার্ড পরিবর্তন করুন"}</button>
        </form>
        {mode==="login"&&<><p className="dm-muted">নতুন দোকান খুলতে Platform Admin-এর যাচাইকৃত আমন্ত্রণ লিংক প্রয়োজন।</p><button className="dm-text-btn" onClick={()=>{setMode("forgot");setError("");setNote("");}}>পাসওয়ার্ড ভুলে গেছেন?</button><button className="dm-text-btn" onClick={resendVerification}>যাচাই ইমেইল আবার পাঠান</button></>}
        {mode!=="login"&&mode!=="owner_invite"&&mode!=="staff_invite"&&<button className="dm-text-btn" onClick={()=>{setMode("login");setRecoveryToken("");setError("");setNote("");setForm(empty);}}>লগইনে ফিরে যান</button>}
      </div>:data===null?<p>Cloudflare D1 থেকে দোকানের তথ্য আনা হচ্ছে…</p>:!store?
      <section className="dm-panel"><h2>আপনার প্রথম দোকান তৈরি করুন</h2><p className="dm-muted">দোকানটি প্রথমে ব্যক্তিগত থাকবে। পণ্য ও মজুত যোগ করে যাচাইয়ের জন্য জমা দিন। অনুমোদনের পর গ্রাহকরা অর্ডার করতে পারবেন।</p>
        <form className="dm-fields" onSubmit={e=>{e.preventDefault();run(async()=>{await call("/api/merchant/store",{method:"POST",token,body:storeForm});},"দোকানের তথ্য সংরক্ষিত হয়েছে।");}}>
        <Field label="দোকানের নাম"><input style={input} value={storeForm.name} minLength={3} required onChange={e=>setStoreForm(x=>({...x,name:e.target.value}))}/></Field>
        <Field label="বিভাগ"><select style={input} value={storeForm.category} onChange={e=>setStoreForm(x=>({...x,category:e.target.value}))}>{categories.map(c=><option key={c}>{c}</option>)}</select></Field>
        <Field label="এলাকা"><input style={input} required value={storeForm.area} onChange={e=>setStoreForm(x=>({...x,area:e.target.value}))} placeholder="যেমন: রাজশাহী"/></Field>
        <Field label="সংক্ষিপ্ত বিবরণ (ঐচ্ছিক)"><input style={input} maxLength={160} value={storeForm.tagline} onChange={e=>setStoreForm(x=>({...x,tagline:e.target.value}))}/></Field>
        <button disabled={busy} type="submit" className="dm-btn">দোকান তৈরি করুন</button></form>
      </section>:
      <>
        <div className="dm-tabs">{[
          ["dashboard","সারসংক্ষেপ"],
          ...(!data.account?.is_staff||["manager","analyst"].includes(data.account?.staff_role)?[["assistant","AI সহকারী"],["analytics","বিক্রয় বিশ্লেষণ"]]:[]),
          ...(!data.account?.is_staff||["manager","sales","inventory","analyst"].includes(data.account?.staff_role)?[["alerts","মজুত সতর্কতা"]]:[]),
          ...(!data.account?.is_staff||["manager","sales","inventory","analyst"].includes(data.account?.staff_role)?[["products","পণ্য ও মজুত"]]:[]),
          ...(!data.account?.is_staff||data.account?.staff_role==="manager"?[["coupons","কুপন"]]:[]),
          ...(!data.account?.is_staff||["manager","sales"].includes(data.account?.staff_role)?[["pos",store.is_demo?"পরীক্ষামূলক বিক্রি":"ক্যাশ বিক্রি"]]:[]),
          ...(!data.account?.is_staff||["manager","sales","support","analyst"].includes(data.account?.staff_role)?[["orders","অর্ডার"]]:[]),
          ...(!data.account?.is_staff||["manager","support"].includes(data.account?.staff_role)?[["returns","ফেরত"],["chat","ক্রেতার বার্তা"]]:[]),
          ...(!data.account?.is_staff?[["staff","কর্মী ও অনুমতি"]]:[]),
          ...(!data.account?.is_staff||data.account?.staff_role==="manager"?[["store","দোকানের সেটিংস"]]:[])
        ].map(([k,l])=><button key={k} onClick={()=>setView(k)} className={view===k?"dm-active":""}>{l}</button>)}</div>
        {view==="dashboard"&&<div className="dm-stack">
          <div className="dm-stats">{store.is_demo?<><Metric title="ডেমো অর্ডার" value={Number(stats.orders||0).toLocaleString("en-BD")}/><Metric title="বাতিল হয়নি এমন নমুনা বিক্রি" value={fmt(stats.placed_total_bdt)} tip="বাস্তবে কোনো টাকা আদায় হয়নি"/><Metric title="প্রকাশিত পণ্য" value={totalProducts}/><Metric title="মজুতের পরিমাণ" value={Number(stats.inventory_units||0)}/><Metric title="কম স্টক" value={Number(stats.low_stock_count||0)+"টি"}/></>:<><Metric title="অর্ডার" value={Number(stats.orders||0).toLocaleString("en-BD")}/><Metric title="COD অর্ডারের মোট মূল্য" value={fmt(stats.placed_total_bdt)} tip="এটি অর্ডারের মূল্য; আদায়কৃত টাকা নয়"/><Metric title="COD আদায় নিশ্চিত" value={fmt(stats.cod_paid_total_bdt)}/><Metric title="COD টাকা বাকি" value={fmt(stats.cod_pending_total_bdt)}/><Metric title="প্রকাশিত পণ্য" value={totalProducts}/><Metric title="মজুতের পরিমাণ" value={Number(stats.inventory_units||0)}/><Metric title="কম স্টক" value={Number(stats.low_stock_count||0)+"টি"}/></>}</div>
          {lowStockProducts.length>0&&<div className="dm-panel" style={{borderColor:"#e5a23b"}}><h2>কম স্টকের সতর্কতা ({lowStockProducts.length})</h2><p className="dm-muted">নির্ধারিত reorder level-এ বা তার নিচে থাকা পণ্যগুলো দ্রুত পুনরায় সংগ্রহ করুন।</p><div className="dm-scroll"><table><thead><tr><th>পণ্য</th><th>বর্তমান মজুত</th><th>সতর্কতার সীমা</th></tr></thead><tbody>{lowStockProducts.map(p=><tr key={p.id}><td>{p.name}</td><td>{p.stock_qty}</td><td>{p.reorder_level??5}</td></tr>)}</tbody></table></div><button className="dm-secondary" onClick={()=>setView("products")}>মজুত পরিচালনা করুন</button></div>}<div className="dm-panel"><h2>{store.name}</h2><p className="dm-muted">{store.area} · {store.category}</p><p>{store.is_demo?"ডেমো দোকান প্রকাশিত":"দোকান প্রকাশিত"}: <strong>{store.is_active?"হ্যাঁ":"না"}</strong></p><p className="dm-muted">দোকানের লিংক: <code>/#/store/{store.slug}</code></p>
          <button className="dm-secondary" onClick={()=>setView("store")}>দোকানের তথ্য সম্পাদনা করুন</button></div>
          <div className="dm-panel"><h2>মজুত সংশোধনের ইতিহাস</h2>{data.stock_adjustments.length===0?<Empty>এখনো মজুত সংশোধন করা হয়নি।</Empty>:
          <div className="dm-scroll"><table><thead><tr><th>সময়</th><th>পণ্য</th><th>আগের পরিমাণ</th><th>নতুন পরিমাণ</th><th>Δ</th></tr></thead><tbody>{data.stock_adjustments.map((a,i)=><tr key={i}><td>{a.created_at}</td><td>{products.find(p=>p.id===a.product_id)?.name||a.product_id}</td><td>{a.old_quantity}</td><td>{a.new_quantity}</td><td>{a.delta}</td></tr>)}</tbody></table></div>}</div>
        </div>}
        {view==="coupons"&&<div className="dm-stack">
          <section className="dm-panel">
            <h2>{couponEditId?"কুপন সম্পাদনা":"নতুন কুপন তৈরি"}</h2>
            <form className="dm-fields" onSubmit={saveCoupon}>
              <Field label="কুপন কোড"><input style={input} required minLength={3} maxLength={32} pattern="[A-Za-z0-9_-]+" value={couponForm.code} onChange={e=>setCouponForm(v=>({...v,code:e.target.value.toUpperCase()}))}/></Field>
              <Field label="ছাড়ের ধরন"><select style={input} value={couponForm.discount_type} onChange={e=>setCouponForm(v=>({...v,discount_type:e.target.value}))}><option value="percent">শতকরা ছাড় (%)</option><option value="fixed">নির্দিষ্ট টাকা (৳)</option></select></Field>
              <Field label="ছাড়ের পরিমাণ"><input style={input} type="number" min="1" max={couponForm.discount_type==="percent"?100:10000000} required value={couponForm.discount_value} onChange={e=>setCouponForm(v=>({...v,discount_value:e.target.value}))}/></Field>
              <Field label="ন্যূনতম অর্ডার (৳)"><input style={input} type="number" min="0" value={couponForm.min_order_bdt} onChange={e=>setCouponForm(v=>({...v,min_order_bdt:e.target.value}))}/></Field>
              <Field label="সর্বোচ্চ ছাড় (৳, ঐচ্ছিক)"><input style={input} type="number" min="1" value={couponForm.max_discount_bdt} onChange={e=>setCouponForm(v=>({...v,max_discount_bdt:e.target.value}))}/></Field>
              <Field label="মোট ব্যবহারের সীমা (ঐচ্ছিক)"><input style={input} type="number" min="1" value={couponForm.usage_limit} onChange={e=>setCouponForm(v=>({...v,usage_limit:e.target.value}))}/></Field>
              <Field label="প্রতি ক্রেতার ব্যবহারের সীমা"><input style={input} type="number" min="1" value={couponForm.per_customer_limit} onChange={e=>setCouponForm(v=>({...v,per_customer_limit:e.target.value}))}/></Field>
              <Field label="শুরুর সময় (ঐচ্ছিক)"><input style={input} type="datetime-local" value={couponForm.starts_at} onChange={e=>setCouponForm(v=>({...v,starts_at:e.target.value}))}/></Field>
              <Field label="শেষ সময় (ঐচ্ছিক)"><input style={input} type="datetime-local" value={couponForm.ends_at} onChange={e=>setCouponForm(v=>({...v,ends_at:e.target.value}))}/></Field>
              <button className="dm-btn" disabled={busy} type="submit">{couponEditId?"পরিবর্তন সংরক্ষণ":"কুপন তৈরি করুন"}</button>
              {couponEditId&&<button type="button" className="dm-secondary" onClick={()=>{setCouponEditId("");setCouponForm(emptyCoupon);}}>সম্পাদনা বাতিল</button>}
            </form>
          </section>
          <section className="dm-panel"><h2>দোকানের কুপন ({coupons.length})</h2>
            {coupons.length===0?<p className="dm-muted">এখনো কোনো কুপন তৈরি করা হয়নি।</p>:<div className="dm-scroll"><table><thead><tr><th>কোড</th><th>ছাড়</th><th>ব্যবহার</th><th>অবস্থা</th><th>কাজ</th></tr></thead><tbody>
              {coupons.map(c=><tr key={c.id}><td><b>{c.code}</b><small>{c.min_order_bdt?(" · ন্যূনতম ৳"+c.min_order_bdt):""}</small></td><td>{c.discount_type==="percent"?c.discount_value+"%":"৳"+c.discount_value}</td><td>{c.usage_count||0}{c.usage_limit?"/"+c.usage_limit:""}</td><td>{c.is_active?"সক্রিয়":"নিষ্ক্রিয়"}</td><td><button type="button" className="dm-secondary" onClick={()=>editCoupon(c)}>সম্পাদনা</button> <button type="button" className="dm-secondary" disabled={!c.is_active} onClick={()=>deactivateCoupon(c.id)}>বন্ধ করুন</button></td></tr>)}
            </tbody></table></div>}
          </section>
        </div>}
        {view==="analytics"&&<D1MerchantInsights token={token} mode="analytics"/>}
        {view==="alerts"&&<D1MerchantInsights token={token} mode="alerts"/>}
        {view==="staff"&&!data.account?.is_staff&&<D1StaffManagement token={token} call={call}/>}
        {view==="assistant"&&<div className="dm-stack">
          <section className="dm-panel">
            <h2>ব্যবসার AI সহকারী</h2>
            <p className="dm-muted">আপনার নিজের দোকানের অর্ডার, বিক্রি, মজুত ও ক্রেতার সারাংশ থেকে উত্তর তৈরি করে। অন্য দোকানের তথ্য এতে ব্যবহার করা হয় না।</p>
            <p className="dm-muted">{assistantAiEnabled?"Workers AI চালু আছে। উত্তরগুলো দোকানের ডেটা দিয়ে যাচাই করা হয়।":"নিরাপদ ডেটা-ভিত্তিক সহকারী সক্রিয়। AI model এখনো চালু করা হয়নি।"}</p>
            <div className="dm-ai-chat" aria-live="polite" style={{maxHeight:380,overflowY:"auto",padding:10,border:"1px solid var(--dm-line)",borderRadius:10}}>
              {assistantMessages.length===0&&<p className="dm-muted">প্রশ্ন করুন: আজকের বিক্রি কত? কোন পণ্যের স্টক কম? সেরা বিক্রিত পণ্য কোনটি?</p>}
              {assistantMessages.map((m,i)=><div key={i} style={{marginBottom:10,padding:11,borderRadius:10,background:m.role==="user"?"var(--dm-soft)":"var(--dm-surface)",border:"1px solid var(--dm-line)",whiteSpace:"pre-line",maxWidth:"100%"}}>
                <strong>{m.role==="user"?"আপনি":"সহকারী"}</strong><p style={{margin:"5px 0 0"}}>{m.content}</p>
                {m.metrics&&<div className="dm-stats" style={{marginTop:10}}>
                  <Metric title="আজকের অর্ডার মূল্য" value={fmt(m.metrics.today_order_value_bdt)}/>
                  <Metric title="আজ আদায় নিশ্চিত" value={fmt(m.metrics.today_collected_bdt)}/>
                  <Metric title="কম স্টক" value={m.metrics.low_stock_count+"টি"}/>
                  <Metric title="পুনরায় অর্ডারকারী" value={m.metrics.repeat_customer_count+" জন"}/>
                </div>}
                {m.low_stock_products?.length>0&&<ul>{m.low_stock_products.map(p=><li key={p.id}>{p.name}: {p.stock_qty}টি বাকি (সতর্কতা {p.reorder_level})</li>)}</ul>}
                {m.top_products?.length>0&&<ul>{m.top_products.map(p=><li key={p.product_id}>{p.name}: {p.units_sold}টি বিক্রি</li>)}</ul>}
              </div>)}
              {assistantBusy&&<p className="dm-muted">তথ্য যাচাই করে উত্তর তৈরি হচ্ছে…</p>}
              {assistantError&&<p className="dm-error" role="alert">{assistantError}</p>}
            </div>
            <div style={{display:"flex",flexWrap:"wrap",gap:7,margin:"10px 0"}}>
              {["আজকের বিক্রি কত?","কোন পণ্যের স্টক কম?","সেরা বিক্রিত পণ্য কোনটি?","ক্রেতাদের অবস্থা কেমন?"].map(q=><button key={q} type="button" className="dm-secondary" disabled={assistantBusy} onClick={()=>sendOwnerQuestion(q)}>{q}</button>)}
            </div>
            <form onSubmit={askOwnerAssistant} style={{display:"flex",gap:8}}>
              <input style={input} value={assistantQuestion} maxLength={500} onChange={e=>setAssistantQuestion(e.target.value)} placeholder="আপনার ব্যবসা সম্পর্কে প্রশ্ন লিখুন…" aria-label="AI assistant question"/>
              <button className="dm-btn" type="submit" disabled={assistantBusy||!assistantQuestion.trim()}>জিজ্ঞেস করুন</button>
            </form>
          </section>
        </div>}
        {view==="products"&&<div className="dm-stack">
          {!inventoryOnly&&<section className="dm-panel"><h2>নতুন পণ্য যোগ করুন</h2><form className="dm-product-form" onSubmit={e=>{e.preventDefault();run(async()=>{await call("/api/merchant/products",{method:"POST",token,body:{...newProduct,tags:newProduct.tags.split(",").map(x=>x.trim()).filter(Boolean),price_bdt:Number(newProduct.price_bdt),stock_qty:Number(newProduct.stock_qty),reorder_level:Number(newProduct.reorder_level),compare_at_price_bdt:newProduct.compare_at_price_bdt===""?null:Number(newProduct.compare_at_price_bdt)}});setNewProduct({sku:"",name:"",category:"",description:"",brand:"",tags:"",compare_at_price_bdt:"",unit_label:"pcs",price_bdt:"",stock_qty:"",reorder_level:"5",is_listed:true});},"নতুন পণ্য সংরক্ষিত হয়েছে।");}}>
          {["sku","name","category","brand","unit_label","price_bdt","compare_at_price_bdt","stock_qty","reorder_level","tags"].map(k=><Field key={k} label={{sku:"পণ্য কোড (SKU)",name:"পণ্যের নাম",category:"বিভাগ",brand:"ব্র্যান্ড (ঐচ্ছিক)",unit_label:"একক",price_bdt:"বিক্রয়মূল্য (টাকা)",compare_at_price_bdt:"আগের/তুলনামূলক দাম (ঐচ্ছিক)",stock_qty:"মজুতের পরিমাণ",reorder_level:"কম স্টকের সতর্কতা (পরিমাণ)",tags:"ট্যাগ (কমা দিয়ে লিখুন)"}[k]}><input style={input} value={newProduct[k]} required={["sku","name","category","price_bdt","stock_qty"].includes(k)} type={["price_bdt","stock_qty","compare_at_price_bdt","reorder_level"].includes(k)?"number":"text"} min={["price_bdt","stock_qty","compare_at_price_bdt","reorder_level"].includes(k)?0:undefined} onChange={e=>setNewProduct(v=>({...v,[k]:e.target.value}))}/></Field>)}
          <Field label="পণ্যের বিস্তারিত বিবরণ"><textarea style={{...input,minHeight:90}} maxLength={3000} value={newProduct.description} onChange={e=>setNewProduct(v=>({...v,description:e.target.value}))}/></Field>
          <label className="dm-check"><input type="checkbox" checked={newProduct.is_listed} onChange={e=>setNewProduct(v=>({...v,is_listed:e.target.checked}))}/>{store.is_demo?"পণ্যটি পরীক্ষামূলক দোকানে দেখান":"পণ্যটি দোকানে প্রকাশ করুন"}</label><button disabled={busy} type="submit" className="dm-btn">পণ্য যোগ করুন</button></form></section>}
          <section className="dm-panel"><h2>আপনার পণ্য ({products.length})</h2>
          {products.length===0?<Empty>এখনো কোনো পণ্য যোগ করা হয়নি।</Empty>:<div className="dm-product-list">{products.map(p=><article key={p.id} className="dm-product">
            <div><strong>{p.name}</strong><p className="dm-muted">{p.sku} · {p.category||"বিভাগ দেওয়া নেই"}</p><p><b>{fmt(p.price_bdt)}</b> · মজুত <b>{p.stock_qty}</b> · সতর্কতা {p.reorder_level??5} · {p.is_listed?"প্রকাশিত":"লুকানো"}</p></div>
            <button className="dm-secondary" onClick={()=>setEdit({...p})}>{inventoryOnly?"মজুত সংশোধন":"সম্পাদনা"}</button></article>)}</div>}</section>
        </div>}
        {view==="pos"&&<div className="dm-stack">
          <section className="dm-panel"><h2>{store.is_demo?"পরীক্ষামূলক কাউন্টার বিক্রি":"কাউন্টার বিক্রি"}</h2><p className="dm-muted">{store.is_demo?"নমুনা বিক্রি ও মজুতের পরিবর্তন D1-তে সংরক্ষিত হবে।":"নগদ বিক্রি, পেমেন্ট এবং মজুতের পরিবর্তন একসঙ্গে D1-তে সংরক্ষিত হবে।"}</p>
            <form className="dm-product-form" onSubmit={e=>{e.preventDefault();const selected=posProduct||products.find(p=>p.is_listed&&p.stock_qty>0)?.id;if(!selected){setError("বিক্রির জন্য প্রকাশিত ও মজুত থাকা কোনো পণ্য নেই।");return;}run(()=>call("/api/merchant/pos",{method:"POST",token,body:{items:[{product_id:selected,quantity:Number(posQty)}]}}),store.is_demo?"নমুনা বিক্রি ও মজুতের পরিবর্তন সংরক্ষিত হয়েছে।":"নগদ বিক্রি, পেমেন্ট ও মজুত সংরক্ষিত হয়েছে।");}}>
              <Field label="পণ্য"><select style={input} required value={posProduct||products.find(p=>p.is_listed&&p.stock_qty>0)?.id||""} onChange={e=>setPosProduct(e.target.value)}>{products.filter(p=>p.is_listed&&p.stock_qty>0).map(p=><option value={p.id} key={p.id}>{p.name} · {fmt(p.price_bdt)} · মজুত {p.stock_qty}</option>)}</select></Field>
              <Field label="পরিমাণ"><input style={input} type="number" min={1} max={30} value={posQty} onChange={e=>setPosQty(e.target.value)}/></Field>
              <button type="submit" className="dm-btn" disabled={busy||!products.some(p=>p.is_listed&&p.stock_qty>0)}>{store.is_demo?"নমুনা বিক্রি সংরক্ষণ করুন":"নগদ বিক্রি সংরক্ষণ করুন"}</button>
            </form></section>
          {(!data.account?.is_staff||data.account?.staff_role==="manager")&&<section className="dm-panel"><h2>নগদ হিসাব</h2><p className="dm-muted">{store.is_demo?"এটি পরীক্ষামূলক নগদ হিসাব।":"দৈনন্দিন নগদ গ্রহণ ও খরচের এন্ট্রি এখানে রাখুন।"}</p>
            <form className="dm-product-form" onSubmit={e=>{e.preventDefault();run(async()=>{await call("/api/merchant/cashbook",{method:"POST",token,body:{...cashForm,amount_bdt:Number(cashForm.amount_bdt)}});setCashForm({kind:"expense",amount_bdt:"",description:""});},store.is_demo?"নমুনা নগদ হিসাব সংরক্ষিত হয়েছে।":"নগদ হিসাব সংরক্ষিত হয়েছে।");}}>
              <Field label="ধরন"><select style={input} value={cashForm.kind} onChange={e=>setCashForm(v=>({...v,kind:e.target.value}))}><option value="expense">খরচ</option><option value="receipt">টাকা গ্রহণ</option></select></Field>
              <Field label="পরিমাণ (টাকা)"><input style={input} type="number" min={1} max={500000} required value={cashForm.amount_bdt} onChange={e=>setCashForm(v=>({...v,amount_bdt:e.target.value}))}/></Field>
              <Field label="বিবরণ"><input style={input} minLength={3} required value={cashForm.description} onChange={e=>setCashForm(v=>({...v,description:e.target.value}))}/></Field>
              <button className="dm-btn" disabled={busy} type="submit">হিসাব সংরক্ষণ করুন</button></form>
          </section>
          </section>}
          {(!data.account?.is_staff||data.account?.staff_role==="manager")&&<section className="dm-panel"><h2>সাম্প্রতিক নগদ হিসাব</h2>
            {!(data.cashbook||[]).length?<Empty>এখনো কোনো হিসাব যোগ করা হয়নি।</Empty>:<div className="dm-scroll"><table><thead><tr><th>তারিখ</th><th>ধরন</th><th>পরিমাণ</th><th>বিবরণ</th></tr></thead>
            <tbody>{data.cashbook.map(row=><tr key={row.id}><td>{row.created_at}</td><td>{CASH_KIND_BN[row.kind]||row.kind}</td><td>{fmt(row.amount_bdt)}</td><td>{row.description}</td></tr>)}</tbody></table></div>}
          </section>}
        </div>}
        {view==="orders"&&<div className="dm-panel"><h2>{store.is_demo?"পরীক্ষামূলক অর্ডার":"দোকানের অর্ডার"} ({orders.length})</h2><p className="dm-muted">{store.is_demo?"অর্ডারের তথ্য Cloudflare D1-তে সংরক্ষিত থাকে। বাস্তব ক্রেতার পরিচয় ব্যবহার করবেন না।":"অর্ডার ও COD payment status D1-তে সংরক্ষিত থাকে। ডেলিভারি সম্পন্ন হওয়ার পর হাতে পাওয়া টাকা এখানে নিশ্চিত করুন।"}</p>
          {orders.length===0?<Empty>অর্ডার আসলে এখানে দেখা যাবে।</Empty>:<div className="dm-scroll"><table><thead><tr><th>অর্ডার ও ক্রেতা</th><th>তারিখ</th><th>মোট</th><th>অবস্থা</th><th>পেমেন্ট</th><th>করণীয়</th></tr></thead><tbody>{orders.map(o=><tr key={o.id}><td><strong>{o.order_number}</strong>{o.shipping_name&&<><br/><small>{o.shipping_name}</small></>}{o.shipping_phone&&<><br/><small>{o.shipping_phone}</small></>}{o.shipping_address&&<><br/><small>{o.shipping_address}</small></>}</td><td>{o.placed_at}</td><td>{fmt(o.total_bdt)}</td><td>{ORDER_STATUS_BN[o.status]||o.status}{o.status_note&&<><br/><small>{o.status_note}</small></>}{o.cancellation_reason&&o.status==="cancelled"&&<><br/><small>বাতিলের কারণ: {o.cancellation_reason}</small></>}</td><td>{PAYMENT_STATUS_BN[o.payment_status]||o.payment_status||"—"}{o.payment_received_at&&<><br/><small>{o.payment_received_at}</small></>}</td><td>{(ORDER_ACTIONS[o.status]||[]).map(action=><button key={action.status} className={action.danger?"dm-danger":"dm-secondary"} style={{marginRight:6,marginBottom:4}} disabled={busy} onClick={()=>run(()=>call("/api/merchant/orders/"+o.id+"/status",{method:"PATCH",token,body:{status:action.status}}),ORDER_ACTION_SUCCESS[action.status])}>{action.label}</button>)}{!store.is_demo&&o.payment_status==="pending_cod"&&["delivered","fulfilled"].includes(o.status)&&<button className="dm-secondary" style={{marginRight:6,marginBottom:4}} disabled={busy} onClick={()=>{if(!window.confirm("ক্রেতার কাছ থেকে COD টাকা সত্যিই গ্রহণ করেছেন?"))return;run(()=>call("/api/merchant/orders/"+o.id+"/payment",{method:"PATCH",token,body:{payment_note:"COD collected at delivery"}}),"COD payment received and recorded.");}}>COD টাকা গ্রহণ নিশ্চিত করুন</button>}{!(ORDER_ACTIONS[o.status]||[]).length&&(store.is_demo||o.payment_status!=="pending_cod"||!["delivered","fulfilled"].includes(o.status))?<span>—</span>:null}</td></tr>)}</tbody></table></div>}
        </div>}
        {view==="returns"&&<section className="dm-panel"><h2>ক্রেতার ফেরত অনুরোধ ({returnRequests.length})</h2><p className="dm-muted">{store.is_demo?"ফেরত পণ্য গ্রহণ করলে পরীক্ষামূলক মজুত একবার পুনরুদ্ধার হবে। এখানে কোনো অর্থ ফেরত দেওয়া হয় না।":"ফেরত পণ্য গ্রহণ করলে মজুত একবার পুনরুদ্ধার হবে। COD অর্থ ফেরত স্বয়ংক্রিয় নয়; আলাদাভাবে নিষ্পত্তি করতে হবে।"}</p>
          {returnRequests.length===0?<Empty>এখনো কোনো ফেরত অনুরোধ আসেনি।</Empty>:<div className="dm-scroll"><table><thead><tr><th>অর্ডার/ক্রেতা</th><th>কারণ</th><th>নোট</th><th>অবস্থা</th><th>করণীয়</th></tr></thead><tbody>{returnRequests.map(r=><tr key={r.id}><td>{r.order_number}<br/><small>{r.customer_name}</small></td><td>{({damaged:"ক্ষতিগ্রস্ত",wrong_item:"ভুল পণ্য",missing_item:"পণ্য অনুপস্থিত",not_as_described:"বর্ণনার সঙ্গে মিল নেই",other:"অন্যান্য"})[r.reason]||r.reason}</td><td>{r.customer_note||"—"}</td><td>{RETURN_STATUS_BN[r.status]||r.status}<br/><small>{r.merchant_note||""}</small></td><td>{r.status==="requested"?<><button className="dm-secondary" disabled={busy} onClick={()=>run(()=>call("/api/merchant/returns/"+r.id,{method:"PATCH",token,body:{status:"approved"}}),"ফেরত অনুরোধ অনুমোদন করা হয়েছে।")}>অনুমোদন</button> <button className="dm-danger" disabled={busy} onClick={()=>run(()=>call("/api/merchant/returns/"+r.id,{method:"PATCH",token,body:{status:"rejected",merchant_note:"অনুরোধটি অনুমোদন করা হয়নি"}}),"ফেরত অনুরোধ প্রত্যাখ্যান করা হয়েছে।")}>প্রত্যাখ্যান</button></>:r.status==="approved"?<button className="dm-secondary" disabled={busy} onClick={()=>run(()=>call("/api/merchant/returns/"+r.id,{method:"PATCH",token,body:{status:"received"}}),store.is_demo?"ফেরত পণ্য গ্রহণ হয়েছে; পরীক্ষামূলক মজুত পুনরুদ্ধার হয়েছে।":"ফেরত পণ্য গ্রহণ হয়েছে; মজুত পুনরুদ্ধার হয়েছে।")}>পণ্য গ্রহণ হয়েছে</button>:r.status==="received"?<button className="dm-secondary" disabled={busy} onClick={()=>run(()=>call("/api/merchant/returns/"+r.id,{method:"PATCH",token,body:{status:"closed_demo"}}),"ফেরত প্রক্রিয়া বন্ধ হয়েছে।")}>বন্ধ করুন</button>: "—"}</td></tr>)}</tbody></table></div>}</section>}
        {view==="chat"&&<section className="dm-panel"><h2>ক্রেতার বার্তা</h2><p className="dm-muted">এই দোকানের গ্রাহকের সঙ্গে বার্তা আদান-প্রদান করুন। বার্তাগুলো D1-তে সংরক্ষিত থাকে।</p>
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
        {view==="store"&&<section className="dm-panel"><h2>দোকানের সেটিংস</h2><p className="dm-muted">{store.is_demo?"এটি একটি পরীক্ষামূলক দোকান।":"স্টোরের প্রকাশনার অবস্থা: "+(store.is_active?"প্রকাশিত":"অনুমোদনের অপেক্ষায়")}</p>
        <form className="dm-fields" onSubmit={e=>{e.preventDefault();run(()=>call("/api/merchant/store",{method:"PATCH",token,body:storeForm}),"দোকানের তথ্য সংরক্ষিত হয়েছে।");}}>
          <Field label="নাম"><input style={input} required minLength={3} value={storeForm.name} onChange={e=>setStoreForm(v=>({...v,name:e.target.value}))}/></Field>
          <Field label="বিভাগ"><select style={input} value={storeForm.category} onChange={e=>setStoreForm(v=>({...v,category:e.target.value}))}>{categories.map(c=><option key={c}>{c}</option>)}</select></Field>
          <Field label="এলাকা"><input style={input} required value={storeForm.area} onChange={e=>setStoreForm(v=>({...v,area:e.target.value}))}/></Field>
          <Field label="বিবরণ"><input style={input} value={storeForm.tagline} onChange={e=>setStoreForm(v=>({...v,tagline:e.target.value}))}/></Field>
          {!store.is_active&&<p className="dm-muted">প্রকাশনার জন্য Platform Admin-এর অনুমোদন প্রয়োজন।</p>}
          <button className="dm-btn" disabled={busy} type="submit">সেটিংস সংরক্ষণ করুন</button>
        </form></section>}
        {edit&&<div className="dm-modal-bg" onClick={()=>setEdit(null)}><section role="dialog" aria-modal="true" aria-label={inventoryOnly?"মজুত সংশোধন":"পণ্য সম্পাদনা"} className="dm-panel dm-dialog" onClick={e=>e.stopPropagation()}><h2>{inventoryOnly?"মজুত সংশোধন":"পণ্য সম্পাদনা"}: {edit.name}</h2>
          <form className="dm-fields" onSubmit={e=>{e.preventDefault();run(async()=>{
            if(inventoryOnly){
              await call("/api/merchant/inventory/"+edit.id,{method:"PATCH",token,body:{stock_qty:Number(edit.stock_qty),reorder_level:Number(edit.reorder_level??5),reason:"Manual inventory correction"}});
            }else{
              await call("/api/merchant/products/"+edit.id,{method:"PATCH",token,body:{name:edit.name,category:edit.category,description:edit.description||"",brand:edit.brand||"",tags:Array.isArray(edit.tags)?edit.tags:(()=>{try{return JSON.parse(edit.tags||"[]")}catch{return []}})(),unit_label:edit.unit_label||"pcs",compare_at_price_bdt:edit.compare_at_price_bdt===""||edit.compare_at_price_bdt==null?null:Number(edit.compare_at_price_bdt),price_bdt:Number(edit.price_bdt),stock_qty:Number(edit.stock_qty),reorder_level:Number(edit.reorder_level??5),is_listed:edit.is_listed}});
            }
            setEdit(null);
          },inventoryOnly?"মজুত সংশোধন সংরক্ষিত হয়েছে।":"পণ্যের তথ্য সংশোধন করা হয়েছে।");}}>
          {(inventoryOnly?["stock_qty","reorder_level"]:["name","category","brand","unit_label","price_bdt","compare_at_price_bdt","stock_qty","reorder_level"]).map(k=><Field key={k} label={{name:"পণ্যের নাম",category:"বিভাগ",brand:"ব্র্যান্ড",unit_label:"একক",price_bdt:"বিক্রয়মূল্য",compare_at_price_bdt:"তুলনামূলক দাম",stock_qty:"মজুত",reorder_level:"কম স্টকের সতর্কতা"}[k]||k}><input style={input} type={["price_bdt","stock_qty","compare_at_price_bdt","reorder_level"].includes(k)?"number":"text"} min={["price_bdt","stock_qty","compare_at_price_bdt","reorder_level"].includes(k)?0:undefined} required={["name","price_bdt","stock_qty"].includes(k)} value={edit[k]??""} onChange={e=>setEdit(v=>({...v,[k]:e.target.value}))}/></Field>)}
          {!inventoryOnly&&<><Field label="পণ্যের বিবরণ"><textarea style={{...input,minHeight:90}} maxLength={3000} value={edit.description||""} onChange={e=>setEdit(v=>({...v,description:e.target.value}))}/></Field><Field label="ট্যাগ (কমা দিয়ে লিখুন)"><input style={input} value={Array.isArray(edit.tags)?edit.tags.join(", "):(()=>{try{return JSON.parse(edit.tags||"[]").join(", ")}catch{return ""}})()} onChange={e=>setEdit(v=>({...v,tags:e.target.value.split(",").map(x=>x.trim()).filter(Boolean)}))}/></Field><label className="dm-check"><input type="checkbox" checked={!!edit.is_listed} onChange={e=>setEdit(v=>({...v,is_listed:e.target.checked}))}/>প্রকাশিত</label></>}
          <div className="dm-actions"><button className="dm-btn" disabled={busy} type="submit">{inventoryOnly?"মজুত সংরক্ষণ করুন":"পরিবর্তন সংরক্ষণ করুন"}</button><button type="button" onClick={()=>setEdit(null)} className="dm-secondary">বন্ধ করুন</button></div></form></section></div>}
      </>}
    </div>
    {token&&store&&<nav className="dm-bottom" aria-label="Store mobile navigation">{[
      ["dashboard","হোম","⌂"],
      ...(!data?.account?.is_staff||["manager","sales","inventory","analyst"].includes(data.account?.staff_role)?[["products","পণ্য","▣"]]:[]),
      ...(!data?.account?.is_staff||["manager","sales"].includes(data.account?.staff_role)?[["pos","বিক্রি","⊞"]]:[]),
      ...(!data?.account?.is_staff||["manager","sales","support","analyst"].includes(data.account?.staff_role)?[["orders","অর্ডার","≡"]]:[]),
      ...(!data?.account?.is_staff||["manager","support"].includes(data.account?.staff_role)?[["returns","ফেরত","↩"]]:[]),
      ...(!data?.account?.is_staff?[["staff","কর্মী","♙"]]:[]),
      ...(!data?.account?.is_staff||data.account?.staff_role==="manager"?[["store","সেটিংস","⚙"]]:[])
    ].map(([k,t,icon])=><button key={k} className={view===k?"selected":""} onClick={()=>{setView(k);window.scrollTo({top:0,behavior:"smooth"});}}><span>{icon}</span>{t}</button>)}</nav>}
  </main>;
}
