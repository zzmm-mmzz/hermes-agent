"""
EIP SSO 登录 - Python RSA 加密模拟
实现前端 JS 的加密逻辑（IE8 模式）：RSAUtils.encryptedString
"""
import requests
import json
import re
import math
import random
import string
import hashlib
import time
import urllib.parse
from datetime import datetime

SSO_BASE = "http://tyqxiscsso.hn.sgcc.com.cn:38080/isc_sso"
EIP_PORTAL = "http://eip.hn.sgcc.com.cn/portal"
USERNAME = "hej80"
PASSWORD = "hejie.1161"

# ── RSA 实现（兼容前端 RsaUtils.js 的加密逻辑）──

class BigInt:
    """模拟 JS 的 BigInt"""
    def __init__(self, digits=None):
        self.digits = digits or [0] * 130
        self.isNeg = False

    def copy(self):
        r = BigInt()
        r.digits = self.digits[:]
        r.isNeg = self.isNeg
        return r


def bi_from_number(i):
    result = BigInt()
    result.isNeg = i < 0
    i = abs(i)
    j = 0
    while i > 0:
        result.digits[j] = i & 0xFFFF
        i = math.floor(i / 65536)
        j += 1
    return result


def bi_high_index(x):
    for i in range(len(x.digits) - 1, -1, -1):
        if x.digits[i] != 0:
            return i
    return -1


def bi_num_digits(x):
    return bi_high_index(x) + 1


def bi_compare(x, y):
    if x.isNeg != y.isNeg:
        return 1 - 2 * (1 if x.isNeg else 0)
    for i in range(bi_num_digits(x) - 1, -1, -1):
        if x.digits[i] != y.digits[i]:
            if x.isNeg:
                return 1 - 2 * (1 if x.digits[i] > y.digits[i] else 0)
            else:
                return 1 - 2 * (1 if x.digits[i] < y.digits[i] else 0)
    return 0


def bi_add(x, y):
    result = BigInt()
    n = max(bi_num_digits(x), bi_num_digits(y))
    carry = 0
    for i in range(n):
        digit = x.digits[i] + y.digits[i] + carry
        result.digits[i] = digit & 0xFFFF
        carry = digit >> 16
    if carry:
        result.digits[n] = carry
    return result


def bi_subtract(x, y):
    result = BigInt()
    n = bi_num_digits(x)
    borrow = 0
    for i in range(n):
        digit = x.digits[i] - borrow - (y.digits[i] if i < len(y.digits) else 0)
        if digit < 0:
            digit += 0x10000
            borrow = 1
        else:
            borrow = 0
        result.digits[i] = digit
    return result


def bi_multiply_digit(x, y):
    n = bi_num_digits(x)
    result = BigInt()
    carry = 0
    for i in range(n):
        digit = x.digits[i] * y + carry
        result.digits[i] = digit & 0xFFFF
        carry = digit >> 16
    if carry:
        result.digits[n] = carry
    return result


def bi_multiply(x, y):
    result = BigInt()
    n = bi_num_digits(x)
    for i in range(n):
        if x.digits[i] == 0:
            continue
        carry = 0
        for j in range(bi_num_digits(y)):
            digit = result.digits[i + j] + x.digits[i] * y.digits[j] + carry
            result.digits[i + j] = digit & 0xFFFF
            carry = digit >> 16
        result.digits[i + n] = carry
    return result


def bi_divide_modulo(x, y):
    n = bi_num_digits(x)
    m = bi_num_digits(y)
    if m == 0:
        raise ValueError("Division by zero")
    if n < m:
        return (BigInt(), x.copy())

    result = BigInt()
    result.digits[n - m] = 0
    remaining = x.copy()

    y2 = y.copy()
    for i in range(n - m):
        y2 = bi_multiply_digit(y2, 65536)

    for i in range(n - m, -1, -1):
        if i < n - m:
            y2 = divide_by_digit(y2, 65536)
        q_digit = 0
        if bi_compare(remaining, y2) >= 0:
            q_digit = 1
            remaining = bi_subtract(remaining, y2)
        result.digits[i] = q_digit

    return (result, remaining)


def divide_by_digit(x, d):
    result = BigInt()
    n = bi_num_digits(x)
    remainder = 0
    for i in range(n - 1, -1, -1):
        digit = (remainder << 16) + x.digits[i]
        result.digits[i] = digit // d
        remainder = digit % d
    return result


