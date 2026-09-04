// Two app-wide display preferences, both persisted to localStorage.
//
//   mode  "simple" | "technical"  — which vocabulary leads (see glossary.js)
//   theme "light"  | "dark"
//
// Simple is the default: the primary user is a business owner, and the thesis
// metrics stay one click away rather than being removed.

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

const UiContext = createContext(null);

function stored(key, fallback) {
  try {
    return localStorage.getItem(key) ?? fallback;
  } catch {
    // private browsing / storage disabled
    return fallback;
  }
}

export function UiProvider({ children }) {
  const [mode, setMode] = useState(() => stored("ui.mode", "simple"));
  const [theme, setTheme] = useState(() =>
    stored(
      "ui.theme",
      window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light",
    ),
  );

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    try {
      localStorage.setItem("ui.theme", theme);
    } catch { /* storage disabled */ }
  }, [theme]);

  useEffect(() => {
    try {
      localStorage.setItem("ui.mode", mode);
    } catch { /* storage disabled */ }
  }, [mode]);

  const value = useMemo(
    () => ({
      mode,
      theme,
      simple: mode === "simple",
      toggleMode: () => setMode((m) => (m === "simple" ? "technical" : "simple")),
      toggleTheme: () => setTheme((t) => (t === "light" ? "dark" : "light")),
    }),
    [mode, theme],
  );

  return <UiContext.Provider value={value}>{children}</UiContext.Provider>;
}

export function useUi() {
  const ctx = useContext(UiContext);
  if (!ctx) throw new Error("useUi must be used inside <UiProvider>");
  return ctx;
}

/** Pick between a plain-language and a technical string for the current mode. */
export function usePhrase() {
  const { simple } = useUi();
  return useCallback((plain, technical) => (simple ? plain : technical), [simple]);
}
