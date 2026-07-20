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

export function Loading({ what = "data" }) {
  return <div className="state">Loading {what}…</div>;
}

export function ErrorBox({ message }) {
  return (
    <div className="state error">
      <p><strong>Could not reach the API.</strong></p>
      <p>{message}</p>
      <p style={{ fontSize: 13, color: "var(--text-muted)" }}>
        Start the backend with:<br />
        <code>./.venv312/Scripts/python.exe -m uvicorn api.main:app --reload</code>
      </p>
    </div>
  );
}
