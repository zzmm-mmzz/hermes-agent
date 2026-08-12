"""
EIP 门户 - ISC SSO 登录分析脚本
"""
import requests
import json
import re
import urllib.parse

BASE_URL = "http://eip.hn.sgcc.com.cn"
SSO_BASE = f"{BASE_URL}/isc_sso"

session = requests.Session()

# 1. 访问门户首页，看是否有 SSO 跳转
print("=== 1. 访问门户首页，跟踪重定向 ===")
resp = session.get(f"{BASE_URL}/portal/", allow_redirects=True, timeout=15)
print(f"最终URL: {resp.url}")
print(f"状态码: {resp.status_code}")
print(f"Cookies: {dict(session.cookies)}")

# 检查是否跳转到了 SSO 登录页
if "isc_sso" in resp.url:
    print("-> 已跳转到 SSO 登录页")

# 2. 查看 SSO 登录页面的表单信息
print("\n=== 2. 访问 SSO 登录页面 ===")
login_page_url = f"{SSO_BASE}/login"
resp = session.get(login_page_url, timeout=15)
print(f"状态码: {resp.status_code}")
print(f"URL: {resp.url}")
print(f"Cookies: {dict(session.cookies)}")

# 提取表单字段
html = resp.text

# 找 form 的 action
form_action = re.search(r'<form[^>]*action=[\"\']([^\"\']+)[\"\']', html)
if form_action:
    print(f"表单 action: {form_action.group(1)}")

# 找 input 隐藏字段
inputs = re.findall(r'<input[^>]*name=[\"\']([^\"\']+)[\"\']\s*value=[\"\']([^\"\']*)[\"\']', html)
print(f"隐藏字段: {inputs}")

# 找所有 input 标签（包括 type=password, type=text）
all_inputs = re.findall(r'<input[^>]+>', html)
for inp in all_inputs:
    name = re.search(r'name=[\"\']([^\"\']+)[\"\']', inp)
    inp_type = re.search(r'type=[\"\']([^\"\']+)[\"\']', inp)
    if name and inp_type:
        print(f"  input: type={inp_type.group(1)}, name={name.group(1)}")

# 找 JS 中可能引用的接口
js_refs = re.findall(r'(login|submit|auth|token|captcha|check)[^\"\'\\s]*', html, re.IGNORECASE)
print(f"\nJS 相关关键词: {set(js_refs)}")

# 保存页面供分析
with open("sso_login_page.html", "w", encoding="utf-8") as f:
    f.write(html)
print(f"\n登录页面已保存: sso_login_page.html ({len(html)} bytes)")

# 3. 尝试找到 API 端点 - 检查常见的 SSO REST 接口
print("\n=== 3. 探测 SSO API ===")
api_endpoints = [
    "/isc_sso/oauth2/authorize",
    "/isc_sso/oauth2/token",
    "/isc_sso/api/login",
    "/isc_sso/api/authentication",
    "/isc_sso/login/authenticate",
    "/isc_sso/rest/login",
    "/isc_sso/rest/authenticate",
    "/isc_sso/sso/login",
    "/isc_sso/check",
    "/isc_sso/validate",
]

for path in api_endpoints:
    url = f"{BASE_URL}{path}"
    try:
        resp2 = session.get(url, timeout=8)
        if resp2.status_code not in [404]:
            print(f"  [{resp2.status_code}] {path} - {resp2.text[:200]}")
    except:
        pass
