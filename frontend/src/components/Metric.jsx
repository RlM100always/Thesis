// Term label that swaps vocabulary with the Simple/Technical toggle.
//
// The dashboard has two audiences: a shop owner who needs to know who to call
// this week, and a thesis examiner who needs the confidence intervals. Rather
// than picking one, every term carries both readings in glossary.js and the
// toggle chooses which is shown. The other reading, plus the one-line "why
// should I care", stays available on hover.

import { term } from "../glossary";
import { useUi } from "../UiContext";

export function TermLabel({ termKey }) {
  const { simple } = useUi();
  const t = term(termKey);
  const shown = simple ? t.plain : t.label;
  const other = simple ? t.label : t.plain;

  return (
    <span className="term" title={t.detail ? `${other} — ${t.detail}` : other}>
      {shown}
    </span>
  );
}
