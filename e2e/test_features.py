"""The everyday features, one journey each, through a real browser."""

import re
from datetime import datetime, timedelta, timezone

from playwright.sync_api import expect

from .conftest import PASSWORD, WEB, bn, call, in_days, sign_in
from .test_panels import no_js_errors, seed_stock


def now():
    return datetime.now(timezone.utc).isoformat()


def api(shop, method, path, body=None):
    return call(method, f"/api/app{path}", body, shop["token"], shop["org"])


def sell(shop, branch, product, qty, invoice, customer=None, paid=None, method="cash", price=15, days_ago=0):
    total = price * qty
    paid = total if paid is None else paid
    sold_at = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat() if days_ago else now()
    return api(shop, "POST", "/sales", {
        "branch_id": branch, "invoice_number": invoice, "sold_at": sold_at, "customer_id": customer,
        "items": [{"product_id": product, "quantity": str(qty)}],
        "payments": [{"method": method, "amount": str(paid)}] if paid else []})


def test_the_morning_brief_and_the_bell_tell_the_owner_what_needs_doing(shop, new_session):
    branch, product = seed_stock(shop)
    customer = api(shop, "POST", "/customers", {"code": "C-9", "display_name": "রফিক মিয়া"})
    api(shop, "PATCH" if False else "POST", "/inventory/adjust", {"branch_id": branch, "product_id": product, "quantity_delta": "-46", "reason": "test"})
    sell(shop, branch, product, 1, "INV-B1", customer=customer["id"], paid=0)       # ৳15 owed; stock is now 3
    api(shop, "POST", "/products", {"sku": "LOW-1", "name": "Low item", "selling_price": "5", "cost_price": "3", "reorder_level": "10"})

    s = new_session()
    sign_in(s, shop["email"])
    page = s.page
    page.goto(f"{WEB}/#/")
    expect(page.get_by_text("আজকের সংক্ষেপ")).to_be_visible()
    expect(page.locator(".brief__col", has_text="কিনতে হবে")).to_be_visible()
    expect(page.locator(".brief__col", has_text="বাকি আদায়")).to_contain_text("রফিক মিয়া")
    expect(page.get_by_role("link", name="WhatsApp-এ পাঠান")).to_have_attribute("href", re.compile(r"^https://wa\.me/\?text="))

    # The bell carries the same warnings from anywhere in the app.
    page.goto(f"{WEB}/#/products")
    bell = page.locator("aside.sidebar .bell")
    expect(bell).to_have_attribute("aria-label", re.compile("সতর্কতা"))
    bell.click()
    dialog = page.locator("dialog[open]")
    expect(dialog).to_contain_text("স্টক")
    dialog.get_by_role("link").first.click()
    expect(page).to_have_url(re.compile(r"#/(inventory|directory|expiry)"))
    no_js_errors(s)


def test_closing_the_cash_drawer_at_night(shop, new_session):
    branch, product = seed_stock(shop)
    sell(shop, branch, product, 4, "INV-C1")                                       # ৳60 cash
    sell(shop, branch, product, 2, "INV-C2", method="bkash")                       # not in the drawer
    api(shop, "POST", "/expenses", {"category": "চা-নাস্তা", "amount": "20", "payment_method": "cash", "incurred_at": now()})

    s = new_session()
    sign_in(s, shop["email"])
    page = s.page
    page.goto(f"{WEB}/#/cash")
    expect(page.locator(".cash-lines .total")).to_contain_text(bn(40))            # 60 - 20; bKash left out
    page.get_by_label("ড্রয়ারে এখন কত টাকা আছে?").fill("35")
    expect(page.locator(".variance")).to_contain_text("কম আছে")
    expect(page.get_by_role("button", name="দিনের হিসাব বন্ধ করুন")).to_be_disabled()   # a reason is required
    page.get_by_label("গরমিলের কারণ").fill("খুচরা দিতে নিজের টাকা গেছে")
    page.get_by_role("button", name="দিনের হিসাব বন্ধ করুন").click()
    expect(page.get_by_text("দিনের হিসাব বন্ধ হয়েছে")).to_be_visible()
    expect(page.get_by_role("heading", name="বন্ধ করা হয়েছে")).to_be_visible()
    expect(page.get_by_role("row", name=re.compile("খুচরা দিতে"))).to_be_visible()   # in the history
    no_js_errors(s)


