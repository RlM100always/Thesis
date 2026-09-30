// What kind of business this is decides defaults and wording, never what the
// software can do: every business gets the same core (sell, stock, buy, baki,
// expenses, recommendations). Expiry and batch tracking is on by default where
// goods expire, and any business can switch it on for a product later.
//
// Only pharmacy has been validated against real pharmacy records; the other
// types share the same engine and are honest about that in the research docs.

export const VERTICALS = {
  pharmacy: { label: "ফার্মেসি / ওষুধের দোকান", item: "ওষুধ", expiry: true, pack: "pharmacy", modules: ["batch", "expiry", "recall"] },
  grocery: { label: "মুদি / জেনারেল স্টোর / সুপারশপ", item: "পণ্য", expiry: true, pack: "retail", modules: ["barcode", "weight", "expiry"] },
  cosmetics: { label: "কসমেটিক্স / বিউটি পণ্য", item: "পণ্য", expiry: true, pack: "retail", modules: ["variant", "expiry"] },
  apparel: { label: "ফ্যাশন / বুটিক / জুতার দোকান", item: "পণ্য", expiry: false, pack: "fashion", modules: ["variant", "exchange", "collection"] },
  wholesale: { label: "পাইকারি / ডিস্ট্রিবিউশন", item: "পণ্য", expiry: false, pack: "wholesale", modules: ["priceList", "credit", "delivery"] },
  restaurant: { label: "রেস্টুরেন্ট / বেকারি / ক্যাফে", item: "আইটেম", expiry: true, pack: "restaurant", modules: ["table", "kitchen", "recipe", "delivery"] },
  electronics: { label: "ইলেকট্রনিক্স / মোবাইল / কম্পিউটার", item: "পণ্য", expiry: false, pack: "electronics", modules: ["serial", "warranty", "service"] },
  hardware: { label: "হার্ডওয়্যার / স্যানিটারি / নির্মাণ সামগ্রী", item: "পণ্য", expiry: false, pack: "hardware", modules: ["measurement", "project", "delivery"] },
  service: { label: "সার্ভিস / রিপেয়ার সেন্টার", item: "সেবা", expiry: false, pack: "service", modules: ["appointment", "jobCard", "technician"] },
  manufacturing: { label: "ছোট কারখানা / ম্যানুফ্যাকচারিং", item: "পণ্য", expiry: false, pack: "manufacturing", modules: ["bom", "production", "quality"] },
  salon: { label: "সেলুন / পার্লার / স্পা / জিম", item: "সেবা", expiry: true, pack: "appointment", modules: ["appointment", "membership", "commission"] },
  clinic: { label: "ক্লিনিক / ডায়াগনস্টিক প্রশাসন", item: "সেবা", expiry: true, pack: "clinic", modules: ["appointment", "queue", "consumable"] },
  education: { label: "কোচিং / ট্রেনিং / শিক্ষা প্রতিষ্ঠান", item: "কোর্স", expiry: false, pack: "education", modules: ["student", "fees", "attendance"] },
  agro: { label: "কৃষি / ফিড / মৎস্য / পোল্ট্রি", item: "পণ্য", expiry: true, pack: "agro", modules: ["batch", "expiry", "season"] },
  transport: { label: "ট্রান্সপোর্ট / কুরিয়ার / ডেলিভারি", item: "সেবা", expiry: false, pack: "transport", modules: ["trip", "cod", "fleet"] },
  rental: { label: "রেন্টাল / ইভেন্ট / ইকুইপমেন্ট", item: "সম্পদ", expiry: false, pack: "rental", modules: ["booking", "deposit", "asset"] },
  other: { label: "অন্যান্য SME ব্যবসা", item: "পণ্য", expiry: false, pack: "retail", modules: [] },
};

export const BUSINESS_TYPES = Object.entries(VERTICALS).map(([value, v]) => [value, v.label]);

// Businesses created before types existed are "retail"; anything unknown is treated as "other".
export function verticalOf(sector) {
  return VERTICALS[sector] || { ...VERTICALS.other, label: "খুচরা ব্যবসা" };
}

export const EXPIRY_HINT = {
  on: "এই ধরনের ব্যবসায় মেয়াদ ও ব্যাচের হিসাব আগে থেকেই চালু থাকবে।",
  off: "মেয়াদ ট্র্যাকিং দরকার হলে পণ্য যোগ করার সময় নিজে চালু করতে পারবেন।",
};
