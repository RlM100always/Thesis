"""Verify fresh D1 v1-v12 schema and stock auditing with stdlib SQLite.

Runs in CI against an isolated in-memory database, never live Cloudflare data.
"""
from pathlib import Path
import sqlite3

migrations = Path(__file__).resolve().parents[1] / "migrations"
db = sqlite3.connect(":memory:")
db.execute("PRAGMA foreign_keys = ON")
for script in sorted(migrations.glob("*.sql")):
    db.executescript(script.read_text(encoding="utf-8"))
assert db.execute("SELECT value FROM commerce_meta WHERE key='schema_version'").fetchone() == ("12",)

db.execute("INSERT INTO merchant_accounts(id,email,password_hash,password_salt) VALUES('owner','owner@example.test','ACCESS_KEY_ONLY','DISABLED')")
db.execute("""INSERT INTO commerce_stores(id,slug,name,category,area,is_demo,is_active,owner_id,real_cod_approved)
              VALUES('real-shop','real-shop','Approved shop','Retail','Rajshahi',0,1,'owner',1)""")
db.execute("""INSERT INTO commerce_products(id,store_id,sku,name,price_bdt,stock_qty)
              VALUES('real-item','real-shop','R1','Item',150,2)""")
db.execute("""INSERT INTO commerce_customers(id,store_id,display_name)
              VALUES('customer','real-shop','Customer Example')""")
db.execute("""INSERT INTO commerce_orders(id,store_id,order_number,access_token,status,subtotal_bdt,total_bdt,
              payment_method,shipping_name,shipping_phone,shipping_address,customer_id)
              VALUES('real-order','real-shop','COD-TEST','TEST-TOKEN','placed',150,150,
              'cod','Customer Example','01712345678','Road 1, Rajshahi','customer')""")
db.execute("""INSERT INTO commerce_order_lines(order_id,product_id,product_name,quantity,price_bdt,line_total_bdt)
              VALUES('real-order','real-item','Item',1,150,150)""")
assert db.execute("SELECT stock_qty FROM commerce_products WHERE id='real-item'").fetchone() == (1,)
assert db.execute("SELECT reason FROM commerce_inventory_movements WHERE order_id='real-order'").fetchone() == ("online_cod_sale",)
db.execute("UPDATE commerce_orders SET status='cancelled' WHERE id='real-order'")
assert db.execute("SELECT stock_qty FROM commerce_products WHERE id='real-item'").fetchone() == (2,)
assert db.execute("SELECT reason FROM commerce_inventory_movements WHERE order_id='real-order' ORDER BY created_at,id").fetchall() == [
    ("online_cod_sale",), ("cod_cancel_return",)
] or set(row[0] for row in db.execute("SELECT reason FROM commerce_inventory_movements WHERE order_id='real-order'")) == {"online_cod_sale","cod_cancel_return"}
db.execute("UPDATE commerce_orders SET status='cancelled' WHERE id='real-order'")
assert db.execute("SELECT COUNT(*) FROM commerce_inventory_movements WHERE order_id='real-order'").fetchone() == (2,)

db.execute("INSERT INTO commerce_stores(id,slug,name) VALUES('demo-shop','demo-shop','Demo')")
db.execute("INSERT INTO commerce_products(id,store_id,sku,name,price_bdt,stock_qty) VALUES('demo-item','demo-shop','D1','Sample',99,3)")
db.execute("INSERT INTO commerce_orders(id,store_id,order_number,access_token,subtotal_bdt,total_bdt) VALUES('demo-order','demo-shop','DEMO-TEST','DEMO-TOKEN',99,99)")
db.execute("INSERT INTO commerce_order_lines(order_id,product_id,product_name,quantity,price_bdt,line_total_bdt) VALUES('demo-order','demo-item','Sample',1,99,99)")
assert db.execute("SELECT reason FROM commerce_inventory_movements WHERE order_id='demo-order'").fetchone() == ("demo_sale",)
assert db.execute("SELECT stock_qty FROM commerce_products WHERE id='demo-item'").fetchone() == (2,)

# v7: transactional owner-side adjustments, threshold values, immutable event audit.
assert db.execute("SELECT reorder_point FROM commerce_products WHERE id='real-item'").fetchone() == (5,)
db.execute("""INSERT INTO commerce_inventory_corrections(id,store_id,product_id,delta,reason,note)
              VALUES('correction-1','real-shop','real-item',8,'restock','Received sealed boxes')""")
assert db.execute("SELECT stock_qty FROM commerce_products WHERE id='real-item'").fetchone() == (10,)
assert db.execute("SELECT old_quantity,new_quantity,delta,reason FROM commerce_stock_adjustments WHERE store_id='real-shop'").fetchone() == (2,10,8,"restock: Received sealed boxes")
db.execute("INSERT INTO commerce_inventory_corrections(id,store_id,product_id,delta,reason) VALUES('correction-2','real-shop','real-item',-3,'damage')")
assert db.execute("SELECT stock_qty FROM commerce_products WHERE id='real-item'").fetchone() == (7,)
for bad in [
    ("bad-negative","real-shop","real-item",-8,"damage"),
    ("bad-store","demo-shop","real-item",1,"restock"),
    ("bad-limit","real-shop","real-item",1000001,"restock")
]:
    try:
        db.execute("INSERT INTO commerce_inventory_corrections(id,store_id,product_id,delta,reason) VALUES(?,?,?,?,?)",bad)
        assert False, "Invalid inventory correction unexpectedly succeeded"
    except sqlite3.IntegrityError:
        pass
