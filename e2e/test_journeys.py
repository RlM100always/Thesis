"""User journeys, driven through a real browser against the real API.

Each test is a story a shop owner (or their cashier) actually lives, and asserts
what they would see, not what the code returns.
"""

import re
from datetime import datetime, timedelta, timezone

from playwright.sync_api import expect

from .conftest import PASSWORD, WEB, bn, call, in_days, sign_in


def open_page(session, hash_path):
    session.page.goto(f"{WEB}/#{hash_path}")


def no_js_errors(session):
    """Fail on any script error. The browser also logs every non-2xx response as
    "Failed to load resource"; those are expected here (a refused sale is a 409)
    and are asserted through what the user sees instead."""
    real = [e for e in session.errors if "Failed to load resource" not in e]
    assert real == [], real


def test_pharmacist_receives_sells_and_recalls_a_batch(shop, new_session):
    s = new_session()
    page = s.page
    sign_in(s, shop["email"])

    # 1. A medicine that tracks expiry.
    open_page(s, "/products")
    page.get_by_role("button", name="নতুন পণ্য").first.click()
    form = page.locator("#product-form")
    text_inputs = form.locator("input:not([type=number]):not([type=checkbox])")
    text_inputs.nth(0).fill("Napa 500")
    text_inputs.nth(1).fill("NAPA-500")
    form.locator("input[type=number]").nth(0).fill("15")   # selling price
    form.locator("input[type=number]").nth(1).fill("10")   # cost price
    form.locator("input[type=checkbox]").check()
    page.locator("dialog[open]").locator("footer").get_by_role("button", name="পণ্য যোগ করুন").click()
    expect(page.get_by_text("Napa 500").first).to_be_visible()
    expect(page.get_by_text("ট্র্যাক হচ্ছে")).to_be_visible()

    # 2. Order 20 strips, then receive them as two batches with different expiry.
    open_page(s, "/purchases")
    page.get_by_role("button", name="নতুন ক্রয় অর্ডার").first.click()
    po = page.locator("#po-form")
    po.locator("select").nth(0).select_option(label="Square Distributor")
    po.locator("select").nth(1).select_option(index=1)
    po.get_by_label("পরিমাণ").fill("20")
    page.locator("dialog[open]").locator("footer").get_by_role("button", name="অর্ডার দিন").click()
    expect(page.get_by_text("অপেক্ষায়").first).to_be_visible()

    page.get_by_role("button", name="মাল রিসিভ").first.click()
    dialog = page.locator("dialog[open]")
    dialog.get_by_label("কত এসেছে").nth(0).fill("5")
    dialog.get_by_label("ব্যাচ নম্বর").nth(0).fill("B-NEAR")
    dialog.get_by_label("মেয়াদ শেষ").nth(0).fill(in_days(20))
    dialog.get_by_role("button", name="আরেকটি ব্যাচ (ভিন্ন মেয়াদ)").click()
    dialog.get_by_label("কত এসেছে").nth(1).fill("15")
    dialog.get_by_label("ব্যাচ নম্বর").nth(1).fill("B-FAR")
    dialog.get_by_label("মেয়াদ শেষ").nth(1).fill(in_days(300))
    dialog.locator("footer").get_by_role("button", name="রিসিভ নিশ্চিত করুন").click()
    expect(page.get_by_text("মাল রিসিভ হয়েছে")).to_be_visible()
    expect(page.get_by_text("সব পেয়েছি").first).to_be_visible()

    # 3. The expiry board shows both batches and the money at risk (5 strips x ৳10).
    open_page(s, "/expiry")
    expect(page.get_by_role("row", name=re.compile("B-NEAR"))).to_be_visible()
    expect(page.get_by_role("row", name=re.compile("B-FAR"))).to_be_visible()
    expect(page.locator(".ui-stat").first).to_contain_text(f"৳ {bn(50)}")

    # 4. Sell 7 at the till: the 5 near-expiry strips must go first, then 2 of the far batch.
    open_page(s, "/sales")
    page.get_by_placeholder("পণ্যের নাম, SKU বা বারকোড লিখুন…").fill("Napa")
    page.get_by_role("button", name=re.compile("Napa 500")).first.click()
    page.locator("input[aria-label='Napa 500-এর পরিমাণ']").fill("7")
    page.get_by_role("button", name=re.compile("বিক্রি সম্পন্ন করুন")).click()
    expect(page.get_by_role("heading", name="বিক্রি সম্পন্ন হয়েছে")).to_be_visible()
    expect(page.locator(".receipt")).to_contain_text(bn(105))          # 7 x ৳15
    page.get_by_role("button", name="নতুন বিক্রি").click()

    open_page(s, "/expiry")
    expect(page.get_by_text("B-NEAR")).to_have_count(0)                 # emptied first
    expect(page.get_by_role("row", name=re.compile("B-FAR"))).to_contain_text(bn(13))

    # 5. Recall notice: block the batch. It can no longer be sold.
    page.get_by_role("row", name=re.compile("B-FAR")).get_by_role("button", name="বন্ধ করুন").click()
    dialog = page.locator("dialog[open]")
    dialog.get_by_label("কেন বন্ধ করছেন?").fill("রিকল নোটিশ এসেছে")
    dialog.locator("footer").get_by_role("button", name="বন্ধ করুন").click()
    expect(page.get_by_text("এটি আর বিক্রি হবে না")).to_be_visible()

    open_page(s, "/sales")
    page.get_by_placeholder("পণ্যের নাম, SKU বা বারকোড লিখুন…").fill("Napa")
    page.get_by_role("button", name=re.compile("Napa 500")).first.click()
    page.get_by_role("button", name=re.compile("বিক্রি সম্পন্ন করুন")).click()
    expect(page.get_by_text("মেয়াদোত্তীর্ণ বা বন্ধ")).to_be_visible()   # refused, in Bangla
    page.get_by_role("button", name="খালি করুন").click()

    # 6. Released: selling works again.
    open_page(s, "/expiry")
    page.get_by_role("row", name=re.compile("B-FAR")).get_by_role("button", name="চালু করুন").click()
    expect(page.get_by_text("আবার বিক্রির জন্য চালু হয়েছে")).to_be_visible()
    open_page(s, "/sales")
    page.get_by_placeholder("পণ্যের নাম, SKU বা বারকোড লিখুন…").fill("Napa")
    page.get_by_role("button", name=re.compile("Napa 500")).first.click()
    page.get_by_role("button", name=re.compile("বিক্রি সম্পন্ন করুন")).click()
    expect(page.get_by_role("heading", name="বিক্রি সম্পন্ন হয়েছে")).to_be_visible()
    page.get_by_role("button", name="নতুন বিক্রি").click()

    # 7. The books agree, and the trail says who did what.
    open_page(s, "/expiry")
    page.get_by_role("button", name="এখনই যাচাই করুন").click()
    expect(page.get_by_text("সব মিলেছে")).to_be_visible()
    open_page(s, "/audit")
    expect(page.get_by_text("ব্যাচ বন্ধ (বিক্রি হবে না)")).to_be_visible()
    expect(page.get_by_text("রহিম উদ্দিন").first).to_be_visible()
    no_js_errors(s)


