// Session tokens and the fetch wrapper that carries them.
//
// The API issues a short-lived access token and a longer-lived refresh token.
// authedFetch attaches the access token, and on a 401 refreshes once and retries
// the request. If that also fails the session is over: tokens are cleared and an
// event tells the app to show the login page.
//
// In development the backend accepts anonymous requests as a local prototype
// owner, so nothing here changes that flow until someone signs in.

const KEY = "bsmart.tokens";
export const AUTH_REQUIRED_EVENT = "bsmart:auth-required";

// Login, register and refresh are the calls that *obtain* a session; a 401 from
// them means "wrong credentials", not "session expired".
const SESSION_ENDPOINTS = /^\/api\/app\/auth\/(login|register|refresh)$/;

export function getTokens() {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null; // private window / blocked storage: behave as signed out
  }
}

export function saveTokens({ access_token: access, refresh_token: refresh }) {
  try {
    localStorage.setItem(KEY, JSON.stringify({ access, refresh }));
  } catch {
    // storage unavailable: the session lasts until the page closes
  }
}

export function clearTokens() {
  try {
    localStorage.removeItem(KEY);
  } catch {
    // nothing to clear
  }
}

// One refresh at a time: several requests can hit 401 together and each would
// otherwise rotate the refresh token and invalidate the others.
let refreshing = null;

function refreshAccess(base) {
  const tokens = getTokens();
  if (!tokens?.refresh) return Promise.resolve(false);
  if (!refreshing) {
    refreshing = fetch(`${base}/api/app/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: tokens.refresh }),
    })
      .then(async (res) => {
        if (!res.ok) return false;
        saveTokens(await res.json());
        return true;
      })
      .catch(() => false)
      .finally(() => { refreshing = null; });
  }
  return refreshing;
}

export async function authedFetch(base, path, init = {}) {
  const send = () => {
    const headers = new Headers(init.headers || {});
    const tokens = getTokens();
    if (tokens?.access) headers.set("Authorization", `Bearer ${tokens.access}`);
    return fetch(`${base}${path}`, { ...init, headers });
  };
  let res = await send();
  if (res.status === 401 && !SESSION_ENDPOINTS.test(path)) {
    if (await refreshAccess(base)) res = await send();
    if (res.status === 401) {
      clearTokens();
      window.dispatchEvent(new Event(AUTH_REQUIRED_EVENT));
    }
  }
  return res;
}
