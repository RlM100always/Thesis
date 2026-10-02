import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { useBusiness } from "../BusinessContext";
import { explain } from "../errors";
import { dateBn, dateTimeBn, money } from "../format";
import { usePermissions } from "../PermissionContext";
import useBranch from "../useBranch";
import DataTable from "../ui/DataTable";
import { Badge, Button, Card, EmptyState, Field, Notice, PageHeader, Segmented } from "../ui/kit";
import { useToast } from "../ui/Toast";

const LEAVE_STATUS = { pending: "অপেক্ষমাণ", approved: "অনুমোদিত", rejected: "বাতিল", cancelled: "বাতিল করা হয়েছে" };
const ADVANCE_STATUS = { outstanding: "বাকি আছে", settled: "পরিশোধিত" };
const PAYROLL_STATUS = { draft: "খসড়া", approved: "অনুমোদিত", paid: "পরিশোধিত" };

// ── Attendance ───────────────────────────────────────────────────────────────

function AttendanceTab() {
  const { active } = useBusiness();
  const { can } = usePermissions();
  const toast = useToast();
  const orgId = active?.id;
  const [mine, setMine] = useState(null);
  const [team, setTeam] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    if (!orgId) return;
    api.myAttendance(orgId).then(setMine).catch(() => setMine([]));
    if (can("attendance:read")) api.teamAttendance(orgId).then(setTeam).catch(() => setTeam([]));
  }, [orgId, can]);
  useEffect(() => { load(); }, [load]);

  const open = mine?.find((r) => !r.check_out_at);

  async function act(fn) {
    setBusy(true);
    try { await fn(); load(); } catch (e) { toast.error(explain(e)); } finally { setBusy(false); }
  }

  return (
    <div className="stack">
      <Card title="আমার উপস্থিতি">
        {open ? (
          <Notice tone="info" action={<Button loading={busy} onClick={() => act(() => api.checkOut(orgId))}>চেক-আউট করুন</Button>}>
            {dateTimeBn(open.check_in_at)}-এ চেক-ইন করেছেন — এখনো চেক-আউট করেননি।
          </Notice>
        ) : (
          <Button loading={busy} onClick={() => act(() => api.checkIn(orgId, {}))}>চেক-ইন করুন</Button>
        )}
      </Card>
      <Card pad={false} title="আমার ইতিহাস">
        <DataTable rowKey="id" loading={mine === null} rows={mine || []} caption="উপস্থিতির ইতিহাস"
                   empty={<EmptyState icon="clock" title="কোনো রেকর্ড নেই" />}
                   columns={[
                     { key: "in", label: "চেক-ইন", render: (r) => dateTimeBn(r.check_in_at) },
                     { key: "out", label: "চেক-আউট", render: (r) => dateTimeBn(r.check_out_at) },
                     { key: "source", label: "উৎস", render: (r) => r.source === "manager_correction" ? <Badge tone="warn">সংশোধিত</Badge> : "ডিভাইস" },
                   ]} />
      </Card>
      {can("attendance:read") && (
        <Card pad={false} title="সবার উপস্থিতি (টিম)">
          <DataTable rowKey="id" loading={team === null} rows={(team || []).slice(0, 50)} caption="টিমের উপস্থিতি"
                     empty={<EmptyState icon="users" title="কোনো রেকর্ড নেই" />}
                     columns={[
                       { key: "user", label: "ইউজার আইডি", render: (r) => r.user_id.slice(0, 8) },
                       { key: "in", label: "চেক-ইন", render: (r) => dateTimeBn(r.check_in_at) },
                       { key: "out", label: "চেক-আউট", render: (r) => dateTimeBn(r.check_out_at) },
                     ]} />
        </Card>
      )}
    </div>
  );
}

// ── Leave ────────────────────────────────────────────────────────────────────

