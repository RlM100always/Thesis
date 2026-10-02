import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { useAuth } from "../AuthContext";
import { getTokens } from "../auth";
import { explain } from "../errors";
import { ROLE_LABELS, usePermissions } from "../PermissionContext";
import { Avatar, Badge, Button, Card, Field, Notice, PageHeader } from "../ui/kit";
import { useToast } from "../ui/Toast";

// Resize+compress client-side before it ever reaches the network — the backend
// caps the stored data: URL at 400KB (ProfileUpdateIn in auth_routes.py), and
// shrinking a multi-MB phone photo down to a small square avoids that limit
// entirely instead of just rejecting large files.
const AVATAR_PX = 256;

function resizeImageFile(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("ফাইলটি পড়া যায়নি।"));
    reader.onload = () => {
      const img = new Image();
      img.onerror = () => reject(new Error("এটি একটি বৈধ ছবি ফাইল নয়।"));
      img.onload = () => {
        const side = Math.min(img.width, img.height);
        const sx = (img.width - side) / 2;
        const sy = (img.height - side) / 2;
        const canvas = document.createElement("canvas");
        canvas.width = AVATAR_PX;
        canvas.height = AVATAR_PX;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(img, sx, sy, side, side, 0, 0, AVATAR_PX, AVATAR_PX);
        resolve(canvas.toDataURL("image/jpeg", 0.85));
      };
      img.src = reader.result;
    };
    reader.readAsDataURL(file);
  });
}

function ProfilePhotoField({ user, updateUser, toast }) {
  const fileRef = useRef(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function onPick(e) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      setError("শুধু ছবি ফাইল (JPG, PNG) দেওয়া যাবে।");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const dataUrl = await resizeImageFile(file);
      const updated = await api.updateProfile({ avatar_data_url: dataUrl });
      updateUser(updated);
      toast.success("প্রোফাইল ছবি বদলানো হয়েছে।");
    } catch (err) {
      setError(explain(err, { 422: "ছবিটি গ্রহণযোগ্য নয়।" }));
    } finally {
      setBusy(false);
    }
  }

  async function onRemove() {
    setBusy(true);
    setError("");
    try {
      const updated = await api.updateProfile({ avatar_data_url: "" });
      updateUser(updated);
      toast.success("প্রোফাইল ছবি সরানো হয়েছে।");
    } catch (err) {
      setError(explain(err, {}));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="ui-person" style={{ alignItems: "center" }}>
      <Avatar name={user?.display_name || "মালিক"} src={user?.avatar_data_url} size={64} />
      <div className="stack" style={{ gap: 6 }}>
        <div style={{ display: "flex", gap: 8 }}>
          <Button type="button" variant="secondary" loading={busy} onClick={() => fileRef.current?.click()}>
            ছবি আপলোড করুন
          </Button>
          {user?.avatar_data_url && (
            <Button type="button" variant="ghost" disabled={busy} onClick={onRemove}>সরিয়ে দিন</Button>
          )}
        </div>
        <small style={{ color: "var(--text-muted)" }}>JPG বা PNG, বর্গাকার করে কাটা হবে।</small>
        {error && <Notice tone="danger">{error}</Notice>}
        <input ref={fileRef} type="file" accept="image/*" hidden onChange={onPick} />
      </div>
    </div>
  );
}

