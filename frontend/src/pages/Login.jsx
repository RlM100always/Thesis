import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../AuthContext";
import { explain } from "../errors";
import { useUi } from "../UiContext";
import Icon from "../ui/Icon";
import { Button, Card, Field, Notice } from "../ui/kit";

const POINTS = [
  ["cart", "বিক্রি, মজুত ও লেনদেনের হিসাব একই জায়গায়"],
  ["userCheck", "মালিক, ক্যাশিয়ার ও কর্মীদের দায়িত্ব অনুযায়ী আলাদা কাজের পাতা"],
  ["zap", "সংখ্যার সঙ্গে কারণ, করণীয় ও ফলাফলের তথ্য"],
];

// Shared by the login screen and the invite screen: brand panel on desktop, a
// compact brand line on a phone.
export function AuthLayout({ title, subtitle, children }) {
  const { theme, toggleTheme } = useUi();
  return (
    <div className="auth-shell">
      {/* Theme toggle — top right corner */}
      <button
        type="button"
        onClick={toggleTheme}
        aria-label="থিম পরিবর্তন করুন"
        style={{
          position: "fixed", top: 16, right: 16, zIndex: 200,
          background: "var(--surface)", border: "1px solid var(--border)",
          borderRadius: 10, padding: "8px 12px", cursor: "pointer",
          fontSize: 18, lineHeight: 1, boxShadow: "var(--shadow-2)",
          color: "var(--text)",
        }}
        title={theme === "dark" ? "লাইট মোড চালু করুন" : "ডার্ক মোড চালু করুন"}
      >
        {theme === "dark" ? "☀️" : "🌙"}
      </button>

      <section className="auth-brand" aria-hidden="true">
        <img className="auth-logo" src="/bsmart-mark.svg" alt="" />
        <span className="auth-brand-kicker">B-SMART · ব্যবসা পরিচালনার সফটওয়্যার</span>
        <h1>আপনার ব্যবসার প্রয়োজনীয় তথ্য,<br />এক জায়গায়</h1>
        <p>বাংলাদেশের ছোট ও মাঝারি ব্যবসার বিক্রি, মজুত, হিসাব ও দৈনন্দিন কাজ পরিচালনায় সহায়ক একটি সফটওয়্যার।</p>
        <ul className="auth-points">
          {POINTS.map(([icon, text]) => (
            <li key={icon}><Icon name={icon} size={20} /><span>{text}</span></li>
          ))}
        </ul>
      </section>
      <main className="auth-panel">
        <div className="auth-card">
          <div className="auth-mobile-brand"><img src="/bsmart-mark.svg" alt="" /><strong>B-SMART</strong><span>ব্যবসা পরিচালনা</span></div>
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

function MfaStep({ mfaToken, onBack }) {
  const { completeMfa } = useAuth();
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await completeMfa(mfaToken, code.trim());
    } catch (err) {
      setError(explain(err, { 401: "কোড ভুল অথবা মেয়াদ শেষ।", 429: "অনেকবার ভুল চেষ্টা হয়েছে। কিছুক্ষণ পরে আবার চেষ্টা করুন।" }));
      setBusy(false);
    }
  }

  return (
    <AuthLayout title="যাচাইকরণ কোড দিন" subtitle="আপনার অথেনটিকেটর অ্যাপের ৬ সংখ্যার কোড অথবা সংরক্ষিত পুনরুদ্ধার কোড লিখুন।">
      <Card>
        <form className="ui-form" onSubmit={submit}>
          <Field label="কোড" required>
            <input value={code} onChange={(e) => setCode(e.target.value)} autoComplete="one-time-code" inputMode="numeric" autoFocus />
          </Field>
          {error && <Notice tone="danger">{error}</Notice>}
          <Button type="submit" block loading={busy}>যাচাই করুন</Button>
        </form>
      </Card>
      <p className="auth-switch"><button type="button" onClick={onBack}>← ফিরে যান</button></p>
    </AuthLayout>
  );
}

