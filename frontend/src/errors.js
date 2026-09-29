// The API's messages are English; a shop owner sees Bangla. Errors are matched
// by HTTP status (never by the English text), with per-call overrides for the
// statuses that mean something specific on that screen.
//
//   catch (e) { setError(explain(e, { 409: "এই ইমেইল আগেই যোগ করা আছে।" })); }

const DEFAULTS = {
  400: "অনুরোধটি ঠিক নেই। তথ্য দেখে আবার চেষ্টা করুন।",
  401: "আপনার সেশন শেষ হয়েছে। আবার লগইন করুন।",
  403: "এই কাজটি করার অনুমতি আপনার ভূমিকায় নেই।",
  404: "যা খুঁজছেন তা পাওয়া যায়নি।",
  409: "এই তথ্যের সাথে সংঘর্ষ হয়েছে। পাতাটি নতুন করে খুলে আবার চেষ্টা করুন।",
  422: "কিছু তথ্য ঠিক নেই। ঘরগুলো দেখে আবার দিন।",
  429: "অনেকবার চেষ্টা হয়েছে। কিছুক্ষণ পরে আবার চেষ্টা করুন।",
};
const SERVER = "সার্ভারে সমস্যা হয়েছে। একটু পরে আবার চেষ্টা করুন।";
const OFFLINE = "সার্ভারের সাথে সংযোগ হচ্ছে না। ইন্টারনেট দেখে আবার চেষ্টা করুন।";

export function explain(error, overrides = {}) {
  const status = error?.status;
  if (status === undefined) return OFFLINE; // fetch itself failed: no response at all
  if (overrides[status]) return overrides[status];
  if (status >= 500) return SERVER;
  return DEFAULTS[status] || SERVER;
}