def test_cashier_is_invited_signs_up_and_sees_only_the_till(shop, new_session):
    owner = new_session()
    sign_in(owner, shop["email"])
    open_page(owner, "/staff")
    page = owner.page
    form = page.locator("form").filter(has_text="কর্মী যোগ করুন").first
    form.get_by_label("নাম").fill("সুমাইয়া আক্তার")
    form.get_by_label("ইমেইল").fill(f"cashier-{shop['tag']}@example.com")
    form.get_by_role("button", name="কর্মী যোগ করুন").click()

    link = page.locator(".ui-copy input").input_value()
    assert "#/accept-invite?token=" in link
    expect(page.get_by_text("পাসওয়ার্ডের অপেক্ষায়")).to_be_visible()

    # The invited person opens the link on their own phone: no account yet.
    cashier = new_session()
    cashier.page.goto(link)
    cashier.page.get_by_label("নতুন পাসওয়ার্ড").fill("a fresh long password")
    cashier.page.get_by_label("পাসওয়ার্ড আবার লিখুন").fill("a fresh long password")
    cashier.page.get_by_role("button", name="শুরু করুন").click()
    cashier.page.get_by_text("ব্যবসা মোড").first.wait_for(timeout=20000)

    c = cashier.page
    expect(c).to_have_url(re.compile(r"#/sales"))                      # a cashier starts at the till
    nav = c.locator("aside.sidebar nav").first
    expect(nav.get_by_role("link", name="বিক্রি", exact=True)).to_be_visible()
    expect(nav.get_by_role("link", name="ড্যাশবোর্ড", exact=True)).to_have_count(0)  # profit is not for the till
    expect(nav.get_by_role("link", name="কর্মী ও ভূমিকা", exact=True)).to_have_count(0)
    expect(nav.get_by_role("link", name="হিসাব", exact=True)).to_have_count(0)
    c.goto(f"{WEB}/#/staff")
    expect(c.get_by_text("এই পাতাটি আপনার ভূমিকার জন্য নয়")).to_be_visible()

    # The owner now sees them as active.
    page.reload()
    expect(page.get_by_text("সুমাইয়া আক্তার")).to_be_visible()
    expect(page.get_by_text("পাসওয়ার্ডের অপেক্ষায়")).to_have_count(0)
    no_js_errors(owner)
    no_js_errors(cashier)


