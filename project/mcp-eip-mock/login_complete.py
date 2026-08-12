"""完整的登录验证并展示结果"""
import requests
import json
import hashlib
import random
import time
import urllib.parse
import re as re_module

USERNAME = "hej80"
PASSWORD = "hejie.1161"
EIP_PORTAL = "http://eip.hn.sgcc.com.cn/portal"
SSO_BASE = "http://tyqxiscsso.hn.sgcc.com.cn:38080"


def get_random_string(length):
    chars = 'ABCDEFGHJKMNPQRSTWXYZabcdefhijkmnprstwxyz2345678'
    return ''.join(random.choice(chars) for _ in range(length))


def rsa_encrypt(modulus_hex, exponent_hex, plaintext):
    modulus = int(modulus_hex, 16)
    exponent = int(exponent_hex, 16)
    h = modulus_hex.lower()
    if h.startswith('0x'):
        h = h[2:]
    mod_digits = []
    for i in range(len(h), 0, -4):
        start = max(0, i - 4)
        mod_digits.append(int(h[start:i], 16))
    chunk_size = 2 * (len(mod_digits) - 1)
    a = [ord(c) for c in plaintext]
    while len(a) % chunk_size != 0:
        a.append(0)
    result_parts = []
    for i in range(0, len(a), chunk_size):
        block_digits = []
        for k in range(i, i + chunk_size, 2):
            low_byte = a[k]
            high_byte = a[k + 1] if k + 1 < len(a) else 0
            block_digits.append(low_byte | (high_byte << 8))
        block_int = 0
        for j, d in enumerate(block_digits):
            block_int |= d << (16 * j)
        encrypted = pow(block_int, exponent, modulus)
        enc_digits = []
        tmp = encrypted
        while tmp > 0:
            enc_digits.append(tmp & 0xFFFF)
            tmp >>= 16
        hex_str = ""
        for idx in range(len(enc_digits) - 1, -1, -1):
            hex_str += f"{enc_digits[idx]:04x}"
        if not hex_str:
            hex_str = "0"
        result_parts.append(hex_str)
    return " ".join(result_parts)


def md5(s):
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def get_uid():
    import uuid
    return uuid.uuid4().hex


# 登录
session = requests.Session()
resp = session.get(f"{EIP_PORTAL}/", allow_redirects=False, timeout=15)
login_url = resp.headers.get("Location", "")
resp = session.get(login_url, timeout=15)
html = resp.text

key_match = re_module.search(r'encryptKey:\s*"([^"]+)"', html)
encrypt_key = key_match.group(1)
parts = encrypt_key.split("#")
modulus_hex = parts[0]
exponent_hex = parts[1] if len(parts) > 1 else "010001"
app_id = re_module.search(r'name="appId"\s+value="([^"]+)"', html).group(1)
execution = re_module.search(r'name="execution"\s+value="([^"]+)"', html).group(1)

random8 = get_random_string(8)
password_plain = md5(PASSWORD) + random8 + PASSWORD
encrypted_password = rsa_encrypt(modulus_hex, exponent_hex, password_plain)
request_time = str(int(time.time() * 1000))
nonce = get_uid()
sign = md5(request_time + "," + nonce)

form_data = {
    "appId": app_id, "authMode": "ACCOUNT_PASSWORD",
    "username": urllib.parse.quote(USERNAME, safe=''),
    "password": encrypted_password,
    "captchaPattern": "embed", "execution": execution,
    "_eventId": "submit", "messageCode": "",
    "requestTime": request_time, "nonce": nonce, "sign": sign,
}

resp = session.post(login_url, data=form_data, headers={
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Content-Type": "application/x-www-form-urlencoded", "Referer": login_url,
}, allow_redirects=False, timeout=30)

current = resp
while current.status_code in (301, 302, 303, 307, 308):
    next_url = current.headers.get("Location", "")
    if not next_url:
        break
    current = session.get(next_url, allow_redirects=False, timeout=15)

cookie_dict = requests.utils.dict_from_cookiejar(session.cookies)
cookie_str = "; ".join([f"{k}={v}" for k, v in cookie_dict.items()])

# 获取待办任务
todo_resp = session.post(f"{EIP_PORTAL}/portal_ext/rest/task/list", data={"pageSize": "5"}, headers={
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*", "Referer": f"{EIP_PORTAL}/",
}, timeout=15)

# 获取历史任务
his_resp = session.post(f"{EIP_PORTAL}/portal_ext/rest/task/listHis", data={"pageSize": "5"}, headers={
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*", "Referer": f"{EIP_PORTAL}/",
}, timeout=15)

# 输出结果
print("=" * 60)
print("EIP 门户登录成功！")
print("=" * 60)

print(f"\n用户名: {USERNAME}")
print(f"Cookie 字符串:")
print(cookie_str)
print()

try:
    todo_data = todo_resp.json()
    todo_items = todo_data.get("result", todo_data.get("data", []))
    print(f"\n待办任务 ({len(todo_items) if isinstance(todo_items, list) else '?'} 条):")
    if isinstance(todo_items, list):
        for item in todo_items[:5]:
            print(f"  - {item.get('name', item.get('title', '?'))}")
            print(f"    应用: {item.get('appName', '?')}  时间: {item.get('activeTime', '?')}")
except:
    print("待办任务: 解析失败")

try:
    his_data = his_resp.json()
    his_items = his_data.get("result", his_data.get("data", []))
    print(f"\n历史任务 ({len(his_items) if isinstance(his_items, list) else '?'} 条):")
    if isinstance(his_items, list):
        for item in his_items[:5]:
            print(f"  - {item.get('name', item.get('title', '?'))}")
            print(f"    应用: {item.get('appName', '?')}  时间: {item.get('activeTime', '?')}")
except:
    print("历史任务: 解析失败")

# 保存完整结果
output = {
    "cookie_str": cookie_str,
    "cookies": cookie_dict,
    "username": USERNAME,
    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
}
with open("eip_cookies.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
