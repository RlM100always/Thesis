"""Every panel, every role, from signup to sign-in.

These tests answer one question: does each person, signing up or being invited,
land on a working screen that shows exactly what their role allows, with no
permission errors leaking onto pages they may open?
"""

import re
import uuid

import pytest
from playwright.sync_api import expect

from .conftest import PASSWORD, WEB, bn, call, sign_in

# Sidebar label → route, for the business-mode menu.
NAV = {
    "ড্যাশবোর্ড": "/", "বিক্রি": "/sales", "স্টক": "/inventory", "মেয়াদ ও ব্যাচ": "/expiry",
    "পণ্য": "/products", "ক্রয়": "/purchases", "রিটার্ন": "/returns",
    "কাস্টমার ও সাপ্লায়ার": "/directory", "হিসাব": "/accounts", "আজকের করণীয়": "/strategy",
    "B-SMART সুপারিশ": "/bsmart-actions", "ব্যবসা ও শাখা": "/setup",
    "কর্মী ও ভূমিকা": "/staff", "কার্যকলাপের ইতিহাস": "/audit", "অনুমোদন": "/approvals",
    "বিক্রির ইতিহাস": "/sales-history", "ক্যাশ মেলান": "/cash", "রিপোর্ট": "/reports",
    "কী কিনবেন": "/reorder", "তথ্য আমদানি": "/import", "ইনসাইটস": "/insights", "আর্থিক প্রতিবেদন": "/accounting",
}
EVERYONE = {"ব্যবসা ও শাখা"}   # the settings page has no permission gate of its own

# role → the menu items it must see. Everything else in NAV must be hidden.
ROLE_MENU = {
    "manager": {"ড্যাশবোর্ড", "বিক্রি", "স্টক", "মেয়াদ ও ব্যাচ", "পণ্য", "ক্রয়", "রিটার্ন", "কাস্টমার ও সাপ্লায়ার",
                "হিসাব", "আজকের করণীয়", "B-SMART সুপারিশ", "কর্মী ও ভূমিকা", "কার্যকলাপের ইতিহাস",
                "বিক্রির ইতিহাস", "ক্যাশ মেলান", "রিপোর্ট", "কী কিনবেন", "তথ্য আমদানি", "ইনসাইটস", "আর্থিক প্রতিবেদন", "অনুমোদন"},
    "cashier": {"বিক্রি", "স্টক", "মেয়াদ ও ব্যাচ", "পণ্য", "রিটার্ন", "কাস্টমার ও সাপ্লায়ার", "বিক্রির ইতিহাস", "ক্যাশ মেলান", "ইনসাইটস"},
    "accountant": {"ড্যাশবোর্ড", "বিক্রি", "স্টক", "মেয়াদ ও ব্যাচ", "পণ্য", "ক্রয়", "রিটার্ন", "কাস্টমার ও সাপ্লায়ার",
                   "হিসাব", "আজকের করণীয়", "B-SMART সুপারিশ", "বিক্রির ইতিহাস", "ক্যাশ মেলান", "রিপোর্ট", "কী কিনবেন", "তথ্য আমদানি", "ইনসাইটস", "আর্থিক প্রতিবেদন", "অনুমোদন"},
    "stock_keeper": {"স্টক", "মেয়াদ ও ব্যাচ", "পণ্য", "ক্রয়", "কী কিনবেন", "ইনসাইটস"},
    "viewer": {"ড্যাশবোর্ড", "বিক্রি", "স্টক", "মেয়াদ ও ব্যাচ", "পণ্য", "ক্রয়", "রিটার্ন", "কাস্টমার ও সাপ্লায়ার",
               "হিসাব", "আজকের করণীয়", "B-SMART সুপারিশ", "বিক্রির ইতিহাস", "ক্যাশ মেলান", "রিপোর্ট", "কী কিনবেন", "ইনসাইটস", "আর্থিক প্রতিবেদন", "অনুমোদন"},
    "evaluator": {"ড্যাশবোর্ড", "আজকের করণীয়", "B-SMART সুপারিশ"},
}
# Where each role should land on "/".
HOME = {"manager": "/", "cashier": "/sales", "accountant": "/", "stock_keeper": "/inventory", "viewer": "/", "evaluator": "/"}


