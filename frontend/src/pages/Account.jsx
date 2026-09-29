import { useState } from "react";
import { api } from "../api";
import { useAuth } from "../AuthContext";
import { getTokens } from "../auth";
import { explain } from "../errors";
import { ROLE_LABELS, usePermissions } from "../PermissionContext";
import { Avatar, Badge, Button, Card, Field, Notice, PageHeader } from "../ui/kit";
import { useToast } from "../ui/Toast";

export default function AccountPage() {
  const { user } = useAuth();
  const { role } = usePermissions();
  const toast = useToast();
  const [form, setForm] = useState({ current: "", next: "", confirm: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });
  const mismatch = form.confirm.length > 0 && form.confirm !== form.next;
  const signedIn = Boolean(getTokens());

  async function submit(e) {
    e.preventDefault();
    if (mismatch) return;
    setBusy(true);
    setError("");
    try {
      await api.changePassword(form.current, form.next);
      setForm({ current: "", next: "", confirm: "" });
      toast.success("পাসওয়ার্ড বদলানো হয়েছে। অন্য ডিভাইস থেকে লগআউট হয়ে গেছে।");
    } catch (err) {
      // 400 = wrong current password (never 401: that would sign the person out).
      setError(explain(err, {
        400: "বর্তমান পাসওয়ার্ড ঠিক নয়।",
        422: "নতুন পাসওয়ার্ড কমপক্ষে ৮ অক্ষরের হতে হবে।",
      }));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page stack">
      <PageHeader title="আমার অ্যাকাউন্ট" subtitle="আপনার পরিচয় ও পাসওয়ার্ড।" />

      <Card>
        <div className="ui-person">
          <Avatar name={user?.display_name || "মালিক"} size={48} />
          <div>
            <strong>{user?.display_name || "লোকাল ডেমো মালিক"}</strong>
            <small>{user?.email || "লগইন ছাড়া ব্যবহার করছেন"}</small>
          </div>
          {role && <Badge tone="info">{ROLE_LABELS[role] || role}</Badge>}
        </div>
      </Card>

      {signedIn ? (
        <Card title="পাসওয়ার্ড বদলান" subtitle="বদলালে অন্য সব ডিভাইস থেকে আপনি লগআউট হয়ে যাবেন।">
          <form className="ui-form" onSubmit={submit} style={{ maxWidth: 440 }}>
            <Field label="বর্তমান পাসওয়ার্ড" required>
              <input type="password" value={form.current} onChange={set("current")} autoComplete="current-password" />
            </Field>
            <Field label="নতুন পাসওয়ার্ড" required hint="কমপক্ষে ৮ অক্ষর">
              <input type="password" value={form.next} onChange={set("next")} minLength={8} autoComplete="new-password" />
            </Field>
            <Field label="নতুন পাসওয়ার্ড আবার লিখুন" required error={mismatch ? "দুই জায়গায় পাসওয়ার্ড মিলছে না।" : undefined}>
              <input type="password" value={form.confirm} onChange={set("confirm")} minLength={8} autoComplete="new-password" />
            </Field>
            {error && <Notice tone="danger">{error}</Notice>}
            <div><Button type="submit" loading={busy} disabled={mismatch}>পাসওয়ার্ড বদলান</Button></div>
          </form>
        </Card>
      ) : (
        <Notice tone="info" title="আপনি লগইন ছাড়া লোকাল ডেমো মালিক হিসেবে আছেন">
          নিজের অ্যাকাউন্ট খুলে লগইন করলে এখানে পাসওয়ার্ড বদলাতে পারবেন।
        </Notice>
      )}
    </div>
  );
}
