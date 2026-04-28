"""E2E feature test v2 - using Odoo form selectors"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

from playwright.sync_api import sync_playwright
SHOTS = True
ODOO_URL = "http://localhost:8070"

def wait_action(page, timeout=10000):
    page.wait_for_selector(
        ".o_action_manager .o_kanban_view, "
        ".o_action_manager .o_list_view, "
        ".o_action_manager .o_form_view, "
        ".o_action_manager .o_view_nocontent",
        timeout=timeout, state="visible",
    )
    page.wait_for_timeout(500)

def shot(page, name):
    if SHOTS:
        page.screenshot(path=f"output/{name}.png", full_page=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=300)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    page = ctx.new_page()

    # Login
    print("Login...")
    page.goto(f"{ODOO_URL}/web/login", wait_until="domcontentloaded")
    page.wait_for_timeout(1500)
    page.locator("input[name='login']").fill("admin")
    page.locator("input[name='password']").fill("admin")
    page.locator(".oe_login_form button[type='submit']").first.click()
    page.wait_for_timeout(3000)

    # === 1. QA ticket ===
    print("\n1. QA ticket workflow...")
    page.goto(f"{ODOO_URL}/odoo/action-diecut_knowledge.action_diecut_kb_qa_ticket",
              wait_until="domcontentloaded")
    wait_action(page)
    shot(page, "f1_qa_list")

    add_btn = page.locator(".o_list_button_add").first
    if add_btn.count():
        add_btn.click()
    else:
        page.locator("button:has-text('New'), button:has-text('新建')").first.click()
    page.wait_for_timeout(2000)

    # Fill form
    name_el = page.locator(".o_field_widget[name='name'] input").first
    if not name_el.count():
        name_el = page.locator("input[name='name']").first
    if name_el.count():
        name_el.fill("E2E QA: VHB temp test")
        print("  Name filled")

    q_el = page.locator("textarea[name='question']").first
    if not q_el.count():
        q_el = page.locator(".o_field_widget[name='question'] textarea").first
    if q_el.count():
        q_el.fill("Test question about VHB?")
        print("  Question filled")

    a_el = page.locator("textarea[name='answer']").first
    if not a_el.count():
        a_el = page.locator(".o_field_widget[name='answer'] textarea").first
    if a_el.count():
        a_el.fill("Test answer about VHB.")
        print("  Answer filled")

    shot(page, "f2_qa_form_filled")

    # Save
    save = page.locator(".o_form_button_save").first
    if save.count():
        save.click()
        page.wait_for_timeout(2000)
        print("  Saved")
    shot(page, "f3_qa_saved")

    # Publish
    pub = page.locator("button:has-text('发布')").first
    if pub.count():
        pub.click()
        page.wait_for_timeout(1500)
        print("  Published")
        shot(page, "f4_qa_published")
    else:
        print("  Publish btn not found")

    # Check sync buttons
    sync = page.locator("button:has-text('立即同步')").first
    ai = page.locator("button:has-text('AI 顾问')").first
    print(f"  Sync btn: {'FOUND' if sync.count() else 'MISS'}")
    print(f"  AI btn: {'FOUND' if ai.count() else 'MISS'}")

    # Open AI drawer
    if ai.count():
        ai.click()
        page.wait_for_timeout(2000)
        shot(page, "f5_ai_drawer")
        drawer = page.locator(".o_diecut_ai_drawer").first
        print(f"  AI drawer: {'VISIBLE' if drawer.count() and drawer.is_visible() else 'HIDDEN'}")

        if drawer.count():
            inp = page.locator("textarea.o_diecut_ai_input").first
            if inp.count():
                inp.fill("What are the features?")
                send = page.locator(".o_diecut_ai_send_btn").first
                if send.count():
                    send.click()
                    page.wait_for_timeout(3000)
                    shot(page, "f6_ai_response")
                    msgs = page.locator(".o_diecut_ai_msg").all()
                    print(f"  Chat messages: {len(msgs)}")

            close = page.locator("button.o_diecut_ai_close").first
            if close.count():
                close.click()
                page.wait_for_timeout(500)

    # === 2. Catalog item AI advisor ===
    print("\n2. Catalog item AI advisor...")
    page.goto(f"{ODOO_URL}/odoo/action-diecut.action_diecut_catalog_item",
              wait_until="domcontentloaded")
    wait_action(page)
    shot(page, "f7_catalog_list")

    row = page.locator(".o_data_row").first
    if row.count():
        row.click()
        page.wait_for_timeout(2000)
        shot(page, "f8_catalog_form")

        ai2 = page.locator("button:has-text('AI 顾问')").first
        if ai2.count():
            ai2.click()
            page.wait_for_timeout(1500)
            d2 = page.locator(".o_diecut_ai_drawer").first
            print(f"  Catalog AI drawer: {'VISIBLE' if d2.count() and d2.is_visible() else 'HIDDEN'}")

            c2 = page.locator("button.o_diecut_ai_close").first
            if c2.count():
                c2.click()
                page.wait_for_timeout(500)
        else:
            print("  No AI btn on catalog form")
    else:
        print("  Catalog list empty")

    # === 3. Menus ===
    print("\n3. Menu tests...")
    page.goto(f"{ODOO_URL}/odoo/action-diecut_knowledge.action_diecut_kb_settings",
              wait_until="domcontentloaded")
    page.wait_for_timeout(2000)
    body = page.locator("body").inner_text()
    print(f"  Settings page: {'PASS' if 'Dify' in body else 'FAIL'}")

    page.goto(f"{ODOO_URL}/odoo/action-diecut_knowledge.action_diecut_kb_qa_ticket",
              wait_until="domcontentloaded")
    wait_action(page)
    shot(page, "f9_qa_menu")
    print(f"  QA ticket page: PASS")

    # === 4. Article workflow ===
    print("\n4. Article workflow...")
    page.goto(f"{ODOO_URL}/odoo/action-diecut_knowledge.action_diecut_kb_article",
              wait_until="domcontentloaded")
    wait_action(page)
    shot(page, "f10_article_list")

    add_btn = page.locator(".o_list_button_add").first
    if add_btn.count():
        add_btn.click()
    page.wait_for_timeout(2000)

    title = page.locator(".o_field_widget[name='name'] input").first
    if title.count():
        title.fill("E2E Article test")
        print("  Article name filled")

    cat_input = page.locator(".o_field_widget[name='category_id'] input").first
    if cat_input.count():
        cat_input.click()
        cat_input.fill("材料")
        page.wait_for_timeout(800)
        page.locator(".ui-menu-item:has-text('材料选型')").first.click()
        page.wait_for_timeout(300)

    save = page.locator(".o_form_button_save").first
    if save.count():
        save.click()
        page.wait_for_timeout(1500)

    pub = page.locator("button:has-text('发布')").first
    if pub.count():
        pub.click()
        page.wait_for_timeout(1500)
        shot(page, "f11_article_published")
        print("  Article published")

    ai3 = page.locator("button:has-text('AI 顾问')").first
    print(f"  Article AI btn: {'FOUND' if ai3.count() else 'MISS'}")

    ctx.close()
    browser.close()
    print("\n=== All done ===")
