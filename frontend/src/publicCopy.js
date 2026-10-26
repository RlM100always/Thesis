/**
 * Public-site presentation copy compatibility.
 * Legacy CMS entries can override newer editorial defaults for years. Keep
 * externally stored content unchanged, but normalize known legacy UI wording
 * when rendering. Unknown merchant/admin-written copy remains untouched.
 */
const exactLegacy = new Map([
 ["বাংলাদেশের SME-এর জন্য actor-aware operation, traceable হিসাব এবং ব্যাখ্যাসহ সিদ্ধান্ত সহায়তা।","বাংলাদেশের ছোট ও মাঝারি ব্যবসার বিক্রি, মজুত, হিসাব ও দৈনন্দিন কাজ পরিচালনার সফটওয়্যার।"],
 ["বিক্রি, স্টক, ক্যাশ, বাকি, কর্মী ও ডেলিভারি — সব এখন একটা অ্যাপ থেকেই চালান। আলাদা খাতা-কলম বা একাধিক হিসাবের ঝামেলা লাগবে না।","বিক্রি, মজুত, নগদ লেনদেন, বাকির হিসাব এবং কর্মীদের কাজ এক জায়গা থেকে দেখুন।"],
 ["আপনার টিম কাজ করবে, সিস্টেম নিজে সব মিলিয়ে রাখবে","আপনার দলের কাজ ও হিসাব একই জায়গায় দেখুন"],
 ["খাতা কলমের দোকান থেকে B-SMART এ গেলে কী বদলায়","খাতা-কলম থেকে ডিজিটাল হিসাবে কী পরিবর্তন আসে"],
 ["এক software, বাস্তব ব্যবসার বহু রূপ","একটি সফটওয়্যার, বিভিন্ন ধরনের ব্যবসার প্রয়োজন"],
 ["Production capability ও rollout status স্বচ্ছভাবে প্রকাশ করা হয়।","কোন সুবিধা চালু আছে আর কোনটি পরীক্ষামূলক, তা স্পষ্টভাবে জানানো হয়।"],
 ["বাংলাদেশের ছোট ও মাঝারি ব্যবসার জন্য তৈরি — সহজ, স্পষ্ট ও প্রমাণসহ।","বাংলাদেশের ছোট ও মাঝারি ব্যবসার দৈনন্দিন কাজ ও হিসাবের জন্য তৈরি।"],
 ["System status","সিস্টেমের অবস্থা"],
 ["ডেমো ডেটা","পরীক্ষামূলক তথ্য"],
 ["Owner account","মালিকের অ্যাকাউন্ট"],
 ["Business login","ব্যবসার অ্যাকাউন্টে প্রবেশ"],
 ["Made in Bangladesh","বাংলাদেশের ব্যবসার জন্য"],
 ["Built for Bangladesh","বাংলাদেশের ব্যবসার জন্য"],
 ["এক software","একটি সফটওয়্যার"],
 ["একটা বিক্রি হলেই পুরো হিসাব নিজে থেকে আপডেট হয়","একটি বিক্রি থেকে সংশ্লিষ্ট হিসাবের অগ্রগতি দেখুন"],
 ["সবার জন্য একই মেনু না","সবার জন্য এক রকম মেনু নয়"],
 ["শুধু শুধু ফিচারের সংখ্যা বাড়ানো নয়।","শুধু ফিচারের সংখ্যা বাড়ানোই লক্ষ্য নয়।"]
]);
const mixedTerms=[
 [/(^|[\s,])stock(?=[\s,।]|$)/gi,"$1মজুত"],
 [/(^|[\s,])inventory(?=[\s,।]|$)/gi,"$1মজুত"],
 [/(^|[\s,])cashbook(?=[\s,।]|$)/gi,"$1নগদ হিসাব"],
 [/(^|[\s,])dashboard(?=[\s,।]|$)/gi,"$1ড্যাশবোর্ড"],
 [/(^|[\s,])outcome(?=[\s,।]|$)/gi,"$1ফলাফল"],
 [/(^|[\s,])owner account(?=[\s,।]|$)/gi,"$1মালিকের অ্যাকাউন্ট"],
 [/(^|[\s,])real payment(?=[\s,।]|$)/gi,"$1বাস্তব পেমেন্ট"],
 [/(^|[\s,])real delivery(?=[\s,।]|$)/gi,"$1বাস্তব ডেলিভারি"],
 [/(^|[\s,])operational database(?=[\s,।]|$)/gi,"$1কার্যকর ডাটাবেস"],
 [/(^|[\s,])business workspace(?=[\s,।]|$)/gi,"$1ব্যবসার কর্মক্ষেত্র"],
 [/(^|[\s,])actor-aware operation(?=[\s,।]|$)/gi,"$1দায়িত্বভিত্তিক কাজ"],
 [/(^|[\s,])traceable হিসাব(?=[\s,।]|$)/gi,"$1যাচাইযোগ্য হিসাব"]
];
function editorialKey(key){
 return !/(?:^|[._])(?:id|icon|src|source|credit|href|link|url|image|logo|code|price|name_key|ref)(?:$|[._])/i.test(key);
}
export function normalizePublicCopy(value,key="",fallback=""){
 if(typeof value!=="string")return value??fallback;
 const trimmed=value.trim();
 if(!trimmed)return fallback;
 if(!editorialKey(key) || /^(?:https?:\/\/|mailto:|tel:|#\/)/i.test(trimmed))return value;
 // Do not replace proper business names, prose we have not reviewed, or user data.
 const canonical=exactLegacy.get(trimmed);
 if(canonical)return canonical;
 return mixedTerms.reduce((result,[pattern,replacement])=>result.replace(pattern,replacement),value);
}
export function normalizePublicContentTree(value,key=""){
 if(typeof value==="string")return normalizePublicCopy(value,key,value);
 if(Array.isArray(value))return value.map((item,index)=>normalizePublicContentTree(item,`${key}.${index}`));
 if(value&&typeof value==="object"){
  return Object.fromEntries(Object.entries(value).map(([k,v])=>[k,editorialKey(k)?normalizePublicContentTree(v,`${key}.${k}`):v]));
 }
 return value;
}
