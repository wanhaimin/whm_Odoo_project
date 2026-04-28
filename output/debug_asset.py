"""Debug: check if AI component is rendered"""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    page = ctx.new_page()

    page.goto("http://localhost:8070/web/login", wait_until="domcontentloaded")
    page.wait_for_timeout(1500)
    page.locator("input[name='login']").fill("admin")
    page.locator("input[name='password']").fill("admin")
    page.locator(".oe_login_form button[type='submit']").first.click()
    page.wait_for_timeout(3000)

    page.goto("http://localhost:8070/odoo/action-diecut_knowledge.action_diecut_kb_qa_ticket",
              wait_until="domcontentloaded")
    page.wait_for_timeout(2000)
    page.locator(".o_list_button_add").first.click()
    page.wait_for_timeout(1500)
    page.locator(".o_field_widget[name='name'] input").first.fill("Bundle Test")
    page.locator("button.o_form_button_save").first.click()
    page.wait_for_timeout(2000)

    # Publish
    page.locator("button:has-text('发布')").first.click()
    page.wait_for_timeout(2000)

    # Close any modal
    page.evaluate("document.querySelector('.modal .btn-close')?.click()")
    page.wait_for_timeout(500)

    # Click AI
    page.locator("button[name='action_open_ai_advisor']").first.click()
    page.wait_for_timeout(3000)
    page.screenshot(path="output/debug_after_ai.png")

    # Check page content
    text = page.evaluate("document.querySelector('.o_content')?.innerText || 'no .o_content'")
    print("Content:", text[:500])

    # Check for our elements
    found = page.evaluate("""
        document.querySelectorAll('[class*=\"diecut_ai\"]').length
    """)
    print(f"Elements with diecut_ai class: {found}")

    # Check full body for any known pattern
    has_our_content = page.evaluate("""
        document.body.innerText.includes('AI') || document.body.innerText.includes('diecut')
    """)
    print(f"Has AI text in body: {has_our_content}")

    ctx.close()
    browser.close()
