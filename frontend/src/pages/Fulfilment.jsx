import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { useBusiness } from "../BusinessContext";
import { explain } from "../errors";
import { dateTimeBn, money } from "../format";
import { usePermissions } from "../PermissionContext";
import DataTable from "../ui/DataTable";
import { Badge, Button, Card, EmptyState, Field, Modal, PageHeader, Segmented } from "../ui/kit";
import { useToast } from "../ui/Toast";

const DELIVERY_STATUS = { assigned: "নির্ধারিত", out_for_delivery: "পথে আছে", delivered: "পৌঁছে গেছে", failed: "ব্যর্থ" };

// ── Reservations ─────────────────────────────────────────────────────────────

function ReservationsTab() {
  const { active } = useBusiness();
  const toast = useToast();
  const orgId = active?.id;
  const [rows, setRows] = useState(null);
  const [status, setStatus] = useState("active");

  const load = useCallback(() => {
    if (!orgId) return;
    api.reservations(orgId, status).then(setRows).catch(() => setRows([]));
  }, [orgId, status]);
  useEffect(() => { load(); }, [load]);

  async function release(documentId) {
    try { await api.releaseReservation(orgId, documentId); toast.success("স্টক ছেড়ে দেওয়া হয়েছে।"); load(); }
    catch (e) { toast.error(explain(e)); }
  }

  return (
    <div className="stack">
      <div className="toolbar">
        <Segmented label="অবস্থা" value={status} onChange={setStatus} options={[
          { value: "active", label: "সক্রিয়" }, { value: "released", label: "মুক্ত করা হয়েছে" }, { value: "fulfilled", label: "সম্পন্ন" },
        ]} />
      </div>
      <Card pad={false}>
        <DataTable rowKey="id" loading={rows === null} rows={rows || []} caption="স্টক রিজার্ভেশন"
                   empty={<EmptyState icon="box" title="কোনো রিজার্ভেশন নেই" hint="অর্ডার পাতা থেকে অর্ডারের জন্য স্টক হোল্ড করুন।" />}
                   columns={[
                     { key: "product", label: "পণ্য আইডি", render: (r) => r.product_id.slice(0, 8) },
                     { key: "quantity", label: "পরিমাণ", render: (r) => r.quantity },
                     { key: "status", label: "অবস্থা", render: (r) => <Badge tone={r.status === "active" ? "warn" : "neutral"}>{r.status}</Badge> },
                     { key: "expires", label: "মেয়াদ", render: (r) => dateTimeBn(r.expires_at) },
                     { key: "actions", label: "", align: "right", render: (r) => r.status === "active" && (
                       <Button size="sm" variant="danger" onClick={() => release(r.sales_document_id)}>মুক্ত করুন</Button>) },
                   ]} />
      </Card>
    </div>
  );
}

// ── Deliveries ───────────────────────────────────────────────────────────────