function LeaveTab() {
  const { active } = useBusiness();
  const { can } = usePermissions();
  const toast = useToast();
  const orgId = active?.id;
  const [mine, setMine] = useState(null);
  const [team, setTeam] = useState(null);
  const [form, setForm] = useState({ start_date: "", end_date: "", reason: "", leave_type: "casual" });
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    if (!orgId) return;
    api.myLeave(orgId).then(setMine).catch(() => setMine([]));
    if (can("leave:decide")) api.teamLeave(orgId, "pending").then(setTeam).catch(() => setTeam([]));
  }, [orgId, can]);
  useEffect(() => { load(); }, [load]);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    try {
      await api.requestLeave(orgId, form);
      toast.success("আবেদন জমা হয়েছে।");
      setForm({ start_date: "", end_date: "", reason: "", leave_type: "casual" });
      load();
    } catch (e2) { toast.error(explain(e2)); } finally { setBusy(false); }
  }

  async function decide(id, status) {
    try { await api.decideLeave(orgId, id, { status }); toast.success("সিদ্ধান্ত নেওয়া হয়েছে।"); load(); }
    catch (e) { toast.error(explain(e)); }
  }

  return (
    <div className="stack">
      <Card title="ছুটির আবেদন করুন">
        <form className="ui-form" onSubmit={submit}>
          <div className="row">
            <Field label="শুরু"><input type="date" required value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} /></Field>
            <Field label="শেষ"><input type="date" required value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })} /></Field>
          </div>
          <Field label="কারণ (ঐচ্ছিক)"><input value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} /></Field>
          <Button type="submit" loading={busy}>আবেদন জমা দিন</Button>
        </form>
      </Card>
      {can("leave:decide") && team && team.length > 0 && (
        <Card pad={false} title="অনুমোদনের অপেক্ষায়">
          <DataTable rowKey="id" rows={team} caption="ছুটির অনুরোধ"
                     columns={[
                       { key: "period", label: "সময়কাল", render: (r) => `${dateBn(r.start_date)} – ${dateBn(r.end_date)}` },
                       { key: "reason", label: "কারণ", render: (r) => r.reason || "—" },
                       { key: "actions", label: "", align: "right", render: (r) => (
                         <div className="row" style={{ gap: 6, justifyContent: "flex-end" }}>
                           <Button size="sm" onClick={() => decide(r.id, "approved")}>অনুমোদন</Button>
                           <Button size="sm" variant="danger" onClick={() => decide(r.id, "rejected")}>বাতিল</Button>
                         </div>) },
                     ]} />
        </Card>
      )}
      <Card pad={false} title="আমার আবেদনের ইতিহাস">
        <DataTable rowKey="id" loading={mine === null} rows={mine || []} caption="ছুটির ইতিহাস"
                   empty={<EmptyState icon="userCheck" title="কোনো আবেদন নেই" />}
                   columns={[
                     { key: "period", label: "সময়কাল", render: (r) => `${dateBn(r.start_date)} – ${dateBn(r.end_date)}` },
                     { key: "status", label: "অবস্থা", render: (r) => <Badge tone={r.status === "approved" ? "success" : r.status === "rejected" ? "danger" : "warn"}>{LEAVE_STATUS[r.status]}</Badge> },
                   ]} />
      </Card>
    </div>
  );
}

// ── Roster ───────────────────────────────────────────────────────────────────

