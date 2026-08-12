"""查询 EIP 邮件列表"""
import requests
import json

EIP_PORTAL = "http://eip.hn.sgcc.com.cn/portal"

# 读取已保存的 Cookie
with open("eip_cookies.json", "r", encoding="utf-8") as f:
    saved = json.load(f)

cookie_str = saved["cookie_str"]

# 构建 session 并设置 Cookie
session = requests.Session()
for item in cookie_str.split("; "):
    if "=" in item:
        k, v = item.split("=", 1)
        session.cookies.set(k, v, domain="eip.hn.sgcc.com.cn")

# 请求邮件接口
url = f"{EIP_PORTAL}/portal_ext/rest/mailNew/queryUserMail?robot="
payload = {
    "appId": "mailAppId",
    "pageNo": 1,
    "pageSize": 50,
    "status": "",
}

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Accept": "application/json, text/plain, */*",
    "Referer": f"{EIP_PORTAL}/",
    "X-Requested-With": "XMLHttpRequest",
}

resp = session.post(url, data=payload, headers=headers, timeout=15)

print(f"状态码: {resp.status_code}")
print(f"Content-Type: {resp.headers.get('Content-Type', '')}")

# 解析 JSON
try:
    data = resp.json()
    print(f"\n响应结构: {json.dumps(data, ensure_ascii=False, indent=2)[:2000]}")
except:
    print(f"\n响应(前500): {resp.text[:500]}")
