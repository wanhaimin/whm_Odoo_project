"""
Playwright 性能测试脚本：测量材料型号清单 Split Form 的加载延迟
"""
import asyncio
import json
import os
import sys
import time
from playwright.async_api import async_playwright

# Fix Windows console encoding
os.environ['PYTHONIOENCODING'] = 'utf-8'
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()

        # ==================== 收集网络请求 ====================
        rpc_logs = []

        def on_request(request):
            url = request.url
            if "/web/dataset/call_kw" in url or "/web/action" in url:
                post = request.post_data or ""
                method_info = ""
                try:
                    body = json.loads(post)
                    params = body.get("params", {})
                    model = params.get("model", "")
                    method = params.get("method", "")
                    if model and method:
                        method_info = f"{model}.{method}"
                    elif method:
                        method_info = method
                except Exception:
                    pass
                rpc_logs.append({
                    "url": url,
                    "method_info": method_info,
                    "start": time.perf_counter(),
                })

        def on_response(response):
            url = response.url
            if "/web/dataset/call_kw" in url or "/web/action" in url:
                for log in reversed(rpc_logs):
                    if log["url"] == url and "end" not in log:
                        log["end"] = time.perf_counter()
                        log["status"] = response.status
                        log["duration_ms"] = (log["end"] - log["start"]) * 1000
                        break

        page.on("request", on_request)
        page.on("response", on_response)

        # ==================== 1. 登录 ====================
        print("=" * 60)
        print("Step 1: 登录 Odoo")
        print("=" * 60)
        await page.goto("http://localhost:8070/web/login")
        await page.fill("input[name='login']", "admin")
        await page.fill("input[name='password']", "admin")
        await page.click(".oe_login_buttons button[type='submit']")
        await page.wait_for_timeout(5000)
        print("  OK 登录成功, 当前URL: " + page.url)

        # ==================== 2. 导航到材料型号清单 ====================
        print()
        print("Step 2: 导航到材料型号清单")
        print("-" * 40)

        # 直接通过 URL 导航到目标 action
        await page.goto("http://localhost:8070/odoo/action-diecut.action_diecut_catalog_item_gray")
        await page.wait_for_timeout(3000)
        
        # 等待列表加载
        try:
            await page.wait_for_selector(".o_data_row", timeout=20000)
        except Exception as nav_err:
            print(f"  直接导航失败: {nav_err}")
            print("  尝试通过菜单导航...")
            await page.goto("http://localhost:8070/web")
            await page.wait_for_timeout(3000)
            # 截图查看当前状态
            await page.screenshot(path="e:/workspace/my_odoo_project/screenshot_debug_nav.png")
            
            # 通过菜单导航
            try:
                menu_root = page.locator("button:has-text('模切管理系统'), a:has-text('模切管理系统'), .o_menu_sections button:has-text('模切'), nav a:has-text('模切')")
                if await menu_root.count() > 0:
                    await menu_root.first.click()
                    await page.wait_for_timeout(1000)
                
                catalog_menu = page.locator("a:has-text('材料选型大全'), button:has-text('材料选型大全'), span:has-text('材料选型大全')")
                if await catalog_menu.count() > 0:
                    await catalog_menu.first.click()
                    await page.wait_for_timeout(1000)
                    
                variant_menu = page.locator("a:has-text('材料型号清单')")
                all_menus = await variant_menu.all()
                for m in all_menus:
                    txt = await m.inner_text()
                    if '旧' not in txt and '实验' not in txt:
                        await m.click()
                        break
            except Exception as menu_err:
                print(f"  菜单导航也失败: {menu_err}")
            
            await page.wait_for_selector(".o_data_row", timeout=20000)

        await page.wait_for_timeout(1500)  # 让 searchpanel 也加载完

        row_count = await page.locator(".o_data_row").count()
        print(f"  OK 列表已加载，可见行数: {row_count}")

        # 检查是否是 split view
        is_split = await page.locator(".o_diecut_split_renderer").count() > 0
        print(f"  Split View 已启用: {is_split}")

        if not is_split:
            print("  警告: 未检测到 split view, 可能是普通列表模式")
            # 看看有没有布局切换按钮
            vertical_btn = page.locator("button.o_vertical")
            if await vertical_btn.count() > 0:
                await vertical_btn.click()
                await page.wait_for_timeout(500)
                is_split = await page.locator(".o_diecut_split_renderer").count() > 0
                print(f"  切换后 Split View: {is_split}")

        # 截图看看当前界面
        await page.screenshot(path="e:/workspace/my_odoo_project/screenshot_before_click.png")
        print("  截图: screenshot_before_click.png")

        # ==================== 3. 测量点击延迟 ====================
        print()
        print("Step 3: 测量 Form 加载延迟")
        print("=" * 60)

        results = []
        test_rows = min(5, row_count)

        for i in range(test_rows):
            row = page.locator(".o_data_row").nth(i)

            # 获取行文本
            try:
                row_text = await row.inner_text()
                # Strip zero-width chars and clean up
                row_label = row_text.strip()[:50].replace("\n", " | ")
                row_label = ''.join(c for c in row_label if ord(c) > 31 and ord(c) != 0x200b)
            except Exception:
                row_label = f"row_{i}"

            # 清空 RPC 日志
            rpc_logs.clear()

            # 记录点击前时间
            t_click = time.perf_counter()

            # 点击行的第一个单元格
            cell = row.locator("td.o_data_cell").first
            await cell.click()

            # 等待右侧 Form 出现
            form_appeared = False
            try:
                # 尝试多种选择器
                await page.wait_for_selector(
                    ".o_diecut_split_panel .o_form_view, .o_diecut_split_panel_form .o_form_view",
                    timeout=10000,
                    state="visible",
                )
                t_form_visible = time.perf_counter()
                form_delay = (t_form_visible - t_click) * 1000
                form_appeared = True
            except Exception:
                # 如果不是 split view，等待其他表现
                try:
                    await page.wait_for_selector(
                        ".o_diecut_split_row_active",
                        timeout=5000,
                    )
                    t_form_visible = time.perf_counter()
                    form_delay = (t_form_visible - t_click) * 1000
                    form_appeared = True
                except Exception:
                    form_delay = -1

            # 等待所有 widget 完全渲染
            await page.wait_for_timeout(800)
            t_fully_loaded = time.perf_counter()
            total_delay = (t_fully_loaded - t_click) * 1000

            # 收集此次点击的 RPC 统计
            completed_rpcs = [r for r in rpc_logs if "end" in r]
            rpc_count = len(completed_rpcs)
            rpc_total = sum(r.get("duration_ms", 0) for r in completed_rpcs)

            results.append({
                "row": i,
                "label": row_label,
                "form_visible_ms": form_delay,
                "total_ms": total_delay,
                "rpc_count": rpc_count,
                "rpc_total_ms": rpc_total,
                "form_appeared": form_appeared,
            })

            print(f"\n  --- Row {i}: {row_label}")
            if form_appeared:
                print(f"      Form 可见延迟:  {form_delay:.0f}ms")
            else:
                print(f"      Form 未检测到可见")
            print(f"      总耗时(含等待): {total_delay:.0f}ms")
            print(f"      RPC 请求数:     {rpc_count}")
            print(f"      RPC 总网络耗时: {rpc_total:.0f}ms")

            # 打印每个 RPC 详情
            for rpc in completed_rpcs:
                mi = rpc.get("method_info", "unknown")
                dur = rpc.get("duration_ms", 0)
                print(f"        -> {dur:6.0f}ms  {mi}")

            if form_appeared and rpc_total > 0:
                frontend_time = form_delay - rpc_total
                print(f"      前端渲染耗时:   {frontend_time:.0f}ms (= {form_delay:.0f} - {rpc_total:.0f})")

            await page.wait_for_timeout(200)

        # 截图最终状态
        await page.screenshot(path="e:/workspace/my_odoo_project/screenshot_after_click.png")
        print("\n  截图: screenshot_after_click.png")

        # ==================== 4. 汇总 ====================
        print()
        print("=" * 60)
        print("SUMMARY")
        print("=" * 60)
        valid = [r for r in results if r["form_appeared"]]
        if valid:
            avg_visible = sum(r["form_visible_ms"] for r in valid) / len(valid)
            avg_rpc = sum(r["rpc_count"] for r in valid) / len(valid)
            avg_rpc_time = sum(r["rpc_total_ms"] for r in valid) / len(valid)

            print(f"  测试行数:              {len(valid)}")
            print(f"  平均 Form 可见延迟:    {avg_visible:.0f}ms")
            print(f"  平均 RPC 请求数:       {avg_rpc:.1f}")
            print(f"  平均 RPC 网络耗时:     {avg_rpc_time:.0f}ms")
            print(f"  平均前端渲染耗时:      {max(0, avg_visible - avg_rpc_time):.0f}ms")
            print()

            if len(valid) > 1:
                first = valid[0]["form_visible_ms"]
                rest_avg = sum(r["form_visible_ms"] for r in valid[1:]) / (len(valid) - 1)
                print(f"  首次点击延迟:          {first:.0f}ms")
                print(f"  后续平均延迟:          {rest_avg:.0f}ms")
                if first > rest_avg * 1.3:
                    print(f"  => 首次比后续慢 {first/rest_avg:.1f}x (view definition缓存效果)")
        else:
            print("  未能收集到有效数据")

        await browser.close()
        print("\n  Done!")


if __name__ == "__main__":
    asyncio.run(main())
