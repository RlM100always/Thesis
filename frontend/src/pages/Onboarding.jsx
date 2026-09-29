import { useState } from "react";
import { useAuth } from "../AuthContext";
import { useBusiness } from "../BusinessContext";
import { explain } from "../errors";
import { BUSINESS_TYPES, EXPIRY_HINT, verticalOf } from "../verticals";
import { Button, Card, Field, Notice } from "../ui/kit";
import { AuthLayout } from "./Login";

// The API wants a Latin, unique slug; the owner should never have to think about it.
const makeSlug = () => `shop-${Math.random().toString(36).slice(2, 8)}${Date.now().toString(36).slice(-3)}`;

// Shown to a signed-in person who has no business yet: right after signing up.
export default function Onboarding() {
  const { create } = useBusiness();
  const { user, signOut } = useAuth();
  const [form, setForm] = useState({ name: "", sector: "grocery", default_branch_name: "প্রধান শাখা" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await create({ ...form, name: form.name.trim(), slug: makeSlug() });
      window.location.hash = "#/";
    } catch (err) {
      setError(explain(err, {
        409: "কোনো কারণে ব্যবসাটি তৈরি হয়নি। আবার চেষ্টা করুন।",
        422: "ব্যবসার নাম কমপক্ষে ২ অক্ষরের দিন।",
      }));
      setBusy(false);
    }
  }

  return (
    <AuthLayout
      title={`স্বাগতম${user ? `, ${user.display_name.split(" ")[0]}` : ""}!`}
      subtitle="আপনার ব্যবসার তথ্য দিন। পরে সবকিছু বদলানো যাবে।"
    >
      <Card>
        <form className="ui-form" onSubmit={submit}>
          <Field label="ব্যবসার নাম" required hint="যেমন: রহমান স্টোর, করিম ফার্মেসি, নূর ফ্যাশন">
            <input value={form.name} onChange={set("name")} minLength={2} maxLength={160} autoComplete="organization" autoFocus />
          </Field>
          <Field label="কী ধরনের ব্যবসা?" required hint={verticalOf(form.sector).expiry ? EXPIRY_HINT.on : EXPIRY_HINT.off}>
            <select value={form.sector} onChange={set("sector")}>
              {BUSINESS_TYPES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </Field>
          <Field label="প্রথম শাখার নাম" required hint="একটাই দোকান হলে ‘প্রধান শাখা’ই থাক">
            <input value={form.default_branch_name} onChange={set("default_branch_name")} minLength={2} maxLength={120} />
          </Field>
          {error && <Notice tone="danger">{error}</Notice>}
          <Button type="submit" block loading={busy}>ব্যবসা তৈরি করুন</Button>
        </form>
      </Card>
      <p className="auth-switch">
        অন্য কারও ব্যবসায় যোগ দিতে এসেছেন? মালিকের পাঠানো লিংকটি খুলুন।
        <button type="button" onClick={signOut}>লগআউট</button>
      </p>
    </AuthLayout>
  );
}
