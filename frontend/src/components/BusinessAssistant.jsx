// "ব্যবসা সম্পর্কে জিজ্ঞাসা করুন" -- plain-Bangla questions, answered from the
// organization's own real data (api/assistant_routes.py). Not a general
// chatbot: an unrecognised question gets an honest "বুঝতে পারছি না" and a
// list of what it can answer, never a guess.
import { useState } from "react";
import { api } from "../api";
import { useBusiness } from "../BusinessContext";
import { explain } from "../errors";
import { Badge, Button, Card } from "../ui/kit";

const SUGGESTIONS = [
  "আজকের বিক্রি কেমন হলো?",
  "কোন পণ্য বেশি বিক্রি হচ্ছে?",
  "কোন পণ্যের স্টক কমে গেছে?",
  "কার কাছে কত বাকি আছে?",
];

export default function BusinessAssistant() {
  const { active } = useBusiness();
  const orgId = active?.id;
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState([]); // [{question, text, answered, source}]
  const [busy, setBusy] = useState(false);

  async function ask(q) {
    const text = (q ?? question).trim();
    if (!text || !orgId) return;
    setBusy(true);
    setQuestion("");
    try {
      const result = await api.askAssistant(orgId, text);
      setHistory((prev) => [...prev, { question: text, ...result }]);
    } catch (err) {
      setHistory((prev) => [...prev, { question: text, answered: false, text: explain(err) }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="ব্যবসা সম্পর্কে জিজ্ঞাসা করুন" subtitle="আপনার দোকানের আসল তথ্য থেকে উত্তর দেয়।">
      {history.length === 0 && (
        <div className="row" style={{ gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
          {SUGGESTIONS.map((s) => (
            <button key={s} type="button" className="assistant-suggestion" onClick={() => ask(s)}>{s}</button>
          ))}
        </div>
      )}
      {history.length > 0 && (
        <div className="assistant-history">
          {history.map((item, i) => (
            <div key={i} className="assistant-turn">
              <div className="assistant-question">{item.question}</div>
              <div className={`assistant-answer ${item.answered === false ? "unanswered" : ""}`}>
                {item.text}
                {item.source === "llm" && <Badge tone="info">AI</Badge>}
              </div>
            </div>
          ))}
        </div>
      )}
      <form className="assistant-input" onSubmit={(e) => { e.preventDefault(); ask(); }}>
        <input
          value={question} onChange={(e) => setQuestion(e.target.value)}
          placeholder="যেমন: আজকে কত বিক্রি হয়েছে?" maxLength={300} autoComplete="off"
        />
        <Button type="submit" loading={busy} disabled={!question.trim()}>জিজ্ঞাসা করুন</Button>
      </form>
    </Card>
  );
}
