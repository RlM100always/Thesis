// Pure WCAG relative-luminance helpers for user-selected store branding.
// Product labels and buttons must stay readable on all supported presets.
function rgb(hex){
 if(!/^#[0-9a-f]{6}$/i.test(String(hex||"")))return [10,135,82];
 return [1,3,5].map(i=>parseInt(hex.slice(i,i+2),16));
}
export function luminance(hex){
 const [r,g,b]=rgb(hex).map(v=>{const c=v/255;return c<=.04045?c/12.92:((c+.055)/1.055)**2.4;});
 return .2126*r+.7152*g+.0722*b;
}
export function contrastRatio(a,b){
 const x=luminance(a),y=luminance(b);
 return (Math.max(x,y)+.05)/(Math.min(x,y)+.05);
}
export function contrastColor(bg){
 return contrastRatio(bg,"#000000")>=contrastRatio(bg,"#ffffff")?"#000000":"#ffffff";
}
export function readableAccent(color,bg="#ffffff"){
 const initial=/^#[0-9a-f]{6}$/i.test(String(color||""))?color:"#0a8752";
 const background=/^#[0-9a-f]{6}$/i.test(String(bg||""))?bg:"#ffffff";
 if(contrastRatio(initial,background)>=4.5)return initial;
 const target=luminance(background)<.18?[255,255,255]:[0,0,0];
 const original=rgb(initial);
 // Preserve brand hue as much as possible while meeting WCAG AA normal text.
 for(let i=1;i<=100;i++){
  const fraction=i/100;
  const v=original.map((c,j)=>Math.round(c+(target[j]-c)*fraction));
  const trial="#"+v.map(c=>c.toString(16).padStart(2,"0")).join("");
  if(contrastRatio(trial,background)>=4.5)return trial;
 }
 return luminance(background)<.18?"#ffffff":"#000000";
}
