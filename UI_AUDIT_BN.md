# B SMART UI কঠোর অডিট

তারিখ: ১ অক্টোবর ২০২৬  
পদ্ধতি: production build, route ও component inspection, supplied mobile screenshot, responsive CSS এবং keyboard semantics review। প্রতিটি live breakpoint visual screenshot পরীক্ষার জন্য browser inspector connection প্রয়োজন; সেটি এই session এ available নয়। তাই নিচের “ভিজ্যুয়াল পুনরায় দেখুন” আইটেমগুলো প্রকাশের আগে বাস্তব device এ নিশ্চিত করতে হবে।

## নকশার মানদণ্ড

| ক্ষেত্র | গ্রহণযোগ্য মান |
| --- | --- |
| পড়া | body text কমপক্ষে 14px, helper text কমপক্ষে 12px, যথেষ্ট contrast |
| touch | primary interactive target কমপক্ষে 44px |
| mobile | 320px viewport এ কোনো horizontal overflow নয়, CTA অর্থবোধক থাকবে |
| hierarchy | প্রতি screen এ একটি প্রধান কাজ, একটি স্পষ্ট primary CTA |
| trust | ছবি, payment, security ও AI দাবি সত্য ও context সহ দেখাতে হবে |
| motion | reduced motion preference মানতে হবে |

## সকল screen এ পাওয়া মূল সমস্যা ও সমাধান

| সমস্যা | প্রভাব | অবস্থা |
| --- | --- | --- |
| Mobile header এ CTA কেবল `+` ছিল | মানুষ বুঝতে পারে না চাপলে কী হবে | ঠিক করা হয়েছে: পাঠযোগ্য CTA রাখা হয়েছে |
| Product demo তে 8px ও 9px লেখা ছিল | বাস্তব ব্যবহারকারী পড়তে পারে না | ঠিক করা হয়েছে: গুরুত্বপূর্ণ demo copy 11px থেকে 13px |
| Dark footer ও photo credit এর contrast কম ছিল | legal attribution ও footer links পড়া কঠিন | ঠিক করা হয়েছে |
| Modern `color-mix()` ছাড়া tour background fail করতে পারত | পুরোনো browser এ visual break | fallback যোগ করা হয়েছে |
| Motion sensitivity | hover transform motion অসুবিধাজনক হতে পারে | reduced motion override যোগ করা হয়েছে |
| Public copy তে dash style অসামঞ্জস্য | লেখা যান্ত্রিক ও অসমান দেখায় | চলমান: human facing copy থেকে সরানো হচ্ছে |
| CSS বিভিন্ন জায়গায় ছড়ানো এবং inline style বেশি | ভবিষ্যৎ পরিবর্তনে regression ঝুঁকি | refactor backlog, design token migration দরকার |

## Google UI ও accessibility guideline compliance

| Google guideline | পাওয়া সমস্যা | কী করা হয়েছে বা বাকি |
| --- | --- | --- |
| Interactive target কমপক্ষে 48dp | Public menu ছিল 42px, primary/secondary CTA ছিল 43px, product tour tab 44px | Public menu ও CTA 48px করা হয়েছে। Internal app এর compact controls আলাদা device test queue তে আছে |
| Text contrast 4.5 to 1 | Footer, image credit ও কয়েকটি dark demo label দুর্বল ছিল | Footer ও credit contrast বাড়ানো হয়েছে; runtime contrast scan বাকি |
| সব icon বা interactive item এর purpose বোঝাতে হবে | Mobile CTA শুধু `+` ছিল, action বোঝাত না | label সহ CTA করা হয়েছে |
| Keyboard দিয়ে সব interactive item ব্যবহারযোগ্য | Public menu button এ label আছে; custom tab ও selector গুলোকে end to end keyboard test দরকার | blocker test হিসেবে রাখা হয়েছে |
| Semantic HTML ও native control prefer | Static scan এ public image গুলোতে alt পাওয়া গেছে; FAQ native `details` ব্যবহার করে | Internal custom controls ও dialog semantics manual audit বাকি |
| বড় font বা magnification এ layout না ভাঙা | Text 200 percent এবং Android font scale দিয়ে এই session এ visual run করা যায়নি | release blocker visual test |
| image এ নতুন তথ্য শুধু image এ নয় | Photo captions ও contextual copy আছে | photo crop এবং image failure fallback device এ দেখুন |
| state কেবল color দিয়ে বোঝাবেন না | status dots এবং warning colour নির্ভর হওয়ার ঝুঁকি | status text label আছে। internal charts, alert, validation state আলাদা করে verify করতে হবে |

