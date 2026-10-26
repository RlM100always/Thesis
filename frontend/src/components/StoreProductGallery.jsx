import {useEffect,useMemo,useState} from "react";
import {productImage} from "../storeImages";
import "./StoreProductGallery.css";

export default function StoreProductGallery({product,storeCategory,context="detail"}){
 const photos=useMemo(()=>{
   const urls=[product.image_data_url,...(Array.isArray(product.gallery_urls)?product.gallery_urls:[])]
     .filter(x=>typeof x==="string"&&x.length>0);
   return [...new Set(urls.length?urls:[productImage(product,storeCategory)])].slice(0,5);
 },[product,storeCategory]);
 const [active,setActive]=useState(0);
 useEffect(()=>setActive(0),[product.id]);
 function keyPress(e){
   if(photos.length<2)return;
   if(e.key==="ArrowRight"){e.preventDefault();setActive(x=>(x+1)%photos.length);}
   if(e.key==="ArrowLeft"){e.preventDefault();setActive(x=>(x-1+photos.length)%photos.length);}
 }
 return <div className={`s-gallery s-gallery-${context}`} aria-label={product.name+" পণ্যের ছবি"} onKeyDown={keyPress}>
    <div className="s-gallery-stage">
      <img src={photos[active]||photos[0]} alt={product.name+" · ছবি "+(active+1)} loading={context==="modal"?"eager":"lazy"}/>
      {photos.length>1&&<>
        <button type="button" className="s-gallery-arrow previous" onClick={()=>setActive(x=>(x-1+photos.length)%photos.length)} aria-label="আগের ছবি">‹</button>
        <button type="button" className="s-gallery-arrow next" onClick={()=>setActive(x=>(x+1)%photos.length)} aria-label="পরের ছবি">›</button>
        <span className="s-gallery-counter">{active+1} / {photos.length}</span>
      </>}
    </div>
    {photos.length>1&&<div className="s-gallery-thumbnails" role="group" aria-label="ছবি বাছাই">
      {photos.map((url,i)=><button type="button" key={url} className={`s-gallery-thumb${i===active?" active":""}`}
        aria-pressed={i===active} aria-label={"ছবি "+(i+1)} onClick={()=>setActive(i)}>
         <img src={url} alt="" loading="lazy"/>
      </button>)}
    </div>}
  </div>;
}
