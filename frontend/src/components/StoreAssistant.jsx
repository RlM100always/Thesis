import { useEffect, useRef, useState } from "react";
import { d1Commerce } from "../api";
import { getCustomerToken } from "../storeCustomerApi";
import "./StoreAssistant.css";

const quickQuestions = ["কম দামের পণ্য দেখান", "ডেলিভারি কীভাবে হবে?", "আমার অর্ডারের অবস্থা"];

export default function StoreAssistant({ store, onOpenAccount, onSelectProduct }) {
  const [open,setOpen]=useState(false);
  const [question,setQuestion]=useState("");
  const [messages,setMessages]=useState([{role:"assistant",content:"স্বাগতম! এই দোকানের পণ্য, দাম, স্টক, ডেলিভারি ও অর্ডার সম্পর্কে আমাকে জিজ্ঞেস করতে পারেন।"}]);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const endRef=useRef(null);

  useEffect(()=>{endRef.current?.scrollIntoView({behavior:"smooth",block:"end"});},[messages,open]);

  async function send(value){
    const text=String(value||"").trim();
    if(!text||busy)return;
    const previous=messages.slice(-6).map(m=>({role:m.role,content:m.content}));
    setMessages(current=>[...current,{role:"user",content:text}]);
    setQuestion("");
    setError("");
    setBusy(true);
    try{
      const token=getCustomerToken(store.slug);
      const result=await d1Commerce("/api/public/assistant/"+encodeURIComponent(store.slug),{
        method:"POST",
        headers:token?{Authorization:"Bearer "+token}:{},
        body:{question:text,history:previous},
      });
      setMessages(current=>[...current,{role:"assistant",content:result.text||"দুঃখিত, এখন উত্তর পাওয়া যায়নি।",products:result.products||[],orders:result.orders||[],ai_enabled:!!result.ai_enabled}]);
    }catch(e){
      setError(e.message||"সহকারী এখন উত্তর দিতে পারছে না।");
    }finally{setBusy(false);}
  }

  return <div className="store-assistant-root">
    {open&&<section className="store-assistant-panel" aria-label={store.display_name+" shopping assistant"}>
      <header className="store-assistant-head">
        <div className="store-assistant-avatar">✦</div>
        <div><strong>{store.display_name} সহকারী</strong><small>পণ্য ও অর্ডারের তথ্যভিত্তিক সাহায্য</small></div>
        <button type="button" aria-label="সহকারী বন্ধ করুন" onClick={()=>setOpen(false)}>×</button>
      </header>
      <div className="store-assistant-messages" aria-live="polite">
        {messages.map((m,i)=><div key={i} className={"store-assistant-message "+(m.role==="user"?"user":"assistant")}>
          <p>{m.content}</p>
          {m.products?.length>0&&<div className="store-assistant-products">{m.products.map(p=><button key={p.id} type="button" onClick={()=>onSelectProduct?.(p.id)}>
            <strong>{p.name}</strong><span>{p.price_bdt==null?"দাম জানতে যোগাযোগ করুন":"৳"+Number(p.price_bdt).toLocaleString("en-BD")}</span><small>{Number(p.stock_qty)>0?"স্টকে আছে":"স্টক নেই"}</small>
          </button>)}</div>}
          {m.orders?.length>0&&<div className="store-assistant-orders">{m.orders.map(o=><div key={o.order_number}><strong>{o.order_number}</strong><span>{o.status}</span></div>)}</div>}
          {m.role==="assistant"&&i>0&&<small className="store-assistant-source">{m.ai_enabled?"AI সহকারী":"দোকানের যাচাইকৃত তথ্য"}</small>}
        </div>)}
        {busy&&<div className="store-assistant-typing">উত্তর তৈরি হচ্ছে…</div>}
        {error&&<div className="store-assistant-error" role="alert">{error}</div>}
        <div ref={endRef}/>
      </div>
      {messages.length<=1&&<div className="store-assistant-quick">{quickQuestions.map(q=><button key={q} type="button" onClick={()=>send(q)}>{q}</button>)}</div>}
      <form className="store-assistant-form" onSubmit={e=>{e.preventDefault();send(question);}}>
        <input value={question} maxLength={500} onChange={e=>setQuestion(e.target.value)} placeholder="আপনার প্রশ্ন লিখুন…" aria-label="আপনার প্রশ্ন" />
        <button type="submit" disabled={busy||!question.trim()} aria-label="প্রশ্ন পাঠান">➤</button>
      </form>
      <button className="store-assistant-account" type="button" onClick={onOpenAccount}>অর্ডার ট্র্যাক করতে Customer Account খুলুন</button>
    </section>}
    <button className={"store-assistant-launch "+(open?"active":"")} type="button" onClick={()=>setOpen(v=>!v)} aria-expanded={open} aria-label={open?"সহকারী বন্ধ করুন":"দোকানের সহকারীর সঙ্গে কথা বলুন"}>
      <span>{open?"×":"✦"}</span>{open?"বন্ধ করুন":"কীভাবে সাহায্য করতে পারি?"}
    </button>
  </div>;
}
