"""Verify fresh D1 v1-v6 schema and stock auditing with stdlib SQLite.

Runs in CI against an isolated in-memory database, never live Cloudflare data.
"""
from pathlib import Path
import sqlite3

migrations = Path(__file__).resolve().parents[1] / "migrations"
db = sqlite3.connect(":memory:")
db.execute("PRAGMA foreign_keys = ON")
for script in sorted(migrations.glob("*.sql")):
    db.executescript(script.read_text(encoding="utf-8"))
assert db.execute("SELECT value FROM commerce_meta WHERE key='schema_version'").fetchone() == ("6",)

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
print("D1 migrations 0001-0006 verified; real & demo stock audit and cancellation OK")
