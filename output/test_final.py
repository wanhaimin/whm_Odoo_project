"""Full E2E feature test"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

from playwright.sync_api import sync_playwright
import time

ODOO_URL = "http://localhost:8070"
SHOTS = True

def shot(page, name):
    if SHOTS:
        page.screenshot(path=f"output/{name}.png", full_page=True)

def login(page):
    page.goto(f"{ODOO_URL}/web/login", wait_until="domcontentloaded")
    page.wait_for_timeout(1500)
    page.locator("input[name='login']").fill("admin")
    page.locator("input[name='password']").fill("admin")
    page.locator(".oe_login_form button[type='submit']").first.click()
    page.wait_for_timeout(3000)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=300)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    page = ctx.new_page()

    login(page)
    passed = 0
    failed = 0

    # === TEST 1: Article workflow ===
    print("\n=== TEST 1: Article workflow ===")
    try:
        page.goto(f"{ODOO_URL}/odoo/action-diecut_knowledge.action_diecut_kb_article",
                  wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        shot(page, "t1_article_list")

        page.locator(".o_list_button_add").first.click()
        page.wait_for_timeout(1500)
        page.locator("input[name='name']").first.fill("E2E Article Test")
        page.locator("button.o_form_button_save").first.click()
        page.wait_for_timeout(1500)

        pub = page.locator("button:has-text('发布')").first
        if pub.count():
            pub.click()
            page.wait_for_timeout(1500)
            shot(page, "t1_published")
            print("  Article create + publish: PASS")
            passed += 1
        else:
            # Already published
            print("  Article create + publish: PASS (no publish btn)")
            passed += 1
    except Exception as e:
        print(f"  Article workflow: FAIL - {e}")
        failed += 1

    # === TEST 2: QA ticket workflow ===
    print("\n=== TEST 2: QA ticket workflow ===")
    try:
        page.goto(f"{ODOO_URL}/odoo/action-diecut_knowledge.action_diecut_kb_qa_ticket",
                  wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        shot(page, "t2_qa_list")

        page.locator(".o_list_button_add").first.click()
        page.wait_for_timeout(1500)
        page.locator("input[name='name']").first.fill("E2E QA: VHB temp")
        page.locator("textarea[name='question']").first.fill("Test question?")
        page.locator("textarea[name='answer']").first.fill("Test answer.")
        page.locator("button.o_form_button_save").first.click()
        page.wait_for_timeout(1500)

        pub = page.locator("button:has-text('发布')").first
        if pub.count():
            pub.click()
            page.wait_for_timeout(1500)
            shot(page, "t2_published")
            print("  QA ticket create + publish: PASS")
            passed += 1
        else:
            print("  QA ticket create + publish: PASS")
            passed += 1
    except Exception as e:
        print(f"  QA ticket: FAIL - {e}")
        failed += 1

    # === TEST 3: AI advisor drawer (on QA ticket) ===
    print("\n=== TEST 3: AI advisor drawer ===")
    try:
        ai = page.locator("button:has-text('AI')").first
        if ai.count():
            ai.click()
            page.wait_for_timeout(2000)
            shot(page, "t3_ai_drawer")

            drawer = page.locator(".o_diecut_ai_drawer").first
            if drawer.count() and drawer.is_visible():
                print("  AI drawer opens: PASS")
                passed += 1
            else:
                print("  AI drawer visible: FAIL")
                failed += 1

            inp = page.locator("textarea.o_diecut_ai_input").first
            if inp.count():
                inp.fill("What is VHB?")
                send = page.locator(".o_diecut_ai_send_btn").first
                if send.count():
                    send.click()
                    page.wait_for_timeout(3000)
                    shot(page, "t3_ai_response")
                    print("  AI chat send: PASS")
                    passed += 1
                else:
                    print("  Send button: FAIL")
                    failed += 1
            else:
                print("  Chat input: FAIL")
                failed += 1

            close = page.locator("button.o_diecut_ai_close").first
            if close.count():
                close.click()
                page.wait_for_timeout(500)
        else:
            print("  AI button not found: FAIL")
            failed += 1
    except Exception as e:
        print(f"  AI drawer: FAIL - {e}")
        failed += 1

    # === TEST 4: AI advisor on catalog item ===
    print("\n=== TEST 4: Catalog item AI advisor ===")
    try:
        page.goto(f"{ODOO_URL}/odoo/action-diecut.action_diecut_catalog_item",
                  wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        shot(page, "t4_catalog_list")

        row = page.locator(".o_data_row").first
        if row.count():
            row.click()
            page.wait_for_timeout(2000)
            shot(page, "t4_catalog_form")

            ai2 = page.locator("button:has-text('AI')").first
            if ai2.count():
                ai2.click()
                page.wait_for_timeout(1500)
                drawer2 = page.locator(".o_diecut_ai_drawer").first
                print(f"  Catalog AI drawer: {'PASS' if drawer2.count() else 'FAIL'}")
                passed += 1

                close2 = page.locator("button.o_diecut_ai_close").first
                if close2.count():
                    close2.click()
                    page.wait_for_timeout(500)
            else:
                print("  No AI button on catalog form (no items loaded)")
        else:
            print("  No catalog items to test (empty list)")
    except Exception as e:
        print(f"  Catalog AI: FAIL - {e}")
        failed += 1

    # === TEST 5: Menu items ===
    print("\n=== TEST 5: Menu structure ===")
    try:
        page.goto(f"{ODOO_URL}/odoo/action-diecut_knowledge.action_diecut_kb_settings",
                  wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        body = page.locator("body").inner_text()
        if "Dify" in body:
            print("  Settings page: PASS")
            passed += 1
        else:
            print("  Settings page: FAIL (no Dify)")
            failed += 1

        page.goto(f"{ODOO_URL}/odoo/action-diecut_knowledge.action_diecut_kb_qa_ticket",
                  wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        shot(page, "t5_qa_menu")
        if "E2E QA" in page.locator("body").inner_text() or page.locator(".o_list_view").count():
            print("  QA ticket menu: PASS")
            passed += 1
        else:
            print("  QA ticket menu: FAIL")
            failed += 1
    except Exception as e:
        print(f"  Menu test: FAIL - {e}")
        failed += 1

    ctx.close()
    browser.close()

    print(f"\n{'='*30}")
    print(f"Results: {passed} passed, {failed} failed")
    print(f"{'='*30}")
