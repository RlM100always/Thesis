import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { useAuth } from "../AuthContext";
import { useBusiness } from "../BusinessContext";
import { useConfirm } from "../components/ConfirmDialog";
import { explain } from "../errors";
import { ROLE_DESCRIPTIONS, ROLE_LABELS, usePermissions } from "../PermissionContext";
import DataTable from "../ui/DataTable";
import Icon from "../ui/Icon";
import { Avatar, Badge, Button, Card, CopyField, EmptyState, Field, Notice, PageHeader } from "../ui/kit";
import { useToast } from "../ui/Toast";

const ROLE_ORDER = ["manager", "cashier", "accountant", "stock_keeper", "rider", "viewer", "evaluator", "owner"];
const EMPTY = { display_name: "", email: "", role: "cashier" };
const CHAT_POLL_MS = 5000;

function TeamChatCard({ orgId, currentUserId }) {
  const toast = useToast();
  const [messages, setMessages] = useState(null);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const listRef = useRef(null);
  const lastIdRef = useRef(null);

  const poll = useCallback(async () => {
    if (!orgId) return;
    try {
      const fresh = await api.teamMessages(orgId, lastIdRef.current);
      if (fresh.length === 0) return;
      setMessages((prev) => [...(prev || []), ...fresh]);
      lastIdRef.current = fresh[fresh.length - 1].id;
    } catch {
      // silent -- a missed poll tick isn't worth interrupting the page with
    }
  }, [orgId]);

  useEffect(() => {
    if (!orgId) return;
    let cancelled = false;
    (async () => {
      try {
        const initial = await api.teamMessages(orgId);
        if (cancelled) return;
        setMessages(initial);
        if (initial.length) lastIdRef.current = initial[initial.length - 1].id;
      } catch (e) {
        if (!cancelled) { toast.error(explain(e)); setMessages([]); }
      }
    })();
    const timer = setInterval(poll, CHAT_POLL_MS);
    return () => { cancelled = true; clearInterval(timer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orgId]);

  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [messages]);

  async function send(e) {
    e.preventDefault();
    const body = draft.trim();
    if (!body) return;
    setSending(true);
    try {
      const sent = await api.postTeamMessage(orgId, body);
      setMessages((prev) => [...(prev || []), sent]);
      lastIdRef.current = sent.id;
      setDraft("");
    } catch (err) {
      toast.error(explain(err));
    } finally {
      setSending(false);
    }
  }

  return (
    <Card title="টিম চ্যাট" subtitle="এই ব্যবসার সব সক্রিয় কর্মী একসাথে এখানে কথা বলতে পারবেন।">
      <div ref={listRef} className="team-chat-list" role="log" aria-live="polite">
        {messages === null && <p className="hint">লোড হচ্ছে...</p>}
        {messages !== null && messages.length === 0 && (
          <EmptyState icon="mail" title="এখনো কোনো বার্তা নেই" hint="টিমকে প্রথম বার্তা পাঠান।" />
        )}
        {messages?.map((m) => (
          <div key={m.id} className={`team-chat-bubble ${m.user_id === currentUserId ? "me" : ""}`}>
            <div className="team-chat-meta">
              <strong>{m.author_name}</strong>
              <small>{new Date(m.created_at).toLocaleString("bn-BD", { hour: "2-digit", minute: "2-digit", day: "numeric", month: "short" })}</small>
            </div>
            <div className="team-chat-body">{m.body}</div>
          </div>
        ))}
      </div>
      <form className="team-chat-input" onSubmit={send}>
        <input
          value={draft} onChange={(e) => setDraft(e.target.value)}
          placeholder="বার্তা লিখুন..." maxLength={2000} autoComplete="off"
        />
        <Button type="submit" icon="chevronRight" loading={sending} disabled={!draft.trim()}>পাঠান</Button>
      </form>
    </Card>
  );
}

// The link a new person opens. Built from the current page so it works on any host.
function inviteLink(token) {
  return `${window.location.origin}${window.location.pathname}#/accept-invite?token=${encodeURIComponent(token)}`;
}

export default function StaffPage() {
  const { active } = useBusiness();
  const { user } = useAuth();
  const { can } = usePermissions();
  const toast = useToast();
  const confirm = useConfirm();
  const orgId = active?.id;
  const canManage = can("staff:manage");

  const [staff, setStaff] = useState(null);
  const [loadError, setLoadError] = useState("");
  const [form, setForm] = useState(EMPTY);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState("");
  const [link, setLink] = useState(null); // { name, url, expires }

  const load = useCallback(async () => {
    if (!orgId) return;
    try {
      setStaff(await api.staff(orgId));
      setLoadError("");
    } catch (e) {
      setLoadError(explain(e));
    }
  }, [orgId]);

  useEffect(() => { load(); }, [load]);

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  async function invite(e) {
    e.preventDefault();
    setBusy(true);
    setFormError("");
    try {
      const result = await api.inviteStaff(orgId, form);
      setForm(EMPTY);
      if (result.setup_token) {
        setLink({ name: result.display_name, url: inviteLink(result.setup_token), expires: result.setup_expires_at });
      } else {
        toast.success(`${result.display_name} এখন এই ব্যবসার সদস্য। তাঁর আগের পাসওয়ার্ডই কাজ করবে।`);
      }
      await load();
    } catch (err) {
      setFormError(explain(err, {
        403: "শুধু মালিক কর্মী যোগ করতে পারেন।",
        409: "এই ইমেইল আগেই এই ব্যবসায় যোগ করা আছে।",
        422: "নাম ও সঠিক ইমেইল দিন।",
      }));
    } finally {
      setBusy(false);
    }
  }

  async function changeRole(person, role) {
    if (role === person.role) return;
    if (!(await confirm(`${person.display_name}-এর ভূমিকা "${ROLE_LABELS[role]}" করা হবে। এতে তিনি কী দেখতে ও করতে পারেন তা বদলে যাবে। নিশ্চিত?`))) {
      await load(); // put the dropdown back
      return;
    }
    try {
      await api.updateStaff(orgId, person.membership_id, { role });
      toast.success("ভূমিকা বদলানো হয়েছে।");
    } catch (err) {
      toast.error(explain(err, { 409: "ব্যবসায় অন্তত একজন সক্রিয় মালিক থাকতেই হবে।" }));
    }
    await load();
  }

  async function toggleActive(person) {
    const next = !person.active;
    const question = next
      ? `${person.display_name}-কে আবার এই ব্যবসায় ঢুকতে দেওয়া হবে। নিশ্চিত?`
      : `${person.display_name} আর এই ব্যবসার হিসাব দেখতে বা কাজ করতে পারবেন না। পরে আবার চালু করা যাবে। নিশ্চিত?`;
    if (!(await confirm(question))) return;
    try {
      await api.updateStaff(orgId, person.membership_id, { active: next });
      toast.success(next ? "আবার চালু করা হয়েছে।" : "প্রবেশ বন্ধ করা হয়েছে।");
    } catch (err) {
      toast.error(explain(err, { 409: "ব্যবসায় অন্তত একজন সক্রিয় মালিক থাকতেই হবে।" }));
    }
    await load();
  }

  async function newLink(person) {
    try {
      const result = await api.staffSetupLink(orgId, person.membership_id);
      setLink({ name: person.display_name, url: inviteLink(result.setup_token), expires: result.setup_expires_at });
    } catch (err) {
      toast.error(explain(err, {
        409: "এই ব্যক্তি অন্য ব্যবসাতেও আছেন, তাই তাঁর পাসওয়ার্ড তাঁকেই বদলাতে হবে। নিজের অ্যাকাউন্টের জন্য 'আমার অ্যাকাউন্ট' ব্যবহার করুন।",
      }));
    }
  }

  const columns = [
    {
      key: "person", label: "নাম", primary: true,
      render: (p) => (
        <div className="ui-person">
          <Avatar name={p.display_name} />
          <div><strong>{p.display_name}{user?.id === p.user_id ? " (আপনি)" : ""}</strong><small>{p.email}</small></div>
        </div>
      ),
    },
    {
      key: "role", label: "ভূমিকা",
      render: (p) => canManage ? (
        <select value={p.role} onChange={(e) => changeRole(p, e.target.value)} aria-label={`${p.display_name}-এর ভূমিকা`}>
          {ROLE_ORDER.map((r) => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
        </select>
      ) : <Badge tone="info">{ROLE_LABELS[p.role] || p.role}</Badge>,
    },
    {
      key: "status", label: "অবস্থা",
      render: (p) => !p.active
        ? <Badge tone="neutral" icon="lock">বন্ধ</Badge>
        : p.pending_setup
          ? <Badge tone="warn" icon="clock">পাসওয়ার্ডের অপেক্ষায়</Badge>
          : <Badge tone="success" icon="check">সক্রিয়</Badge>,
    },
  ];
  if (canManage) {
    columns.push({
      key: "actions", label: "কাজ", align: "right",
      render: (p) => (
        <div className="row" style={{ justifyContent: "flex-end", flexWrap: "nowrap" }}>
          {user?.id !== p.user_id && (
            <Button size="sm" variant="ghost" icon="link" onClick={() => newLink(p)}>লিংক</Button>
          )}
          <Button size="sm" variant={p.active ? "danger" : "secondary"} onClick={() => toggleActive(p)}>
            {p.active ? "বন্ধ করুন" : "চালু করুন"}
          </Button>
        </div>
      ),
    });
  }

  return (
    <div className="page stack">
      <PageHeader
        title="কর্মী ও ভূমিকা"
        subtitle="কে কী দেখতে ও করতে পারবেন তা ঠিক করুন। ক্যাশিয়ার লাভ-খরচ দেখেন না, শুধু বিক্রি করেন।"
      />

      {loadError && <Notice tone="danger" action={<Button size="sm" variant="secondary" onClick={load}>আবার চেষ্টা</Button>}>{loadError}</Notice>}

      {link && (
        <Card className="setup-card" title={`${link.name}-এর জন্য পাসওয়ার্ড লিংক`}
              subtitle="এই লিংক শুধু এখনই দেখানো হচ্ছে। WhatsApp বা SMS-এ পাঠিয়ে দিন।"
              actions={<Button size="sm" variant="ghost" icon="x" onClick={() => setLink(null)}>বন্ধ করুন</Button>}>
          <CopyField value={link.url} label="পাসওয়ার্ড লিংক" />
          <p className="muted" style={{ margin: "10px 0 0", fontSize: 13 }}>
            লিংকটি ৭ দিন পর্যন্ত কাজ করবে এবং একবার ব্যবহারের পর বন্ধ হয়ে যাবে।
          </p>
        </Card>
      )}

      {canManage && (
        <Card title="নতুন কর্মী যোগ করুন" subtitle="যোগ করলে তাঁর জন্য একটি লিংক তৈরি হবে, সেই লিংকে তিনি নিজের পাসওয়ার্ড দেবেন।">
          <form className="ui-form ui-form--2" onSubmit={invite}>
            <Field label="নাম" required>
              <input value={form.display_name} onChange={set("display_name")} minLength={2} autoComplete="off" />
            </Field>
            <Field label="ইমেইল" required>
              <input type="email" value={form.email} onChange={set("email")} autoComplete="off" inputMode="email" />
            </Field>
            <div className="ui-span">
              <Field label="ভূমিকা" required hint={ROLE_DESCRIPTIONS[form.role]}>
                <select value={form.role} onChange={set("role")}>
                  {ROLE_ORDER.map((r) => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
                </select>
              </Field>
            </div>
            {formError && <div className="ui-span"><Notice tone="danger">{formError}</Notice></div>}
            <div className="ui-span"><Button type="submit" icon="plus" loading={busy}>কর্মী যোগ করুন</Button></div>
          </form>
        </Card>
      )}

      {active?.feature_flags?.team_chat !== false && <TeamChatCard orgId={orgId} currentUserId={user?.id} />}

      <Card pad={false} title={`সদস্য${staff ? ` (${staff.length})` : ""}`}>
        <DataTable
          columns={columns}
          rows={staff || []}
          rowKey="membership_id"
          loading={staff === null && !loadError}
          caption="ব্যবসার সদস্যদের তালিকা"
          empty={<EmptyState icon="users" title="এখনো কেউ নেই" hint="প্রথম কর্মী যোগ করুন।" />}
        />
      </Card>

      <Card title="কোন ভূমিকা কী পারে">
        <ul className="role-note">
          {ROLE_ORDER.map((r) => (
            <li key={r}><Icon name="check" size={14} /> <strong>{ROLE_LABELS[r]}:</strong> {ROLE_DESCRIPTIONS[r]}</li>
          ))}
        </ul>
      </Card>
      {confirm.dialog}
    </div>
  );
}
