import { useRef, useState } from "react";
import { api } from "../api";
import { useBusiness } from "../BusinessContext";
import { explain } from "../errors";
import { num } from "../format";
import DataTable from "../ui/DataTable";
import { Button, Card, Field, Notice, PageHeader, Segmented } from "../ui/kit";
import { useToast } from "../ui/Toast";
import useBranch from "../useBranch";

// What each kind of list needs, in the words a shop owner uses.
const KINDS = {
  products: {
    label: "পণ্যের তালিকা",
    intro: "আপনার সব পণ্য একবারে যোগ করুন। প্রতিটি সারিতে একটি পণ্য।",
    fields: {
      sku: "পণ্যের কোড", name: "পণ্যের নাম", selling_price: "বিক্রয়মূল্য", cost_price: "ক্রয়মূল্য", category: "ক্যাটাগরি",
      unit: "একক", barcode: "বারকোড", reorder_level: "কমপক্ষে কত স্টক থাকা উচিত", track_expiry: "মেয়াদ ট্র্যাক করবেন? (হ্যাঁ/না)",
    },
    template: "sku,name,selling_price,cost_price,unit,reorder_level,track_expiry\nP-001,নাপা ৫০০ মিগ্রা,১.৫,১.১,পাতা,২০,হ্যাঁ\nP-002,চিনি ১ কেজি,১২৫,১১৫,প্যাকেট,১০,না\n",
  },
  customers: {
    label: "কাস্টমারের তালিকা",
    intro: "কাস্টমারের নাম ও মোবাইল নম্বর। নম্বর সরাসরি জমা থাকে না, শুধু সুরক্ষিত কোড হয়ে থাকে।",
    fields: { code: "কাস্টমার কোড", display_name: "নাম", phone: "মোবাইল নম্বর", marketing_consent: "মেসেজ পাঠানোর সম্মতি (হ্যাঁ/না)" },
    template: "code,name,phone,consent\nC-001,রিনা বেগম,01712345678,হ্যাঁ\nC-002,করিম উদ্দিন,01812345678,না\n",
  },
  opening_stock: {
    label: "শুরুর স্টক",
    intro: "এখন দোকানে কোন পণ্য কতটা আছে। পণ্য আগে যোগ করা থাকতে হবে। মেয়াদ ট্র্যাক করা পণ্যে ব্যাচ ও মেয়াদ লাগবে।",
    fields: { sku: "পণ্যের কোড", quantity: "পরিমাণ", batch_no: "ব্যাচ নম্বর", expiry_date: "মেয়াদ শেষের তারিখ", unit_cost: "প্রতি ইউনিট ক্রয়মূল্য" },
    template: "sku,quantity,batch_no,expiry_date,unit_cost\nP-001,200,B-2401,2027-06-30,1.1\nP-002,40,,,115\n",
  },
};
const REQUIRED = { products: ["sku", "name", "selling_price"], customers: ["code"], opening_stock: ["sku", "quantity"] };

