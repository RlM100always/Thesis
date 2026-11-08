import { useCallback, useEffect, useState } from "react";

const BASE=(import.meta.env.VITE_D1_COMMERCE_URL || "https://bsmart-commerce-api.bcs-written-rakib.workers.dev").replace(/\/$/,"");
const input={width:"100%",boxSizing:"border-box",padding:"10px 12px",borderRadius:9,border:"1px solid var(--border,#dfe7e2)",background:"var(--bg,#fff)",color:"var(--text,#14251d)",font:"inherit"};
const statusLabel={published:"Published",awaiting_approval:"Awaiting approval",legacy_test_record:"Internal test record"};
const roleLabel={manager:"Manager",sales:"Sales / Cashier",inventory:"Inventory",support:"Customer Support",analyst:"Analyst"};
async function call(path,key,{method="GET",body}={}){
 const response=await fetch(BASE+path,{method,headers:{"Content-Type":"application/json",Authorization:"Bearer "+key},...(body!==undefined?{body:JSON.stringify(body)}:{})});
 const data=await response.json().catch(()=>({}));
 if(!response.ok)throw new Error(data.detail||"Request could not be completed.");
 return data;
}
const csvCell=value=>'"'+String(value??"").replace(/"/g,'""')+'"';
export default function D1PlatformAccess({secret}){
 const [subtab,setSubtab]=useState("invites");
 const [invites,setInvites]=useState([]);
 const [register,setRegister]=useState(null);
 const [form,setForm]=useState({email:"",owner_name:"",store_name:"",category:"মুদি",area:"",tagline:""});
 const [identityConfirmed,setIdentityConfirmed]=useState(false);
 const [inviteUrl,setInviteUrl]=useState("");
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState("");
 const [notice,setNotice]=useState("");
 const refresh=useCallback(async()=>{
  const [a,b]=await Promise.all([call("/api/platform-admin/owner-invites",secret),call("/api/platform-admin/access-register",secret)]);
  setInvites(a.invites||[]);setRegister(b);
 },[secret]);
 useEffect(()=>{refresh().catch(e=>setError(e.message));},[refresh]);
 async function createInvite(e){
  e.preventDefault();setBusy(true);setError("");setNotice("");setInviteUrl("");
  try{
   const result=await call("/api/platform-admin/owner-invites",secret,{method:"POST",body:{...form,identity_confirmed:identityConfirmed}});
   setInviteUrl(result.invite_url||"");setNotice("Owner invitation created. Share the one-time link securely.");
   setForm({email:"",owner_name:"",store_name:"",category:"মুদি",area:"",tagline:""});setIdentityConfirmed(false);
   await refresh();
  }catch(e){setError(e.message);}
  finally{setBusy(false);}
 }
 async function revoke(invite){
  if(!window.confirm("Revoke the pending invitation for "+invite.email+"?"))return;
  setBusy(true);setError("");setNotice("");
  try{await call("/api/platform-admin/owner-invites/"+encodeURIComponent(invite.id),secret,{method:"PATCH",body:{revoke:true}});await refresh();setNotice("Invitation revoked.");}
  catch(e){setError(e.message);}
  finally{setBusy(false);}
 }
 async function copy(value){
  try{await navigator.clipboard.writeText(value);setNotice("Copied to clipboard.");}
  catch{setError("Could not copy. Select the link and copy it manually.");}
 }
 function downloadRegister(){
  const rows=[["Store","Slug","Store status","Owner name","Owner email","Owner active","Owner email verified","Staff name","Staff email","Staff role","Staff active","Public URL"]];
  for(const store of (register?.stores||[])){
   if(!store.staff.length)rows.push([store.store_name,store.slug,statusLabel[store.store_status]||store.store_status,store.owner.name,store.owner.email,store.owner.is_active,store.owner.email_verified,"","","","",store.store_status==="published"?store.public_store_url:""]);
   else for(const staff of store.staff)rows.push([store.store_name,store.slug,statusLabel[store.store_status]||store.store_status,store.owner.name,store.owner.email,store.owner.is_active,store.owner.email_verified,staff.display_name,staff.email,roleLabel[staff.role]||staff.role,!!staff.is_active&&!!staff.account_active,store.store_status==="published"?store.public_store_url:""]);
  }
  const csv="\uFEFF"+rows.map(row=>row.map(csvCell).join(",")).join("\r\n");
  const url=URL.createObjectURL(new Blob([csv],{type:"text/csv;charset=utf-8"}));
  const a=document.createElement("a");a.href=url;a.download="bsmart-store-access-register.csv";a.click();URL.revokeObjectURL(url);
 }
 return <section style={{display:"grid",gap:14}}>
  <div style={{display:"flex",gap:7,flexWrap:"wrap"}}>
   <button type="button" style={{padding:"9px 13px",borderRadius:9,border:"1px solid var(--border,#dfe7e2)",background:subtab==="invites"?"#087e59":"var(--surface,#fff)",color:subtab==="invites"?"#fff":"var(--text,#14251d)",fontWeight:750}} onClick={()=>setSubtab("invites")}>Owner onboarding</button>
   <button type="button" style={{padding:"9px 13px",borderRadius:9,border:"1px solid var(--border,#dfe7e2)",background:subtab==="register"?"#087e59":"var(--surface,#fff)",color:subtab==="register"?"#fff":"var(--text,#14251d)",fontWeight:750}} onClick={()=>setSubtab("register")}>Store access register</button>
  </div>
  {subtab==="invites"&&<>
   <section style={{background:"var(--surface,#fff)",border:"1px solid var(--border,#dfe7e2)",borderRadius:14,padding:16}}>
    <h2 style={{marginTop:0,fontSize:18}}>Create a verified store-owner login</h2>
    <p style={{fontSize:12,lineHeight:1.7,color:"var(--text-muted,#65736b)"}}>This creates a one-time owner setup link. Confirm the real business owner and contact email outside this system first. The link expires in 72 hours, creates a private store draft, and never exposes a password.</p>
    <form onSubmit={createInvite} style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(220px,1fr))",gap:10}}>
     <label style={{fontSize:12,fontWeight:700}}>Owner email<input style={{...input,marginTop:5}} type="email" required value={form.email} onChange={e=>setForm(v=>({...v,email:e.target.value}))}/></label>
     <label style={{fontSize:12,fontWeight:700}}>Owner name<input style={{...input,marginTop:5}} required minLength={2} value={form.owner_name} onChange={e=>setForm(v=>({...v,owner_name:e.target.value}))}/></label>
     <label style={{fontSize:12,fontWeight:700}}>Store name<input style={{...input,marginTop:5}} required minLength={3} value={form.store_name} onChange={e=>setForm(v=>({...v,store_name:e.target.value}))}/></label>
     <label style={{fontSize:12,fontWeight:700}}>Category<select style={{...input,marginTop:5}} value={form.category} onChange={e=>setForm(v=>({...v,category:e.target.value}))}>{["মুদি","পোশাক","ইলেকট্রনিক্স","রেস্টুরেন্ট","স্টেশনারি","বিউটি","মোবাইল","ফার্নিচার","হার্ডওয়্যার","অন্যান্য"].map(x=><option key={x}>{x}</option>)}</select></label>
     <label style={{fontSize:12,fontWeight:700}}>Area / district<input style={{...input,marginTop:5}} required value={form.area} onChange={e=>setForm(v=>({...v,area:e.target.value}))}/></label>
     <label style={{fontSize:12,fontWeight:700}}>Short description<input style={{...input,marginTop:5}} maxLength={160} value={form.tagline} onChange={e=>setForm(v=>({...v,tagline:e.target.value}))}/></label>
     <label style={{gridColumn:"1/-1",display:"flex",alignItems:"flex-start",gap:9,fontSize:12,lineHeight:1.6}}><input type="checkbox" checked={identityConfirmed} onChange={e=>setIdentityConfirmed(e.target.checked)}/><span>I have independently verified this real business owner and the email address that will receive the private setup link.</span></label>
     <button style={{padding:"11px 14px",border:0,borderRadius:9,background:"#087e59",color:"#fff",fontWeight:800}} type="submit" disabled={busy||!identityConfirmed}>Create one-time owner invitation</button>
    </form>
    {inviteUrl&&<div style={{marginTop:14,padding:12,border:"1px solid var(--border,#dfe7e2)",borderRadius:10}}>
     <strong>One-time owner setup link</strong><p style={{fontSize:12,color:"var(--text-muted,#65736b)"}}>Copy and send securely to the verified owner. It is shown only once; if lost, revoke and issue a new invitation.</p>
     <div style={{display:"flex",gap:8,flexWrap:"wrap"}}><input style={{...input,flex:"1 1 300px"}} readOnly value={inviteUrl}/><button type="button" style={{padding:"9px 13px",borderRadius:9,border:"1px solid var(--border,#dfe7e2)"}} onClick={()=>copy(inviteUrl)}>Copy link</button></div>
    </div>}
   </section>
   <section style={{background:"var(--surface,#fff)",border:"1px solid var(--border,#dfe7e2)",borderRadius:14,padding:16}}>
    <h2 style={{marginTop:0,fontSize:18}}>Owner invitations ({invites.length})</h2>
    <div style={{overflowX:"auto"}}>{!invites.length?<p style={{color:"var(--text-muted,#65736b)"}}>No owner invitations have been issued.</p>:<table style={{width:"100%",borderCollapse:"collapse",fontSize:12,minWidth:680}}><thead><tr>{["Owner / email","Store","Created","Expires","Status","Action"].map(x=><th key={x} style={{textAlign:"left",padding:9,borderBottom:"1px solid var(--border,#dfe7e2)"}}>{x}</th>)}</tr></thead><tbody>{invites.map(i=><tr key={i.id}><td style={{padding:9,borderBottom:"1px solid var(--border,#dfe7e2)"}}><strong>{i.owner_name}</strong><div>{i.email}</div></td><td style={{padding:9,borderBottom:"1px solid var(--border,#dfe7e2)"}}>{i.store_name}<div>{i.area}</div></td><td style={{padding:9,borderBottom:"1px solid var(--border,#dfe7e2)"}}>{i.created_at}</td><td style={{padding:9,borderBottom:"1px solid var(--border,#dfe7e2)"}}>{i.expires_at}</td><td style={{padding:9,borderBottom:"1px solid var(--border,#dfe7e2)"}}>{i.accepted_at?"Accepted":i.revoked_at?"Revoked":new Date(i.expires_at)<new Date()?"Expired":"Pending"}</td><td style={{padding:9,borderBottom:"1px solid var(--border,#dfe7e2)"}}>{!i.accepted_at&&!i.revoked_at&&new Date(i.expires_at)>new Date()&&<button type="button" style={{padding:"6px 9px",borderRadius:8,border:"1px solid var(--border,#dfe7e2)"}} disabled={busy} onClick={()=>revoke(i)}>Revoke</button>}</td></tr>)}</tbody></table>}</div>
   </section>
  </>}
  {subtab==="register"&&<section style={{background:"var(--surface,#fff)",border:"1px solid var(--border,#dfe7e2)",borderRadius:14,padding:16}}>
   <div style={{display:"flex",justifyContent:"space-between",gap:10,flexWrap:"wrap",alignItems:"center"}}>
    <div><h2 style={{margin:"0 0 5px",fontSize:18}}>Individual store access register</h2><p style={{margin:0,fontSize:12,color:"var(--text-muted,#65736b)"}}>Generated from Cloudflare Primary D1. Passwords and session tokens are never included.</p></div>
    <button type="button" style={{padding:"9px 13px",borderRadius:9,border:"1px solid var(--border,#dfe7e2)"}} disabled={!register?.stores?.length} onClick={downloadRegister}>Download CSV</button>
   </div>
   {register&&<p style={{fontSize:12,margin:"12px 0"}}>Owner login: <a href={register.owner_login_url}>{register.owner_login_url}</a> · Stores registered: <strong>{register.stores.length}</strong></p>}
   {!register?.stores?.length?<p style={{color:"var(--text-muted,#65736b)"}}>No individual operational store logins are registered yet. Create verified owner invitations above; accepted owners will appear here automatically.</p>:<div style={{overflowX:"auto"}}><table style={{width:"100%",borderCollapse:"collapse",fontSize:12,minWidth:780}}><thead><tr>{["Store / public link","Owner login","Store status","Staff access"].map(x=><th key={x} style={{textAlign:"left",padding:9,borderBottom:"1px solid var(--border,#dfe7e2)"}}>{x}</th>)}</tr></thead><tbody>{register.stores.map(s=><tr key={s.store_id}><td style={{padding:9,borderBottom:"1px solid var(--border,#dfe7e2)"}}><strong>{s.store_name}</strong><div>{s.slug}</div>{s.store_status==="published"&&<a href={s.public_store_url}>Open store</a>}</td><td style={{padding:9,borderBottom:"1px solid var(--border,#dfe7e2)"}}>{s.owner.name||"—"}<div>{s.owner.email||"No owner account"}</div><div>{s.owner.is_active?"Active":"Inactive"} · {s.owner.email_verified?"Verified":"Unverified"}</div></td><td style={{padding:9,borderBottom:"1px solid var(--border,#dfe7e2)"}}>{statusLabel[s.store_status]||s.store_status}</td><td style={{padding:9,borderBottom:"1px solid var(--border,#dfe7e2)"}}>{s.staff.length?s.staff.map(m=><div key={m.id}>{m.display_name||m.email} · {roleLabel[m.role]||m.role} · {m.is_active&&m.account_active?"Active":"Suspended"}</div>):"No staff"}</td></tr>)}</tbody></table></div>}
  </section>}
  {error&&<div role="alert" style={{padding:12,borderRadius:10,color:"#b91c1c",border:"1px solid #fecaca"}}>{error}</div>}
  {notice&&<div role="status" style={{padding:12,borderRadius:10,color:"#15803d"}}>{notice}</div>}
 </section>;
}
