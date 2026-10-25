const photos = {
  grocery: "photo-1542838132-92c53300491e",
  pharmacy: "photo-1585435557343-3b092031a831",
  fashion: "photo-1445205170230-053b83016050",
  restaurant: "photo-1517248135467-4c7edcad34c4",
  electronics: "photo-1498049794561-7780e7231661",
  hardware: "photo-1530124566582-a618bc2615dc",
  beauty: "photo-1596462502278-27bfdc403348",
  stationery: "photo-1455390582262-044cdead277a",
  mobile: "photo-1511707171634-5f897ff02aa9",
  furniture: "photo-1555041469-a586c61ea9bc",
  generic: "photo-1441986300917-64674bd600d8",
};

const demoStoreCovers = {
  "al-helal-pharma": "photo-1587854692152-cbe660dbde88",
  "ma-moni-grocery": "photo-1542838132-92c53300491e",
  "new-look-fashion": "photo-1496747611176-843222e1e57c",
  "shwader-kitchen": "photo-1504674900247-0877df9cc836",
  "digital-zone": "photo-1498049794561-7780e7231661",
  "builders-hardware": "photo-1504917595217-d4dc5ebe6122",
  "glamour-beauty": "photo-1596462502278-27bfdc403348",
  "gyan-bhandar-stationery": "photo-1455390582262-044cdead277a",
  "smart-mobile-center": "photo-1511707171634-5f897ff02aa9",
  "aramdayak-furniture": "photo-1555041469-a586c61ea9bc",
  "prita-business-store": "photo-1522335789203-aabd1fc54bc9",
};

const productPhotos = {
  medicine: [208512, 3683098, 3873209, 593451],
  produce: [3184183, 1435735, 616401, 1640777],
  bread: [1410235, 825661, 376464],
  dairy: [1640777, 1435735, 406152],
  clothing: [2220306, 1536619, 3622608, 1884581],
  food: [1410235, 825661, 376464, 958545],
  electronics: [356056, 1279107, 404280, 1714208],
  mobile: [1042143, 788946, 1616470, 699122],
  beauty: [3762875, 3997991, 4465124, 2113855],
  furniture: [1350789, 276583, 1866149, 2082090],
};

const url = (id, width = 900) => `https://images.unsplash.com/${id}?auto=format&fit=crop&w=${width}&q=82`;
const pexelsUrl = id => `https://images.pexels.com/photos/${id}/pexels-photo-${id}.jpeg?auto=compress&cs=tinysrgb&w=700&h=700&fit=crop`;
const isSeedSvgCover = value => typeof value === "string" && value.startsWith("data:image/svg+xml");
const categoryKey = (value = "") => {
  const text = value.toLowerCase();
  if (/ফার্মেসি|pharm|medicine|drug/.test(text)) return "pharmacy";
  if (/গ্রোসারি|grocery|supermarket|খাদ্য/.test(text)) return "grocery";
  if (/পোশাক|fashion|clothing|apparel/.test(text)) return "fashion";
  if (/রেস্তোরাঁ|restaurant|cafe|food/.test(text)) return "restaurant";
  if (/ইলেকট্রনিক|electronics/.test(text)) return "electronics";
  if (/হার্ডওয়্যার|hardware|tools/.test(text)) return "hardware";
  if (/বিউটি|beauty|cosmetic/.test(text)) return "beauty";
  if (/স্টেশনারি|stationery|book/.test(text)) return "stationery";
  if (/মোবাইল|mobile|phone/.test(text)) return "mobile";
  if (/ফার্নিচার|furniture/.test(text)) return "furniture";
  return "generic";
};

export function storeCoverImage(store = {}) {
  const demoCover = demoStoreCovers[store.slug];
  if (store.cover_data_url && !(demoCover && isSeedSvgCover(store.cover_data_url))) {
    return store.cover_data_url;
  }
  if (demoCover) return url(demoCover, 1400);
  const key = categoryKey(`${store.category || ""} ${store.display_name || ""} ${store.tagline || ""}`);
  return url(photos[key] || photos.generic, 1200);
}

export function productImage(product = {}, storeCategory = "") {
  const text = `${product.name || ""} ${product.category || ""} ${(product.tags || []).join(" ")}`.toLowerCase();
  let key;
  if (/tablet|capsule|medicine|drug|syrup|ঔষধ|ট্যাবলেট|ক্যাপসুল|সিরাপ|mg\b/.test(text)) key = "medicine";
  else if (/rice|চাল|vegetable|সবজি|fruit|ফল|fish|মাছ/.test(text)) key = "produce";
  else if (/bread|ব্রেড|রুটি|bakery/.test(text)) key = "bread";
  else if (/milk|দুধ|dairy/.test(text)) key = "dairy";
  else if (/shirt|শার্ট|dress|পোশাক|shoe|জুতা|cloth/.test(text)) key = "clothing";
  else if (/mobile|phone|মোবাইল|charger|চার্জার/.test(text)) key = "mobile";
  else if (/electronic|electronics|bulb|fan|ইলেকট্র/.test(text)) key = "electronics";
  else if (/beauty|cosmetic|কসমেট/.test(text)) key = "beauty";
  else if (/chair|table|sofa|furniture|আসবাব/.test(text)) key = "furniture";
  else if (/food|meal|restaurant|খাবার/.test(text)) key = "food";
  else key = categoryKey(storeCategory);
  const storeKey = categoryKey(storeCategory);
  const categoryFallback = { pharmacy: "medicine", grocery: "produce", fashion: "clothing", restaurant: "food", mobile: "mobile", electronics: "electronics", beauty: "beauty", furniture: "furniture" }[storeKey] || "food";
  const ids = productPhotos[key] || productPhotos[categoryFallback];
  const name = `${product.name || ""}${product.sku || ""}`;
  const index = [...name].reduce((sum, char) => sum + char.codePointAt(0), 0) % ids.length;
  return pexelsUrl(ids[index]);
}
