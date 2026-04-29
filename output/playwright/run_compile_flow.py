from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import expect, sync_playwright


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = PROJECT_ROOT / "output" / "playwright" / "compile_flow"
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

ODOO_URL = os.environ.get("ODOO_URL", "http://localhost:8070")
LOGIN = os.environ.get("ODOO_LOGIN", "admin")
PASSWORD = os.environ.get("ODOO_PASSWORD", "admin")
HEADLESS = os.environ.get("HEADLESS", "0") not in ("0", "false", "False", "")
SLOWMO_MS = int(os.environ.get("SLOWMO_MS", "150") or 0)
SOURCE_DOC_ID = int(os.environ.get("COMPILE_SOURCE_DOC_ID", "72"))
SOURCE_DOC_NAME = os.environ.get("COMPILE_SOURCE_DOC_NAME", "tesa 6928 TDS")
ACTION_ID = int(os.environ.get("COMPILE_ACTION_ID", "737"))


def shot(page, name: str) -> None:
    path = ARTIFACT_DIR / f"{datetime.now().strftime('%H%M%S')}_{name}.png"
    page.screenshot(path=str(path), full_page=True)
    print(f"[shot] {path}")


def wait_action(page, selector: str, timeout: int = 20000) -> None:
    page.wait_for_selector(selector, state="visible", timeout=timeout)
    page.wait_for_timeout(500)


def login(page) -> None:
    print("[step] login")
    page.goto(f"{ODOO_URL}/web/login", wait_until="domcontentloaded")
    login_input = page.locator("form.oe_login_form input[name='login']")
    if login_input.count() and not login_input.first.is_visible():
        sign_in = page.locator("a:has-text('Sign in'), button:has-text('Sign in')").first
        if sign_in.count():
            sign_in.click()
            page.wait_for_timeout(500)
    if login_input.count():
        login_input.fill(LOGIN)
        page.locator("form.oe_login_form input[name='password']").fill(PASSWORD)
        page.locator("form.oe_login_form button[type='submit']").first.click()
        page.wait_for_url("**/odoo**", timeout=20000)
    else:
        page.wait_for_url("**/odoo**", timeout=20000)
    shot(page, "01_after_login")


def open_source_document(page) -> None:
    print(f"[step] open source document {SOURCE_DOC_ID}/{SOURCE_DOC_NAME}")
    page.goto(
        f"{ODOO_URL}/odoo/action-{ACTION_ID}/{SOURCE_DOC_ID}?view_type=form",
        wait_until="domcontentloaded",
    )
    try:
        wait_action(page, ".o_form_view")
    except PlaywrightTimeoutError:
        print("[info] direct form route did not land, fallback to list click")
        page.goto(f"{ODOO_URL}/odoo/action-{ACTION_ID}?view_type=list", wait_until="domcontentloaded")
        wait_action(page, ".o_list_view")
        row = page.locator(
            f".o_list_view tbody tr:has(td:text-is('{SOURCE_DOC_NAME}')), "
            f".o_list_view tbody tr:has(td:has-text('{SOURCE_DOC_NAME}'))"
        ).first
        expect(row).to_be_visible(timeout=20000)
        row.click()
        wait_action(page, ".o_form_view")
    shot(page, "02_source_doc_form")


def run_compile(page) -> None:
    parse_button = page.locator("button:has-text('解析原始资料')").first
    if parse_button.count() and parse_button.is_visible():
        print("[step] click 解析原始资料")
        parse_button.click()
        page.wait_for_timeout(2000)
        page.reload(wait_until="domcontentloaded")
        wait_action(page, ".o_form_view", timeout=30000)

    print("[step] click 编译为 Wiki")
    button = page.locator("button:has-text('编译为 Wiki')").first
    expect(button).to_be_visible(timeout=15000)
    button.click()
    page.wait_for_timeout(2000)

    notifications = page.locator(".o_notification, .o_notification_manager .o_notification")
    try:
        expect(notifications.first).to_be_visible(timeout=30000)
        print("[info] notification:", notifications.first.inner_text())
        shot(page, "03_compile_notification")
        return
    except AssertionError:
        pass

    page.reload(wait_until="domcontentloaded")
    wait_action(page, ".o_form_view", timeout=30000)
    compiled_btn = page.locator("button:has-text('打开 Wiki文章')").first
    expect(compiled_btn).to_be_visible(timeout=30000)
    print("[info] compile completed without visible toast; compiled article button is now available")
    shot(page, "03_compile_completed_without_toast")


def verify_result(page) -> None:
    print("[step] verify compiled article entry")
    page.reload(wait_until="domcontentloaded")
    wait_action(page, ".o_form_view")
    compiled_btn = page.locator("button:has-text('打开 Wiki文章')").first
    expect(compiled_btn).to_be_visible(timeout=20000)
    shot(page, "04_compiled_button_visible")
    compiled_btn.click()
    page.wait_for_timeout(1500)

    if page.locator(".o_list_view").count():
        wait_action(page, ".o_list_view", timeout=30000)
        first_row = page.locator(".o_list_view tbody tr").first
        expect(first_row).to_be_visible(timeout=20000)
        shot(page, "05_compiled_article_list")
        first_row.click()
        page.wait_for_timeout(1500)

    if page.locator(".o_form_view").count():
        wait_action(page, ".o_form_view", timeout=30000)
        shot(page, "06_compiled_article_form")
        return

    body = page.locator("body")
    expect(body).to_contain_text("材料选型知识", timeout=20000)
    shot(page, "06_compiled_article_fallback")


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS, slow_mo=SLOWMO_MS)
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        page.set_default_timeout(20000)
        try:
            login(page)
            open_source_document(page)
            run_compile(page)
            verify_result(page)
            print("[done] compile flow succeeded")
        finally:
            browser.close()


if __name__ == "__main__":
    main()
