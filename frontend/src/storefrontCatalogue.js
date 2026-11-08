export function filterAndSortProducts(products, { search = "", category = null, brand = "", stock = "all", sort = "recommended" } = {}) {
  const q = String(search).trim().toLocaleLowerCase();
  const selectedBrand = String(brand).trim().toLocaleLowerCase();
  const list = (products || []).filter(product => {
    if (q) {
      const haystack = [product.name, product.sku, product.category, product.brand, product.description, ...(product.tags || [])]
        .filter(Boolean).join(" ").toLocaleLowerCase();
      if (!haystack.includes(q)) return false;
    }
    if (category && product.category !== category && !(product.tags || []).includes(category)) return false;
    if (selectedBrand && String(product.brand || "").trim().toLocaleLowerCase() !== selectedBrand) return false;
    if (stock !== "all") {
      const available = product.in_stock !== undefined
        ? !!product.in_stock
        : Number(product.quantity ?? product.stock_qty ?? 0) > 0;
      if (stock === "available" && !available) return false;
      if (stock === "unavailable" && available) return false;
    }
    return true;
  });
  if (sort === "price-low" || sort === "price-high") list.sort((a, b) => {
    if (a.price == null) return b.price == null ? 0 : 1;
    if (b.price == null) return -1;
    return sort === "price-low" ? a.price - b.price : b.price - a.price;
  });
  if (sort === "name") list.sort((a, b) => String(a.name || "").localeCompare(String(b.name || ""), "bn"));
  return list;
}
