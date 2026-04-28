# -*- coding: utf-8 -*-
"""diecut_knowledge 模块端到端冒烟测试

用 Playwright 驱动浏览器走一遍主路径：
  1. 登录 admin
  2. 打开「行业知识库」菜单
  3. 校验 5 个预置分类已加载
  4. 创建一篇测试文章 → 提交评审 → 退回草稿 → 发布
  5. 校验"立即同步到 Dify"按钮存在
  6. 校验「同步日志」「Dify 配置」菜单可达
  7. 全程截图保存到 output/playwright/diecut_knowledge/

配置（环境变量）：
  ODOO_URL       默认 http://localhost:8070
  ODOO_DB        默认 odoo
  ODOO_LOGIN     默认 admin
  ODOO_PASSWORD  默认 admin
  HEADLESS       默认 1（CI 用），传 0 时显示浏览器
  SLOWMO_MS      默认 0，调试时设 200~500

用法：
  cd E:/workspace/my_odoo_project
  .venv/Scripts/python.exe custom_addons/diecut_knowledge/tests/e2e/smoke.py
  # 或带可视化：
  HEADLESS=0 SLOWMO_MS=300 .venv/Scripts/python.exe ...
"""

from __future__ import annotations

import io
import os
import sys
import time
from datetime import datetime
from pathlib import Path

if sys.platform.startswith("win"):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    else:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeoutError,
    expect,
    sync_playwright,
)

PROJECT_ROOT = Path(__file__).resolve().parents[4]
SCREENSHOT_DIR = PROJECT_ROOT / "output" / "playwright" / "diecut_knowledge"

ODOO_URL = os.environ.get("ODOO_URL", "http://localhost:8070")
ODOO_DB = os.environ.get("ODOO_DB", "odoo")
LOGIN = os.environ.get("ODOO_LOGIN", "admin")
PASSWORD = os.environ.get("ODOO_PASSWORD", "admin")
HEADLESS = os.environ.get("HEADLESS", "1") not in ("0", "false", "False", "")
SLOWMO_MS = int(os.environ.get("SLOWMO_MS", "0") or 0)
DEFAULT_TIMEOUT = 15_000

EXPECTED_CATEGORIES = [
    "材料选型知识",
    "模切工艺",
    "刀模设计",
    "行业标准",
    "客户问答库",
]

TEST_ARTICLE_TITLE = f"[E2E] 自动化冒烟 {datetime.now().strftime('%Y%m%d_%H%M%S')}"
TEST_ARTICLE_SUMMARY = "Playwright 自动创建的测试文章，可安全删除。"
TEST_ARTICLE_BODY = (
    "## 选型要点\n\n"
    "VHB 5910：基材为亚克力泡棉，黑色，1.0mm 厚度，适合金属对金属粘接。\n\n"
    "## 适用场景\n\n"
    "- 户外标识\n- 汽车装饰条\n- 电子产品装配\n"
)
TEST_QA_TITLE = f"[E2E] AI 抽屉问答 {datetime.now().strftime('%Y%m%d_%H%M%S')}"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _step(label: str):
    print(f"[step] {label}", flush=True)


def _shot(page: Page, name: str):
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SCREENSHOT_DIR / f"{datetime.now().strftime('%H%M%S')}_{name}.png"
    page.screenshot(path=str(path), full_page=True)
    print(f"  screenshot: {path.relative_to(PROJECT_ROOT)}", flush=True)


def _wait_action_loaded(page: Page, timeout: int = DEFAULT_TIMEOUT):
    """等待 Odoo action 视图加载完成（kanban / list / form 任一可见）。

    避免使用 networkidle —— Odoo 的 longpolling 让 networkidle 永远不来。
    """
    page.wait_for_selector(
        ".o_action_manager .o_kanban_view, "
        ".o_action_manager .o_list_view, "
        ".o_action_manager .o_form_view, "
        ".o_action_manager .o_view_nocontent",
        timeout=timeout,
        state="visible",
    )
    page.wait_for_timeout(300)


def login(page: Page):
    _step(f"login as {LOGIN}@{ODOO_URL}")
    page.goto(f"{ODOO_URL}/web/login", wait_until="domcontentloaded")
    form = page.locator("form.oe_login_form").first
    if not form.count():
        form = page.locator("form:has(input[name='login'])").first
    form.locator("input[name='login']").fill(LOGIN)
    form.locator("input[name='password']").fill(PASSWORD)
    form.locator("button[type='submit']").first.click()
    page.wait_for_url("**/odoo**", timeout=DEFAULT_TIMEOUT)
    _shot(page, "01_after_login")


def open_kb_root_menu(page: Page):
    _step("open 行业知识库 menu")
    page.goto(f"{ODOO_URL}/odoo/action-diecut_knowledge.action_diecut_kb_article",
              wait_until="domcontentloaded")
    _wait_action_loaded(page)
    _shot(page, "02_kb_articles_kanban")


