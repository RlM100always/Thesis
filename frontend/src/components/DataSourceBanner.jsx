// Says whose numbers are on screen.
//
// Without this, a business owner lands on Overview and reads "৳5.28B revenue ·
// 4,996 customers" as their own. Every page that can show either the research
// dataset or an uploaded file renders this at the top, so the question is never
// left open.

import { Link } from "react-router-dom";
import { useWorkspace } from "../WorkspaceContext";

export function DataSourceBanner() {
  const { workspace, hasData, close } = useWorkspace();

  if (hasData) {
    return (
      <div className="source-banner own">
        <span>
          Showing <strong>your business</strong> — {workspace.filename}
          {workspace.rowCount ? ` · ${workspace.rowCount.toLocaleString()} sales` : ""}
        </span>
        <button type="button" className="btn-secondary" onClick={close}>
          Back to sample data
        </button>
      </div>
    );
  }

  return (
    <div className="source-banner sample">
      <span>
        <strong>This is sample data</strong> from the research dataset — not your business.
      </span>
      <Link to="/upload" className="btn-primary btn-sm">Upload your sales file</Link>
    </div>
  );
}