function RosterTab() {
  const { active } = useBusiness();
  const { can } = usePermissions();
  const orgId = active?.id;
  const { branch } = useBranch(orgId);
  const [mine, setMine] = useState(null);
  const [team, setTeam] = useState(null);

  const load = useCallback(() => {
    if (!orgId) return;
    api.myRoster(orgId).then(setMine).catch(() => setMine([]));
    if (can("staff:read")) api.teamRoster(orgId, branch).then(setTeam).catch(() => setTeam([]));
  }, [orgId, branch, can]);
  useEffect(() => { load(); }, [load]);

  return (
    <div className="stack">
      <Card pad={false} title="আমার শিফট">
        <DataTable rowKey="id" loading={mine === null} rows={mine || []} caption="আমার শিফট"
                   empty={<EmptyState icon="calendar" title="কোনো শিফট নির্ধারিত নেই" />}
                   columns={[
                     { key: "date", label: "তারিখ", render: (r) => dateBn(r.shift_date) },
                     { key: "time", label: "সময়", render: (r) => `${r.start_time} – ${r.end_time}` },
                     { key: "station", label: "স্টেশন", render: (r) => r.station || "—" },
                   ]} />
      </Card>
      {can("staff:read") && (
        <Card pad={false} title="সবার শিফট">
          <DataTable rowKey="id" loading={team === null} rows={team || []} caption="টিমের শিফট"
                     empty={<EmptyState icon="calendar" title="কোনো শিফট নেই" />}
                     columns={[
                       { key: "user", label: "ইউজার আইডি", render: (r) => r.user_id.slice(0, 8) },
                       { key: "date", label: "তারিখ", render: (r) => dateBn(r.shift_date) },
                       { key: "time", label: "সময়", render: (r) => `${r.start_time} – ${r.end_time}` },
                     ]} />
        </Card>
      )}
    </div>
  );
}

// ── Commission & Targets ─────────────────────────────────────────────────────

function CommissionTab() {
  const { active } = useBusiness();
  const { can } = usePermissions();
  const toast = useToast();
  const orgId = active?.id;
  const [mine, setMine] = useState(null);
  const [team, setTeam] = useState(null);
  const [rule, setRule] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    if (!orgId) return;
    api.myCommission(orgId).then(setMine).catch(() => setMine({ balance: 0, entries: [] }));
    if (can("commission:read")) { api.teamCommission(orgId).then(setTeam).catch(() => setTeam([])); api.commissionRule(orgId).then(setRule).catch(() => setRule(null)); }
  }, [orgId, can]);
  useEffect(() => { load(); }, [load]);

  async function toggleRule() {
    setBusy(true);
    try { await api.updateCommissionRule(orgId, { active: !rule.active }); toast.success("পরিবর্তন হয়েছে।"); load(); }
    catch (e) { toast.error(explain(e)); } finally { setBusy(false); }
  }

  return (
    <div className="stack">
      <div className="ui-stats">
        <div className="ui-stat"><span className="ui-stat__label">আমার কমিশন ব্যালেন্স</span><strong className="ui-stat__value">{mine ? money(mine.balance) : "—"}</strong></div>
      </div>
      {can("settings:write") && rule && (
        <Card title="কমিশনের নিয়ম" subtitle={`বর্তমান হার: ${rule.rate_percent}%`}>
          <Button variant="secondary" loading={busy} onClick={toggleRule}>{rule.active ? "বন্ধ করুন" : "চালু করুন"}</Button>
        </Card>
      )}
      {can("commission:read") && team && (
        <Card pad={false} title="টিমের কমিশন">
          <DataTable rowKey="user_id" rows={team} caption="টিমের কমিশন ব্যালেন্স"
                     empty={<EmptyState icon="wallet" title="কোনো কমিশন নেই" />}
                     columns={[
                       { key: "name", label: "নাম", render: (r) => r.name },
                       { key: "balance", label: "ব্যালেন্স", align: "right", render: (r) => money(r.balance) },
                     ]} />
        </Card>
      )}
    </div>
  );
}

// ── Advances ─────────────────────────────────────────────────────────────────

