// A typo in a stock-adjustment or delete action used to apply instantly with
// no way back. This asks once, in plain Bangla, before anything destructive
// or hard-to-reverse actually runs.
//
// Usage: const confirm = useConfirm();
//        const ok = await confirm("স্টক থেকে ৮ ইউনিট বাদ যাবে। নিশ্চিত?");
//        if (ok) { ...do the thing... }

import { useCallback, useRef, useState } from "react";

export function useConfirm() {
  const [prompt, setPrompt] = useState(null);
  const resolver = useRef(null);

  const confirm = useCallback((message) => {
    setPrompt(message);
    return new Promise((resolve) => {
      resolver.current = resolve;
    });
  }, []);

  const resolve = useCallback((value) => {
    setPrompt(null);
    resolver.current?.(value);
  }, []);

  const dialog = prompt ? (
    <div className="confirm-overlay" role="alertdialog" aria-modal="true">
      <div className="confirm-box">
        <p>{prompt}</p>
        <div className="confirm-actions">
          <button type="button" className="btn-secondary" onClick={() => resolve(false)}>
            বাতিল
          </button>
          <button type="button" className="btn-danger" onClick={() => resolve(true)}>
            নিশ্চিত করুন
          </button>
        </div>
      </div>
    </div>
  ) : null;

  return Object.assign(confirm, { dialog });
}
