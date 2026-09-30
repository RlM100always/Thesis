// Shared by the public landing page (pages/Landing.jsx) and the in-app
// "গাইড" page (pages/Guide.jsx) — one description per panel, in one place,
// so the two never drift into two different explanations of the same thing.

import { BUSINESS_GUIDE, RESEARCH_GUIDE } from "../panelGuide";

export default function PanelGuide({ subtitle }) {
  return (
    <section className="landing-guide">
      <h2>কোন প্যানেল কী করে</h2>
      <p className="landing-guide-sub">{subtitle ?? <>সাইন-আপ করার পর বাম দিকে এই প্যানেলগুলো দেখবেন — <strong>ব্যবসা মোড</strong>-এ।</>}</p>
      <div className="landing-guide-grid">
        {BUSINESS_GUIDE.map((group) => (
          <div key={group.heading} className="landing-guide-group">
            <h3>{group.heading}</h3>
            <ul>
              {group.items.map((item) => (
                <li key={item.to}>
                  <strong>{item.label}</strong>
                  <span>{item.description}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <div className="landing-research-note">
        <h3>{RESEARCH_GUIDE.heading}</h3>
        <p>{RESEARCH_GUIDE.note}</p>
        <ul>
          {RESEARCH_GUIDE.items.map((item) => (
            <li key={item.label}><strong>{item.label}</strong><span>{item.description}</span></li>
          ))}
        </ul>
      </div>
    </section>
  );
}