## Public website audit

| পাতা | মানবিক ব্যবহারকারী দৃষ্টিতে সমস্যা | অবস্থা ও করণীয় |
| --- | --- | --- |
| Home | এক screen এ অনেক feature থাকলে owner এর প্রথম প্রশ্ন “আমার লাভ কী” হারিয়ে যেতে পারে | Hero থেকে product tour পর্যন্ত narrative রাখা হয়েছে। 375px ও 1440px এ hero CTA wrapping visual check করতে হবে |
| Features | capability list দীর্ঘ; feature কে business outcome ছাড়া দেখালে ভারী লাগে | group ও outcome copy ব্যবহার করা হয়েছে। card height সমান আছে কি না device এ দেখুন |
| Solutions | ব্যবসার ধরন ও বাস্তব ছবির সম্পর্ক পরিষ্কার, তবে photo crop ছোট screen এ মুখ বা কাজ কেটে দিতে পারে | `object-position` দিয়ে প্রতি image crop review করতে হবে |
| Solution detail | primary CTA ও consultation CTA পাশাপাশি; নতুন owner ভুল সিদ্ধান্ত নিতে পারে | primary action সবুজ, secondary outline। long title এ 320px wrapping verify করতে হবে |
| Pricing | বাস্তব দাম বা চুক্তির সীমা অস্পষ্ট হলে trust কমবে | “quote based” context দৃশ্যমান রাখুন; publish এর আগে package, VAT এবং support boundary legal review করুন |
| Security | security promise অতিরিক্ত হলে বিশ্বাসযোগ্যতা হারায় | honest limitations লেখা হয়েছে। compliance claim আইনগত অনুমোদন ছাড়া ব্যবহার করবেন না |
| About | বিশ্বাস তৈরির page, কিন্তু real team/customer proof না থাকলে generic লাগে | বাস্তব verified team photo, office address ও case study যোগ করা প্রয়োজন |
| Help | FAQ ভালো, কিন্তু support response time ও escalation route দরকার | support SLA, phone hours ও ticket status link যোগ করা বাকি |
| Guidelines | role selector mobile এ horizontal scroll | functionally safe, কিন্তু real device এ focus visibility ও last item reachability দেখতে হবে |
| Contact | contact channel এর পাশে প্রত্যাশিত response time না থাকলে owner uncertain থাকে | sales, support, emergency route আলাদা এবং response expectation যোগ করুন |
| Privacy and terms | dense legal copy mobile এ cognitive load বাড়ায় | section anchor, effective date, data controller contact এবং downloadable policy যোগ করা প্রয়োজন |
| Status | status label বাস্তব monitoring data ছাড়া ভুল trust signal হতে পারে | backend health source ছাড়া “live” status publish করবেন না |

## Authentication এবং onboarding audit

| পাতা | সমস্যা | করণীয় |
| --- | --- | --- |
| Login | password error, locked account, reset password, language help সব একই মুহূর্তে পরিষ্কার হওয়া চাই | inline error, show password, caps lock, reset journey এবং rate limit message visual test করুন |
| Signup | business type, branch, currency, consent, verification এর order নতুন user কে ক্লান্ত করতে পারে | দুই ধাপের progressive signup, saved progress ও verification explanation ব্যবহার করুন |
| Invite acceptance | expired invite ও already member case স্পষ্ট না হলে support load বাড়ে | deterministic status card এবং sign in CTA রাখা বাধ্যতামূলক |
| Business setup | setup checklist এর completion state জরুরি | per step save, owner role hint, sample data warning এবং “later” state visible করুন |

## Signed in application audit