def test_finding_an_invoice_and_reading_a_customer(shop, new_session):
    branch, product = seed_stock(shop)
    customer = api(shop, "POST", "/customers", {"code": "C-7", "display_name": "সালমা বেগম", "marketing_consent": True})
    sell(shop, branch, product, 3, "INV-H1", customer=customer["id"], paid=0)
    sell(shop, branch, product, 1, "INV-H2")

    s = new_session()
    sign_in(s, shop["email"])
    page = s.page
    page.goto(f"{WEB}/#/sales-history")
    expect(page.get_by_role("row", name=re.compile("INV-H"))).to_have_count(2)
    page.get_by_label("চালান নম্বর").fill("H1")
    expect(page.get_by_role("row", name=re.compile("INV-H"))).to_have_count(1)
    page.get_by_role("button", name="INV-H1").click()
    expect(page.locator(".receipt")).to_contain_text(bn(45))
    page.locator("dialog[open]").locator("footer").get_by_role("button", name="বন্ধ করুন").click()

    page.goto(f"{WEB}/#/directory")
    page.get_by_role("button", name="সালমা বেগম", exact=True).click()
    dialog = page.locator("dialog[open]")
    expect(dialog).to_contain_text("বাকি আছে")
    expect(dialog.locator(".reminder")).to_contain_text("আপনার ৳ ৪৫ বাকি আছে")
    dialog.get_by_role("button", name="বাকি আদায় করুন").click()
    page.locator("dialog[open]").locator("footer").get_by_role("button", name="আদায় নিশ্চিত করুন").click()
    expect(page.get_by_text("আদায় হয়েছে")).to_be_visible()
    no_js_errors(s)


def test_a_report_downloads_as_a_csv_that_excel_can_read(shop, new_session):
    branch, product = seed_stock(shop)
    sell(shop, branch, product, 2, "INV-R1")
    s = new_session()
    sign_in(s, shop["email"])
    page = s.page
    page.goto(f"{WEB}/#/reports")
    with page.expect_download() as download:
        page.locator(".ui-card", has_text="বিক্রির রিপোর্ট").get_by_role("button", name="Excel (CSV)").click()
    path = download.value.path()
    raw = open(path, "rb").read()
    assert raw.startswith(b"\xef\xbb\xbf"), "needs a byte-order mark so Excel reads Bangla"
    text = raw.decode("utf-8-sig")
    assert "চালান" in text.splitlines()[0] and "INV-R1" in text
    expect(page.get_by_text("নামানো হয়েছে")).to_be_visible()

    page.get_by_role("button", name="সারাংশ তৈরি করুন").click()
    expect(page.locator(".summary")).to_contain_text("নিট বিক্রি")
    no_js_errors(s)


def test_moving_stock_between_two_branches(shop, new_session):
    branch, product = seed_stock(shop)
    second = api(shop, "POST", "/branches", {"code": "MIRPUR", "name": "মিরপুর শাখা"})["id"]
    s = new_session()
    sign_in(s, shop["email"])
    page = s.page
    page.goto(f"{WEB}/#/inventory")
    page.get_by_role("row", name=re.compile("Napa")).get_by_role("button", name="স্থানান্তর").click()
    dialog = page.locator("dialog[open]")
    dialog.get_by_label("কোন শাখায় পাঠাবেন?").select_option(label="মিরপুর শাখা")
    dialog.get_by_label("কত ইউনিট?").fill("12")
    dialog.locator("footer").get_by_role("button", name="স্থানান্তর করুন").click()
    expect(page.get_by_text("অন্য শাখায় গেছে")).to_be_visible()
    there = api(shop, "GET", f"/inventory?branch_id={second}")
    here = api(shop, "GET", f"/inventory?branch_id={branch}")
    assert [float(r["quantity"]) for r in there if r["product_id"] == product] == [12.0]
    assert [float(r["quantity"]) for r in here if r["product_id"] == product] == [38.0]
    no_js_errors(s)


