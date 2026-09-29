import { useEffect, useState } from "react";
import { api } from "../api";
import { explain } from "../errors";
import { money } from "../format";
import { Button, Field, Modal, Notice } from "../ui/kit";
import { useToast } from "../ui/Toast";

export const PAY_METHODS = [["cash", "ক্যাশ"], ["bkash", "বিকাশ"], ["nagad", "নগদ"], ["bank", "ব্যাংক"]];

// Collect a baki from a customer, or pay a supplier. One form, two directions,
// so both the customers list and the accounts page behave identically.
export default function SettleModal({ orgId, kind, party, onClose, onDone }) {
  const toast = useToast();
  const isCustomer = kind === "customer";
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState("cash");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (party) { setAmount(String(party.balance)); setMethod("cash"); setNote(""); setError(""); }
  }, [party]);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const body = {
      amount: Number(amount).toFixed(2), payment_method: method,
      occurred_at: new Date().toISOString(), note: note || null,
    };
    try {
      if (isCustomer) await api.receiveCustomerPayment(orgId, party.id, body);
      else await api.paySupplier(orgId, party.id, body);
      toast.success(isCustomer ? `${party.name}-এর কাছ থেকে ${money(amount)} আদায় হয়েছে।` : `${party.name}-কে ${money(amount)} দেওয়া হয়েছে।`);
      onDone();
    } catch (err) {
      setError(explain(err, {
        409: "পরিমাণ বাকির চেয়ে বেশি। বাকির বেশি নেওয়া বা দেওয়া যায় না।",
        422: "পরিমাণ ও মাধ্যম ঠিকভাবে দিন।",
      }));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal open={Boolean(party)} onClose={onClose} title={isCustomer ? "বাকি আদায়" : "সাপ্লায়ারকে পেমেন্ট"}
           footer={<>
             <Button variant="secondary" onClick={onClose}>বাতিল</Button>
             <Button type="submit" form="settle-form" loading={busy}>{isCustomer ? "আদায় নিশ্চিত করুন" : "পেমেন্ট নিশ্চিত করুন"}</Button>
           </>}>
      {party && (
        <form id="settle-form" className="ui-form" onSubmit={submit}>
          <Notice tone="info">{party.name} · {isCustomer ? "আপনি পাবেন" : "আপনি দেবেন"}: <strong>{money(party.balance)}</strong></Notice>
          <Field label="কত টাকা?" required>
            <input type="number" min="0.01" max={party.balance} step="0.01" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} autoFocus />
          </Field>
          <Field label="মাধ্যম">
            <select value={method} onChange={(e) => setMethod(e.target.value)}>{PAY_METHODS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
          </Field>
          <Field label="নোট (ঐচ্ছিক)"><input value={note} onChange={(e) => setNote(e.target.value)} maxLength={200} /></Field>
          {error && <Notice tone="danger">{error}</Notice>}
        </form>
      )}
    </Modal>
  );
}
