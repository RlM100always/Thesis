import { useEffect, useState } from "react";

// One hook for every page's data fetch, so loading and error states are
// handled identically everywhere instead of being re-invented per page.
//
// `deps` controls refetching; pass the values the fetcher closes over.
export function useApi(fetcher, deps = []) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetcher()
      .then((result) => {
        // Guard against a slow response landing after the user navigated away
        if (!cancelled) setData(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, error, loading };
}

export function Loading({ what = "তথ্য" }) {
  return <div className="state">{what} লোড হচ্ছে…</div>;
}

export function ErrorBox({ message }) {
  return (
    <div className="state error">
      <p><strong>সার্ভারের সাথে সংযোগ করা যায়নি।</strong></p>
      <p>{message}</p>
      <p style={{ fontSize: 13, color: "var(--text-muted)" }}>
        ইন্টারনেট সংযোগ পরীক্ষা করুন, অথবা কিছুক্ষণ পর আবার চেষ্টা করুন।
      </p>
    </div>
  );
}
