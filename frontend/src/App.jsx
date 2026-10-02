import { lazy, Suspense, useEffect, useState } from "react";
import { Link, Navigate, NavLink, Route, HashRouter as Router, Routes, useLocation } from "react-router-dom";
import { api } from "./api";
import { AuthProvider, useAuth } from "./AuthContext";
import { PermissionProvider, ROLE_LABELS, usePermissions } from "./PermissionContext";
import { UiProvider, useUi } from "./UiContext";
import { WorkspaceProvider } from "./WorkspaceContext";
import { BusinessProvider, useBusiness } from "./BusinessContext";
import NotificationBell from "./components/NotificationBell";
import Icon from "./ui/Icon";
import { Avatar, Button, EmptyState, PageHeader } from "./ui/kit";
import { BranchProvider } from "./useBranch";
import WorkspaceBar from "./components/WorkspaceBar";

const Actions = lazy(() => import("./pages/Actions"));
const Customers = lazy(() => import("./pages/Customers"));
const Forecast = lazy(() => import("./pages/Forecast"));
const PublicSite = lazy(() => import("./pages/PublicSite"));
const Login = lazy(() => import("./pages/Login"));
const ModelReport = lazy(() => import("./pages/ModelReport"));
const Overview = lazy(() => import("./pages/Overview"));
const Segments = lazy(() => import("./pages/Segments"));
const Upload = lazy(() => import("./pages/Upload"));
const WhatIf = lazy(() => import("./pages/WhatIf"));
const BusinessSetup = lazy(() => import("./pages/Settings"));
const AccountsPage = lazy(() => import("./pages/Accounts"));
const DirectoryPage = lazy(() => import("./pages/Directory"));
const ReturnsPage = lazy(() => import("./pages/Returns"));
const StrategyPage = lazy(() => import("./pages/Strategy"));
const SalesPage = lazy(() => import("./pages/Pos"));
const ProductsPage = lazy(() => import("./pages/Products"));
const InventoryPage = lazy(() => import("./pages/Inventory"));
const ExpiryPage = lazy(() => import("./pages/Expiry"));
const PurchasesPage = lazy(() => import("./pages/Purchases"));
const PurchaseReturnsPage = lazy(() => import("./pages/PurchaseReturns"));
const OperationalDashboard = lazy(() => import("./pages/Dashboard"));
const RealDataValidation = lazy(() => import("./pages/RealDataValidation"));
const BSmartAlgorithm = lazy(() => import("./pages/BSmartAlgorithm"));
const BSmartActions = lazy(() => import("./pages/Recommendations"));
const StaffPage = lazy(() => import("./pages/Staff"));
const WorkforcePage = lazy(() => import("./pages/Workforce"));
const CrmPage = lazy(() => import("./pages/Crm"));
const FulfilmentPage = lazy(() => import("./pages/Fulfilment"));
const AccountPage = lazy(() => import("./pages/Account"));
const AuditPage = lazy(() => import("./pages/Audit"));
const CashPage = lazy(() => import("./pages/Cash"));
const SalesHistoryPage = lazy(() => import("./pages/SalesHistory"));
const ReportsPage = lazy(() => import("./pages/Reports"));
const ImportDataPage = lazy(() => import("./pages/ImportData"));
const InsightsPage = lazy(() => import("./pages/Insights"));
const ApprovalsPage = lazy(() => import("./pages/Approvals"));
const AccountingPage = lazy(() => import("./pages/Accounting"));
const StockCountPage = lazy(() => import("./pages/StockCount"));
const OrdersPage = lazy(() => import("./pages/Orders"));
const ReorderPlanPage = lazy(() => import("./pages/ReorderPlan"));
const GuidePage = lazy(() => import("./pages/Guide"));
const PlatformPage = lazy(() => import("./pages/Platform"));
const AcceptInvite = lazy(() => import("./pages/AcceptInvite"));
const Onboarding = lazy(() => import("./pages/Onboarding"));
const StorePage = lazy(() => import("./pages/Store"));
const OrderStatusPage = lazy(() => import("./pages/OrderStatus"));
const StoreAdminPage = lazy(() => import("./pages/StoreAdmin"));

