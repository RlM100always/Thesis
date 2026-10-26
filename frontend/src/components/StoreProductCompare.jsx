import {useEffect} from "react";
import {productImage} from "../storeImages";

const bdMoney=value=>value==null?"দাম জানতে যোগাযোগ":"৳"+Number(value).toLocaleString("bn-BD",{maximumFractionDigits:0});
function ProductCell({product,storeCategory,onRemove,onView,onAdd}){
 const sellable=product.in_stock!==false&&product.price!=null;
 return <article className="s-compare-item">
   <button type="button" className="s-compare-remove" onClick={()=>onRemove(product.id)}
      aria-label={product.name+" তুলনা থেকে সরান"}>×</button>
   <button type="button" className="s-compare-picture" onClick={()=>onView(product)} aria-label={product.name+" বিস্তারিত"}>
     <img src={product.image_data_url||productImage(product,storeCategory)} alt={product.name} loading="lazy"/>
   </button>
   <strong>{product.name}</strong>
   <span className="s-compare-price">{bdMoney(product.sale_price??product.price)}</span>
   <button type="button" className="s-add-btn" disabled={!sellable} onClick={()=>onAdd(product)}>{sellable?"কার্টে যোগ করুন":"এখন পাওয়া যাচ্ছে না"}</button>
 </article>;
}
export default function StoreProductCompare({items,storeCategory,onClose,onRemove,onView,onAdd}){
 useEffect(()=>{
   function onKey(e){if(e.key==="Escape")onClose();}
   window.addEventListener("keydown",onKey);
   return ()=>window.removeEventListener("keydown",onKey);
 },[onClose]);
 return <div className="s-compare-overlay" role="presentation" onMouseDown={e=>{if(e.target===e.currentTarget)onClose();}}>
   <section role="dialog" aria-modal="true" aria-label="পণ্যের তুলনা" className="s-compare-dialog">
     <header className="s-compare-heading">
       <div><small>SHOP SMARTER</small><h2>পণ্যের তুলনা</h2><p>সরাসরি দোকানের প্রকাশিত তথ্য অনুযায়ী তুলনা করুন।</p></div>
       <button type="button" onClick={onClose} className="s-compare-close" aria-label="তুলনা বন্ধ">✕</button>
     </header>
     <div className="s-compare-columns" style={{gridTemplateColumns:`repeat(${items.length},minmax(180px,1fr))`}}>
       {items.map(p=><ProductCell key={p.id} product={p} storeCategory={storeCategory} onRemove={onRemove} onView={onView} onAdd={onAdd}/>)}
     </div>
     <div className="s-compare-table-wrap">
       <table className="s-compare-table">
         <tbody>
          {[
           ["বিভাগ",p=>p.category||p.tags?.[0]||"উল্লেখ নেই"],
           ["একক",p=>p.unit||"pcs"],
           ["মজুত",p=>p.in_stock===false?"নেই":"পাওয়া যাচ্ছে"],
           ["বিশেষ পণ্য",p=>p.is_featured?"হ্যাঁ":"—"],
           ["বর্ণনা",p=>p.description||"বর্ণনা দেওয়া হয়নি"]
          ].map(([label,value])=><tr key={label}><th scope="row">{label}</th>{items.map(p=><td key={p.id}>{value(p)}</td>)}</tr>)}
         </tbody>
       </table>
     </div>
     <p className="s-compare-note">এখানে দেখানো দাম ও মজুত checkout-এর আগে পরিবর্তিত হতে পারে। ডেমো দোকানে কোনো বাস্তব পেমেন্ট বা ডেলিভারি নেই।</p>
   </section>
 </div>;
}
