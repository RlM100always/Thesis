// Distinguishes a trained-model prediction from the transparent baseline
// (api/analytics_routes.py returns confidence: "model" | "baseline" on every
// recommendation). Never shown identically — this is the UI proof of the
// thesis's "AI-powered" claim, not just a backend field nobody sees.

export function ConfidenceBadge({ confidence }) {
  if (confidence === "model") {
    return <span className="badge-confidence model">প্রশিক্ষিত মডেল</span>;
  }
  return <span className="badge-confidence baseline">সাধারণ হিসাব</span>;
}
