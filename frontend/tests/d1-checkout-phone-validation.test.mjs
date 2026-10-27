import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { isValidShippingPhone } from "../../cloudflare/commerce-worker.js";

const workerSource = readFileSync(new URL("../../cloudflare/commerce-worker.js", import.meta.url), "utf8");

test("COD checkout accepts common valid Bangladesh and international phone formats", () => {
  for (const phone of [
    "01712345678",
    "+8801712345678",
    "+880 1712 345678",
    "+880 (171) 234-5678",
    "1234567",
  ]) {
    assert.equal(isValidShippingPhone(phone), true, `expected valid phone: ${phone}`);
  }
});

test("COD checkout rejects missing, too-short, too-long and alphabetic phone numbers", () => {
  for (const phone of ["", "123456", "017ABC45678", "1234567890123456", "++8801712345678", "017/12345678"]) {
    assert.equal(isValidShippingPhone(phone), false, `expected invalid phone: ${phone}`);
  }
});

test("operational checkout uses the tested phone validator", () => {
  assert.match(workerSource, /!isValidShippingPhone\(shippingPhone\)/);
});
