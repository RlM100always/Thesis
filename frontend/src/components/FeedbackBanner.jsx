// Success and failure look different, on purpose. Every form used to dump
// both into the same grey <p>{msg}</p> — a shop owner could not tell at a
// glance whether "পণ্য যোগ হয়েছে" was the outcome or "স্টক পাওয়া যায়নি" was.
//
// Usage: const [feedback, setFeedback] = useFeedback();
//        setFeedback({ type: "success", text: "..." })
//        <FeedbackBanner feedback={feedback} />

import { useCallback, useState } from "react";

export function useFeedback() {
  const [feedback, setFeedback] = useState(null);
  const show = useCallback((type, text) => setFeedback({ type, text }), []);
  return [feedback, show];
}

export function FeedbackBanner({ feedback }) {
  if (!feedback) return null;
  const isError = feedback.type === "error";
  return (
    <div className={`feedback-banner ${isError ? "error" : "success"}`} role="status">
      <span className="feedback-icon" aria-hidden="true">{isError ? "✕" : "✓"}</span>
      <span>{feedback.text}</span>
    </div>
  );
}
