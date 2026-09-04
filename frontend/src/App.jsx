import { NavLink, Route, HashRouter as Router, Routes } from "react-router-dom";
import { api, formatPct } from "./api";
import Actions from "./pages/Actions";
import Customers from "./pages/Customers";
import Forecast from "./pages/Forecast";
import ModelReport from "./pages/ModelReport";
import Overview from "./pages/Overview";
import Segments from "./pages/Segments";
import Upload from "./pages/Upload";
import WhatIf from "./pages/WhatIf";
import { UiProvider, useUi } from "./UiContext";
import { useApi } from "./useApi";
import { WorkspaceProvider } from "./WorkspaceContext";
import { BusinessProvider, useBusiness } from "./BusinessContext";
import BusinessSetup from "./pages/BusinessSetup";
import { AccountsPage, InventoryPage, ProductsPage, SalesPage } from "./pages/Operations";
import OperationalDashboard from "./pages/OperationalDashboard";
import { DirectoryPage, PurchasesPage, ReturnsPage, StrategyPage } from "./pages/SupplyChain";

// HashRouter rather than BrowserRouter: the production build is served as
// static files by FastAPI, and hash routing needs no server-side rewrite
// rule for deep links to work.
// Split so a business owner can tell which pages describe their business and
// which exist to show how the system was validated. Both stay visible — the
// thesis evidence is not hidden, just labelled.
const NAV_GROUPS = [
  {
    heading: "দৈনিক ব্যবসা",
    items: [
      { to: "/", label: "ড্যাশবোর্ড", end: true },
      { to: "/sales", label: "বিক্রি" },
      { to: "/purchases", label: "ক্রয়" },
      { to: "/returns", label: "রিটার্ন" },
      { to: "/inventory", label: "স্টক" },
      { to: "/products", label: "পণ্য" },
      { to: "/directory", label: "কাস্টমার ও সাপ্লায়ার" },
      { to: "/accounts", label: "হিসাব" },
      { to: "/setup", label: "ব্যবসা সেটআপ" },
    ],
  },
  {
    heading: "AI সিদ্ধান্ত সহায়তা",
    items: [
      { to: "/strategy", label: "করণীয় ও অগ্রাধিকার" },
      { to: "/overview", label: "Sales overview" },
      { to: "/forecast", label: "Sales forecast" },
      { to: "/segments", label: "Customer groups" },
      { to: "/upload", label: "Upload / update data" },
    ],
  },
  {
    heading: "How this system was built",
    items: [
      { to: "/models", label: "Model report" },
      { to: "/customers", label: "Research dataset" },
      { to: "/whatif", label: "Risk calculator" },
    ],
  },
];

export default function App() {
  return (
    <UiProvider>
      <WorkspaceProvider>
        <BusinessProvider><Router>
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
        </Router></BusinessProvider>
      </WorkspaceProvider>
    </UiProvider>
  );
}

function Sidebar() {
  const { simple, theme, toggleMode, toggleTheme } = useUi();
  // Read the headline accuracy from the artifacts rather than hardcoding it,
  // so rerunning the pipeline cannot leave a stale number in the chrome.
  const { data } = useApi(() => api.modelMetrics(), []);
  const business = useBusiness();
  const models = data?.segment?.models;
  // Highest test accuracy, whichever model that turns out to be.
  const best = models
    ? Object.values(models).reduce((a, b) => (b.accuracy > a.accuracy ? b : a))
    : null;

  return (
    <aside className="sidebar">
      <h1>AI Business Analytics</h1>
      <p className="subtitle">Bangladeshi Retail · CSE Thesis</p>
      {business.active && <p className="business-chip">{business.active.name}</p>}

      <nav>
        {NAV_GROUPS.map((group) => (
          <div key={group.heading} className="nav-group">
            <span className="nav-heading">{group.heading}</span>
            {group.items.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.end}
                       className={({ isActive }) => (isActive ? "active" : "")}>
                {item.label}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      <div className="toggles">
        <button type="button" className="toggle" onClick={toggleMode}
                aria-pressed={!simple}>
          {simple ? "Plain language" : "Technical detail"}
          <span className="toggle-hint">{simple ? "show metrics" : "show plain words"}</span>
        </button>
        <button type="button" className="toggle" onClick={toggleTheme}
                aria-label="Switch colour theme">
          {theme === "dark" ? "🌙 Dark" : "☀️ Light"}
        </button>
      </div>

      <div className="footer">
        {best ? <>Segment accuracy {formatPct(best.accuracy, 2)}</> : <>Segment accuracy —</>}
        <br />
        <span style={{ opacity: 0.75 }}>leak-free · see Model Report</span>
      </div>
    </aside>
  );
}

function NotFound() {
  return (
    <div className="page">
      <header className="page-head">
        <h2>Page not found</h2>
        <p className="subtitle">
          That link doesn't match anything. Pick a page from the menu on the left.
        </p>
      </header>
    </div>
  );
}