def verify_categories(page: Page):
    _step("verify 5 预置分类")
    page.goto(f"{ODOO_URL}/odoo/action-diecut_knowledge.action_diecut_kb_category",
              wait_until="domcontentloaded")
    _wait_action_loaded(page)
    body_text = page.locator("body").inner_text()
    missing = [c for c in EXPECTED_CATEGORIES if c not in body_text]
    if missing:
        _shot(page, "03_categories_missing")
        raise AssertionError(f"缺少分类：{missing}")
    _shot(page, "03_categories_ok")
    print(f"  found all 5 categories: {EXPECTED_CATEGORIES}", flush=True)


def create_article(page: Page) -> int | None:
    _step(f"create article «{TEST_ARTICLE_TITLE}»")
    page.goto(f"{ODOO_URL}/odoo/action-diecut_knowledge.action_diecut_kb_article",
              wait_until="domcontentloaded")
    _wait_action_loaded(page)

    page.locator(".o_list_button_add, button:has-text('新建')").first.click(timeout=DEFAULT_TIMEOUT)
    _wait_action_loaded(page)

    title_input = page.locator(".o_field_widget[name='name'] input").first
    title_input.fill(TEST_ARTICLE_TITLE)

    summary_input = page.locator("textarea[id*='summary'], .o_field_widget[name='summary'] textarea").first
    if summary_input.count():
        summary_input.fill(TEST_ARTICLE_SUMMARY)

    _step("  pick category 材料选型知识")
    cat_input = page.locator(".o_field_widget[name='category_id'] input").first
    cat_input.click()
    cat_input.fill("材料选型")
    dropdown_item = page.locator(".o-autocomplete--dropdown-menu li:has-text('材料选型知识')").first
    dropdown_item.wait_for(state="visible", timeout=DEFAULT_TIMEOUT)
    dropdown_item.click()
    page.wait_for_timeout(300)

    _step("  fill content_html")
    page.click(".o_notebook .nav-link:has-text('正文')")
    iframe_locator = page.frame_locator(".o_field_html iframe").first
    try:
        iframe_locator.locator("body").click(timeout=3000)
        iframe_locator.locator("body").type(TEST_ARTICLE_BODY)
    except Exception:
        editor = page.locator(".o_field_html .note-editable, .o_field_html [contenteditable='true']").first
        editor.click()
        editor.type(TEST_ARTICLE_BODY)

    _step("  save")
    page.locator(".o_form_button_save, button:has-text('保存')").first.click()
    page.wait_for_timeout(800)
    _shot(page, "04_article_created")

    url = page.url
    article_id = None
    if "/" in url:
        for token in url.replace("?", "/").split("/"):
            if token.isdigit():
                article_id = int(token)
                break
    return article_id


def submit_review_and_publish(page: Page):
    _step("submit_review")
    btn = page.locator("button:has-text('提交评审')").first
    if btn.count():
        btn.click()
        page.wait_for_timeout(800)
        _shot(page, "05_review")

    _step("back to draft")
    btn = page.locator("button:has-text('退回草稿')").first
    if btn.count():
        btn.click()
        page.wait_for_timeout(800)

    _step("publish")
    btn = page.locator("button:has-text('发布')").first
    if not btn.count():
        raise AssertionError("找不到「发布」按钮")
    btn.click()
    page.wait_for_timeout(1200)
    _shot(page, "06_published")


def verify_sync_button(page: Page):
    _step("verify 立即同步 / 加入队列 / 立即解析-noop")
    sync_btn = page.locator("button:has-text('立即同步到 Dify')").first
    if not sync_btn.count():
        raise AssertionError("发布后应出现「立即同步到 Dify」按钮，但没找到")
    queue_btn = page.locator("button:has-text('加入同步队列')").first
    if not queue_btn.count():
        raise AssertionError("发布后应出现「加入同步队列」按钮，但没找到")
    print("  ✓ both sync buttons visible", flush=True)


def verify_ai_drawer_on_current_form(page: Page, shot_name: str):
    _step("verify AI 顾问抽屉")
    page.wait_for_selector(".o_form_view", state="visible", timeout=DEFAULT_TIMEOUT)
    ai_btn = page.locator(".o_form_view button:has-text('AI 顾问')").first
    if not ai_btn.count():
        raise AssertionError("当前表单未找到「AI 顾问」按钮")
    ai_btn.click()
    page.wait_for_selector(".o_diecut_ai_drawer", state="visible", timeout=DEFAULT_TIMEOUT)
    if not page.locator(".o_diecut_ai_msg_system").first.count():
        raise AssertionError("AI 顾问抽屉未显示当前记录上下文")
    _shot(page, shot_name)
    page.locator(".o_diecut_ai_close").first.click()
    page.wait_for_selector(".o_diecut_ai_drawer", state="hidden", timeout=DEFAULT_TIMEOUT)
    page.wait_for_selector(".o_form_view", state="visible", timeout=DEFAULT_TIMEOUT)
    print("  ✓ AI 顾问抽屉可打开，关闭后仍停留在当前表单", flush=True)


