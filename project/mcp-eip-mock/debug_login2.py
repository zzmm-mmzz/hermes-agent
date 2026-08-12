"""
EIP SSO - 检查登录失败原因
使用完整 POST 后检查错误提示
"""
import requests
import re
import hashlib
import time
import urllib.parse
import json as json_lib

USERNAME = "hej80"
PASSWORD = "hejie.1161"
EIP_PORTAL = "http://eip.hn.sgcc.com.cn/portal"
SSO_BASE = "http://tyqxiscsso.hn.sgcc.com.cn:38080"

def md5(s):
    return hashlib.md5(s.encode("utf-8")).hexdigest()

def get_uid():
    import uuid
    return uuid.uuid4().hex

def rsa_encrypt(modulus_hex, exponent_hex, plaintext):
    modulus = int(modulus_hex, 16)
    exponent = int(exponent_hex, 16)
    m_digits = (modulus.bit_length() + 15) // 16
    chunk_size = (m_digits - 1) * 2

    a = [ord(c) for c in plaintext]
    while len(a) % chunk_size != 0:
        a.append(0)

    result_parts = []
    for i in range(0, len(a), chunk_size):
        block_int = 0
        for k in range(i, i + chunk_size, 2):
            val = a[k]
            if k + 1 < len(a):
                val += a[k + 1] << 8
            block_int = (block_int << 16) | val
        encrypted = pow(block_int, exponent, modulus)
        hex_str = hex(encrypted)[2:]
        if len(hex_str) % 2:
            hex_str = "0" + hex_str
        result_parts.append(hex_str)
    return " ".join(result_parts)

session = requests.Session()

# Get login page
resp = session.get(f"{EIP_PORTAL}/", allow_redirects=False, timeout=15)
login_url = resp.headers.get("Location", "")

resp = session.get(login_url, timeout=15)
html = resp.text

key_match = re.search(r'encryptKey:\s*"([^"]+)"', html)
encrypt_key = key_match.group(1)
parts = encrypt_key.split("#")
modulus_hex = parts[0]
exponent_hex = parts[1] if len(parts) > 1 else "010001"

app_id = re.search(r'name="appId"\s+value="([^"]+)"', html).group(1)
execution = re.search(r'name="execution"\s+value="([^"]+)"', html).group(1)

# Encrypt
import random
import string
random8 = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(8))
password_plain = md5(PASSWORD) + random8 + PASSWORD
encrypted_password = rsa_encrypt(modulus_hex, exponent_hex, password_plain)

request_time = str(int(time.time() * 1000))
nonce = get_uid()
sign = md5(request_time + "," + nonce)

# 提交
form_data = {
    "appId": app_id,
    "authMode": "ACCOUNT_PASSWORD",
    "username": urllib.parse.quote(USERNAME, safe=''),
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

print(f"Status: {resp.status_code}")
print(f"Location: {resp.headers.get('Location', 'none')}")
print(f"Set-Cookie: {resp.headers.get('Set-Cookie', 'none')}")

# 检查响应中是否包含错误信息
html_resp = resp.text

# 找错误提示
error_match = re.search(r'id="getApVerifyCodeMsg"[^>]*>(.*?)</div>', html_resp, re.DOTALL)
if error_match:
    err_content = error_match.group(1).strip()
    if err_content:
        print(f"\nError msg: {err_content}")

# 看是否有验证码弹窗
for pat in ['验证码', '滑块', 'captcha', '验证', '错误']:
    if pat in html_resp:
        for m in re.finditer(f'.{{0,50}}{pat}.{{0,80}}', html_resp):
            print(f"  Found '{pat}': ...{m.group()}...")

# 看看是否有 message 或 error 相关的 hidden input
for m in re.finditer(r'<input[^>]*message[^>]*>', html_resp, re.IGNORECASE):
    print(f"Message input: {m.group()}")

# 也尝试检查 SM3/SM2 加密模式（非 IE8）
print("\n\n--- 尝试 SM2/SM3 加密模式 ---")
# 检查 smPass 的值
sm_pass_match = re.search(r'smPass:\s*(true|false)', html)
sm_pass = sm_pass_match.group(1) if sm_pass_match else "unknown"
print(f"smPass: {sm_pass}")

is_ie8_match = re.search(r'isIE8:\s*(true|false)', html)
is_ie8 = is_ie8_match.group(1) if is_ie8_match else "unknown"
print(f"isIE8: {is_ie8}")

# 如果 smPass = false 但实际是 SM 模式，那就尝试 SM2/SM3
# 先检查脚本文件中关于 SM2 的函数
print("\n检查 SM2/SM3 函数...")
sm2_check = re.search(r'(do_sm2_encrypt|do_sm3_encrypt)', html)
print(f"Has SM2/SM3 in page: {sm2_check is not None}")