// HashRouter rather than BrowserRouter: the production build is served as
// static files by FastAPI, and hash routing needs no server-side rewrite
// rule for deep links to work.
//
// Navigation is split into two modes, not three flat groups. A shop owner
// never needs to see "Model report" or "Research dataset" in the same list
// as "বিক্রি" — those exist to show how the system was validated, not to run
// a business. গবেষণা মোড keeps them one click away instead of hidden or
// mixed in.
//
// Each item names the permission needed to see it; the API enforces the same
// permission, so hiding an item here is a convenience, not the control.
const BUSINESS_NAV = [
  {
    heading: "দৈনিক কাজ",
    items: [
      { to: "/app", label: "ড্যাশবোর্ড", icon: "home", end: true, perm: "dashboard:read" },
    ],
  },
  {
    heading: "বিক্রি ও কাস্টমার",
    items: [
      { to: "/sales", label: "বিক্রি", icon: "cart", perm: "sales:read" },
      { to: "/sales-history", label: "বিক্রির ইতিহাস", icon: "fileText", perm: "sales:read" },
      { to: "/orders", label: "কোটেশন ও অর্ডার", icon: "fileText", perm: "orders:read" },
      { to: "/returns", label: "রিটার্ন", icon: "undo", perm: "returns:read" },
      { to: "/directory", label: "কাস্টমার ও সাপ্লায়ার", icon: "users", perm: "customers:read" },
      { to: "/crm", label: "টিকেট, লিড ও ফিডব্যাক", icon: "userCheck", perm: "tickets:read", featureFlag: "crm" },
      { to: "/fulfilment", label: "রিজার্ভেশন ও ডেলিভারি", icon: "truck", perm: "orders:read", featureFlag: "fulfilment" },
      { to: "/store-admin", label: "অনলাইন স্টোর", icon: "globe", perm: "catalog:read" },
    ],
  },
  {
    heading: "স্টক ও ক্রয়",
    items: [
      { to: "/inventory", label: "স্টক", icon: "box", badgeKey: "lowStock", perm: "inventory:read" },
      { to: "/expiry", label: "মেয়াদ ও ব্যাচ", icon: "clock", perm: "inventory:read", feature: "expiry" },
      { to: "/stock-count", label: "স্টক গণনা", icon: "check", perm: "inventory:read" },
      { to: "/products", label: "পণ্য", icon: "tag", perm: "catalog:read" },
      { to: "/reorder", label: "কী কিনবেন", icon: "zap", perm: "purchases:read" },
      { to: "/purchases", label: "ক্রয়", icon: "truck", perm: "purchases:read" },
      { to: "/purchase-returns", label: "সাপ্লায়ার ক্লেইম", icon: "undo", perm: "purchase_returns:read" },
    ],
  },
  {
    heading: "টাকা ও প্রতিবেদন",
    items: [
      { to: "/accounts", label: "হিসাব", icon: "card", perm: "ledger:read" },
      { to: "/cash", label: "ক্যাশ মেলান", icon: "wallet", perm: "cash:read" },
      { to: "/accounting", label: "আর্থিক প্রতিবেদন", icon: "fileText", perm: "ledger:read" },
      { to: "/insights", label: "ইনসাইটস", icon: "pie", perm: "inventory:read" },
      { to: "/reports", label: "রিপোর্ট", icon: "download", perm: "ledger:read" },
    ],
  },
  {
    heading: "AI সুপারিশ",
    items: [
      { to: "/strategy", label: "আজকের করণীয়", icon: "zap", perm: "recommendations:read" },
      { to: "/bsmart-actions", label: "সুপারিশ", icon: "target", perm: "bsmart:read", featureFlag: "bsmart" },
      { to: "/forecast", label: "বিক্রির পূর্বাভাস", icon: "trend" },
      { to: "/segments", label: "কাস্টমার গ্রুপ", icon: "pie" },
      { to: "/upload", label: "নিজের ফাইল আপলোড করুন", icon: "upload", featureFlag: "upload" },
    ],
  },
  {
    heading: "সেটআপ",
    items: [
      { to: "/setup", label: "ব্যবসা ও শাখা", icon: "sliders" },
      { to: "/guide", label: "সাহায্য ও গাইড", icon: "info" },
      { to: "/import", label: "তথ্য আমদানি", icon: "upload", perm: "imports:write" },
      { to: "/approvals", label: "অনুমোদন", icon: "check", badgeKey: "approvals", perm: "approvals:read" },
      { to: "/staff", label: "কর্মী ও ভূমিকা", icon: "userCheck", perm: "staff:read" },
      { to: "/workforce", label: "উপস্থিতি, ছুটি ও পে-রোল", icon: "clock", featureFlag: "workforce" },
      { to: "/audit", label: "কার্যকলাপের ইতিহাস", icon: "clock", perm: "audit:read" },
    ],
  },
];

