/* Browser-only shopping conveniences, scoped to the current store.
 * Stored IDs, not personal data. No tracking, API calls or account required.
 */
const MAX_RECENT=8;
const MAX_COMPARE=3;
const STORAGE_PREFIX="bsmart-recent-products:v1:";
const keyFor=storeId=>STORAGE_PREFIX+encodeURIComponent(String(storeId||"unknown").slice(0,110));
export function recentProducts(storeId){
 try {
  const raw=JSON.parse(localStorage.getItem(keyFor(storeId))||"[]");
  return Array.isArray(raw)?[...new Set(raw.filter(v=>typeof v==="string"&&v.length>0&&v.length<=120))].slice(0,MAX_RECENT):[];
 }catch{return [];}
}
export function rememberProduct(storeId,productId){
 if(!productId)return recentProducts(storeId);
 const id=String(productId);
 if(id.length>120)return recentProducts(storeId);
 const next=[id,...recentProducts(storeId).filter(item=>item!==id)].slice(0,MAX_RECENT);
 try{localStorage.setItem(keyFor(storeId),JSON.stringify(next));}catch{/* private browsing */ }
 return next;
}
export function toggleCompared(ids,id,limit=MAX_COMPARE){
 const key=String(id);
 if(ids.includes(key))return ids.filter(v=>v!==key);
 if(ids.length>=limit)return ids;
 return [...ids,key];
}
export const COMPARE_LIMIT=MAX_COMPARE;
