// The shop's own details at the top and bottom of every printed receipt.
// Only what the owner filled in is printed; nothing is invented.
export function ReceiptHeader({ shop, branch }) {
  return (
    <>
      <h4>{shop.name}</h4>
      {branch && <p>{branch}</p>}
      {shop.address && <p>{shop.address}</p>}
      {shop.phone && <p>ফোন: {shop.phone}</p>}
      {shop.vat_reg_no && <p>VAT/BIN: {shop.vat_reg_no}</p>}
    </>
  );
}

export function ReceiptFooter({ shop }) {
  return <p style={{ marginTop: 10 }}>{shop.receipt_footer || "ধন্যবাদ!"}</p>;
}