def no_js_errors(session):
    real = [e for e in session.errors if "Failed to load resource" not in e]
    assert real == [], real


def invite(shop, role):
    """Owner invites someone (API), they set a password from their link, ready to sign in."""
    email = f"{role}-{uuid.uuid4().hex[:6]}@example.com"
    staff = call("POST", "/api/app/staff", {"email": email, "display_name": f"{role} user", "role": role}, shop["token"], shop["org"])
    call("POST", "/api/app/auth/set-password", {"token": staff["setup_token"], "password": PASSWORD})
    return email


def seed_stock(shop):
    branch = call("GET", "/api/app/branches", token=shop["token"], org=shop["org"])[0]["id"]
    product = call("POST", "/api/app/products", {"sku": "P-1", "name": "Napa", "selling_price": "15", "cost_price": "10"}, shop["token"], shop["org"])
    call("POST", "/api/app/inventory/adjust", {"branch_id": branch, "product_id": product["id"], "quantity_delta": "50", "reason": "opening stock"}, shop["token"], shop["org"])
    return branch, product["id"]


# ── signup → first business → first steps ────────────────────────────────────

def test_a_new_owner_signs_up_creates_a_business_and_is_guided(stack, new_session):
    s = new_session()
    page = s.page
    email = f"new-{uuid.uuid4().hex[:8]}@example.com"
    page.goto(f"{WEB}/#/login")
    page.get_by_role("button", name="অ্যাকাউন্ট খুলুন").first.click()
    page.get_by_label("আপনার নাম").fill("করিম উদ্দিন")
    page.get_by_label("ইমেইল").fill(email)
    page.get_by_label("পাসওয়ার্ড").fill(PASSWORD)
    page.get_by_role("button", name="অ্যাকাউন্ট খুলুন").last.click()

    # No business yet, so signup leads straight to creating one, not to an empty screen.
    expect(page.get_by_role("heading", name=re.compile("স্বাগতম"))).to_be_visible()
    page.get_by_label("ব্যবসার নাম").fill("করিম ফার্মেসি")
    page.get_by_role("button", name="ব্যবসা তৈরি করুন").click()

    expect(page.get_by_role("heading", name="ব্যবসার ড্যাশবোর্ড")).to_be_visible()
    expect(page.get_by_text("শুরু করুন — ৪টি ধাপে প্রস্তুত")).to_be_visible()
    expect(page.get_by_text("করিম ফার্মেসি").first).to_be_visible()
    page.get_by_role("link", name=re.compile("পণ্য যোগ করুন")).click()
    expect(page.get_by_role("heading", name="পণ্য ও মূল্য")).to_be_visible()
    no_js_errors(s)


def test_signup_errors_are_explained_in_bangla(shop, new_session):
    s = new_session()
    page = s.page
    page.goto(f"{WEB}/#/login")
    page.get_by_role("button", name="অ্যাকাউন্ট খুলুন").first.click()
    page.get_by_label("আপনার নাম").fill("রহিম উদ্দিন")
    page.get_by_label("ইমেইল").fill(shop["email"])           # already registered
    page.get_by_label("পাসওয়ার্ড").fill(PASSWORD)
    page.get_by_role("button", name="অ্যাকাউন্ট খুলুন").last.click()
    expect(page.get_by_text("এই ইমেইল দিয়ে আগেই অ্যাকাউন্ট খোলা আছে")).to_be_visible()


# ── the money side ───────────────────────────────────────────────────────────

