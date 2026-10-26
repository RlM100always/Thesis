// Privacy-friendly, device-local wishlists. No customer account or cloud sync.
const PREFIX="bsmart-wishlist-v1:";
function safeKey(key){return PREFIX+encodeURIComponent(String(key||"unknown").slice(0,100));}
export function readFavorites(key){
 try {
  const raw=JSON.parse(localStorage.getItem(safeKey(key))||"[]");
  return Array.isArray(raw)?raw.filter(x=>typeof x==="string"&&x.length<150).slice(0,300):[];
 }catch{return [];}
}
export function saveFavorites(key,ids){
 const clean=[...new Set(ids.filter(x=>typeof x==="string"&&x.length<150))].slice(0,300);
 try{localStorage.setItem(safeKey(key),JSON.stringify(clean));}catch{/* storage may be disabled */}
 return clean;
}
export function toggleFavorite(key,current,id){
 const next=current.includes(id)?current.filter(x=>x!==id):[...current,id];
 return saveFavorites(key,next);
}