function ProfileDetailsForm({ user, updateUser, toast }) {
  const [form, setForm] = useState({ display_name: user?.display_name || "", phone: user?.phone || "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const dirty = form.display_name !== (user?.display_name || "") || form.phone !== (user?.phone || "");

  async function submit(e) {
    e.preventDefault();
    if (!form.display_name.trim()) {
      setError("নাম খালি রাখা যাবে না।");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const updated = await api.updateProfile({
        display_name: form.display_name.trim(), phone: form.phone.trim(),
      });
      updateUser(updated);
      toast.success("তথ্য আপডেট হয়েছে।");
    } catch (err) {
      setError(explain(err, { 422: "দেওয়া তথ্য সঠিক নয়।" }));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="ui-form" onSubmit={submit} style={{ maxWidth: 440 }}>
      <Field label="নাম" required>
        <input value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} />
      </Field>
      <Field label="ফোন নম্বর" hint="ঐচ্ছিক">
        <input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder="01XXXXXXXXX" />
      </Field>
      {error && <Notice tone="danger">{error}</Notice>}
      <div><Button type="submit" loading={busy} disabled={!dirty}>তথ্য সংরক্ষণ করুন</Button></div>
    </form>
  );
}

// ── দুই-ধাপের নিরাপত্তা (TOTP) ─────────────────────────────────────
function MfaSection({ user, updateUser, toast }) {
  const [step, setStep] = useState("idle"); // idle | enrolling | recovery-codes
  const [enroll, setEnroll] = useState(null); // { secret, otpauth_uri }
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [recoveryCodes, setRecoveryCodes] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function startEnroll() {
    setBusy(true);
    setError("");
    try {
      setEnroll(await api.setupMfa());
      setStep("enrolling");
    } catch (err) {
      setError(explain(err, {}));
    } finally {
      setBusy(false);
    }
  }

  async function confirmEnroll(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const { recovery_codes } = await api.enableMfa(code);
      setRecoveryCodes(recovery_codes);
      setStep("recovery-codes");
      updateUser({ mfa_enabled: true });
      setCode("");
    } catch (err) {
      setError(explain(err, { 400: "কোডটি সঠিক নয় বা মেয়াদ শেষ হয়ে গেছে।" }));
    } finally {
      setBusy(false);
    }
  }

  function finishEnroll() {
    setStep("idle");
    setEnroll(null);
    setRecoveryCodes(null);
    toast.success("দুই-ধাপের নিরাপত্তা চালু হয়েছে।");
  }

  async function disable(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.disableMfa(password);
      updateUser({ mfa_enabled: false });
      setPassword("");
      setStep("idle");
      toast.success("দুই-ধাপের নিরাপত্তা বন্ধ করা হয়েছে।");
    } catch (err) {
      setError(explain(err, { 400: "পাসওয়ার্ড সঠিক নয়।" }));
    } finally {
      setBusy(false);
    }
  }

  if (step === "recovery-codes" && recoveryCodes) {
    return (
      <Card title="রিকভারি কোড সংরক্ষণ করুন">
        <Notice tone="warn" title="এই কোডগুলো আর দেখানো হবে না">
          ফোন হারালে এই কোড দিয়ে লগইন করতে পারবেন। নিরাপদ জায়গায় লিখে রাখুন।
        </Notice>
        <ul className="format-rules" style={{ fontFamily: "monospace", fontSize: 14 }}>
          {recoveryCodes.map((c) => <li key={c}>{c}</li>)}
        </ul>
        <Button type="button" onClick={finishEnroll}>বুঝেছি, সংরক্ষণ করা হয়েছে</Button>
      </Card>
    );
  }

  if (step === "enrolling" && enroll) {
    return (
      <Card title="Authenticator অ্যাপ দিয়ে যুক্ত করুন">
        <p className="hint">
          Google Authenticator বা এই জাতীয় কোনো অ্যাপে নিচের কোডটি ম্যানুয়ালি যোগ করুন,
          তারপর অ্যাপে দেখানো ৬-সংখ্যার কোড লিখুন।
        </p>
        <p style={{ fontFamily: "monospace", fontSize: 15, background: "var(--surface-2)", padding: "10px 14px", borderRadius: 8, wordBreak: "break-all" }}>
          {enroll.secret}
        </p>
        <form className="ui-form" onSubmit={confirmEnroll} style={{ maxWidth: 300 }}>
          <Field label="৬-সংখ্যার কোড" required>
            <input value={code} onChange={(e) => setCode(e.target.value)} maxLength={6} inputMode="numeric" autoFocus />
          </Field>
          {error && <Notice tone="danger">{error}</Notice>}
          <div style={{ display: "flex", gap: 8 }}>
            <Button type="submit" loading={busy} disabled={code.length !== 6}>নিশ্চিত করুন</Button>
            <Button type="button" variant="ghost" onClick={() => { setStep("idle"); setEnroll(null); }}>বাতিল</Button>
          </div>
        </form>
      </Card>
    );
  }

  return (
    <Card title="দুই-ধাপের নিরাপত্তা (2FA)" subtitle="পাসওয়ার্ডের পাশাপাশি ফোনের অ্যাপ থেকে কোড দিয়ে লগইন নিরাপদ করুন।">
      {user?.mfa_enabled ? (
        <>
          <Badge tone="success">চালু আছে</Badge>
          <form className="ui-form" onSubmit={disable} style={{ maxWidth: 360, marginTop: 12 }}>
            <Field label="বন্ধ করতে পাসওয়ার্ড দিন" required>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
            </Field>
            {error && <Notice tone="danger">{error}</Notice>}
            <Button type="submit" variant="secondary" loading={busy} disabled={!password}>২FA বন্ধ করুন</Button>
          </form>
        </>
      ) : (
        <>
          <Badge tone="info">বন্ধ আছে</Badge>
          {error && <Notice tone="danger" style={{ marginTop: 10 }}>{error}</Notice>}
          <div style={{ marginTop: 12 }}>
            <Button type="button" loading={busy} onClick={startEnroll}>২FA চালু করুন</Button>
          </div>
        </>
      )}
    </Card>
  );
}

