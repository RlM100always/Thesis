import { useEffect, useMemo, useState } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { useBusiness } from "../BusinessContext";
import { explain } from "../errors";
import { money, num } from "../format";
import { usePermissions } from "../PermissionContext";
import MorningBrief from "../components/MorningBrief";
import Icon from "../ui/Icon";
import { Button, Card, EmptyState, Field, Notice, PageHeader, Skeleton, Stat } from "../ui/kit";
import useBranch from "../useBranch";

const shortDate = new Intl.DateTimeFormat("bn-BD", { day: "numeric", month: "short" });

function Step({ done, n, title, hint, href, action }) {
  return (
    <a className={`step${done ? " done" : ""}`} href={href}>
      <span className="step__badge">{done ? <Icon name="check" size={16} /> : num(n)}</span>
      <span><strong>{title}</strong><small>{hint}</small></span>
      {!done && <span className="step__go">{action} →</span>}
    </a>
  );
}

export default function Dashboard() {
  const { active, features } = useBusiness();
  const { can } = usePermissions();
  const orgId = active?.id;
  const { branches, branch } = useBranch(orgId);
  const [scope, setScope] = useState("");
  const [data, setData] = useState(null);
  const [expiry, setExpiry] = useState(null);
  const [uncosted, setUncosted] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!orgId) return undefined;
    let current = true;
    setData(null);
    api.dashboardApp(orgId, scope)
      .then((d) => { if (current) { setData(d); setError(""); } })
      .catch((e) => current && setError(explain(e)));
    return () => { current = false; };
  }, [orgId, scope]);

  // Two extras that need other permissions: silently skipped when the role lacks them.
  useEffect(() => {
    if (!orgId || !branch) return;
    if (features.expiry && can("inventory:read")) api.expirySummary(orgId, scope || branch).then(setExpiry).catch(() => setExpiry(null));
    if (can("catalog:read")) {
      api.productsApp(orgId)
        .then((rows) => setUncosted(rows.filter((p) => Number(p.cost_price) <= 0).length))
        .catch(() => setUncosted(0));
    }
  }, [orgId, branch, scope, can, features.expiry]);

  const chart = useMemo(() => (data?.daily_sales || []).map((d) => ({ ...d, label: shortDate.format(new Date(d.date)) })), [data]);

  if (!active) return null;
  const isNew = data && data.product_count === 0;
  const atRisk = expiry ? Number(expiry.at_risk_value) : 0;
  const partialCost = data && data.cost_coverage !== null && data.cost_coverage < 0.999;

  return (
    <div className="page stack">
      <PageHeader
        title="ব্যবসার ড্যাশবোর্ড"
        subtitle={`${active.name} · গত ৩০ দিনের প্রকৃত হিসাব`}
        actions={branches && branches.length > 1 && (
          <Field label="শাখা"><select value={scope} onChange={(e) => setScope(e.target.value)}>
            <option value="">সব শাখা</option>
            {branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select></Field>
        )}
      />
      {error && <Notice tone="danger" action={<Button size="sm" variant="secondary" onClick={() => setScope((s) => s)}>আবার চেষ্টা</Button>}>{error}</Notice>}

      {!data ? (
        <div className="ui-stats">{[0, 1, 2, 3].map((i) => <Skeleton key={i} lines={2} height={34} />)}</div>
      ) : (
        <>
          {!isNew && <MorningBrief />}

          {isNew && (
            <Card className="setup-card" title="শুরু করুন — ৪টি ধাপে প্রস্তুত" subtitle="প্রথম বিক্রি পর্যন্ত পৌঁছাতে এই ধাপগুলো সারুন।">
              <div className="steps">
                <Step n={1} done={data.product_count > 0} title="পণ্য যোগ করুন" hint="নাম, দাম, মেয়াদ ট্র্যাক করবেন কিনা" href="#/products" action="পণ্য যোগ" />
                <Step n={2} done={data.supplier_count > 0} title="সাপ্লায়ার যোগ করুন" hint="কার কাছ থেকে মাল কেনেন" href="#/directory" action="সাপ্লায়ার" />
                <Step n={3} done={Number(data.stock_value_at_cost) > 0} title="মাল কিনে স্টকে তুলুন" hint="ক্রয় অর্ডার দিয়ে মাল রিসিভ করুন" href="#/purchases" action="ক্রয়" />
                <Step n={4} done={data.orders > 0} title="প্রথম বিক্রি করুন" hint="বিক্রি পাতায় বিল বানান" href="#/sales" action="বিক্রি" />
              </div>
            </Card>
          )}

          <div className="ui-stats">
            <Stat icon="cart" label="নিট বিক্রি" value={money(data.net_sales)} sub={`${num(data.orders)}টি চালান`} />
            <Stat icon="trend" label="মুনাফা (খরচের আগে)" tone={partialCost ? "warn" : "success"} value={money(data.gross_profit_known)}
                  sub={data.cost_coverage === null ? "এখনো বিক্রি নেই" : partialCost ? `ক্রয়মূল্য জানা বিক্রির ${num(Math.round(data.cost_coverage * 100))}% ধরে` : "সব বিক্রির ক্রয়মূল্য ধরে"} />
            <Stat icon="card" label="খরচের পর ফলাফল" tone={data.estimated_operating_result < 0 ? "danger" : "success"}
                  value={money(data.estimated_operating_result)} sub={`খরচ ${money(data.expenses)}`} />
            <Stat icon="users" label="বাকি পাবেন" tone={data.receivable > 0 ? "warn" : "neutral"} value={money(data.receivable)} sub={`${num(data.customer_count)} কাস্টমার`} />
            <Stat icon="truck" label="বাকি দেবেন" tone={data.payable > 0 ? "warn" : "neutral"} value={money(data.payable)} sub={`${num(data.supplier_count)} সাপ্লায়ার`} />
            <Stat icon="box" label="কম স্টক" tone={data.low_stock_products ? "warn" : "success"} value={`${num(data.low_stock_products)} / ${num(data.product_count)}`}
                  sub="পুনঃঅর্ডার সীমার নিচে" onClick={can("inventory:read") ? () => { window.location.hash = "#/inventory"; } : undefined} />
            {expiry && <Stat icon="clock" label="মেয়াদে আটকে থাকা টাকা" tone={atRisk > 0 ? "danger" : "success"} value={money(atRisk)}
                             sub="মেয়াদোত্তীর্ণ বা ৯০ দিনে শেষ" onClick={() => { window.location.hash = "#/expiry"; }} />}
          </div>

          {(partialCost || uncosted > 0) && can("catalog:read") && (
            <Notice tone="warn" title="মুনাফার হিসাব পুরো নির্ভরযোগ্য নয়"
                    action={<a className="ui-btn ui-btn--secondary ui-btn--sm" href="#/products">ক্রয়মূল্য দিন</a>}>
              {num(uncosted)}টি পণ্যের ক্রয়মূল্য দেওয়া নেই। ওপরের মুনাফা শুধু যেসব বিক্রির ক্রয়মূল্য জানা আছে সেগুলোর — বাকিগুলোর লাভ আন্দাজ করা হয়নি।
            </Notice>
          )}

          <Card title="দৈনিক বিক্রি" subtitle="গত ৩০ দিন">
            {data.orders === 0 ? (
              <EmptyState icon="trend" title="এখনো কোনো বিক্রি নেই" hint="প্রথম বিক্রি হলে এখানে গ্রাফ দেখা যাবে।" action={can("sales:create") && <a className="ui-btn ui-btn--primary" href="#/sales">বিক্রি শুরু করুন</a>} />
            ) : (
              <ResponsiveContainer width="100%" height={260}>
                <AreaChart data={chart} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
                  <defs>
                    <linearGradient id="salesFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#0a8754" stopOpacity={0.35} />
                      <stop offset="100%" stopColor="#0a8754" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="label" tickLine={false} axisLine={false} interval="preserveStartEnd" minTickGap={28} />
                  <YAxis tickLine={false} axisLine={false} tickFormatter={(x) => (x >= 1000 ? `${num(Math.round(x / 1000))}K` : num(x))} width={56} />
                  <Tooltip formatter={(v) => [money(v), "বিক্রি"]} labelFormatter={(l) => l} />
                  <Area type="monotone" dataKey="sales" stroke="#0a8754" strokeWidth={2.5} fill="url(#salesFill)" />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </Card>

          <div className="quick">
            {[
              ["sales:create", "#/sales", "cart", "নতুন বিক্রি"],
              ["purchases:receive", "#/purchases", "truck", "মাল রিসিভ"],
              ["inventory:read", "#/expiry", "clock", "মেয়াদ দেখুন"],
              ["recommendations:read", "#/strategy", "zap", "আজকের করণীয়"],
            ].filter(([perm]) => can(perm)).map(([, href, icon, label]) => (
              <a key={href} className="quick__item" href={href}><Icon name={icon} size={22} /><span>{label}</span></a>
            ))}
          </div>

          <Card title="সারাংশ">
            <div className="summary">
              <div><span>গড় চালান</span><strong>{money(data.average_order_value)}</strong></div>
              <div><span>ফেরত</span><strong>{money(data.returns)}</strong></div>
              <div><span>ক্রয়মূল্যে স্টকের মূল্য</span><strong>{money(data.stock_value_at_cost)}</strong></div>
              <div><span>মোট পণ্য</span><strong>{num(data.product_count)}</strong></div>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