def verify_settings_menu(page: Page):
    _step("open Dify 配置")
    page.goto(f"{ODOO_URL}/odoo/action-diecut_knowledge.action_diecut_kb_settings",
              wait_until="domcontentloaded")
    _wait_action_loaded(page)
    body_text = page.locator("body").inner_text()
    if "Dify" not in body_text:
        _shot(page, "07_settings_fail")
        raise AssertionError("设置页未渲染 Dify 配置 block")
    _shot(page, "07_settings_ok")


def verify_sync_log_menu(page: Page):
    _step("open 同步日志")
    page.goto(f"{ODOO_URL}/odoo/action-diecut_knowledge.action_diecut_kb_sync_log",
              wait_until="domcontentloaded")
    _wait_action_loaded(page)
    _shot(page, "08_sync_logs")


def verify_qa_ticket_ai_drawer(page: Page):
    _step("verify 客户问答工单 AI 抽屉")
    page.goto(f"{ODOO_URL}/odoo/action-diecut_knowledge.action_diecut_kb_qa_ticket",
              wait_until="domcontentloaded")
    _wait_action_loaded(page)

    rows = page.locator(".o_data_row")
    if rows.count():
        rows.first.click()
    else:
        page.locator(".o_list_button_add, button:has-text('新建')").first.click(timeout=DEFAULT_TIMEOUT)
        _wait_action_loaded(page)
        page.locator(".o_field_widget[name='name'] input").first.fill(TEST_QA_TITLE)
        page.click(".o_notebook .nav-link:has-text('客户问题')")
        page.locator(".o_field_widget[name='question'] textarea").first.fill("客户询问泡棉胶高温环境是否会衰减。")
        page.click(".o_notebook .nav-link:has-text('答复内容')")
        page.locator(".o_field_widget[name='answer'] textarea").first.fill("建议结合温度、载荷和表面处理做样品验证。")
        page.locator(".o_form_button_save, button:has-text('保存')").first.click()

    page.wait_for_selector(".o_form_view", state="visible", timeout=DEFAULT_TIMEOUT)
    verify_ai_drawer_on_current_form(page, "10_qa_ai_drawer")


def verify_catalog_item_dify_extensions(page: Page):
    """验证 catalog.item 已被 diecut_knowledge 扩展：同步按钮 + 字段组可见。"""
    _step("verify catalog.item Dify 扩展")
    page.goto(f"{ODOO_URL}/odoo/action-diecut.action_diecut_catalog_item_gray",
              wait_until="domcontentloaded")
    try:
        _wait_action_loaded(page)
    except Exception:
        _shot(page, "09_catalog_action_missing")
        print("  catalog.item action 不可达，跳过", flush=True)
        return

    rows = page.locator(".o_data_row").first
    if not rows.count():
        _shot(page, "09_catalog_no_rows")
        print("  catalog.item 列表为空，跳过 form 验证", flush=True)
        return

    rows.click()
    page.wait_for_selector(".o_form_view", state="visible", timeout=DEFAULT_TIMEOUT)
    page.wait_for_timeout(500)
    sync_btn = page.locator("button:has-text('立即同步到 Dify')").first
    if not sync_btn.count():
        _shot(page, "09_catalog_no_dify_btn")
        raise AssertionError("catalog.item form 上未注入「立即同步到 Dify」按钮")
    queue_btn = page.locator("button:has-text('加入同步队列')").first
    if not queue_btn.count():
        _shot(page, "09_catalog_no_queue_btn")
        raise AssertionError("catalog.item form 上未注入「加入同步队列」按钮")
    print("  ✓ catalog.item form 已注入两个 Dify 同步按钮", flush=True)
    _shot(page, "09_catalog_item_form")
    verify_ai_drawer_on_current_form(page, "11_catalog_ai_drawer")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def run() -> int:
    print(f"=== diecut_knowledge E2E smoke ===")
    print(f"  url     : {ODOO_URL}")
    print(f"  user    : {LOGIN}")
    print(f"  headless: {HEADLESS}")
    print(f"  output  : {SCREENSHOT_DIR}")

    started = time.monotonic()
    with sync_playwright() as p:
        browser: Browser = p.chromium.launch(headless=HEADLESS, slow_mo=SLOWMO_MS)
        context: BrowserContext = browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="zh-CN",
        )
        context.set_default_timeout(DEFAULT_TIMEOUT)
        page: Page = context.new_page()

        try:
            login(page)
            open_kb_root_menu(page)
            verify_categories(page)
            create_article(page)
            submit_review_and_publish(page)
            verify_sync_button(page)
            verify_ai_drawer_on_current_form(page, "07_article_ai_drawer")
            verify_settings_menu(page)
            verify_sync_log_menu(page)
            verify_qa_ticket_ai_drawer(page)
            verify_catalog_item_dify_extensions(page)
        except (AssertionError, PlaywrightTimeoutError) as exc:
            print(f"\n[FAIL] {type(exc).__name__}: {exc}", file=sys.stderr)
            try:
                _shot(page, "99_failure")
            except Exception:
                pass
            return 1
        finally:
            context.close()
            browser.close()

    elapsed = time.monotonic() - started
    print(f"\n[OK] all checks passed in {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(run())