def test_selling_with_the_internet_down_and_syncing_exactly_once_when_it_returns(shop, new_session):
    branch, product = seed_stock(shop)
    s = new_session()
    sign_in(s, shop["email"])
    page = s.page
    page.goto(f"{WEB}/#/sales")
    expect(page.get_by_role("button", name=re.compile("Napa"))).to_be_visible()      # catalogue loaded (and cached)

    s.context.set_offline(True)
    page.get_by_role("button", name=re.compile("Napa")).first.click()
    page.get_by_role("button", name=re.compile("বিক্রি সম্পন্ন করুন")).click()
    expect(page.get_by_role("heading", name="বিক্রি সম্পন্ন হয়েছে")).to_be_visible()
    expect(page.locator(".receipt")).to_contain_text("অফলাইনে জমা")
    page.get_by_role("button", name="নতুন বিক্রি").click()
    expect(page.locator(".offline-bar")).to_contain_text(f"{bn(1)}টি বিক্রি")
    assert len(api(shop, "GET", "/sales")) == 0                                       # nothing reached the server yet

    s.context.set_offline(False)                                                     # connection is back
    expect(page.locator(".offline-bar")).to_have_count(0, timeout=30000)
    sales = api(shop, "GET", "/sales")
    assert len(sales) == 1, "the bill must arrive exactly once"
    stock = [float(r["quantity"]) for r in api(shop, "GET", f"/inventory?branch_id={branch}") if r["product_id"] == product]
    assert stock == [49.0]
    no_js_errors(s)


def test_a_shop_loads_its_products_and_opening_stock_from_a_file(shop, new_session):
    branch = api(shop, "GET", "/branches")[0]["id"]
    s = new_session()
    sign_in(s, shop["email"])
    page = s.page
    page.goto(f"{WEB}/#/import")

    products = "পণ্যের কোড,পণ্যের নাম,বিক্রয়মূল্য,ক্রয়মূল্য\nA-1,নাপা,১৫,১০\nA-2,ভুল দামের পণ্য,দাম নেই,৫\nA-3,ওরস্যালাইন,১০,৭\n"
    page.locator("input[type=file]").set_input_files({"name": "products.csv", "mimeType": "text/csv", "buffer": products.encode("utf-8-sig")})
    # Bangla headers are recognised without the owner mapping anything.
    expect(page.get_by_label("পণ্যের কোড")).to_have_value("পণ্যের কোড")
    expect(page.get_by_label("বিক্রয়মূল্য")).to_have_value("বিক্রয়মূল্য")
    page.get_by_role("button", name=re.compile("সারি জমা করুন")).click()
    summary = page.locator(".summary")
    expect(summary.locator("div", has_text="নতুন যোগ")).to_contain_text(bn(2))
    expect(summary.locator("div", has_text="ভুল সারি")).to_contain_text(bn(1))
    expect(page.get_by_role("row", name=re.compile("লাইন ৩"))).to_be_visible()     # the bad row, by its line in the file
    assert {p["sku"] for p in api(shop, "GET", "/products")} == {"A-1", "A-3"}

    page.get_by_role("button", name="আরেকটি ফাইল").click()
    page.get_by_role("tab", name="শুরুর স্টক").click()
    page.locator("input[type=file]").set_input_files({"name": "stock.csv", "mimeType": "text/csv", "buffer": b"sku,quantity\nA-1,120\nZ-9,5\n"})
    page.get_by_role("button", name=re.compile("সারি জমা করুন")).click()
    expect(page.locator(".summary div", has_text="নতুন যোগ")).to_contain_text(bn(1))
    expect(page.get_by_role("row", name=re.compile("লাইন ৩"))).to_be_visible()      # unknown SKU Z-9
    stock = {r["sku"]: r["quantity"] for r in api(shop, "GET", f"/inventory?branch_id={branch}")}
    assert float(stock["A-1"]) == 120
    no_js_errors(s)


