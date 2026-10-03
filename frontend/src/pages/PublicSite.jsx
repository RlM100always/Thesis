import { useEffect, useState } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../AuthContext";
import { useUi } from "../UiContext";
import Icon from "../ui/Icon";

// Platform-admin overrides — fetched once, cached module-wide.
// useSiteContent() returns { get(key, fallback), getJson(key, fallback), ...raw }
// get()     → raw[key] ?? fallback  (string/number)
// getJson() → raw[key] parsed as JSON, or fallback if absent/invalid
// Missing key = use hardcoded default; never blocks rendering.
let _siteContentCache = null;
let _siteContentCacheAt = 0;
let _siteContentPromise = null;
const SITE_CONTENT_TTL = 5 * 60 * 1000; // 5 minutes
function useSiteContent() {
  const [content, setContent] = useState(_siteContentCache || {});
  useEffect(() => {
    const stale = Date.now() - _siteContentCacheAt > SITE_CONTENT_TTL;
    if (_siteContentCache && !stale) return;
    if (!_siteContentPromise) {
      _siteContentCache = null;
      _siteContentPromise = api.publicSiteContent().then((r) => r.content || {}).catch(() => ({}));
    }
    _siteContentPromise.then((c) => { _siteContentCache = c; _siteContentCacheAt = Date.now(); _siteContentPromise = null; setContent(c); });
  }, []);
  const get = (key, fallback = "") => content[key] ?? fallback;
  const getJson = (key, fallback = null) => {
    const v = content[key];
    if (v == null) return fallback;
    if (Array.isArray(v) || (typeof v === "object" && v !== null)) return v;
    try { return JSON.parse(v); } catch { return fallback; }
  };
  return { ...content, get, getJson };
}

const NAV = [
  ["/features", "ফিচার"],
  ["/solutions", "ব্যবসার ধরন"],
  ["/pricing", "মূল্য পরিকল্পনা"],
  ["/security", "নিরাপত্তা"],
  ["/guidelines", "ব্যবহারবিধি"],
  ["/about", "আমাদের কথা"],
];

const SOLUTIONS = {
  pharmacy: { icon: "plus", title: "ফার্মেসি", tagline: "মেয়াদ দেখে আগে বিক্রি হয়, ভুল ওষুধ বিক্রি হবে না", capabilities: ["কোন ব্যাচ কবে আনা হয়েছে, মেয়াদ কবে শেষ হবে — সব মনে রাখে", "মেয়াদ কাছাকাছি এলে সেই ব্যাচ আগে বিক্রি করতে বলে", "মেয়াদ শেষ হওয়ার আগেই জানিয়ে দেয়, সাপ্লায়ারকে ফেরত দেওয়ার হিসাবও রাখে", "বক্স, পাতা বা এক পিস — যেভাবে বিক্রি করেন সেভাবেই হিসাব হয়"], status: "ফার্মেসির জন্য বিশেষভাবে তৈরি" },
  grocery: { icon: "cart", title: "মুদি ও সুপারশপ", tagline: "একাধিক কাউন্টার থাকলেও দ্রুত বিল করতে পারবেন", capabilities: ["বারকোড স্ক্যান করলেই দাম ও নাম উঠে আসে", "কাস্টমারকে লাইনে দাঁড় করাতে হয় না, এমন দ্রুতগতির বিল ব্যবস্থা", "মেয়াদ শেষ হয়ে নষ্ট হওয়া মাল আলাদা করে হিসাব রাখে", "প্রতিটা কাউন্টারের ক্যাশ আলাদাভাবে মিলিয়ে দেখা যায়"] },
  fashion: { icon: "tag", title: "ফ্যাশন ও বুটিক", tagline: "সাইজ, রং অনুযায়ী স্টক ও এক্সচেঞ্জ", capabilities: ["একই পোশাকের আলাদা সাইজ-রং আলাদাভাবে ট্র্যাক হয়", "কোন সিজনের কালেকশন কেমন বিক্রি হচ্ছে দেখুন", "এক্সচেঞ্জ করলে দামের পার্থক্য নিজেই হিসাব করে", "কোন সাইজ বেশি চলে সেটা বুঝে নতুন অর্ডার দিন"] },
  wholesale: { icon: "truck", title: "পাইকারি ও ডিস্ট্রিবিউশন", tagline: "বাকি, চালান ও কালেকশন এক জায়গায়", capabilities: ["কাস্টমার ভেদে আলাদা দামের তালিকা", "কার কত বাকি, কবে দেবে বলেছে — সব মনে রাখে", "মাল বাছাই, প্যাকিং ও ডেলিভারি চালান এক জায়গা থেকে", "সেলসম্যানের মাসিক টার্গেট ও অগ্রগতি দেখুন"] },
  restaurant: { icon: "card", title: "রেস্টুরেন্ট ও ক্যাফে", tagline: "টেবিল থেকে রান্নাঘর হয়ে বিল পর্যন্ত এক সুতায়", capabilities: ["বসে খাওয়া, পার্সেল বা হোম ডেলিভারি — সব অর্ডার এক জায়গায়", "রান্নাঘরে কোন টেবিলের কী অর্ডার এসেছে সাথে সাথে দেখা যায়", "কোন আইটেমে কত উপকরণ লাগে, তাই লাভ কত বুঝতে পারবেন", "বিল ভাগ করে দেওয়া ও হোম ডেলিভারি রাইডার ট্র্যাকিং"] },
  electronics: { icon: "zap", title: "ইলেকট্রনিক্স", tagline: "IMEI, ওয়ারেন্টি ও সার্ভিসিং একসাথে", capabilities: ["প্রতিটা ফোন/পণ্যের IMEI বা সিরিয়াল নম্বর ধরে রাখে", "ওয়ারেন্টির মেয়াদ ও বদলে দেওয়ার হিসাব", "সার্ভিসিংয়ে কোন পার্টস লাগলো তার জব কার্ড", "সাপ্লায়ারকে ত্রুটিপূর্ণ মাল ফেরত দেওয়ার হিসাব"] },
  service: { icon: "sliders", title: "সার্ভিস ও মেরামত", tagline: "মাল জমা নেওয়া থেকে ডেলিভারি পর্যন্ত পুরো হিসাব", capabilities: ["অ্যাপয়েন্টমেন্ট ও কাজের জব কার্ড", "কোন টেকনিশিয়ানকে কোন কাজ দেওয়া হলো", "খরচের এস্টিমেট কাস্টমারকে দেখিয়ে অনুমোদন নিন", "কাজ শেষে যাচাই করে বিল ও ওয়ারেন্টি দিন"] },
  manufacturing: { icon: "box", title: "ছোট কারখানা", tagline: "কাঁচামাল থেকে তৈরি পণ্য পর্যন্ত হিসাব", capabilities: ["একটা পণ্য বানাতে কী কী কাঁচামাল লাগে তার তালিকা", "কাঁচামাল বের করার ও উৎপাদনের হিসাব", "নষ্ট হওয়া মাল ও মান যাচাইয়ের রেকর্ড", "উৎপাদনে আসলে কত খরচ হলো তার হিসাব"] },
  salon: { icon: "calendar", title: "সেলুন ও বিউটি পার্লার", tagline: "বুকিং, প্যাকেজ ও স্টাফের কমিশন", capabilities: ["কর্মী ও চেয়ার অনুযায়ী বুকিং ক্যালেন্ডার", "প্যাকেজ ও মেম্বারশিপ অফার করুন", "কোন সার্ভিসে কতটুকু পণ্য খরচ হলো", "কর্মীর কমিশন হিসাব ও পরের অ্যাপয়েন্টমেন্ট মনে করিয়ে দেওয়া"] },
  education: { icon: "users", title: "কোচিং ও ট্রেনিং সেন্টার", tagline: "ব্যাচ, উপস্থিতি ও বেতন আদায়", capabilities: ["ছাত্র ও অভিভাবকের তথ্য এক জায়গায়", "কোর্স অনুযায়ী ব্যাচ তৈরি করুন", "প্রতিদিনের উপস্থিতি রাখুন", "মাসিক বেতনের ইনভয়েস ও বকেয়ার হিসাব"] },
  transport: { icon: "truck", title: "কুরিয়ার ও পরিবহন", tagline: "ট্রিপ, প্রমাণ ও ক্যাশ-অন-ডেলিভারি", capabilities: ["কোন পার্সেল কোন রুটে যাচ্ছে তার হিসাব", "রাইডার বা ড্রাইভারকে কাজ ভাগ করে দিন", "ডেলিভারি হয়েছে তার প্রমাণ ও ফেরত আসা পার্সেলের হিসাব", "ক্যাশ-অন-ডেলিভারির টাকা জমা দেওয়ার হিসাব"] },
  rental: { icon: "calendar", title: "ভাড়া ও ইভেন্ট", tagline: "কোনটা খালি আছে, জামানত ও ফেরত", capabilities: ["কোন জিনিস কবে খালি আছে তার ক্যালেন্ডার", "বুকিং ও জামানতের টাকা হিসাব", "নেওয়া ও ফেরত দেওয়ার সময় চেকলিস্ট মিলিয়ে দেখা", "ক্ষতি হলে বা দেরি হলে জরিমানার হিসাব"] },
};

const commonsImage = (file, width = 1600) => `https://commons.wikimedia.org/wiki/Special:Redirect/file/${encodeURIComponent(file)}?width=${width}`;

const REAL_WORK = {
  retail: {
    src: commonsImage("Shopkeeper in BD.jpg"),
    alt: "বাংলাদেশের স্থানীয় বাজারে পণ্য সাজিয়ে বসা একজন দোকানি",
    label: "দোকান ও মুদি ব্যবসা",
    detail: "বিক্রি, স্টক, বাকির হিসাব ও সাপ্লায়ারের কাছ থেকে কেনা",
    credit: "Masum-al-hasan · CC BY-SA 3.0",
    source: "https://commons.wikimedia.org/wiki/File:Shopkeeper_in_BD.jpg",
  },
  restaurant: {
    src: commonsImage("ঢাকার রেস্তোরাঁয় গরম গরম ডালপুরি ভাজা হচ্ছে.jpg"),
    alt: "ঢাকার একটি রেস্তোরাঁয় খাবার প্রস্তুতের বাস্তব দৃশ্য",
    label: "রেস্টুরেন্ট ও ক্যাফে",
    detail: "অর্ডার, রান্নাঘরের সারি, উপকরণের খরচ ও ডেলিভারি",
    credit: "Md. Fahamidul Islam Dipro · CC BY-SA 4.0",
    source: "https://commons.wikimedia.org/wiki/File:ঢাকার_রেস্তোরাঁয়_গরম_গরম_ডালপুরি_ভাজা_হচ্ছে.jpg",
  },
  manufacturing: {
    src: commonsImage("Garment factory in Dhaka.jpg"),
    alt: "ঢাকার একটি পোশাক কারখানায় উৎপাদনের বাস্তব দৃশ্য",
    label: "উৎপাদন",
    detail: "কাঁচামাল, চলমান কাজ, মান যাচাই, উৎপাদন ও খরচ",
    credit: "Wikimedia Commons · CC licensed",
    source: "https://commons.wikimedia.org/wiki/File:Garment_factory_in_Dhaka.jpg",
  },
  craft: {
    src: commonsImage("Workshop on handicraft, Sirajganj 15.JPG"),
    alt: "সিরাজগঞ্জের হস্তশিল্প কর্মশালায় কর্মরত উদ্যোক্তারা",
    label: "কারুশিল্প ও ছোট কারখানা",
    detail: "অর্ডার, উপকরণ, কারিগরের কাজ ও তৈরি পণ্য",
    credit: "Afifa Afrin · CC BY-SA 4.0",
    source: "https://commons.wikimedia.org/wiki/File:Workshop_on_handicraft,_Sirajganj_15.JPG",
  },
  service: {
    src: commonsImage("Craftsman Creating Designs on a Brass Bracket, Dhamrai, Savar, Bangladesh NK.JPG"),
    alt: "ধামরাইয়ে একজন কারিগরের দক্ষতার সঙ্গে কাজ করার দৃশ্য",
    label: "সার্ভিস ও ওয়ার্কশপ",
    detail: "কাজের কার্ড, খরচের হিসাব, যন্ত্রাংশ, কারিগর ও ডেলিভারি",
    credit: "Nasir Khan Saikat · CC BY-SA 3.0",
    source: "https://commons.wikimedia.org/wiki/File:Craftsman_Creating_Designs_on_a_Brass_Bracket,_Dhamrai,_Savar,_Bangladesh_NK.JPG",
  },
  electronics: {
    src: commonsImage("Ryans Computers IDB Branch Front View.jpg"),
    alt: "ঢাকার একটি প্রযুক্তিপণ্য বিক্রয়কেন্দ্রের বাস্তব দৃশ্য",
    label: "ইলেকট্রনিক্স ও প্রযুক্তিপণ্য",
    detail: "সিরিয়াল নম্বর, ওয়ারেন্টি, যন্ত্রাংশ ও মেরামত",
    credit: "Md Shuvo Sheikh · Wikimedia Commons",
    source: "https://commons.wikimedia.org/wiki/File:Ryans_Computers_IDB_Branch_Front_View.jpg",
  },
};

const SOLUTION_MEDIA = {
  pharmacy: "retail", grocery: "retail", fashion: "manufacturing", wholesale: "retail",
  restaurant: "restaurant", electronics: "electronics", service: "service", manufacturing: "manufacturing",
  salon: "service", education: "craft", transport: "retail", rental: "craft",
};

