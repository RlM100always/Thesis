import { useEffect, useState } from "react";
import { api } from "../api";
import { explain } from "../errors";
import { Button, Field, Modal, Notice } from "../ui/kit";
import { useToast } from "../ui/Toast";

const str = (v) => (v == null ? "" : String(v));

// Change a product after it was created. The code (SKU) and expiry tracking are fixed.
export function EditProductModal({ orgId, product, onClose, onSaved }) {
  const toast = useToast();
  const [form, setForm] = useState({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!product) return;
    setError("");
    setForm({
      name: product.name, category: str(product.category), barcode: str(product.barcode), selling_price: str(product.selling_price),
      cost_price: str(product.cost_price), wholesale_price: str(product.wholesale_price), reorder_level: str(product.reorder_level),
    });
  }, [product]);
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  async function save(e) {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      await api.updateProduct(orgId, product.id, {
        name: form.name, category: form.category || null, barcode: form.barcode || null,
        selling_price: form.selling_price, cost_price: form.cost_price || "0",
        wholesale_price: form.wholesale_price === "" ? null : form.wholesale_price, reorder_level: form.reorder_level || "0",
      });
      toast.success("পণ্যের তথ্য সংরক্ষিত হয়েছে। দামের বদল কার্যকলাপের ইতিহাসে লেখা থাকবে।");
      onSaved();
    } catch (err) {
      setError(explain(err, { 403: "পণ্য বদলানোর অনুমতি আপনার ভূমিকায় নেই।", 422: "নাম ও দাম ঠিকভাবে দিন।" }));
    } finally { setBusy(false); }
  }

  async function archive() {
    setBusy(true);
    try {
      await api.updateProduct(orgId, product.id, { active: false });
      toast.success("পণ্যটি তালিকা থেকে সরানো হয়েছে। আগের বিক্রির হিসাব অক্ষত আছে।");
      onSaved();
    } catch (err) { setError(explain(err)); } finally { setBusy(false); }
  }

  return (
    <Modal open={Boolean(product)} title={product ? `সম্পাদনা: ${product.name}` : ""} onClose={onClose}
           footer={<>
             <Button variant="ghost" onClick={archive} loading={busy}>তালিকা থেকে সরান</Button>
             <Button variant="secondary" onClick={onClose}>বাতিল</Button>
             <Button type="submit" form="edit-product-form" loading={busy}>সংরক্ষণ করুন</Button>
           </>}>
      <form id="edit-product-form" className="ui-form ui-form--2" onSubmit={save}>
        <Field label="পণ্যের নাম" required><input value={form.name || ""} onChange={set("name")} /></Field>
        <Field label="ক্যাটাগরি"><input value={form.category || ""} onChange={set("category")} /></Field>
        <Field label="বিক্রয়মূল্য (৳)" required><input type="number" min="0" step="0.01" value={form.selling_price || ""} onChange={set("selling_price")} /></Field>
        <Field label="পাইকারি দাম (৳)" hint="পাইকারি কাস্টমারের জন্য; ফাঁকা রাখলে সবাই একই দাম দেবে"><input type="number" min="0" step="0.01" value={form.wholesale_price || ""} onChange={set("wholesale_price")} /></Field>
        <Field label="ক্রয়মূল্য (৳)"><input type="number" min="0" step="0.01" value={form.cost_price || ""} onChange={set("cost_price")} /></Field>
        <Field label="পুনঃঅর্ডার সীমা"><input type="number" min="0" step="0.001" value={form.reorder_level || ""} onChange={set("reorder_level")} /></Field>
        <Field label="বারকোড"><input value={form.barcode || ""} onChange={set("barcode")} /></Field>
        {error && <div className="ui-span"><Notice tone="danger">{error}</Notice></div>}
      </form>
    </Modal>
  );
}

// Credit limit and price tier live here so a shop can decide who may buy on baki, and at what price.
export function EditCustomerModal({ orgId, customer, onClose, onSaved }) {
  const toast = useToast();
  const [form, setForm] = useState({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!customer) return;
    setError("");
    setForm({ display_name: str(customer.display_name), phone: "", credit_limit: str(customer.credit_limit), price_tier: customer.price_tier || "retail", marketing_consent: customer.marketing_consent });
  }, [customer]);

  async function save(e) {
    e.preventDefault();
    setBusy(true); setError("");
    const body = {
      display_name: form.display_name || null, credit_limit: form.credit_limit === "" ? null : form.credit_limit,
      price_tier: form.price_tier, marketing_consent: form.marketing_consent,
    };
    if (form.phone) body.phone = form.phone;
    try {
      await api.updateCustomer(orgId, customer.id, body);
      toast.success("কাস্টমারের তথ্য সংরক্ষিত হয়েছে।");
      onSaved();
    } catch (err) {
      setError(explain(err, { 422: "মোবাইল নম্বর (১০-১৫ সংখ্যা) ও বাকির সীমা ঠিকভাবে দিন।" }));
    } finally { setBusy(false); }
  }

  return (
    <Modal open={Boolean(customer)} title={customer ? `সম্পাদনা: ${customer.display_name || customer.code}` : ""} onClose={onClose}
           footer={<><Button variant="secondary" onClick={onClose}>বাতিল</Button><Button type="submit" form="edit-customer-form" loading={busy}>সংরক্ষণ করুন</Button></>}>
      <form id="edit-customer-form" className="ui-form" onSubmit={save}>
        <Field label="নাম"><input value={form.display_name || ""} onChange={(e) => setForm({ ...form, display_name: e.target.value })} /></Field>
        <Field label="নতুন মোবাইল নম্বর" hint="বদলাতে চাইলে দিন; ফাঁকা রাখলে আগেরটাই থাকবে"><input inputMode="tel" value={form.phone || ""} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></Field>
        <Field label="বাকির সীমা (৳)" hint="এর বেশি বাকিতে বিক্রি হবে না। ফাঁকা রাখলে সীমা নেই"><input type="number" min="0" step="0.01" value={form.credit_limit || ""} onChange={(e) => setForm({ ...form, credit_limit: e.target.value })} /></Field>
        <Field label="দামের ধরন">
          <select value={form.price_tier || "retail"} onChange={(e) => setForm({ ...form, price_tier: e.target.value })}>
            <option value="retail">খুচরা</option>
            <option value="wholesale">পাইকারি</option>
          </select>
        </Field>
        <label className="checkbox" style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <input type="checkbox" checked={Boolean(form.marketing_consent)} onChange={(e) => setForm({ ...form, marketing_consent: e.target.checked })} style={{ width: 20, height: 20 }} />
          <span>বার্তা পাঠানোর সম্মতি আছে</span>
        </label>
        {error && <Notice tone="danger">{error}</Notice>}
      </form>
    </Modal>
  );
}