def test_the_shop_address_and_footer_appear_on_the_receipt(shop, new_session):
    branch, product = seed_stock(shop)
    sell(shop, branch, product, 2, "INV-P1")
    s = new_session()
    sign_in(s, shop["email"])
    page = s.page
    page.goto(f"{WEB}/#/setup")
    page.get_by_label("দোকানের ঠিকানা").fill("মিরপুর-১০, ঢাকা")
    page.get_by_label("ফোন নম্বর").fill("01712345678")
    page.get_by_label("VAT / BIN নম্বর").fill("BIN-4455")
    page.get_by_label("রসিদের শেষের লেখা").fill("আবার আসবেন")
    page.locator(".ui-card", has_text="রসিদের তথ্য").get_by_role("button", name="সংরক্ষণ করুন").click()
    expect(page.get_by_text("দোকানের তথ্য সংরক্ষিত হয়েছে")).to_be_visible()

    page.goto(f"{WEB}/#/sales-history")
    page.get_by_role("button", name="INV-P1").click()
    receipt = page.locator(".receipt")
    for text in ("মিরপুর-১০, ঢাকা", "01712345678", "BIN-4455", "আবার আসবেন"):
        expect(receipt).to_contain_text(text)
    no_js_errors(s)


def test_what_to_buy_shows_its_working_and_orders_in_one_step(shop, new_session):
    branch, product = seed_stock(shop)
    sell(shop, branch, product, 30, "INV-W1")                                       # ~1.07 a day, 20 left
    s = new_session()
    sign_in(s, shop["email"])
    page = s.page
    page.goto(f"{WEB}/#/reorder")
    row = page.get_by_role("row", name=re.compile("Napa"))
    expect(row).to_be_visible()
    expect(row).to_contain_text("দৈনিক")                                           # the arithmetic is shown
    expect(row.get_by_label("Napa কেনা দাম")).to_have_value("10")                   # pre-filled from the product
    order_button = page.get_by_role("button", name=re.compile("পণ্যের অর্ডার দিন"))
    expect(order_button).to_be_disabled()                                           # no supplier chosen yet
    row.get_by_label("Napa সাপ্লায়ার").select_option(label="Square Distributor")
    order_button.click()
    page.locator(".confirm-box").get_by_role("button", name="নিশ্চিত করুন").click()
    expect(page.get_by_text("অর্ডার তৈরি হয়েছে").first).to_be_visible()
    orders = api(shop, "GET", "/purchases")
    assert len(orders) == 1 and orders[0]["status"] == "ordered" and float(orders[0]["items"][0]["quantity"]) >= 1
    expect(page.get_by_role("heading", name="এখন কিছু কেনার দরকার নেই")).to_be_visible()   # stock on order now counts, so it is not suggested twice
    no_js_errors(s)


def test_voiding_a_wrong_invoice_puts_the_stock_back(shop, new_session):
    branch, product = seed_stock(shop)
    sale = sell(shop, branch, product, 4, "INV-V1")
    s = new_session()
    sign_in(s, shop["email"])
    page = s.page
    page.goto(f"{WEB}/#/sales-history")
    page.get_by_role("button", name="INV-V1").click()
    dialog = page.locator("dialog[open]")
    dialog.get_by_role("button", name="চালান বাতিল").click()
    confirm = page.locator("dialog[open]").last
    expect(confirm.get_by_role("button", name="হ্যাঁ, বাতিল করুন")).to_be_disabled()      # a reason is required
    confirm.get_by_label("বাতিলের কারণ").fill("ভুল পণ্য স্ক্যান হয়েছিল")
    confirm.get_by_role("button", name="হ্যাঁ, বাতিল করুন").click()
    expect(page.get_by_text("বাতিল হয়েছে").first).to_be_visible()
    expect(page.get_by_role("row", name=re.compile("INV-V1")).get_by_text("বাতিল")).to_be_visible()
    stock = {r["sku"]: float(r["quantity"]) for r in api(shop, "GET", f"/inventory?branch_id={branch}")}
    assert stock["P-1"] == 50
    no_js_errors(s)


