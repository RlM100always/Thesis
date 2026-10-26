// Public presentation only. Never modify names or order payloads saved in the database.
// Localize known catalog vocabulary and internal test/demo seed boilerplate.
const CATEGORY_LABELS={
  grocery:"মুদি",groceries:"মুদি",pharmacy:"ফার্মেসি",medicine:"ফার্মেসি",
  fashion:"পোশাক",clothing:"পোশাক",apparel:"পোশাক",restaurant:"রেস্টুরেন্ট",
  electronics:"ইলেকট্রনিক্স",hardware:"হার্ডওয়্যার",beauty:"সৌন্দর্যপণ্য",
  stationery:"স্টেশনারি",mobile:"মোবাইল",furniture:"আসবাবপত্র",
  supermarket:"সুপারশপ",wholesale:"পাইকারি",service:"সেবা"
};
const UNIT_LABELS={
  pcs:"পিস",pc:"পিস",piece:"পিস",pieces:"পিস",unit:"পিস",units:"পিস",
  kg:"কেজি",g:"গ্রাম",gm:"গ্রাম",gram:"গ্রাম",grams:"গ্রাম",
  l:"লিটার",ltr:"লিটার",liter:"লিটার",litre:"লিটার",
  ml:"মিলিলিটার",box:"বাক্স",boxes:"বাক্স",pack:"প্যাকেট",packs:"প্যাকেট",
  packet:"প্যাকেট",packets:"প্যাকেট",bottle:"বোতল",bottles:"বোতল",
  pair:"জোড়া",pairs:"জোড়া",dozen:"ডজন",carton:"কার্টন"
};
const DEMO_TAGLINES={
  "owner-managed demo storefront (not verified real commerce)":"পরীক্ষামূলক দোকান—বাস্তব কেনাকাটার জন্য নয়।",
  "demo storefront (not verified real commerce)":"পরীক্ষামূলক দোকান—বাস্তব কেনাকাটার জন্য নয়।",
  "synthetic demonstration store":"শুধু পরীক্ষামূলক ব্যবহারের দোকান।"
};
const DEMO_DELIVERY_NOTES={
  "demo orders only; no real shipping or payment":"এখানে দেওয়া অর্ডার শুধু পরীক্ষামূলক। বাস্তব পেমেন্ট বা ডেলিভারি হবে না।",
  "no real shipping or payment":"এটি ডেমো দোকান। বাস্তব পেমেন্ট বা ডেলিভারি হবে না।"
};
const key=value=>String(value??"").trim().toLowerCase();
export function displayStoreCategory(value){return CATEGORY_LABELS[key(value)]||value||"";}
export function displayProductUnit(value){return UNIT_LABELS[key(value)]||value||"";}
export function displayStoreTagline(value,isDemo=false){
 const original=String(value??"").trim();
 return isDemo?DEMO_TAGLINES[key(original)]||original:original;
}
export function displayStoreDelivery(value,isDemo=false){
 const original=String(value??"").trim();
 return isDemo?DEMO_DELIVERY_NOTES[key(original)]||original:original;
}
export function displayStoreArea(value,isDemo=false){
 const original=String(value??"").trim();
 return isDemo&&key(original)==="automated test only"?"শুধু পরীক্ষামূলক এলাকা":original;
}
export function isSyntheticDemoArea(value,isDemo=false){
 return Boolean(isDemo&&key(value)==="automated test only");
}