def test_the_phone_layout_works_end_to_end(shop, new_session):
    call("POST", "/api/app/products", {
        "sku": "ORS-1", "name": "Orsaline", "selling_price": "10", "cost_price": "6"}, shop["token"], shop["org"])
    branch = call("GET", "/api/app/branches", token=shop["token"], org=shop["org"])[0]["id"]
    product = call("GET", "/api/app/products", token=shop["token"], org=shop["org"])[0]["id"]
    call("POST", "/api/app/inventory/adjust", {
        "branch_id": branch, "product_id": product, "quantity_delta": "30", "reason": "opening stock"},
         shop["token"], shop["org"])

    s = new_session(390, 844)
    sign_in(s, shop["email"])
    page = s.page
    bottom = page.get_by_role("navigation", name="প্রধান মেনু")
    expect(bottom).to_be_visible()
    expect(page.locator("aside.sidebar").first).to_be_hidden()          # desktop sidebar is gone

    # Nothing may scroll sideways on a phone.
    for path in ("/", "/sales", "/products", "/inventory", "/expiry", "/purchases", "/staff", "/audit"):
        open_page(s, path)
        page.wait_for_load_state("networkidle")
        overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        assert overflow <= 1, f"{path} scrolls sideways by {overflow}px"

    # The full menu is one tap away, and reaches pages that are not on the bottom bar.
    bottom.get_by_role("button", name="আরও").click()
    drawer = page.locator("aside.drawer-panel")
    expect(drawer).to_be_visible()
    drawer.get_by_role("link", name="মেয়াদ ও ব্যাচ").click()
    expect(page).to_have_url(re.compile(r"#/expiry"))
    expect(page.get_by_role("heading", name="মেয়াদ ও ব্যাচ")).to_be_visible()
    expect(drawer).to_have_count(0)                                     # closes on navigation

    # And a sale can be made with thumbs alone.
    open_page(s, "/sales")
    page.get_by_role("button", name=re.compile("Orsaline")).first.click()
    page.get_by_role("button", name=re.compile("বিক্রি সম্পন্ন করুন")).click()
    expect(page.get_by_role("heading", name="বিক্রি সম্পন্ন হয়েছে")).to_be_visible()
    no_js_errors(s)