| Screen group | ঝুঁকি | প্রয়োজনীয় visual verification |
| --- | --- | --- |
| Dashboard, overview, operational dashboard | dense KPI ভিড়ে সবচেয়ে জরুরি কাজ হারাতে পারে | empty, loading, error এবং 7 দিনের কম data state দেখতে হবে |
| POS, orders, sales history, returns | cashier দ্রুত কাজ করে; keyboard ও payment status সবচেয়ে গুরুত্বপূর্ণ | 1024px touchscreen, barcode entry, split payment, failed payment এবং refund state test করুন |
| Inventory, expiry, stock count, products | quantity mistake অর্থনৈতিক ক্ষতি করে | negative stock, serial batch, offline sync conflict এবং destructive confirmation check করুন |
| Purchases, reorder, supplier directory | approval ও expected delivery date চোখে পড়তে হবে | long supplier name, no supplier, partial GRN ও overdue PO test করুন |
| Cash, accounts, accounting, reports | টাকা ও ledger ভুল পড়া যাবে না | negative money colour শুধু colour নির্ভর নয়, export/print এবং reconciliation mismatch test করুন |
| CRM, customers, fulfilment | customer privacy ও order status স্পষ্ট হওয়া চাই | no contact permission, COD failure, rider handoff এবং duplicate customer test করুন |
| Workforce, staff | owner ও employee permission boundary | mobile attendance, leave collision, payroll draft এবং PII masking test করুন |
| AI, forecast, B SMART, strategy, what if | suggestion কে certainty মনে হতে পারে | confidence, evidence, data freshness, approval and “not enough data” state বাধ্যতামূলক |
| Audit, approvals, platform, settings, account | admin pages dense এবং sensitive | destructive action, empty audit, unauthorized view এবং long permission list test করুন |
| Import and upload | file error, column mapping ও undo unclear হলে data damage | sample download, row level errors, dry run, rollback and resumable import test করুন |
| Store, order status | public customer page কম তথ্য দেখাবে | mobile tracking, cancelled COD, invalid token এবং accessibility test করুন |

## ব্যবহারকারী হয়ে করা journey audit

| ব্যবহারকারী ও কাজ | user কী দেখবে বা করবে | আটকে যাওয়ার সম্ভাব্য জায়গা | release এর আগে pass condition |
| --- | --- | --- | --- |
| নতুন মালিক account খোলে | language, phone, business type, branch | কেন phone লাগে বা পরের ধাপে কী হবে অস্পষ্ট | প্রতিটি field এর label, example, error এবং progress visible |
| দোকানের ক্যাশিয়ার sale করে | product search, cart, tender, receipt | ধীর search, ছোট payment button, ভুল tender | keyboard ও barcode দিয়ে sale, failed payment থেকে recovery, 48px touch target |
| মালিক mobile এ রাতের হিসাব দেখে | sales, due, cash difference, action | chart দেখে কী করতে হবে বোঝে না | KPI এর সাথে plain Bangla insight ও একটি next action |
| storekeeper stock count করে | batch, counted quantity, variance | negative quantity বা duplicate scan | inline validation, save draft, conflict explanation, irreversible submit confirmation |
| rider COD handover করে | order, collection, proof | internet না থাকলে কাজ শেষ হয়েছে কি না বোঝে না | offline badge, queued sync status, duplicate proof prevention |
| HR leave approve করে | employee, leave balance, date overlap | balance বা salary impact গোপন | clear balance, conflict warning, approval audit trail |
| accountant reconciliation করে | bank/MFS statement, mismatch | শুধু red colour দেখে error বুঝতে হয় | text status, amount, source, proposed resolution এবং export |
| owner AI advice দেখে | prediction, evidence, approve or dismiss | advice কে নিশ্চিত ফল ভাবে | confidence, data date, evidence, consequence, human approval |
| customer order status দেখে | token link, COD status, delivery update | private order info leak বা invalid link | minimal information, expired/invalid state, support route |

## Fixed in this pass

1. Public mobile header এর meaningless plus CTA সরিয়ে readable action রাখা হয়েছে।
2. Public CTA এবং menu 48px touch target এ উন্নীত করা হয়েছে।
3. Coarse pointer device এ common internal compact controls 48px target পাবে।
4. Public demo তে চোখে কষ্ট দেয় এমন ক্ষুদ্র text বড় ও contrast বেশি করা হয়েছে।
5. Footer, image attribution, dark labels ও reduced motion behaviour উন্নত করা হয়েছে।
6. Product tour এর unsupported colour syntax এর জন্য fallback যোগ করা হয়েছে।

## প্রকাশের আগে বাধ্যতামূলক visual test matrix

1. Chrome Android: 320px, 360px, 390px, 412px wide
2. iPhone Safari: 375px ও 430px wide
3. Tablet: 768px portrait ও 1024px landscape
4. Desktop: 1280px ও 1440px
5. Keyboard only: tab, shift tab, enter, escape এবং visible focus
6. Zoom: 200 percent এবং browser text scale 130 percent
7. State: loading, empty, success, validation error, offline, permission denied, long Bengali name

## Release blocker

- কোনো page এ 320px horizontal scroll
- CTA icon মাত্র, label নেই
- error শুধু red colour দিয়ে বোঝানো
- AI recommendation কে নিশ্চিত ফল হিসেবে লেখা
- live payment, WhatsApp, SMS বা compliance claim credential ও contract ছাড়া প্রকাশ
- real customer data বা private contact consent ছাড়া UI তে দেখানো
