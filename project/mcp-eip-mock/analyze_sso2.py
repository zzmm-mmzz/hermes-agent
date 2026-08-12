"""
EIP 门户 - ISC SSO 登录（实际 SSO 服务器地址）
"""
import requests
import json
import re
import urllib.parse

SSO_BASE = "http://tyqxiscsso.hn.sgcc.com.cn:38080/isc_sso"
EIP_PORTAL = "http://eip.hn.sgcc.com.cn/portal"
USERNAME = "hej80"
PASSWORD = "hejie.1161"

session = requests.Session()

# 1. 访问门户触发 SSO 跳转，获取 service
print("=== 1. 获取 SSO 登录 URL ===")
resp = session.get(f"{EIP_PORTAL}/", allow_redirects=True, timeout=15)
print(f"最终URL: {resp.url}")
print(f"Cookies: {dict(session.cookies)}")

# 从 URL 提取 service 参数
parsed = urllib.parse.urlparse(resp.url)
params = urllib.parse.parse_qs(parsed.query)
service = params.get("service", [""])[0]
print(f"service: {service}")

# 2. 获取 SSO 登录页面
print("\n=== 2. 获取 SSO 登录页面 ===")
resp = session.get(resp.url, timeout=15)
html = resp.text
print(f"状态码: {resp.status_code}")
print(f"响应大小: {len(html)} bytes")
print(f"Cookies: {dict(session.cookies)}")

# 保存页面
with open("sso_login.html", "w", encoding="utf-8") as f:
    f.write(html)
print("页面已保存")

# 3. 分析登录表单
print("\n=== 3. 分析登录表单 ===")

# 找 form action
form_actions = re.findall(r'<form[\s\S]*?</form>', html, re.IGNORECASE)
print(f"找到 {len(form_actions)} 个表单")

# 提取所有 input
inputs = re.findall(r'<input[^>]+>', html)
for inp in inputs:
    name_m = re.search(r'name=[\"\']([^\"\']+)[\"\']', inp)
    type_m = re.search(r'type=[\"\']([^\"\']+)[\"\']', inp)
    val_m = re.search(r'value=[\"\']([^\"\']*)[\"\']', inp)
    name = name_m.group(1) if name_m else "?"
    itype = type_m.group(1) if type_m else "?"
    val = val_m.group(1) if val_m else ""
    print(f"  <input type={itype} name={name} value={val}")

# 找 form action
action_m = re.search(r'<form[^>]*action=[\"\']([^\"\']+)[\"\']', html)
if action_m:
    print(f"\n表单 action: {action_m.group(1)}")

# 找 JS 中的关键逻辑
js_login = re.findall(r'(login|submit|ajax|fetch|axios|\.post|\.get)\s*\([^)]*\)', html)
print(f"\nJS 调用: {len(js_login)} 个")

# 找 scripts
scripts = re.findall(r'<script[^>]*src=[\"\']([^\"\']+\.js)[\"\']', html)
for s in scripts:
    print(f"  JS: {s}")

# 找所有链接
links = re.findall(r'<a[^>]+>([^<]+)</a>', html)
for link in links:
    print(f"  链接: {link.strip()}")
