// The uploaded file, held for the whole session.
//
// Once a file is uploaded and mapped, every business page reads from it instead
// of the research dataset. Without this the upload page is an island: the owner
// sees their own customers on one screen and someone else's revenue on the next.
//
// Stored in sessionStorage so a refresh keeps the workspace, but closing the tab
// clears it — the server holds the frame in memory anyway (upload_service
// evicts after 5 sessions), so a token that outlived the process would only
// produce confusing "upload has expired" errors.

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

const WorkspaceContext = createContext(null);
const KEY = "workspace";

function load() {
  try {
    const raw = sessionStorage.getItem(KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function WorkspaceProvider({ children }) {
  const [workspace, setWorkspace] = useState(load);

  useEffect(() => {
    try {
      if (workspace) sessionStorage.setItem(KEY, JSON.stringify(workspace));
      else sessionStorage.removeItem(KEY);
    } catch { /* storage disabled */ }
  }, [workspace]);

  const open = useCallback(
    ({ token, mapping, filename, rowCount }) =>
      setWorkspace({ token, mapping, filename, rowCount }),
    [],
  );
  const close = useCallback(() => setWorkspace(null), []);

  const value = useMemo(
    () => ({ workspace, hasData: !!workspace, open, close }),
    [workspace, open, close],
  );

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useWorkspace() {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error("useWorkspace must be used inside <WorkspaceProvider>");
  return ctx;
}
