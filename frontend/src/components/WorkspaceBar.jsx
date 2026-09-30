import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useBusiness } from "../BusinessContext";
import { usePermissions } from "../PermissionContext";
import useBranch from "../useBranch";
import Icon from "../ui/Icon";

const COMMANDS = [
  ["/", "ড্যাশবোর্ড", "আজকের অবস্থা, করণীয় ও সতর্কতা", "home", "dashboard:read"],
  ["/sales", "নতুন বিক্রি", "POS খুলে বিক্রি করুন", "cart", "sales:read"],
  ["/sales-history", "বিক্রির ইতিহাস", "চালান খুঁজুন, রিটার্ন বা পুনরায় প্রিন্ট", "fileText", "sales:read"],
  ["/orders", "কোটেশন ও অর্ডার", "কোটেশন, ডেলিভারি ও ইনভয়েস", "fileText", "orders:read"],
  ["/inventory", "স্টক", "বর্তমান মজুত, ট্রান্সফার ও সমন্বয়", "box", "inventory:read"],
  ["/stock-count", "স্টক গণনা", "বাস্তব মজুত গুনে সিস্টেমের সাথে মেলান", "check", "inventory:read"],
  ["/reorder", "কী কিনবেন", "চাহিদা ও মজুত ধরে ক্রয় পরিকল্পনা", "zap", "purchases:read"],
  ["/purchases", "ক্রয়", "অর্ডার, রিসিভ ও সরবরাহকারীর বাকি", "truck", "purchases:read"],
  ["/purchase-returns", "সাপ্লায়ার ক্লেইম", "ক্রয় ফেরত, dispatch ও credit note", "undo", "purchase_returns:read"],
  ["/directory", "কাস্টমার ও সাপ্লায়ার", "পার্টি, বাকি ও ইতিহাস", "users", "customers:read"],
  ["/accounts", "বাকি ও খরচ", "পাওনা, দেনা ও দৈনিক খরচ", "card", "ledger:read"],
  ["/accounting", "আর্থিক প্রতিবেদন", "ট্রায়াল ব্যালেন্স ও লাভ-ক্ষতি", "fileText", "ledger:read"],
  ["/cash", "ক্যাশ মেলান", "দিনশেষে বই ও ড্রয়ার মিলিয়ে নিন", "wallet", "cash:read"],
  ["/approvals", "অনুমোদন", "অপেক্ষায় থাকা সিদ্ধান্তগুলো", "check", "approvals:read"],
  ["/strategy", "আজকের করণীয়", "ব্যবসার তথ্য থেকে অগ্রাধিকার", "target", "recommendations:read"],
  ["/reports", "রিপোর্ট", "Excel, print ও বিস্তারিত রিপোর্ট", "download", "ledger:read"],
  ["/setup", "ব্যবসা ও শাখা", "প্রোফাইল, শাখা ও সেটআপ", "sliders", null],
  ["/staff", "কর্মী ও ভূমিকা", "কর্মী, অনুমতি ও invite", "userCheck", "staff:read"],
];

function pendingCount(orgId) {
  if (!orgId) return 0;
  try { return JSON.parse(localStorage.getItem(`pos.queue.${orgId}`) || "[]").length; } catch { return 0; }
}

export default function WorkspaceBar({ onMenu }) {
  const business = useBusiness();
  const { branches, branch, setBranch, current } = useBranch(business.active?.id);
  const { can } = usePermissions();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [online, setOnline] = useState(navigator.onLine);
  const queued = pendingCount(business.active?.id);

  useEffect(() => {
    const down = () => setOnline(false); const up = () => setOnline(true);
    const shortcut = (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault(); setOpen((value) => !value);
      }
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("offline", down); window.addEventListener("online", up);
    window.addEventListener("keydown", shortcut);
    return () => { window.removeEventListener("offline", down); window.removeEventListener("online", up); window.removeEventListener("keydown", shortcut); };
  }, []);

  const results = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("bn-BD");
    return COMMANDS.filter(([, title, hint, , permission]) => (!permission || can(permission))
      && (!needle || `${title} ${hint}`.toLocaleLowerCase("bn-BD").includes(needle)));
  }, [query, can]);

  const go = (to) => { navigate(to); setOpen(false); setQuery(""); };

  return (
    <>
      <header className="workspace-bar">
        <button type="button" className="workspace-menu" onClick={onMenu} aria-label="মেনু খুলুন"><Icon name="menu" /></button>
        <div className="workspace-context">
          <div className="workspace-context__business">
            <span>ব্যবসা</span><strong>{business.active?.name || "B-SMART"}</strong>
          </div>
          <span className="workspace-divider" />
          <label className="workspace-branch">
            <span>শাখা</span>
            <select value={branch} onChange={(e) => setBranch(e.target.value)} disabled={!branches?.length}>
              {(branches || []).map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
            </select>
          </label>
        </div>
        <button type="button" className="command-trigger" onClick={() => setOpen(true)}>
          <Icon name="search" size={18} /><span>পাতা বা কাজ খুঁজুন</span><kbd>Ctrl K</kbd>
        </button>
        <div className={`sync-state ${online ? "is-online" : "is-offline"}`} title={current ? `${current.name} শাখা` : "সংযোগের অবস্থা"}>
          <i />{online ? (queued ? `${queued}টি অপেক্ষায়` : "সিঙ্ক হয়েছে") : "অফলাইন"}
        </div>
      </header>

      {open && (
        <div className="command-backdrop" role="presentation" onMouseDown={() => setOpen(false)}>
          <section className="command-palette" role="dialog" aria-modal="true" aria-label="দ্রুত খুঁজুন" onMouseDown={(e) => e.stopPropagation()}>
            <div className="command-search"><Icon name="search" /><input autoFocus value={query} onChange={(e) => setQuery(e.target.value)} placeholder="যেমন: বিক্রি, স্টক, রিপোর্ট…" /></div>
            <div className="command-results">
              {results.map(([to, title, hint, icon]) => (
                <button type="button" key={to} onClick={() => go(to)}>
                  <span className="command-icon"><Icon name={icon} /></span>
                  <span><strong>{title}</strong><small>{hint}</small></span>
                  <Icon name="chevronRight" size={17} />
                </button>
              ))}
              {!results.length && <p className="command-empty">এই নামে কোনো কাজ পাওয়া যায়নি।</p>}
            </div>
            <footer><span><kbd>Esc</kbd> বন্ধ</span><span>আপনার ভূমিকা অনুযায়ী ফলাফল</span></footer>
          </section>
        </div>
      )}
    </>
  );
}
