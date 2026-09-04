# B-SMART UI/UX পুনর্নির্মাণ পরিকল্পনা

কোড পড়ে (অনুমান না) পাওয়া সমস্যা, তার কারণ, এবং একটা world-class,
বাংলা-প্রথম, বাংলাদেশি SME-কেন্দ্রিক সিস্টেমে রূপান্তরের পূর্ণাঙ্গ পরিকল্পনা।

---

## ০. সংক্ষেপে সমস্যা কী, কোথায়

আপনার অভিযোগ তিনটা — প্রতিটার পেছনে কোড-প্রমাণ:

### ১. "সবকিছু বাংলায় হবে" — কিন্তু হয়নি

`OperationalDashboard.jsx:32-40` — যেটা একজন দোকান মালিক **প্রথম** যে পেজ
দেখেন, সেখানেই:

```
নিট বিক্রি | Gross profit | খরচের পর ফল | বাকি পাবেন | বাকি দেবেন
"Return:" | "Cost অনুযায়ী বর্তমান stock value:" | "গড় invoice:"
```

এক বাক্যের মধ্যে বাংলা আর ইংরেজি এলোমেলোভাবে মেশানো। `App.jsx:41-58`-এ
সাইডবার নেভিগেশনেও একই সমস্যা — "দৈনিক ব্যবসা" গ্রুপ বাংলা, কিন্তু তার
পাশেই "AI সিদ্ধান্ত সহায়তা" গ্রুপের ভেতরে "Sales overview", "Sales
forecast", "Customer groups", "Upload / update data" — সব ইংরেজি।
`useApi.jsx:38-53`-এর loading/error message পুরোপুরি ইংরেজি এবং error
message-এ raw terminal command দেখানো হয় (`uvicorn api.main:app --reload`)
— একজন দোকানদারের কাছে এটা সম্পূর্ণ অর্থহীন।

**কারণ**: কোনো কেন্দ্রীয় translation/i18n layer নেই। প্রতিটা পেজ নিজের
মতো করে হার্ডকোড করা Bangla/English string বসিয়েছে, কেউ পুরো ব্যাপারটা
নিয়ন্ত্রণ করেনি।

### ২. "UI প্রপারলি কাজ করতেছে না" — architecture-এর কারণে

`Operations.jsx`-এর প্রতিটা page component **একটাই লাইনে লেখা** —
`ProductsPage` ফাংশনের JSX ১,১৪২ অক্ষর একটানা, `SalesPage`-এর একটা লাইন
২,১০২ অক্ষর। এটা কোনো bundler-generated বা minified কোড না — হাতে লেখা
সোর্স। ফলাফল:

- **Success আর error একই দেখতে** — প্রতিটা ফর্মে `msg` নামে একটাই state,
  সফল হলে "পণ্য যোগ হয়েছে" আর ব্যর্থ হলে error message — দুটোই একই ধূসর
  `<p>{msg}</p>`-তে বসে। ব্যবহারকারী চোখের পলকে বুঝতে পারবেন না তার কাজ
  হয়েছে না ব্যর্থ হয়েছে। (`Operations.jsx:16,24,33,40-41` — প্রতিটা
  ফর্মে একই প্যাটার্ন পুনরাবৃত্তি)
- **কোনো loading feedback নেই** — ডেটা আসার আগ পর্যন্ত টেবিল ফাঁকা দেখায়,
  মনে হয় সিস্টেম আটকে গেছে।
- **প্রতিটা mutation-এর পর পুরো পেজ রিলোড** (`load()` পুরো ডেটাসেট আবার
  আনে) — কোনো optimistic update নেই, তাই ধীরগতি মনে হয়।
- **স্টক সমন্বয়ে কোনো confirm নেই** — টাইপো হলেই সাথে সাথে স্টক ভুল
  পরিমাণে বদলে যায়, undo নেই।
- **Category ফ্রি-টেক্সট** (`AccountsPage`-এ খরচের category একটা সাধারণ
  input, dropdown না) — একই খরচ কেউ লিখবে "ভাড়া", কেউ "rent", কেউ "Bhara"
  — AI analytics-এর জন্য এই ডেটা এলোমেলো হয়ে যাবে।