function DeliveriesTab() {
  const { active } = useBusiness();
  const { can } = usePermissions();
  const toast = useToast();
  const orgId = active?.id;
  const [mine, setMine] = useState(null);
  const [team, setTeam] = useState(null);
  const [completing, setCompleting] = useState(null);
  const [form, setForm] = useState({ status: "delivered", cod_collected: "", proof_note: "" });
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    if (!orgId) return;
    api.myDeliveries(orgId).then(setMine).catch(() => setMine([]));
    if (can("deliveries:read")) api.teamDeliveries(orgId).then(setTeam).catch(() => setTeam([]));
  }, [orgId, can]);
  useEffect(() => { load(); }, [load]);

  async function start(id) {
    try { await api.startDelivery(orgId, id); toast.success("যাত্রা শুরু হয়েছে।"); load(); }
    catch (e) { toast.error(explain(e)); }
  }

  async function complete(e) {
    e.preventDefault();
    setBusy(true);
    try {
      await api.completeDelivery(orgId, completing.id, { ...form, cod_collected: form.cod_collected || undefined });
      toast.success("ডেলিভারি সম্পন্ন হয়েছে।"); setCompleting(null); load();
    } catch (e2) { toast.error(explain(e2)); } finally { setBusy(false); }
  }

  return (
    <div className="stack">
      <Card pad={false} title="আমার ডেলিভারি">
        <DataTable rowKey="id" loading={mine === null} rows={mine || []} caption="আমার ডেলিভারি"
                   empty={<EmptyState icon="truck" title="কোনো ডেলিভারি নির্ধারিত নেই" />}
                   columns={[
                     { key: "status", label: "অবস্থা", render: (r) => <Badge tone={r.status === "delivered" ? "success" : r.status === "failed" ? "danger" : "warn"}>{DELIVERY_STATUS[r.status]}</Badge> },
                     { key: "cod", label: "COD প্রত্যাশিত", render: (r) => money(r.cod_amount_expected) },
                     { key: "actions", label: "", align: "right", render: (r) => (
                       <div className="row" style={{ gap: 6, justifyContent: "flex-end" }}>
                         {r.status === "assigned" && <Button size="sm" onClick={() => start(r.id)}>যাত্রা শুরু</Button>}
                         {r.status === "out_for_delivery" && <Button size="sm" onClick={() => { setForm({ status: "delivered", cod_collected: "", proof_note: "" }); setCompleting(r); }}>সম্পন্ন করুন</Button>}
                       </div>) },
                   ]} />
      </Card>
      {can("deliveries:read") && (
        <Card pad={false} title="সব ডেলিভারি">
          <DataTable rowKey="id" loading={team === null} rows={team || []} caption="টিমের ডেলিভারি"
                     empty={<EmptyState icon="truck" title="কোনো ডেলিভারি নেই" />}
                     columns={[
                       { key: "rider", label: "রাইডার", render: (r) => r.rider_user_id.slice(0, 8) },
                       { key: "status", label: "অবস্থা", render: (r) => <Badge tone={r.status === "delivered" ? "success" : r.status === "failed" ? "danger" : "warn"}>{DELIVERY_STATUS[r.status]}</Badge> },
                       { key: "cod", label: "COD", render: (r) => money(r.cod_amount_collected || 0) },
                     ]} />
        </Card>
      )}
      <Modal open={Boolean(completing)} title="ডেলিভারি সম্পন্ন করুন" onClose={() => setCompleting(null)}
             footer={<><Button variant="secondary" onClick={() => setCompleting(null)}>বাতিল</Button><Button type="submit" form="complete-form" loading={busy}>জমা দিন</Button></>}>
        <form id="complete-form" className="ui-form" onSubmit={complete}>
          <Field label="ফলাফল">
            <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
              <option value="delivered">পৌঁছে গেছে</option>
              <option value="failed">ব্যর্থ</option>
            </select>
          </Field>
          {form.status === "delivered" && <Field label="COD সংগ্রহ করা টাকা"><input type="number" min="0" step="0.01" value={form.cod_collected} onChange={(e) => setForm({ ...form, cod_collected: e.target.value })} /></Field>}
          {form.status === "failed" && <Field label="ব্যর্থতার কারণ" required><input required value={form.proof_note} onChange={(e) => setForm({ ...form, proof_note: e.target.value, failure_reason: e.target.value })} /></Field>}
        </form>
      </Modal>
    </div>
  );
}

const TABS = [
  { value: "deliveries", label: "ডেলিভারি" },
  { value: "reservations", label: "রিজার্ভেশন" },
];

export default function FulfilmentPage() {
  const [tab, setTab] = useState("deliveries");
  return (
    <div className="page stack">
      <PageHeader title="রিজার্ভেশন ও ডেলিভারি" subtitle="অর্ডারের জন্য স্টক হোল্ড এবং রাইডার/COD ডেলিভারি।" />
      <Segmented value={tab} onChange={setTab} options={TABS} />
      {tab === "reservations" && <ReservationsTab />}
      {tab === "deliveries" && <DeliveriesTab />}
    </div>
  );
}
