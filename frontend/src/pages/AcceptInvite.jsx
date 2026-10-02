import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api";
import { explain } from "../errors";
import { Button, Card, Field, Notice } from "../ui/kit";
import { AuthLayout } from "./Login";

// Opened from the link an owner sends a new team member (#/accept-invite?token=…)
// or from a self-service "forgot password" email (#/reset-password?token=…).
// Both land on the same token-for-a-new-password exchange on the backend, so
// one page serves both -- only the copy differs.
export default function AcceptInvite({ mode = "invite" }) {
  const isReset = mode === "reset";
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const mismatch = confirm.length > 0 && confirm !== password;

  async function submit(e) {
    e.preventDefault();
    if (password !== confirm) return;
    setBusy(true);
    setError("");
    try {
      await api.setPassword(token, password);
      window.location.hash = "#/";
      window.location.reload();
    } catch (err) {
      setError(explain(err, {
        400: "এই লিংকটি কাজ করছে না — হয় মেয়াদ শেষ, নয়তো আগেই ব্যবহার হয়েছে। মালিকের কাছ থেকে নতুন লিংক চেয়ে নিন।",
        422: "পাসওয়ার্ড কমপক্ষে ৮ অক্ষরের হতে হবে।",
      }));
      setBusy(false);
    }
  }

  return (
    <AuthLayout
      title={isReset ? "নতুন পাসওয়ার্ড দিন" : "পাসওয়ার্ড তৈরি করুন"}
      subtitle={isReset ? "আপনার অ্যাকাউন্টের জন্য একটি নতুন পাসওয়ার্ড দিন।" : "আপনাকে ব্যবসায় যোগ করা হয়েছে। নিজের পাসওয়ার্ড দিয়ে শুরু করুন।"}
    >
      {!token ? (
        <Notice tone="danger" title="লিংকটি অসম্পূর্ণ">
          মালিকের পাঠানো পুরো লিংকটি খুলুন, অথবা নতুন লিংক চেয়ে নিন।
        </Notice>
      ) : (
        <Card>
          <form className="ui-form" onSubmit={submit}>
            <Field label="নতুন পাসওয়ার্ড" required hint="কমপক্ষে ৮ অক্ষর">
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                     minLength={8} autoComplete="new-password" />
            </Field>
            <Field label="পাসওয়ার্ড আবার লিখুন" required error={mismatch ? "দুই জায়গায় পাসওয়ার্ড মিলছে না।" : undefined}>
              <input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)}
                     minLength={8} autoComplete="new-password" />
            </Field>
            {error && <Notice tone="danger">{error}</Notice>}
            <Button type="submit" block loading={busy} disabled={mismatch}>শুরু করুন</Button>
          </form>
        </Card>
      )}
    </AuthLayout>
  );
}