- **কোনো shared component নেই** — `components/` ফোল্ডারে মাত্র দুটো ফাইল
  (`Metric.jsx`, `DataSourceBanner.jsx`)। প্রতিটা পেজ নিজের ফর্ম, টেবিল,
  বাটন নতুন করে লিখছে — একই কাজ ১৫ বার আলাদাভাবে, তাই একটায় বাগ ফিক্স করলে
  বাকি ১৪টায় থেকে যায়।

### ৩. Navigation নিজেই বিভ্রান্তিকর

`App.jsx:26-59`-এ তিনটা nav group: "দৈনিক ব্যবসা", "AI সিদ্ধান্ত সহায়তা",
"How this system was built"। শেষ গ্রুপে আছে "Model report", "Research
dataset", "Risk calculator" — এগুলো থিসিস মূল্যায়নের জন্য দরকারি, কিন্তু
**একজন বাস্তব দোকান মালিকের জন্য সম্পূর্ণ অপ্রাসঙ্গিক এবং বিভ্রান্তিকর**।
"আমার ব্যবসার জন্য 'Research dataset' মানে কী?" — এই প্রশ্ন তুলবে।

---

## ১. ডিজাইন নীতি (Bangladeshi SME context-এর জন্য)

আগের রিসার্চ থেকে (`docs/SME_FEATURE_RESEARCH.md`, `THESIS_PRODUCT_MASTER_PLAN.md`
§৯): SME digital maturity মাঝারি (~0.45/1), বাধা হলো স্কিল-ঘাটতি ও আস্থার
অভাব, ইচ্ছার অভাব না। তাই:

1. **বাংলা-প্রথম, ইংরেজি-শূন্য নয় — কিন্তু নিয়ন্ত্রিত**। দোকান মালিক যা
   ছোঁবেন (POS, স্টক, ড্যাশবোর্ড, সুপারিশ) — ১০০% বাংলা। গবেষক/মূল্যায়নকারীর
   জন্য যা (Model Report, literature-related) — সেটা আলাদা এলাকায়, স্পষ্ট
   লেবেল দিয়ে আলাদা রাখা, প্রধান নেভিগেশনে মেশানো নয়।
2. **প্রতিটা action-এর ফলাফল স্পষ্ট, রঙিন, আলাদা** — সবুজ = সফল, লাল =
   ব্যর্থ, কখনো একই ধূসর টেক্সট না।
3. **কম টাইপ, বেশি বাছাই** — dropdown, বাটন, preset — free-text কমানো
   (বিশেষ করে category-জাতীয় ফিল্ড, যেখানে ভুল টাইপ ডেটা নষ্ট করে)।
4. **মোবাইল-প্রথম বিবেচনা** — অনেক দোকান মালিক ফোন থেকেই চালাবেন, ল্যাপটপ
   না। বর্তমান sidebar `@media (max-width: 720px)`-এ horizontal-scroll নেভে
   বদলায় (`index.css:175-184`) — কাজ করে, কিন্তু POS ফর্ম এখনো
   `grid-template-columns: repeat(2, ...)` যা ছোট স্ক্রিনে চাপা লাগে।
5. **বিশ্বাস তৈরি করা UI দিয়ে** — যে সংখ্যা AI predict করেছে vs যেটা
   real হিসাব, সেটা visually আলাদা হওয়া উচিত (এটা `analytics_routes.py`-তে
   `confidence: model|baseline` ব্যাকএন্ডে ইতিমধ্যে আছে — কিন্তু frontend-এ
   এই পার্থক্য কোথাও দেখানো হয় না, এটা একটা বড় miss)।
6. **ক্যালেন্ডার সচেতনতা দৃশ্যমান করা** — ঈদ/রমজানের মতো মৌসুমি প্রভাব
   dashboard-এ note হিসেবে দেখানো, শুধু মডেলের হিডেন ফিচার না রাখা।

---

## ২. Information Architecture পুনর্গঠন

বর্তমান তিন-গ্রুপ নেভিগেশন ভেঙে **persona-ভিত্তিক** দুটো mode করা:

```
┌─────────────────────────────────────┐
│  🏪 ব্যবসা মোড (ডিফল্ট, ১০০% বাংলা)   │
├─────────────────────────────────────┤
│  ড্যাশবোর্ড                           │
│  বিক্রি (POS)                         │
│  স্টক ও পণ্য                          │
│  ক্রয় ও সাপ্লায়ার                    │
│  কাস্টমার                             │
│  হিসাব (আয়-ব্যয়, বাকি)                │
│  ── AI সুপারিশ ──                     │
│  আজকের করণীয়                         │
│  পূর্বাভাস (কী বিক্রি হবে)             │
│  কাস্টমার ঝুঁকি                        │
│  ── সেটআপ ──                          │
│  ব্যবসা ও শাখা                        │
│  ডেটা import                          │
└─────────────────────────────────────┘
        [পাদদেশে ছোট লিংক:]
        "গবেষণা ও মডেল বিস্তারিত →"
        (এখানেই Model Report, Research
         dataset, Risk calculator সরানো —
         আলাদা /research route-এ, যেখানে
         header স্পষ্ট করে বলে "এটি থিসিস
         মূল্যায়নের জন্য, দৈনিক ব্যবহারের
         অংশ না")
```

এটা কোনো নতুন backend লাগে না — শুধু `App.jsx`-এর `NAV_GROUPS` আর
routing পুনর্বিন্যাস।

---

## ৩. Component ও Design System — architecture ঠিক করা

### সমস্যার মূল কারণ ঠিক করা: shared component library

`frontend/src/components/`-এ যোগ করতে হবে (প্রতিটা ছোট, single-purpose):

| Component | সমাধান করে |
|---|---|
| `<Toast />` / `<FeedbackBanner success/error>` | success/error আলাদা দেখানো — সবুজ ✓ vs লাল ✗, auto-dismiss |
| `<DataTable columns rows loading empty />` | প্রতিটা পেজ নিজের `<table>` না লিখে একটাই ব্যবহার করবে — loading skeleton, empty state, sort সব একসাথে |
| `<FormField label hint error />` | label + input + inline error message এক জায়গায়, ভুল ইনপুটে লাল বর্ডার |
| `<ConfirmDialog />` | স্টক সমন্বয়, ডিলিট-জাতীয় action-এর আগে "নিশ্চিত?" |
| `<Money value trend />` | `formatBDT` এর সাথে সাথে up/down arrow, সব জায়গায় consistent |
| `<ConfidenceBadge level="model"|"baseline" />` | AI prediction vs সাধারণ হিসাব — ভিজ্যুয়ালি আলাদা, বিশ্বাস তৈরি করে |
| `<CategorySelect options />` | free-text-এর বদলে controlled dropdown (খরচের category, ইত্যাদি) |

### i18n layer — ভাষার সমস্যার আসল সমাধান

`frontend/src/i18n.js` — একটা কেন্দ্রীয় ডিকশনারি:

```js
export const t = {
  grossProfit: "মোট মুনাফা",
  netSales: "নিট বিক্রি",
  return: "ফেরত",
  // ...
};
```

নিয়ম: **কোনো JSX ফাইলে সরাসরি hardcoded label লেখা যাবে না** — সব
`t.xxx` দিয়ে আসবে। এতে ভবিষ্যতে কেউ ভুলে ইংরেজি বসিয়ে দিলেও এক জায়গায়
ধরা পড়বে ও ঠিক করা যাবে। (ইংরেজি UI দরকার হলে ভবিষ্যতে ভাষা টগলও সহজ হবে
— যদিও এখনকার scope শুধু বাংলা)।

### দৃশ্যত প্রুফ — একটা redesigned screen

নিচের আর্টিফ্যাক্টে নতুন ডিজাইন ভাষায় Operational Dashboard-এর high-fidelity
mockup আছে — success/error state, ConfidenceBadge, Bangla-only labels,
ক্যালেন্ডার-সচেতন annotation সহ।

---

## ৪. বিদ্যমান ফিচার অডিট — কাজ করে কিনা, দরকার কিনা, কেন