def bi_mod_pow(x, e, m):
    """简化的模幂运算（针对 tokens=16 的 RSA）"""
    result = bi_from_number(1)
    base = x.copy()
    exp = e.copy()

    while bi_num_digits(exp) > 0 or exp.digits[0] > 0:
        if exp.digits[0] & 1:
            result = bi_mod_multiply(result, base, m)
        exp = shift_right(exp)
        base = bi_mod_multiply(base, base, m)

    return result


def shift_right(x):
    result = BigInt()
    n = bi_num_digits(x)
    for i in range(n):
        result.digits[i] = x.digits[i] >> 1
        if i + 1 < n:
            result.digits[i] |= (x.digits[i + 1] & 1) << 15
    return result


def bi_mod_multiply(x, y, m):
    return bi_mod(bi_multiply(x, y), m)


def bi_mod(x, m):
    _, r = bi_divide_modulo(x, m)
    return r


def bi_from_hex(s):
    result = BigInt()
    sl = len(s)
    for i in range(sl, 0, -4):
        start = max(0, i - 4)
        chunk = int(s[start:i], 16)
        result.digits[(sl - i) // 4] = chunk
    return result


def bi_to_hex(x):
    n = bi_num_digits(x)
    result = ""
    for i in range(n - 1, -1, -1):
        result += f"{x.digits[i]:04x}"
    return result or "0"


def encrypted_string(modulus_hex, exponent_hex, s):
    """模拟 RSAUtils.encryptedString"""
    # chunkSize = biHighIndex(m) * 2
    m = bi_from_hex(modulus_hex)
    chunk_size = bi_high_index(m) * 2

    # 将字符串转成 char codes
    a = [ord(c) for c in s]

    # 补齐到 chunk_size 的倍数
    while len(a) % chunk_size != 0:
        a.append(0)

    # 加密每个 chunk
    result = []
    for i in range(0, len(a), chunk_size):
        block = BigInt()
        j = 0
        for k in range(i, i + chunk_size, 2):
            if k < len(a):
                block.digits[j] = a[k]
                if k + 1 < len(a):
                    block.digits[j] += a[k + 1] << 8
                j += 1

        # powMod
        e = bi_from_hex(exponent_hex)
        crypt = bi_mod_pow(block, e, m)
        result.append(bi_to_hex(crypt))

    return " ".join(result)


def get_random_string(length):
    chars = string.ascii_letters + string.digits + "_-"
    return "".join(random.choice(chars) for _ in range(length))


def md5(s):
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def get_uid():
    import uuid
    return uuid.uuid4().hex


# ── 登录流程 ──

session = requests.Session()

# 1. 访问 EIP 门户，获取 SSO 登录 URL
print("=== 1. 访问 EIP 门户 ===")
resp = session.get(f"{EIP_PORTAL}/", allow_redirects=False, timeout=15)
print(f"状态码: {resp.status_code}")
print(f"Location: {resp.headers.get('Location', '无')}")

# 跟踪重定向
login_url = resp.headers.get("Location", "")
if login_url:
    print(f"\nSSO 登录 URL: {login_url}")

# 2. 获取 SSO 登录页面（获取加密 key 和表单参数）
print("\n=== 2. 获取 SSO 登录页面 ===")
resp = session.get(login_url, timeout=15)
html = resp.text
print(f"状态码: {resp.status_code}")
print(f"Cookies: {dict(session.cookies)}")

# 提取 encryptKey
key_match = re.search(r'encryptKey:\s*"([^"]+)"', html)
if key_match:
    encrypt_key = key_match.group(1)
    print(f"encryptKey: {encrypt_key[:50]}...")
    parts = encrypt_key.split("#")
    modulus_hex = parts[0]
    exponent_hex = parts[1] if len(parts) > 1 else "010001"
    print(f"Modulus: {modulus_hex[:50]}...")
    print(f"Exponent: {exponent_hex}")
else:
    print("未找到 encryptKey")
    sys.exit(1)

# 提取其他表单参数
app_id = re.search(r'name="appId"\s*value="([^"]+)"', html)
app_id = app_id.group(1) if app_id else ""

auth_mode = "ACCOUNT_PASSWORD"
execution = re.search(r'name="execution"\s*value="([^"]+)"', html)
execution = execution.group(1) if execution else "e2s1"

event_id = "submit"
captcha_pattern = re.search(r'name="captchaPattern"\s*value="([^"]+)"', html)
captcha_pattern = captcha_pattern.group(1) if captcha_pattern else "embed"

print(f"appId: {app_id}")
print(f"execution: {execution}")
print(f"captchaPattern: {captcha_pattern}")

# 3. 加密账号和密码
print("\n=== 3. 加密账号密码 ===")

# 密码加密（IE8 模式）：md5(pass) + random8 + pass
random8 = get_random_string(8)
password_plaintext = md5(PASSWORD) + random8 + PASSWORD
print(f"密码原文(前50): {md5(PASSWORD)}{random8}{PASSWORD[:5]}...")

encrypted_password = encrypted_string(modulus_hex, exponent_hex, password_plaintext)
print(f"加密后(前100): {encrypted_password[:100]}...")

# 账号加密：encodeURIComponent(username) 后 RSA 加密
import urllib.parse
username_encoded = urllib.parse.quote(USERNAME, safe='')
username_plaintext = username_encoded  # encodeURIComponent 后直接加密（非 IE8 下无 md5+random 前缀）
# 注意：前端 apLoginCheck 中，账号加密调用 aostaritEncryptUtils.string.encrypt(encodeURIComponent(userTag))
# 但 encrypt 函数里，只有当 smPass == true 时才添加 md5+random 前缀
# 默认 smPass = false，所以直接对 encodeURIComponent 后的字符串进行 RSA 加密
encrypted_username = encrypted_string(modulus_hex, exponent_hex, username_encoded)
print(f"账号加密后(前100): {encrypted_username[:100]}...")

# 4. 构造防重放参数
print("\n=== 4. 构造防重放参数 ===")
request_time = str(int(time.time() * 1000))
nonce = get_uid()
sign_input = request_time + "," + nonce
sign = hashlib.md5(sign_input.encode("utf-8")).hexdigest()
print(f"requestTime: {request_time}")
print(f"nonce: {nonce}")
print(f"sign: {sign}")

# 5. 提交登录
print("\n=== 5. 提交登录表单 ===")

# 获取 SSO 登录页的 URL（不含 service 参数的 form action）
# 提交到包含 service 参数的当前 URL
submit_url = login_url

form_data = {
    "appId": app_id,
    "authMode": auth_mode,
    "username": encrypted_username,
    "password": encrypted_password,
    "captchaPattern": captcha_pattern,
    "execution": execution,
    "_eventId": event_id,
    "messageCode": "",
    "requestTime": request_time,
    "nonce": nonce,
    "sign": sign,
}

print(f"提交 URL: {submit_url}")
print(f"表单数据字段: {list(form_data.keys())}")

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": login_url,
    "Origin": "http://tyqxiscsso.hn.sgcc.com.cn:38080",
}