const RESEARCH_NAV = [
  {
    heading: "থিসিস মূল্যায়ন",
    items: [
      { to: "/bsmart", label: "B-SMART অ্যালগরিদম (R_t)", icon: "target" },
      { to: "/models", label: "মডেল রিপোর্ট", icon: "fileText" },
      { to: "/real-data-validation", label: "Real-data validation", icon: "shield" },
      { to: "/customers", label: "গবেষণা ডেটাসেট", icon: "users" },
      { to: "/whatif", label: "ঝুঁকি ক্যালকুলেটর", icon: "zap" },
      { to: "/overview", label: "বিক্রি ওভারভিউ (synthetic)", icon: "pie" },
    ],
  },
];

// Phone bottom bar: the first four of these the person may use, then "আরও".
const BOTTOM_ORDER = ["/app", "/sales", "/inventory", "/strategy", "/purchases", "/directory", "/products"];

const PUBLIC_PATHS = new Set(["/", "/features", "/solutions", "/pricing", "/security", "/about", "/help", "/guidelines", "/contact", "/privacy", "/terms", "/status"]);

export default function App() {
  return (
    <UiProvider>
      <AuthProvider>
        <WorkspaceProvider>
          <BusinessProvider>
            <BranchProvider>
              <PermissionProvider>
                <Router>
                  <Suspense fallback={<RouteLoading />}>
                    <Shell />
                  </Suspense>
                </Router>
              </PermissionProvider>
            </BranchProvider>
          </BusinessProvider>
        </WorkspaceProvider>
      </AuthProvider>
    </UiProvider>
  );
}

function RouteLoading() {
  return (
    <div className="route-loading" role="status" aria-live="polite">
      <img src="/bsmart-mark.svg" alt="" />
      <div><strong>B-SMART</strong><span>আপনার workspace প্রস্তুত হচ্ছে…</span></div>
    </div>
  );
}

