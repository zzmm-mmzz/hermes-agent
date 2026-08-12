"""
EIP 门户数据助手 HTTP 服务
封装登录 + 邮件列表 + 待办列表 为 RESTful API

端口: 8300 (在 mcp-eip-mock 的 8200 基础上递增)

提供接口:
  GET  /                           - 服务信息
  GET  /api/mail?pageSize=50       - 获取邮件列表
  GET  /api/todo?pageSize=10      - 获取待办列表
  GET  /api/task-history?pageSize=10 - 获取历史任务列表
  POST /api/refresh               - 刷新登录会话(重新登录获取新Cookie)
"""
import asyncio
import json
import os
import hashlib
import random
import time
import urllib.parse
import re as re_module
from typing import Any, Dict, Optional
from http import HTTPStatus
from urllib.parse import urlparse

# ── 配置 ──────────────────────────────────────────────────────────────────

HOST = os.environ.get("EIP_HOST", "0.0.0.0")
PORT = int(os.environ.get("EIP_PORT", "8300"))

EIP_PORTAL = "http://eip.hn.sgcc.com.cn/portal"
SSO_BASE = "http://tyqxiscsso.hn.sgcc.com.cn:38080"

# ── 全局会话状态 ──────────────────────────────────────────────────────────

_session_lock = asyncio.Lock()
_session = {
    "cookies": {},
    "cookie_str": "",
    "expires_at": 0,
    "username": "",
    "password": "",
}


# ── RSA 加密（与前端 ISC SSO 加密逻辑一致）────────────────────────────────

def _get_random_string(length: int = 8) -> str:
    chars = 'ABCDEFGHJKMNPQRSTWXYZabcdefhijkmnprstwxyz2345678'
    return ''.join(random.choice(chars) for _ in range(length))


def _rsa_encrypt(modulus_hex: str, exponent_hex: str, plaintext: str) -> str:
    modulus = int(modulus_hex, 16)
    exponent = int(exponent_hex, 16)

    h = modulus_hex.lower()
    if h.startswith("0x"):
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


def _md5(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def _get_uid() -> str:
    import uuid
    return uuid.uuid4().hex


# ── 登录函数 ─────────────────────────────────────────────────────────────

async def eip_login(username: str, password: str) -> Dict[str, Any]:
    """登录 EIP 门户，返回 Cookie 信息"""
    import requests as req

    session = req.Session()

    # 1. 访问门户触发 SSO 跳转
    resp = session.get(f"{EIP_PORTAL}/", allow_redirects=False, timeout=15)
    login_url = resp.headers.get("Location", "")
    if not login_url:
        return {"success": False, "error": "未能获取 SSO 登录 URL"}

    # 2. 获取 SSO 登录页
    resp = session.get(login_url, timeout=15)
    html = resp.text

    key_match = re_module.search(r'encryptKey:\s*"([^"]+)"', html)
    if not key_match:
        return {"success": False, "error": "未能获取加密密钥"}

    encrypt_key = key_match.group(1)
    parts = encrypt_key.split("#")
    modulus_hex = parts[0]
    exponent_hex = parts[1] if len(parts) > 1 else "010001"

    app_id = re_module.search(r'name="appId"\s+value="([^"]+)"', html)
    app_id = app_id.group(1) if app_id else ""

    execution = re_module.search(r'name="execution"\s+value="([^"]+)"', html)
    execution = execution.group(1) if execution else "e1s1"

    # 3. 加密密码
    random8 = _get_random_string(8)
    password_plain = _md5(password) + random8 + password
    encrypted_pwd = _rsa_encrypt(modulus_hex, exponent_hex, password_plain)

    # 4. 防重放参数
    request_time = str(int(time.time() * 1000))
    nonce = _get_uid()
    sign = _md5(request_time + "," + nonce)

    # 5. 提交登录
    form_data = {
        "appId": app_id,
        "authMode": "ACCOUNT_PASSWORD",
        "username": urllib.parse.quote(username, safe=""),
        "password": encrypted_pwd,
        "captchaPattern": "embed",
        "execution": execution,
        "_eventId": "submit",
        "messageCode": "",
        "requestTime": request_time,
        "nonce": nonce,
        "sign": sign,
    }

    resp = session.post(login_url, data=form_data, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": login_url,
    }, allow_redirects=False, timeout=30)

    # 6. 跟踪重定向到 EIP 门户
    current = resp
    redirect_count = 0
    while current.status_code in (301, 302, 303, 307, 308) and redirect_count < 10:
        next_url = current.headers.get("Location", "")
        if not next_url:
            break
        current = session.get(next_url, allow_redirects=False, timeout=15)
        redirect_count += 1

    # 7. 收集 Cookie
    cookie_dict = req.utils.dict_from_cookiejar(session.cookies)
    cookie_str = "; ".join([f"{k}={v}" for k, v in cookie_dict.items()])

    is_logged_in = "eip.hn.sgcc.com.cn" in current.url

    return {
        "success": is_logged_in,
        "final_url": current.url,
        "cookies": cookie_dict,
        "cookie_str": cookie_str,
        "error": None if is_logged_in else "登录后未跳转到 EIP 门户",
    }