| ফিচার | ব্যাকএন্ড আছে? | Frontend কাজ করে? | কাস্টমারের কোন সমস্যা সমাধান করে | সমস্যা |
|---|---|---|---|---|
| POS বিক্রি এন্ট্রি | ✅ | ✅ কাজ করে | দ্রুত বিক্রি লেখা, হাতে খাতার বদলে | Success/error আলাদা না, mobile-এ চাপা |
| স্টক সমন্বয় | ✅ | ✅ কাজ করে | কত মাল আছে জানা | কোনো confirm নেই, ভুল হলে সাথে সাথে ক্ষতি |
| ক্রয়/সাপ্লায়ার | ✅ | ✅ (দেখা যায়নি বিস্তারিত, একই প্যাটার্নে লেখা সম্ভবত একই সমস্যা) | কার কাছে কী বাকি, কবে মাল আসবে | একই architecture সমস্যা |
| হিসাব/খরচ | ✅ | ✅ কাজ করে | লাভ-ক্ষতি বোঝা | Category free-text — ডেটা নোংরা হবে |
| Operational Dashboard | ✅ | ✅ কাজ করে | দৈনিক অবস্থা এক নজরে | ভাষা মিশ্রণ (সবচেয়ে গুরুতর) |
| AI সুপারিশ/করণীয় (`/strategy`) | ✅ (model+baseline উভয়) | ✅ কাজ করে | কী অর্ডার করব, কার সাথে যোগাযোগ করব | model vs baseline পার্থক্য frontend-এ দেখানো হয় না — এটা AI-powered দাবির মূল প্রমাণ, লুকিয়ে থাকা উচিত না |
| Real-data import (`BusinessSetup.jsx`) | ✅ | ✅ কাজ করে (আজ টেস্ট করা হয়েছে) | নিজের পুরনো বিক্রির ইতিহাস আপলোড | ঠিক আছে, তুলনামূলক ভালো লেখা |
| Bring-your-own CSV (`Upload.jsx`) | ✅ | ✅ কাজ করে | কোনো ব্যবসা account ছাড়াই এক-দফা বিশ্লেষণ | সম্পূর্ণ ইংরেজি UI, একটা আলাদা design language — মূল অ্যাপ থেকে বিচ্ছিন্ন মনে হয় |
| Model Report / Research dataset / Risk calculator | ✅ | ✅ কাজ করে | থিসিস মূল্যায়নের প্রমাণ দেখানো | **দোকান মালিকের জন্য না** — প্রধান নেভে থাকা উচিত না |
| Market-basket / association analysis | ❌ কোডে নেই | — | "কোন পণ্য একসাথে কেনে" — proposal-এ আছে | এখনো তৈরিই হয়নি |

---

## ৫. নতুন ফিচার আইডিয়া — বাংলাদেশি SME বাস্তবতা অনুযায়ী

প্রতিটার সাথে: **কোন সমস্যা সমাধান করে, ইউজার আসলে ব্যবহার করতে পারবে কিনা**।

1. **দৈনিক "আজকের সারাংশ" SMS/হোমপেজ কার্ড** — "আজ ৳৮,৫০০ বিক্রি, গতকালের
   চেয়ে ১২% বেশি, ৩টা পণ্য কম আছে" — একবার দেখেই পুরো দিন বোঝা। কারণ: SME
   মালিক প্রতিদিন ড্যাশবোর্ডে ডুব দিয়ে numbers ঘাঁটবেন না, একনজরে চান।
   *ব্যবহারযোগ্যতা*: high — dashboard খোলার সাথেই দেখা যায়, কোনো নতুন
   ক্লিক লাগে না।
2. **কম-স্টক অ্যালার্ট ব্যাজ (নেভিগেশনে লাল বিন্দু)** — এখন `low_stock`
   ডেটা আছে কিন্তু dashboard-এ না গেলে দেখা যায় না। *সমাধান*: sidebar-এর
   "স্টক" আইটেমে ব্যাজ, যেন মিস না হয়।
3. **কণ্ঠস্বর/ছবি দিয়ে বিক্রি এন্ট্রি (ভবিষ্যতের জন্য)** — অনেক দোকানদার
   টাইপ করতে স্বচ্ছন্দ না। *এখনকার scope-এ না*, কিন্তু future-work-এ
   উল্লেখযোগ্য।
4. **"গত বছরের এই সময়ে" তুলনা** — ঈদ/পূজার সময় এই তুলনা মালিকের কাছে সবচেয়ে
   অর্থবহ (`ml/real_pipeline.py` ইতিমধ্যে seasonal-naive baseline হিসাব
   করে, শুধু UI-তে "গত বছর এই সময়ে" হিসেবে ফ্রেম করা দরকার)।
5. **Simple/Detailed টগল প্রতিটা পেজে** — `UiContext.jsx`-এ ইতিমধ্যে
   `simple` mode আছে কিন্তু ব্যবহার সীমিত। *সম্প্রসারণ*: প্রতিটা KPI-তে এই
   টগল সম্মান করা উচিত — simple mode-এ শুধু টাকা ও শতাংশ, detailed mode-এ
   confidence score, sample size ইত্যাদি।