// ── সক্রিয় ডিভাইস ───────────────────────────────────────────────
function SessionsSection({ toast }) {
  const [sessions, setSessions] = useState(null);
  const [busyId, setBusyId] = useState(null);

  useEffect(() => {
    api.sessions().then(setSessions).catch(() => setSessions([]));
  }, []);

  async function revoke(id) {
    setBusyId(id);
    try {
      await api.revokeSession(id);
      setSessions((prev) => prev.filter((s) => s.id !== id));
      toast.success("ডিভাইস থেকে সাইন-আউট করা হয়েছে।");
    } catch (err) {
      toast.error(explain(err, {}));
    } finally {
      setBusyId(null);
    }
  }

  if (sessions === null) return null;
  if (sessions.length === 0) return null;

  return (
    <Card title="সক্রিয় ডিভাইস" subtitle="যেসব ডিভাইসে আপনি এখনো লগইন আছেন।">
      <div className="stack" style={{ gap: 10 }}>
        {sessions.map((s) => (
          <div key={s.id} className="ui-person" style={{ justifyContent: "space-between" }}>
            <div>
              <strong style={{ fontSize: 13.5 }}>{s.device_label || "অজানা ডিভাইস"}</strong>
              <small>{s.ip_address || ""} · সর্বশেষ সক্রিয় {new Date(s.last_used_at).toLocaleString("bn-BD")}</small>
            </div>
            <Button type="button" variant="ghost" size="sm" loading={busyId === s.id} onClick={() => revoke(s.id)}>
              সাইন-আউট
            </Button>
          </div>
        ))}
      </div>
    </Card>
  );
}

export default function AccountPage() {
  const { user, updateUser } = useAuth();
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
        <div className="ui-person" style={{ marginBottom: role ? 12 : 0 }}>
          <Avatar name={user?.display_name || "মালিক"} src={user?.avatar_data_url} size={48} />
          <div>
            <strong>{user?.display_name || "লোকাল ডেমো মালিক"}</strong>
            <small>{user?.email || "লগইন ছাড়া ব্যবহার করছেন"}</small>
          </div>
          {role && <Badge tone="info">{ROLE_LABELS[role] || role}</Badge>}
        </div>
      </Card>

      {signedIn && (
        <>
          <Card title="প্রোফাইল ছবি">
            <ProfilePhotoField user={user} updateUser={updateUser} toast={toast} />
          </Card>

          <Card title="নাম ও যোগাযোগ">
            <ProfileDetailsForm user={user} updateUser={updateUser} toast={toast} />
          </Card>
        </>
      )}

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

      {signedIn && (
        <>
          <MfaSection user={user} updateUser={updateUser} toast={toast} />
          <SessionsSection toast={toast} />
        </>
      )}
    </div>
  );
}