// The API answers 401 when a sign-in is required (AUTH_MODE=jwt, or an expired
// session); until then the local prototype owner works without logging in.
// The invite page must work for someone who has no account yet.
function Shell() {
  const { requiresLogin } = useAuth();
  const { pathname } = useLocation();
  const { loading, organizations, error, wizardActive } = useBusiness();
  if (pathname === "/accept-invite") return <AcceptInvite />;
  if (pathname === "/reset-password") return <AcceptInvite mode="reset" />;
  if (pathname === "/login") return <Login initialMode="login" />;
  if (pathname === "/signup") return <Login initialMode="register" />;
  // The public storefront and order-status lookup need no account at all —
  // a visitor opens these from a link the shop shares, not through the app.
  if (pathname.startsWith("/store/") || pathname.startsWith("/order-status/")) {
    return (
      <Routes>
        <Route path="/store/:orgId" element={<StorePage />} />
        <Route path="/order-status/:orgId/:token" element={<OrderStatusPage />} />
      </Routes>
    );
  }
  if (PUBLIC_PATHS.has(pathname) || pathname.startsWith("/solutions/")) return <PublicSite />;
  // Public marketing pages are always reachable. Protected work pages send an
  // expired or anonymous session straight to the business login form.
  if (requiresLogin) return <Login initialMode="login" />;
  // Platform admin is a completely separate shell -- no business sidebar, no
  // business switcher, distinct visual theme -- so there is never a moment of
  // confusion about which "mode" is on screen. It doesn't care whether this
  // account has zero, one or many business memberships.
  if (pathname.startsWith("/platform")) return <PlatformShell />;
  // Signed in but no business yet (right after signing up): create one first.
  // wizardActive keeps the setup wizard open through its later steps even after
  // the organization itself already exists (see BusinessContext.jsx).
  if (!loading && !error && (organizations.length === 0 || wizardActive)) return <Onboarding />;
  return <AppFrame />;
}

function PlatformShell() {
  const { user, signOut } = useAuth();
  if (!user?.is_platform_admin) {
    return (
      <div className="platform-denied">
        <Icon name="lock" size={32} />
        <h2>এই পাতাটা আপনার জন্য না</h2>
        <p>শুধু প্ল্যাটফর্ম অ্যাডমিন অ্যাকাউন্ট দিয়ে লগইন করলে এটা দেখা যাবে।</p>
        <Link className="public-cta" to="/app">নিজের ব্যবসায় ফিরে যান</Link>
      </div>
    );
  }
  return (
    <div className="platform-shell">
      <header className="platform-topbar">
        <div className="platform-brand"><img src="/bsmart-mark.svg" alt="" /><div><strong>B-SMART প্ল্যাটফর্ম অ্যাডমিন</strong><small>{user.email}</small></div></div>
        <div className="platform-topbar-actions">
          <Link className="platform-exit" to="/app"><Icon name="chevronRight" size={14} style={{ transform: "rotate(180deg)" }} /> নিজের ব্যবসায় ফিরে যান</Link>
          <button type="button" className="platform-exit" onClick={signOut}><Icon name="logout" size={14} />লগআউট</button>
        </div>
      </header>
      <main className="platform-main"><PlatformPage /></main>
    </div>
  );
}

