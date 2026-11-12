export const LOGIN_FAILURE_THRESHOLD = 6;
export const LOGIN_LOCK_DURATION_MS = 15 * 60 * 1000;

export function isLoginLocked(lock, now = Date.now()) {
  const until = Date.parse(lock?.lock_until || "");
  return Number.isFinite(until) && until > now;
}

export function nextLoginFailure(lock, now = Date.now()) {
  const oldUntil = Date.parse(lock?.lock_until || "");
  const lockExpired = Number.isFinite(oldUntil) && oldUntil <= now;
  const previousFailures = lockExpired ? 0 : Number(lock?.failures || 0);
  const failures = previousFailures + 1;
  return {
    failures,
    lock_until: failures >= LOGIN_FAILURE_THRESHOLD
      ? new Date(now + LOGIN_LOCK_DURATION_MS).toISOString()
      : null,
  };
}
