import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "./api";
import { useBusiness } from "./BusinessContext";

const BranchContext = createContext(null);

function storageKey(orgId) { return `activeBranch.${orgId}`; }
function readBranch(orgId) {
  try { return localStorage.getItem(storageKey(orgId)) || ""; } catch { return ""; }
}
function writeBranch(orgId, id) {
  try { localStorage.setItem(storageKey(orgId), id); } catch { /* storage may be unavailable */ }
}

// One branch selection for the entire workspace. Previously every page loaded
// branches independently, so changing branch on Stock did not change Sales or
// Cash. This provider makes the selected branch an application-level invariant.
export function BranchProvider({ children }) {
  const { active } = useBusiness();
  const orgId = active?.id || "";
  const [branches, setBranches] = useState(null);
  const [branch, setBranchState] = useState("");
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    if (!orgId) { setBranches([]); setBranchState(""); return; }
    try {
      const rows = await api.branches(orgId);
      setBranches(rows);
      setBranchState((current) => {
        const remembered = readBranch(orgId);
        const candidate = rows.find((b) => b.id === current)
          || rows.find((b) => b.id === remembered)
          || rows.find((b) => b.code === "MAIN") || rows[0];
        if (candidate) writeBranch(orgId, candidate.id);
        return candidate?.id || "";
      });
      setError("");
    } catch (e) {
      setBranches([]); setError(e.message || "শাখা আনা যায়নি");
    }
  }, [orgId]);

  useEffect(() => { setBranches(null); setBranchState(readBranch(orgId)); refresh(); }, [orgId, refresh]);

  const setBranch = useCallback((id) => {
    if (!branches?.some((row) => row.id === id)) return;
    setBranchState(id); writeBranch(orgId, id);
  }, [branches, orgId]);

  const value = useMemo(() => ({
    organizationId: orgId, branches, branch, setBranch, refresh, error,
    current: branches?.find((b) => b.id === branch) || null,
  }), [orgId, branches, branch, setBranch, refresh, error]);

  return <BranchContext.Provider value={value}>{children}</BranchContext.Provider>;
}

// Keep the old hook signature so every existing page automatically joins the
// shared branch context without a page-by-page rewrite.
export default function useBranch(orgId) {
  const value = useContext(BranchContext);
  if (!value) throw new Error("useBranch must be used inside BranchProvider");
  if (orgId && value.organizationId && orgId !== value.organizationId) {
    return { branches: [], branch: "", setBranch: () => {}, current: null, error: "Business changed" };
  }
  return value;
}