function AdvancesTab() {
  const { active } = useBusiness();
  const { can } = usePermissions();
  const toast = useToast();
  const orgId = active?.id;
  const [mine, setMine] = useState(null);
  const [team, setTeam] = useState(null);
  const [repayAmount, setRepayAmount] = useState({});
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    if (!orgId) return;
    api.myAdvances(orgId).then(setMine).catch(() => setMine([]));
    if (can("advances:read")) api.teamAdvances(orgId).then(setTeam).catch(() => setTeam([]));
  }, [orgId, can]);
  useEffect(() => { load(); }, [load]);

  async function repay(id) {
    const amount = repayAmount[id];
    if (!amount) return;
    setBusy(true);
    try { await api.repayAdvance(orgId, id, { amount }); toast.success("পরিশোধ রেকর্ড হয়েছে।"); load(); }
    catch (e) { toast.error(explain(e)); } finally { setBusy(false); }
  }

  return (
    <div className="stack">
      <Card pad={false} title="আমার অগ্রিম">
        <DataTable rowKey="id" loading={mine === null} rows={mine || []} caption="অগ্রিম"
                   empty={<EmptyState icon="wallet" title="কোনো অগ্রিম নেই" />}
                   columns={[
                     { key: "amount", label: "টাকা", render: (r) => money(r.amount) },
                     { key: "outstanding", label: "বাকি", render: (r) => money(r.outstanding_amount) },
                     { key: "status", label: "অবস্থা", render: (r) => <Badge tone={r.status === "settled" ? "success" : "warn"}>{ADVANCE_STATUS[r.status]}</Badge> },
                   ]} />
      </Card>
      {can("advances:read") && (
        <Card pad={false} title="টিমের অগ্রিম">
          <DataTable rowKey="id" loading={team === null} rows={team || []} caption="টিমের অগ্রিম"
                     empty={<EmptyState icon="wallet" title="কোনো অগ্রিম নেই" />}
                     columns={[
                       { key: "user", label: "ইউজার", render: (r) => r.user_id.slice(0, 8) },
                       { key: "amount", label: "টাকা", render: (r) => money(r.amount) },
                       { key: "outstanding", label: "বাকি", render: (r) => money(r.outstanding_amount) },
                       { key: "status", label: "অবস্থা", render: (r) => <Badge tone={r.status === "settled" ? "success" : "warn"}>{ADVANCE_STATUS[r.status]}</Badge> },
                       { key: "repay", label: "", align: "right", render: (r) => r.status === "outstanding" && (
                         <div className="row" style={{ gap: 6, justifyContent: "flex-end" }}>
                           <input style={{ width: 90 }} type="number" placeholder="টাকা" onChange={(e) => setRepayAmount({ ...repayAmount, [r.id]: e.target.value })} />
                           <Button size="sm" loading={busy} onClick={() => repay(r.id)}>পরিশোধ</Button>
                         </div>) },
                     ]} />
        </Card>
      )}
    </div>
  );
}

// ── Payroll ──────────────────────────────────────────────────────────────────

