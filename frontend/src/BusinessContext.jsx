import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "./api";

const BusinessContext = createContext(null);

export function BusinessProvider({ children }) {
  const [organizations, setOrganizations] = useState([]);
  const [activeId, setActiveId] = useState(() => localStorage.getItem("activeOrganization"));
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    try {
      const rows = await api.appOrganizations();
      setOrganizations(rows);
      setActiveId((current) => {
        const next = rows.some((row) => row.id === current) ? current : rows[0]?.id || null;
        if (next) localStorage.setItem("activeOrganization", next);
        return next;
      });
      setError("");
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);
  const select = useCallback((id) => {
    setActiveId(id);
    localStorage.setItem("activeOrganization", id);
  }, []);
  const create = useCallback(async (payload) => {
    const created = await api.createOrganization(payload);
    await refresh();
    select(created.id);
    return created;
  }, [refresh, select]);
  const active = organizations.find((row) => row.id === activeId) || null;
  const value = useMemo(() => ({ organizations, active, loading, error, refresh, select, create }),
    [organizations, active, loading, error, refresh, select, create]);
  return <BusinessContext.Provider value={value}>{children}</BusinessContext.Provider>;
}

export function useBusiness() {
  const value = useContext(BusinessContext);
  if (!value) throw new Error("useBusiness must be used inside BusinessProvider");
  return value;
}