const CORE_FEATURES = [
  { icon: "cart", title: "বিক্রি ও অর্ডার", text: "দ্রুত বিল, কোটেশন, অর্ডার, রিটার্ন, ভাগে টাকা নেওয়া ও বাকি — সব একসাথে, আলাদা করে হিসাব রাখতে হয় না।" },
  { icon: "box", title: "স্টক ও ক্রয়", text: "কোন পণ্য কবে ঢুকলো, কবে বিক্রি হলো — সব হিসাব থাকে। গণনা, শাখা বদল, নতুন অর্ডার সব এক জায়গা থেকে।" },
  { icon: "truck", title: "রিজার্ভেশন ও ডেলিভারি", text: "অর্ডারের জন্য স্টক আলাদা করে রাখা, রাইডারকে কাজ দেওয়া, ডেলিভারি হয়েছে তার প্রমাণ, এবং ক্যাশ-অন-ডেলিভারির টাকা ক্যাশের হিসাবে সরাসরি যোগ হওয়া।" },
  { icon: "wallet", title: "ক্যাশ ও পেমেন্ট", text: "ক্যাশিয়ারের শিফট, bKash/Nagad/কার্ডের টাকা এখনো আসেনি এমন অবস্থা, এবং দিনশেষে হিসাব মেলানো।" },
  { icon: "fileText", title: "হিসাব ও মাস-শেষ", text: "কার কাছে পাওনা, কাকে দেনা, লাভ-ক্ষতি — সব হিসাব স্বয়ংক্রিয়ভাবে তৈরি হয়। মাস শেষ হলে সেই মাসের হিসাব লক করে দিতে পারবেন, পরে কেউ ভুলেও বদলাতে পারবে না।" },
  { icon: "users", title: "কর্মী ও বেতন", text: "উপস্থিতি, ছুটি, ডিউটি রোস্টার, কমিশন, অগ্রিম টাকা এবং বেতন — একজন বানায়, আরেকজন অনুমোদন দেয়, তাই ভুল বা কারচুপির সুযোগ কম।" },
  { icon: "userCheck", title: "কাস্টমার সম্পর্ক ও সার্ভিস", text: "সম্ভাব্য কাস্টমার, অভিযোগ, মতামত এবং একজন কাস্টমারের সব কেনাকাটার ইতিহাস এক জায়গায়।" },
  { icon: "check", title: "অনুমোদন ও কার কাজ কখন", text: "বেশি ছাড়, রিফান্ড, বড় ক্রয় বা খরচ — মালিকের অনুমোদন ছাড়া হবে না। কে কখন কী করেছে সব লেখা থাকে, মুছে ফেলা যায় না।" },
  { icon: "zap", title: "কারণ-সহ পরামর্শ (B-SMART)", text: "কোন পণ্য আবার কিনবেন, কার মেয়াদ ফুরাচ্ছে, কোন কাস্টমার হারাতে বসেছেন — শুধু পরামর্শ না, কেন এই পরামর্শ সেই কারণটাও দেখায়। শেষ সিদ্ধান্ত সবসময় আপনার।" },
  { icon: "pie", title: "ব্যবসার স্বাস্থ্য ও আজকের কাজ", text: "ক্যাশ, স্টক, বিক্রি, কাস্টমার — কোনটা ভালো আছে কোনটা ঝুঁকিতে, এক নজরে দেখুন। আজকে সবচেয়ে জরুরি কোন কাজটা করা দরকার তার তালিকাও থাকে।" },
];

const OWNER_PROBLEMS = [
  { icon: "wallet", question: "বিক্রি হচ্ছে, কিন্তু হাতে টাকা থাকছে না?", answer: "ক্যাশ, bKash/Nagad, কার্ড, বাকি, খরচ ও ডেলিভারির টাকা আলাদা করে মিলিয়ে দেখুন কোথায় ফাঁক হচ্ছে।", path: "ক্যাশ মেলান + হিসাব মিলানো", actor: "মালিক · ক্যাশিয়ার · হিসাবরক্ষক" },
  { icon: "box", question: "খাতার স্টক আর দোকানের স্টক মেলে না?", answer: "বিক্রি, ক্রয়, রিটার্ন, শাখা বদল, নষ্ট হওয়া মাল ও গণনা — প্রতিটা বদলের উৎস ধরে পার্থক্য খুঁজে বের করুন।", path: "স্টকের ইতিহাস + গণনা মিলানো", actor: "ম্যানেজার · স্টোরকিপার" },
  { icon: "truck", question: "কখন, কত এবং কার কাছ থেকে মাল কিনবেন?", answer: "বিক্রির গতি, হাতে থাকা স্টক, সাপ্লায়ারের মাল দিতে কতদিন লাগে ও বাজেট দেখে কেনার তালিকা পান।", path: "কী কিনবেন + ক্রয় অর্ডার", actor: "মালিক · ক্রয় বিভাগ" },
  { icon: "users", question: "কর্মী কী করছে বুঝতে সারাদিন দোকানে থাকতে হয়?", answer: "যার যা কাজ, কার শিফট চলছে, কী অনুমোদনের অপেক্ষায় আছে, ডেলিভারির প্রমাণ — সব এক জায়গা থেকে মালিক দেখতে পারেন।", path: "আজকের করণীয়", actor: "মালিক · ম্যানেজার · স্টাফ" },
];

const AI_DECISIONS = [
  { icon: "box", title: "কী কিনবেন তার পরামর্শ", data: "বিক্রির গতি + হাতের স্টক + সাপ্লায়ারের সময় + মৌসুম", output: "কোন পণ্য কত কিনবেন, কতটা নিশ্চিত এবং কারণ সহ" },
  { icon: "alert", title: "অস্বাভাবিক কিছু হলে সতর্কতা", data: "বাতিল বিল + রিফান্ড + ছাড় + গণনার গরমিল + শিফট", output: "কোথায় কিছু ঠিক নেই মনে হচ্ছে, সম্ভাব্য কারণ ও যাচাই করার কাজ" },
  { icon: "users", title: "কোন কাস্টমারকে কী করবেন", data: "কতদিন আসেনি + কত বাকি + কত কেনে + যোগাযোগের অনুমতি আছে কিনা", output: "কাকে বাকি আদায়ের কল দেবেন, কাকে ফিরিয়ে আনতে অফার দেবেন" },
  { icon: "wallet", title: "সামনে টাকার অবস্থা কেমন হবে", data: "পাওনা + দেনা + খরচ + কেনার পরিকল্পনা", output: "কবে টাকার টান পড়তে পারে, কী করে সামলাবেন" },
  { icon: "tag", title: "মেয়াদ ফুরানো মাল নিয়ে করণীয়", data: "ব্যাচের বয়স + চাহিদা + লাভ + সাপ্লায়ারের শর্ত", output: "শাখা বদল করবেন, ছাড় দেবেন, ফেরত দেবেন নাকি বিক্রিই করে ফেলবেন" },
  { icon: "target", title: "আজকের সবচেয়ে জরুরি কাজ", data: "সব বিভাগের ঝুঁকি + প্রভাব + সময়সীমা একসাথে দেখে", output: "আজকে মালিক নিজে কোন সিদ্ধান্তগুলো নেবেন তার তালিকা" },
];

const BANGLADESH_READY = [
  { icon: "wallet", title: "ক্যাশ, bKash/Nagad, কার্ড ও COD", text: "একটা বিক্রিতে একাধিক মাধ্যমে টাকা নিতে পারেন। bKash/Nagad-এর টাকা এখনো কনফার্ম হয়নি, বা রাইডার থেকে COD-র টাকা এখনো জমা হয়নি — এই অবস্থাগুলো স্পষ্ট দেখায়, লুকিয়ে রাখে না।" },
  { icon: "tag", title: "আপনার দোকানের মতোই একক ও প্যাকেট", text: "পিস, বক্স, পাতা, কার্টন, কেজি বা লিটার — যেভাবে কেনেন আর যেভাবে বিক্রি করেন, দুটো আলাদা একক হলেও হিসাব নিজে থেকেই মিলিয়ে দেয়।" },
  { icon: "users", title: "বাকি ও সম্পর্কের ব্যবসা", text: "কোন কাস্টমারের কত বাকি, কতদিনের পুরোনো, কবে দেবে বলেছিল, এবং আপনি নিজে সাপ্লায়ারকে কত দেনা — সব একই জায়গায়।" },
  { icon: "refresh", title: "ইন্টারনেট চলে গেলেও কাজ বন্ধ হবে না", text: "ইন্টারনেট না থাকলেও বিক্রি বন্ধ হয় না, হিসাব জমা থেকে যায় এবং নেট ফিরলে নিজে থেকেই মিলে যায়। কোনো কিছু 'হয়ে গেছে' বলে মিথ্যা দেখানো হয় না — যতক্ষণ না আসলেই নিশ্চিত হয়।" },
  { icon: "fileText", title: "সহজ বাংলা, হিসাবে কোনো ফাঁকি নেই", text: "দৈনন্দিন কাজ পুরোটাই সহজ বাংলায়। প্রতিটা বিল, স্টক বদল, অনুমোদন ও সংশোধন কোথা থেকে এলো তার প্রমাণ খুঁজে বের করা যায়।" },
  { icon: "box", title: "এক দোকান থেকে একাধিক শাখা পর্যন্ত", text: "একটা দোকান দিয়ে শুরু করুন, পরে একাধিক কাউন্টার, গুদাম এবং শাখা যোগ করলেও মালিক হিসেবে সব এক জায়গা থেকে দেখতে পারবেন।" },
];

const PRODUCT_TOUR = [
  { id: "pos", icon: "cart", tab: "দ্রুত বিক্রি", kicker: "কাউন্টারের কাজ", title: "স্ক্যান থেকে রসিদ পর্যন্ত এক জায়গায়", text: "কাস্টমার বাছাই, ছাড় দেওয়ার অনুমতি, ক্যাশ/bKash/কার্ড/বাকি এবং রিটার্নের নিয়ম — সব একই বিক্রির মধ্যে।", metric: "৩ ধাপে বিক্রি শেষ", points: ["বারকোড স্ক্যান করে পণ্য খোঁজা", "ভাগে ভাগে টাকা নেওয়া ও বাকি রাখা", "সার্ভার-নিশ্চিত রসিদ, ভুল হিসাব নেই"], accent: "mint" },
  { id: "stock", icon: "box", tab: "স্টকের সত্য হিসাব", kicker: "স্টক নিয়ন্ত্রণ", title: "কত আছে এবং কেন বদলেছে — দুটোই দেখুন", text: "ক্রয়, বিক্রি, শাখা বদল, রিটার্ন, নষ্ট হওয়া মাল ও গণনা — প্রতিটা বদল কোথা থেকে এলো তার প্রমাণ সহ।", metric: "প্রতিটা বদলের প্রমাণ থাকে", points: ["ব্যাচ, সিরিয়াল ও মেয়াদ ট্র্যাকিং", "নিজে গুনে মিলিয়ে দেখা (গণনার সময় আগের সংখ্যা দেখায় না)", "নতুন অর্ডার ও সাপ্লায়ার দাবি"], accent: "blue" },
  { id: "cash", icon: "wallet", tab: "টাকার মিল", kicker: "ক্যাশের হিসাব", title: "ক্যাশ, bKash, কার্ড ও COD একসাথে মেলান", text: "শিফট শুরুর ক্যাশ থেকে শেষের গণনা পর্যন্ত — হিসাব আর হাতের টাকার পার্থক্য, কারণ ও অনুমোদন সব দেখা যায়।", metric: "প্রতিটা মাধ্যম আলাদা করে মেলে", points: ["ক্যাশিয়ারের নিজের শিফটের দায়িত্ব", "bKash/Nagad এখনো কনফার্ম হয়নি এমন অবস্থা দেখা যায়", "COD-র টাকা জমা দেওয়ার প্রমাণ"], accent: "amber" },
  { id: "ai", icon: "zap", tab: "AI পরামর্শ", kicker: "কারণ-সহ বুদ্ধিমত্তা", title: "কী করবেন, কেন করবেন আর তাতে কী হবে", text: "শুধু একটা সংখ্যা বা পূর্বাভাস না — কোন তথ্যের ভিত্তিতে এই পরামর্শ, কতটা নিশ্চিত এবং আপনি কী সিদ্ধান্ত নিলেন সব এক কার্ডে।", metric: "সিদ্ধান্ত সবসময় আপনার হাতে", points: ["বিক্রির ধরন অনুযায়ী নতুন অর্ডারের পরামর্শ", "ক্ষতির ঝুঁকি থাকলে আগেই সংকেত", "পরামর্শ অনুযায়ী কাজ করলে ফলাফল কেমন হলো তার হিসাব"], accent: "violet" },
];

const TRUST = [
  ["shield", "প্রতিটা ব্যবসার তথ্য আলাদা ও সুরক্ষিত", "আপনার ব্যবসার তথ্য অন্য কোনো ব্যবসা দেখতে পারবে না। প্রতিটা কর্মীও শুধু নিজের ভূমিকা অনুযায়ী যতটুকু দেখার কথা ততটুকুই দেখবে — সার্ভারে যাচাই করা হয়, শুধু বোতাম লুকিয়ে না।"],
  ["key", "লগইন সেশন ও দুই-ধাপের নিরাপত্তা", "অন্য ডিভাইস থেকে লগআউট করে দেওয়া যায়, চাইলে ফোনের অ্যাপ দিয়ে দুই-ধাপে লগইন চালু করতে পারবেন, আর গুরুত্বপূর্ণ কাজের আগে আবার পাসওয়ার্ড চাওয়া হয়।"],
  ["fileText", "হিসাব মুছে ফেলা যায় না, শুধু সংশোধন করা যায়", "একবার বিক্রি বা স্টকের হিসাব জমা হয়ে গেলে সেটা মুছে ফেলা যায় না — ভুল হলে উল্টো এন্ট্রি দিয়ে ঠিক করতে হয়, তাই কে কী করেছে সবসময় বোঝা যায়।"],
  ["refresh", "কোনো কিছু আটকে গেলেও তথ্য হারাবে না", "একই বিল দুইবার জমা হবে না, ইন্টারনেট চলে গেলেও আগের কাজ হারাবে না, এবং bKash/Nagad থেকে উত্তর দেরি হলে সেই অবস্থাও স্পষ্ট দেখা যায়।"],
];

