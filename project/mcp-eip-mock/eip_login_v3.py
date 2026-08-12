"""
EIP SSO 登录 V3 - 修正加密逻辑
根据前端代码分析：
- 密码: aostaritEncryptUtils.string.encrypt(userPwd, true) -> 强制 RSA 加密（IE8模式）
- 账号: aostaritEncryptUtils.string.encrypt(encodeURIComponent(userTag)) -> smPass=false, 不加密 -> 返回 URI encoded 原文
"""
import requests
import json
import re
import random
import string
import hashlib
import time
import urllib.parse
import sys


def rsa_encrypt(modulus_hex, exponent_hex, plaintext):
    """
    模拟前端 RSAUtils.encryptedString 逻辑:
    1. 字符串转 charCodes 数组
    2. 补齐到 chunkSize 倍数
    3. 每2个byte组成一个digit
    4. powMod 加密
    5. 结果 hex 空格拼接
    """
    modulus = int(modulus_hex, 16)
    exponent = int(exponent_hex, 16)

    # chunkSize = biHighIndex(m) * 2
    m_digits = (modulus.bit_length() + 15) // 16
    chunk_size = (m_digits - 1) * 2

    # 转 char codes
    a = [ord(c) for c in plaintext]

    # 补齐
    while len(a) % chunk_size != 0:
        a.append(0)

    result_parts = []
    for i in range(0, len(a), chunk_size):
        # 构建 block (每2个byte -> 1个16-bit digit)
        block_int = 0
        for k in range(i, i + chunk_size, 2):
            val = a[k]
            if k + 1 < len(a):
                val += a[k + 1] << 8
            block_int = (block_int << 16) | val

        # powMod
        encrypted = pow(block_int, exponent, modulus)

        # biToHex
        hex_str = hex(encrypted)[2:]
        if len(hex_str) % 2:
            hex_str = "0" + hex_str

        result_parts.append(hex_str)

    return " ".join(result_parts)


def md5(s):
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def get_random_string(length):
    chars = string.ascii_letters + string.digits
    return "".join(random.choice(chars) for _ in range(length))


def get_uid():
    import uuid
    return uuid.uuid4().hex


SSO_BASE = "http://tyqxiscsso.hn.sgcc.com.cn:38080"
EIP_PORTAL = "http://eip.hn.sgcc.com.cn/portal"
USERNAME = "hej80"
PASSWORD = "hejie.1161"

session = requests.Session()

# 1. 访问门户触发 SSO
print("=== 1. 访问 EIP 门户 ===")
resp = session.get(f"{EIP_PORTAL}/", allow_redirects=False, timeout=15)
login_url = resp.headers.get("Location", "")
print(f"SSO URL: {login_url}")

# 2. 获取 SSO 页面
print("\n=== 2. 获取 SSO 登录页 ===")
resp = session.get(login_url, timeout=15)
html = resp.text

key_match = re.search(r'encryptKey:\s*"([^"]+)"', html)
if not key_match:
    print("未找到 encryptKey")
    sys.exit(1)

encrypt_key = key_match.group(1)
parts = encrypt_key.split("#")
modulus_hex = parts[0]
exponent_hex = parts[1] if len(parts) > 1 else "010001"

app_id = re.search(r'name="appId"\s+value="([^"]+)"', html)
app_id = app_id.group(1) if app_id else ""

execution = re.search(r'name="execution"\s+value="([^"]+)"', html)
execution = execution.group(1) if execution else "e1s1"

print(f"appId: {app_id}, execution: {execution}")

# 3. 构造提交数据（根据前端实际逻辑）
print("\n=== 3. 构造表单数据 ===")

# 账号：直接传 encodeURIComponent 后的值（smPass=false 不加密）
username_value = urllib.parse.quote(USERNAME, safe='')
print(f"账号值: {username_value} (明文, URI encoded)")

# 密码：强制 RSA 加密 (IE8 模式: md5 + random8 + 明文)
random8 = get_random_string(8)
password_plain = md5(PASSWORD) + random8 + PASSWORD
encrypted_password = rsa_encrypt(modulus_hex, exponent_hex, password_plain)
print(f"密码(加密后前100): {encrypted_password[:100]}...")

# 防重放
request_time = str(int(time.time() * 1000))
nonce = get_uid()
sign = md5(request_time + "," + nonce)

# 4. 提交登录
print("\n=== 4. 提交登录 ===")
form_data = {
    "appId": app_id,
    "authMode": "ACCOUNT_PASSWORD",
    "username": username_value,
    "password": encrypted_password,
    "captchaPattern": "embed",
    "execution": execution,
    "_eventId": "submit",
    "messageCode": "",
    "requestTime": request_time,
    "nonce": nonce,
    "sign": sign,
}

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": login_url,
    "Origin": SSO_BASE,
}

resp = session.post(login_url, data=form_data, headers=headers,
                    allow_redirects=False, timeout=30)

print(f"状态码: {resp.status_code}")
print(f"Location: {resp.headers.get('Location', '无')}")

# 5. 处理重定向
count = 0
current_resp = resp
while current_resp.status_code in (301, 302, 303, 307, 308) and count < 10:
    next_url = current_resp.headers.get("Location", "")
    print(f"重定向到: {next_url}")
    current_resp = session.get(next_url, allow_redirects=False, timeout=15)
    print(f"状态码: {current_resp.status_code}")
    count += 1

print(f"\n最终 URL: {current_resp.url}")

if "eip.hn.sgcc.com.cn" in current_resp.url:
    print("==> 登录成功！")

# 6. Cookie
print("\n=== Cookie ===")
cookie_dict = requests.utils.dict_from_cookiejar(session.cookies)
cookie_str = "; ".join([f"{k}={v}" for k, v in cookie_dict.items()])
print(f"Cookie: {cookie_str}")

# 7. 验证登录 - 访问任务列表
print("\n=== 5. 验证 - 任务列表 ===")
task_url = f"{EIP_PORTAL}/portal_ext/rest/task/listHis?pageSize=5"
task_resp = session.get(task_url, headers={
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": f"{EIP_PORTAL}/",
}, timeout=15)

print(f"状态码: {task_resp.status_code}")
print(f"响应(前500): {task_resp.text[:500]}")

# 如果成功，保存 Cookie
if "eip.hn.sgcc.com.cn" in current_resp.url:
    output = {
        "cookie_str": cookie_str,
        "cookies": cookie_dict,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open("eip_cookies.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\nCookie 已保存到 eip_cookies.json")
