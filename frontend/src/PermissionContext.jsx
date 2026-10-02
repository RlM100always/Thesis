import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { api } from "./api";
import { useBusiness } from "./BusinessContext";

const PermissionContext = createContext(null);

// Bangla role names for the sidebar. The role strings are the API's.
export const ROLE_LABELS = {
  owner: "মালিক",
  manager: "ম্যানেজার",
  cashier: "ক্যাশিয়ার",
  accountant: "হিসাবরক্ষক",
  stock_keeper: "স্টোরকিপার",
  viewer: "দর্শক",
  evaluator: "মূল্যায়নকারী",
  rider: "ডেলিভারি রাইডার",
};

// One line per role, in plain Bangla, shown where an owner chooses a role.
export const ROLE_DESCRIPTIONS = {
  owner: "সব কিছু দেখতে ও করতে পারেন, কর্মী ব্যবস্থাপনাসহ।",
  manager: "বিক্রি, স্টক, ক্রয় ও সুপারিশ পরিচালনা করেন। কর্মী যোগ করতে বা সাপ্লায়ারকে টাকা দিতে পারেন না।",
  cashier: "শুধু বিক্রি, রিটার্ন ও কাস্টমারের বাকি আদায়। লাভ-খরচ দেখেন না।",
  accountant: "হিসাব, খরচ, ক্রয় ও সাপ্লায়ার পেমেন্ট দেখেন। বিক্রি করেন না।",
  stock_keeper: "স্টক গ্রহণ, সমন্বয় ও ক্রয়ের মাল রিসিভ করেন। টাকার হিসাব দেখেন না।",
  viewer: "শুধু দেখতে পারেন, কিছু বদলাতে পারেন না।",
  evaluator: "গবেষণা ও মনিটরিংয়ের তথ্য শুধু পড়তে পারেন (সুপারভাইজার বা পরীক্ষকের জন্য)।",
  rider: "শুধু নিজের ডেলিভারি দেখেন ও আপডেট করেন -- রুট, ডেলিভারি প্রমাণ ও COD সংগ্রহ।",
};

// What the signed-in user may do in the active business.
//
// This only decides what to *show*. The server enforces every permission, so if
// the lookup fails we fall back to showing everything and let the API answer 403,
// rather than hiding a page the user is in fact allowed to use.
export function PermissionProvider({ children }) {
  const { active } = useBusiness();
  const activeId = active?.id;
  const [state, setState] = useState({ orgId: null, role: null, granted: null });

  useEffect(() => {
    if (!activeId) return undefined;
    let current = true;
    api.permissions(activeId)
      .then((res) => current && setState({ orgId: activeId, role: res.role, granted: new Set(res.permissions) }))
      .catch(() => current && setState({ orgId: activeId, role: null, granted: null }));
    return () => { current = false; };
  }, [activeId]);

  const value = useMemo(() => {
    const ready = !activeId || state.orgId === activeId;
    const granted = ready ? state.granted : null;
    return {
      ready,
      role: ready ? state.role : null,
      can: (permission) => !permission || granted === null || granted.has(permission),
    };
  }, [activeId, state]);

  return <PermissionContext.Provider value={value}>{children}</PermissionContext.Provider>;
}

export function usePermissions() {
  const value = useContext(PermissionContext);
  if (!value) throw new Error("usePermissions must be used inside PermissionProvider");
  return value;
}
