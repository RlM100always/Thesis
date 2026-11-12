import { useCallback, useEffect, useState } from "react";

const ROLES=[
 {id:"manager",label:"Manager",description:"পণ্য, অর্ডার, কুপন, মজুত, সাপোর্ট ও বিশ্লেষণ"},
 {id:"sales",label:"Sales / Cashier",description:"বিক্রি, অর্ডার ও পণ্য দেখা"},
 {id:"inventory",label:"Inventory",description:"পণ্য ও মজুত যোগ/সংশোধন"},
 {id:"support",label:"Customer Support",description:"ক্রেতার অর্ডার, রিটার্ন ও বার্তা"},
 {id:"analyst",label:"Analyst",description:"বিক্রয় ও মজুত বিশ্লেষণ; পরিবর্তনের অনুমতি নেই"},
];
const ROLE_NAME=Object.fromEntries(ROLES.map(x=>[x.id,x.label]));
const input={minHeight:42,padding:"10px 12px",border:"1px solid var(--dm-line)",background:"var(--dm-surface)",borderRadius:10,color:"var(--dm-text)",font:"inherit",width:"100%"};
export default function D1StaffManagement({token,call}){
 const [data,setData]=useState({staff:[],invites:[]});
 const [form,setForm]=useState({email:"",display_name:"",role:"sales"});
 const [inviteUrl,setInviteUrl]=useState("");
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState("");
 const [notice,setNotice]=useState("");
 const refresh=useCallback(async()=>{
  const result=await call("/api/merchant/staff",{token});
  setData({staff:result.staff||[],invites:result.invites||[]});
 },[token,call]);
 useEffect(()=>{refresh().catch(e=>setError(e.message));},[refresh]);
 async function createInvite(e){
  e.preventDefault();setBusy(true);setError("");setNotice("");setInviteUrl("");
  try{
   const result=await call("/api/merchant/staff",{method:"POST",token,body:form});
   setInviteUrl(result.invite_url||"");setNotice("কর্মীর জন্য একবার ব্যবহারযোগ্য প্রবেশ লিংক তৈরি হয়েছে।");
   setForm({email:"",display_name:"",role:"sales"});await refresh();
  }catch(e){setError(e.message||"কর্মীর আমন্ত্রণ তৈরি করা যায়নি।");}
  finally{setBusy(false);}
 }
 async function update(member,patch){
  setBusy(true);setError("");setNotice("");
  try{
   await call("/api/merchant/staff/"+encodeURIComponent(member.id),{method:"PATCH",token,body:patch});
   await refresh();setNotice("কর্মীর অনুমতি আপডেট হয়েছে।");
  }catch(e){setError(e.message||"অনুমতি পরিবর্তন করা যায়নি।");}
  finally{setBusy(false);}
 }
 async function revoke(invite){
  if(!window.confirm(invite.email+" — এই আমন্ত্রণ বাতিল করবেন?"))return;
  setBusy(true);setError("");setNotice("");
  try{
   await call("/api/merchant/staff-invites/"+encodeURIComponent(invite.id),{method:"PATCH",token,body:{revoke:true}});
   await refresh();setNotice("আমন্ত্রণ বাতিল হয়েছে।");
  }catch(e){setError(e.message||"আমন্ত্রণ বাতিল করা যায়নি।");}
  finally{setBusy(false);}
 }
 async function copyLink(){
  try{await navigator.clipboard.writeText(inviteUrl);setNotice("প্রবেশ লিংক কপি হয়েছে।");}
  catch{setError("কপি করা যায়নি। লিংকটি নির্বাচন করে কপি করুন।");}
 }
 return <div className="dm-stack">
  <section className="dm-panel"><h2>কর্মী ও ভূমিকা</h2><p className="dm-muted">প্রতিটি কর্মীর নিজস্ব ইমেইল ও পাসওয়ার্ড থাকবে। ভূমিকা অনুযায়ী API-তে অনুমতি যাচাই হয়; শুধু মেনু লুকিয়ে রাখা নয়।</p>
   <form className="dm-fields" onSubmit={createInvite}>
    <label className="dm-field"><strong>কর্মীর নাম</strong><input style={input} minLength={2} maxLength={120} required value={form.display_name} onChange={e=>setForm(v=>({...v,display_name:e.target.value}))}/></label>
    <label className="dm-field"><strong>কর্মীর ইমেইল</strong><input style={input} type="email" required value={form.email} onChange={e=>setForm(v=>({...v,email:e.target.value}))}/></label>
    <label className="dm-field"><strong>ভূমিকা</strong><select style={input} value={form.role} onChange={e=>setForm(v=>({...v,role:e.target.value}))}>{ROLES.map(role=><option key={role.id} value={role.id}>{role.label}</option>)}</select></label>
    <p className="dm-muted">{ROLES.find(x=>x.id===form.role)?.description}</p>
    <button className="dm-btn" type="submit" disabled={busy}>একবার ব্যবহারযোগ্য আমন্ত্রণ তৈরি করুন</button>
   </form>
   {inviteUrl&&<div style={{marginTop:14,padding:12,border:"1px solid var(--dm-line)",borderRadius:10}}>
    <strong>নতুন কর্মীর প্রবেশ লিংক</strong>
    <p className="dm-muted">লিংকটি ৭২ ঘণ্টা বৈধ এবং একবারই ব্যবহার করা যাবে। কর্মীর কাছে নিরাপদ মাধ্যমে পাঠান। লিংকটি শুধু এই মুহূর্তে দেখানো হচ্ছে।</p>
    <div style={{display:"flex",gap:8,flexWrap:"wrap"}}><input style={{...input,flex:"1 1 280px"}} readOnly value={inviteUrl}/><button type="button" className="dm-secondary" onClick={copyLink}>লিংক কপি করুন</button></div>
   </div>}
  </section>
  <section className="dm-panel"><h2>সক্রিয় ও স্থগিত কর্মী ({data.staff.length})</h2>
   {!data.staff.length?<p className="dm-muted">এখনো কোনো কর্মী যুক্ত হয়নি।</p>:<div className="dm-scroll"><table><thead><tr><th>কর্মী</th><th>ভূমিকা</th><th>সর্বশেষ লগইন</th><th>অ্যাক্সেস</th></tr></thead><tbody>
    {data.staff.map(member=><tr key={member.id}>
     <td><strong>{member.display_name||"—"}</strong><div className="dm-muted">{member.email}</div></td>
     <td><select style={{...input,minWidth:145}} value={member.role} disabled={busy||!member.is_active} onChange={e=>update(member,{role:e.target.value})}>{ROLES.map(role=><option key={role.id} value={role.id}>{role.label}</option>)}</select></td>
     <td>{member.last_login_at||"এখনো লগইন করেনি"}</td>
     <td><button type="button" className={member.is_active&&member.account_active?"dm-danger":"dm-secondary"} disabled={busy} onClick={()=>update(member,{is_active:!(member.is_active&&member.account_active)})}>{member.is_active&&member.account_active?"স্থগিত করুন":"আবার চালু করুন"}</button></td>
    </tr>)}
   </tbody></table></div>}
  </section>
  <section className="dm-panel"><h2>অপেক্ষমাণ আমন্ত্রণ ({data.invites.length})</h2>
   {!data.invites.length?<p className="dm-muted">কোনো অপেক্ষমাণ আমন্ত্রণ নেই।</p>:<div className="dm-scroll"><table><thead><tr><th>ইমেইল</th><th>নাম</th><th>ভূমিকা</th><th>মেয়াদ শেষ</th><th>কাজ</th></tr></thead><tbody>
    {data.invites.map(invite=><tr key={invite.id}><td>{invite.email}</td><td>{invite.display_name}</td><td>{ROLE_NAME[invite.role]||invite.role}</td><td>{invite.expires_at}</td><td><button type="button" className="dm-danger" disabled={busy} onClick={()=>revoke(invite)}>বাতিল</button></td></tr>)}
   </tbody></table></div>}
  </section>
  {error&&<p className="dm-error" role="alert">{error}</p>}
  {notice&&<p className="dm-success" role="status">{notice}</p>}
 </div>;
}
