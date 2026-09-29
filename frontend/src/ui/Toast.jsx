// Transient confirmation ("কর্মী যোগ হয়েছে") without blocking the screen.
// Use a <Notice> for anything the user must act on; a toast disappears.
//
//   const toast = useToast();
//   toast.success("সংরক্ষণ হয়েছে");  toast.error("সংরক্ষণ করা যায়নি");

import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";
import Icon from "./Icon";

const ToastContext = createContext(null);
const LIFETIME_MS = 5000;

export function ToastProvider({ children }) {
  const [items, setItems] = useState([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id) => setItems((list) => list.filter((t) => t.id !== id)), []);
  const push = useCallback((tone, text) => {
    const id = nextId.current++;
    setItems((list) => [...list.slice(-3), { id, tone, text }]);
    setTimeout(() => dismiss(id), LIFETIME_MS);
  }, [dismiss]);

  const api = useMemo(() => ({
    success: (text) => push("success", text),
    error: (text) => push("danger", text),
    info: (text) => push("info", text),
  }), [push]);

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="ui-toasts" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className={`ui-toast ui-toast--${t.tone}`} role={t.tone === "danger" ? "alert" : "status"}>
            <Icon name={t.tone === "success" ? "check" : t.tone === "danger" ? "alert" : "info"} size={18} />
            <span>{t.text}</span>
            <button type="button" className="ui-toast__close" onClick={() => dismiss(t.id)} aria-label="বন্ধ করুন">
              <Icon name="x" size={16} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const value = useContext(ToastContext);
  if (!value) throw new Error("useToast must be used inside ToastProvider");
  return value;
}