def _make_session_from_cookies(cookie_str: str) -> "requests.Session":
    """从 Cookie 字符串创建 requests.Session"""
    import requests as req
    session = req.Session()
    for item in cookie_str.split("; "):
        if "=" in item:
            k, v = item.split("=", 1)
            session.cookies.set(k, v, domain="eip.hn.sgcc.com.cn")
    return session


async def _ensure_session(username: str, password: str) -> Optional[str]:
    """确保有有效的 Cookie，过期则重新登录"""
    global _session
    async with _session_lock:
        now = time.time()
        # Cookie 过期判断（JSESSIONID 通常 30 分钟，保险取 25 分钟）
        if _session["cookie_str"] and _session["expires_at"] > now:
            return _session["cookie_str"]

        result = await eip_login(username, password)
        if not result.get("success"):
            return None

        _session["cookies"] = result["cookies"]
        _session["cookie_str"] = result["cookie_str"]
        _session["expires_at"] = time.time() + 1500  # 25 分钟有效
        _session["username"] = username
        _session["password"] = password
        return result["cookie_str"]


# ── 数据查询函数 ─────────────────────────────────────────────────────────

async def _eip_request(method: str, path: str, data: Dict = None,
                       params: Dict = None) -> Dict:
    """通用的 EIP API 请求"""
    import requests as req

    cookie_str = await _ensure_session(_session["username"], _session["password"])
    if not cookie_str:
        return {"success": False, "error": "登录失败，请检查账号密码"}

    session = _make_session_from_cookies(cookie_str)

    url = f"{EIP_PORTAL}{path}"
    if params:
        qs = urllib.parse.urlencode(params)
        url = f"{url}?{qs}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": f"{EIP_PORTAL}/",
    }

    if method == "GET":
        resp = session.get(url, headers=headers, timeout=15)
    else:
        headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        headers["X-Requested-With"] = "XMLHttpRequest"
        resp = session.post(url, data=data, headers=headers, timeout=15)

    try:
        return {"success": True, "status": resp.status_code, "data": resp.json()}
    except Exception:
        return {
            "success": False,
            "status": resp.status_code,
            "error": "响应非 JSON 格式",
            "raw": resp.text[:500],
        }


# ── HTTP 服务 ────────────────────────────────────────────────────────────