def test_loyalty_points_are_earned_then_redeemed_at_the_till(shop, new_session):
    branch = call("GET", "/api/app/branches", token=shop["token"], org=shop["org"])[0]["id"]
    product = call("POST", "/api/app/products",
                   {"sku": "LOY-1", "name": "Loyalty Item", "selling_price": "100", "cost_price": "60"},
                   shop["token"], shop["org"])
    call("POST", "/api/app/inventory/adjust",
         {"branch_id": branch, "product_id": product["id"], "quantity_delta": "1000", "reason": "opening stock"},
         shop["token"], shop["org"])
    call("POST", "/api/app/customers", {"code": "LOY-C", "display_name": "Loyal Customer"}, shop["token"], shop["org"])

    s = new_session()
    page = s.page
    sign_in(s, shop["email"])

    # 1. Off by default: no redemption field shown yet for a customer with no points.
    open_page(s, "/setup")
    card = page.locator(".ui-card", has_text="লয়্যালটি পয়েন্ট")
    expect(card.get_by_role("checkbox")).not_to_be_checked()

    # 2. Turn it on: ৳100 = 1 point, each point worth ৳0.5.
    card.get_by_role("checkbox").check()
    card.get_by_label("কত টাকায় ১ পয়েন্ট").fill("100")
    card.get_by_label("১ পয়েন্টের মূল্য (৳)").fill("0.5")
    card.get_by_role("button", name="সংরক্ষণ করুন").click()
    expect(page.get_by_text("লয়্যালটি পয়েন্টের নিয়ম সংরক্ষিত হয়েছে")).to_be_visible()

    # 3. Sell ৳2000 to the customer: earns 20 points, no redemption offered yet (balance was 0 at sale time).
    open_page(s, "/sales")
    page.get_by_placeholder("পণ্যের নাম, SKU বা বারকোড লিখুন…").fill("Loyalty Item")
    page.get_by_role("button", name=re.compile("Loyalty Item")).first.click()
    page.locator("input[aria-label='Loyalty Item-এর পরিমাণ']").fill("20")
    page.locator("select").filter(has_text="সাধারণ ক্রেতা").select_option(label="Loyal Customer")
    page.get_by_role("button", name=re.compile("বিক্রি সম্পন্ন করুন")).click()
    expect(page.get_by_role("heading", name="বিক্রি সম্পন্ন হয়েছে")).to_be_visible()
    page.get_by_role("button", name="নতুন বিক্রি").click()

    # 4. A second sale to the same customer offers redemption; using 10 points takes ৳5 off.
    page.get_by_placeholder("পণ্যের নাম, SKU বা বারকোড লিখুন…").fill("Loyalty Item")
    page.get_by_role("button", name=re.compile("Loyalty Item")).first.click()
    page.locator("input[aria-label='Loyalty Item-এর পরিমাণ']").fill("5")
    page.locator("select").filter(has_text="সাধারণ ক্রেতা").select_option(label="Loyal Customer")
    redeem = page.get_by_label(re.compile("লয়্যালটি পয়েন্ট ভাঙান"))
    expect(redeem).to_be_visible()
    redeem.fill("10")
    expect(page.get_by_text("পয়েন্ট ছাড়")).to_be_visible()
    page.get_by_role("button", name=re.compile("বিক্রি সম্পন্ন করুন")).click()
    expect(page.get_by_role("heading", name="বিক্রি সম্পন্ন হয়েছে")).to_be_visible()
    expect(page.locator(".receipt")).to_contain_text(bn(495))            # ৳500 - ৳5 point discount
    page.get_by_role("button", name="নতুন বিক্রি").click()

    # 5. The customer's own page shows the remaining balance: 20 earned - 10 redeemed + 4 earned on ৳495.
    open_page(s, "/directory")
    page.get_by_role("button", name="Loyal Customer", exact=True).click()
    expect(page.get_by_text("লয়্যালটি পয়েন্ট")).to_be_visible()
    expect(page.get_by_text(bn(14), exact=True)).to_be_visible()
    no_js_errors(s)


def test_bsmart_can_run_on_the_shops_own_data_not_just_the_research_sample(shop, new_session):
    branch = call("GET", "/api/app/branches", token=shop["token"], org=shop["org"])[0]["id"]
    product = call("POST", "/api/app/products",
                   {"sku": "BS-1", "name": "Live Reorder Item", "selling_price": "100", "cost_price": "60",
                    "reorder_level": "5"}, shop["token"], shop["org"])
    call("POST", "/api/app/inventory/adjust",
         {"branch_id": branch, "product_id": product["id"], "quantity_delta": "25", "reason": "opening stock"},
         shop["token"], shop["org"])
    now = datetime.now(timezone.utc)
    for day in range(10):
        sold_at = (now - timedelta(days=day)).isoformat()
        call("POST", "/api/app/sales", {
            "branch_id": branch, "invoice_number": f"BS-{day}", "sold_at": sold_at,
            "items": [{"product_id": product["id"], "quantity": "2"}],
            "payments": [{"method": "cash", "amount": "200"}],
        }, shop["token"], shop["org"])

    s = new_session()
    page = s.page
    sign_in(s, shop["email"])
    open_page(s, "/bsmart-actions")
    page.get_by_role("button", name="নিজের ব্যবসার ডেটা থেকে রান করুন").click()
    expect(page.get_by_text("আপনার নিজের ব্যবসার ডেটা থেকে")).to_be_visible(timeout=20000)

    card = page.locator(".reco", has_text="BS-1")
    expect(card).to_be_visible()
    expect(card.get_by_text("নিজের ডেটা")).to_be_visible()
    no_js_errors(s)


def test_wrong_password_is_explained_in_bangla_and_the_session_survives_a_reload(shop, new_session):
    s = new_session()
    page = s.page
    page.goto(f"{WEB}/#/login")
    page.get_by_label("ইমেইল").fill(shop["email"])
    page.get_by_label("পাসওয়ার্ড").fill("definitely wrong")
    page.get_by_role("button", name="লগইন", exact=True).click()
    expect(page.get_by_text("ইমেইল বা পাসওয়ার্ড ভুল হয়েছে")).to_be_visible()

    sign_in(s, shop["email"], PASSWORD)
    page.reload()
    expect(page.get_by_text("ব্যবসা মোড").first).to_be_visible()      # still signed in
    page.get_by_role("button", name="লগআউট").first.click()
    page.get_by_role("button", name="লগইন", exact=True).wait_for(timeout=20000)
