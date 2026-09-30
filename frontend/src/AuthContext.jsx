import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "./api";
import { AUTH_REQUIRED_EVENT, getTokens } from "./auth";

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
    if (getTokens()) api.me().then(setUser).catch(() => {});
  }, []);

  const finish = useCallback((hash = "#/") => {
    window.location.hash = hash;
    window.location.reload();
  }, []);

  const signIn = useCallback(async (email, password) => {
    setUser(await api.login(email, password));
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

  const value = useMemo(
    () => ({ user, requiresLogin, signIn, signUp, signOut }),
    [user, requiresLogin, signIn, signUp, signOut],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