const FAQ = [
  ["আমার কম্পিউটার জানা নেই, আমি কি চালাতে পারব?", "হ্যাঁ। B-SMART সাধারণ মোবাইল ফোন বা ট্যাবলেট থেকেই চালানো যায়। আলাদা কম্পিউটার লাগবে না। প্রতিটি বোতাম বাংলায় লেখা, এবং প্রথম তিনটি বিক্রি করার সময় ধাপে ধাপে দেখিয়ে দেওয়া হয়।"],
  ["আমার স্টাফ ইংরেজি পড়তে পারে না, সমস্যা হবে?", "না। ব্যবসা মোডের বিক্রি, স্টক, হিসাব ও কর্মীর পুরো দৈনিক কাজ সম্পূর্ণ বাংলায়। শুধু গবেষণার জন্য কিছু প্রযুক্তিগত পাতা ইংরেজিতে, যেটা মালিক ছাড়া কারও দেখার দরকার নেই।"],
  ["আমার দোকানে বার বার ইন্টারনেট চলে যায়, তাহলে?", "ক্যাশে বিক্রি, স্টক গণনা বা ডেলিভারি আপডেট — ইন্টারনেট না থাকলেও জমা থাকে, বিক্রি বন্ধ হয় না। ইন্টারনেট ফিরলেই নিজে থেকে মিলে যায়। ততক্ষণ রসিদে স্পষ্ট লেখা থাকে 'এখনো পাঠানো বাকি', যাতে মিথ্যা করে 'হয়ে গেছে' না দেখায়।"],
  ["আমি এখন খাতায় হিসাব রাখি। পুরোনো হিসাব কীভাবে আনব?", "শুরুর সময় একবার বর্তমান বাকি, স্টক ও হাতের ক্যাশ 'শুরুর হিসাব' হিসেবে নিজে মিলিয়ে ঢুকিয়ে দিতে পারবেন। এরপর থেকে প্রতিটা নতুন লেনদেন সিস্টেম নিজেই হিসাবে যোগ করবে।"],
  ["এটা কি শুধু ফার্মেসির জন্য?", "না। বিক্রি, স্টক, ক্রয়, হিসাব, কাস্টমার, কর্মী ও ডেলিভারি — এই মূল কাজগুলো সব ধরনের ব্যবসার জন্যই এক। শুধু ব্যবসার ধরন অনুযায়ী (ফার্মেসি, মুদি, রেস্টুরেন্ট ইত্যাদি) কিছু বিশেষ অংশ আলাদাভাবে চালু হয়।"],
  ["bKash, Nagad বা কার্ড কি সরাসরি কাজ করবে?", "আসল টাকা লেনদেনের জন্য আপনার নিজের bKash/Nagad মার্চেন্ট অ্যাকাউন্ট লাগবে। সেটা যুক্ত না করা পর্যন্ত সিস্টেম শুধু পরীক্ষা করে দেখাবে, মিথ্যা করে 'সফল হয়েছে' কখনো দেখাবে না।"],
  ["একজন কর্মী কি একাধিক শাখায় বা ব্যবসায় কাজ করতে পারে?", "হ্যাঁ। একটা লগইন দিয়ে একাধিক ব্যবসায় যুক্ত থাকতে পারেন, প্রতিটায় আলাদা ভূমিকা নিয়ে। প্রতিটা ব্যবসার তথ্য ও অনুমতি সম্পূর্ণ আলাদা থাকে, একটার তথ্য আরেকটায় দেখা যায় না।"],
  ["মূল্য কত?", "শাখা, কতজন ব্যবহার করবেন এবং কোন কোন সুবিধা চালু রাখবেন তার উপর দাম নির্ভর করবে। এখনো চূড়ান্ত দামের তালিকা ঠিক হয়নি বলে এখানে কাল্পনিক কোনো ফি দেখানো হয়নি।"],
];

const BEFORE_AFTER = [
  ["খাতায় লিখে হিসাব, ভুল হলে কাটাকাটি", "প্রতিটি বিক্রি সঙ্গে সঙ্গে স্টক, ক্যাশ ও হিসাবে যোগ হয়। ভুল হলে reverse entry হয়, খাতা ছেঁড়া লাগে না"],
  ["স্টক কত আছে বুঝতে গুনে দেখতে হয়", "যেকোনো সময় স্ক্রিনে দেখুন কোনটা কত আছে, কোনটা ফুরিয়ে যাচ্ছে"],
  ["কে কত বাকি দিল মনে রাখা কঠিন", "প্রতিটি কাস্টমারের বাকি, কবেকার এবং কত পুরোনো সব এক তালিকায়"],
  ["কর্মী কী করল সারাদিন বোঝা যায় না", "প্রতিটি কাজ কে করল এবং কখন করল সব audit এ থেকে যায়"],
  ["মাস শেষে লাভ ও ক্ষতি বসে হিসাব করতে হয়", "যেকোনো দিনের লাভ ও ক্ষতি সঙ্গে সঙ্গে দেখুন, উৎস পর্যন্ত যাচাই করে"],
];

const ROLE_GUIDES = [
  { id: "owner", icon: "target", name: "মালিক", start: "ড্যাশবোর্ড", goal: "পুরো ব্যবসার স্বাস্থ্য, ঝুঁকি ও বড় সিদ্ধান্ত নিজের নিয়ন্ত্রণে রাখা", steps: [
    ["সকালে প্রথম কাজ", "ড্যাশবোর্ড → আজকের করণীয়", "হাতে কত টাকা আছে, কী অনুমোদনের অপেক্ষায়, কোন পণ্য কমে যাচ্ছে আর কোন শাখায় সমস্যা — সব এক জায়গায় দেখুন।"],
    ["অনুমোদন দিন", "অনুমোদন → অপেক্ষমাণ", "কত টাকার অনুরোধ, কে চেয়েছে, কেন চেয়েছে — দেখে অনুমোদন দিন বা না করুন।"],
    ["ব্যবসা যাচাই করুন", "রিপোর্ট / আর্থিক প্রতিবেদন", "যেকোনো সংখ্যায় ক্লিক করে সেটার পেছনের আসল বিল, স্টক বদল বা হিসাব পর্যন্ত দেখে নিন।"],
    ["দিনের শেষে", "ক্যাশ মেলান", "ক্যাশ/bKash/কার্ড/COD-র হিসাব মিলেছে কিনা, না মিললে কারণ কী — যাচাই করুন।"],
  ], features: ["সার্বিক ড্যাশবোর্ড", "অনুমোদনের নিয়ম ঠিক করা", "শাখাওয়ারি তুলনা", "নিরাপত্তা ও সেটিংস", "B-SMART সিদ্ধান্ত"] },
  { id: "manager", icon: "sliders", name: "ম্যানেজার", start: "অপারেশন ড্যাশবোর্ড", goal: "নিজের শাখার দৈনিক সমস্যা সামলানো ও টিমকে কাজ বুঝিয়ে দেওয়া", steps: [
    ["শুরু করুন", "ড্যাশবোর্ড → শাখার অবস্থা", "কোন শিফট চলছে, কর্মী কারা আছে, অর্ডার ও ডেলিভারি কী অবস্থায় দেখুন।"],
    ["সমস্যা সমাধান", "আমার কাজ / অনুমোদন", "বেশি ছাড়, রিফান্ড, গণনার গরমিল বা ডেলিভারির সমস্যা নিয়মমাফিক সমাধান করুন।"],
    ["কাজ ভাগ করুন", "স্টক / ডেলিভারি / কর্মী", "গণনা, শাখা বদল বা রাইডারের কাজ যার যার দায়িত্বে দিন।"],
    ["দিন শেষ করুন", "ক্যাশ মেলান", "কোথাও গরমিল থাকলে কারণ দেখে মালিকের কাছে পাঠান বা নিজেই বন্ধ করুন।"],
  ], features: ["শাখার ড্যাশবোর্ড", "দৈনিক কাজের অনুমোদন", "কাজ ভাগ করে দেওয়া", "স্টক ও ডেলিভারি নিয়ন্ত্রণ", "শাখার রিপোর্ট"] },
  { id: "cashier", icon: "cart", name: "ক্যাশিয়ার", start: "ক্যাশিয়ার ড্যাশবোর্ড / বিক্রি", goal: "দ্রুত ও সঠিকভাবে বিক্রি করা, নিজের শিফটের ক্যাশের হিসাব রাখা", steps: [
    ["শিফট শুরু করুন", "ক্যাশ মেলান → শিফট খুলুন", "কাউন্টার ঠিক করে হাতে কত টাকা নিয়ে শুরু করছেন তা গুনে লিখুন।"],
    ["বিক্রি করুন", "বিক্রি → স্ক্যান/খুঁজুন", "পণ্য, কাস্টমার, ছাড় ও কীভাবে টাকা নিচ্ছেন দিয়ে বিক্রি সম্পন্ন করুন।"],
    ["রসিদ দিন", "বিক্রি শেষ → রসিদ", "চূড়ান্ত বিল নম্বর পাওয়ার পর প্রিন্ট বা শেয়ার করুন।"],
    ["শিফট বন্ধ করুন", "শিফট → গণনা", "হাতে যা আছে গুনে লিখুন (আগের হিসাব দেখানো হয় না); না মিললে কারণ লিখতে হবে, ম্যানেজার যাচাই করবেন।"],
  ], features: ["বিক্রির পাতা (POS)", "হোল্ড করা বিল", "কাস্টমার খোঁজা", "নিজের শিফট", "রসিদ ও অনুমতি-সাপেক্ষ রিটার্ন"] },
  { id: "stock", icon: "box", name: "স্টোরকিপার", start: "স্টক ড্যাশবোর্ড", goal: "দোকানের আসল মাল আর সিস্টেমের হিসাব সবসময় এক রাখা", steps: [
    ["মাল গ্রহণ করুন", "ক্রয় → মাল গ্রহণ", "অর্ডার করা পরিমাণ, ব্যাচ/মেয়াদ/সিরিয়াল মিলিয়ে কতটুকু ভালো আর কতটুকু ফেরতযোগ্য তা লিখুন।"],
    ["জায়গামতো রাখুন", "স্টক → গুছিয়ে রাখা", "কোন মাল কোথায় রাখলেন তা নিশ্চিত করুন।"],
    ["গণনা করুন", "স্টক গণনা", "নিজে গুনে জমা দিন (সিস্টেমের আগের সংখ্যা দেখা যায় না, তাই সত্যিকার গণনা হয়); গরমিল নিজে ঠিক করবেন না, ম্যানেজারের কাছে যাবে।"],
    ["শাখা বদল করুন", "স্টক → শাখা বদল", "পাঠানো ও গ্রহণ করা — দুই ধাপেই আলাদাভাবে মিলিয়ে নিশ্চিত করুন।"],
  ], features: ["মাল গ্রহণ ও যাচাই", "স্টকের ইতিহাস", "ব্যাচ ও সিরিয়াল", "গণনা", "শাখা বদল ও আটকে রাখা"] },
  { id: "procurement", icon: "truck", name: "ক্রয় বিভাগ", start: "ক্রয় ড্যাশবোর্ড", goal: "সঠিক সাপ্লায়ার থেকে সঠিক পরিমাণ ও দামে সময়মতো কেনা", steps: [
    ["প্রয়োজন যাচাই", "কী কিনবেন", "স্টক, বিক্রির গতি, সাপ্লায়ারের সময় ও বাজেট দেখুন।"],
    ["দাম তুলনা করুন", "সাপ্লায়ার তুলনা", "কে কত দামে, কত দ্রুত দিতে পারবে তুলনা করুন।"],
    ["অর্ডার দিন", "ক্রয় → নতুন অর্ডার", "খসড়া বানিয়ে জমা দিন; অনুমোদন পেলে সাপ্লায়ারকে পাঠান।"],
    ["খোঁজ রাখুন", "ক্রয় অর্ডার / দাবি", "দেরি বা আংশিক মাল এলে এবং ত্রুটিপূর্ণ মাল ফেরত দেওয়ার হিসাব রাখুন।"],
  ], features: ["কী কিনবেন তার পরামর্শ", "চাহিদাপত্র/দাম-তুলনা", "ক্রয় অর্ডার", "সাপ্লায়ারের কাছে দাবি", "সাপ্লায়ারের পারফরম্যান্স"] },
  { id: "accountant", icon: "wallet", name: "হিসাবরক্ষক", start: "হিসাব ড্যাশবোর্ড", goal: "ক্যাশ, বাকি-দেনা ও হিসাবের খাতা মিলিয়ে রাখা", steps: [
    ["গরমিল আগে দেখুন", "হিসাব মিলানো", "ক্যাশ/bKash/কার্ড/ব্যাংক/COD-এ যা মেলেনি তা আগে সমাধান করুন।"],
    ["বাকি-দেনা", "হিসাব → পাওনা/দেনা", "কোন টাকা কোন বিলের বিপরীতে জমা হলো তা মিলিয়ে দিন।"],
    ["খাতা যাচাই", "আর্থিক প্রতিবেদন", "প্রতিটা হিসাবের উৎস ও সার্বিক আর্থিক অবস্থা যাচাই করুন।"],
    ["মাস বন্ধ করুন", "মাস-শেষের তালিকা", "সব ধাপ শেষ করে মালিকের অনুমোদনের জন্য সেই মাসের হিসাব জমা দিন।"],
  ], features: ["হিসাব মিলানো", "পাওনা/দেনা", "খরচ", "সাধারণ খাতা", "আর্থিক প্রতিবেদন"] },
  { id: "hr", icon: "userCheck", name: "এইচআর / অ্যাডমিন", start: "কর্মী ড্যাশবোর্ড", goal: "কর্মী নিয়োগ, উপস্থিতি, ছুটি ও বেতনের তথ্য প্রস্তুত রাখা", steps: [
    ["কর্মী তালিকা", "কর্মী ও ভূমিকা", "নতুন কর্মী যোগ করা, শাখা ঠিক করা ও ভূমিকা বদলানো।"],
    ["দৈনিক", "উপস্থিতি / রোস্টার", "কে আসেনি, কে দেরি করেছে, ডিউটিতে ফাঁক আছে কিনা দেখুন।"],
    ["ছুটি", "ছুটির আবেদন", "বাকি ছুটি, একসাথে অনেকে চাইলে এবং বদলি কর্মী দেখে অনুমোদন দিন।"],
    ["বেতন", "বেতনের খসড়া", "উপস্থিতি, কমিশন, অগ্রিম টাকা ও কর্তন মিলিয়ে বেতনের হিসাব যাচাই করুন।"],
  ], features: ["কর্মীর তালিকা", "ডিউটি রোস্টার", "উপস্থিতি", "ছুটি", "বেতন প্রস্তুত করা"] },
  { id: "field", icon: "truck", name: "রাইডার / টেকনিশিয়ান", start: "আমার কাজ", goal: "ফোন থেকেই নিজের ডেলিভারি বা কাজ প্রমাণসহ শেষ করা", steps: [
    ["কাজ দেখুন", "আমার কাজ", "শুধু নিজের রুট বা কাজ এবং কোনটা আগে করতে হবে তা দেখুন।"],
    ["কাজ করুন", "ডেলিভারি / জব কার্ড", "স্ক্যান করুন, অবস্থা জানান, প্রয়োজনে ছবি বা প্রমাণ দিন।"],
    ["সমস্যা হলে", "ব্যর্থ / অপেক্ষমাণ", "কারণ ও প্রমাণ দিয়ে ম্যানেজারকে জানান, পরবর্তী সিদ্ধান্ত তার হাতে।"],
    ["টাকা বা মাল বুঝিয়ে দিন", "COD / কাজ সম্পন্ন", "নগদ টাকা বা সম্পন্ন কাজ দুই পক্ষ নিশ্চিত করার পরেই জমা হিসাবে যোগ হবে।"],
  ], features: ["নিজের কাজের তালিকা", "অফলাইনেও আপডেট", "ছবি/প্রমাণ জমা দেওয়া", "COD/পার্টস বুঝিয়ে দেওয়া", "সমস্যা হলে ম্যানেজারকে জানানো"] },
];

