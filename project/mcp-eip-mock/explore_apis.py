"""探索 EIP 实际接口"""
import requests
import json
import hashlib
import random
import time
import urllib.parse

USERNAME = "hej80"
PASSWORD = "hejie.1161"
EIP_PORTAL = "http://eip.hn.sgcc.com.cn/portal"


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

key_match = __import__('re').search(r'encryptKey:\s*"([^"]+)"', html)
encrypt_key = key_match.group(1)
parts = encrypt_key.split("#")
modulus_hex = parts[0]
exponent_hex = parts[1] if len(parts) > 1 else "010001"
app_id = __import__('re').search(r'name="appId"\s+value="([^"]+)"', html).group(1)
execution = __import__('re').search(r'name="execution"\s+value="([^"]+)"', html).group(1)

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

cookie_str = "; ".join([f"{k}={v}" for k, v in requests.utils.dict_from_cookiejar(session.cookies).items()])

print("=== 探索 EIP 接口 ===")

# 尝试更多可能的 API
test_endpoints = [
    # 待办/任务相关
    ("GET", f"{EIP_PORTAL}/portal_ext/rest/task/pendingList", {"pageSize": "3"}),
    ("GET", f"{EIP_PORTAL}/portal_ext/rest/task/listNew", {"pageSize": "3"}),
    ("GET", f"{EIP_PORTAL}/portal_ext/rest/task/myTasks", {"pageSize": "3"}),
    ("GET", f"{EIP_PORTAL}/portal_ext/rest/task/search", {"pageSize": "3"}),
    # 首页
    ("GET", f"{EIP_PORTAL}/portal_ext/rest/home/taskStat", None),
    ("GET", f"{EIP_PORTAL}/portal_ext/rest/home/notice", None),
    ("GET", f"{EIP_PORTAL}/portal_ext/rest/home/apps", None),
    # 消息通知
    ("GET", f"{EIP_PORTAL}/portal_ext/rest/notice/list", {"pageSize": "3"}),
    ("GET", f"{EIP_PORTAL}/portal_ext/rest/message/list", {"pageSize": "3"}),
    # 门户
    ("GET", f"{EIP_PORTAL}/portal-web/rest/todo/list", {"pageSize": "3"}),
    ("GET", f"{EIP_PORTAL}/portal-web/rest/task/list", {"pageSize": "3"}),
    ("GET", f"{EIP_PORTAL}/portal-web/rest/mail/list", {"pageSize": "3"}),
    ("GET", f"{EIP_PORTAL}/portal-web/rest/home/todoList", {"pageSize": "3"}),
    ("GET", f"{EIP_PORTAL}/portal-web/rest/home/taskStat", None),
    ("GET", f"{EIP_PORTAL}/portal-web/rest/home/message", {"pageSize": "3"}),
    ("GET", f"{EIP_PORTAL}/portal-web/rest/notice/list", {"pageSize": "3"}),
    ("GET", f"{EIP_PORTAL}/portal-web/rest/message/list", {"pageSize": "3"}),
    # 老版本 portal_ext/rest
    ("POST", f"{EIP_PORTAL}/portal_ext/rest/task/listHis", {"pageSize": "3"}),
    ("POST", f"{EIP_PORTAL}/portal_ext/rest/task/list", {"pageSize": "3"}),
]

for method, url, params in test_endpoints:
    try:
        if params:
            url = url + "?" + urllib.parse.urlencode(params)
        if method == "GET":
            r = session.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json, text/plain, */*",
                "Referer": f"{EIP_PORTAL}/",
            }, timeout=10)
        else:
            r = session.post(url, data=params, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json, text/plain, */*",
                "Referer": f"{EIP_PORTAL}/",
            }, timeout=10)

        content_type = r.headers.get("Content-Type", "")
        is_json = "json" in content_type
        try:
            json.loads(r.text)
            is_json = True
        except:
            pass

        mark = "JSON" if is_json else "HTML"
        size = len(r.text)
        preview = r.text[:150].replace('\n', ' ').replace('\r', '')
        print(f"[{r.status_code}/{mark}/{size}B] {method} {url}")
        if is_json:
            print(f"  {preview}")
    except Exception as e:
        print(f"[ERR] {method} {url}: {e}")

print("\n=== 完成 ===")
