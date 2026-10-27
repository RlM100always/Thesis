/* Shared order workflow for the D1 merchant API and customer tracking UI. */
export const ORDER_STATUS_TRANSITIONS = Object.freeze({
  placed: ["confirmed", "cancelled"],
  confirmed: ["processing", "ready", "fulfilled", "cancelled"],
  processing: ["ready", "cancelled"],
  ready: ["dispatched", "shipped", "cancelled"],
  dispatched: ["delivered"],
  shipped: ["delivered"],
  fulfilled: [],
  delivered: [],
  cancelled: [],
});

const STATUS_NOTES = Object.freeze({
  placed: "অর্ডার গ্রহণ করা হয়েছে।",
  confirmed: "দোকান অর্ডারটি নিশ্চিত করেছে।",
  processing: "পণ্য প্রস্তুত করা হচ্ছে।",
  ready: "পণ্য প্যাক করা হয়েছে এবং পাঠানোর জন্য প্রস্তুত।",
  dispatched: "অর্ডার ডেলিভারির জন্য পাঠানো হয়েছে।",
  shipped: "অর্ডার পথে রয়েছে।",
  fulfilled: "অর্ডার সম্পন্ন হয়েছে।",
  delivered: "অর্ডার ডেলিভারি সম্পন্ন হয়েছে।",
  cancelled: "অর্ডার বাতিল করা হয়েছে।",
});

export function canTransitionOrderStatus(current, next) {
  return Array.isArray(ORDER_STATUS_TRANSITIONS[current]) &&
    ORDER_STATUS_TRANSITIONS[current].includes(next);
}

export function defaultOrderStatusNote(status, isDemo = true) {
  const note = STATUS_NOTES[status] || "অর্ডারের অবস্থা হালনাগাদ হয়েছে।";
  return isDemo
    ? `পরীক্ষামূলক অর্ডার: ${note} বাস্তব ডেলিভারি বা পেমেন্ট নেই।`
    : note;
}
