#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
1688 超安全模式采集脚本
集成：随机延迟、拟人轨迹、人工干预、状态保持
"""

import json
import random
import time
from playwright.sync_api import sync_playwright

class Safe1688Scraper:
    def __init__(self, headless=False):
        self.headless = headless
        self.browser = None
        self.context = None
        self.page = None
        self.results = []
        self.state_path = "1688_auth_state.json"

    def human_delay(self, min_s=3, max_s=8):
        """模拟人类思考时间的停顿"""
        delay = random.uniform(min_s, max_s)
        print(f"  [安全等待] 暂停 {delay:.2f} 秒...")
        time.sleep(delay)

    def mouse_jitter(self):
        """模拟人类无意识的鼠标移动轨迹"""
        print("  [仿真模拟] 模拟鼠标微弱抖动...")
        for _ in range(random.randint(3, 7)):
            x = random.randint(100, 800)
            y = random.randint(100, 600)
            self.page.mouse.move(x, y, steps=random.randint(10, 30))
            time.sleep(random.uniform(0.1, 0.5))

    def start(self):
        """启动仿真浏览器"""
        self.playwright = sync_playwright().start()
        # 伪装 User-Agent
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        
        launch_args = {
            "headless": self.headless,
            "args": ["--disable-blink-features=AutomationControlled"]
        }
        
        self.browser = self.playwright.chromium.launch(**launch_args)
        
        # 尝试加载之前的登录状态
        try:
            with open(self.state_path, 'r') as f:
                storage_state = json.load(f)
            self.context = self.browser.new_context(user_agent=user_agent, storage_state=storage_state)
            print("  [状态读取] 已从本地记录加载登录状态")
        except:
            self.context = self.browser.new_context(user_agent=user_agent)
            print("  [首次启动] 未发现本地登录状态，可能需要手动登录")

        self.page = self.context.new_page()
        # 关键：抹掉自动化标记
        self.page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => eval('false')})")

    def check_and_wait_for_user(self):
        """检测到登录或验证码时暂停，等待人工干预"""
        content = self.page.content()
        if "login" in self.page.url.lower() or "verify" in self.page.url.lower() or "验证码" in content:
            print("\n" + "!"*50)
            print("检测到登录墙或验证码！由于超安全模式已开启，请执行以下操作：")
            print("1. 在弹出的浏览器窗口中手动完成登录或滑动验证。")
            print("2. 确认看到产品详情内容。")
            print("3. 回到终端按 Enter 键继续。")
            print("!"*50 + "\n")
            input("请在操作完成后按 Enter...")
            
            # 操作完后保存一次状态，防止下次还弹
            self.context.storage_state(path=self.state_path)
            print("  [状态保存] 身份令牌已更新至本地。")

    def scrape_product(self, url):
        """采集单个产品详情"""
        print(f"\n[任务] 开始采集：{url}")
        self.human_delay(4, 10)
        
        try:
            self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
            self.mouse_jitter()
            self.check_and_wait_for_user()
            
            # 模拟向下滚动阅读
            print("  [仿真模拟] 模拟阅读页面...")
            for i in range(1, 4):
                self.page.evaluate(f"window.scrollBy(0, {random.randint(300, 600)})")
                time.sleep(random.uniform(1, 3))

            # 提取核心数据
            data = {
                "url": url,
                "title": self.page.title(),
                "price": self.page.locator(".price-text, .offer-current-price").first.inner_text() if self.page.locator(".price-text, .offer-current-price").count() > 0 else "N/A",
                "company": self.page.locator(".company-name, .supplier-info-name").first.inner_text() if self.page.locator(".company-name, .supplier-info-name").count() > 0 else "N/A",
                "specs": []
            }
            
            # 抓取表格参数
            specs = self.page.locator(".prop-item").all_inner_texts()
            data["specs"] = [s.replace("\n", ": ").strip() for s in specs]
            
            print(f"  [成功] 提取到厂家：{data['company']}")
            self.results.append(data)
            return True
        except Exception as e:
            print(f"  [失败] 采集出错：{str(e)}")
            return False

    def close(self):
        if self.browser:
            # 最后再存一次，确保最新
            self.context.storage_state(path=self.state_path)
            self.browser.close()
        self.playwright.stop()

def main():
    urls = [
        "https://detail.1688.com/offer/653063544321.html", # MagSafe 磁吸环
        "https://detail.1688.com/offer/677021423343.html", # 卓效五金
        "https://detail.1688.com/offer/625345678901.html", # 圆形铁片
        "https://detail.1688.com/offer/589765432101.html"  # 车载支架
    ]
    
    scraper = Safe1688Scraper(headless=False)
    scraper.start()
    
    try:
        count = 0
        for url in urls:
            if scraper.scrape_product(url):
                count += 1
            # 每采三个大休息一次，防止被标记
            if count % 3 == 0:
                print("\n[安全防护] 已连续采集 3 个，强制进行长休息 30 秒...")
                time.sleep(30)
        
        print(f"\n采集完成！共计获取 {len(scraper.results)} 条数据。")
        # 保存结果
        with open("引磁片采集结果.json", "w", encoding="utf-8") as f:
            json.dump(scraper.results, f, ensure_ascii=False, indent=2)
            
    finally:
        scraper.close()

if __name__ == "__main__":
    main()
