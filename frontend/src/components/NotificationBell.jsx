import { useCallback, useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { api } from "../api";
import { useBusiness } from "../BusinessContext";
import { num } from "../format";
import Icon from "../ui/Icon";
import { Badge, EmptyState, Modal } from "../ui/kit";

const TONE = { danger: "danger", warn: "warn", info: "info" };
const REFRESH_MS = 120000;

// What needs attention right now, wherever you are in the app. Only what your role
// may see comes back from the server, so a cashier's bell never mentions money.
export default function NotificationBell({ className = "" }) {
  const { active } = useBusiness();
  const { pathname } = useLocation();
  const orgId = active?.id;
  const [data, setData] = useState({ count: 0, alerts: [] });
  const [open, setOpen] = useState(false);

  const load = useCallback(() => {
    if (!orgId) return;
    Promise.all([
      api.alerts(orgId).catch(() => ({ count: 0, alerts: [] })),
      api.notifications(orgId, true).catch(() => []),
    ]).then(([operational, notes]) => {
      const fromNotes = notes.map((n) => ({
        kind: `note-${n.id}`, href: "#/workforce",
        severity: n.severity === "critical" ? "danger" : n.severity === "warning" ? "warn" : "info",
        title: n.title,
      }));
      setData({ count: operational.count + notes.length, alerts: [...fromNotes, ...operational.alerts] });
    }).catch(() => { /* the bell is a convenience; stay quiet if it fails */ });
  }, [orgId]);

  useEffect(() => {
    load();
    const timer = setInterval(load, REFRESH_MS);
    return () => clearInterval(timer);
  }, [load, pathname]);

  const urgent = data.alerts.some((a) => a.severity === "danger");

  return (
    <>
      <button type="button" className={`bell ${urgent ? "urgent" : ""} ${className}`} onClick={() => { load(); setOpen(true); }}
              aria-label={data.count ? `${num(data.count)}টি সতর্কতা` : "কোনো সতর্কতা নেই"}>
        <Icon name="bell" size={20} />
        {data.count > 0 && <span className="bell__count">{num(data.count)}</span>}
      </button>
      <Modal open={open} title="যা এখন দেখা দরকার" onClose={() => setOpen(false)}>
        {data.alerts.length === 0 ? (
          <EmptyState icon="check" title="সবকিছু ঠিক আছে" hint="এই মুহূর্তে কোনো জরুরি বিষয় নেই।" />
        ) : (
          <ul className="alert-list">
            {data.alerts.map((a) => (
              <li key={a.kind}>
                <a href={a.href} onClick={() => setOpen(false)}>
                  <Badge tone={TONE[a.severity]} icon={a.severity === "info" ? "info" : "alert"}>{a.severity === "danger" ? "জরুরি" : a.severity === "warn" ? "সতর্ক" : "খেয়াল রাখুন"}</Badge>
                  <span>{a.title}</span>
                  <Icon name="chevronRight" size={16} />
                </a>
              </li>
            ))}
          </ul>
        )}
      </Modal>
    </>
  );
}