def test_edit_a_product_and_customer_then_sell_at_the_wholesale_price_on_hold(shop, new_session):
    branch, product = seed_stock(shop)
    api(shop, "POST", "/customers", {"code": "WS-1", "display_name": "পাইকার করিম"})
    s = new_session()
    sign_in(s, shop["email"])
    page = s.page

    page.goto(f"{WEB}/#/products")
    page.get_by_role("button", name="Napa সম্পাদনা").click()
    page.get_by_label("পাইকারি দাম (৳)").fill("12")
    page.locator("dialog[open]").get_by_role("button", name="সংরক্ষণ করুন").click()
    expect(page.get_by_text("পণ্যের তথ্য সংরক্ষিত হয়েছে")).to_be_visible()
    assert float(api(shop, "GET", "/products")[0]["wholesale_price"]) == 12

    page.goto(f"{WEB}/#/directory")
    page.get_by_role("button", name="পাইকার করিম সম্পাদনা").click()
    dialog = page.locator("dialog[open]")
    dialog.get_by_label("বাকির সীমা (৳)").fill("10")
    dialog.get_by_label("দামের ধরন").select_option("wholesale")
    dialog.get_by_role("button", name="সংরক্ষণ করুন").click()
    expect(page.get_by_text("কাস্টমারের তথ্য সংরক্ষিত হয়েছে")).to_be_visible()
    customer = api(shop, "GET", "/customers")[0]
    assert customer["price_tier"] == "wholesale" and float(customer["credit_limit"]) == 10

    page.goto(f"{WEB}/#/sales")
    page.get_by_placeholder("পণ্যের নাম, SKU বা বারকোড লিখুন…").fill("Napa")
    page.get_by_role("button", name=re.compile("Napa")).first.click()
    expect(page.locator(".pos-line__total")).to_contain_text(bn(15))                 # retail until a customer is chosen
    page.get_by_label("কাস্টমার", exact=True).select_option(label="পাইকার করিম")
    expect(page.locator(".pos-line__total")).to_contain_text(bn(12))                 # repriced to wholesale

    page.get_by_label("ক্রেতা দিয়েছেন (৳)").fill("0")                               # all on baki: 12 > limit 10
    expect(page.get_by_text("বাকির সীমা ছাড়িয়ে যাবে").first).to_be_visible()
    expect(page.get_by_role("button", name=re.compile("বিক্রি সম্পন্ন|বিক্রি করুন|সম্পন্ন"))).to_be_disabled()

    page.get_by_role("button", name="বিল ধরে রাখুন").click()                          # park the bill, serve someone else
    expect(page.locator(".pos-line__total")).to_have_count(0)
    held = page.get_by_role("status", name="ধরে রাখা বিল")
    expect(held).to_be_visible()
    held.get_by_role("button", name=re.compile("টি পণ্য")).click()
    expect(page.locator(".pos-line__total")).to_contain_text(bn(12))
    no_js_errors(s)


def test_the_baki_ageing_shows_who_has_owed_longest(shop, new_session):
    branch, product = seed_stock(shop)
    old = api(shop, "POST", "/customers", {"code": "OLD-1", "display_name": "পুরোনো বাকিদার"})
    from datetime import timedelta
    api(shop, "POST", "/sales", {"branch_id": branch, "invoice_number": "INV-OLD", "sold_at": (datetime.now(timezone.utc) - timedelta(days=95)).isoformat(),
                                 "customer_id": old["id"], "items": [{"product_id": product, "quantity": "2"}], "payments": []})
    sell(shop, branch, product, 1, "INV-NEW", customer=old["id"], paid=0)
    s = new_session()
    sign_in(s, shop["email"])
    page = s.page
    page.goto(f"{WEB}/#/accounts")
    page.get_by_role("tab", name=re.compile("কাস্টমারের বাকি")).click()
    card = page.locator(".ui-card", has_text="বাকির বয়স")
    expect(card).to_be_visible()
    expect(card.locator(".ui-stat", has_text="৯০+ দিন")).to_contain_text(bn(30))       # 2 x 15 owed for 95 days
    expect(card.locator(".ui-stat", has_text="০–৩০ দিন")).to_contain_text(bn(15))
    expect(card.get_by_role("row", name=re.compile("পুরোনো বাকিদার"))).to_contain_text("৯৫")
    no_js_errors(s)


