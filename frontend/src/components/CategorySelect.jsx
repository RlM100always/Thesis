// A free-text category field means the same expense gets typed "ভাড়া",
// "Bhara", "rent" by different sessions — the AI analytics can't group what
// it can't recognize as one category. A closed dropdown keeps the data usable
// without stopping an owner from adding something new via "অন্যান্য".

import { useState } from "react";

export const EXPENSE_CATEGORIES = [
  "দোকান ভাড়া",
  "বিদ্যুৎ বিল",
  "কর্মচারীর বেতন",
  "পরিবহন",
  "মেরামত",
  "বিবিধ",
];

export function CategorySelect({ value, onChange, options = EXPENSE_CATEGORIES }) {
  const [customMode, setCustomMode] = useState(() => !!value && !options.includes(value));

  if (customMode) {
    return (
      <div className="category-custom">
        <input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="খরচের ধরন লিখুন"
        />
        <button type="button" className="btn-link" onClick={() => { setCustomMode(false); onChange(options[0]); }}>
          তালিকা থেকে বাছাই করুন
        </button>
      </div>
    );
  }

  return (
    <select
      value={value}
      onChange={(e) => {
        if (e.target.value === "__other__") { setCustomMode(true); onChange(""); }
        else onChange(e.target.value);
      }}
    >
      {options.map((option) => (
        <option key={option} value={option}>{option}</option>
      ))}
      <option value="__other__">অন্যান্য (নিজে লিখুন)</option>
    </select>
  );
}
