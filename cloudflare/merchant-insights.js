// Read-only merchant analytics. All amounts are order values, NOT verified cash.
// Never join across stores without scoping the merchant's store id.
export function summarizeOrderStatuses(rows = []) {
 const initial={orders:0,booked_bdt:0,fulfilled_bdt:0,cancelled:0,open:0,
   avg_order_bdt:0,cancellation_rate_pct:0};
 for(const row of rows){
  const count=Number(row.orders||0),amount=Number(row.amount_bdt||0);
  initial.orders+=count;
  if(row.status==="cancelled")initial.cancelled+=count;
  else initial.booked_bdt+=amount;
  if(row.status==="fulfilled")initial.fulfilled_bdt+=amount;
  else if(row.status!=="cancelled")initial.open+=count;
 }
 initial.avg_order_bdt=initial.orders?Math.round(initial.booked_bdt/(initial.orders-initial.cancelled||1)):0;
 initial.cancellation_rate_pct=initial.orders?Math.round(initial.cancelled*1000/initial.orders)/10:0;
 return initial;
}
export async function merchantInsights(db,storeId,days=30){
 const range="-"+days+" days";
 const [statuses,daily,top,low]=await Promise.all([
  db.prepare("SELECT status,COUNT(*) AS orders,COALESCE(SUM(total_bdt),0) AS amount_bdt FROM commerce_orders WHERE store_id=? AND placed_at >= datetime('now',?) GROUP BY status").bind(storeId,range).all(),
  db.prepare("SELECT date(placed_at) AS day,COUNT(*) AS orders,COALESCE(SUM(CASE WHEN status!='cancelled' THEN total_bdt ELSE 0 END),0) AS booked_bdt FROM commerce_orders WHERE store_id=? AND placed_at >= datetime('now',?) GROUP BY date(placed_at) ORDER BY day ASC LIMIT 100").bind(storeId,range).all(),
  db.prepare("SELECT l.product_id,l.product_name,SUM(l.quantity) AS units,SUM(l.line_total_bdt) AS amount_bdt FROM commerce_order_lines l JOIN commerce_orders o ON o.id=l.order_id WHERE o.store_id=? AND o.status!='cancelled' AND o.placed_at >= datetime('now',?) GROUP BY l.product_id,l.product_name ORDER BY units DESC,amount_bdt DESC LIMIT 10").bind(storeId,range).all(),
  db.prepare("SELECT id,sku,name,stock_qty,reorder_point,is_listed FROM commerce_products WHERE store_id=? AND is_listed=1 AND stock_qty<=reorder_point ORDER BY stock_qty ASC,name LIMIT 50").bind(storeId).all()
 ]);
 return {days,amounts_are_verified_payments:false,summary:summarizeOrderStatuses(statuses.results),
   status_breakdown:statuses.results,daily:daily.results,top_products:top.results,
   low_stock:low.results,low_stock_count:low.results.length,
   low_stock_count_capped:low.results.length===50};
}
