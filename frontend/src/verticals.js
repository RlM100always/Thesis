// What kind of business this is decides defaults and wording, never what the
// software can do: every business gets the same core (sell, stock, buy, baki,
// expenses, recommendations). Expiry and batch tracking is on by default where
// goods expire, and any business can switch it on for a product later.
//
// Only pharmacy has been validated against real pharmacy records; the other
// types share the same engine and are honest about that in the research docs.

export const VERTICALS = {
  pharmacy: { label: "ফার্মেসি / ওষুধের দোকান", item: "ওষুধ", expiry: true },
  grocery: { label: "মুদি / জেনারেল স্টোর", item: "পণ্য", expiry: true },
  cosmetics: { label: "কসমেটিক্স / বিউটি", item: "পণ্য", expiry: true },
  apparel: { label: "পোশাক / কাপড়", item: "পণ্য", expiry: false },
  hardware: { label: "হার্ডওয়্যার / ইলেকট্রনিক্স", item: "পণ্য", expiry: false },
  other: { label: "অন্যান্য ব্যবসা", item: "পণ্য", expiry: false },
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
