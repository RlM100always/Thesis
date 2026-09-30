// One description per panel, shared by the public landing page (pages/Landing.jsx)
// and the in-app guide (pages/Guide.jsx) — so the two never drift apart into
// two different explanations of the same feature.

export const BUSINESS_GUIDE = [
  {
    heading: "দৈনিক কাজ",
    items: [
      { label: "ড্যাশবোর্ড", to: "/", description: "আজকের বিক্রি, বাকি, কম স্টক ও করণীয় — এক নজরে।" },
    ],
  },
  {
    heading: "বিক্রি ও কাস্টমার",
    items: [
      { label: "বিক্রি", to: "/sales", description: "ক্যাশ, বিকাশ, নগদ বা বাকিতে বিক্রি করুন — অফলাইনেও কাজ করে।" },
      { label: "বিক্রির ইতিহাস", to: "/sales-history", description: "পুরনো চালান খুঁজুন, আবার প্রিন্ট করুন।" },
      { label: "কোটেশন ও অর্ডার", to: "/orders", description: "দাম জানিয়ে কোটেশন দিন, গ্রাহক রাজি হলে অর্ডারে বদলান।" },
      { label: "রিটার্ন", to: "/returns", description: "ফেরত নেওয়া পণ্য, টাকা ফেরত বা বাকি সমন্বয়।" },
      { label: "কাস্টমার ও সাপ্লায়ার", to: "/directory", description: "কার কাছে কত বাকি পাবেন, কাকে কত দেবেন — আদায় ও পেমেন্ট এখান থেকেই।" },
    ],
  },
  {
    heading: "স্টক ও ক্রয়",
    items: [
      { label: "স্টক", to: "/inventory", description: "কোন পণ্যের কত আছে, শাখা বদল করে মাল পাঠান।" },
      { label: "মেয়াদ ও ব্যাচ", to: "/expiry", description: "কোন ব্যাচ কবে মেয়াদ শেষ হবে, কত টাকার মাল ঝুঁকিতে।" },
      { label: "স্টক গণনা", to: "/stock-count", description: "শেলফে গুনে সিস্টেমের সাথে মিলিয়ে নিন, গরমিল একবারে ঠিক করুন।" },
      { label: "পণ্য", to: "/products", description: "নাম, দাম, ক্রয়মূল্য, বারকোড — পণ্যের তালিকা।" },
      { label: "কী কিনবেন", to: "/reorder", description: "বিক্রির হিসাবে কোন পণ্য কত কিনতে হবে, এক ক্লিকে অর্ডার।" },
      { label: "ক্রয়", to: "/purchases", description: "সাপ্লায়ারকে অর্ডার দিন, মাল এলে ব্যাচ/মেয়াদ লিখে রিসিভ করুন।" },
      { label: "সাপ্লায়ার ক্লেইম", to: "/purchase-returns", description: "খারাপ বা ভুল মাল সাপ্লায়ারকে ফেরত পাঠানোর হিসাব।" },
    ],
  },
  {
    heading: "টাকা ও প্রতিবেদন",
    items: [
      { label: "হিসাব", to: "/accounts", description: "কাস্টমার/সাপ্লায়ারের বাকি, বয়স অনুযায়ী ভাগ করা।" },
      { label: "ক্যাশ মেলান", to: "/cash", description: "দিনশেষে ক্যাশ বাক্সের টাকা সিস্টেমের হিসাবের সাথে মেলান।" },
      { label: "আর্থিক প্রতিবেদন", to: "/accounting", description: "পূর্ণ খতিয়ান — ট্রায়াল ব্যালান্স, লাভ-ক্ষতি, ব্যালান্স শিট।" },
      { label: "ইনসাইটস", to: "/insights", description: "কোন পণ্য বেশি লাভ দেয়, কোনটা পড়ে আছে, দাম বেড়েছে কিনা।" },
      { label: "রিপোর্ট", to: "/reports", description: "সব হিসাব CSV আকারে নামিয়ে নিন, Excel-এ খোলা যায়।" },
    ],
  },
  {
    heading: "AI সুপারিশ",
    items: [
      { label: "আজকের করণীয়", to: "/strategy", description: "আজ কী কী করা উচিত — লাভ, খরচ, ঝুঁকি হিসাব করে সাজানো তালিকা।" },
      { label: "সুপারিশ", to: "/bsmart-actions", description: "নিজের ব্যবসার ডেটা থেকে reorder/মেয়াদ/কাস্টমার-ফেরানোর সুপারিশ, গ্রহণ-বাতিল করুন, ফলাফল লিখুন।" },
      { label: "বিক্রির পূর্বাভাস", to: "/forecast", description: "আগামী দিনের বিক্রি কেমন হতে পারে, তার পূর্বাভাস।" },
      { label: "কাস্টমার গ্রুপ", to: "/segments", description: "কাস্টমারদের কেনাকাটার ধরন অনুযায়ী দলে ভাগ করা।" },
      { label: "নিজের ফাইল আপলোড করুন", to: "/upload", description: "পুরনো বিক্রির ফাইল দিয়ে দ্রুত ঝুঁকি স্কোর দেখুন, অ্যাকাউন্ট ছাড়াই।" },
    ],
  },
  {
    heading: "সেটআপ",
    items: [
      { label: "ব্যবসা ও শাখা", to: "/setup", description: "দোকানের তথ্য, শাখা, লয়্যালটি নিয়ম, পুরনো ডেটা আমদানি।" },
      { label: "তথ্য আমদানি", to: "/import", description: "পুরনো বিক্রি/পণ্য/কাস্টমারের ফাইল সিস্টেমে তুলুন।" },
      { label: "অনুমোদন", to: "/approvals", description: "বড় খরচ, ছাড় বা অর্ডারের জন্য মালিকের অনুমোদন — একটা ইনবক্সে।" },
      { label: "কর্মী ও ভূমিকা", to: "/staff", description: "কর্মী যোগ করুন, কে কী দেখতে/করতে পারবে ঠিক করুন।" },
      { label: "কার্যকলাপের ইতিহাস", to: "/audit", description: "কে কখন কী পরিবর্তন করেছে, তার পূর্ণ ইতিহাস।" },
    ],
  },
];

