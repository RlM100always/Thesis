import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { useBusiness } from "../BusinessContext";
import { explain } from "../errors";
import { dateTimeBn, money } from "../format";
import { usePermissions } from "../PermissionContext";
import DataTable from "../ui/DataTable";
import { Badge, Button, Card, EmptyState, Field, Modal, Notice, PageHeader, Segmented } from "../ui/kit";
import { useToast } from "../ui/Toast";

const KIND_LABEL = { expense_amount: "খরচ", purchase_amount: "ক্রয় অর্ডার" };
const ROLE_LABEL = { manager: "ম্যানেজার", owner: "মালিক" };
const STATUS_LABEL = { pending: "অপেক্ষমাণ", approved: "অনুমোদিত", rejected: "বাতিল" };

// Held actions waiting for someone senior to say yes — an expense over the
// owner's own threshold today, more kinds later. Deciding replays the action
// through the exact same code a direct request would have used.
export default function ApprovalsPage() {
  const { active } = useBusiness();
  const { can } = usePermissions();
  const toast = useToast();
  const orgId = active?.id;
  const canDecide = can("approvals:decide");
  const canEditRules = can("settings:write");

  const [status, setStatus] = useState("pending");
  const [rows, setRows] = useState(null);
  const [rules, setRules] = useState(null);
  const [error, setError] = useState("");
  const [deciding, setDeciding] = useState(null); // { request, action }
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [editingRule, setEditingRule] = useState(null);
  const [ruleForm, setRuleForm] = useState({ threshold: "", approver_role: "owner" });

  const load = useCallback(() => {
    if (!orgId) return;
    api.approvals(orgId, status).then(setRows).catch((e) => { setError(explain(e)); setRows([]); });
    if (canEditRules) api.approvalRules(orgId).then(setRules).catch(() => setRules([]));
  }, [orgId, status, canEditRules]);
  useEffect(() => { load(); }, [load]);

  async function decide() {
    setBusy(true);
    try {
      await api.decideApproval(orgId, deciding.request.id, deciding.action, reason);
      toast.success(deciding.action === "approve" ? "অনুমোদন করা হয়েছে — এখন এটি হিসাবে যোগ হয়েছে।" : "বাতিল করা হয়েছে।");
      setDeciding(null); setReason("");
      load();
    } catch (e) {
      toast.error(explain(e, { 409: "এটি ইতিমধ্যে সিদ্ধান্ত নেওয়া হয়ে গেছে।", 422: "বাতিলের কারণ লিখুন।" }));
    } finally { setBusy(false); }
  }

  async function saveRule(e) {
    e.preventDefault();
    setBusy(true);
    try {
      await api.updateApprovalRule(orgId, editingRule.kind, { threshold: ruleForm.threshold, approver_role: ruleForm.approver_role });
      toast.success("নিয়ম পরিবর্তন হয়েছে।");
      setEditingRule(null);
      load();
    } catch (e) {
      toast.error(explain(e));
    } finally { setBusy(false); }
  }

  return (
    <div className="page stack">
      <PageHeader title="অনুমোদনের তালিকা" subtitle="নির্দিষ্ট সীমার বেশি খরচ মালিকের অনুমোদন ছাড়া হিসাবে যোগ হয় না।" />
      {error && <Notice tone="danger">{error}</Notice>}

      {canEditRules && rules && rules.length > 0 && (
        <Card title="অনুমোদনের নিয়ম" subtitle="কোন ধরনের খরচ কত টাকার বেশি হলে কার অনুমোদন লাগবে।">
          <div className="ui-form">
            {rules.map((r) => (
              <div key={r.kind} className="row" style={{ justifyContent: "space-between" }}>
                <span>
                  <strong>{KIND_LABEL[r.kind] || r.kind}</strong> — {money(r.threshold)}-এর বেশি হলে {ROLE_LABEL[r.approver_role] || r.approver_role}-এর অনুমোদন লাগবে
                  {!r.active && <> <Badge>বন্ধ</Badge></>}
                </span>
                <Button size="sm" variant="secondary" onClick={() => { setEditingRule(r); setRuleForm({ threshold: String(r.threshold), approver_role: r.approver_role }); }}>বদলান</Button>
              </div>
            ))}
          </div>
        </Card>
      )}

      <div className="toolbar">
        <Segmented label="অবস্থা" value={status} onChange={setStatus} options={[
          { value: "pending", label: "অপেক্ষমাণ" }, { value: "approved", label: "অনুমোদিত" },
          { value: "rejected", label: "বাতিল" }, { value: "all", label: "সব" },
        ]} />
      </div>

      <Card pad={false}>
        <DataTable rowKey="id" loading={rows === null} rows={rows || []} caption="অনুমোদনের তালিকা"
                   empty={<EmptyState icon="check" title="এখানে কিছু নেই" hint={status === "pending" ? "কোনো খরচ এখন অনুমোদনের অপেক্ষায় নেই।" : "কিছু নেই।"} />}
                   columns={[
                     { key: "kind", label: "ধরন", primary: true, render: (r) => (
                       <div><strong>{KIND_LABEL[r.kind] || r.kind}</strong>
                         {(r.payload?.category || r.payload?.order_number) && <div className="muted" style={{ fontSize: 12.5 }}>{r.payload.category || r.payload.order_number}</div>}
                       </div>) },
                     { key: "amount", label: "টাকা", align: "right", render: (r) => money(r.amount) },
                     { key: "requested_by", label: "অনুরোধ করেছেন", render: (r) => <div>{r.requested_by || "—"}<div className="muted" style={{ fontSize: 12 }}>{dateTimeBn(r.requested_at)}</div></div> },
                     { key: "status", label: "অবস্থা", render: (r) => (
                       <Badge tone={r.status === "pending" ? "warn" : r.status === "approved" ? "success" : "danger"}>{STATUS_LABEL[r.status]}</Badge>) },
                     { key: "decided", label: "সিদ্ধান্ত", render: (r) => (r.decided_by ? <div>{r.decided_by}{r.decision_reason && <div className="muted" style={{ fontSize: 12 }}>{r.decision_reason}</div>}</div> : "—") },
                     ...(canDecide ? [{
                       key: "actions", label: "", align: "right", render: (r) => r.status === "pending" && (
                         <div className="row" style={{ gap: 6, flexWrap: "nowrap", justifyContent: "flex-end" }}>
                           <Button size="sm" onClick={() => { setReason(""); setDeciding({ request: r, action: "approve" }); }}>অনুমোদন</Button>
                           <Button size="sm" variant="danger" onClick={() => { setReason(""); setDeciding({ request: r, action: "reject" }); }}>বাতিল</Button>
                         </div>),
                     }] : []),
                   ]} />
      </Card>

      <Modal open={Boolean(deciding)} title={deciding?.action === "approve" ? "অনুমোদন করবেন?" : "বাতিল করবেন?"} onClose={() => setDeciding(null)}
             footer={<>
               <Button variant="secondary" onClick={() => setDeciding(null)}>ফিরে যান</Button>
               <Button variant={deciding?.action === "reject" ? "danger" : "primary"} loading={busy}
                       disabled={deciding?.action === "reject" && reason.trim().length < 2} onClick={decide}>
                 {deciding?.action === "approve" ? "হ্যাঁ, অনুমোদন করুন" : "হ্যাঁ, বাতিল করুন"}
               </Button>
             </>}>
        {deciding && (
          <div className="ui-form">
            <Notice tone="info">{KIND_LABEL[deciding.request.kind] || deciding.request.kind} — {money(deciding.request.amount)}, অনুরোধ করেছেন {deciding.request.requested_by}।</Notice>
            <Field label={deciding.action === "reject" ? "বাতিলের কারণ" : "মন্তব্য (ঐচ্ছিক)"} required={deciding.action === "reject"}>
              <input value={reason} onChange={(e) => setReason(e.target.value)} autoComplete="off" />
            </Field>
          </div>
        )}
      </Modal>

      <Modal open={Boolean(editingRule)} title="নিয়ম পরিবর্তন করুন" onClose={() => setEditingRule(null)}
             footer={<><Button variant="secondary" onClick={() => setEditingRule(null)}>বাতিল</Button><Button type="submit" form="rule-form" loading={busy}>সংরক্ষণ করুন</Button></>}>
        <form id="rule-form" className="ui-form" onSubmit={saveRule}>
          <Field label="সীমা (৳)" hint="এর বেশি হলে অনুমোদন লাগবে">
            <input type="number" min="0" step="0.01" value={ruleForm.threshold} onChange={(e) => setRuleForm({ ...ruleForm, threshold: e.target.value })} />
          </Field>
          <Field label="কার অনুমোদন লাগবে">
            <select value={ruleForm.approver_role} onChange={(e) => setRuleForm({ ...ruleForm, approver_role: e.target.value })}>
              <option value="manager">ম্যানেজার</option>
              <option value="owner">মালিক</option>
            </select>
          </Field>
        </form>
      </Modal>
    </div>
  );
}