def test_credit_sale_collect_baki_record_expense_and_take_a_return(shop, new_session):
    branch, product = seed_stock(shop)
    s = new_session()
    page = s.page
    sign_in(s, shop["email"])

    # A customer who consents to messages.
    page.goto(f"{WEB}/#/directory")
    page.get_by_role("button", name="নতুন কাস্টমার").click()
    dialog = page.locator("dialog[open]")
    dialog.get_by_label("কোড").fill("C-101")
    dialog.get_by_label("নাম").fill("হালিমা খাতুন")
    dialog.get_by_label("মোবাইল নম্বর").fill("01712345678")
    dialog.locator("input[type=checkbox]").check()
    dialog.locator("footer").get_by_role("button", name="যোগ করুন").click()
    expect(page.get_by_text("হালিমা খাতুন")).to_be_visible()

    # Sell 2 on credit (nothing paid): a due of ৳30 appears against her name.
    page.goto(f"{WEB}/#/sales")
    page.get_by_placeholder(re.compile("পণ্যের নাম")).fill("Napa")
    page.get_by_role("button", name=re.compile("Napa")).first.click()
    page.locator("input[aria-label='Napa-এর পরিমাণ']").fill("2")
    page.get_by_label("কাস্টমার").select_option(label="হালিমা খাতুন")
    page.get_by_role("button", name="সবটা বাকি").click()
    expect(page.get_by_text("বাকি থাকবে")).to_be_visible()
    page.get_by_role("button", name=re.compile("বিক্রি সম্পন্ন করুন")).click()
    expect(page.get_by_role("heading", name="বিক্রি সম্পন্ন হয়েছে")).to_be_visible()
    page.get_by_role("button", name="নতুন বিক্রি").click()

    # Collect it.
    page.goto(f"{WEB}/#/directory")
    row = page.get_by_role("row", name=re.compile("হালিমা"))
    expect(row).to_contain_text(bn(30))
    row.get_by_role("button", name="বাকি আদায়").click()
    page.locator("dialog[open]").locator("footer").get_by_role("button", name="আদায় নিশ্চিত করুন").click()
    expect(page.get_by_text("আদায় হয়েছে")).to_be_visible()
    expect(page.get_by_role("row", name=re.compile("হালিমা"))).not_to_contain_text("বাকি আদায়")

    # An expense.
    page.goto(f"{WEB}/#/accounts")
    page.get_by_role("button", name="নতুন খরচ").first.click()
    dialog = page.locator("dialog[open]")
    dialog.get_by_label("টাকা").fill("5000")
    dialog.locator("footer").get_by_role("button", name="খরচ লিখুন").click()
    expect(page.get_by_text("খরচ লেখা হয়েছে")).to_be_visible()
    expect(page.get_by_role("row", name=re.compile("দোকান ভাড়া"))).to_contain_text(bn("5,000"))

    # A return of 1 unit goes back to stock.
    page.goto(f"{WEB}/#/returns")
    page.get_by_role("button", name="নতুন রিটার্ন").click()
    dialog = page.locator("dialog[open]")
    dialog.get_by_label("কত ফেরত এসেছে?").fill("1")
    dialog.get_by_label("টাকা কীভাবে ফেরত?").select_option(index=3)   # against the baki, not cash
    dialog.locator("footer").get_by_role("button", name="রিটার্ন নিশ্চিত করুন").click()
    expect(page.get_by_text("রিটার্ন সম্পন্ন হয়েছে")).to_be_visible()
    expect(page.get_by_role("row", name=re.compile("RET-"))).to_be_visible()
    no_js_errors(s)


def test_owner_decides_a_recommendation_and_records_what_happened(shop, new_session):
    seed_stock(shop)
    s = new_session()
    page = s.page
    sign_in(s, shop["email"])
    page.goto(f"{WEB}/#/bsmart-actions")
    page.get_by_role("button", name="নতুন সুপারিশ আনুন").click()
    expect(page.locator(".reco").first).to_be_visible(timeout=20000)

    page.get_by_role("button", name="গ্রহণ করুন").first.click()
    page.locator("dialog[open]").locator("footer").get_by_role("button", name="সিদ্ধান্ত নিশ্চিত করুন").click()
    expect(page.get_by_text("সিদ্ধান্ত রাখা হয়েছে")).to_be_visible()

    page.get_by_role("tab", name=re.compile("সিদ্ধান্ত হয়েছে")).click()
    page.get_by_role("button", name="ফলাফল লিখুন").first.click()
    dialog = page.locator("dialog[open]")
    dialog.get_by_label("কাজটি কি সত্যিই করেছেন?").select_option("yes")
    dialog.locator("footer").get_by_role("button", name="ফলাফল রাখুন").click()
    expect(page.get_by_text("ফলাফল লেখা হয়েছে").first).to_be_visible()

    # Monitoring now reflects one accepted decision; unmeasured figures stay "not measured", not zero.
    expect(page.locator(".ui-stat", has_text="গ্রহণের হার")).to_contain_text(f"{bn(100)}%")
    expect(page.locator(".ui-stat", has_text="স্টকআউট দিন বদল")).to_contain_text("মাপা হয়নি")
    no_js_errors(s)