6. **Export/Backup — নিজের ডেটা নিজে ডাউনলোড** — মালিকের আস্থার জন্য
   গুরুত্বপূর্ণ ("আমার ডেটা আটকে নেই")। PDF মাসিক রিপোর্ট + পুরো ডেটা
   CSV backup।
7. **রোল-ভিত্তিক UI ভিউ** — backend-এ `Membership.role` (owner/manager/staff)
   আছে, কিন্তু frontend সবাইকে একই UI দেখায়। কর্মচারীকে হিসাব/খরচ পেজ
   দেখানো উচিত না। *সমাধান*: route guard `role` অনুযায়ী।

---

## ৬. Backend–Frontend–Dataset ডায়নামিক সংযোগ — "যেকোনো ব্যবসার জন্য পূর্ণ সমাধান"

আপনার মূল চাওয়া: *"যেকোনো ডেটাসেট বা যেকোনো বিজনেস ওনার এখান থেকে তার real
problem সমাধান করতে পারুক"*। এটা কাঠামোগতভাবে **ইতিমধ্যে সম্ভব** — শুধু UI
সেই flow-টা স্পষ্ট করে দেখাচ্ছে না। প্রকৃত dynamic flow:

```
নতুন ব্যবসা মালিক
    │
    ▼
[১] সাইন-আপ → Organization তৈরি (BusinessSetup.jsx → POST /api/app/organizations)
    │
    ▼
[২] দৈনিক ব্যবহার শুরু → POS দিয়ে বিক্রি, স্টক, ক্রয় এন্ট্রি
    │  (এখান থেকেই তার নিজস্ব dataset ক্রমশ তৈরি হচ্ছে bsmart.db-তে)
    │
    ▼
[৩] যথেষ্ট ইতিহাস জমলে (৯০+ দিন, ৫০০+ sales row)
    → এক ক্লিকে "নিজের ডেটা দিয়ে AI ট্রেন করুন" বাটন
    → export (/api/app/datasets/sales.csv) + train (ml/real_pipeline.py) —
      এখন এটা ম্যানুয়াল CLI স্টেপ, UI বাটন বানানো দরকার (§৭ দেখুন)
    │
    ▼
[৪] তার নিজের ট্রেইন করা মডেল স্বয়ংক্রিয়ভাবে
    /api/app/recommendations-এ ব্যবহার শুরু হয় (এটা ইতিমধ্যে কাজ করে —
    আজকের সেশনে টেস্ট করা হয়েছে)
    │
    ▼
[৫] AI-চালিত পূর্ণ সমাধান: reorder পরিমাণ, কাস্টমার ঝুঁকি,
    anomaly সতর্কতা — সবই তার নিজস্ব ব্যবসার real ডেটা থেকে
```

**এই flow-টা technically সম্পূর্ণ**, কিন্তু ধাপ ৩-এর "নিজের ডেটা দিয়ে
ট্রেন করুন" অংশটা এখনো UI-তে বাটন হিসেবে নেই — CLAUDE.md-এ লেখা আছে এটা
"manual export → train step"। এটাই dynamic হওয়ার একমাত্র বাকি কাঠামোগত
গ্যাপ, ফিচার-ভিত্তিক না।

---

## ৭. বাস্তবায়ন রোডম্যাপ (অগ্রাধিকার অনুসারে)

