"""E2E test: AI advisor drawer + QA ticket"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

from playwright.sync_api import sync_playwright

ODOO_URL = "http://localhost:8070"
LOGIN = "admin"
PASSWORD = "admin"

def login(page):
    page.goto(f"{ODOO_URL}/web/login", wait_until="domcontentloaded")
    page.wait_for_timeout(1500)
    page.locator("input[name='login']").fill(LOGIN)
    page.locator("input[name='password']").fill(PASSWORD)
    page.locator(".oe_login_form button[type='submit']").first.click()
    page.wait_for_timeout(2000)

def shot(page, name):
    path = f"output/{name}.png"
    page.screenshot(path=path, full_page=True)
    print(f"  [shot] {name}.png")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=200)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    page = ctx.new_page()
    page.set_default_timeout(15000)

    # Login
    print("1. Login...")
    login(page)

    # ---- QA Ticket ----
    print("\n2. Test QA ticket...")
    page.goto(f"{ODOO_URL}/odoo/action-diecut_knowledge.action_diecut_kb_qa_ticket",
              wait_until="domcontentloaded")
    page.wait_for_timeout(2000)
    shot(page, "21_qa_ticket_list")

    page.locator(".o_list_button_add").first.click()
    page.wait_for_timeout(1000)

    title = page.locator("input[name='name']").first
    if title.count():
        title.fill("E2E test: VHB high temp adhesion")
    page.wait_for_timeout(200)

    q = page.locator("textarea[name='question']").first
    if q.count():
        q.fill("How much does VHB lose adhesion at 80C?")
    page.wait_for_timeout(200)

    a = page.locator("textarea[name='answer']").first
    if a.count():
        a.fill("VHB 5952 retains 85%+ after 80C aging per ASTM D1002.")
    page.wait_for_timeout(200)

    c = page.locator("input[name='customer_name']").first
    if c.count():
        c.fill("Test Customer")

    page.locator(".o_form_button_save").first.click()
    page.wait_for_timeout(1000)
    shot(page, "22_qa_ticket_saved")

    pub = page.locator("button:has-text('Publish')").first
    if not pub.count():
        pub = page.locator("button:has-text('publish')").first
    if not pub.count():
        pub = page.locator("button:has-text('发布')").first
    if pub.count():
        pub.click()
        page.wait_for_timeout(1000)
        print("  Published")
        shot(page, "23_qa_ticket_published")

    sync = page.locator("button:has-text('Sync')").first
    if not sync.count():
        sync = page.locator("button:has-text('sync')").first
    if not sync.count():
        sync = page.locator("button:has-text('同步')").first
    print(f"  Sync btn: {sync.count()}")

    ai = page.locator("button:has-text('AI')").first
    print(f"  AI advisor btn: {ai.count()}")
    if ai.count():
        ai.click()
        page.wait_for_timeout(2000)
        shot(page, "24_ai_drawer")
        print("  AI drawer opened")

        inp = page.locator("textarea.o_diecut_ai_input").first
        if inp.count():
            inp.fill("What are the features?")
            send = page.locator("button:has-text('Send')").first
            if not send.count():
                send = page.locator("button:has-text('发送')").first
            send.click()
            page.wait_for_timeout(3000)
            shot(page, "25_ai_response")
            print("  Message sent")

        close = page.locator("button.o_diecut_ai_close").first
        if close.count():
            close.click()
            page.wait_for_timeout(500)

    # ---- catalog.item AI advisor ----
    print("\n3. Test catalog.item AI advisor...")
    page.goto(f"{ODOO_URL}/odoo/action-diecut.action_diecut_catalog_item",
              wait_until="domcontentloaded")
    page.wait_for_timeout(2000)
    shot(page, "31_catalog_list")

    row = page.locator(".o_data_row").first
    if row.count():
        row.click()
        page.wait_for_timeout(2000)
        shot(page, "32_catalog_form")

        ai2 = page.locator("button:has-text('AI')").first
        print(f"  catalog AI advisor btn: {ai2.count()}")
        if ai2.count():
            ai2.click()
            page.wait_for_timeout(2000)
            shot(page, "33_catalog_ai_drawer")

            close2 = page.locator("button.o_diecut_ai_close").first
            if close2.count():
                close2.click()
                page.wait_for_timeout(500)

    ctx.close()
    browser.close()
    print("\n=== All tests done ===")
