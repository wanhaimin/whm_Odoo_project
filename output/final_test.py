"""Final test: AI advisor action"""
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
    page.locator(".o_field_widget[name='name'] input").first.fill("Final Test")
    page.locator("button.o_form_button_save").first.click()
    page.wait_for_timeout(2000)

    # Publish
    btn = page.locator("button:has-text('发布')").first
    if btn.count():
        btn.click()
        page.wait_for_timeout(2000)

    # Close any modal
    page.evaluate("document.querySelector('.modal .btn-close')?.click()")
    page.wait_for_timeout(500)

    url_before = page.url
    print(f"URL before: {url_before}")

    page.locator("button[name='action_open_ai_advisor']").first.click()
    page.wait_for_timeout(3000)
    page.screenshot(path="output/final_after_ai.png")

    url_after = page.url
    print(f"URL after:  {url_after}")
    print(f"Changed: {url_before != url_after}")

    has_overlay = page.evaluate("document.querySelector('.o_diecut_ai_overlay') !== null")
    has_drawer = page.evaluate("document.querySelector('.o_diecut_ai_drawer') !== null")
    print(f"Overlay: {has_overlay}, Drawer: {has_drawer}")

    ctx.close()
    browser.close()
