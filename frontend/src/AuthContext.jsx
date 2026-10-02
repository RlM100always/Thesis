import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "./api";
import { AUTH_REQUIRED_EVENT } from "./auth";

const AuthContext = createContext(null);

// Who is signed in, and whether the API has told us a sign-in is required.
//
// Contexts further down (organizations, permissions) are keyed by user, so a
// sign-in or sign-out reloads the page rather than trying to reset each of them.
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [requiresLogin, setRequiresLogin] = useState(false);

  useEffect(() => {
    const onRequired = () => { setUser(null); setRequiresLogin(true); };
    window.addEventListener(AUTH_REQUIRED_EVENT, onRequired);
    return () => window.removeEventListener(AUTH_REQUIRED_EVENT, onRequired);
  }, []);

  useEffect(() => {
    // Always ask, not just when a token is saved: the backend's dev-mode
    // bypass (AUTH_MODE=development) answers /auth/me for an anonymous
    // request too, as the local prototype owner -- including that owner's
    // real is_platform_admin flag. Without this, someone who never explicitly
    // logged in would never see the platform-admin nav link, even though the
    // server has been granting them that access all along. In production
    // mode (a real deployment) this simply 401s and leaves user as null,
    // same as before.
    api.me().then(setUser).catch(() => {});
  }, []);

  const finish = useCallback((hash = "#/app") => {
    window.location.hash = hash;
    window.location.reload();
  }, []);

  // On success: signs in and navigates away (returns nothing meaningful).
  // On MFA challenge: returns { mfa_required: true, mfa_token } and does NOT
  // sign in yet — the caller (Login.jsx) collects the code and calls
  // completeMfa with it.
  const signIn = useCallback(async (email, password) => {
    const result = await api.login(email, password);
    if (result?.mfa_required) return result;
    setUser(result);
    finish();
    return undefined;
  }, [finish]);

  const completeMfa = useCallback(async (mfaToken, code) => {
    setUser(await api.verifyMfa(mfaToken, code));
    finish();
  }, [finish]);

  const signUp = useCallback(async (payload) => {
    setUser(await api.register(payload));
    finish();
  }, [finish]);

  // Straight back to the login form, not the marketing landing page --
  // someone who just chose to log out wants to sign back in, not be sold
  // the product again.
  const signOut = useCallback(async () => {
    await api.logout();
    setUser(null);
    finish("#/login");
  }, [finish]);

  const updateUser = useCallback((patch) => setUser((prev) => (prev ? { ...prev, ...patch } : prev)), []);

  const value = useMemo(
    () => ({ user, requiresLogin, signIn, completeMfa, signUp, signOut, updateUser }),
    [user, requiresLogin, signIn, completeMfa, signUp, signOut, updateUser],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