// ── Default constants for admin-editable sections ──────────────────────────
const FLOW_ITEMS_DEFAULT = [
  ["cart","বিক্রি","বিল ও কাস্টমার"],["box","স্টক","কমলো বা বাড়লো"],
  ["wallet","টাকা","নগদ অথবা বাকি"],["fileText","হিসাব","খাতা মিলে যায়"],
  ["pie","ফলাফল","প্রমাণসহ পরামর্শ"],
];
const GETTING_STARTED_STEPS_DEFAULT = [
  ["নিজের অ্যাকাউন্ট","মোবাইল/ইমেইল, পাসওয়ার্ড ও ব্যবসার পরিচয়"],
  ["ব্যবসার তথ্য","শাখা, কাউন্টার, গুদাম ও ব্যবসার ধরন"],
  ["শুরুর হিসাব","পণ্য, স্টক, কাস্টমারের বাকি, সাপ্লায়ারের দেনা ও হাতের ক্যাশ"],
  ["টিম নিয়ে শুরু","কর্মী যোগ করা, ভূমিকা ঠিক করা ও একবার পরীক্ষা করে যাচাই"],
];
const CUSTOMER_QUESTIONS_DEFAULT = [
  ["কোন মাল আজই কিনতে হবে?","স্টক + বিক্রি + সাপ্লায়ার","কতদিনের স্টক আছে, সাপ্লায়ারের সময় কত আর বাজেটে কত কেনা যাবে — কারণসহ দেখুন।","ক্রয় বিভাগ"],
  ["ক্যাশ কম দেখাচ্ছে কেন?","শিফট + পেমেন্ট + রিফান্ড","শুরুর ক্যাশ, বিক্রি, রিফান্ড ও COD মিলিয়ে কোথায় পার্থক্য হয়েছে তার প্রমাণ।","ক্যাশিয়ার → ম্যানেজার"],
  ["কার কাছে বাকি, আজ কাকে বলব?","বিল + বয়স + প্রতিশ্রুতি","কত বাকি, কতদিনের পুরোনো আর আগে কী বলেছিল — আজকের কল করার তালিকা।","সেলস / হিসাবরক্ষক"],
  ["রাইডার টাকা জমা দিয়েছে কি?","ডেলিভারি + COD","ডেলিভারি হওয়া অর্ডার আর আসলে হাতে টাকা আসা — আলাদা করে দেখায়, কোনটা বাকি তাও বলে।","রাইডার → ক্যাশিয়ার"],
  ["কোন স্টকে গরমিলের ঝুঁকি বেশি?","বদল + গণনা + সংঘাত","অনেকবার সংশোধন হয়েছে বা অনেকদিন গোনা হয়নি এমন পণ্য আগে গণনার তালিকায় আসবে।","স্টোরকিপার"],
  ["আজ মালিক হিসেবে আমার কাজ কী?","অনুমোদন + ঝুঁকি + সময়সীমা","সব জায়গা থেকে শুধু গুরুত্বপূর্ণ সিদ্ধান্তগুলো বেছে আজকের করণীয় তালিকা।","মালিক"],
];
const ACTOR_ITEMS_DEFAULT = [
  ["userCheck","মালিক","ক্যাশ, ব্যবসার অবস্থা, ঝুঁকি ও অনুমোদন"],
  ["sliders","ম্যানেজার","শাখার দৈনিক কাজ ও সমস্যা সমাধান"],
  ["cart","ক্যাশিয়ার","শিফট, বিক্রি ও রসিদ"],
  ["box","স্টোরকিপার","মাল গ্রহণ, গণনা ও শাখা বদল"],
  ["wallet","হিসাবরক্ষক","বাকি-দেনা, মিলানো ও মাস বন্ধ করা"],
  ["truck","রাইডার","রুট, প্রমাণ ও COD"],
];
const PREVIEW_STATS_DEFAULT = [
  {label:"আজকের বিক্রি",value:"৳ ৮৪,৬৫০",note:"গত বুধবারের চেয়ে ১২% বেশি"},
  {label:"হাতে ক্যাশ",value:"৳ ৩২,৪০০",note:"২টি shift চলছে"},
  {label:"আদায়যোগ্য বাকি",value:"৳ ১,১৮,২০০",note:"আজ promise ৪টি"},
];
const PREVIEW_MISSION_DEFAULT = ["PO-234 অনুমোদন","২টি payment যাচাই","Expiry claim পাঠান"];
const PRIVACY_SECTIONS_DEFAULT = [
  {heading:"কী তথ্য লাগে",body:"আপনার অ্যাকাউন্টের তথ্য, ব্যবসার সদস্যপদ, বিক্রি-ক্রয়ের লেনদেন, এবং কাজের জন্য প্রয়োজনীয় কাস্টমার-সাপ্লায়ার-কর্মীর তথ্য। পাসওয়ার্ড খোলামেলা, OTP বা কার্ডের পুরো তথ্য কখনো সংরক্ষণ বা AI-কে দেখানো হয় না।"},
  {heading:"কেন ব্যবহার হয়",body:"লগইন, বিক্রি-ক্রয়-স্টক-হিসাবের কাজ, কাস্টমার সার্ভিস, নিরাপত্তা, ব্যাকআপ, রিপোর্ট এবং আপনার অনুমতি নিয়ে বিশ্লেষণের জন্য।"},
  {heading:"কে দেখতে পারে",body:"শুধু আপনার ব্যবসার সদস্য, এবং যার যতটুকু ভূমিকা ততটুকু অনুমতি। সাপোর্টের জন্য কেউ দেখলে তার সময় ও কারণ লেখা থাকবে।"},
  {heading:"তথ্য রাখা ও আপনার অধিকার",body:"আইনি/হিসাবের প্রয়োজনে কিছু তথ্য একটা সময় পর্যন্ত রাখা হয়। নিজের প্রোফাইল ঠিক করা, তথ্য ডাউনলোড করা ও অ্যাকাউন্ট বন্ধের অনুরোধ করা যাবে।"},
];
const TERMS_SECTIONS_DEFAULT = [
  {heading:"কীভাবে ব্যবহার করা যাবে",body:"ব্যবসার মালিক নিশ্চিত করবেন যে তার কর্মী, কাস্টমার-সাপ্লায়ারের তথ্য ও যুক্ত পেমেন্ট অ্যাকাউন্ট ব্যবহারের অধিকার তার আছে।"},
  {heading:"ব্যবসার নিজের দায়িত্ব",body:"পণ্যের দাম, কর, কর্মী-কাস্টমারের অনুমতি, শুরুর হিসাব এবং পেমেন্ট অ্যাকাউন্টের তথ্য ঠিক রাখা ব্যবসার নিজের দায়িত্ব।"},
  {heading:"সেবার সীমা",body:"পেমেন্ট সফল হবে যখন bKash/Nagad-এর মতো প্রতিষ্ঠান নিশ্চিত করবে। AI পরামর্শ শুধু পরামর্শ, মানুষ অনুমোদন না দিলে কোনো টাকা বা বার্তা যায় না।"},
  {heading:"চূড়ান্ত চুক্তি",body:"প্যাকেজ, ব্যবহারের সীমা, সাপোর্টের সময়, তথ্য রপ্তানি, বন্ধ করার নিয়ম — এসব আসল ব্যবহারের চুক্তিতে স্পষ্ট করে লেখা থাকবে।"},
];
const STATUS_COMPONENTS_DEFAULT = [
  ["ওয়েব অ্যাপ","এখন আপনি যা দেখছেন সেটাই চলছে"],
  ["ব্যবসার API","সার্ভারের স্বাস্থ্য যাচাই করা যায়"],
  ["ডেটাবেজ ও ব্যাকআপ","ব্যাকআপ কত পুরোনো তা নিয়মিত যাচাই করা হয়"],
  ["bKash/Nagad সংযোগ","প্রতিটা আলাদাভাবে পরীক্ষা করতে হয়"],
  ["SMS / WhatsApp","পাঠানো বার্তার অবস্থা আলাদা দেখা যায়"],
  ["ব্যাকগ্রাউন্ড সিংক","আটকে থাকা কাজের উপর নজর দরকার"],
];
const CONTACT_CARDS_DEFAULT = [
  {icon:"zap",title:"নতুন ব্যবসা",text:"নিজেই অ্যাকাউন্ট খুলে ধাপে ধাপে শুরু করুন।",link_label:"অ্যাকাউন্ট খুলুন",link_to:"/signup"},
  {icon:"key",title:"আগে থেকে ব্যবহারকারী",text:"লগইন করে সাহায্য পাতা ও গাইড দেখুন।",link_label:"লগইন করুন",link_to:"/login",ghost:true},
  {icon:"fileText",title:"কথা বলে জেনে নিতে চান",text:"আপনার ব্যবসার ধরন অনুযায়ী কী লাগবে বুঝে নিন।",link_label:"ব্যবসার ধরন দেখুন",link_to:"/solutions",ghost:true},
];

const ABOUT_VALUES_DEFAULT = [
  {num:"01",title:"সত্যি কথা বলি, বাড়িয়ে না",text:"ভুয়া কাস্টমার সংখ্যা, মিথ্যা সাফল্যের গল্প বা এখনো তৈরি না হওয়া ফিচারকে চালু আছে বলে দেখাই না।"},
  {num:"02",title:"মানুষ আগে, মেনু পরে",text:"মালিক, ক্যাশিয়ার, স্টোরকিপার, হিসাবরক্ষক ও রাইডার — প্রত্যেকের কাজ আলাদা করে ভেবে সাজানো।"},
  {num:"03",title:"পুরো হিসাব এক জায়গায়",text:"শুধু ফিচারের সংখ্যা বাড়ানো না। স্টক, টাকা, খাতা, অনুমোদন — সব একসাথে মিলে কাজ করাই আসল।"},
];
function Brand({ compact = false }) {
  return (
    <Link to="/" className={`public-brand${compact ? " compact" : ""}`} aria-label="B-SMART হোম">
      <img className="public-brandmark" src="/bsmart-mark.svg" alt="" />
      <span><strong>B-SMART</strong><small>Business OS</small></span>
    </Link>
  );
}

function ThemeToggleBtn({ small }) {
  const { theme, toggleTheme } = useUi();
  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label="থিম পরিবর্তন করুন"
      className="public-theme-toggle"
      style={small ? { padding: "6px 8px", fontSize: 14 } : {}}
      title={theme === "dark" ? "Light mode এ যান" : "Dark mode এ যান"}
    >
      {theme === "dark" ? "☀️" : "🌙"}
    </button>
  );
}

function PublicHeader() {
  const [open, setOpen] = useState(false);
  const { user } = useAuth();
  const { pathname } = useLocation();
  const site = useSiteContent();
  const nav = site.getJson("nav_links", NAV);
  useEffect(() => { setOpen(false); window.scrollTo(0, 0); }, [pathname]);
  return (
    <header className="public-header">
      <div className="public-navwrap">
        <Brand />
        <button className="public-menu" type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open} aria-controls="public-navigation" aria-label={open ? "মেনু বন্ধ করুন" : "মেনু খুলুন"}>
          <Icon name={open ? "x" : "menu"} />
        </button>
        <nav id="public-navigation" className={`public-nav${open ? " is-open" : ""}`} aria-label="প্রধান নেভিগেশন">
          {nav.map(([to, label]) => <NavLink key={to} to={to} className={({ isActive }) => isActive ? "active" : ""}>{label}</NavLink>)}
          <NavLink to="/help" className={({ isActive }) => isActive ? "active" : ""}>{site.get("header.help_label","সহায়তা")}</NavLink>
        </nav>
        <div className="public-actions">
          <ThemeToggleBtn />
          {user ? <Link className="public-linkbtn" to="/app">{site.get("header.dashboard_label","ড্যাশবোর্ড")}</Link> : <Link className="public-linkbtn" to="/login">{site.get("header.login_label","লগইন")}</Link>}
          <Link className="public-cta" to="/signup">{site.get("header.cta_label","বিনামূল্যে শুরু করুন")} <Icon name="chevronRight" size={16} /></Link>
        </div>
      </div>
    </header>
  );
}

const FOOTER_COL1 = [["/features","ফিচার"],["/solutions","ব্যবসার ধরন"],["/pricing","মূল্য পরিকল্পনা"]];
const FOOTER_COL2 = [["/security","নিরাপত্তা"],["/guidelines","ব্যবহারবিধি"],["/about","আমাদের কথা"],["/help","সহায়তা"]];
const FOOTER_COL3 = [["/signup","Owner account"],["/login","Business login"],["/contact","যোগাযোগ"]];

function PublicFooter() {
  const site = useSiteContent();
  const col1 = site.getJson("footer.col1_links", FOOTER_COL1);
  const col2 = site.getJson("footer.col2_links", FOOTER_COL2);
  const col3 = site.getJson("footer.col3_links", FOOTER_COL3);
  return (
    <footer className="public-footer">
      <div className="public-footergrid">
        <div><Brand compact /><p>{site.get("footer.tagline", "বাংলাদেশের ছোট ও মাঝারি ব্যবসার জন্য তৈরি — সহজ, স্পষ্ট ও প্রমাণসহ।")}</p></div>
        <div><strong>পণ্য</strong>{col1.map(([to, label]) => <Link key={to} to={to}>{label}</Link>)}</div>
        <div><strong>বিশ্বাস</strong>{col2.map(([to, label]) => <Link key={to} to={to}>{label}</Link>)}</div>
        <div><strong>শুরু করুন</strong>{col3.map(([to, label]) => <Link key={to} to={to}>{label}</Link>)}</div>
      </div>
      <div className="public-footnote"><span>{site.get("footer.copy","© 2026 B-SMART · Bangladesh SME Business OS")}</span><span className="public-legal"><Link to="/privacy">গোপনীয়তা</Link><Link to="/terms">শর্তাবলি</Link><Link to="/status">System status</Link></span><span>{site.get("footer.rollout_note","Production capability ও rollout status স্বচ্ছভাবে প্রকাশ করা হয়।")}</span></div>
    </footer>
  );
}

function PublicFrame({ children }) {
  return <div className="public-site"><a className="public-skip" href="#public-main">মূল কনটেন্টে যান</a><PublicHeader /><main id="public-main">{children}</main><PublicFooter /></div>;
}

