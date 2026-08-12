"""
EIP 门户 - 使用 Playwright 自动化登录获取 Cookie
"""
import asyncio
import json
import re
import os
import sys
import time

# 尝试导入 Playwright
try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Playwright 未安装，尝试安装...")
    os.system("pip install playwright && playwright install chromium")
    from playwright.async_api import async_playwright

SSO_BASE = "http://tyqxiscsso.hn.sgcc.com.cn:38080/isc_sso"
EIP_PORTAL = "http://eip.hn.sgcc.com.cn/portal"
USERNAME = "hej80"
PASSWORD = "hejie.1161"


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            ignore_https_errors=True,
        )

        page = await context.new_page()

        try:
            # 第一步：访问 EIP 门户，自动跳转到 SSO
            print("=== 1. 访问 EIP 门户 ===")
            await page.goto(f"{EIP_PORTAL}/", wait_until="networkidle", timeout=30000)
            print(f"当前 URL: {page.url}")

            # 等待登录页面加载
            await page.wait_for_load_state("networkidle", timeout=15000)

            # 第二步：填写登录表单
            print("\n=== 2. 填写登录表单 ===")

            # 等待账号输入框出现
            try:
                await page.wait_for_selector("#user_tag", timeout=10000)
                print("账号输入框已找到")
            except:
                print("页面源代码:")
                print(await page.content())
                raise

            # 填写账号
            await page.fill("#user_tag", USERNAME)
            print(f"已填写账号: {USERNAME}")

            # 填写密码
            await page.fill("#user_pd", PASSWORD)
            print("已填写密码")

            # 点击"记住账号"复选框（可选）
            try:
                await page.check("#checkAcc")
                print("已勾选记住账号")
            except:
                pass

            # 第三步：提交登录
            print("\n=== 3. 提交登录 ===")

            # 监听导航和响应
            async with context.expect_page() as page_info:
                pass

            # 点击登录按钮
            await page.click("#submi")

            # 等待页面跳转（登录成功后重定向回 EIP）
            print("等待登录完成...")

            # 等待最多 15 秒，看是否跳转
            try:
                await page.wait_for_url("**/portal/**", timeout=15000)
                print(f"登录成功！跳转到: {page.url}")
            except:
                # 检查是否还在登录页 - 可能是验证码弹窗
                current_url = page.url
                print(f"当前 URL: {current_url}")

                # 检查页面内容
                content = await page.content()

                if "验证码" in content or "captcha" in content.lower():
                    print("需要验证码！停止。")
                    await page.screenshot(path="captcha_needed.png")
                    print("验证码截图已保存: captcha_needed.png")

                    # 尝试查看是否有任何错误提示
                    error_elem = await page.query_selector("#getApVerifyCodeMsg")
                    if error_elem:
                        error_text = await error_elem.inner_text()
                        print(f"错误提示: {error_text}")

                    return None

                # 检查错误信息
                error_elem = await page.query_selector("#getApVerifyCodeMsg")
                if error_elem:
                    error_text = await error_elem.inner_text()
                    print(f"错误提示: {error_text}")

                await page.screenshot(path="login_failed.png")
                print("登录失败截图已保存: login_failed.png")
                return None

            # 第四步：获取所有 Cookie
            print("\n=== 4. 获取 Cookie ===")
            all_cookies = await context.cookies()
            cookie_dict = {c["name"]: c["value"] for c in all_cookies}
            cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in all_cookies])

            print(f"Cookie 数量: {len(all_cookies)}")
            for c in all_cookies:
                print(f"  {c['name']} = {c['value'][:50]}... (domain: {c['domain']})")

            print(f"\n完整 Cookie 字符串:\n{cookie_str}")

            # 第五步：验证 - 访问任务列表接口
            print("\n=== 5. 验证登录 - 访问任务列表 ===")
            task_url = f"{EIP_PORTAL}/portal_ext/rest/task/listHis?pageSize=5"
            resp = await page.evaluate(f"""
                fetch('{task_url}', {{
                    headers: {{
                        'Accept': 'application/json, text/plain, */*',
                        'Referer': '{EIP_PORTAL}/'
                    }}
                }}).then(r => r.text())
            """)
            print(f"任务列表响应(前500字符):\n{resp[:500]}")

            # 尝试解析 JSON
            try:
                data = json.loads(resp)
                print(f"\nJSON 解析成功: code={data.get('code')}, message={data.get('message')}")
            except:
                print("\n响应不是 JSON 格式")

            return {"cookies": cookie_dict, "cookie_str": cookie_str}

        except Exception as e:
            print(f"\n错误: {e}")
            import traceback
            traceback.print_exc()
            try:
                await page.screenshot(path="error_screenshot.png")
                print("错误截图已保存: error_screenshot.png")
            except:
                pass
            return None

        finally:
            await browser.close()


if __name__ == "__main__":
    result = asyncio.run(main())
    if result:
        # 保存 Cookie 到文件
        output = {
            "cookie_str": result["cookie_str"],
            "cookies": result["cookies"],
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        with open("eip_cookies.json", "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"\nCookie 已保存到 eip_cookies.json")
        print(f"\n最终 Cookie 字符串:\n{result['cookie_str']}")
    else:
        print("\n登录失败")
