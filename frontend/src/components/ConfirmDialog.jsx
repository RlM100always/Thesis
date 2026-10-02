// A typo in a stock-adjustment or delete action used to apply instantly with
// no way back. This asks once, in plain Bangla, before anything destructive
// or hard-to-reverse actually runs.
//
// Usage: const confirm = useConfirm();
//        const ok = await confirm("স্টক থেকে ৮ ইউনিট বাদ যাবে। নিশ্চিত?");
//        if (ok) { ...do the thing... }

import { useCallback, useEffect, useRef, useState } from "react";

export function useConfirm() {
  const [prompt, setPrompt] = useState(null);
  const resolver = useRef(null);
  const dialogRef = useRef(null);
  const previousFocus = useRef(null);

  useEffect(() => {
    if (!prompt) {
      previousFocus.current?.focus?.();
      previousFocus.current = null;
      return undefined;
    }
    previousFocus.current = document.activeElement;
    const timer = window.setTimeout(() => dialogRef.current?.querySelector("button")?.focus(), 0);
    return () => window.clearTimeout(timer);
  }, [prompt]);

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

  const onKeyDown = useCallback((event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      resolve(false);
      return;
    }
    if (event.key !== "Tab") return;
    const controls = [...dialogRef.current?.querySelectorAll("button:not([disabled])") || []];
    if (!controls.length) return;
    const first = controls[0];
    const last = controls.at(-1);
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }, [resolve]);

  const dialog = prompt ? (
    <div className="confirm-overlay" role="presentation">
      <div ref={dialogRef} className="confirm-box" role="alertdialog" aria-modal="true" aria-labelledby="confirm-dialog-message" onKeyDown={onKeyDown}>
        <p id="confirm-dialog-message">{prompt}</p>
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
