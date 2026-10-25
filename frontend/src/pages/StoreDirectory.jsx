/** B-SMART public marketplace: active, real operational stores only.
 * No simulated research shops are inserted here.
 */
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";

const styles = `
.store-market { background:var(--bg,#f5f7fb); min-height:100vh; color:var(--text,#17212d); padding-bottom:calc(92px + env(safe-area-inset-bottom)); }
.store-market * { box-sizing:border-box }
.store-market header { padding:18px 18px 14px; background:var(--surface,#fff); border-bottom:1px solid #dce4e8; position:sticky;top:0;z-index:20; }
.store-market-head { max-width:1160px;margin:auto;display:flex;gap:14px;align-items:center;justify-content:space-between }
.store-market header h1 { font-size:clamp(21px,3vw,29px);margin:0 }
.store-market small { font-size:12px;color:#637582 }
.store-market a { text-decoration:none;color:inherit }
.store-market .hero { background:linear-gradient(125deg,#075f49,#0a9871);color:#fff;padding:30px 18px 34px; }
.store-market .hero-inner {max-width:1160px;margin:auto;}
.store-market .hero h2 {font-size:clamp(23px,4vw,40px);margin:5px 0 8px}
.store-market .hero p {opacity:.87;margin:0 0 18px}
.store-market .filter {display:flex;align-items:center;flex-wrap:wrap;gap:10px}
.store-market input,.store-market select {padding:12px 14px;border:1px solid #d1dade;border-radius:12px;min-height:46px;background:#fff;color:#253543;font:inherit}
.store-market input {width:min(100%,430px);flex:1}
.store-market main {max-width:1160px;margin:22px auto;padding:0 15px}
.store-market .cards {display:grid;grid-template-columns:repeat(auto-fill,minmax(235px,1fr));gap:15px}
.store-market .store-card {display:block;border:1px solid #d9e2e4;border-radius:17px;background:#fff;overflow:hidden;box-shadow:0 4px 17px #123e3710;transition:transform .2s,box-shadow .2s}
.store-market .store-card:hover {transform:translateY(-3px);box-shadow:0 8px 24px #123e3720}
.store-market .cover {height:126px;background:linear-gradient(125deg,#188363,#0c4c42);background-position:center;background-size:cover;display:flex;align-items:flex-end;padding:10px}
.store-market .store-logo {height:52px;width:52px;border:3px solid #fff;object-fit:cover;border-radius:13px;background:#fff;display:grid;place-items:center;font-size:27px}
.store-market .info {padding:15px}
.store-market .info h3 {margin:0 0 4px;font-size:17px;line-height:1.4}
.store-market .info p {font-size:13px;line-height:1.5;color:#506477;min-height:36px;margin:0 0 12px}
.store-market .meta {display:flex;gap:8px;flex-wrap:wrap;font-size:11px;color:#3b6c62}
.store-market .meta span {padding:5px 8px;border-radius:20px;background:#eaf4f0}
.store-market .visit {margin-top:14px;color:#087354;font-weight:700;font-size:13px}
.store-market .empty {background:#fff;border:1px solid #e1e8ec;padding:24px;border-radius:16px}
.store-market .bottom {display:none}
@media(max-width:720px){
 .store-market header {padding:12px 14px}
 .store-market header h1 {font-size:18px}
 .store-market .hero {padding:26px 14px}
 .store-market .cards {grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
 .store-market .cover {height:100px}
 .store-market .store-logo {height:42px;width:42px}
 .store-market .info {padding:11px}
 .store-market .info h3 {font-size:14px}
 .store-market .info p {min-height:34px;font-size:12px}
 .store-market .bottom {display:grid;grid-template-columns:repeat(3,1fr);background:#fff;position:fixed;bottom:0;left:0;right:0;z-index:99;border-top:1px solid #dce7e8;padding:7px 6px calc(8px + env(safe-area-inset-bottom));box-shadow:0 -4px 18px #103f3213}
 .store-market .bottom a {display:flex;flex-direction:column;align-items:center;gap:3px;font-size:11px;color:#4e6b65;text-align:center;font-weight:650}
 .store-market .bottom a[aria-current="page"] {color:#0a8063}
 .store-market .bottom b {font-size:22px;font-weight:400}
}
@media(max-width:360px){.store-market .cards {grid-template-columns:1fr}}
`;
const gradient = {pharmacy:"linear-gradient(120deg,#08795c,#25a684)",grocery:"linear-gradient(120deg,#3a905a,#77c181)",fashion:"linear-gradient(120deg,#8b4682,#d67ea6)",electronics:"linear-gradient(120deg,#205186,#6f9cce)"};
const fallbackCover = (category="") => {
  const c = category.toLowerCase();
  return Object.entries(gradient).find(([k])=>c.includes(k))?.[1] || "linear-gradient(120deg,#08795c,#48b1a1)";
};
export default function StoreDirectory() {
  const [rows,setRows]=useState([]),[busy,setBusy]=useState(true),[error,setError]=useState("");
  const [query,setQuery]=useState(""),[category,setCategory]=useState("all");
  useEffect(()=>{
    let live=true;
    api.getPublicStores().then(d=>{if(live)setRows(Array.isArray(d)?d:d.stores||[])})
      .catch(e=>{if(live)setError(e.message||"Could not load stores")})
      .finally(()=>{if(live)setBusy(false)});
    return ()=>{live=false};
  },[]);
  const categories=useMemo(()=>[...new Set(rows.map(s=>s.category).filter(Boolean))].sort(),[rows]);
  const result=useMemo(()=>{
    const q=query.trim().toLowerCase();
    return rows.filter(s=>(category==="all"||s.category===category)
      && (!q||[s.display_name,s.category,s.area,s.tagline].join(" ").toLowerCase().includes(q)));
  },[rows,query,category]);
  return <div className="store-market">
    <style>{styles}</style>
    <header><div className="store-market-head">
      <Link to="/" aria-label="B-SMART home"><h1>🛍️ B-SMART Stores</h1><small>বাংলাদেশের অনলাইন স্টোর</small></Link>
      <Link to="/" style={{fontSize:13,color:"#09785c",fontWeight:700}}>← মূল ওয়েবসাইট</Link>
    </div></header>
    <section className="hero"><div className="hero-inner">
      <div style={{fontSize:12,opacity:.9}}>B-SMART MARKETPLACE</div>
      <h2>সব দোকান, এক জায়গায়</h2><p>দোকান বাছুন, পণ্য দেখুন এবং সরাসরি অর্ডার করুন</p>
      <div className="filter">
        <input aria-label="দোকান খুঁজুন" placeholder="দোকানের নাম, এলাকা, পণ্যের ধরন" value={query} onChange={e=>setQuery(e.target.value)}/>
        <select aria-label="দোকানের ক্যাটাগরি" value={category} onChange={e=>setCategory(e.target.value)}>
          <option value="all">সব ক্যাটাগরি</option>{categories.map(c=><option key={c} value={c}>{c}</option>)}
        </select>
      </div>
    </div></section>
    <main>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:15,gap:8}}>
        <h2 style={{margin:0,fontSize:20}}>অনলাইন স্টোর</h2><small>{busy?"লোড হচ্ছে...":`${result.length} টি দোকান`}</small>
      </div>
      {busy?<div className="empty" role="status">দোকানগুলো লোড হচ্ছে...</div>
       :error?<div className="empty" role="alert">দোকান লোড করা যায়নি: {error}</div>
       :result.length===0?<div className="empty">এখন কোনো active দোকান পাওয়া যায়নি। দোকানের মালিক Store Management থেকে স্টোর চালু করলে এখানে আসবে। এটি simulated research shops-এর তালিকা নয়।</div>
       :<div className="cards">{result.map(s=><Link to={`/store/${encodeURIComponent(s.organization_id)}`} className="store-card" key={s.organization_id}>
          <div className="cover" style={{backgroundImage:s.cover_data_url?`url("${s.cover_data_url}")`:fallbackCover(s.category)}}>
            {s.logo_data_url?<img className="store-logo" src={s.logo_data_url} alt="" loading="lazy"/>:<div className="store-logo">🏪</div>}
          </div>
          <div className="info">
            <h3>{s.display_name||"Online Shop"}</h3>
            <p>{s.tagline||s.area||s.category||"B-SMART online store"}</p>
            <div className="meta">{s.category&&<span>{s.category}</span>}{s.area&&<span>📍 {s.area}</span>}{s.payment_cod&&<span>Cash on delivery</span>}</div>
            <div className="visit">পণ্য ও অর্ডার দেখুন →</div>
          </div>
        </Link>)}</div>}
    </main>
    <nav className="bottom" aria-label="Mobile store navigation">
      <Link to="/" ><b>⌂</b>হোম</Link>
      <Link to="/stores" aria-current="page"><b>▦</b>স্টোরসমূহ</Link>
      <Link to="/login"><b>♙</b>আমার অ্যাকাউন্ট</Link>
    </nav>
  </div>;
}