def test_the_cash_locked_meter_and_insights_page_show_real_arithmetic(shop, new_session):
    branch, product = seed_stock(shop)
    # Make P-1 look dead: sell it, but 90 days ago, with nothing since.
    sell(shop, branch, product, 2, "INV-OLD", days_ago=90)
    big = api(shop, "POST", "/products", {"sku": "BIG-1", "name": "Big seller", "selling_price": "100", "cost_price": "40"})
    api(shop, "POST", "/inventory/adjust", {"branch_id": branch, "product_id": big["id"], "quantity_delta": "50", "reason": "open"})
    sell(shop, branch, big["id"], 20, "INV-BIG", price=100)
    customer = api(shop, "POST", "/customers", {"code": "C-OLD", "display_name": "পুরোনো বাকিদার"})
    sell(shop, branch, product, 1, "INV-DUE", customer=customer["id"], paid=0, days_ago=95)
    supplier = api(shop, "POST", "/suppliers", {"code": "S1", "name": "Square"})
    for cost, days_ago in [("10", 60), ("12", 3)]:
        api(shop, "POST", "/purchases", {"branch_id": branch, "supplier_id": supplier["id"], "order_number": f"PO-{days_ago}",
                                         "ordered_at": (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat(),
                                         "items": [{"product_id": big["id"], "quantity": "5", "unit_cost": cost}]})

    s = new_session()
    sign_in(s, shop["email"])
    page = s.page
    page.goto(f"{WEB}/#/")
    meter = page.locator(".cash-locked")
    expect(meter).to_be_visible()
    expect(meter).to_contain_text("অবিক্রীত পুরোনো স্টক")
    expect(meter).to_contain_text("পুরোনো বাকি")

    page.goto(f"{WEB}/#/insights")
    row = page.get_by_role("row", name=re.compile("Big seller"))
    expect(row).to_be_visible()
    expect(row.locator(".abc-badge")).to_have_text("A")
    page.get_by_role("tab", name=re.compile("^অবিক্রীত পুরোনো স্টক")).click()
    expect(page.get_by_role("row", name=re.compile("Napa"))).to_be_visible()
    expect(page.get_by_role("row", name=re.compile("Big seller"))).to_be_hidden()

    page.get_by_role("tab", name=re.compile("দামের পরিবর্তন")).click()
    price_row = page.get_by_role("row", name=re.compile("Big seller"))
    expect(price_row).to_contain_text("Square")
    expect(price_row).to_contain_text(f"+{bn(20)}%")
    no_js_errors(s)


def test_the_accounting_page_shows_a_balanced_trial_balance_and_correct_pnl(shop, new_session):
    branch, product = seed_stock(shop)
    sell(shop, branch, product, 4, "INV-ACC1")                                   # ৳60 revenue, cost ৳40
    api(shop, "POST", "/expenses", {"category": "ভাড়া", "amount": "20", "payment_method": "cash", "incurred_at": now()})

    s = new_session()
    sign_in(s, shop["email"])
    page = s.page
    page.goto(f"{WEB}/#/accounting")
    expect(page.get_by_text("হিসাব মিলেছে।")).to_be_visible()
    row = page.get_by_role("row", name=re.compile("^নগদ "))
    expect(row).to_be_visible()

    page.get_by_role("tab", name="লাভ-ক্ষতি (P&L)").click()
    page.get_by_label("থেকে").fill(in_days(-1))
    stats = page.locator(".ui-stats")
    expect(stats).to_contain_text(bn(60))       # revenue
    expect(stats).to_contain_text(bn(20))       # operating expenses
    no_js_errors(s)


def test_a_large_expense_waits_for_the_owner_and_shows_up_in_the_inbox(shop, new_session):
    from .test_panels import invite
    manager_email = invite(shop, "manager")

    mgr_session = new_session()
    sign_in(mgr_session, manager_email)
    page = mgr_session.page
    page.goto(f"{WEB}/#/accounts")
    page.get_by_role("button", name="নতুন খরচ").click()
    dialog = page.locator("dialog[open]")
    dialog.get_by_label("খরচের ধরন").select_option(label="দোকান ভাড়া")
    dialog.get_by_label("টাকা").fill("6000")
    dialog.get_by_role("button", name="খরচ লিখুন").click()
    expect(page.get_by_text("অনুমোদনের অপেক্ষায়")).to_be_visible()
    no_js_errors(mgr_session)

    owner_session = new_session()
    sign_in(owner_session, shop["email"])
    page = owner_session.page
    page.goto(f"{WEB}/#/approvals")
    row = page.get_by_role("row", name=re.compile("৬,০০০|6,000|6000"))
    expect(row).to_be_visible()
    expect(row).to_contain_text("manager user")
    row.get_by_role("button", name="অনুমোদন").click()
    page.locator("dialog[open]").get_by_role("button", name="হ্যাঁ, অনুমোদন করুন").click()
    expect(page.get_by_text("অনুমোদন করা হয়েছে")).to_be_visible()
    expect(page.get_by_role("row", name=re.compile("৬,০০০|6,000|6000"))).to_be_hidden()   # no longer pending
    no_js_errors(owner_session)


def test_a_cashier_needs_a_managers_password_for_a_big_discount(shop, new_session):
    from .test_panels import invite
    branch, product = seed_stock(shop)
    manager_email = invite(shop, "manager")
    cashier_email = invite(shop, "cashier")

    s = new_session()
    sign_in(s, cashier_email)
    page = s.page
    page.goto(f"{WEB}/#/sales")
    page.get_by_placeholder("পণ্যের নাম, SKU বা বারকোড লিখুন…").fill("Napa")
    page.get_by_role("button", name=re.compile("Napa")).first.click()
    page.get_by_label(re.compile("Napa-এর ছাড়")).fill("10")   # ৳10 off a ৳15 line = 67% discount
    page.get_by_role("button", name=re.compile("বিক্রি সম্পন্ন")).click()
    expect(page.get_by_text("বড় ছাড়ের জন্য অনুমোদন লাগবে")).to_be_visible()

    dialog = page.locator("dialog[open]")
    dialog.get_by_label("অনুমোদনকারীর ইমেইল").fill(manager_email)
    dialog.get_by_label("পাসওয়ার্ড").fill("wrong")
    dialog.get_by_role("button", name="অনুমোদন করে বিক্রি সম্পন্ন করুন").click()
    expect(page.get_by_text("মানানসই কর্মী পাওয়া যায়নি")).to_be_visible()

    dialog.get_by_label("পাসওয়ার্ড").fill(PASSWORD)
    dialog.get_by_role("button", name="অনুমোদন করে বিক্রি সম্পন্ন করুন").click()
    expect(page.get_by_text("বিক্রি সম্পন্ন হয়েছে")).to_be_visible()
    no_js_errors(s)


def test_a_large_cash_refund_needs_a_managers_password(shop, new_session):
    from .test_panels import invite
    branch, product = seed_stock(shop)
    manager_email = invite(shop, "manager")
    cashier_email = invite(shop, "cashier")
    api(shop, "POST", "/inventory/adjust", {"branch_id": branch, "product_id": product, "quantity_delta": "50", "reason": "more stock"})
    # A fully-paid ৳1500 sale so the whole thing is refundable in cash.
    sell(shop, branch, product, 100, "INV-REF1")
    line = api(shop, "GET", "/sales")[0]["items"][0]

    s = new_session()
    sign_in(s, cashier_email)   # a cashier ranks below the manager the rule requires
    page = s.page
    page.goto(f"{WEB}/#/returns")
    page.get_by_role("button", name="নতুন রিটার্ন").click()
    dialog = page.locator("dialog[open]")
    dialog.get_by_label("কত ফেরত এসেছে?").fill("100")
    dialog.get_by_role("button", name="রিটার্ন নিশ্চিত করুন").click()
    expect(page.get_by_text("বড় টাকা ফেরতের জন্য অনুমোদন লাগবে")).to_be_visible()

    dialog2 = page.locator("dialog[open]")
    dialog2.get_by_label("অনুমোদনকারীর ইমেইল").fill(manager_email)
    dialog2.get_by_label("পাসওয়ার্ড").fill(PASSWORD)
    dialog2.get_by_role("button", name="অনুমোদন করে ফেরত সম্পন্ন করুন").click()
    expect(page.get_by_text("রিটার্ন সম্পন্ন হয়েছে")).to_be_visible()
    no_js_errors(s)


def test_a_large_purchase_order_by_a_manager_waits_for_the_owner(shop, new_session):
    from .test_panels import invite
    branch, product = seed_stock(shop)
    api(shop, "POST", "/suppliers", {"code": "S-PO", "name": "Square Distributor"})
    manager_email = invite(shop, "manager")

    mgr_session = new_session()
    sign_in(mgr_session, manager_email)
    page = mgr_session.page
    page.goto(f"{WEB}/#/purchases")
    page.get_by_role("button", name="নতুন ক্রয় অর্ডার").click()
    dialog = page.locator("dialog[open]")
    dialog.get_by_label("সাপ্লায়ার").select_option(label="Square Distributor")
    dialog.get_by_label("পণ্য").select_option(label="Napa")
    dialog.get_by_label("পরিমাণ").fill("3000")
    dialog.get_by_label("ক্রয়মূল্য (৳)").fill("10")               # ৳30,000, over the ৳20,000/owner default
    dialog.get_by_role("button", name="অর্ডার দিন").click()
    expect(page.get_by_text("অনুমোদনের অপেক্ষায়")).to_be_visible()
    no_js_errors(mgr_session)

    owner_session = new_session()
    sign_in(owner_session, shop["email"])
    page = owner_session.page
    page.goto(f"{WEB}/#/approvals")
    row = page.get_by_role("row", name=re.compile("৩০,০০০|30,000"))
    expect(row).to_be_visible()
    row.get_by_role("button", name="অনুমোদন").click()
    page.locator("dialog[open]").get_by_role("button", name="হ্যাঁ, অনুমোদন করুন").click()
    expect(page.get_by_text("অনুমোদন করা হয়েছে")).to_be_visible()

    page.goto(f"{WEB}/#/purchases")
    expect(page.get_by_text("৩০,০০০", exact=False).first).to_be_visible()
    no_js_errors(owner_session)


def test_a_stock_count_finds_and_fixes_a_shelf_shortage(shop, new_session):
    branch, product = seed_stock(shop)   # Napa, 50 units
    s = new_session()
    sign_in(s, shop["email"])
    page = s.page
    page.goto(f"{WEB}/#/stock-count")
    page.get_by_role("button", name="নতুন গণনা শুরু করুন").click()
    expect(page.get_by_text("চলমান গণনা")).to_be_visible()
    row = page.get_by_role("row", name=re.compile("Napa"))
    expect(row).to_contain_text(bn(50))
    row.get_by_label("Napa গণনা").fill("47")
    row.get_by_label("Napa গণনা").blur()
    expect(row.get_by_text("সংরক্ষিত")).to_be_visible()

    page.get_by_role("button", name=re.compile("গণনা শেষ করুন")).click()
    dialog = page.locator(".confirm-box")
    expect(dialog).to_contain_text("সব গরমিল স্টকে প্রয়োগ হবে")   # only one product was seeded, so nothing is left uncounted
    dialog.get_by_role("button", name="নিশ্চিত করুন").click()
    expect(page.get_by_text("গণনা শেষ।")).to_be_visible()

    stock = {r["sku"]: float(r["quantity"]) for r in api(shop, "GET", f"/inventory?branch_id={branch}")}
    assert stock["P-1"] == 47
    no_js_errors(s)