function SectionHead({ eyebrow, title, text, align = "center" }) {
  return <div className={`public-sectionhead ${align}`}><span>{eyebrow}</span><h2>{title}</h2>{text && <p>{text}</p>}</div>;
}

function PhotoCredit({ media }) {
  return <a className="photo-credit" href={media.source} target="_blank" rel="noreferrer">ছবি: {media.credit}</a>;
}

function RealWorkGallery() {
  const site = useSiteContent();
  const rw = site.getJson("real_work", REAL_WORK);
  const cardEyebrow = site.get("real_work_section.card_eyebrow", "বাংলাদেশের বাস্তব ব্যবসা");
  const items = Object.values(rw).slice(0, 5).filter(Boolean);
  return (
    <div className="real-work-gallery">
      {items.map((media, index) => (
        <figure className={`real-work-card real-work-${index + 1}`} key={media.label}>
          <img src={media.src} alt={media.alt} loading="lazy" referrerPolicy="no-referrer" />
          <figcaption><small>{cardEyebrow}</small><b>{media.label}</b><span>{media.detail}</span></figcaption>
          <PhotoCredit media={media} />
        </figure>
      ))}
    </div>
  );
}

function ProductPreview() {
  const site = useSiteContent();
  const stats = site.getJson("preview.stats", PREVIEW_STATS_DEFAULT);
  const missionItems = site.getJson("preview.mission_items", PREVIEW_MISSION_DEFAULT);
  return (
    <div className="public-productshot" aria-label="B-SMART dashboard preview">
      <div className="productshot-bar"><span /><span /><span /><b>{site.get("preview.branch_name","B-SMART · মিরপুর শাখা")}</b><em>ডেমো ডেটা</em></div>
      <div className="productshot-layout">
        <aside><strong>আজকের কাজ</strong>{["ড্যাশবোর্ড", "বিক্রি", "স্টক", "ক্রয়", "হিসাব"].map((x, i) => <span className={i === 0 ? "on" : ""} key={x}>{x}</span>)}</aside>
        <div className="productshot-main">
          <div className="productshot-welcome"><div><small>{site.get("preview.date_label","বুধবার · ১ অক্টোবর")}</small><strong>{site.get("preview.greeting","শুভ সকাল, Rahim")}</strong><span>{site.get("preview.task_subtitle","৩টি কাজ এখন আপনার মনোযোগ চায়")}</span></div><i><Icon name="zap" size={18} /> Today Mission</i></div>
          <div className="productshot-stats">{stats.map((s) => <div key={s.label}><span>{s.label}</span><b>{s.value}</b><small>{s.note}</small></div>)}</div>
          <div className="productshot-bottom"><div className="fake-chart"><span>বিক্রির ধারা</span><svg viewBox="0 0 420 100" role="img" aria-label="ঊর্ধ্বমুখী বিক্রির রেখা"><path d="M4 86 C45 80 52 61 88 68 S140 87 170 54 S230 67 264 38 S330 52 416 12" /></svg></div><div className="mission-list"><span>এখন করুন</span>{missionItems.map((label, i) => <b key={label}><i>{i + 1}</i> {label}</b>)}</div></div>
        </div>
      </div>
    </div>
  );
}

function ProductTour() {
  const site = useSiteContent();
  const tourItems = site.getJson("product_tour", PRODUCT_TOUR);
  const [activeId, setActiveId] = useState("pos");
  const active = tourItems.find((item) => item.id === activeId) || tourItems[0];
  return (
    <section className="public-section product-tour-section">
      <SectionHead eyebrow="বাস্তবে কাজ করে দেখুন" title="আপনার টিম কাজ করবে, সিস্টেম নিজে সব মিলিয়ে রাখবে" text="একটা অংশ বেছে নিন। দেখুন একই বিক্রি কীভাবে কাউন্টার থেকে মালিকের হিসাব পর্যন্ত যায়।" />
      <div className="product-tour-tabs" role="tablist" aria-label="Product workflow">
        {tourItems.map((item) => <button type="button" role="tab" aria-selected={item.id === activeId} className={item.id === activeId ? "active" : ""} onClick={() => setActiveId(item.id)} key={item.id}><Icon name={item.icon} /><span>{item.tab}</span></button>)}
      </div>
      <div className={`product-tour-stage tone-${active.accent}`}>
        <div className="product-tour-copy"><small>{active.kicker}</small><h2>{active.title}</h2><p>{active.text}</p><strong><Icon name="check" /> {active.metric}</strong><ul>{active.points.map((point) => <li key={point}><Icon name="chevronRight" />{point}</li>)}</ul><Link className="public-textlink" to="/features">সব capability দেখুন <Icon name="chevronRight" /></Link></div>
        <div className="tour-window" aria-label={`${active.tab} interface preview`}>
          <div className="tour-window-bar"><span /><span /><span /><b>{active.tab}</b><em>মিরপুর শাখা</em></div>
          {active.id === "pos" && <div className="tour-pos"><div className="tour-search"><Icon name="search" /><span>Barcode scan অথবা পণ্য খুঁজুন</span></div><div className="tour-items"><div><span>Paracetamol 500mg · 2 box</span><b>৳ ১,২০০</b></div><div><span>Vitamin C · 1 box</span><b>৳ ৪৮০</b></div><div><span>Delivery charge</span><b>৳ ৬০</b></div></div><div className="tour-total"><span>সর্বমোট</span><b>৳ ১,৭৪০</b></div><div className="tour-tenders"><span>Cash · ৳১,০০০</span><span>MFS · ৳৭৪০</span></div></div>}
          {active.id === "stock" && <div className="tour-stock"><div className="tour-kpis"><span><small>বর্তমান মজুত</small><b>২৪ box</b></span><span><small>চলবে</small><b>৫ দিন</b></span><span><small>Lead time</small><b>৭ দিন</b></span></div><div className="tour-ledger"><div><i className="in" /><span>GRN · PO-219</span><b>+ 40</b></div><div><i className="out" /><span>Sale · INV-8821</span><b>− 2</b></div><div><i className="out" /><span>Transfer · Uttara</span><b>− 8</b></div><div><i className="in" /><span>Return · INV-8790</span><b>+ 1</b></div></div></div>}
          {active.id === "cash" && <div className="tour-cash"><div className="tour-balance"><small>Expected closing cash</small><strong>৳ ৩২,৪০০</strong><span>Actual count · ৳ ৩২,২০০</span></div><div className="tour-reconcile"><div><span>Cash sale</span><b>৳ ২৫,৮০০</b></div><div><span>MFS confirmed</span><b>৳ ১৮,৭৫০</b></div><div><span>COD received</span><b>৳ ৬,২০০</b></div><div className="warn"><span>Difference</span><b>− ৳ ২০০</b></div></div><div className="tour-exception"><Icon name="alert" /><span>Reason ও manager review প্রয়োজন</span></div></div>}
          {active.id === "ai" && <div className="tour-ai"><div className="tour-ai-head"><span><Icon name="zap" /> Reorder recommendation</span><em>Confidence 87%</em></div><h3>Paracetamol 500mg · ২৪ box কিনুন</h3><p>৫ দিনের stock আছে, supplier lead time ৭ দিন এবং আগামী সপ্তাহে demand ১২% বাড়ার সম্ভাবনা।</p><div className="tour-ai-evidence"><span>Budget-এর মধ্যে <b>হ্যাঁ</b></span><span>MOQ পূরণ <b>হ্যাঁ</b></span><span>Expiry risk <b>কম</b></span></div><div className="tour-ai-actions"><span>কারণ দেখুন</span><strong>খসড়া PO তৈরি</strong></div></div>}
        </div>
      </div>
    </section>
  );
}

