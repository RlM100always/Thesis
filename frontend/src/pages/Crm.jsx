import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { useBusiness } from "../BusinessContext";
import { explain } from "../errors";
import { dateTimeBn, money, num } from "../format";
import DataTable from "../ui/DataTable";
import { Badge, Button, Card, EmptyState, Field, Modal, PageHeader, Segmented } from "../ui/kit";
import { useToast } from "../ui/Toast";

const TICKET_STATUS = { open: "খোলা", pending: "অপেক্ষমাণ", resolved: "সমাধান হয়েছে", closed: "বন্ধ" };
const TICKET_PRIORITY = { low: "কম", normal: "সাধারণ", high: "উচ্চ", urgent: "জরুরি" };
const LEAD_STAGE = { new: "নতুন", qualified: "যোগ্য", quoted: "কোটেশন দেওয়া হয়েছে", won: "জিতেছে", lost: "হারিয়েছে" };

// ── Tickets ──────────────────────────────────────────────────────────────────

function TicketsTab() {
  const { active } = useBusiness();
  const toast = useToast();
  const orgId = active?.id;
  const [rows, setRows] = useState(null);
  const [status, setStatus] = useState("");
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ subject: "", priority: "normal" });
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    if (!orgId) return;
    api.tickets(orgId, status).then(setRows).catch((e) => { toast.error(explain(e)); setRows([]); });
  }, [orgId, status, toast]);
  useEffect(() => { load(); }, [load]);

  async function create(e) {
    e.preventDefault();
    setBusy(true);
    try { await api.createTicket(orgId, form); toast.success("টিকেট তৈরি হয়েছে।"); setCreating(false); setForm({ subject: "", priority: "normal" }); load(); }
    catch (e2) { toast.error(explain(e2)); } finally { setBusy(false); }
  }

  async function updateStatus(id, newStatus) {
    try { await api.updateTicket(orgId, id, { status: newStatus }); toast.success("পরিবর্তন হয়েছে।"); load(); }
    catch (e) { toast.error(explain(e)); }
  }

  return (
    <div className="stack">
      <div className="toolbar">
        <Segmented label="অবস্থা" value={status} onChange={setStatus} options={[
          { value: "", label: "সব" }, { value: "open", label: "খোলা" }, { value: "pending", label: "অপেক্ষমাণ" }, { value: "resolved", label: "সমাধান" },
        ]} />
        <Button onClick={() => setCreating(true)}>নতুন টিকেট</Button>
      </div>
      <Card pad={false}>
        <DataTable rowKey="id" loading={rows === null} rows={rows || []} caption="সাপোর্ট টিকেট"
                   empty={<EmptyState icon="info" title="কোনো টিকেট নেই" />}
                   columns={[
                     { key: "subject", label: "বিষয়", primary: true, render: (r) => r.subject },
                     { key: "priority", label: "গুরুত্ব", render: (r) => <Badge tone={r.priority === "urgent" ? "danger" : r.priority === "high" ? "warn" : "neutral"}>{TICKET_PRIORITY[r.priority]}</Badge> },
                     { key: "status", label: "অবস্থা", render: (r) => <Badge tone={r.status === "resolved" || r.status === "closed" ? "success" : "warn"}>{TICKET_STATUS[r.status]}</Badge> },
                     { key: "created", label: "সময়", render: (r) => dateTimeBn(r.created_at) },
                     { key: "actions", label: "", align: "right", render: (r) => r.status !== "resolved" && r.status !== "closed" && (
                       <Button size="sm" variant="secondary" onClick={() => updateStatus(r.id, "resolved")}>সমাধান হয়েছে</Button>) },
                   ]} />
      </Card>
      <Modal open={creating} title="নতুন টিকেট" onClose={() => setCreating(false)}
             footer={<><Button variant="secondary" onClick={() => setCreating(false)}>বাতিল</Button><Button type="submit" form="ticket-form" loading={busy}>তৈরি করুন</Button></>}>
        <form id="ticket-form" className="ui-form" onSubmit={create}>
          <Field label="বিষয়"><input required value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} /></Field>
          <Field label="গুরুত্ব">
            <select value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })}>
              {Object.entries(TICKET_PRIORITY).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </Field>
        </form>
      </Modal>
    </div>
  );
}

// ── Leads ────────────────────────────────────────────────────────────────────