async def handle_http(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """处理 HTTP 请求"""
    try:
        request_data = b""
        while True:
            chunk = await asyncio.wait_for(reader.read(65536), timeout=30)
            if not chunk:
                break
            request_data += chunk
            if b"\r\n\r\n" in request_data:
                header_end = request_data.find(b"\r\n\r\n")
                headers_raw = request_data[:header_end].decode("utf-8", errors="replace")
                content_length = 0
                for line in headers_raw.split("\r\n")[1:]:
                    if line.lower().startswith("content-length:"):
                        content_length = int(line.split(":")[1].strip())
                body_start = header_end + 4
                if content_length == 0:
                    break
                if len(request_data) - body_start >= content_length:
                    break

        request_text = request_data.decode("utf-8", errors="replace")
        lines = request_text.split("\r\n")
        if not lines:
            raise ValueError("Empty request")

        request_line = lines[0]
        method, path, _ = request_line.split(" ", 2)

        body_start_idx = request_text.find("\r\n\r\n")
        body = request_text[body_start_idx + 4:] if body_start_idx != -1 else ""

        # 解析查询参数
        parsed_path = urlparse(path)
        route = parsed_path.path.rstrip("/")
        query_params = urllib.parse.parse_qs(parsed_path.query)

        # 解析 POST body
        post_data = {}
        if method == "POST" and body:
            try:
                post_data = json.loads(body)
            except json.JSONDecodeError:
                try:
                    post_data = dict(urllib.parse.parse_qsl(body))
                except Exception:
                    post_data = {}

        # ── 路由 ──
        response_data = {}

        if route == "" or route == "/":
            response_data = {
                "server": "EIP 门户数据助手",
                "version": "1.0.0",
                "port": PORT,
                "endpoints": [
                    {"path": "GET /api/mail", "desc": "获取邮件列表", "params": "pageSize(默认50), pageNo(默认1), status(默认空)"},
                    {"path": "GET /api/todo", "desc": "获取待办列表", "params": "pageSize(默认10)"},
                    {"path": "GET /api/task-history", "desc": "获取历史任务列表", "params": "pageSize(默认10)"},
                    {"path": "POST /api/refresh", "desc": "刷新登录会话", "params": "username, password"},
                ],
                "status": "running",
            }

        elif route == "/api/mail":
            page_size = int(query_params.get("pageSize", [50])[0])
            page_no = int(query_params.get("pageNo", [1])[0])
            status = query_params.get("status", [""])[0]
            result = await _eip_request(
                "POST",
                "/portal_ext/rest/mailNew/queryUserMail?robot=",
                data={
                    "appId": "mailAppId",
                    "pageNo": str(page_no),
                    "pageSize": str(page_size),
                    "status": status,
                },
            )
            response_data = result

        elif route == "/api/todo":
            page_size = int(query_params.get("pageSize", [10])[0])
            result = await _eip_request(
                "POST",
                "/portal_ext/rest/task/list",
                data={"pageSize": str(page_size)},
            )
            response_data = result

        elif route == "/api/task-history":
            page_size = int(query_params.get("pageSize", [10])[0])
            keyword = query_params.get("keyword", [""])[0]
            app_id = query_params.get("appId", [""])[0]
            timestamp = str(int(time.time() * 1000))
            result = await _eip_request(
                "GET",
                f"/portal_ext/rest/task/listHis",
                params={
                    "appId": app_id,
                    "keyWord": keyword,
                    "pageSize": str(page_size),
                    "_": timestamp,
                },
            )
            response_data = result

        elif route == "/api/refresh":
            username = post_data.get("username", _session["username"])
            password = post_data.get("password", _session["password"])
            if not username or not password:
                response_data = {
                    "success": False,
                    "error": "请提供 username 和 password",
                }
            else:
                login_result = await eip_login(username, password)
                if login_result.get("success"):
                    async with _session_lock:
                        _session["cookies"] = login_result["cookies"]
                        _session["cookie_str"] = login_result["cookie_str"]
                        _session["expires_at"] = time.time() + 1500
                        _session["username"] = username
                        _session["password"] = password
                    response_data = {
                        "success": True,
                        "message": "登录会话已刷新",
                        "cookies": login_result["cookies"],
                    }
                else:
                    response_data = {
                        "success": False,
                        "error": login_result.get("error", "登录失败"),
                    }

        elif route == "/api/set-credentials":
            """设置登录凭据（不立即登录，下次请求时自动登录）"""
            username = post_data.get("username", "")
            password = post_data.get("password", "")
            if not username or not password:
                response_data = {"success": False, "error": "请提供 username 和 password"}
            else:
                async with _session_lock:
                    _session["username"] = username
                    _session["password"] = password
                    _session["cookie_str"] = ""  # 强制下次重新登录
                    _session["expires_at"] = 0
                response_data = {
                    "success": True,
                    "message": f"凭据已保存（用户: {username}）",
                }

        else:
            response_data = {"error": f"Not Found: {route}"}
            response_body = json.dumps(response_data, ensure_ascii=False)
            await send_response(writer, 404, "application/json", response_body)
            return

        response_body = json.dumps(response_data, ensure_ascii=False, indent=2)
        await send_response(writer, 200, "application/json", response_body)

    except Exception as e:
        try:
            error_data = json.dumps({"error": str(e)}, ensure_ascii=False)
            await send_response(writer, 500, "application/json", error_data)
        except Exception:
            pass
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def send_response(writer: asyncio.StreamWriter, status_code: int,
                        content_type: str, body: str):
    status_text = {
        200: "OK", 201: "Created", 204: "No Content",
        400: "Bad Request", 404: "Not Found", 500: "Internal Server Error",
    }.get(status_code, "Unknown")

    body_bytes = body.encode("utf-8")
    response = (
        f"HTTP/1.1 {status_code} {status_text}\r\n"
        f"Content-Type: {content_type}; charset=utf-8\r\n"
        f"Content-Length: {len(body_bytes)}\r\n"
        f"Access-Control-Allow-Origin: *\r\n"
        f"Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n"
        f"Access-Control-Allow-Headers: Content-Type\r\n"
        f"\r\n"
    )
    writer.write(response.encode("utf-8") + body_bytes)
    await writer.drain()


# ── 主入口 ────────────────────────────────────────────────────────────────


async def main():
    # 初始设置凭据
    _session["username"] = "hej80"
    _session["password"] = "hejie.1161"

    server = await asyncio.start_server(handle_http, host=HOST, port=PORT)

    print(f"")
    print(f"  EIP 门户数据助手已启动")
    print(f"  ─────────────────────────────")
    print(f"  监听端口: {PORT}")
    print(f"  当前用户: {_session['username']}")
    print(f"")
    print(f"  可用接口:")
    print(f"  GET  http://127.0.0.1:{PORT}/")
    print(f"  GET  http://127.0.0.1:{PORT}/api/mail?pageSize=50")
    print(f"  GET  http://127.0.0.1:{PORT}/api/todo?pageSize=10")
    print(f"  GET  http://127.0.0.1:{PORT}/api/task-history?pageSize=10")
    print(f"  POST http://127.0.0.1:{PORT}/api/refresh")
    print(f"")

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