function HomePage() {
  const site = useSiteContent();
  const solutions = site.getJson("solutions_list", SOLUTIONS);
  const flowItems = site.getJson("flow_section.items", FLOW_ITEMS_DEFAULT);
  const gettingStartedSteps = site.getJson("getting_started.steps", GETTING_STARTED_STEPS_DEFAULT);
  const customerQuestions = site.getJson("customer_questions.items", CUSTOMER_QUESTIONS_DEFAULT);
  const actorItems = site.getJson("actor_section.items", ACTOR_ITEMS_DEFAULT);
  return (
    <>
      <section className="public-hero">
        <div className="public-hero-copy">
          <span className="public-kicker"><i /> {site.get("hero.kicker", "বাংলাদেশের ছোট ও মাঝারি ব্যবসার জন্য তৈরি")}</span>
          <h1>{site.get("hero.title", "আপনার দোকানের প্রতিদিনের হিসাব, এখন হাতের মুঠোয়")}</h1>
          <p>{site.get("hero.subtitle", "বিক্রি, স্টক, ক্যাশ, বাকি, কর্মী ও ডেলিভারি — সব এখন একটা অ্যাপ থেকেই চালান। আলাদা খাতা-কলম বা একাধিক হিসাবের ঝামেলা লাগবে না।")}</p>
          <div className="public-hero-actions"><Link className="public-cta large" to="/signup">{site.get("hero.cta_primary", "ব্যবসা শুরু করুন")} <Icon name="chevronRight" /></Link><Link className="public-ghost large" to="/features"><Icon name="zap" /> {site.get("hero.cta_secondary", "কীভাবে কাজ করে")}</Link></div>
          <div className="public-assurances"><span><Icon name="check" /> {site.get("hero.assurance_1", "সম্পূর্ণ বাংলায়")}</span><span><Icon name="check" /> {site.get("hero.assurance_2", "যার যতটুকু দরকার ততটুকুই দেখবে")}</span><span><Icon name="check" /> {site.get("hero.assurance_3", "প্রতিটা কাজের প্রমাণ থাকে")}</span></div>
        </div>
        <ProductPreview />
      </section>

      <section className="public-strip"><span>{site.get("strip.label", "একটাই অ্যাপে")}</span><b>{site.get("strip.item_1", "বিক্রি")}</b><i /> <b>{site.get("strip.item_2", "স্টক")}</b><i /> <b>{site.get("strip.item_3", "হিসাব")}</b><i /> <b>{site.get("strip.item_4", "কর্মী")}</b><i /> <b>{site.get("strip.item_5", "ডেলিভারি")}</b><i /> <b>{site.get("strip.item_6", "AI পরামর্শ")}</b></section>

      <ProductTour />

      <section className="public-section public-story">
        <div className="public-story-image">
          <img src={site.get("story.image_src", "https://asiapacific.unwomen.org/sites/default/files/Field%20Office%20ESEAsia/Images/2018/02/Sita-Rani-675px.jpg")} alt={site.get("story.image_alt", "বাংলাদেশের একটি মুদি দোকানে উদ্যোক্তা")} loading="lazy" referrerPolicy="no-referrer" />
          <a href={site.get("story.image_link", "https://asiapacific.unwomen.org/en/news-and-events/stories/2018/02/sita-rani-gour")} target="_blank" rel="noreferrer">ছবি: {site.get("story.image_credit", "UN Women Asia-Pacific")}</a>
        </div>
        <div><SectionHead align="left" eyebrow={site.get("story.eyebrow", "বাস্তব কাজের কথা ভেবে তৈরি")} title={site.get("story.title", "কাউন্টারের ব্যস্ততা থেকে মালিকের সিদ্ধান্ত পর্যন্ত")} text={site.get("story.text", "বাংলাদেশে একজন মানুষ একই দিনে ক্যাশিয়ার, মাল কেনার লোক আর মালিক — সব ভূমিকায় কাজ করেন। তাই এটা জটিল মেনু দিয়ে শুরু হয় না, বরং আপনি কে এবং আজ আপনার কী কাজ সেটা দিয়ে শুরু হয়।")} /><div className="story-points"><div><b>শেখা সহজ</b><span>পুরোটা বাংলায়, ধাপে ধাপে দেখানো</span></div><div><b>ইন্টারনেট দুর্বল হলেও চলে</b><span>কাজ আটকায় না, পরে নিজে থেকে মিলে যায়</span></div><div><b>সব হিসাবের প্রমাণ থাকে</b><span>রসিদ থেকে স্টক ও হিসাবের খাতা পর্যন্ত</span></div></div><Link className="public-textlink" to="/guidelines">{site.get("story.cta", "কে কীভাবে ব্যবহার করবেন দেখুন")} <Icon name="chevronRight" /></Link></div>
      </section>

      <section className="public-section owner-problem-section">
        <SectionHead eyebrow={site.get("problems.eyebrow", "আপনার সমস্যা থেকেই শুরু")} title={site.get("problems.title", "ফিচারের নাম নয়, আপনার ব্যবসার প্রশ্নের উত্তর")} text={site.get("problems.text", "নিচের যেকোনো একটা প্রশ্ন আপনার মনে হলে, কোন তথ্য মিলিয়ে, কাকে কাজ দিয়ে এটা সমাধান হবে তা দেখে নিন।")} />
        <div className="owner-problem-grid">{(site.getJson("owner_problems", OWNER_PROBLEMS)).map((item) => <article key={item.question}><span><Icon name={item.icon} /></span><h3>{item.question}</h3><p>{item.answer}</p><div><b>{item.path}</b><small>{item.actor}</small></div></article>)}</div>
      </section>

      <section className="public-section bd-ready-section">
        <div className="bd-ready-intro"><SectionHead align="left" eyebrow={site.get("bd_ready.eyebrow", "বাংলাদেশের বাস্তবতা মাথায় রেখে")} title={site.get("bd_ready.title", "বিদেশি সফটওয়্যার না, এখানকার ব্যবসার আসল নিয়ম")} text={site.get("bd_ready.text", "বাংলাদেশের ব্যবসার নগদ টাকার উপর নির্ভরতা, বাকির সম্পর্ক, bKash/Nagad, COD, নিজস্ব প্যাকেজিং একক, একাধিক মানুষ এক ডিভাইস ব্যবহার করা এবং দুর্বল ইন্টারনেট — এই বাস্তবতা মাথায় রেখেই তৈরি।")} /><Link className="public-textlink" to="/security">তথ্য কীভাবে নিরাপদ রাখা হয় দেখুন <Icon name="chevronRight" /></Link></div>
        <div className="bd-ready-grid">{(site.getJson("bangladesh_ready", BANGLADESH_READY)).map((item) => <article key={item.title}><span><Icon name={item.icon} /></span><div><h3>{item.title}</h3><p>{item.text}</p></div></article>)}</div>
      </section>

      <section className="public-section public-tint before-after-section">
        <SectionHead eyebrow={site.get("before_after.eyebrow", "সহজ ভাষায়")} title={site.get("before_after.title", "খাতা কলমের দোকান থেকে B-SMART এ গেলে কী বদলায়")} text={site.get("before_after.text", "প্রযুক্তির নাম নয়। এটি আপনার প্রতিদিনের বাস্তব সমস্যার তুলনা।")} />
        <div className="before-after-grid">
          <div className="before-after-head"><span>{site.get("before_after.col_before", "এখন যেভাবে চলছে")}</span><span>{site.get("before_after.col_after", "B-SMART দিয়ে যেভাবে চলবে")}</span></div>
          {site.getJson("before_after.items", BEFORE_AFTER).map(([before, after]) => (
            <div className="before-after-row" key={before}>
              <div className="before-after-cell before"><Icon name="x" size={16} /><span>{before}</span></div>
              <div className="before-after-cell after"><Icon name="check" size={16} /><span>{after}</span></div>
            </div>
          ))}
        </div>
      </section>

      <section className="public-section">
        <SectionHead eyebrow={site.get("flow_section.eyebrow","সব এক সুতায় বাঁধা")} title={site.get("flow_section.title","একটা বিক্রি হলেই পুরো হিসাব নিজে থেকে আপডেট হয়")} text={site.get("flow_section.text","আলাদা খাতা বা আলাদা অ্যাপ লাগবে না। প্রতিটা বিক্রি স্টক, টাকা, বাকি ও হিসাবের খাতা — সবখানে একসাথে যোগ হয়ে যায়।")} />
        <div className="public-flow">{flowItems.flatMap(([icon, label, sub], i, arr) => [
          <div key={label}><Icon name={icon} /><b>{label}</b><span>{sub}</span></div>,
          ...(i < arr.length - 1 ? [<Icon key={`sep-${i}`} name="chevronRight" />] : [])
        ])}</div>
      </section>

      <section className="public-section public-tint getting-started">
        <div><SectionHead align="left" eyebrow={site.get("getting_started.eyebrow","শুরু করার ধাপ")} title={site.get("getting_started.title","খাতা থেকে অ্যাপে যাওয়ার চারটা সহজ ধাপ")} text={site.get("getting_started.text","আপনার ব্যবসার ধরন অনুযায়ী শুধু দরকারি প্রশ্নই করা হবে। পুরনো হিসাব একদিনে না বদলে, ধাপে ধাপে ও যাচাই করে নতুন সিস্টেমে যাবেন।")} /><div className="setup-proof"><Icon name="shield" /><span><b>{site.get("getting_started.proof_title","আপনার হাতে নিয়ন্ত্রণ")}</b> {site.get("getting_started.proof_text","শুরুর স্টক, হিসাব ও বাকি — মালিক নিজে অনুমোদন না দেওয়া পর্যন্ত কিছুই চূড়ান্ত হবে না।")}</span></div></div>
        <ol>{gettingStartedSteps.map(([stepTitle, stepText], index) => <li key={stepTitle}><i>{index + 1}</i><div><b>{stepTitle}</b><span>{stepText}</span></div></li>)}</ol>
      </section>

      <section className="public-section public-tint customer-questions">
        <SectionHead eyebrow={site.get("customer_questions.eyebrow","আপনার বাস্তব প্রশ্ন")} title={site.get("customer_questions.title","রিপোর্ট না, সরাসরি উত্তর আর পরের করণীয়")} text={site.get("customer_questions.text","প্রতিটা উত্তর আসল লেনদেন থেকে আসে, আর ঠিক যার কাজ তার কাছেই যায়।")} />
        <div>{customerQuestions.map(([q, source, answer, actor], i) => <article key={q}><i>{String(i + 1).padStart(2, "0")}</i><div><small>{source}</small><h3>{q}</h3><p>{answer}</p><span><Icon name="userCheck" /> {actor}</span></div></article>)}</div>
      </section>

      <section className="public-section real-work-section">
        <SectionHead eyebrow={site.get("real_work_section.eyebrow","Built for Bangladesh")} title={site.get("real_work_section.title","এক software, বাস্তব ব্যবসার বহু রূপ")} text={site.get("real_work_section.text","ছবির ব্যবসাগুলো আলাদা, কিন্তু প্রতিটির মৌলিক প্রশ্ন একই। কী বিক্রি হলো, কত stock আছে, টাকা কোথায় এবং পরের কাজ কার।")} />
        <RealWorkGallery />
        <div className="real-work-note"><Icon name="info" /><span>{site.get("real_work_section.disclaimer","ছবিগুলো বাস্তব বাংলাদেশি ব্যবসা ও কর্মপরিবেশের licensed editorial photograph; এগুলো B-SMART customer endorsement নয়।")}</span></div>
      </section>

      <section className="public-section public-tint">
        <SectionHead eyebrow={site.get("actor_section.eyebrow","যার যা কাজ, তার তাই দেখা")} title={site.get("actor_section.title","সবার জন্য একই মেনু না")} text={site.get("actor_section.text","প্রত্যেকে লগইন করে শুধু নিজের কাজটুকুই দেখবেন — বাকি কিছু দেখার দরকার নেই।")} />
        <div className="actor-cards">{actorItems.map(([icon, title, text]) => <article key={title}><span><Icon name={icon} /></span><b>{title}</b><p>{text}</p></article>)}</div>
      </section>

      <section className="public-section">
        <SectionHead eyebrow={site.get("home_solutions.eyebrow","যেকোনো ব্যবসার জন্য")} title={site.get("home_solutions.title","একই ভিত্তির উপর প্রতিটা ব্যবসার নিজস্ব কাজ")} text={site.get("home_solutions.text","ব্যবসার ধরন বেছে শুরু করুন। পরে পণ্য বিক্রি, সেবা, বুকিং বা ডেলিভারি — যেটা দরকার যোগ করুন।")} />
        <div className="solution-grid compact">{Object.entries(solutions).slice(0, 8).map(([slug, s]) => <Link to={`/solutions/${slug}`} key={slug}><span><Icon name={s.icon} /></span><div><b>{s.title}</b><p>{s.tagline}</p></div><Icon name="chevronRight" /></Link>)}</div>
        <div className="public-center"><Link className="public-textlink" to="/solutions">{site.get("home_solutions.see_all","সব ব্যবসার ধরন দেখুন")} <Icon name="chevronRight" /></Link></div>
      </section>

      <section className="public-section ai-decision-section">
        <div className="ai-decision-head"><SectionHead align="left" eyebrow={site.get("ai_decisions.eyebrow", "AI পরামর্শ")} title={site.get("ai_decisions.title", "শুধু তথ্য না, পরের সঠিক কাজটা বুঝিয়ে দেয়")} text={site.get("ai_decisions.text", "আসল লেনদেন থেকে পরামর্শ তৈরি হয়। প্রতিটা পরামর্শের কারণ, কতটা নিশ্চিত, আর কী প্রভাব পড়বে তা দেখা যায়। শেষ সিদ্ধান্ত সবসময় আপনার।")} /><div className="ai-signal"><Icon name="zap" /><div><b>{site.get("ai_decisions.signal_title", "শেখে · পরামর্শ দেয় · ফলাফল মাপে")}</b><span>{site.get("ai_decisions.signal_text", "কাজের ফলাফল আবার মডেলে ফিরে যায়, যাতে পরেরবার আরও ভালো হয়")}</span></div></div></div>
        <div className="ai-decision-grid">{site.getJson("ai_decisions.items", AI_DECISIONS).map((item) => <article key={item.title}><span><Icon name={item.icon} /></span><h3>{item.title}</h3><small>{site.get("ai_decisions.col_input", "যা দেখে")}</small><p>{item.data}</p><small>{site.get("ai_decisions.col_output", "আপনি যা পাবেন")}</small><b>{item.output}</b></article>)}</div>
      </section>

      <section className="public-section public-darkcallout"><div><span className="public-kicker light"><i /> {site.get("dark_callout.kicker", "যাদুর মতো না, বোঝা যায় এমন")}</span><h2>{site.get("dark_callout.title", "AI কারণ বলবে, সিদ্ধান্ত থাকবে আপনার হাতে")}</h2><p>{site.get("dark_callout.text", "পরামর্শের পেছনের সংখ্যা, শর্ত, কতটা নিশ্চিত আর কী ফল হতে পারে — সব দেখুন। গ্রহণ, বদলানো, আটকে রাখা বা বাতিল করার সিদ্ধান্ত সবসময় মানুষের।")}</p><Link className="public-cta light" to="/features">{site.get("dark_callout.cta", "পরামর্শ কীভাবে আসে দেখুন")} <Icon name="chevronRight" /></Link></div><div className="decision-card"><small>আজকের সুপারিশ · স্টক</small><b>Paracetamol 500mg-এর ২৪ বক্স নতুন অর্ডার</b><p>বর্তমান মজুত ৫ দিন চলবে · সাপ্লায়ারের মাল দিতে ৭ দিন লাগে</p><div><span>ফুরিয়ে যাওয়ার ঝুঁকি</span><strong>উচ্চ থেকে কম হবে</strong></div><footer><span>কারণ দেখুন</span><span>খসড়া অর্ডার</span></footer></div></section>

      <CtaBand />
    </>
  );
}

function FeaturesPage() {
  const site = useSiteContent();
  const features = site.getJson("core_features", CORE_FEATURES);
  const rw = site.getJson("real_work", REAL_WORK);
  return (
    <>
      <PageHero eyebrow={site.get("features.eyebrow", "সব ফিচার")} title={site.get("features.title", "দৈনিক কাজ থেকে মালিকের সিদ্ধান্ত, সব একটা সিস্টেমে")} text={site.get("features.text", "একই core সব ধরনের ব্যবসার জন্য কাজ করে, আর ব্যবসার ধরন অনুযায়ী বিশেষ অংশগুলো যোগ হয়।")} />
      <section className="public-section"><div className="feature-grid">{features.map((f) => <article key={f.title}><span><Icon name={f.icon} /></span><h3>{f.title}</h3><p>{f.text}</p></article>)}</div></section>
      <section className="public-section feature-photo-story">
        <div className="feature-photo-copy"><SectionHead align="left" eyebrow={site.get("features_photo.eyebrow","একই নিয়ম সব জায়গায়")} title={site.get("features_photo.title","দোকানের কাউন্টার, রান্নাঘর বা কারখানা — সব জায়গায় একই নিয়ম")} text={site.get("features_photo.text","কাজ কে শুরু করলো, কী হলো, টাকায় কী প্রভাব পড়লো আর তার প্রমাণ — এসব একসাথে যুক্ত থাকলেই মালিক আসল নিয়ন্ত্রণ পান।")} /><Link className="public-textlink" to="/guidelines">কে কীভাবে ব্যবহার করবেন <Icon name="chevronRight" /></Link></div>
        {[rw.restaurant, rw.service, rw.electronics].filter(Boolean).map((media) => <figure key={media.label}><img src={media.src} alt={media.alt} loading="lazy" referrerPolicy="no-referrer" /><figcaption><b>{media.label}</b><span>{media.detail}</span></figcaption><PhotoCredit media={media} /></figure>)}
      </section>
      <section className="public-section public-tint"><div className="split-feature"><div><SectionHead align="left" eyebrow={site.get("features_workflow.eyebrow","তথ্য থেকে সরাসরি কাজে")} title={site.get("features_workflow.title","শুধু রিপোর্ট দেখে বসে না থেকে, সরাসরি কাজে নামুন")} text={site.get("features_workflow.text","স্টক কমে গেলে সেখান থেকেই নতুন অর্ডার, বাকি পুরোনো হলে কালেকশনের কাজ, মেয়াদ ফুরালে সাপ্লায়ারের দাবি — এক ক্লিকে তৈরি করুন।")} /><ul className="check-list">{site.getJson("features_workflow.checklist",["যেকোনো সংখ্যার আসল উৎস পর্যন্ত দেখা যায়","কাকে কাজ দেওয়া হলো ও কবের মধ্যে","অনুমোদনের পর আবার যাচাই হয়","ফলাফল পরে মাপা হয়"]).map((item) => <li key={item}><Icon name="check" /> {item}</li>)}</ul></div><div className="public-stack">{site.getJson("features_workflow.tasks",[["আজকের করণীয়","ঠিক মানুষের সামনে জরুরি কাজ"],["ক্যাশ মেলানো","ক্যাশ, bKash, কার্ড ও COD-র গরমিল"],["স্টকের সত্য হিসাব","গণনা থেকে ভুলের ঝুঁকি"],["বাকি আদায়ের পরিকল্পনা","প্রতিশ্রুতি ও বয়স দেখে আদায়ের কাজ"]]).map(([x, desc], i) => <div key={x}><i>{String(i + 1).padStart(2, "0")}</i><b>{x}</b><span>{desc}</span></div>)}</div></div></section>
      <section className="public-section"><SectionHead eyebrow={site.get("features_status.eyebrow","পরিষ্কার অবস্থা")} title={site.get("features_status.title","কোনটা চালু, কোনটা এখনো বাকি — স্পষ্ট করে বলি")} text={site.get("features_status.text","একটা পূর্ণ সমাধানের সব অংশ সবসময় সব ব্যবসায় একসাথে চালু নাও থাকতে পারে। আপনার নিজের workspace-এ ঠিক কী চালু আছে তা স্পষ্ট দেখা যাবে।")} /><div className="status-row"><div><i className="status-live" /><b>চালু আছে</b><span>আপনার workspace-এ এখনই ব্যবহার করা যায়</span></div><div><i className="status-pilot" /><b>সীমিত আকারে চালু</b><span>নির্দিষ্ট শাখা বা ভূমিকার জন্য</span></div><div><i className="status-roadmap" /><b>সেট করা লাগবে</b><span>প্রয়োজনীয় তথ্য বা অনুমতি এখনো দেওয়া হয়নি</span></div></div></section>
      <CtaBand />
    </>
  );
}

