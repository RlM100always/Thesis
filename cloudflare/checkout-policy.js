// Pure, testable safeguards. No payment gateway: this phase is COD only.
export function realCODReady(store,env) {
  return Boolean(store && !store.is_demo && store.owner_id
    && Number(store.real_cod_approved) === 1 && env?.ENABLE_REAL_COD === "true");
}
export function normalizeBangladeshPhone(raw) {
  if (typeof raw !== "string") return null;
  const digits=raw.replace(/[\s()+-]/g,"");
  if (!/^(?:88)?01[3-9][0-9]{8}$/.test(digits)) return null;
  return digits.startsWith("88") ? digits.slice(2) : digits;
}
export function normalizeCODContact(payload) {
  const name=typeof payload?.shipping_name==="string"?payload.shipping_name.trim():"";
  const address=typeof payload?.shipping_address==="string"?payload.shipping_address.trim():"";
  const phone=normalizeBangladeshPhone(payload?.shipping_phone);
  if (name.length<2 || name.length>100 || /[\x00-\x1f]/.test(name))
    throw new Error("Enter a valid customer name (2-100 characters)");
  if (!phone) throw new Error("Enter a valid Bangladesh mobile number");
  if (address.length<10 || address.length>350 || /[\x00-\x08\x0b-\x1f]/.test(address))
    throw new Error("Enter a complete delivery address (10-350 characters)");
  if (payload?.privacy_consent !== true)
    throw new Error("Consent for sharing delivery details with the merchant is required");
  if (payload?.payment_method !== "cod")
    throw new Error("Only cash on delivery is supported; do not transfer money");
  if (payload?.payment_screenshot || payload?.coupon_code || payload?.store_customer_token)
    throw new Error("Online payment, coupons and customer accounts are not yet enabled for D1 COD");
  return {name,phone,address};
}