| ধাপ | কাজ | প্রভাব | অবস্থা |
|---|---|---|---|
| ১ | i18n fix — সব hardcoded English label বাংলায় রূপান্তর (`useApi.jsx`, `OperationalDashboard.jsx`, `App.jsx` nav, `Upload.jsx`) | সবচেয়ে দৃশ্যমান সমস্যার সমাধান | ✅ সম্পন্ন |
| ২ | `<FeedbackBanner>` + `<ConfirmDialog>` component বানিয়ে সব ফর্মে বসানো | "UI কাজ করতেছে না" অনুভূতির প্রধান কারণ দূর | ✅ সম্পন্ন |
| ৩ | Navigation পুনর্গঠন — ব্যবসা মোড vs গবেষণা মোড আলাদা, কম-স্টক ব্যাজ | বিভ্রান্তি দূর, professional মনে হবে | ✅ সম্পন্ন |
| ৪ | `<ConfidenceBadge>` — AI prediction vs baseline visually আলাদা করা | "AI-powered" দাবির UI প্রমাণ | ✅ সম্পন্ন (`SupplyChain.jsx`-এর `StrategyPage`) |
| ৫ | `Operations.jsx`/`SupplyChain.jsx` পুনর্লিখন — এক-লাইন JSX ভেঙে readable, shared component ব্যবহার করে | দীর্ঘমেয়াদী maintainability, বাগ কমবে | ✅ সম্পন্ন |
| ৬ | "নিজের ডেটা দিয়ে AI ট্রেন করুন" বাটন — নতুন `POST /api/app/train-demand-model` endpoint, export+train এক ক্লিকে | Dynamic flow সম্পূর্ণ করা | ✅ সম্পন্ন, end-to-end টেস্ট করা হয়েছে |
| ৭ | নতুন ফিচার (§৫: দৈনিক সারাংশ কার্ড, role-ভিত্তিক UI, PDF/Excel export, ইত্যাদি) | Product polish | ⏳ বাকি — এখনো implement হয়নি |
| ৮ | `Actions.jsx` (গবেষণা-flow assembly page) এখনো ইংরেজিতে | ভাষা সংগতি | ⏳ বাকি — এটা `/research-actions` route-এ, কোনো nav-এ লিংক করা নেই, তাই কম অগ্রাধিকার |

**যা পরিবর্তন হয়েছে**: `CategorySelect` (free-text-এর বদলে dropdown, খরচের
category-তে), স্টক সমন্বয়ে negative quantity হলে `ConfirmDialog`, sidebar-এ
"স্টক" নেভ-আইটেমে লাল ব্যাজ dot যখন কম স্টকে থাকা পণ্য আছে।

## ৮. দ্বিতীয় দফার audit — visual design system (২০২৬-০৯-০৪)

আগের অডিট মূলত functional bug (ভাষা, success/error, architecture) ধরেছিল।
ব্যবহারকারী পরে সঠিকভাবে ধরিয়ে দেন: এর আগে বানানো "world-class" mockup
Artifact (Tiro Bangla + Hind Siliguri font, spacing/elevation system)
**কখনো আসল `index.css`-এ back-port করা হয়নি** — mockup ছিল শুধু একটা pitch,
বাস্তবায়ন হয়নি। এটাই "no design planning" অভিযোগের প্রকৃত কারণ। কোডে পাওয়া
নির্দিষ্ট প্রমাণ:

- কোনো বাংলা-অপ্টিমাইজড ফন্ট ছিল না — শুধু generic `system-ui` stack, যেখানে
  এখন বেশিরভাগ UI বাংলা টেক্সট।
- `.btn-primary` **দুইবার** সংজ্ঞায়িত ছিল (ভিন্ন padding/font-size সহ) — এক
  জায়গায় প্রথমে লেখা, পরে না মুছেই আবার নতুন করে লেখা হয়েছিল।
- একই বৃত্তাকার-লেবেল কনসেপ্টের জন্য **তিনটা আলাদা class** ছিল (`.badge`,
  `.pill`, `.badge-confidence`) — ভিন্ন সময়ে ভিন্ন নামে বানানো, কখনো
  একীভূত করা হয়নি।
- কোনো spacing scale ছিল না — 14/17/18/20/22/34px এলোমেলো।
- সব card/kpi একই elevation — কোনো visual hierarchy ছিল না।
- Loading state শুধু ধূসর টেক্সট, কোনো spinner ছিল না।

**ঠিক করা হয়েছে**: Hind Siliguri (UI টেক্সট) + Tiro Bangla (heading/সংখ্যা)
ফন্ট যোগ, spacing scale (`--sp-1` থেকে `--sp-8`) ও ৩-স্তরের elevation
(`--shadow-1/2/3`) টোকেন যোগ, badge/pill/badge-confidence-কে একটা shared
base rule-এ একীভূত করা (class name বদলানো হয়নি, শুধু CSS duplicate সরানো),
duplicate `.btn-primary` মুছে একটাই সংজ্ঞা রাখা, `<Loading>`-এ ঘোরানো spinner
যোগ ও সব পেজে সেটাই ব্যবহার করা (আগে কিছু পেজ প্লেইন `<p>লোড হচ্ছে…</p>`
ব্যবহার করত)।

**এখনো বাকি** (পরবর্তী ধাপ হতে পারে): icon system, নতুন card layout
hierarchy আরও গভীরভাবে page-by-page প্রয়োগ, table-এর visual polish।