function downloadTemplate(kind) {
  const blob = new Blob(["﻿" + KINDS[kind].template], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = `${kind}-নমুনা.csv`; a.click();
  URL.revokeObjectURL(url);
}

export default function ImportDataPage() {
  const { active } = useBusiness();
  const toast = useToast();
  const orgId = active?.id;
  const { branches, branch, setBranch } = useBranch(orgId);
  const fileRef = useRef(null);

  const [kind, setKind] = useState("products");
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [mapping, setMapping] = useState({});
  const [mode, setMode] = useState("skip_existing");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  const spec = KINDS[kind];
  const reset = () => { setFile(null); setPreview(null); setMapping({}); setResult(null); setError(""); if (fileRef.current) fileRef.current.value = ""; };
  const changeKind = (next) => { setKind(next); reset(); };

  async function pick(picked) {
    if (!picked) return;
    reset();
    setBusy("read");
    try {
      const data = await api.importPreview(orgId, kind, picked);
      setFile(picked);
      setPreview(data);
      setMapping(Object.fromEntries(Object.entries(data.mapping).filter(([, column]) => column)));
    } catch (e) {
      setError(explain(e, {
        400: "ফাইলটি পড়া যায়নি। শুধু CSV বা Excel (.xlsx) দিন, আর ফাইলে অন্তত একটি সারি থাকতে হবে।",
        403: "এই তালিকা আমদানির অনুমতি আপনার ভূমিকায় নেই।",
        413: "ফাইল খুব বড়। ৮ MB বা ৫,০০০ সারির মধ্যে রাখুন।",
      }));
    } finally { setBusy(""); }
  }

  async function commit() {
    setBusy("commit"); setError("");
    try {
      const done = await api.importCommit(orgId, kind, file, mapping, { mode, branchId: kind === "opening_stock" ? branch : "" });
      setResult(done);
      toast.success(`${num(done.created)}টি যোগ হয়েছে।`);
    } catch (e) {
      setError(explain(e, { 422: "প্রয়োজনীয় সব ঘরের জন্য ফাইলের একটি কলাম বেছে নিন।" }));
    } finally { setBusy(""); }
  }

  const ready = preview && REQUIRED[kind].every((f) => mapping[f]) && (kind !== "opening_stock" || branch);

  return (
    <div className="page stack">
      <PageHeader title="তথ্য আমদানি" subtitle="খাতা বা Excel থেকে পণ্য, কাস্টমার ও শুরুর স্টক একসাথে তুলে নিন। ভুল সারি আলাদা করে দেখানো হয়, বাকিগুলো জমা হয়।" />

      <Card>
        <div className="ui-form">
          <Segmented label="কী আমদানি করবেন" value={kind} onChange={changeKind}
                     options={Object.entries(KINDS).map(([value, k]) => ({ value, label: k.label }))} />
          <p className="muted" style={{ margin: 0 }}>{spec.intro}</p>
          <div className="row">
            <Button variant="secondary" icon="download" onClick={() => downloadTemplate(kind)}>নমুনা ফাইল নামান</Button>
          </div>
          {!preview && (
            <div>
              <input ref={fileRef} type="file" accept=".csv,.xlsx" aria-label="আমদানির ফাইল বেছে নিন" onChange={(e) => pick(e.target.files?.[0])} />
              {busy === "read" && <p className="muted">ফাইল পড়া হচ্ছে…</p>}
            </div>
          )}
          {error && <Notice tone="danger">{error}</Notice>}
        </div>
      </Card>

      {preview && !result && (
        <Card title="কলাম মিলিয়ে নিন" subtitle={`${file.name} · ${num(preview.rows)} সারি। আমরা যা অনুমান করেছি তা দেখে ঠিক করুন।`}>
          <div className="ui-form">
            <div className="ui-form ui-form--2">
              {Object.entries(spec.fields).map(([field, label]) => (
                <Field key={field} label={label} required={REQUIRED[kind].includes(field)}>
                  <select value={mapping[field] || ""} onChange={(e) => setMapping({ ...mapping, [field]: e.target.value })}>
                    <option value="">{REQUIRED[kind].includes(field) ? "— বেছে নিন —" : "— নেই —"}</option>
                    {preview.columns.map((c) => <option key={c} value={c}>{c}</option>)}
                  </select>
                </Field>
              ))}
            </div>

            {kind === "opening_stock" && (
              <Field label="কোন শাখার স্টক" required>
                <select value={branch} onChange={(e) => setBranch(e.target.value)}>
                  {(branches || []).map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
                </select>
              </Field>
            )}
            {kind !== "opening_stock" && (
              <Field label="আগে থেকে থাকা সারি হলে কী হবে">
                <select value={mode} onChange={(e) => setMode(e.target.value)}>
                  <option value="skip_existing">বাদ দিন (যা আছে তা অপরিবর্তিত)</option>
                  <option value="update_existing">নতুন তথ্য দিয়ে হালনাগাদ করুন</option>
                </select>
              </Field>
            )}

            <div>
              <strong style={{ fontSize: 13 }}>ফাইলের প্রথম কয়েকটি সারি</strong>
              <DataTable rowKey="_i" caption="ফাইলের নমুনা" rows={preview.sample.map((r, i) => ({ ...r, _i: i }))}
                         columns={preview.columns.slice(0, 6).map((c, i) => ({ key: c, label: c, primary: i === 0, render: (r) => r[c] || "—" }))} />
            </div>

            <div className="row">
              <Button disabled={!ready} loading={busy === "commit"} onClick={commit}>{num(preview.rows)}টি সারি জমা করুন</Button>
              <Button variant="secondary" onClick={reset}>অন্য ফাইল</Button>
            </div>
          </div>
        </Card>
      )}

      {result && (
        <Card title="আমদানি শেষ">
          <div className="ui-form">
            <div className="summary">
              <div><span>নতুন যোগ</span><strong>{num(result.created)}</strong></div>
              <div><span>হালনাগাদ</span><strong>{num(result.updated)}</strong></div>
              <div><span>বাদ (আগে থেকে আছে)</span><strong>{num(result.skipped)}</strong></div>
              <div><span>ভুল সারি</span><strong>{num(result.errors.length)}</strong></div>
            </div>
            {result.errors.length > 0 ? (
              <>
                <Notice tone="warn" title="এই সারিগুলো জমা হয়নি">ফাইলে ঠিক করে শুধু এই সারিগুলো আবার আমদানি করতে পারেন। বাকি সারি জমা হয়ে গেছে।</Notice>
                <DataTable rowKey="row" caption="ভুল সারির তালিকা" rows={result.errors}
                           columns={[
                             { key: "row", label: "লাইন", primary: true, render: (e) => `লাইন ${num(e.row)}` },
                             { key: "message", label: "কারণ", render: (e) => e.message },
                           ]} />
              </>
            ) : <Notice tone="success">সব সারি ঠিকঠাক জমা হয়েছে।</Notice>}
            <div className="row">
              <Button onClick={reset}>আরেকটি ফাইল</Button>
              {kind === "products" && <a className="ui-btn ui-btn--secondary" href="#/products">পণ্যের তালিকা দেখুন</a>}
              {kind === "opening_stock" && <a className="ui-btn ui-btn--secondary" href="#/inventory">স্টক দেখুন</a>}
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
