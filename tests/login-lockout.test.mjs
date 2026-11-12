import test from "node:test";
import assert from "node:assert/strict";
import { isLoginLocked, nextLoginFailure, LOGIN_LOCK_DURATION_MS } from "../cloudflare/login-lockout.mjs";

test("login failures trigger a temporary lock after six attempts", () => {
  const now = Date.parse("2026-11-08T10:00:00.000Z");
  let state = null;
  for (let i = 0; i < 5; i++) state = nextLoginFailure(state, now);
  assert.equal(state.failures, 5);
  assert.equal(state.lock_until, null);
  state = nextLoginFailure(state, now);
  assert.equal(state.failures, 6);
  assert.equal(Date.parse(state.lock_until), now + LOGIN_LOCK_DURATION_MS);
  assert.equal(isLoginLocked(state, now), true);
});

test("expired lockouts reset the failure counter instead of locking forever", () => {
  const now = Date.parse("2026-11-08T10:16:00.000Z");
  const expired = { failures: 9, lock_until: "2026-11-08T10:15:00.000Z" };
  assert.equal(isLoginLocked(expired, now), false);
  const next = nextLoginFailure(expired, now);
  assert.deepEqual(next, { failures: 1, lock_until: null });
});

test("active lockouts do not reset before their expiry", () => {
  const now = Date.parse("2026-11-08T10:14:00.000Z");
  const active = { failures: 6, lock_until: "2026-11-08T10:15:00.000Z" };
  assert.equal(isLoginLocked(active, now), true);
  assert.equal(nextLoginFailure(active, now).failures, 7);
});