function AppFrame() {
  const { pathname } = useLocation();
  const business = useBusiness();
  const { can, ready } = usePermissions();
  const [mode, setMode] = useState("business");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [lowStock, setLowStock] = useState(0);
  const [pendingApprovals, setPendingApprovals] = useState(0);
  const activeId = business.active?.id;
  const canSeeDashboard = ready && can("dashboard:read");

  useEffect(() => { setDrawerOpen(false); }, [pathname]);

  useEffect(() => {
    if (!activeId || !canSeeDashboard) return;
    api.dashboardApp(activeId).then((d) => setLowStock(d.low_stock_products || 0)).catch(() => {});
  }, [activeId, canSeeDashboard]);

  useEffect(() => {
    if (!activeId || !can("approvals:read")) return;
    api.approvals(activeId).then((rows) => setPendingApprovals(rows.length)).catch(() => {});
  }, [activeId, can]);

  const body = { mode, setMode, badges: { lowStock: lowStock > 0, approvals: pendingApprovals > 0 } };

  return (
    <div className="app">
      <aside className="sidebar"><SidebarBody {...body} /></aside>

      <WorkspaceBar onMenu={() => setDrawerOpen(true)} />

      <main className="main">
        <Routes>
          <Route path="/app" element={<Home />} />
          <Route path="/research-actions" element={<Actions />} />
          <Route path="/overview" element={<Overview />} />
          <Route path="/upload" element={<Guard featureFlag="upload"><Upload /></Guard>} />
          <Route path="/whatif" element={<WhatIf />} />
          <Route path="/segments" element={<Segments />} />
          <Route path="/customers" element={<Customers />} />
          <Route path="/customers/:customerId" element={<Customers />} />
          <Route path="/forecast" element={<Forecast />} />
          <Route path="/models" element={<ModelReport />} />
          <Route path="/real-data-validation" element={<RealDataValidation />} />
          <Route path="/bsmart" element={<BSmartAlgorithm />} />
          <Route path="/bsmart-actions" element={<Guard perm="bsmart:read" featureFlag="bsmart"><BSmartActions /></Guard>} />
          <Route path="/setup" element={<BusinessSetup />} />
          <Route path="/guide" element={<GuidePage />} />
          <Route path="/platform" element={<PlatformPage />} />
          <Route path="/staff" element={<Guard perm="staff:read"><StaffPage /></Guard>} />
          <Route path="/workforce" element={<Guard featureFlag="workforce"><WorkforcePage /></Guard>} />
          <Route path="/crm" element={<Guard perm="tickets:read" featureFlag="crm"><CrmPage /></Guard>} />
          <Route path="/fulfilment" element={<Guard perm="orders:read" featureFlag="fulfilment"><FulfilmentPage /></Guard>} />
          <Route path="/audit" element={<Guard perm="audit:read"><AuditPage /></Guard>} />
          <Route path="/account" element={<AccountPage />} />
          <Route path="/sales-history" element={<Guard perm="sales:read"><SalesHistoryPage /></Guard>} />
          <Route path="/orders" element={<Guard perm="orders:read"><OrdersPage /></Guard>} />
          <Route path="/cash" element={<Guard perm="cash:read"><CashPage /></Guard>} />
          <Route path="/import" element={<Guard perm="imports:write"><ImportDataPage /></Guard>} />
          <Route path="/reorder" element={<Guard perm="purchases:read"><ReorderPlanPage /></Guard>} />
          <Route path="/reports" element={<Guard perm="ledger:read"><ReportsPage /></Guard>} />
          <Route path="/sales" element={<Guard perm="sales:read"><SalesPage /></Guard>} />
          <Route path="/inventory" element={<Guard perm="inventory:read"><InventoryPage /></Guard>} />
          <Route path="/expiry" element={<Guard perm="inventory:read"><ExpiryPage /></Guard>} />
          <Route path="/stock-count" element={<Guard perm="inventory:read"><StockCountPage /></Guard>} />
          <Route path="/products" element={<Guard perm="catalog:read"><ProductsPage /></Guard>} />
          <Route path="/accounts" element={<Guard perm="ledger:read"><AccountsPage /></Guard>} />
          <Route path="/insights" element={<Guard perm="inventory:read"><InsightsPage /></Guard>} />
          <Route path="/accounting" element={<Guard perm="ledger:read"><AccountingPage /></Guard>} />
          <Route path="/approvals" element={<Guard perm="approvals:read"><ApprovalsPage /></Guard>} />
          <Route path="/purchases" element={<Guard perm="purchases:read"><PurchasesPage /></Guard>} />
          <Route path="/purchase-returns" element={<Guard perm="purchase_returns:read"><PurchaseReturnsPage /></Guard>} />
          <Route path="/returns" element={<Guard perm="returns:read"><ReturnsPage /></Guard>} />
          <Route path="/directory" element={<Guard perm="customers:read"><DirectoryPage /></Guard>} />
          <Route path="/strategy" element={<Guard perm="recommendations:read"><StrategyPage /></Guard>} />
          <Route path="/store-admin" element={<Guard perm="catalog:read"><StoreAdminPage /></Guard>} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>

      <BottomNav onMore={() => setDrawerOpen(true)} badges={body.badges} />

      {drawerOpen && (
        <>
          <div className="drawer-overlay" onClick={() => setDrawerOpen(false)} />
          <aside className="sidebar drawer-panel" role="dialog" aria-modal="true" aria-label="মেনু">
            <button type="button" className="drawer-close" onClick={() => setDrawerOpen(false)} aria-label="মেনু বন্ধ করুন">
              <Icon name="x" />
            </button>
            <SidebarBody {...body} />
          </aside>
        </>
      )}
    </div>
  );
}

