import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { useBusiness } from "../BusinessContext";
import { explain } from "../errors";
import { ROLE_LABELS } from "../PermissionContext";
import Icon from "../ui/Icon";
import { Avatar, Badge, Button, Card, EmptyState, Notice, PageHeader, Skeleton } from "../ui/kit";

// What each action is called for an owner. Unknown actions fall back to the raw
// name rather than disappearing, so a new action is visible before it is translated.
const ACTIONS = {
  "organization.created": ["ব্যবসা তৈরি হয়েছে", "sliders"],
  "product.created": ["নতুন পণ্য যোগ", "tag"],
  "inventory.adjusted": ["স্টক সমন্বয়", "box"],
  "product.expiry_tracking_enabled": ["মেয়াদ ট্র্যাকিং চালু", "clock"],
  "batch.blocked": ["ব্যাচ বন্ধ (বিক্রি হবে না)", "ban"],
  "batch.released": ["ব্যাচ আবার চালু", "check"],
  "sale.created": ["বিক্রি", "cart"],
  "sale.returned": ["রিটার্ন", "undo"],
  "purchase.created": ["ক্রয়ের অর্ডার", "truck"],
  "purchase.received": ["মাল রিসিভ", "truck"],
  "supplier.created": ["নতুন সাপ্লায়ার", "users"],
  "supplier.paid": ["সাপ্লায়ারকে পেমেন্ট", "card"],
  "customer.created": ["নতুন কাস্টমার", "users"],
  "customer.paid": ["কাস্টমারের বাকি আদায়", "card"],
  "expense.created": ["খরচ লেখা", "card"],
  "branch.created": ["নতুন শাখা", "sliders"],
  "staff.invited": ["কর্মী যোগ", "userCheck"],
  "staff.role_changed": ["ভূমিকা বদল", "userCheck"],
  "staff.deactivated": ["প্রবেশ বন্ধ", "lock"],
  "staff.reactivated": ["প্রবেশ চালু", "userCheck"],
  "staff.setup_link_issued": ["পাসওয়ার্ড লিংক তৈরি", "link"],
  "import.uploaded": ["ফাইল আপলোড", "upload"],
  "dataset.exported": ["ডেটা এক্সপোর্ট", "upload"],
  "model.trained": ["AI মডেল প্রশিক্ষণ", "zap"],
  "bsmart.imported": ["সুপারিশ আনা হয়েছে", "target"],
  "bsmart.decided": ["সুপারিশে সিদ্ধান্ত", "target"],
  "bsmart.outcome_recorded": ["ফলাফল লেখা হয়েছে", "target"],
};

// Sensitive or bulk-data actions get a warmer badge so they stand out in a long list.
const NOTABLE = new Set(["batch.blocked", "dataset.exported", "staff.role_changed", "staff.deactivated", "staff.setup_link_issued", "supplier.paid"]);

const FILTERS = [
  { key: "all", label: "সব", actions: "" },
  { key: "staff", label: "কর্মী", actions: "staff." },
  { key: "sales", label: "বিক্রি ও রিটার্ন", actions: "sale." },
  { key: "stock", label: "স্টক ও ক্রয়", actions: "inventory.,purchase.,product.,supplier.created,batch." },
  { key: "money", label: "টাকা-পয়সা", actions: "supplier.paid,customer.paid,expense." },
  { key: "data", label: "ডেটা ও AI", actions: "import.,dataset.,model." },
  { key: "reco", label: "সুপারিশ", actions: "bsmart." },
];

const DECISIONS = { accept: "গ্রহণ", reject: "বাতিল", modify: "পরিবর্তন", defer: "পরে" };
const KEYS = {
  role: "ভূমিকা", amount: "পরিমাণ", total: "মোট", method: "মাধ্যম", category: "ধরন", rows: "সারি",
  filename: "ফাইল", decision: "সিদ্ধান্ত", modified_quantity: "নতুন পরিমাণ", order_number: "অর্ডার নং",
  code: "কোড", cutoff: "তারিখ", recommendations: "সুপারিশ", marketing_consent: "মার্কেটিং সম্মতি",
  quantity: "পরিমাণ", reason: "কারণ", source: "উৎস", active: "সক্রিয়",
  batch_no: "ব্যাচ", opening_units: "প্রারম্ভিক স্টক",
};

const when = new Intl.DateTimeFormat("bn-BD", { dateStyle: "medium", timeStyle: "short" });

