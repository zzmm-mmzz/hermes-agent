"""
EIP 门户后台登录脚本
通过 requests 模拟登录获取 Cookie
"""
import requests
import json
import sys

BASE_URL = "http://eip.hn.sgcc.com.cn/portal"
SESSION = requests.Session()

# 1. 先访问首页获取必要的会话信息
print("=== 1. 访问门户首页 ===")
try:
    resp = SESSION.get(BASE_URL, timeout=15)
    print(f"状态码: {resp.status_code}")
    print(f"Cookies: {dict(SESSION.cookies)}")
    print(f"响应头: {dict(resp.headers)}")
except Exception as e:
    print(f"首页访问失败: {e}")
    sys.exit(1)

# 2. 尝试常见的登录接口
LOGIN_URLS = [
    f"{BASE_URL}/login",
    f"{BASE_URL}/portal/login",
    f"{BASE_URL}/portal_ext/rest/login",
    f"{BASE_URL}/portal_ext/rest/user/login",
    f"{BASE_URL}/sso/login",
    f"{BASE_URL}/cas/login",
]

USERNAME = "hej80"
PASSWORD = "hejie.1161"

for login_url in LOGIN_URLS:
    print(f"\n=== 尝试登录: {login_url} ===")
    try:
        payload = {
            "username": USERNAME,
            "password": PASSWORD,
            "j_username": USERNAME,
            "j_password": PASSWORD,
            "account": USERNAME,
            "userAccount": USERNAME,
            "j_username": USERNAME,
            "j_password": PASSWORD,
        }

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Accept": "application/json, text/plain, */*",
            "Referer": f"{BASE_URL}/",
            "X-Requested-With": "XMLHttpRequest",
        }

        resp = SESSION.post(login_url, data=payload, headers=headers, timeout=15)
        print(f"状态码: {resp.status_code}")
        print(f"响应内容(前500字符): {resp.text[:500]}")
        print(f"Cookies: {dict(SESSION.cookies)}")

        if resp.status_code == 200:
            # 检查响应是否表示成功
            try:
                data = resp.json()
                print(f"JSON响应: {json.dumps(data, ensure_ascii=False, indent=2)[:500]}")
            except:
                pass
    except Exception as e:
        print(f"登录失败: {e}")

# 3. 尝试保存完整的 Cookie
print("\n=== 最终 Cookies ===")
cookies_jar = SESSION.cookies
cookie_dict = requests.utils.dict_from_cookiejar(cookies_jar)
cookie_str = "; ".join([f"{k}={v}" for k, v in cookie_dict.items()])
print(f"Cookie: {cookie_str}")
print(f"Cookie 字典: {json.dumps(cookie_dict, ensure_ascii=False, indent=2)}")

# 4. 尝试访问需要登录的接口
if cookie_str:
    print("\n=== 尝试访问任务列表接口 ===")
    task_url = f"{BASE_URL}/portal_ext/rest/task/listHis?pageSize=5"
    try:
        resp = SESSION.get(task_url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": f"{BASE_URL}/",
        }, timeout=15)
        print(f"状态码: {resp.status_code}")
        print(f"响应(前500字符): {resp.text[:500]}")
    except Exception as e:
        print(f"请求失败: {e}")