# ── one test per role ────────────────────────────────────────────────────────

@pytest.mark.parametrize("role", list(ROLE_MENU))
def test_each_role_signs_in_and_sees_exactly_its_panels(shop, new_session, role):
    seed_stock(shop)
    email = invite(shop, role)
    s = new_session()
    page = s.page
    sign_in(s, email)

    # Lands on the right start page.
    expected = HOME[role]
    if expected != "/":
        expect(page).to_have_url(re.compile(f"#{re.escape(expected)}$"))
    nav = page.locator("aside.sidebar nav").first

    allowed = ROLE_MENU[role] | EVERYONE
    for label in NAV:
        link = nav.get_by_role("link", name=label, exact=True)
        if label in allowed:
            expect(link, f"{role} should see {label}").to_be_visible()
        else:
            expect(link, f"{role} must not see {label}").to_have_count(0)

    # Every page in the menu opens, and none shows a permission or server error.
    for label in sorted(allowed):
        page.goto(f"{WEB}/#{NAV[label]}")
        page.locator("main.main").wait_for(state="visible")
        page.wait_for_load_state("networkidle")
        assert page.locator(".ui-notice--danger").count() == 0, f"{role} sees an error on {label}"
        assert page.get_by_text("এই পাতাটি আপনার ভূমিকার জন্য নয়").count() == 0, f"{role} is blocked from {label}"

    # A page outside the menu is refused politely, not with a crash.
    for label in NAV:
        # "/" is skipped: it sends each role to its own start page instead of refusing.
        if label not in allowed and NAV[label] != "/":
            page.goto(f"{WEB}/#{NAV[label]}")
            expect(page.get_by_text("এই পাতাটি আপনার ভূমিকার জন্য নয়")).to_be_visible()
            break
    no_js_errors(s)


def test_the_owner_can_open_every_screen_without_an_error(shop, new_session):
    seed_stock(shop)
    s = new_session()
    page = s.page
    sign_in(s, shop["email"])
    business = [*NAV.values(), "/account", "/forecast", "/segments", "/upload"]
    research = ["/bsmart", "/models", "/real-data-validation", "/customers", "/whatif", "/overview"]
    for path in business + research:
        page.goto(f"{WEB}/#{path}")
        page.locator("main.main").wait_for(state="visible")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(300)
        assert page.get_by_text("এই পাতাটি আপনার ভূমিকার জন্য নয়").count() == 0, f"owner blocked from {path}"
        assert page.get_by_text("পাতা পাওয়া যায়নি").count() == 0, f"{path} does not exist"
        # Research pages compute over the study dataset and can take a while: give them time.
        page.locator("main.main h2, main.main h1").first.wait_for(timeout=45000)
        assert page.locator(".state.error, .ui-notice--danger").count() == 0, f"{path} shows an error"
    no_js_errors(s)