export const RESEARCH_GUIDE = {
  heading: "থিসিস মূল্যায়ন (গবেষণা মোড)",
  note: "এই অংশ ইচ্ছাকৃতভাবে স্থির/read-only — থিসিসের গবেষণা ডেটাসেটের উপর চালানো একটা নির্দিষ্ট ফলাফল, যাতে একটা উদ্ধৃত সংখ্যা প্রতিবার পাতা খুললে বদলে না যায়। দৈনন্দিন ব্যবসার আসল কাজ ব্যবসা মোডে।",
  items: [
    { label: "B-SMART অ্যালগরিদম (R_t)", description: "গবেষণা ডেটাসেটের উপর অ্যালগরিদম ১-এর সম্পূর্ণ, উদ্ধৃতযোগ্য ফলাফল।" },
    { label: "মডেল রিপোর্ট", description: "প্রতিটা মডেলের accuracy, ROC-AUC, leakage-ablation ইত্যাদি।" },
    { label: "Real-data validation", description: "প্রকৃত পাবলিক ডেটাসেটের (UCI, BD retailer) উপর একই মডেলের ফলাফল।" },
    { label: "গবেষণা ডেটাসেট", description: "যে সিন্থেটিক-লিংকড ডেটাসেটের উপর থিসিসের সংখ্যাগুলো হিসাব করা।" },
    { label: "ঝুঁকি ক্যালকুলেটর", description: "constraint বদলালে সুপারিশ কীভাবে বদলায়, তার what-if।" },
    { label: "বিক্রি ওভারভিউ (synthetic)", description: "ডেমো ড্যাশবোর্ড, সিন্থেটিক ডেটার উপর — লাইভ ব্যবসার নয়।" },
  ],
};
