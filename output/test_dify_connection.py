"""Playwright 脚本：测试 Odoo Dify 连接"""
from playwright.sync_api import sync_playwright
import sys

ODOO_URL = "http://localhost:8070"
LOGIN = "admin"
PASSWORD = "admin"

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=300)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
        page = ctx.new_page()

        # 1. Login
        print("1. Login...")
        page.goto(f"{ODOO_URL}/web/login", wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        page.screenshot(path="output/01_login_page.png")
        # Try different selectors for login submit
        btn = page.locator(".oe_login_form button[type='submit']").first
        if not btn.count():
            btn = page.locator("form:has(input[name='login']) button[type='submit']").first
        page.locator("input[name='login']").fill(LOGIN)
        page.locator("input[name='password']").fill(PASSWORD)
        btn.click()
        page.wait_for_timeout(3000)
        page.screenshot(path="output/01_logged_in.png")
        print("   current url:", page.url)

        # 2. Open Dify settings
        print("2. Open Dify settings...")
        page.goto(f"{ODOO_URL}/odoo/action-diecut_knowledge.action_diecut_kb_settings", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        page.screenshot(path="output/02_settings.png")
        print("   current url:", page.url)

        # 3. Fill Dify base URL
        print("3. Set Dify base URL...")
        base_url_input = page.locator("input[name='diecut_kb_dify_base_url']").first
        if base_url_input.count():
            base_url_input.fill("http://localhost")
            print("   Filled base URL")
        else:
            print("   Base URL field not found!")
        page.screenshot(path="output/03_filled_url.png")

        # 4. Fill API key for testing
        print("4. Set Dataset API Key...")
        api_key_input = page.locator("input[name='diecut_kb_dify_api_key']").first
        if api_key_input.count():
            api_key_input.fill("dataset-test-key")
            print("   Filled API key (dummy)")

        # 5. Click 测试连接
        print("5. Click 测试连接...")
        test_btn = page.locator("button:has-text('测试连接')").first
        if test_btn.count():
            print(f"   Found test button: {test_btn.inner_text()}")
            test_btn.click()
            page.wait_for_timeout(3000)
            page.screenshot(path="output/04_test_result.png")
            print("   Clicked")
        else:
            print("   Test button not found!")
            body = page.locator("body").inner_text()
            print(f"   Page text: {body[:1000]}")

        # 6. Check for notification
        print("6. Check result...")
        notification = page.locator(".o_notification .o_notification_title, .o_notification .o_notification_content").first
        if notification.count():
            print(f"   Notification title: {notification.inner_text()}")
            page.screenshot(path="output/05_notification.png")
        else:
            # Try to find any notification
            notif = page.locator(".o_notification").first
            if notif.count():
                print(f"   Notification element: {notif.inner_text()}")
            else:
                print("   No notification found")
                page.screenshot(path="output/05_no_notification.png")

        page.wait_for_timeout(1000)
        ctx.close()
        browser.close()

main()
