import { useEffect, useState } from "react";
import { api } from "./api";

// The branches of the active business and the one currently selected.
// Most screens are per-branch; this keeps that choice in one place.
export default function useBranch(orgId) {
  const [branches, setBranches] = useState(null);
  const [branch, setBranch] = useState("");

  useEffect(() => {
    if (!orgId) return undefined;
    let current = true;
    api.branches(orgId)
      .then((rows) => {
        if (!current) return;
        setBranches(rows);
        // Start on the main branch (created with the business), not whichever sorts first by name.
        const main = rows.find((b) => b.code === "MAIN") || rows[0];
        setBranch((existing) => (rows.some((b) => b.id === existing) ? existing : main?.id || ""));
      })
      .catch(() => current && setBranches([]));
    return () => { current = false; };
  }, [orgId]);

  return { branches, branch, setBranch, current: branches?.find((b) => b.id === branch) || null };
}
