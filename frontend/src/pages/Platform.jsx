// Platform super-admin: every tenant on this deployment, read-only.
// Gated server-side by User.is_platform_admin (never settable through any
// API) -- this page is reachable in the UI only for an account already
// carrying that flag; api.platformOrganizations()/platformSummary() return
// 403 for anyone else regardless of what this page renders.
import { useEffect, useState } from "react";
import { api } from "../api";
import { explain } from "../errors";
import { dateBn } from "../format";
import DataTable from "../ui/DataTable";
import { Notice, PageHeader, Skeleton, Stat } from "../ui/kit";

export default function PlatformPage() {
  const [summary, setSummary] = useState(null);
  const [orgs, setOrgs] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api.platformSummary(), api.platformOrganizations()])
      .then(([s, o]) => { setSummary(s); setOrgs(o.organizations); })
      .catch((e) => setError(explain(e)));
  }, []);

  return (
    <div className="page stack">
      <PageHeader title="প্ল্যাটফর্ম" subtitle="এই ডেপ্লয়মেন্টের সব ব্যবসা — শুধু দেখার জন্য, কোনো ব্যবসার ডেটা এখান থেকে বদলানো যায় না।" />
      {error && <Notice tone="danger">{error}</Notice>}

      {!summary ? <Skeleton lines={2} height={60} /> : (
        <div className="ui-stats">
          <Stat label="মোট ব্যবসা" value={summary.organizations_total} />
          <Stat label="সক্রিয় ব্যবসা" value={summary.organizations_active} />
          <Stat label="মোট ব্যবহারকারী" value={summary.users_total} />
          <Stat label="মোট বিক্রির চালান" value={summary.sales_orders_total} />
        </div>
      )}

      <DataTable
        rowKey="id" loading={orgs === null} rows={orgs || []} caption="ব্যবসার তালিকা"
        columns={[
          { key: "name", label: "ব্যবসা", primary: true, render: (o) => <div><strong>{o.name}</strong><div className="muted" style={{ fontSize: 12.5 }}>{o.slug} · {o.sector}</div></div> },
          { key: "active", label: "অবস্থা", render: (o) => (o.active ? "সক্রিয়" : "বন্ধ") },
          { key: "members", label: "সদস্য", align: "right", render: (o) => o.member_count },
          { key: "branches", label: "শাখা", align: "right", render: (o) => o.branch_count },
          { key: "products", label: "পণ্য", align: "right", render: (o) => o.product_count },
          { key: "last_sale", label: "শেষ বিক্রি", render: (o) => (o.last_sale_at ? dateBn(o.last_sale_at) : "কখনো না") },
          { key: "created", label: "তৈরি হয়েছে", render: (o) => dateBn(o.created_at) },
        ]}
      />
    </div>
  );
}