assert db.execute("SELECT stock_qty FROM commerce_products WHERE id='real-item'").fetchone() == (7,)
events=[row[0] for row in db.execute("SELECT new_status FROM commerce_order_events WHERE order_id='real-order' ORDER BY created_at,id")]
assert sorted(events)==["cancelled","placed"], events
try:
    db.execute("DELETE FROM commerce_order_events WHERE order_id='real-order'")
    assert False, "Immutable order event deletion unexpectedly succeeded"
except sqlite3.IntegrityError:
    pass
assert db.execute("SELECT COUNT(*) FROM commerce_order_events WHERE order_id='demo-order'").fetchone()==(1,)
# v8: the same merchant may not create another order with the same
# idempotency key; another merchant has a separate namespace for that key.
db.execute("UPDATE commerce_orders SET checkout_request_id='safe-key' WHERE id='real-order'")
db.execute("UPDATE commerce_orders SET checkout_request_id='safe-key' WHERE id='demo-order'")
try:
    db.execute("""INSERT INTO commerce_orders(id,store_id,order_number,access_token,
      subtotal_bdt,total_bdt,checkout_request_id)
      VALUES('duplicate','real-shop','COD-DUPLICATE','DUPLICATE-TOKEN',0,0,'safe-key')""")
    assert False, "Duplicate checkout accepted"
except sqlite3.IntegrityError:
    pass
assert db.execute("SELECT COUNT(*) FROM commerce_orders WHERE store_id='real-shop'").fetchone() == (1,)
assert db.execute("SELECT stock_qty FROM commerce_products WHERE id='real-item'").fetchone() == (7,)

# v9: store metadata and merchant product presentation persist independently.
db.execute("UPDATE commerce_products SET description='Soft cotton everyday socks',image_url='https://example.org/socks.jpg',is_featured=1 WHERE id='real-item'")
assert db.execute("SELECT description,image_url,is_featured FROM commerce_products WHERE id='real-item'").fetchone()==(
    'Soft cotton everyday socks','https://example.org/socks.jpg',1)
assert db.execute("SELECT description FROM commerce_products WHERE id='demo-item'").fetchone()==('',)
db.execute("""UPDATE commerce_stores SET cover_image_url='https://example.org/banner.webp',
 logo_image_url='https://example.org/logo.webp',
 public_phone='01712345678',public_address='Rajshahi Bangladesh' WHERE id='real-shop'""")
assert db.execute("SELECT logo_image_url,cover_image_url,public_phone FROM commerce_stores WHERE id='real-shop'").fetchone() == (
    "https://example.org/logo.webp","https://example.org/banner.webp","01712345678")
assert db.execute("SELECT logo_image_url FROM commerce_stores WHERE id='demo-shop'").fetchone() == (None,)
# v11: merchant controls transparent store copy, without modifying sales data.
db.execute("""UPDATE commerce_stores SET
 announcement_text='New arrivals today',
 about_text='We sell quality socks',
 delivery_policy_text='Dispatch subject to merchant confirmation',
 return_policy_text='Contact merchant for returns'
 WHERE id='real-shop'""")
assert db.execute("SELECT announcement_text,about_text,delivery_policy_text,return_policy_text FROM commerce_stores WHERE id='real-shop'").fetchone() == (
 'New arrivals today','We sell quality socks','Dispatch subject to merchant confirmation','Contact merchant for returns')
assert db.execute("SELECT announcement_text FROM commerce_stores WHERE id='demo-shop'").fetchone() == ('',)
# v12: user-authored catalog images and Q&A are strictly per store / product.
db.execute("""UPDATE commerce_products SET gallery_json='["https://example.org/a.webp","https://example.org/b.webp"]' WHERE id='real-item'""")
assert db.execute("SELECT gallery_json FROM commerce_products WHERE id='real-item'").fetchone() == (
 '["https://example.org/a.webp","https://example.org/b.webp"]',)
db.execute("""UPDATE commerce_stores SET faq_json='[{"question":"Do you deliver?","answer":"Please contact us."}]' WHERE id='real-shop'""")
assert db.execute("SELECT faq_json FROM commerce_stores WHERE id='real-shop'").fetchone() == (
 '[{"question":"Do you deliver?","answer":"Please contact us."}]',)
assert db.execute("SELECT gallery_json FROM commerce_products WHERE id='demo-item'").fetchone() == ('[]',)
assert db.execute("SELECT faq_json FROM commerce_stores WHERE id='demo-shop'").fetchone() == ('[]',)
for sql in [
 "UPDATE commerce_stores SET faq_json='broken' WHERE id='real-shop'",
 "UPDATE commerce_products SET gallery_json='{}' WHERE id='real-item'"
]:
 try:
  db.execute(sql)
  assert False,"Invalid JSON was accepted"
 except sqlite3.IntegrityError:
  pass
print("D1 migrations 0001-0012 verified; audit, tenancy, reorder thresholds and atomic inventory corrections OK")