function PayrollTab() {
  const { active } = useBusiness();
  const { can } = usePermissions();
  const toast = useToast();
  const orgId = active?.id;
  const [runs, setRuns] = useState(null);
  const [payslips, setPayslips] = useState(null);
  const [form, setForm] = useState({ period_start: "", period_end: "" });
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    if (!orgId) return;
    api.myPayslips(orgId).then(setPayslips).catch(() => setPayslips([]));
    if (can("payroll:read")) api.payrollRuns(orgId).then(setRuns).catch(() => setRuns([]));
  }, [orgId, can]);
  useEffect(() => { load(); }, [load]);

  async function createRun(e) {
    e.preventDefault();
    setBusy(true);
    try { await api.createPayrollRun(orgId, form); toast.success("খসড়া তৈরি হয়েছে।"); load(); }
    catch (e2) { toast.error(explain(e2)); } finally { setBusy(false); }
  }

  async function act(fn, msg) {
    setBusy(true);
    try { await fn(); toast.success(msg); load(); } catch (e) { toast.error(explain(e)); } finally { setBusy(false); }
  }

  return (
    <div className="stack">
      {can("payroll:write") && (
        <Card title="নতুন পে-রোল রান তৈরি করুন">
          <form className="ui-form" onSubmit={createRun}>
            <div className="row">
              <Field label="শুরু"><input type="date" required value={form.period_start} onChange={(e) => setForm({ ...form, period_start: e.target.value })} /></Field>
              <Field label="শেষ"><input type="date" required value={form.period_end} onChange={(e) => setForm({ ...form, period_end: e.target.value })} /></Field>
            </div>
            <Button type="submit" loading={busy}>খসড়া তৈরি করুন</Button>
          </form>
        </Card>
      )}
      {can("payroll:read") && (
        <Card pad={false} title="পে-রোল রান">
          <DataTable rowKey="id" loading={runs === null} rows={runs || []} caption="পে-রোল রান"
                     empty={<EmptyState icon="wallet" title="কোনো রান নেই" />}
                     columns={[
                       { key: "period", label: "সময়কাল", render: (r) => `${dateBn(r.period_start)} – ${dateBn(r.period_end)}` },
                       { key: "status", label: "অবস্থা", render: (r) => <Badge tone={r.status === "paid" ? "success" : r.status === "approved" ? "info" : "warn"}>{PAYROLL_STATUS[r.status]}</Badge> },
                       { key: "actions", label: "", align: "right", render: (r) => (
                         <div className="row" style={{ gap: 6, justifyContent: "flex-end" }}>
                           {r.status === "draft" && can("payroll:approve") && <Button size="sm" loading={busy} onClick={() => act(() => api.approvePayrollRun(orgId, r.id), "অনুমোদিত হয়েছে।")}>অনুমোদন</Button>}
                           {r.status === "approved" && can("payroll:pay") && <Button size="sm" loading={busy} onClick={() => act(() => api.payPayrollRun(orgId, r.id), "পরিশোধিত হয়েছে।")}>পরিশোধ করুন</Button>}
                         </div>) },
                     ]} />
        </Card>
      )}
      <Card pad={false} title="আমার পে-স্লিপ">
        <DataTable rowKey="id" loading={payslips === null} rows={payslips || []} caption="পে-স্লিপ"
                   empty={<EmptyState icon="fileText" title="এখনো কোনো পে-স্লিপ নেই" hint="পরিশোধিত পে-রোল রান হলে এখানে দেখা যাবে।" />}
                   columns={[
                     { key: "period", label: "সময়কাল", render: (r) => `${dateBn(r.period_start)} – ${dateBn(r.period_end)}` },
                     { key: "base", label: "বেতন", render: (r) => money(r.base_salary) },
                     { key: "commission", label: "কমিশন", render: (r) => money(r.commission_amount) },
                     { key: "net", label: "মোট", render: (r) => <strong>{money(r.net_pay)}</strong> },
                   ]} />
      </Card>
    </div>
  );
}

// ── Page shell ───────────────────────────────────────────────────────────────

const TABS = [
  { value: "attendance", label: "উপস্থিতি" },
  { value: "leave", label: "ছুটি" },
  { value: "roster", label: "রোস্টার" },
  { value: "commission", label: "কমিশন" },
  { value: "advances", label: "অগ্রিম" },
  { value: "payroll", label: "পে-রোল" },
];

export default function WorkforcePage() {
  const [tab, setTab] = useState("attendance");
  return (
    <div className="page stack">
      <PageHeader title="কর্মী ও সময়" subtitle="উপস্থিতি, ছুটি, রোস্টার, কমিশন, অগ্রিম এবং পে-রোল — নিজের ও টিমের।" />
      <Segmented value={tab} onChange={setTab} options={TABS} />
      {tab === "attendance" && <AttendanceTab />}
      {tab === "leave" && <LeaveTab />}
      {tab === "roster" && <RosterTab />}
      {tab === "commission" && <CommissionTab />}
      {tab === "advances" && <AdvancesTab />}
      {tab === "payroll" && <PayrollTab />}
    </div>
  );
}
