"""
EIP SSO 登录 V4 - 修正 getRandomString 字符集
"""
import requests
import json
import re
import random
import hashlib
import time
import urllib.parse
import sys


def get_random_string(length):
    """与前端一致的随机字符串生成"""
    chars = 'ABCDEFGHJKMNPQRSTWXYZabcdefhijkmnprstwxyz2345678'
    return ''.join(random.choice(chars) for _ in range(length))


def rsa_encrypt(modulus_hex, exponent_hex, plaintext):
    """
    精确模拟前端 RSAUtils.encryptedString
    使用与前端一致的 BigInt LSB-first 表示
    """
    modulus = int(modulus_hex, 16)
    exponent = int(exponent_hex, 16)

    # 计算 chunk_size = 2 * biHighIndex(m)
    mod_digits = []
    h = modulus_hex.lower()
    if h.startswith('0x'):
        h = h[2:]
    for i in range(len(h), 0, -4):
        start = max(0, i - 4)
        mod_digits.append(int(h[start:i], 16))
    bi_high = len(mod_digits) - 1
    chunk_size = 2 * bi_high

    # 转 char codes
    a = [ord(c) for c in plaintext]
    while len(a) % chunk_size != 0:
        a.append(0)

    result_parts = []
    for i in range(0, len(a), chunk_size):
        # 构建 block digits (LSB first)
        block_digits = []
        for k in range(i, i + chunk_size, 2):
            low_byte = a[k]
            high_byte = a[k + 1] if k + 1 < len(a) else 0
            block_digits.append(low_byte | (high_byte << 8))

        # 转为整数 (digits[0] = 最低16位)
        block_int = 0
        for j, d in enumerate(block_digits):
            block_int |= d << (16 * j)

        # powMod
        encrypted = pow(block_int, exponent, modulus)

        # biToHex (从 MSW 到 LSW)
        enc_hex = hex(encrypted)[2:]
        if len(enc_hex) % 2:
            enc_hex = '0' + enc_hex

        # 将 encrypted 转为前端 biToHex 格式
        # 将加密结果转为 digits (LSB first)
        enc_digits = []
        tmp = encrypted
        while tmp > 0:
            enc_digits.append(tmp & 0xFFFF)
            tmp >>= 16

        # 从高 index 到低 index 输出每个 digit 的4位hex
        bi_to_hex_result = ""
        for idx in range(len(enc_digits) - 1, -1, -1):
            bi_to_hex_result += f"{enc_digits[idx]:04x}"
        if not bi_to_hex_result:
            bi_to_hex_result = "0"

        result_parts.append(bi_to_hex_result)

    return " ".join(result_parts)


def md5(s):
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def get_uid():
    import uuid
    return uuid.uuid4().hex


SSO_BASE = "http://tyqxiscsso.hn.sgcc.com.cn:38080"
EIP_PORTAL = "http://eip.hn.sgcc.com.cn/portal"
USERNAME = "hej80"
PASSWORD = "hejie.1161"

session = requests.Session()

# 1. 访问门户
print("=== 1. 访问 EIP 门户 ===")
resp = session.get(f"{EIP_PORTAL}/", allow_redirects=False, timeout=15)
login_url = resp.headers.get("Location", "")
print(f"SSO URL: {login_url}")

# 2. 获取登录页
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

app_id = re.search(r'name="appId"\s+value="([^"]+)"', html).group(1)
execution = re.search(r'name="execution"\s+value="([^"]+)"', html).group(1)

print(f"appId: {app_id}, execution: {execution}")

# 3. 加密
print("\n=== 3. 加密数据 ===")

# 账号：smPass=false 时不加密，直接传 encodeURIComponent
username_value = urllib.parse.quote(USERNAME, safe='')
print(f"账号: {username_value} (明文)")

# 密码：force=true, IE8模式: md5 + random(8) + password
random8 = get_random_string(8)
password_plain = md5(PASSWORD) + random8 + PASSWORD
print(f"random8: {random8}")
print(f"密码原文结构: md5(pwd) + random8 + pwd")
print(f"密码原文长度: {len(password_plain)}")

encrypted_password = rsa_encrypt(modulus_hex, exponent_hex, password_plain)
print(f"密码加密后(前100): {encrypted_password[:100]}...")

# 防重放
request_time = str(int(time.time() * 1000))
nonce = get_uid()
sign = md5(request_time + "," + nonce)

# 4. 提交
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

# 检查错误
html_resp = resp.text
error_match = re.search(r'id="getApVerifyCodeMsg"[^>]*>(.*?)</div>', html_resp, re.DOTALL)
if error_match:
    err = error_match.group(1).strip()
    if err:
        print(f"错误提示: {err}")

# 5. 重定向跟踪
count = 0
current_resp = resp
while current_resp.status_code in (301, 302, 303, 307, 308) and count < 10:
    next_url = current_resp.headers.get("Location", "")
    print(f"重定向到: {next_url}")
    current_resp = session.get(next_url, allow_redirects=False, timeout=15)
    print(f"状态码: {current_resp.status_code}")
    count += 1

print(f"\n最终 URL: {current_resp.url}")

# 6. Cookie
print("\n=== Cookie ===")
cookie_dict = requests.utils.dict_from_cookiejar(session.cookies)
cookie_str = "; ".join([f"{k}={v}" for k, v in cookie_dict.items()])
print(f"Cookie: {cookie_str}")

# 7. 验证
if "eip.hn.sgcc.com.cn" in current_resp.url:
    print("\n登录成功！")
    print("\n=== 验证 - 任务列表 ===")
    task_url = f"{EIP_PORTAL}/portal_ext/rest/task/listHis?pageSize=5"
    task_resp = session.get(task_url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": f"{EIP_PORTAL}/",
    }, timeout=15)
    print(f"状态码: {task_resp.status_code}")
    print(f"响应(前500): {task_resp.text[:500]}")

    output = {
        "cookie_str": cookie_str,
        "cookies": cookie_dict,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open("eip_cookies.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print("\nCookie 已保存到 eip_cookies.json")
else:
    print("\n登录失败 - 未跳转到 EIP 门户")
