import { useEffect, useState } from "react";
import { NavLink, Route, HashRouter as Router, Routes } from "react-router-dom";
import { api } from "./api";
import Actions from "./pages/Actions";
import Customers from "./pages/Customers";
import Forecast from "./pages/Forecast";
import ModelReport from "./pages/ModelReport";
import Overview from "./pages/Overview";
import Segments from "./pages/Segments";
import Upload from "./pages/Upload";
import WhatIf from "./pages/WhatIf";
import { UiProvider, useUi } from "./UiContext";
import { WorkspaceProvider } from "./WorkspaceContext";
import { BusinessProvider, useBusiness } from "./BusinessContext";
import BusinessSetup from "./pages/BusinessSetup";
import { AccountsPage, InventoryPage, ProductsPage, SalesPage } from "./pages/Operations";
import OperationalDashboard from "./pages/OperationalDashboard";
import { DirectoryPage, PurchasesPage, ReturnsPage, StrategyPage } from "./pages/SupplyChain";

// HashRouter rather than BrowserRouter: the production build is served as
// static files by FastAPI, and hash routing needs no server-side rewrite
// rule for deep links to work.
//
// Navigation is split into two modes, not three flat groups. A shop owner
// never needs to see "Model report" or "Research dataset" in the same list
// as "বিক্রি" — those exist to show how the system was validated, not to run
// a business. গবেষণা মোড keeps them one click away instead of hidden or
// mixed in.
const BUSINESS_NAV = [
  {
    heading: "দৈনিক কাজ",
    items: [
      { to: "/", label: "ড্যাশবোর্ড", end: true },
      { to: "/sales", label: "বিক্রি" },
      { to: "/inventory", label: "স্টক", badgeKey: "lowStock" },
      { to: "/products", label: "পণ্য" },
      { to: "/purchases", label: "ক্রয়" },
      { to: "/returns", label: "রিটার্ন" },
      { to: "/directory", label: "কাস্টমার ও সাপ্লায়ার" },
      { to: "/accounts", label: "হিসাব" },
    ],
  },
  {
    heading: "AI সুপারিশ",
    items: [
      { to: "/strategy", label: "আজকের করণীয়" },
      { to: "/forecast", label: "বিক্রির পূর্বাভাস" },
      { to: "/segments", label: "কাস্টমার গ্রুপ" },
      { to: "/upload", label: "নিজের ফাইল আপলোড করুন" },
    ],
  },
  {
    heading: "সেটআপ",
    items: [{ to: "/setup", label: "ব্যবসা ও শাখা" }],
  },
];

const RESEARCH_NAV = [
  {
    heading: "থিসিস মূল্যায়ন",
    items: [
      { to: "/models", label: "মডেল রিপোর্ট" },
      { to: "/customers", label: "গবেষণা ডেটাসেট" },
      { to: "/whatif", label: "ঝুঁকি ক্যালকুলেটর" },
      { to: "/overview", label: "বিক্রি ওভারভিউ (synthetic)" },
    ],
  },
];

export default function App() {
  return (
    <UiProvider>
      <WorkspaceProvider>
        <BusinessProvider>
          <Router>
            <div className="app">
              <Sidebar />
              <main className="main">
                <Routes>
                  <Route path="/" element={<OperationalDashboard />} />
                  <Route path="/research-actions" element={<Actions />} />
                  <Route path="/overview" element={<Overview />} />
                  <Route path="/upload" element={<Upload />} />
                  <Route path="/whatif" element={<WhatIf />} />
                  <Route path="/segments" element={<Segments />} />
                  <Route path="/customers" element={<Customers />} />
                  <Route path="/customers/:customerId" element={<Customers />} />
                  <Route path="/forecast" element={<Forecast />} />
                  <Route path="/models" element={<ModelReport />} />
                  <Route path="/setup" element={<BusinessSetup />} />
                  <Route path="/sales" element={<SalesPage />} />
                  <Route path="/inventory" element={<InventoryPage />} />
                  <Route path="/products" element={<ProductsPage />} />
                  <Route path="/accounts" element={<AccountsPage />} />
                  <Route path="/purchases" element={<PurchasesPage />} />
                  <Route path="/returns" element={<ReturnsPage />} />
                  <Route path="/directory" element={<DirectoryPage />} />
                  <Route path="/strategy" element={<StrategyPage />} />
                  <Route path="*" element={<NotFound />} />
                </Routes>
              </main>
            </div>
          </Router>
        </BusinessProvider>
      </WorkspaceProvider>
    </UiProvider>
  );
}

function Sidebar() {
  const { simple, theme, toggleMode, toggleTheme } = useUi();
  const business = useBusiness();
  const [mode, setMode] = useState("business");
  const [lowStock, setLowStock] = useState(0);
  const activeId = business.active?.id;

  useEffect(() => {
    if (!activeId) return;
    api.dashboardApp(activeId).then((d) => setLowStock(d.low_stock_products || 0)).catch(() => {});
  }, [activeId]);

  const groups = mode === "business" ? BUSINESS_NAV : RESEARCH_NAV;
  const badges = { lowStock: lowStock > 0 };

  return (
    <aside className="sidebar">
      <div className="brand">
        <h1>B-SMART</h1>
        <p className="subtitle">বাংলাদেশি SME ব্যবসা বিশ্লেষণ</p>
        {business.active && <p className="business-chip">{business.active.name}</p>}
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
        {mode === "business" ? (
          <>দৈনন্দিন ব্যবহারের বাইরে? <button type="button" className="link-btn" onClick={() => setMode("research")}>গবেষণা ও মডেল বিস্তারিত →</button></>
        ) : (
          <>থিসিস মূল্যায়নের জন্য — দৈনিক ব্যবহারের অংশ নয়।</>
        )}
      </div>
    </aside>
  );
}

function NotFound() {
  return (
    <div className="page">
      <header className="page-head">
        <h2>পাতা পাওয়া যায়নি</h2>
        <p className="subtitle">
          এই লিংকের সাথে কিছু মেলেনি। বাম পাশের মেনু থেকে একটি পাতা বেছে নিন।
        </p>
      </header>
    </div>
  );
}
