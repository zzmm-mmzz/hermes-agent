"""
EIP SSO 登录 - 调试验证模式
逐步验证每个步骤
"""
import requests
import json
import re
import hashlib
import time
import urllib.parse
import sys

USERNAME = "hej80"
PASSWORD = "hejie.1161"
EIP_PORTAL = "http://eip.hn.sgcc.com.cn/portal"
SSO_BASE = "http://tyqxiscsso.hn.sgcc.com.cn:38080"

session = requests.Session()

# 访问门户
resp = session.get(f"{EIP_PORTAL}/", allow_redirects=False, timeout=15)
login_url = resp.headers.get("Location", "")
print(f"1. SSO URL: {login_url}")

# 获取登录页
resp = session.get(login_url, timeout=15)
html = resp.text

# 提取关键参数
key_match = re.search(r'encryptKey:\s*"([^"]+)"', html)
encrypt_key = key_match.group(1)
parts = encrypt_key.split("#")
modulus_hex = parts[0]
exponent_hex = parts[1] if len(parts) > 1 else "010001"
app_id = re.search(r'name="appId"\s+value="([^"]+)"', html).group(1)
execution = re.search(r'name="execution"\s+value="([^"]+)"', html).group(1)

print(f"2. Params: appId={app_id}, execution={execution}")
print(f"   Modulus bits: {int(modulus_hex, 16).bit_length()}")

# 检查登录页中是否有任何隐藏的 error/message 字段
msg_match = re.search(r'id="getApVerifyCodeMsg"[^>]*>(.*?)</div>', html, re.DOTALL)
if msg_match:
    msg_content = msg_match.group(1).strip()
    print(f"   Error msg initial: '{msg_content}'")

# 检查 form action
action_match = re.search(r'<form[^>]*action=[\"\']([^\"\']*)[\"\']', html)
form_action = action_match.group(1) if action_match else ""
print(f"3. Form action: '{form_action}'")

# 检查实际的 form 提交 URL
# 如果 form action 为空，则提交到当前 URL
if form_action:
    submit_url = urllib.parse.urljoin(login_url, form_action)
else:
    submit_url = login_url

print(f"   Submit URL: {submit_url}")

# 保存当前 cookies
current_cookies = requests.utils.dict_from_cookiejar(session.cookies)
print(f"4. Current cookies: {current_cookies}")

# 尝试先用 GET 方式访问提交 URL 来检查 service ticket 机制
print(f"\n5. 尝试直接访问带 ticket 的 callback URL...")
# SSO 登录成功后应该回调 service URL
service_url = re.search(r'service=([^&]+)', login_url)
if service_url:
    decoded_service = urllib.parse.unquote(service_url.group(1))
    print(f"   Service URL: {decoded_service}")
    resp2 = session.get(decoded_service, allow_redirects=False, timeout=15)
    print(f"   Status: {resp2.status_code}, URL: {resp2.url}")

# 尝试另一种方式 - 直接用密码尝试 HTTP Basic Auth
print(f"\n6. 尝试 Basic Auth...")
basic_url = f"{EIP_PORTAL}/portal_ext/rest/task/listHis?pageSize=3"
resp3 = session.get(basic_url, auth=(USERNAME, PASSWORD), timeout=15)
print(f"   Status: {resp3.status_code}")
print(f"   Response(200chars): {resp3.text[:200]}")

# 检查 EIP 的 portal_um 接口
print(f"\n7. 检查 portal login 接口...")
um_url = re.search(r'service=http[^&]+', login_url)
if um_url:
    um_full = urllib.parse.unquote(um_url.group(0).replace('service=', ''))
    print(f"   UM URL: {um_full}")
    resp4 = session.get(um_full, allow_redirects=False, timeout=15)
    print(f"   Status: {resp4.status_code}")
    if resp4.status_code == 302:
        print(f"   Location: {resp4.headers.get('Location', '')}")
