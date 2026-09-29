import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useBusiness } from "../BusinessContext";
import { dateBn, money, num } from "../format";
import Icon from "../ui/Icon";
import { Button, Card, Skeleton } from "../ui/kit";
import { useToast } from "../ui/Toast";

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? "সুপ্রভাত" : h < 17 ? "শুভ দুপুর" : "শুভ সন্ধ্যা";
}

// Plain text the owner can paste anywhere (WhatsApp to a partner, a note to themselves).
function briefText(shop, b) {
  const lines = [`${shop} — ${dateBn(b.date)}`, `গতকাল বিক্রি: ${money(b.yesterday.sales)} (${num(b.yesterday.orders)}টি চালান)`];
  if (b.low_stock?.count) lines.push(`কম স্টক (${num(b.low_stock.count)}টি): ${b.low_stock.items.map((i) => i.name).join(", ")}`);
  if (b.expiry && (Number(b.expiry.expired_units) || Number(b.expiry.within_30_units))) {
    lines.push(`মেয়াদ: শেষ ${num(b.expiry.expired_units)} ইউনিট, ৩০ দিনে শেষ হবে ${num(b.expiry.within_30_units)} ইউনিট`);
  }
  if (b.dues?.customers) lines.push(`বাকি পাওনা: ${money(b.dues.total)} (${num(b.dues.customers)} জনের কাছে)`);
  if (Number(b.we_owe) > 0) lines.push(`সাপ্লায়ারকে দিতে হবে: ${money(b.we_owe)}`);
  return lines.join("\n");
}

// One screen-full for the start of the day, computed from the shop's own records.
export default function MorningBrief() {
  const { active } = useBusiness();
  const toast = useToast();
  const [brief, setBrief] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!active?.id) return;
    api.brief(active.id).then(setBrief).catch(() => setFailed(true));
  }, [active?.id]);

  const text = useMemo(() => (brief ? briefText(active.name, brief) : ""), [brief, active]);
  if (failed) return null;
  if (!brief) return <Card><Skeleton lines={3} height={18} /></Card>;

  const y = brief.yesterday;
  const usual = Number(y.usual_daily_sales);
  const change = usual > 0 ? Math.round(((Number(y.sales) - usual) / usual) * 100) : null;
  const nothingToDo = !brief.low_stock?.count && !brief.dues?.customers && !(brief.expiry && (Number(brief.expiry.expired_units) || Number(brief.expiry.within_30_units))) && !brief.pending_purchases && !brief.pending_recommendations;

  async function copy() {
    try { await navigator.clipboard.writeText(text); toast.success("কপি হয়েছে।"); } catch { toast.error("কপি করা যায়নি।"); }
  }

  return (
    <Card>
      <div className="brief">
        <div className="brief__hello">
          <div>
            <h3>{greeting()}! আজকের সংক্ষেপ</h3>
            <p>
              গতকাল <strong>{money(y.sales)}</strong> বিক্রি হয়েছে ({num(y.orders)}টি চালান)
              {change !== null && ` — গত ৭ দিনের গড়ের চেয়ে ${num(Math.abs(change))}% ${change >= 0 ? "বেশি" : "কম"}`}।
            </p>
          </div>
          <div className="row">
            <Button size="sm" variant="secondary" icon="copy" onClick={copy}>কপি</Button>
            <a className="ui-btn ui-btn--secondary ui-btn--sm" href={`https://wa.me/?text=${encodeURIComponent(text)}`} target="_blank" rel="noreferrer">
              <Icon name="share" size={16} /><span>WhatsApp-এ পাঠান</span>
            </a>
          </div>
        </div>

        {nothingToDo ? (
          <p className="muted" style={{ margin: 0 }}>আজ জরুরি কিছু নেই। বিক্রি চালিয়ে যান!</p>
        ) : (
          <div className="brief__cols">
            {brief.low_stock?.count > 0 && (
              <div className="brief__col">
                <h4><Icon name="box" size={16} />কিনতে হবে ({num(brief.low_stock.count)}টি)</h4>
                <ul>{brief.low_stock.items.map((i) => <li key={i.product_id}><span>{i.name}</span><span>{num(i.quantity)} বাকি</span></li>)}</ul>
                <p style={{ margin: "8px 0 0" }}><a href="#/purchases">ক্রয় অর্ডার দিন →</a></p>
              </div>
            )}
            {brief.expiry && (Number(brief.expiry.expired_units) > 0 || Number(brief.expiry.within_30_units) > 0) && (
              <div className="brief__col">
                <h4><Icon name="clock" size={16} />মেয়াদ</h4>
                <ul>
                  {Number(brief.expiry.expired_units) > 0 && <li><span>মেয়াদ শেষ</span><span>{num(brief.expiry.expired_units)} ইউনিট</span></li>}
                  {Number(brief.expiry.within_30_units) > 0 && <li><span>৩০ দিনে শেষ হবে</span><span>{num(brief.expiry.within_30_units)} ইউনিট</span></li>}
                  <li><span>আটকে থাকা টাকা</span><span>{money(brief.expiry.at_risk_value)}</span></li>
                </ul>
                <p style={{ margin: "8px 0 0" }}><a href="#/expiry">মেয়াদ দেখুন →</a></p>
              </div>
            )}
            {brief.dues?.customers > 0 && (
              <div className="brief__col">
                <h4><Icon name="users" size={16} />বাকি আদায় ({money(brief.dues.total)})</h4>
                <ul>{brief.dues.top.map((c) => <li key={c.customer_id}><span>{c.name}</span><span>{money(c.balance)}</span></li>)}</ul>
                <p style={{ margin: "8px 0 0" }}><a href="#/directory">সবার তালিকা →</a></p>
              </div>
            )}
            {(brief.pending_purchases > 0 || brief.pending_recommendations > 0) && (
              <div className="brief__col">
                <h4><Icon name="zap" size={16} />অপেক্ষায় আছে</h4>
                <ul>
                  {brief.pending_purchases > 0 && <li><span>মাল আসার অপেক্ষায় অর্ডার</span><span>{num(brief.pending_purchases)}টি</span></li>}
                  {brief.pending_recommendations > 0 && <li><span>সিদ্ধান্ত বাকি সুপারিশ</span><span>{num(brief.pending_recommendations)}টি</span></li>}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </Card>
  );
}