function SolutionsPage({ slug }) {
  const site = useSiteContent();
  const solutions = site.getJson("solutions_list", SOLUTIONS);
  const rw = site.getJson("real_work", REAL_WORK);
  const selected = slug && solutions[slug];
  if (selected) return <SolutionDetail slug={slug} solution={selected} rw={rw} />;
  return (
    <>
      <PageHero eyebrow={site.get("solutions.eyebrow", "ব্যবসার ধরন")} title={site.get("solutions.title", "আপনার ব্যবসার মতো করেই সাজানো")} text={site.get("solutions.text", "যেকোনো একটা ধরন বেছে দ্রুত শুরু করুন। পরে আরও প্রয়োজন হলে নতুন সুবিধা যোগ করতে পারবেন।")} />
      <section className="public-section solution-visual-intro"><div><SectionHead align="left" eyebrow={site.get("solutions_intro.eyebrow","আপনার ব্যবসা বুঝে সাজানো")} title={site.get("solutions_intro.title","প্রতিটা ব্যবসার কাজ আলাদা, তাই স্ক্রিনও আলাদা")} text={site.get("solutions_intro.text","মুদি দোকানের স্ক্রিন, রেস্টুরেন্টের রান্নাঘর, আর ওয়ার্কশপের কাজের কার্ড — একরকম না। ভেতরের হিসাব একই থাকলেও, আপনার সামনে যা দেখাবে তা আপনার ব্যবসার মতো করেই সাজানো থাকবে।")} /></div><div className="solution-visual-stack">{[rw.retail, rw.manufacturing, rw.craft].filter(Boolean).map((media, index) => <figure key={media.label} style={{ "--stack-index": index }}><img src={media.src} alt={media.alt} loading="lazy" referrerPolicy="no-referrer" /><figcaption>{media.label}</figcaption></figure>)}</div></section>
      <section className="public-section"><div className="solution-grid full">{Object.entries(solutions).map(([key, s]) => <Link to={`/solutions/${key}`} key={key}><span><Icon name={s.icon} /></span><div><b>{s.title}</b><p>{s.tagline}</p>{s.status && <small>{s.status}</small>}</div><Icon name="chevronRight" /></Link>)}</div></section>
      <section className="public-section public-tint"><SectionHead eyebrow={site.get("solutions_hybrid.eyebrow","একসাথে একাধিক কাজ")} title={site.get("solutions_hybrid.title","এক ব্যবসায় দুই ধরনের কাজ করলেও সমস্যা নেই")} text={site.get("solutions_hybrid.text","যেমন ইলেকট্রনিক্স বিক্রির সাথে সার্ভিসিংও করেন, বা রেস্টুরেন্টের সাথে ডেলিভারিও দেন — কাস্টমার, টাকা, স্টক ও হিসাব সব একই জায়গায় থাকবে, আলাদা করে দুইবার লিখতে হবে না।")} /><div className="hybrid-map"><div><b>{site.get("solutions_hybrid.example_name","রহিম ইলেকট্রনিক্স")}</b><span>একটাই ব্যবসা হিসেবে</span></div>{site.getJson("solutions_hybrid.items",["দোকানে বিক্রি","অনলাইন অর্ডার","সার্ভিসিং সেন্টার","গুদাম","হিসাব"]).map((x) => <article key={x}><Icon name="chevronRight" /><b>{x}</b></article>)}</div></section>
      <CtaBand />
    </>
  );
}

function SolutionDetail({ slug, solution, rw = REAL_WORK }) {
  const media = rw[SOLUTION_MEDIA[slug]] || rw.retail || REAL_WORK.retail;
  return (
    <>
      <section className="solution-hero"><div><Link to="/solutions" className="public-back">← সব ধরন দেখুন</Link><span className="solution-icon"><Icon name={solution.icon} size={28} /></span><small>{solution.status || "ব্যবসার ধরন"}</small><h1>{solution.title}</h1><p>{solution.tagline}। বিক্রি, টাকা, হিসাব, অনুমতি ও প্রমাণ — সব একসাথে যুক্ত।</p><div className="public-hero-actions"><Link className="public-cta large" to={`/signup?solution=${slug}`}>এই ধরনের ব্যবসা দিয়ে শুরু করুন <Icon name="chevronRight" /></Link><Link className="public-ghost large" to="/contact">আমাদের সাথে কথা বলুন</Link></div></div><div className="solution-hero-visual"><img src={media.src} alt={media.alt} loading="eager" referrerPolicy="no-referrer" /><div><small>বাস্তব কাজের জন্য তৈরি</small><b>{media.label}</b><span>{media.detail}</span></div><PhotoCredit media={media} /></div></section>
      <section className="public-section"><SectionHead eyebrow="একসাথে যুক্ত কাজ" title="আলাদা আলাদা অংশ না, একটা পূর্ণ চক্র" /><div className="public-flow vertical-flow"><div><b>কাজ শুরু করেন</b><span>যার যেটুকু অনুমতি</span></div><Icon name="chevronRight" /><div><b>দৈনন্দিন কাজ</b><span>{solution.title}-এর নিজস্ব ধাপ</span></div><Icon name="chevronRight" /><div><b>স্টক বা সেবা</b><span>কী হলো তার প্রমাণ থাকে</span></div><Icon name="chevronRight" /><div><b>টাকা ও হিসাব</b><span>পেমেন্ট, বাকি ও খাতা</span></div><Icon name="chevronRight" /><div><b>মালিকের ফলাফল</b><span>রিপোর্ট, সতর্কতা ও সিদ্ধান্ত</span></div></div></section>
      <section className="public-section public-tint"><div className="split-feature"><div><SectionHead align="left" eyebrow="একই মান সবখানে" title="ব্যবসার ধরন বদলালেও হিসাবের সত্যতা একই থাকে" text="যে ব্যবসাই হোক, টাকার হিসাব, অনুমতির নিয়ম, স্টকের হিসাব আর ইন্টারনেট না থাকলে কী হবে — সব জায়গায় একই নিয়ম মানা হয়।" /><Link className="public-textlink" to="/security">আমরা কীভাবে নিরাপদ রাখি দেখুন <Icon name="chevronRight" /></Link></div><div className="solution-note"><Icon name="info" size={24} /><b>আপনার দোকানের জন্য কী লাগবে</b><p>শুরুর হিসাব, কর্মীর অনুমতি আর পেমেন্টের তথ্য সেট করার পর ঠিক কোন কোন সুবিধা চালু আছে আর কী বাকি আছে তা স্পষ্ট দেখা যাবে।</p></div></div></section>
      <CtaBand />
    </>
  );
}

function PricingPage() {
  const site = useSiteContent();
  const plans = site.getJson("pricing_plans", [
    { name: "ছোট দোকান", label: "একটা শাখা দিয়ে শুরু", text: "একটা দোকানের দৈনিক কাজ দিয়ে শুরু করুন।", points: ["ধাপে ধাপে শেখানো হবে", "বিক্রি, স্টক ও ক্যাশ নিয়ন্ত্রণ", "পুরনো হিসাব একবারে ঢোকানো", "যার যতটুকু দরকার ততটুকু দেখবে"], action: "ব্যবসা শুরু করুন" },
    { name: "বাড়ন্ত ব্যবসা", label: "বড় হচ্ছে এমন ব্যবসা", text: "বিক্রি, স্টক, টাকা, কর্মী ও AI পরামর্শ — সব একসাথে।", points: ["যার যা ভূমিকা তার মতো পাতা", "শাখা যোগ করার সুবিধা প্রস্তুত", "অনুমোদন, ইতিহাস ও রিপোর্ট", "bKash/Nagad যুক্ত করা যায়"], action: "অ্যাকাউন্ট খুলুন", featured: true },
    { name: "একাধিক শাখা", label: "বড় পরিসরের ব্যবসা", text: "একাধিক শাখা, গুদাম ও শক্তিশালী নিয়ন্ত্রণ।", points: ["সব শাখা একসাথে এক নজরে", "শাখা অনুযায়ী আলাদা অনুমতি", "শাখার মধ্যে মাল আদান-প্রদান", "চালু করার আগে একসাথে পরিকল্পনা"], action: "আমাদের সাথে কথা বলুন" },
  ]);
  return (
    <>
      <PageHero eyebrow={site.get("pricing.eyebrow", "স্বচ্ছ মূল্য পরিকল্পনা")} title={site.get("pricing.title", "আপনার ব্যবসার আকার অনুযায়ী সঠিক প্যাকেজ")} text={site.get("pricing.text", "শাখা কতটা, কতজন ব্যবহার করবেন আর কোন কোন সুবিধা লাগবে তা বুঝে বেছে নিন — কোনো লুকানো খরচ থাকবে না।")} />
      <section className="public-section"><div className="pricing-grid">{plans.map((p) => <article className={p.featured ? "featured" : ""} key={p.name}>{p.featured && <span className="plan-ribbon">সবচেয়ে উপযোগী</span>}<small>{p.label}</small><h2>{p.name}</h2><p>{p.text}</p><div className="price-state">দাম <b>প্রয়োজন বুঝে জানানো হবে</b></div><ul>{p.points.map((x) => <li key={x}><Icon name="check" />{x}</li>)}</ul><Link className={p.featured ? "public-cta" : "public-ghost"} to={p.name === "একাধিক শাখা" ? "/contact" : "/signup"}>{p.action}</Link></article>)}</div><p className="pricing-note"><Icon name="info" /> SMS, WhatsApp বা bKash/Nagad ব্যবহারের নিজস্ব খরচ সেই প্রতিষ্ঠানের নিয়ম অনুযায়ী আলাদা হবে।</p></section>
      <section className="public-section public-tint"><SectionHead eyebrow="সব প্যাকেজেই যা থাকে" title="প্যাকেজ যাই হোক, এই জিনিসগুলো সবসময় থাকবে" /><div className="promise-grid">{[["shield", "তথ্যের নিরাপত্তা"], ["fileText", "কাজের ইতিহাস"], ["download", "নিজের তথ্য ডাউনলোড"], ["refresh", "নিয়মিত ব্যাকআপ"]].map(([icon, x]) => <div key={x}><Icon name={icon} /><b>{x}</b></div>)}</div></section>
      <CtaBand />
    </>
  );
}

function SecurityPage() {
  const site = useSiteContent();
  const trust = site.getJson("trust_items", TRUST);
  return (
    <>
      <PageHero eyebrow={site.get("security.eyebrow", "নিরাপত্তা")} title={site.get("security.title", "নিরাপত্তা শুধু একটা ফিচার না, প্রতিটা কাজের ভিত্তি")} text={site.get("security.text", "যা বানানো হয়ে গেছে আর যা এখনো বাকি — দুটোই স্পষ্ট করে বলি, কোনোটা লুকিয়ে রাখি না।")} />
      <section className="public-section"><div className="trust-grid">{trust.map(([icon, title, text]) => <article key={title}><span><Icon name={icon} /></span><h3>{title}</h3><p>{text}</p></article>)}</div></section>
      <section className="public-section public-tint"><div className="security-table"><div><SectionHead align="left" eyebrow="চালু করার আগে যাচাই" title="সিস্টেম চালু করার আগে যা যাচাই করে দেখা হয়" text="শতভাগ ত্রুটিহীন থাকার দাবি করি না — বরং সমস্যা হলে তা ধরা পড়বে ও ঠিক করা যাবে, এটাই নিশ্চিত করি।" /></div><ul><li><Icon name="check" /> এক ব্যবসার তথ্য আরেক ব্যবসা দেখতে পারে কিনা তার পরীক্ষা</li><li><Icon name="check" /> স্টক, টাকা ও হিসাবের খাতা মিলিয়ে দেখা</li><li><Icon name="check" /> ব্যাকআপ থেকে তথ্য ফিরিয়ে আনা আসলেই কাজ করে কিনা তার মহড়া</li><li><Icon name="check" /> bKash/Nagad-এর উত্তর দেরি হলে বা দুইবার এলে কী হয় তার পরীক্ষা</li><li><Icon name="check" /> নিরাপত্তার দুর্বলতা খোঁজা ও সমস্যা হলে কী করতে হবে তার পরিকল্পনা</li><li><Icon name="check" /> আসল ব্যবসার মতো পরিস্থিতি দিয়ে পরীক্ষা</li></ul></div></section>
      <section className="public-section"><SectionHead eyebrow="সত্য অবস্থা" title="এই পাতা কোনো সার্টিফিকেট না" text="এনবিআর, বাংলাদেশ ব্যাংক বা অন্য কোনো নিয়ন্ত্রক সংস্থার অনুমোদন লাগলে, সেটার জন্য যোগ্য আইনজীবী বা হিসাববিদের মাধ্যমে আলাদাভাবে যাচাই করিয়ে নিতে হবে — এই সিস্টেম নিজে থেকে সেই নিশ্চয়তা দেয় না।" /><div className="public-notice"><Icon name="shield" /><div><b>পাসওয়ার্ড ও গোপন তথ্যের নিরাপত্তা</b><p>bKash/Nagad-এর মতো পেমেন্ট প্রতিষ্ঠানের গোপন চাবি (API key) ইন্টারনেট থেকে সরাসরি নেওয়া যায় না — ব্যবসার মালিক নিজে সেই প্রতিষ্ঠানের সাথে চুক্তি করার পরেই এটা নিরাপদভাবে যুক্ত করা হয়।</p></div></div></section>
      <CtaBand />
    </>
  );
}

function AboutPage() {
  const site = useSiteContent();
  return (
    <>
      <PageHero eyebrow={site.get("about.eyebrow", "আমরা কেন এটা বানাচ্ছি")} title={site.get("about.title", "বাংলাদেশের ব্যবসার বাস্তব কাজ দেখে তৈরি")} text={site.get("about.text", "ছোট্ট একটা দোকান থেকে শুরু করে একাধিক শাখার ব্যবসা পর্যন্ত — দৈনিক কাজ, মানুষ, টাকা আর বুদ্ধিমান পরামর্শ, সব একটা বিশ্বস্ত জায়গায় রাখাই আমাদের লক্ষ্য।")} />
      <section className="public-section"><div className="about-grid">{site.getJson("about_values.items", ABOUT_VALUES_DEFAULT).map((v) => <div key={v.num}><span>{v.num}</span><h3>{v.title}</h3><p>{v.text}</p></div>)}</div></section>
      <section className="public-section public-people-story"><div><img src={site.get("about.image_src","https://www.undp.org/sites/g/files/zskgke326/files/migration/bd/swapno1.jpg")} alt={site.get("about.image_alt","বাংলাদেশের একজন ক্ষুদ্র উদ্যোক্তা দোকানের হিসাব করছেন")} loading="lazy" referrerPolicy="no-referrer" /><a href={site.get("about.image_link","https://www.undp.org/bangladesh/blog/mitu-hasina-and-jamila-champions-womens-empowerment")} target="_blank" rel="noreferrer">ছবি: {site.get("about.image_credit","UNDP Bangladesh")}</a></div><div><SectionHead align="left" eyebrow={site.get("about_audience.eyebrow","আমরা যাদের জন্য বানাচ্ছি")} title={site.get("about_audience.title","যারা খাতা, ফোন আর ক্যাশ বাক্সের উপর ভরসা করে ব্যবসা চালান")} text={site.get("about_audience.text","আপনাকে নতুন ভাষা শিখতে হবে না। আমরা আপনার কাজের প্রমাণ এক জায়গায় এনে ভুল আর অপেক্ষা কমাই। ব্যবসা বাড়লে একই জায়গায় আরও নিয়ন্ত্রণ যোগ হবে।")} /><ul className="check-list"><li><Icon name="check" /> একটা দোকান থেকে একাধিক শাখা পর্যন্ত</li><li><Icon name="check" /> পণ্য বিক্রি, সেবা বা দুটোই একসাথে</li><li><Icon name="check" /> একই ডিভাইস কয়েকজন ব্যবহার করলেও কে কী করলো বোঝা যায়</li><li><Icon name="check" /> ইন্টারনেট দুর্বল হলেও সত্যি অবস্থা দেখায়, লুকায় না</li></ul></div></section>
      <section className="public-section public-tint"><div className="split-feature"><div><SectionHead align="left" eyebrow={site.get("about_ai.eyebrow","দায়িত্বশীল AI")} title={site.get("about_ai.title","যে পরামর্শ বোঝা যায়, সেটাই দেই")} text={site.get("about_ai.text","সহজ হিসাব যথেষ্ট হলে জটিল মডেল ব্যবহার করি না। প্রতিটা পরামর্শের সাথে কতটা নিশ্চিত আর কীসের ভিত্তিতে বলা হচ্ছে তা দেখানো হয়।")} /></div><div className="research-card"><Icon name="target" size={30} /><b>{site.get("about_ai.cycle_title","পরামর্শ থেকে শেখা পর্যন্ত চক্র")}</b><p>{site.get("about_ai.cycle_text","পরামর্শ দেওয়া হয় → মালিক সিদ্ধান্ত নেন → কাজ হয় → ফলাফল মাপা হয় → মডেল আরও ভালো হয়")}</p></div></div></section>
      <CtaBand />
    </>
  );
}