def test_a_clothing_shop_uses_the_same_software_without_expiry_screens(stack, new_session):
    """The product is for any SME: an apparel shop signs up, and expiry never gets in its way."""
    s = new_session()
    page = s.page
    email = f"noor-{uuid.uuid4().hex[:8]}@example.com"
    page.goto(f"{WEB}/#/login")
    page.get_by_role("button", name="অ্যাকাউন্ট খুলুন").first.click()
    page.get_by_label("আপনার নাম").fill("নূর জাহান")
    page.get_by_label("ইমেইল").fill(email)
    page.get_by_label("পাসওয়ার্ড").fill(PASSWORD)
    page.get_by_role("button", name="অ্যাকাউন্ট খুলুন").last.click()
    page.get_by_label("ব্যবসার নাম").fill("নূর ফ্যাশন")
    page.get_by_label("কী ধরনের ব্যবসা?").select_option("apparel")
    expect(page.get_by_text("নিজে চালু করতে পারবেন")).to_be_visible()
    page.get_by_role("button", name="ব্যবসা তৈরি করুন").click()

    expect(page.get_by_role("heading", name="ব্যবসার ড্যাশবোর্ড")).to_be_visible()
    nav = page.locator("aside.sidebar nav").first
    expect(nav.get_by_role("link", name="মেয়াদ ও ব্যাচ", exact=True)).to_have_count(0)

    # A shirt: no expiry box ticked by default, nothing about medicine anywhere.
    page.goto(f"{WEB}/#/products")
    page.get_by_role("button", name="নতুন পণ্য").first.click()
    form = page.locator("#product-form")
    text_inputs = form.locator("input:not([type=number]):not([type=checkbox])")
    text_inputs.nth(0).fill("সুতির শার্ট")
    text_inputs.nth(1).fill("SHIRT-1")
    form.locator("input[type=number]").nth(0).fill("800")
    form.locator("input[type=number]").nth(1).fill("500")
    expect(form.locator("input[type=checkbox]")).not_to_be_checked()
    page.locator("dialog[open]").locator("footer").get_by_role("button", name="পণ্য যোগ করুন").click()
    expect(page.get_by_text("সুতির শার্ট").first).to_be_visible()

    # Supplier, purchase, receive: no batch or expiry questions.
    page.goto(f"{WEB}/#/directory")
    page.get_by_role("button", name="নতুন সাপ্লায়ার").click()
    dialog = page.locator("dialog[open]")
    dialog.get_by_label("কোড").fill("TEX-1")
    dialog.get_by_label("নাম").fill("ঢাকা টেক্সটাইল")
    dialog.locator("footer").get_by_role("button", name="যোগ করুন").click()
    expect(page.get_by_text("সাপ্লায়ার যোগ হয়েছে")).to_be_visible()

    page.goto(f"{WEB}/#/purchases")
    page.get_by_role("button", name="নতুন ক্রয় অর্ডার").first.click()
    po = page.locator("#po-form")
    po.locator("select").nth(0).select_option(label="ঢাকা টেক্সটাইল")
    po.locator("select").nth(1).select_option(index=1)
    po.get_by_label("পরিমাণ").fill("10")
    page.locator("dialog[open]").locator("footer").get_by_role("button", name="অর্ডার দিন").click()
    page.get_by_role("button", name="মাল রিসিভ").first.click()
    dialog = page.locator("dialog[open]")
    assert dialog.get_by_label("ব্যাচ নম্বর").count() == 0
    dialog.locator("footer").get_by_role("button", name="রিসিভ নিশ্চিত করুন").click()
    expect(page.get_by_text("মাল রিসিভ হয়েছে")).to_be_visible()

    # Sell two shirts.
    page.goto(f"{WEB}/#/sales")
    page.get_by_placeholder(re.compile("পণ্যের নাম")).fill("শার্ট")
    page.get_by_role("button", name=re.compile("সুতির শার্ট")).first.click()
    page.locator("input[aria-label='সুতির শার্ট-এর পরিমাণ']").fill("2")
    page.get_by_role("button", name=re.compile("বিক্রি সম্পন্ন করুন")).click()
    expect(page.locator(".receipt")).to_contain_text(bn("1,600"))
    page.get_by_role("button", name="নতুন বিক্রি").click()

    page.goto(f"{WEB}/#/")
    expect(page.locator(".ui-stat", has_text="নিট বিক্রি")).to_contain_text(bn("1,600"))
    expect(page.get_by_text("মেয়াদে আটকে থাকা টাকা")).to_have_count(0)

    # Expiry is still one click away when a product needs it.
    page.goto(f"{WEB}/#/products")
    page.get_by_role("button", name="চালু করুন").first.click()
    page.get_by_role("button", name="নিশ্চিত করুন").click()
    expect(page.get_by_text("মেয়াদ ট্র্যাকিং চালু হয়েছে")).to_be_visible()
    expect(nav.get_by_role("link", name="মেয়াদ ও ব্যাচ", exact=True)).to_be_visible()
    no_js_errors(s)