// A page the caller's role cannot use is replaced by an explanation, not an
// error from the API. The server still enforces the same permission.
function Guard({ perm, featureFlag, children }) {
  const { can, ready } = usePermissions();
  const business = useBusiness();
  if (!ready) return null;
  if (featureFlag && business.active?.feature_flags?.[featureFlag] === false) {
    return (
      <div className="page">
        <EmptyState icon="lock" title="এই মডিউলটি এই ব্যবসার জন্য বন্ধ" hint="প্রয়োজনে সাপোর্টের সাথে যোগাযোগ করুন।" />
      </div>
    );
  }
  return can(perm) ? children : <NotAllowed />;
}

// A cashier has no dashboard (it shows profit); send each role to its own start page.
function Home() {
  const { can, ready } = usePermissions();
  if (!ready) return null;
  if (can("dashboard:read")) return <OperationalDashboard />;
  if (can("sales:read")) return <Navigate to="/sales" replace />;
  if (can("inventory:read")) return <Navigate to="/inventory" replace />;
  if (can("orders:read")) return <Navigate to="/fulfilment" replace />;
  return <NotAllowed />;
}

function NotAllowed() {
  return (
    <div className="page">
      <EmptyState
        icon="lock"
        title="এই পাতাটি আপনার ভূমিকার জন্য নয়"
        hint="আপনার ভূমিকা (রোল) অনুযায়ী এই তথ্য দেখার অনুমতি নেই। প্রয়োজনে ব্যবসার মালিকের সাথে কথা বলুন।"
      />
    </div>
  );
}