function ForgotPasswordStep({ onBack }) {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    try { await api.forgotPassword(email); } catch { /* always show the same generic message */ }
    setSent(true);
    setBusy(false);
  }

  return (
    <AuthLayout title="পাসওয়ার্ড ভুলে গেছেন?" subtitle="ইমেইল দিন। অ্যাকাউন্ট থাকলে একটি রিসেট লিংক পাঠানো হবে।">
      <Card>
        {sent ? (
          <Notice tone="success">এই ইমেইলে অ্যাকাউন্ট থাকলে একটি রিসেট লিংক পাঠানো হয়েছে।</Notice>
        ) : (
          <form className="ui-form" onSubmit={submit}>
            <Field label="ইমেইল" required><input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" autoFocus /></Field>
            <Button type="submit" block loading={busy}>রিসেট লিংক পাঠান</Button>
          </form>
        )}
      </Card>
      <p className="auth-switch"><button type="button" onClick={onBack}>← লগইনে ফিরে যান</button></p>
    </AuthLayout>
  );
}

export default function Login({ initialMode = "login" }) {
  const { signIn, signUp } = useAuth();
  const [mode, setMode] = useState(initialMode);
  const [form, setForm] = useState({ email: "", password: "", display_name: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [mfaChallenge, setMfaChallenge] = useState(null);
  const [forgotPassword, setForgotPassword] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });
  const isLogin = mode === "login";

  useEffect(() => { setMode(initialMode); setError(""); setMfaChallenge(null); setForgotPassword(false); }, [initialMode]);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (isLogin) {
        const result = await signIn(form.email, form.password);
        if (result?.mfa_required) { setMfaChallenge(result.mfa_token); setBusy(false); return; }
      } else {
        await signUp(form);
      }
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

  if (mfaChallenge) return <MfaStep mfaToken={mfaChallenge} onBack={() => setMfaChallenge(null)} />;
  if (forgotPassword) return <ForgotPasswordStep onBack={() => setForgotPassword(false)} />;

  return (
    <AuthLayout
      title={isLogin ? "ব্যবসার অ্যাকাউন্টে লগইন করুন" : "নতুন ব্যবসার অ্যাকাউন্ট খুলুন"}
      subtitle={isLogin ? "লগইন করলে আপনার অনুমতি অনুযায়ী কাজের পাতা দেখতে পাবেন।" : "নিজের ব্যবসার তথ্য যোগ করে ধাপে ধাপে শুরু করুন।"}
    >
      <Card>
        <form className="ui-form" onSubmit={submit} noValidate={false}>
          {!isLogin && (
            <>
              <div className="auth-owner-note"><Icon name="info" size={17} /><span>এখান থেকে ব্যবসার মালিক নতুন অ্যাকাউন্ট খুলতে পারবেন। কর্মী হলে মালিকের পাঠানো আমন্ত্রণ লিংক ব্যবহার করুন।</span></div>
              <Field label="আপনার নাম" required>
                <input value={form.display_name} onChange={set("display_name")} minLength={2} autoComplete="name" />
              </Field>
            </>
          )}
          <Field label="ইমেইল" required>
            <input type="email" value={form.email} onChange={set("email")} autoComplete="email" inputMode="email" />
          </Field>
          <Field label="পাসওয়ার্ড" required hint={isLogin ? undefined : "কমপক্ষে ৮ অক্ষর"}>
            <span className="auth-password">
              <input type={showPassword ? "text" : "password"} value={form.password} onChange={set("password")}
                     minLength={isLogin ? 1 : 8} autoComplete={isLogin ? "current-password" : "new-password"} />
              <button type="button" className="auth-password-toggle" onClick={() => setShowPassword((value) => !value)} aria-pressed={showPassword}>
                {showPassword ? "লুকান" : "দেখুন"}
              </button>
            </span>
          </Field>
          {error && <Notice tone="danger">{error}</Notice>}
          <Button type="submit" block loading={busy}>{isLogin ? "লগইন" : "অ্যাকাউন্ট খুলুন"}</Button>
          {isLogin && <button type="button" className="auth-forgot" onClick={() => setForgotPassword(true)}>পাসওয়ার্ড ভুলে গেছেন?</button>}
        </form>
      </Card>
      <p className="auth-switch">
        {isLogin ? "নতুন এসেছেন?" : "আগেই অ্যাকাউন্ট আছে?"}
        <button type="button" onClick={() => { setMode(isLogin ? "register" : "login"); setError(""); }}>
          {isLogin ? "অ্যাকাউন্ট খুলুন" : "লগইন করুন"}
        </button>
      </p>
      <div className="auth-public-links"><Link to="/">← হোমপেজ</Link><Link to="/guidelines">ব্যবহারবিধি</Link><Link to="/privacy">গোপনীয়তা</Link></div>
    </AuthLayout>
  );
}
