import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "./api";
import { verticalOf } from "./verticals";

const BusinessContext = createContext(null);
const KEY = "activeOrganization";

// Storage can be blocked (private window, embedded frame, strict privacy
// settings) and then throws on access. The app must still open, so the last
// chosen business is a convenience, never a requirement.
function readActive() {
  try { return localStorage.getItem(KEY); } catch { return null; }
}
function writeActive(id) {
  try { localStorage.setItem(KEY, id); } catch { /* storage disabled */ }
}

export function BusinessProvider({ children }) {
  const [organizations, setOrganizations] = useState([]);
  const [activeId, setActiveId] = useState(readActive);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    try {
      const rows = await api.appOrganizations();
      setOrganizations(rows);
      setActiveId((current) => {
        const next = rows.some((row) => row.id === current) ? current : rows[0]?.id || null;
        if (next) writeActive(next);
        return next;
      });
      setError("");
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);
  const select = useCallback((id) => {
    setActiveId(id);
    writeActive(id);
  }, []);
  const create = useCallback(async (payload) => {
    const created = await api.createOrganization(payload);
    await refresh();
    select(created.id);
    return created;
  }, [refresh, select]);
  const active = organizations.find((row) => row.id === activeId) || null;
  const vertical = verticalOf(active?.sector);
  // Expiry screens appear for businesses whose goods expire, or as soon as any product tracks it.
  const features = useMemo(() => ({ expiry: vertical.expiry || Boolean(active?.uses_expiry) }), [vertical.expiry, active?.uses_expiry]);
  const value = useMemo(() => ({ organizations, active, vertical, features, loading, error, refresh, select, create }),
    [organizations, active, vertical, features, loading, error, refresh, select, create]);
  return <BusinessContext.Provider value={value}>{children}</BusinessContext.Provider>;
}

export function useBusiness() {
  const value = useContext(BusinessContext);
  if (!value) throw new Error("useBusiness must be used inside BusinessProvider");
  return value;
}