function value(key, raw) {
  if (Array.isArray(raw)) {
    return raw.map((v) => value(key, v)).join(" → ");
  }
  if (key === "role") return ROLE_LABELS[raw] || raw;
  if (key === "decision") return DECISIONS[raw] || raw;
  if (typeof raw === "boolean") return raw ? "হ্যাঁ" : "না";
  if ((key === "amount" || key === "total") && !Number.isNaN(Number(raw))) {
    return `৳ ${Number(raw).toLocaleString("bn-BD")}`;
  }
  return String(raw);
}

function Details({ details }) {
  const entries = Object.entries(details || {}).filter(([, v]) => v !== null && v !== "");
  if (!entries.length) return null;
  return (
    <div className="audit-details">
      {entries.map(([k, v]) => (
        <span key={k}><em>{KEYS[k] || k}</em> {value(k, v)}</span>
      ))}
    </div>
  );
}

export default function AuditPage() {
  const { active } = useBusiness();
  const orgId = active?.id;
  const [filter, setFilter] = useState("all");
  const [items, setItems] = useState(null);
  const [cursor, setCursor] = useState(null);
  const [error, setError] = useState("");
  const [loadingMore, setLoadingMore] = useState(false);
  const actions = FILTERS.find((f) => f.key === filter).actions;

  const load = useCallback(async () => {
    if (!orgId) return;
    setItems(null);
    try {
      const page = await api.audit(orgId, { actions });
      setItems(page.items);
      setCursor(page.next_cursor);
      setError("");
    } catch (e) {
      setError(explain(e, { 403: "কার্যকলাপের ইতিহাস শুধু মালিক ও ম্যানেজার দেখতে পারেন।" }));
      setItems([]);
    }
  }, [orgId, actions]);

  useEffect(() => { load(); }, [load]);

  async function more() {
    setLoadingMore(true);
    try {
      const page = await api.audit(orgId, { actions, cursor });
      setItems((current) => [...current, ...page.items]);
      setCursor(page.next_cursor);
    } catch (e) {
      setError(explain(e));
    } finally {
      setLoadingMore(false);
    }
  }

  return (
    <div className="page stack">
      <PageHeader
        title="কার্যকলাপের ইতিহাস"
        subtitle="কে, কখন, কী করেছেন — এখানে সব লেখা থাকে। এই তালিকা কেউ মুছতে বা বদলাতে পারে না।"
      />

      <div className="audit-filters" role="tablist" aria-label="ধরন অনুযায়ী দেখুন">
        {FILTERS.map((f) => (
          <button key={f.key} type="button" role="tab" aria-selected={filter === f.key}
                  className={filter === f.key ? "on" : ""} onClick={() => setFilter(f.key)}>
            {f.label}
          </button>
        ))}
      </div>

      {error && <Notice tone="danger" action={<Button size="sm" variant="secondary" onClick={load}>আবার চেষ্টা</Button>}>{error}</Notice>}

      {!(error && items?.length === 0) && <Card pad={false}>
        {items === null ? (
          <div style={{ padding: 24 }}><Skeleton lines={5} height={18} /></div>
        ) : items.length === 0 ? (
          <EmptyState icon="clock" title="এখনো কিছু লেখা হয়নি"
                      hint={filter === "all" ? "কেউ কিছু করলে এখানে দেখা যাবে।" : "এই ধরনের কোনো কাজ এখনো হয়নি।"} />
        ) : (
          <ol className="audit-list">
            {items.map((entry) => {
              const [label, icon] = ACTIONS[entry.action] || [entry.action, "info"];
              return (
                <li key={entry.id}>
                  <span className={`audit-icon${NOTABLE.has(entry.action) ? " notable" : ""}`}><Icon name={icon} size={18} /></span>
                  <div className="audit-main">
                    <div className="audit-line">
                      <strong>{label}</strong>
                      {NOTABLE.has(entry.action) && <Badge tone="warn">সংবেদনশীল</Badge>}
                    </div>
                    <Details details={entry.details} />
                    <div className="audit-who">
                      {entry.actor ? (
                        <><Avatar name={entry.actor.name} size={20} /> {entry.actor.name}</>
                      ) : "সিস্টেম"}
                    </div>
                  </div>
                  <time dateTime={entry.created_at} title={entry.created_at}>{when.format(new Date(entry.created_at))}</time>
                </li>
              );
            })}
          </ol>
        )}
        {cursor && items && (
          <div style={{ padding: 16, textAlign: "center" }}>
            <Button variant="secondary" loading={loadingMore} onClick={more}>আরও দেখান</Button>
          </div>
        )}
      </Card>}
    </div>
  );
}