function HelpPage() {
  const site = useSiteContent();
  const faqItems = site.getJson("faq_items", FAQ);
  return (
    <>
      <PageHero eyebrow={site.get("help.eyebrow", "সহায়তা কেন্দ্র")} title={site.get("help.title", "শুরু করার আগে উত্তর খুঁজুন")} text={site.get("help.text", "Account, setup, payment, offline এবং product scope সম্পর্কে পরিষ্কার উত্তর।")} />
      <section className="public-section"><div className="help-grid"><Link to="/signup"><Icon name="zap" /><b>নতুন ব্যবসা শুরু</b><span>অ্যাকাউন্ট খুলে শুরু করা</span></Link><Link to="/login"><Icon name="key" /><b>লগইন সহায়তা</b><span>অ্যাকাউন্টে ঢুকতে সমস্যা</span></Link><Link to="/features"><Icon name="sliders" /><b>ফিচার গাইড</b><span>কোন অংশ কী কাজ করে</span></Link><Link to="/security"><Icon name="shield" /><b>নিরাপত্তা ও তথ্য</b><span>কীভাবে নিরাপদ রাখা হয়</span></Link></div><div className="faq-list">{faqItems.map(([q, a]) => <details key={q}><summary>{q}<Icon name="chevronDown" /></summary><p>{a}</p></details>)}</div></section>
      <CtaBand />
    </>
  );
}

function GuidelinesPage() {
  const site = useSiteContent();
  const roleGuides = site.getJson("role_guides", ROLE_GUIDES);
  const [role, setRole] = useState("owner");
  const guide = roleGuides.find((item) => item.id === role) || roleGuides[0];
  return (
    <>
      <PageHero eyebrow={site.get("guidelines.eyebrow", "ভূমিকা অনুযায়ী ব্যবহারবিধি")} title={site.get("guidelines.title", "কে কোন কাজ, কখন ও কীভাবে করবে")} text={site.get("guidelines.text", "নিজের ভূমিকা বেছে নিন। প্রতিটা মানুষের প্রথম পাতা, দৈনিক কাজের ধাপ এবং কতটুকু দেখতে-করতে পারবেন তা আলাদা করে দেখুন।")} />
      <section className="public-section guideline-layout">
        <aside className="guideline-roles" aria-label="ব্যবহারকারীর ধরন">
          <small>আপনার ভূমিকা</small>
          {roleGuides.map((item) => <button type="button" key={item.id} className={role === item.id ? "active" : ""} onClick={() => setRole(item.id)}><Icon name={item.icon} /><span>{item.name}</span><Icon name="chevronRight" /></button>)}
        </aside>
        <div className="guideline-content">
          <div className="guideline-head"><span><Icon name={guide.icon} size={26} /></span><div><small>লগইন করলে প্রথম পাতা · {guide.start}</small><h2>{guide.name} ব্যবহারবিধি</h2><p>{guide.goal}</p></div></div>
          <div className="guideline-steps">{guide.steps.map(([title, path, text], index) => <article key={title}><i>{index + 1}</i><div><small>{path}</small><h3>{title}</h3><p>{text}</p></div></article>)}</div>
          <div className="guideline-features"><h3>এই actor এর প্রধান feature</h3><div>{guide.features.map((x) => <span key={x}><Icon name="check" />{x}</span>)}</div></div>
          <div className="guideline-rule"><Icon name="shield" /><div><b>নিরাপত্তার নিয়ম</b><p>শুধু মেনুতে কিছু দেখা যাওয়া মানেই সেটা করার অনুমতি থাকা না — প্রতিটা কাজ সার্ভারেও আবার যাচাই করা হয়, যাতে ভুল করে কেউ অননুমোদিত কাজ করতে না পারে।</p></div></div>
        </div>
      </section>
      <section className="public-section public-tint"><SectionHead eyebrow="সবার জন্য একই পথ" title="প্রতিটা মানুষের শুরুটা একইভাবে সহজ" /><div className="public-flow"><div><b>লগইন</b><span>পরিচয় ও নিরাপত্তা যাচাই</span></div><Icon name="chevronRight" /><div><b>ব্যবসা</b><span>কোন ব্যবসার সদস্য</span></div><Icon name="chevronRight" /><div><b>শাখা</b><span>কোন শাখায় কাজ করেন</span></div><Icon name="chevronRight" /><div><b>নিজের পাতা</b><span>যতটুকু অনুমতি ততটুকু দেখা</span></div><Icon name="chevronRight" /><div><b>আমার কাজ</b><span>কাজ ও হস্তান্তর</span></div></div></section>
      <CtaBand />
    </>
  );
}

function ContactPage() {
  const site = useSiteContent();
  return (
    <>
      <PageHero eyebrow={site.get("contact.eyebrow", "যোগাযোগ")} title={site.get("contact.title", "আপনার জন্য সবচেয়ে ভালো পথ বেছে নিন")} text={site.get("contact.text", "এখনো ইমেইল/ফোনে সরাসরি সাপোর্ট চালু হয়নি। তাই মিথ্যা করে একটি বার্তা পাঠানো হয়েছে না দেখিয়ে, যা সত্যিই কাজ করে সেই পথ দেখাচ্ছি।")} />
      <section className="public-section"><div className="contact-grid">{site.getJson("contact.cards", CONTACT_CARDS_DEFAULT).map((c) => <article key={c.title}><span><Icon name={c.icon} /></span><h3>{c.title}</h3><p>{c.text}</p>{c.ghost ? <Link className="public-ghost" to={c.link_to}>{c.link_label}</Link> : <Link className="public-cta" to={c.link_to}>{c.link_label}</Link>}</article>)}</div><div className="public-notice warn"><Icon name="alert" /><div><b>{site.get("contact.notice_title","এখনো চালু হয়নি")}</b><p>{site.get("contact.notice_text","পাবলিক ইমেইল বা ফোন সাপোর্ট এখনো চালু করা হয়নি। চালু না হওয়া পর্যন্ত মিথ্যা করে পাঠানো হয়েছে দেখানো হবে না।")}</p></div></div></section>
    </>
  );
}

function PrivacyPage() {
  const site = useSiteContent();
  return (
    <>
      <PageHero eyebrow={site.get("privacy.eyebrow", "গোপনীয়তা")} title={site.get("privacy.title", "যতটুকু দরকার, ততটুকুই তথ্য নেওয়া হয়")} text={site.get("privacy.text", "এই পাতাটা এখনো খসড়া। চূড়ান্ত হওয়ার আগে আইনজীবী দিয়ে যাচাই করানো হবে।")} />
      <section className="public-section legal-copy">
        {site.getJson("privacy.sections", PRIVACY_SECTIONS_DEFAULT).map((s) => <article key={s.heading}><h2>{s.heading}</h2><p>{s.body}</p></article>)}
        <div className="public-notice warn"><Icon name="alert" /><div><b>এটা খসড়া</b><p>এটা আইনি পরামর্শ বা চূড়ান্ত চুক্তি না। সত্যিকার ব্যবহারের আগে বাংলাদেশের আইনজীবী দিয়ে অনুমোদন করিয়ে নিতে হবে।</p></div></div>
      </section>
    </>
  );
}

function TermsPage() {
  const site = useSiteContent();
  return (
    <>
      <PageHero eyebrow={site.get("terms.eyebrow", "শর্তাবলি")} title={site.get("terms.title", "সিস্টেম কী করবে, আর কী করবে না")} text={site.get("terms.text", "চূড়ান্ত ব্যবসায়িক শর্ত ঠিক না হওয়া পর্যন্ত কোনো কাল্পনিক প্রতিশ্রুতি এখানে দেওয়া হয়নি।")} />
      <section className="public-section legal-copy">
        {site.getJson("terms.sections", TERMS_SECTIONS_DEFAULT).map((s) => <article key={s.heading}><h2>{s.heading}</h2><p>{s.body}</p></article>)}
      </section>
    </>
  );
}

function StatusPage() {
  const site = useSiteContent();
  return (
    <>
      <PageHero eyebrow={site.get("status.eyebrow","সিস্টেমের অবস্থা")} title={site.get("status.title","না মেপে মিথ্যা সংখ্যা দেখাই না")} text={site.get("status.text","এই সার্ভার এখনো কোনো uptime মনিটরিং সিস্টেমের সাথে যুক্ত না।")} />
      <section className="public-section status-page">
        <div className="status-summary"><span><i /> {site.get("status.summary_label","সার্ভার চালু আছে")}</span><small>{site.get("status.monitoring_note","বাইরের monitoring এখনো যুক্ত করা হয়নি")}</small></div>
        <div className="status-components">{site.getJson("status.components", STATUS_COMPONENTS_DEFAULT).map(([name, detail]) => <article key={name}><div><i /><b>{name}</b></div><p>{detail}</p><span>নজরদারি প্রয়োজন</span></article>)}</div>
        <div className="public-notice"><Icon name="info" /><div><b>{site.get("status.notice_title","আসল ব্যবহারের আগে যা লাগবে")}</b><p>{site.get("status.notice_text","স্বাধীন নজরদারি ব্যবস্থা, আগের সমস্যার ইতিহাস ও রক্ষণাবেক্ষণের সময়সূচি যুক্ত হলে এই পাতা সত্যিকার অবস্থা দেখাবে।")}</p></div></div>
      </section>
    </>
  );
}

function PageHero({ eyebrow, title, text, ctaPrimary, ctaSecondary }) {
  const site = useSiteContent();
  return <section className="public-pagehero"><span>{eyebrow}</span><h1>{title}</h1><p>{text}</p><div><Link className="public-cta" to="/signup">{ctaPrimary || site.get("pagehero.cta_primary", "শুরু করুন")} <Icon name="chevronRight" /></Link><Link className="public-ghost" to="/solutions">{ctaSecondary || site.get("pagehero.cta_secondary", "ব্যবসার ধরন দেখুন")}</Link></div></section>;
}

function CtaBand() {
  const site = useSiteContent();
  return (
    <section className="public-section cta-band">
      <SectionHead eyebrow={site.get("cta_band.eyebrow", "শুরু করার সময় এখনই")} title={site.get("cta_band.title", "আপনার ব্যবসা নিয়ে আলাদা করে ভাবা হয়েছে")} text={site.get("cta_band.text", "ছোট দোকান থেকে একাধিক শাখার ব্যবসা — যেখান থেকেই শুরু করুন, সিস্টেম আপনার সাথে বাড়বে।")} />
      <div className="public-hero-actions"><Link className="public-cta large" to="/signup">{site.get("cta_band.cta_primary", "বিনামূল্যে শুরু করুন")} <Icon name="chevronRight" /></Link><Link className="public-ghost large" to="/solutions">{site.get("cta_band.cta_secondary", "ব্যবসার ধরন দেখুন")}</Link></div>
    </section>
  );
}

export default function PublicSite() {
  const { pathname } = useLocation();
  const site = useSiteContent();
  const siteName = site.get("meta.title", "B-SMART");
  const siteDesc = site.get("meta.description", "বাংলাদেশের SME এর জন্য বিক্রি, স্টক, হিসাব, কর্মী, ডেলিভারি ও ব্যাখ্যাসহ সিদ্ধান্ত সহায়তার connected Business OS।");
  useEffect(() => {
    const labels = {
      "/": "বাংলাদেশের SME Business OS", "/features": "ফিচার", "/solutions": "ব্যবসার Solution",
      "/pricing": "মূল্য পরিকল্পনা", "/security": "নিরাপত্তা", "/about": "আমাদের কথা",
      "/help": "সহায়তা", "/guidelines": "ব্যবহারবিধি", "/contact": "যোগাযোগ",
      "/privacy": "গোপনীয়তা", "/terms": "শর্তাবলি", "/status": "System Status",
    };
    const title = pathname.startsWith("/solutions/") ? "ব্যবসার Solution" : labels[pathname] || siteName;
    document.title = `${title} · ${siteName}`;
    const description = document.querySelector('meta[name="description"]');
    if (description) description.setAttribute("content", siteDesc);
    return () => { document.title = siteName; };
  }, [pathname, siteName, siteDesc]);
  let page = <HomePage />;
  if (pathname === "/features") page = <FeaturesPage />;
  else if (pathname === "/solutions") page = <SolutionsPage />;
  else if (pathname.startsWith("/solutions/")) page = <SolutionsPage slug={pathname.split("/")[2]} />;
  else if (pathname === "/pricing") page = <PricingPage />;
  else if (pathname === "/security") page = <SecurityPage />;
  else if (pathname === "/about") page = <AboutPage />;
  else if (pathname === "/help") page = <HelpPage />;
  else if (pathname === "/guidelines") page = <GuidelinesPage />;
  else if (pathname === "/contact") page = <ContactPage />;
  else if (pathname === "/privacy") page = <PrivacyPage />;
  else if (pathname === "/terms") page = <TermsPage />;
  else if (pathname === "/status") page = <StatusPage />;
  return <PublicFrame>{page}</PublicFrame>;
}
