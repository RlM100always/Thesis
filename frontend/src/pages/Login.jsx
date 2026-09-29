import { useState } from "react";
import { useAuth } from "../AuthContext";
import { explain } from "../errors";
import Icon from "../ui/Icon";
import { Button, Card, Field, Notice } from "../ui/kit";

const POINTS = [
  ["box", "কোন পণ্য কতটা কিনতে হবে, আগে থেকেই জানুন"],
  ["card", "বাকি, খরচ আর লাভের হিসাব এক জায়গায়"],
  ["users", "কোন কাস্টমার আর আসছেন না, সময়মতো বুঝুন"],
];

// Shared by the login screen and the invite screen: brand panel on desktop, a
// compact brand line on a phone.
export function AuthLayout({ title, subtitle, children }) {
  return (
    <div className="auth-shell">
      <section className="auth-brand" aria-hidden="true">
        <h1>B-SMART</h1>
        <p>ছোট ও মাঝারি ব্যবসার জন্য সিদ্ধান্তের সহকারী — আপনার নিজের হিসাব থেকে, আপনার ভাষায়।</p>
        <ul className="auth-points">
          {POINTS.map(([icon, text]) => (
            <li key={icon}><Icon name={icon} size={20} /><span>{text}</span></li>
          ))}
        </ul>
      </section>
      <main className="auth-panel">
        <div className="auth-card">
          <div className="auth-mobile-brand"><strong>B-SMART</strong></div>
          <div>
            <h2>{title}</h2>
            {subtitle && <p className="muted" style={{ margin: "6px 0 0" }}>{subtitle}</p>}
          </div>
          {children}
        </div>
      </main>
    </div>
  );
}

export default function Login() {
  const { signIn, signUp } = useAuth();
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ email: "", password: "", display_name: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });
  const isLogin = mode === "login";

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (isLogin) await signIn(form.email, form.password);
      else await signUp(form);
    } catch (err) {
      setError(explain(err, {
        401: "ইমেইল বা পাসওয়ার্ড ভুল হয়েছে।",
        403: "নতুন অ্যাকাউন্ট খোলা এখন বন্ধ আছে।",
        409: "এই ইমেইল দিয়ে আগেই অ্যাকাউন্ট খোলা আছে। লগইন করুন।",
        422: "সঠিক ইমেইল দিন এবং পাসওয়ার্ড কমপক্ষে ৮ অক্ষরের রাখুন।",
        429: "অনেকবার ভুল চেষ্টা হয়েছে। কিছুক্ষণ পরে আবার চেষ্টা করুন।",
      }));
      setBusy(false);
    }
  }

  return (
    <AuthLayout
      title={isLogin ? "আবার স্বাগতম" : "নতুন অ্যাকাউন্ট খুলুন"}
      subtitle={isLogin ? "আপনার ব্যবসার হিসাবে ঢুকতে লগইন করুন।" : "কয়েক সেকেন্ডেই শুরু করতে পারবেন।"}
    >
      <Card>
        <form className="ui-form" onSubmit={submit} noValidate={false}>
          {!isLogin && (
            <Field label="আপনার নাম" required>
              <input value={form.display_name} onChange={set("display_name")} minLength={2} autoComplete="name" />
            </Field>
          )}
          <Field label="ইমেইল" required>
            <input type="email" value={form.email} onChange={set("email")} autoComplete="email" inputMode="email" />
          </Field>
          <Field label="পাসওয়ার্ড" required hint={isLogin ? undefined : "কমপক্ষে ৮ অক্ষর"}>
            <input type="password" value={form.password} onChange={set("password")}
                   minLength={isLogin ? 1 : 8} autoComplete={isLogin ? "current-password" : "new-password"} />
          </Field>
          {error && <Notice tone="danger">{error}</Notice>}
          <Button type="submit" block loading={busy}>{isLogin ? "লগইন" : "অ্যাকাউন্ট খুলুন"}</Button>
        </form>
      </Card>
      <p className="auth-switch">
        {isLogin ? "নতুন এসেছেন?" : "আগেই অ্যাকাউন্ট আছে?"}
        <button type="button" onClick={() => { setMode(isLogin ? "register" : "login"); setError(""); }}>
          {isLogin ? "অ্যাকাউন্ট খুলুন" : "লগইন করুন"}
        </button>
      </p>
    </AuthLayout>
  );
}
