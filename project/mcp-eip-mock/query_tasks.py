"""查询 EIP 待办列表"""
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

# 请求待办列表接口（GET 方式，带时间戳参数）
url = f"{EIP_PORTAL}/portal_ext/rest/task/listHis?appId=&keyWord=&pageSize=10&_=1785844001844"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": f"{EIP_PORTAL}/",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

resp = session.get(url, headers=headers, timeout=15)

print(f"状态码: {resp.status_code}")
print(f"Content-Type: {resp.headers.get('Content-Type', '')}")

# 解析 JSON
try:
    data = resp.json()
    result = data.get("result", data.get("data", []))
    total = data.get("total", len(result) if isinstance(result, list) else "?")
    print(f"\n总记录数: {total}")
    print(f"返回条数: {len(result) if isinstance(result, list) else '?'}")
    print()

    if isinstance(result, list):
        for i, item in enumerate(result, 1):
            name = item.get("name", item.get("title", "?"))
            app = item.get("appName", "?")
            sender = item.get("sender", item.get("handlerName", "?"))
            time_val = item.get("activeTime", item.get("createTime", "?"))
            status = item.get("statusName", item.get("state", "?"))
            print(f"{i}. [{status}] {name}")
            print(f"   应用: {app}  |  发送人: {sender}  |  时间: {time_val}")
            print()
except Exception as e:
    print(f"解析失败: {e}")
    print(f"响应(前500): {resp.text[:500]}")