function LeadsTab() {
  const { active } = useBusiness();
  const toast = useToast();
  const orgId = active?.id;
  const [rows, setRows] = useState(null);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ name: "", source: "" });
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    if (!orgId) return;
    api.leads(orgId).then(setRows).catch(() => setRows([]));
  }, [orgId]);
  useEffect(() => { load(); }, [load]);

  async function create(e) {
    e.preventDefault();
    setBusy(true);
    try { await api.createLead(orgId, form); toast.success("লিড যোগ হয়েছে।"); setCreating(false); setForm({ name: "", source: "" }); load(); }
    catch (e2) { toast.error(explain(e2)); } finally { setBusy(false); }
  }

  async function convert(id) {
    try { await api.convertLead(orgId, id); toast.success("কাস্টমারে রূপান্তরিত হয়েছে।"); load(); }
    catch (e) { toast.error(explain(e)); }
  }

  return (
    <div className="stack">
      <div className="toolbar"><Button onClick={() => setCreating(true)}>নতুন লিড</Button></div>
      <Card pad={false}>
        <DataTable rowKey="id" loading={rows === null} rows={rows || []} caption="বিক্রয় লিড"
                   empty={<EmptyState icon="target" title="কোনো লিড নেই" />}
                   columns={[
                     { key: "name", label: "নাম", primary: true, render: (r) => r.name },
                     { key: "stage", label: "ধাপ", render: (r) => <Badge tone={r.stage === "won" ? "success" : r.stage === "lost" ? "danger" : "neutral"}>{LEAD_STAGE[r.stage]}</Badge> },
                     { key: "value", label: "সম্ভাব্য মূল্য", render: (r) => r.estimated_value ? money(r.estimated_value) : "—" },
                     { key: "actions", label: "", align: "right", render: (r) => !["won", "lost"].includes(r.stage) && (
                       <Button size="sm" onClick={() => convert(r.id)}>কাস্টমারে রূপান্তর</Button>) },
                   ]} />
      </Card>
      <Modal open={creating} title="নতুন লিড" onClose={() => setCreating(false)}
             footer={<><Button variant="secondary" onClick={() => setCreating(false)}>বাতিল</Button><Button type="submit" form="lead-form" loading={busy}>যোগ করুন</Button></>}>
        <form id="lead-form" className="ui-form" onSubmit={create}>
          <Field label="নাম"><input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
          <Field label="উৎস (ঐচ্ছিক)"><input value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value })} /></Field>
        </form>
      </Modal>
    </div>
  );
}

// ── Feedback ─────────────────────────────────────────────────────────────────

function FeedbackTab() {
  const { active } = useBusiness();
  const orgId = active?.id;
  const [rows, setRows] = useState(null);
  const [summary, setSummary] = useState(null);

  useEffect(() => {
    if (!orgId) return;
    api.feedbackList(orgId).then(setRows).catch(() => setRows([]));
    api.feedbackSummary(orgId).then(setSummary).catch(() => setSummary(null));
  }, [orgId]);

  return (
    <div className="stack">
      {summary && summary.count > 0 && (
        <div className="ui-stats">
          <div className="ui-stat"><span className="ui-stat__label">NPS</span><strong className="ui-stat__value">{summary.nps}</strong></div>
          <div className="ui-stat"><span className="ui-stat__label">গড় স্কোর</span><strong className="ui-stat__value">{summary.average_score}</strong></div>
          <div className="ui-stat"><span className="ui-stat__label">প্রমোটার</span><strong className="ui-stat__value">{num(summary.promoters)}</strong></div>
          <div className="ui-stat"><span className="ui-stat__label">ডিট্র্যাক্টর</span><strong className="ui-stat__value">{num(summary.detractors)}</strong></div>
        </div>
      )}
      <Card pad={false} title="সাম্প্রতিক ফিডব্যাক">
        <DataTable rowKey="id" loading={rows === null} rows={rows || []} caption="কাস্টমার ফিডব্যাক"
                   empty={<EmptyState icon="userCheck" title="এখনো কোনো ফিডব্যাক নেই" />}
                   columns={[
                     { key: "score", label: "স্কোর", render: (r) => <Badge tone={r.score >= 9 ? "success" : r.score <= 6 ? "danger" : "warn"}>{r.score}/10</Badge> },
                     { key: "comment", label: "মন্তব্য", render: (r) => r.comment || "—" },
                     { key: "time", label: "সময়", render: (r) => dateTimeBn(r.created_at) },
                     { key: "ticket", label: "ফলো-আপ টিকেট", render: (r) => r.follow_up_ticket_id ? <Badge tone="warn">তৈরি হয়েছে</Badge> : "—" },
                   ]} />
      </Card>
    </div>
  );
}

const TABS = [
  { value: "tickets", label: "সাপোর্ট টিকেট" },
  { value: "leads", label: "লিড" },
  { value: "feedback", label: "ফিডব্যাক" },
];

export default function CrmPage() {
  const [tab, setTab] = useState("tickets");
  return (
    <div className="page stack">
      <PageHeader title="টিকেট, লিড ও ফিডব্যাক" subtitle="কাস্টমার সাপোর্ট, বিক্রয়ের সম্ভাবনা এবং সন্তুষ্টি — এক জায়গায়।" />
      <Segmented value={tab} onChange={setTab} options={TABS} />
      {tab === "tickets" && <TicketsTab />}
      {tab === "leads" && <LeadsTab />}
      {tab === "feedback" && <FeedbackTab />}
    </div>
  );
}