resp = session.post(submit_url, data=form_data, headers=headers, allow_redirects=False, timeout=30)
print(f"\n响应状态码: {resp.status_code}")
print(f"Location: {resp.headers.get('Location', '无')}")
print(f"Set-Cookie: {resp.headers.get('Set-Cookie', '无')}")
print(f"响应(前300字符): {resp.text[:300]}")

# 6. 跟踪重定向
if resp.status_code in (301, 302, 303, 307, 308):
    redirect_url = resp.headers["Location"]
    print(f"\n重定向到: {redirect_url}")
    resp2 = session.get(redirect_url, headers=headers, allow_redirects=True, timeout=15)
    print(f"重定向后状态码: {resp2.status_code}")
    print(f"最终 URL: {resp2.url}")

    if "eip.hn.sgcc.com.cn" in resp2.url:
        print("登录成功！已跳转回 EIP 门户")
else:
    print(f"\n响应内容(前500): {resp.text[:500]}")
    if "错误" in resp.text or "失败" in resp.text:
        print("登录可能失败，检查响应")
    elif "验证码" in resp.text:
        print("需要验证码")

# 7. 展示最终 Cookie
print("\n=== 6. 最终 Cookie ===")
cookie_dict = requests.utils.dict_from_cookiejar(session.cookies)
cookie_str = "; ".join([f"{k}={v}" for k, v in cookie_dict.items()])
print(f"Cookie: {cookie_str}")

if "eip.hn.sgcc.com.cn" in resp.url if resp.status_code != 302 else False:
    # 保存 Cookie
    output = {
        "cookie_str": cookie_str,
        "cookies": cookie_dict,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open("eip_cookies.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\nCookie 已保存到 eip_cookies.json")
