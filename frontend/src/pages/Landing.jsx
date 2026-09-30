// The public landing page — the first thing anyone sees before signing in.
// Explains what B-SMART is, what ব্যবসা মোড vs গবেষণা মোড mean, and exactly
// what every panel does, so a first-time owner (or an evaluator) is never
// dropped straight into a login form with no idea what the product is.

import { Link } from "react-router-dom";
import Icon from "../ui/Icon";
import { Badge, Card } from "../ui/kit";
import PanelGuide from "../components/PanelGuide";

const VALUE_PROPS = [
  ["zap", "AI সুপারিশ", "নিজের বিক্রি, স্টক ও কাস্টমারের ডেটা থেকে — কোনটা রিঅর্ডার করবেন, কোনটার মেয়াদ শেষ হয়ে যাচ্ছে, কোন কাস্টমার ফিরিয়ে আনতে হবে।"],
  ["box", "স্টক ও মেয়াদ", "ব্যাচ-ভিত্তিক স্টক, FEFO (আগে মেয়াদ শেষ হবে যেটা, আগে বিক্রি হবে সেটা), আর মেয়াদ ঝুঁকির টাকার হিসাব।"],
  ["card", "পূর্ণ হিসাব", "ডাবল-এন্ট্রি অ্যাকাউন্টিং, বাকি, ক্যাশ মেলানো, লাভ-ক্ষতি — সব এক জায়গায়, ম্যানুয়াল খাতার দরকার নেই।"],
  ["shield", "মালিকের নিয়ন্ত্রণ", "প্রতিটা বড় সিদ্ধান্তে মালিকের অনুমোদন লাগে; সিস্টেম সুপারিশ করে, শেষ সিদ্ধান্ত সবসময় মানুষের।"],
];

export default function Landing() {
  return (
    <div className="landing">
      <header className="landing-hero">
        <div className="landing-hero-inner">
          <Badge tone="success" icon="zap">বাংলাদেশি SME-দের জন্য</Badge>
          <h1>B-SMART</h1>
          <p className="landing-tagline">
            আপনার নিজের বিক্রি, স্টক ও কাস্টমারের ডেটা থেকে — কী করবেন, তার
            স্পষ্ট, ব্যাখ্যাসহ সুপারিশ। POS থেকে হিসাব-নিকাশ পর্যন্ত পুরো
            ব্যবসা একটা সফটওয়্যারে।
          </p>
          <div className="landing-cta">
            <Link className="ui-btn ui-btn--primary" to="/login">লগইন করুন</Link>
            <Link className="ui-btn ui-btn--secondary" to="/login">নতুন অ্যাকাউন্ট খুলুন</Link>
          </div>
        </div>
      </header>

      <section className="landing-values">
        {VALUE_PROPS.map(([icon, title, text]) => (
          <Card key={title} className="landing-value">
            <Icon name={icon} size={26} />
            <h3>{title}</h3>
            <p>{text}</p>
          </Card>
        ))}
      </section>

      <section className="landing-modes">
        <h2>দুইটা মোড, দুইটা আলাদা কাজের জন্য</h2>
        <div className="landing-modes-grid">
          <Card className="landing-mode">
            <Badge tone="success">ব্যবসা মোড</Badge>
            <p>দৈনন্দিন কাজের জায়গা — বিক্রি, স্টক, হিসাব, AI সুপারিশ। সম্পূর্ণ বাংলায়, ব্যবসার মালিক ও কর্মীদের জন্য বানানো।</p>
          </Card>
          <Card className="landing-mode">
            <Badge tone="info">গবেষণা মোড</Badge>
            <p>থিসিসের গবেষণা প্রমাণ — মডেলের accuracy, অ্যালগরিদমের ফলাফল, ডেটাসেটের বিস্তারিত। ইচ্ছাকৃতভাবে স্থির (static), যাতে উদ্ধৃত সংখ্যা বদলে না যায়।</p>
          </Card>
        </div>
      </section>

      <PanelGuide />

      <footer className="landing-footer">
        <p>শুরু করতে প্রস্তুত?</p>
        <Link className="ui-btn ui-btn--primary" to="/login">লগইন / নতুন অ্যাকাউন্ট</Link>
      </footer>
    </div>
  );
}
