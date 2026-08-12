"""
EIP SSO 登录 - Python 内置 RSA 加密
使用 Python int 进行 RSA 运算，与前端 JS 逻辑一致
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
    模拟前端 RSAUtils.encryptedString 的加密逻辑。
    
    前端逻辑：
    1. 将字符串转为 charCodes 数组
    2. chunkSize = biHighIndex(m) * 2 (其中 m = 模数)
    3. 每 chunkSize 个 bytes 组成一个 BigInt（每2个byte放一个digit）
    4. 用 powMod 加密，结果转 hex
    5. 结果用空格拼接
    """
    modulus = int(modulus_hex, 16)
    exponent = int(exponent_hex, 16)

    # 计算 chunkSize = biHighIndex(m) * 2
    # biHighIndex(m) 获取最高非零 digit 的索引
    # digits 使用 16-bit 表示，所以 biHighIndex(m) = (bit_length - 1) // 16
    m_digits_count = (modulus.bit_length() + 15) // 16  # 需要的digit数
    chunk_size = (m_digits_count - 1) * 2  # biHighIndex(m) * 2
    # 如果上面算的不对，直接用 256-bit key 的默认值
    if chunk_size <= 0:
        chunk_size = 30  # 默认值

    # 将字符串转成 char codes
    a = [ord(c) for c in plaintext]

    # 补齐到 chunk_size 的倍数
    while len(a) % chunk_size != 0:
        a.append(0)

    result_parts = []
    for i in range(0, len(a), chunk_size):
        # 构建 block：每2个byte组合成一个16-bit digit
        block_int = 0
        for j in range(chunk_size - 1, -1, -1):
            block_int = (block_int << 8) | (a[i + j] if i + j < len(a) else 0)

        # 注意：前端代码中 block.digits[j] 先赋值为 a[k]，再加 a[k+1]<<8
        # 所以 low byte 在前，high byte 在后
        # 重新实现：
        block_int2 = 0
        for k in range(i, i + chunk_size, 2):
            val = a[k]
            if k + 1 < len(a):
                val += a[k + 1] << 8
            block_int2 = (block_int2 << 16) | val

        # RSA 加密 powMod = pow(block, e) mod m
        encrypted = pow(block_int2, exponent, modulus)

        # 转 hex（前端用 biToHex）
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

# 1. 访问门户触发 SSO 跳转
print("=== 1. 访问 EIP 门户 ===")
resp = session.get(f"{EIP_PORTAL}/", allow_redirects=False, timeout=15)
login_url = resp.headers.get("Location", "")
print(f"SSO URL: {login_url}")
if not login_url:
    print("未获取到 SSO URL")
    sys.exit(1)

# 2. 获取 SSO 登录页
print("\n=== 2. 获取 SSO 登录页面 ===")
resp = session.get(login_url, timeout=15)
html = resp.text
print(f"页面大小: {len(html)} bytes")

# 提取 encryptKey
key_match = re.search(r'encryptKey:\s*"([^"]+)"', html)
if not key_match:
    print("未找到 encryptKey")
    sys.exit(1)

encrypt_key = key_match.group(1)
parts = encrypt_key.split("#")
modulus_hex = parts[0]
exponent_hex = parts[1] if len(parts) > 1 else "010001"
print(f"Modulus(前60): {modulus_hex[:60]}...")
print(f"Exponent: {exponent_hex}")

# 提取参数
app_id = re.search(r'name="appId"\s+value="([^"]+)"', html)
app_id = app_id.group(1) if app_id else ""

execution = re.search(r'name="execution"\s+value="([^"]+)"', html)
execution = execution.group(1) if execution else "e1s1"
print(f"execution: {execution}")

# 3. 加密
print("\n=== 3. 加密数据 ===")

# 账号加密（smPass=false 时直接加密 encodeURIComponent 后的字符串）
username_encoded = urllib.parse.quote(USERNAME, safe='')

# 密码加密（IE8 模式）：md5(pass) + random8 + pass
random8 = get_random_string(8)
password_raw = md5(PASSWORD) + random8 + PASSWORD

print(f"账号原文: {username_encoded}")
print(f"密码原文(前50): {password_raw[:50]}...")

# 先测试短字符串
test_str = "test"
test_enc = rsa_encrypt(modulus_hex, exponent_hex, test_str)
print(f"测试加密(简单): {test_enc[:60]}...")

encrypted_username = rsa_encrypt(modulus_hex, exponent_hex, username_encoded)
print(f"账号加密(前100): {encrypted_username[:100]}...")

encrypted_password = rsa_encrypt(modulus_hex, exponent_hex, password_raw)
print(f"密码加密(前100): {encrypted_password[:100]}...")

# 4. 构造防重放参数
print("\n=== 4. 防重放参数 ===")
request_time = str(int(time.time() * 1000))
nonce = get_uid()
sign_data = request_time + "," + nonce
sign = md5(sign_data)
print(f"sign: {sign}")

# 5. 提交登录
print("\n=== 5. 提交登录 ===")
form_data = {
    "appId": app_id,
    "authMode": "ACCOUNT_PASSWORD",
    "username": encrypted_username,
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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": login_url,
    "Origin": SSO_BASE,
}

resp = session.post(login_url, data=form_data, headers=headers, 
                    allow_redirects=False, timeout=30)

print(f"状态码: {resp.status_code}")
print(f"Location: {resp.headers.get('Location', '无')}")
set_cookie = resp.headers.get('Set-Cookie', '')
print(f"Set-Cookie(前200): {set_cookie[:200]}")

# 检查响应内容
content_preview = resp.text[:800]
print(f"\n响应内容(前800字符):\n{content_preview}")

# 6. 处理重定向
if resp.status_code in (301, 302, 303, 307, 308):
    redirect_url = resp.headers["Location"]
    print(f"\n重定向到: {redirect_url}")
    
    resp2 = session.get(redirect_url, allow_redirects=False, timeout=15)
    print(f"重定向状态码: {resp2.status_code}")
    print(f"最终 URL: {resp2.url}")
    print(f"Set-Cookie(重定向): {resp2.headers.get('Set-Cookie', '无')}")

    # 继续重定向直到到达 EIP
    final_resp = resp2
    while final_resp.status_code in (301, 302, 303, 307, 308):
        next_url = final_resp.headers.get("Location", "")
        if not next_url:
            break
        print(f"继续重定向到: {next_url}")
        final_resp = session.get(next_url, allow_redirects=False, timeout=15)
        print(f"状态码: {final_resp.status_code}")

    print(f"\n最终页面 URL: {final_resp.url}")

    if "eip.hn.sgcc.com.cn" in final_resp.url:
        print("==> 登录成功！已到达 EIP 门户")
    else:
        # 检查错误
        print(f"最终页面(前500): {final_resp.text[:500]}")

# 7. 展示 Cookie
print("\n=== 6. 最终 Cookie ===")
cookie_dict = requests.utils.dict_from_cookiejar(session.cookies)
cookie_str = "; ".join([f"{k}={v}" for k, v in cookie_dict.items()])
print(f"Cookie: {cookie_str}")

# 检查是否登录成功
# 如果在 EIP 域下有 Cookie，则成功
eip_cookies = {k: v for k, v in cookie_dict.items() if 'eip' in k.lower() or 'JSESSIONID' in k}
print(f"\nEIP Cookies: {eip_cookies}")

if eip_cookies or "eip.hn.sgcc.com.cn" in str(session.cookies):
    output = {
        "cookie_str": cookie_str,
        "cookies": cookie_dict,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open("eip_cookies.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print("\nCookie 已保存到 eip_cookies.json")
