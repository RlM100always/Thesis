import { NavLink, Route, HashRouter as Router, Routes } from "react-router-dom";
import Customers from "./pages/Customers";
import Forecast from "./pages/Forecast";
import ModelReport from "./pages/ModelReport";
import Overview from "./pages/Overview";
import Segments from "./pages/Segments";

// HashRouter rather than BrowserRouter: the production build is served as
// static files by FastAPI, and hash routing needs no server-side rewrite
// rule for deep links to work.
const NAV = [
  { to: "/", label: "Overview", end: true },
  { to: "/segments", label: "Segments" },
  { to: "/customers", label: "Customers" },
  { to: "/forecast", label: "Forecast" },
  { to: "/models", label: "Model Report" },
];

export default function App() {
  return (
    <Router>
      <div className="app">
        <aside className="sidebar">
          <h1>AI Business Analytics</h1>
          <p className="subtitle">Bangladeshi Retail · CSE Thesis</p>
          <nav>
            {NAV.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.end}
                       className={({ isActive }) => (isActive ? "active" : "")}>
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="footer">
            Segment accuracy 67.07%<br />
            <span style={{ opacity: 0.75 }}>leak-free · see Model Report</span>
          </div>
        </aside>

        <main className="main">
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/segments" element={<Segments />} />
            <Route path="/customers" element={<Customers />} />
            <Route path="/forecast" element={<Forecast />} />
            <Route path="/models" element={<ModelReport />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}