function SidebarBody({ mode, setMode, badges }) {
  const { simple, theme, toggleMode, toggleTheme } = useUi();
  const business = useBusiness();
  const { user, signOut } = useAuth();
  const { can, role } = usePermissions();

  const groups = (mode === "business" ? BUSINESS_NAV : RESEARCH_NAV)
    .map((group) => ({
      ...group,
      items: group.items.filter((item) =>
        can(item.perm)
        && (!item.feature || business.features[item.feature])
        && (!item.featureFlag || business.active?.feature_flags?.[item.featureFlag] !== false)),
    }))
    .filter((group) => group.items.length > 0);

  return (
    <>
      <div className="brand">
        <div className="brand-row"><div className="app-brandlockup"><img src="/bsmart-mark.svg" alt="" /><div><h1>B-SMART</h1><p className="subtitle">Business OS</p></div></div><NotificationBell /></div>
        <p className="subtitle app-brandtag">বাংলাদেশি SME ব্যবসা পরিচালনা</p>
        {business.organizations.length > 1 ? (
          <select className="business-switch" value={business.active?.id || ""} aria-label="ব্যবসা বদলান"
                  onChange={(e) => business.select(e.target.value)}>
            {business.organizations.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
          </select>
        ) : (
          business.active && <p className="business-chip">{business.active.name}</p>
        )}
      </div>

      <div className="mode-switch" role="tablist" aria-label="নেভিগেশন মোড">
        <button type="button" className={mode === "business" ? "on" : ""} onClick={() => setMode("business")} role="tab" aria-selected={mode === "business"}>
          ব্যবসা মোড
        </button>
        <button type="button" className={mode === "research" ? "on" : ""} onClick={() => setMode("research")} role="tab" aria-selected={mode === "research"}>
          গবেষণা মোড
        </button>
      </div>

      <nav>
        {groups.map((group) => (
          <div key={group.heading} className="nav-group">
            <span className="nav-heading">{group.heading}</span>
            {group.items.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.end}
                       className={({ isActive }) => (isActive ? "active" : "")}>
                <Icon name={item.icon} size={19} />
                <span>{item.label}</span>
                {item.badgeKey && badges[item.badgeKey] && (
                  <span className="nav-badge-dot" title="কম স্টকে থাকা পণ্য আছে" />
                )}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      <div className="toggles">
        {mode === "research" && (
          <button type="button" className="toggle" onClick={toggleMode} aria-pressed={!simple}>
            {simple ? "সহজ ভাষা" : "প্রযুক্তিগত বিবরণ"}
            <span className="toggle-hint">{simple ? "বিস্তারিত দেখুন" : "সহজ ভাষায় দেখুন"}</span>
          </button>
        )}
        <button type="button" className="toggle" onClick={toggleTheme}
                aria-label="থিম পরিবর্তন করুন">
          {theme === "dark" ? "🌙 ডার্ক" : "☀️ লাইট"}
        </button>
      </div>

      <div className="footer">
        {user ? (
          <>
            <div className="account-chip">
              <Avatar name={user.display_name} size={34} />
              <div>
                <strong>{user.display_name}</strong>
                <small>{role ? ROLE_LABELS[role] || role : user.email}</small>
              </div>
            </div>
            <div className="account-actions">
              {user.is_platform_admin && (
                <NavLink to="/platform"><Icon name="shield" size={14} />প্ল্যাটফর্ম</NavLink>
              )}
              <NavLink to="/account"><Icon name="key" size={14} />পাসওয়ার্ড</NavLink>
              <button type="button" onClick={signOut}><Icon name="logout" size={14} />লগআউট</button>
            </div>
          </>
        ) : (
          <div className="account-actions">
            {role && <span className="account-chip"><small>ভূমিকা: {ROLE_LABELS[role] || role}</small></span>}
            <NavLink to="/login"><Icon name="key" size={14} />লগইন / নতুন অ্যাকাউন্ট</NavLink>
          </div>
        )}
        {mode === "business" ? (
          <>দৈনন্দিন ব্যবহারের বাইরে? <button type="button" className="link-btn" onClick={() => setMode("research")}>গবেষণা ও মডেল বিস্তারিত →</button></>
        ) : (
          <>থিসিস মূল্যায়নের জন্য। এটি দৈনিক ব্যবহারের অংশ নয়।</>
        )}
      </div>
    </>
  );
}

function BottomNav({ onMore, badges }) {
  const { can } = usePermissions();
  const items = BOTTOM_ORDER
    .map((to) => BUSINESS_NAV.flatMap((g) => g.items).find((item) => item.to === to))
    .filter((item) => item && can(item.perm))
    .slice(0, 4);
  return (
    <nav className="bottomnav" aria-label="প্রধান মেনু">
      {items.map((item) => (
        <NavLink key={item.to} to={item.to} end={item.end}
                 className={({ isActive }) => (isActive ? "active" : "")}>
          <span className="bottomnav__icon">
            <Icon name={item.icon} size={22} />
            {item.badgeKey && badges[item.badgeKey] && <span className="nav-badge-dot" />}
          </span>
          {item.label.length > 8 ? item.label.split(" ")[0] : item.label}
        </NavLink>
      ))}
      <button type="button" onClick={onMore}><Icon name="menu" size={22} />আরও</button>
    </nav>
  );
}

function NotFound() {
  return (
    <div className="page">
      <PageHeader
        title="পাতা পাওয়া যায়নি"
        subtitle="এই লিংকের সাথে কিছু মেলেনি। মেনু থেকে একটি পাতা বেছে নিন।"
        actions={<Button variant="secondary" onClick={() => { window.location.hash = "#/"; }}>হোমে ফিরুন</Button>}
      />
    </div>
  );
}
