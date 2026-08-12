"""
EIP 门户集成服务（Mock MCP + RESTful 代理）

统一服务，端口 8200，提供两类功能：

1. 模拟数据（MCP 工具 + 快捷端点）：
   - get_task_list     - 模拟任务历史列表
   - get_app_list      - 模拟应用列表
   - get_task_detail   - 模拟任务详情

2. 真实代理（MCP 工具 + RESTful API），需 SSO 登录：
   - get_mail_list     - 获取邮件列表
   - get_todo_list     - 获取待办列表
   - get_task_history  - 获取历史任务列表（真实）
   - eip_refresh_session   - 刷新登录会话
   - eip_set_credentials   - 设置登录凭据

RESTful 端点：
  GET  /                        - 服务信息
  GET  /api/mail?pageSize=50    - 获取邮件列表
  GET  /api/todo?pageSize=10    - 获取待办列表
  GET  /api/task-history?pageSize=10 - 获取历史任务列表
  POST /api/refresh             - 刷新登录会话
  POST /api/set-credentials     - 设置登录凭据
  POST /mcp                     - JSON-RPC 协议
  POST /tools/<tool_name>       - 直接调用工具

依赖: Python 3.9+ 标准库 + requests（真实代理部分需要）

运行:
    pip install requests
    python server.py
"""

import asyncio
import hashlib
import json
import os
import random
import re as re_module
import sys
import time
import urllib.parse
import uuid
from datetime import datetime, timedelta
from http import HTTPStatus
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, parse_qs
from dataclasses import dataclass, field, asdict

# ── 配置 ──────────────────────────────────────────────────────────────────

MCP_HOST = os.environ.get("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.environ.get("MCP_PORT", "8200"))

EIP_PORTAL = os.environ.get("EIP_PORTAL", "http://eip.hn.sgcc.com.cn/portal")
SSO_BASE = os.environ.get("SSO_BASE", "http://tyqxiscsso.hn.sgcc.com.cn:38080")

# ── 全局会话状态（真实代理用）──────────────────────────────────────────────

_session_lock = asyncio.Lock()
_session = {
    "cookies": {},
    "cookie_str": "",
    "expires_at": 0,
    "username": "",
    "password": "",
}

# ── 个人重点事项存储（模拟数据）──────────────────────────────────────────────
# 每条记录: { "id": str, "title": str, "content": str, "source": str, "extra": dict,
#             "remindTime": str("YYYY-MM-DD HH:MM:SS" 或 ""), "remindStatus": str,
#             "createTime": str, "updateTime": str }
# remindStatus: "" 不提醒 / pending 等待触发 / sent 已触发待确认 / acked 已确认

PERSONAL_NOTES: List[Dict[str, Any]] = []
_note_id_counter: int = 0

def _next_note_id() -> str:
    global _note_id_counter
    _note_id_counter += 1
    return f"NOTE{int(time.time())}{_note_id_counter:04d}"

# ══════════════════════════════════════════════════════════════════════════
# 第一部分：模拟数据（Mock）
# ══════════════════════════════════════════════════════════════════════════

# 应用列表
APP_LIST = [
    {"appId": "1001", "appName": "营销业务应用"},
    {"appId": "1002", "appName": "生产管理系统"},
    {"appId": "1003", "appName": "调度自动化系统"},
    {"appId": "1004", "appName": "综合数据平台"},
    {"appId": "1005", "appName": "协同办公平台"},
]

# 任务类型
TASK_TYPES = [
    {"typeId": "T01", "typeName": "流程审批"},
    {"typeId": "T02", "typeName": "数据填报"},
    {"typeId": "T03", "typeName": "异常处理"},
    {"typeId": "T04", "typeName": "定期检查"},
    {"typeId": "T05", "typeName": "报表生成"},
]

# 任务状态
TASK_STATUS = [
    {"code": "COMPLETED", "name": "已完成"},
    {"code": "TERMINATED", "name": "已终止"},
    {"code": "REFUSED", "name": "已驳回"},
    {"code": "CANCELED", "name": "已取消"},
]

# 处理人
HANDLERS = [
    "张三", "李四", "王五", "赵六", "陈七",
    "周文", "吴明", "郑涛", "孙丽", "黄华",
]

ORG_NAMES = [
    "长沙供电公司", "株洲供电公司", "湘潭供电公司", "衡阳供电公司",
    "岳阳供电公司", "常德供电公司", "益阳供电公司", "娄底供电公司",
]


def _build_assignee() -> Dict[str, Any]:
    """生成随机处理人信息"""
    handler = HANDLERS[uuid.uuid4().int % len(HANDLERS)]
    return {
        "handlerName": handler,
        "handlerId": f"USR{10000 + uuid.uuid4().int % 90000}",
        "handlerOrg": f"ORG{10000 + uuid.uuid4().int % 100}",
        "handlerOrgName": ORG_NAMES[uuid.uuid4().int % len(ORG_NAMES)],
    }


def _build_task_item(index: int, base_time: datetime, keyword: str = "") -> Dict[str, Any]:
    """生成单个任务项"""
    app = APP_LIST[uuid.uuid4().int % len(APP_LIST)]
    task_type = TASK_TYPES[uuid.uuid4().int % len(TASK_TYPES)]
    status = TASK_STATUS[uuid.uuid4().int % len(TASK_STATUS)]
    assignee = _build_assignee()
    task_id = f"TASK{int(base_time.timestamp())}{index:04d}"

    titles = [
        f"{app['appName']}-{task_type['typeName']}申请",
        f"{assignee['handlerOrgName']}{task_type['typeName']}工单",
        f"关于{app['appName']}的{task_type['typeName']}通知",
        f"{task_type['typeName']}任务-{assignee['handlerName']}",
        f"月度{task_type['typeName']}报告",
    ]
    title = titles[index % len(titles)]

    return {
        "taskId": task_id,
        "title": title,
        "appId": app["appId"],
        "appName": app["appName"],
        "taskType": task_type["typeId"],
        "taskTypeName": task_type["typeName"],
        "status": status["code"],
        "statusName": status["name"],
        "createTime": (base_time - timedelta(hours=index)).strftime("%Y-%m-%d %H:%M:%S"),
        "completeTime": (base_time - timedelta(hours=index - 1)).strftime("%Y-%m-%d %H:%M:%S"),
        "handlerName": assignee["handlerName"],
        "handlerId": assignee["handlerId"],
        "handlerOrgName": assignee["handlerOrgName"],
        "description": f"这是{app['appName']}系统中的一个{task_type['typeName']}任务，由{assignee['handlerName']}处理，状态为{status['name']}。",
        "priority": ["高", "中", "低"][uuid.uuid4().int % 3],
        "urgent": uuid.uuid4().int % 5 == 0,
    }


def generate_mock_data(page_size: int = 10, keyword: str = "", app_id: str = "") -> Dict[str, Any]:
    """生成模拟的任务列表数据"""
    now = datetime.now()
    all_tasks = []

    for i in range(page_size):
        task = _build_task_item(i, now, keyword)
        if keyword and keyword.lower() not in task["title"].lower() and keyword not in task["taskId"].lower():
            continue
        if app_id and task["appId"] != app_id:
            continue
        all_tasks.append(task)

    while len(all_tasks) < page_size:
        task = _build_task_item(len(all_tasks), now, keyword)
        if keyword and keyword.lower() not in task["title"].lower() and keyword not in task["taskId"].lower():
            task["title"] = f"{keyword}相关任务-{uuid.uuid4().int % 100}"
        all_tasks.append(task)

    total_count = 100 + uuid.uuid4().int % 900

    return {
        "code": 0,
        "message": "success",
        "data": {
            "total": total_count,
            "pageSize": page_size,
            "pageNum": 1,
            "totalPages": (total_count + page_size - 1) // page_size,
            "list": all_tasks[:page_size],
        },
    }


# ══════════════════════════════════════════════════════════════════════════
# 第二部分：真实代理（SSO 登录 + RSA 加密）
# ══════════════════════════════════════════════════════════════════════════

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
    return uuid.uuid4().hex


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

    app_id_match = re_module.search(r'name="appId"\s+value="([^"]+)"', html)
    app_id = app_id_match.group(1) if app_id_match else ""

    execution_match = re_module.search(r'name="execution"\s+value="([^"]+)"', html)
    execution = execution_match.group(1) if execution_match else "e1s1"

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


async def handle_eip_mail(page_size: int = 50, page_no: int = 1, status: str = "") -> Dict:
    """获取 EIP 邮件列表"""
    return await _eip_request(
        "POST",
        "/portal_ext/rest/mailNew/queryUserMail?robot=",
        data={
            "appId": "mailAppId",
            "pageNo": str(page_no),
            "pageSize": str(page_size),
            "status": status,
        },
    )


async def handle_eip_todo(page_size: int = 10) -> Dict:
    """获取 EIP 待办列表"""
    return await _eip_request(
        "POST",
        "/portal_ext/rest/task/list",
        data={"pageSize": str(page_size)},
    )


async def handle_eip_task_history(page_size: int = 10, keyword: str = "", app_id: str = "") -> Dict:
    """获取 EIP 历史任务列表"""
    timestamp = str(int(time.time() * 1000))
    return await _eip_request(
        "GET",
        "/portal_ext/rest/task/listHis",
        params={
            "appId": app_id,
            "keyWord": keyword,
            "pageSize": str(page_size),
            "_": timestamp,
        },
    )


async def handle_eip_refresh(username: str, password: str) -> Dict:
    """刷新登录会话"""
    if not username or not password:
        return {"success": False, "error": "请提供 username 和 password"}

    login_result = await eip_login(username, password)
    if login_result.get("success"):
        async with _session_lock:
            _session["cookies"] = login_result["cookies"]
            _session["cookie_str"] = login_result["cookie_str"]
            _session["expires_at"] = time.time() + 1500
            _session["username"] = username
            _session["password"] = password
        return {
            "success": True,
            "message": "登录会话已刷新",
            "cookies": login_result["cookies"],
        }
    else:
        return {
            "success": False,
            "error": login_result.get("error", "登录失败"),
        }


async def handle_eip_set_credentials(username: str, password: str) -> Dict:
    """设置登录凭据（不立即登录，下次请求时自动登录）"""
    if not username or not password:
        return {"success": False, "error": "请提供 username 和 password"}
    async with _session_lock:
        _session["username"] = username
        _session["password"] = password
        _session["cookie_str"] = ""
        _session["expires_at"] = 0
    return {
        "success": True,
        "message": f"凭据已保存（用户: {username}）",
    }


# ══════════════════════════════════════════════════════════════════════════
# 第三部分：MCP 协议
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class MCPTool:
    """MCP 工具描述"""
    name: str
    description: str
    input_schema: Dict[str, Any]


class MCPServer:
    """MCP 服务端"""

    def __init__(self):
        self.tools: Dict[str, MCPTool] = {}
        self._register_tools()

    def _register_tools(self):
        """注册所有工具（模拟 + 真实代理）"""

        # ── 真实代理工具 ──
        self.tools["get_mail_list"] = MCPTool(
            name="get_mail_list",
            description="获取 EIP 门户邮件列表（真实数据，需 SSO 登录）。需要先通过 eip_set_credentials 设置用户名密码。",
            input_schema={
                "type": "object",
                "properties": {
                    "pageSize": {
                        "type": "integer",
                        "description": "每页记录数",
                        "default": 50,
                        "minimum": 1,
                        "maximum": 100,
                    },
                    "pageNo": {
                        "type": "integer",
                        "description": "页码",
                        "default": 1,
                        "minimum": 1,
                    },
                    "status": {
                        "type": "string",
                        "description": "邮件状态筛选（可选）",
                        "default": "",
                    },
                },
                "required": [],
            },
        )

        self.tools["get_todo_list"] = MCPTool(
            name="get_todo_list",
            description="获取 EIP 门户待办任务列表（真实数据，需 SSO 登录）。需要先通过 eip_set_credentials 设置用户名密码。",
            input_schema={
                "type": "object",
                "properties": {
                    "pageSize": {
                        "type": "integer",
                        "description": "每页记录数",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 100,
                    },
                },
                "required": [],
            },
        )

        self.tools["get_task_history"] = MCPTool(
            name="get_task_history",
            description="获取 EIP 门户历史任务列表（真实数据，需 SSO 登录）。需要先通过 eip_set_credentials 设置用户名密码。",
            input_schema={
                "type": "object",
                "properties": {
                    "pageSize": {
                        "type": "integer",
                        "description": "每页记录数",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 100,
                    },
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词（可选）",
                        "default": "",
                    },
                    "appId": {
                        "type": "string",
                        "description": "应用ID筛选（可选）",
                        "default": "",
                    },
                },
                "required": [],
            },
        )

        self.tools["eip_refresh_session"] = MCPTool(
            name="eip_refresh_session",
            description="刷新 EIP 门户登录会话。当 Cookie 过期时调用此工具重新登录获取新 Cookie。",
            input_schema={
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "description": "EIP 门户用户名",
                    },
                    "password": {
                        "type": "string",
                        "description": "EIP 门户密码",
                    },
                },
                "required": ["username", "password"],
            },
        )

        # ── 个人重点事项工具 ──
        self.tools["add_personal_note"] = MCPTool(
            name="add_personal_note",
            description="将单条数据保存到个人重点事项。支持灵活传入任意字段数据，自动生成唯一ID和时间戳。可选传 remindTime（YYYY-MM-DD HH:MM:SS）设置定时提醒，到点后可通过 GET /api/reminders/pending 轮询到。注意：此为重点事项（个人笔记/备忘），不是待办任务。",
            input_schema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "重点事项标题（必填）",
                    },
                    "content": {
                        "type": "string",
                        "description": "重点事项详细内容",
                        "default": "",
                    },
                    "source": {
                        "type": "string",
                        "description": "来源，例如：邮件、待办、任务等",
                        "default": "",
                    },
                    "extra": {
                        "type": "object",
                        "description": "额外自定义数据（可选，透传保存）",
                        "default": {},
                    },
                    "remindTime": {
                        "type": "string",
                        "description": "提醒时间，格式 YYYY-MM-DD HH:MM:SS（可选，不传则不提醒）",
                        "default": "",
                    },
                },
                "required": ["title"],
            },
        )

        self.tools["delete_personal_note"] = MCPTool(
            name="delete_personal_note",
            description="根据 ID 删除个人重点事项。",
            input_schema={
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "重点事项 ID",
                    },
                },
                "required": ["id"],
            },
        )

        self.tools["list_personal_notes"] = MCPTool(
            name="list_personal_notes",
            description="获取个人重点事项列表（可选按关键词搜索）。",
            input_schema={
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词（可选）",
                        "default": "",
                    },
                    "pageSize": {
                        "type": "integer",
                        "description": "每页记录数",
                        "default": 20,
                        "minimum": 1,
                        "maximum": 100,
                    },
                    "pageNo": {
                        "type": "integer",
                        "description": "页码",
                        "default": 1,
                        "minimum": 1,
                    },
                },
                "required": [],
            },
        )

        self.tools["list_due_reminders"] = MCPTool(
            name="list_due_reminders",
            description="获取已触发但未确认的提醒列表（remindStatus=sent），供前端定时轮询。到点的重点事项会由后台协程自动置为 sent。",
            input_schema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        )

        self.tools["ack_reminder"] = MCPTool(
            name="ack_reminder",
            description="确认一条提醒：把 remindStatus 从 sent 置为 acked，确认后不再出现在待确认列表。",
            input_schema={
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "提醒对应的重点事项 ID",
                    },
                },
                "required": ["id"],
            },
        )

        self.tools["eip_set_credentials"] = MCPTool(
            name="eip_set_credentials",
            description="设置 EIP 门户登录凭据（不立即登录，下次请求时自动登录）。需要在调用 get_mail_list / get_todo_list / get_task_history 之前先设置。",
            input_schema={
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "description": "EIP 门户用户名",
                    },
                    "password": {
                        "type": "string",
                        "description": "EIP 门户密码",
                    },
                },
                "required": ["username", "password"],
            },
        )

    def handle_request(self, body: dict) -> dict:
        """处理 JSON-RPC 请求"""
        method = body.get("method", "")
        params = body.get("params", {})

        if method == "mcp.list_tools":
            return {
                "result": {
                    "tools": [
                        {
                            "name": t.name,
                            "description": t.description,
                            "input_schema": t.input_schema,
                        }
                        for t in self.tools.values()
                    ]
                }
            }

        elif method == "mcp.call_tool":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})

            if tool_name == "get_mail_list":
                return self._handle_get_mail_list(arguments)
            elif tool_name == "get_todo_list":
                return self._handle_get_todo_list(arguments)
            elif tool_name == "get_task_history":
                return self._handle_get_task_history(arguments)
            elif tool_name == "eip_refresh_session":
                return self._handle_eip_refresh(arguments)
            elif tool_name == "eip_set_credentials":
                return self._handle_eip_set_credentials(arguments)
            elif tool_name == "add_personal_note":
                return self._handle_add_personal_note(arguments)
            elif tool_name == "delete_personal_note":
                return self._handle_delete_personal_note(arguments)
            elif tool_name == "list_personal_notes":
                return self._handle_list_personal_notes(arguments)
            elif tool_name == "list_due_reminders":
                return self._handle_list_due_reminders(arguments)
            elif tool_name == "ack_reminder":
                return self._handle_ack_reminder(arguments)
            else:
                return {
                    "error": {
                        "code": -32601,
                        "message": f"Tool not found: {tool_name}",
                    }
                }
        else:
            return {
                "result": {
                    "serverInfo": "EIP 门户集成服务",
                    "version": "2.0.0",
                    "endpoints": list(self.tools.keys()),
                }
            }

    # ── 个人重点事项工具处理 ──

    def _handle_add_personal_note(self, arguments: dict) -> dict:
        title = arguments.get("title", "").strip()
        if not title:
            return {
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                {"code": 1, "message": "标题不能为空"},
                                ensure_ascii=False,
                                indent=2,
                            ),
                        }
                    ],
                    "isError": True,
                }
            }

        # 提醒时间（可选）：格式 "YYYY-MM-DD HH:MM:SS"；不传或空串 = 不提醒
        remind_time = str(arguments.get("remindTime", "") or "").strip()
        remind_status = ""
        if remind_time:
            try:
                datetime.strptime(remind_time, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return {
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(
                                    {
                                        "code": 1,
                                        "message": "remindTime 格式错误，应为 YYYY-MM-DD HH:MM:SS",
                                    },
                                    ensure_ascii=False,
                                    indent=2,
                                ),
                            }
                        ],
                        "isError": True,
                    }
                }
            remind_status = "pending"  # 待提醒（后台协程到点后置为 sent）

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        note = {
            "id": _next_note_id(),
            "title": title,
            "content": arguments.get("content", ""),
            "source": arguments.get("source", ""),
            "extra": arguments.get("extra", {}),
            "remindTime": remind_time,
            "remindStatus": remind_status,
            "createTime": now_str,
            "updateTime": now_str,
        }
        PERSONAL_NOTES.append(note)

        return {
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {"code": 0, "message": "重点事项已保存", "data": note},
                            ensure_ascii=False,
                            indent=2,
                        ),
                    }
                ],
                "isError": False,
            }
        }

    def _handle_delete_personal_note(self, arguments: dict) -> dict:
        note_id = arguments.get("id", "").strip()
        if not note_id:
            return {
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                {"code": 1, "message": "请提供要删除的重点事项 ID"},
                                ensure_ascii=False,
                                indent=2,
                            ),
                        }
                    ],
                    "isError": True,
                }
            }

        global PERSONAL_NOTES
        for i, note in enumerate(PERSONAL_NOTES):
            if note["id"] == note_id:
                deleted = PERSONAL_NOTES.pop(i)
                return {
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(
                                    {"code": 0, "message": "重点事项已删除", "data": deleted},
                                    ensure_ascii=False,
                                    indent=2,
                                ),
                            }
                        ],
                        "isError": False,
                    }
                }

        return {
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {"code": 404, "message": f"未找到 ID 为 {note_id} 的重点事项"},
                            ensure_ascii=False,
                            indent=2,
                        ),
                    }
                ],
                "isError": True,
            }
        }

    def _handle_list_personal_notes(self, arguments: dict) -> dict:
        keyword = arguments.get("keyword", "").strip().lower()
        page_size = max(1, min(100, arguments.get("pageSize", 20)))
        page_no = max(1, arguments.get("pageNo", 1))

        if keyword:
            filtered = [
                n for n in PERSONAL_NOTES
                if keyword in n["title"].lower()
                or keyword in n["content"].lower()
                or keyword in n.get("source", "").lower()
            ]
        else:
            filtered = list(PERSONAL_NOTES)

        # 按更新时间降序
        filtered.sort(key=lambda n: n["updateTime"], reverse=True)

        total = len(filtered)
        total_pages = max(1, (total + page_size - 1) // page_size)
        start = (page_no - 1) * page_size
        end = start + page_size
        page_items = filtered[start:end]

        return {
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "code": 0,
                                "message": "success",
                                "data": {
                                    "total": total,
                                    "pageSize": page_size,
                                    "pageNo": page_no,
                                    "totalPages": total_pages,
                                    "list": page_items,
                                },
                            },
                            ensure_ascii=False,
                            indent=2,
                        ),
                    }
                ],
                "isError": False,
            }
        }

    def _handle_list_due_reminders(self, arguments: dict) -> dict:
        """返回已触发但未确认的提醒列表（remindStatus == "sent"），供前端轮询。"""
        due = [
            n
            for n in PERSONAL_NOTES
            if n.get("remindStatus") == "sent"
        ]
        # 按提醒时间升序（先到期的排前面）
        due.sort(key=lambda n: n.get("remindTime", ""))
        return {
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "code": 0,
                                "message": "success",
                                "data": {
                                    "total": len(due),
                                    "list": due,
                                },
                            },
                            ensure_ascii=False,
                            indent=2,
                        ),
                    }
                ],
                "isError": False,
            }
        }

    def _handle_ack_reminder(self, arguments: dict) -> dict:
        """确认提醒：把 remindStatus 从 sent 置为 acked，确认后不再出现在待确认列表。"""
        note_id = arguments.get("id", "").strip()
        if not note_id:
            return {
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                {"code": 1, "message": "请提供要确认的提醒 ID"},
                                ensure_ascii=False,
                                indent=2,
                            ),
                        }
                    ],
                    "isError": True,
                }
            }

        for note in PERSONAL_NOTES:
            if note["id"] == note_id:
                note["remindStatus"] = "acked"
                note["updateTime"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                return {
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(
                                    {"code": 0, "message": "提醒已确认", "data": note},
                                    ensure_ascii=False,
                                    indent=2,
                                ),
                            }
                        ],
                        "isError": False,
                    }
                }

        return {
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {"code": 404, "message": f"未找到 ID 为 {note_id} 的提醒"},
                            ensure_ascii=False,
                            indent=2,
                        ),
                    }
                ],
                "isError": True,
            }
        }

    # ── 真实代理工具处理 ──

    def _handle_get_mail_list(self, arguments: dict) -> dict:
        page_size = arguments.get("pageSize", 50)
        page_no = arguments.get("pageNo", 1)
        status = arguments.get("status", "")
        
        self._ensure_event_loop()
        result = asyncio.run_coroutine_threadsafe(
            handle_eip_mail(page_size, page_no, status),
            _event_loop,
        ).result()

        return {
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2),
                    }
                ],
                "isError": not result.get("success", False),
            }
        }

    def _handle_get_todo_list(self, arguments: dict) -> dict:
        page_size = arguments.get("pageSize", 10)

        self._ensure_event_loop()
        result = asyncio.run_coroutine_threadsafe(
            handle_eip_todo(page_size),
            _event_loop,
        ).result()

        return {
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2),
                    }
                ],
                "isError": not result.get("success", False),
            }
        }

    def _handle_get_task_history(self, arguments: dict) -> dict:
        page_size = arguments.get("pageSize", 10)
        keyword = arguments.get("keyword", "")
        app_id = arguments.get("appId", "")

        self._ensure_event_loop()
        result = asyncio.run_coroutine_threadsafe(
            handle_eip_task_history(page_size, keyword, app_id),
            _event_loop,
        ).result()

        return {
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2),
                    }
                ],
                "isError": not result.get("success", False),
            }
        }

    def _handle_eip_refresh(self, arguments: dict) -> dict:
        username = arguments.get("username", "")
        password = arguments.get("password", "")

        self._ensure_event_loop()
        result = asyncio.run_coroutine_threadsafe(
            handle_eip_refresh(username, password),
            _event_loop,
        ).result()

        return {
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2),
                    }
                ],
                "isError": not result.get("success", False),
            }
        }

    def _handle_eip_set_credentials(self, arguments: dict) -> dict:
        username = arguments.get("username", "")
        password = arguments.get("password", "")

        self._ensure_event_loop()
        result = asyncio.run_coroutine_threadsafe(
            handle_eip_set_credentials(username, password),
            _event_loop,
        ).result()

        return {
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2),
                    }
                ],
                "isError": not result.get("success", False),
            }
        }

    def _ensure_event_loop(self):
        """确保异步事件循环可用"""
        global _event_loop
        if _event_loop is None or not _event_loop.is_running():
            _event_loop = asyncio.new_event_loop()


# 全局引用
mcp_server: Optional[MCPServer] = None
_event_loop: Optional[asyncio.AbstractEventLoop] = None


# ══════════════════════════════════════════════════════════════════════════
# 第四部分：HTTP 服务
# ══════════════════════════════════════════════════════════════════════════

async def send_http_response(writer: asyncio.StreamWriter, status_code: int,
                              content_type: str, body: str):
    """发送 HTTP 响应"""
    status_text = {
        200: "OK", 201: "Created", 204: "No Content",
        400: "Bad Request", 404: "Not Found", 405: "Method Not Allowed",
        500: "Internal Server Error",
    }.get(status_code, "Unknown")

    body_bytes = body.encode("utf-8")
    response = (
        f"HTTP/1.1 {status_code} {status_text}\r\n"
        f"Content-Type: {content_type}; charset=utf-8\r\n"
        f"Content-Length: {len(body_bytes)}\r\n"
        f"Access-Control-Allow-Origin: *\r\n"
        f"Access-Control-Allow-Methods: GET, POST, PUT, DELETE, PATCH, OPTIONS\r\n"
        f"Access-Control-Allow-Headers: Content-Type, Authorization, X-Requested-With\r\n"
        f"Access-Control-Max-Age: 86400\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    ).encode("utf-8") + body_bytes

    writer.write(response)
    await writer.drain()


async def handle_http_request(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """处理 HTTP 请求"""
    server = mcp_server

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

        headers = {}
        body_start_idx = request_text.find("\r\n\r\n")
        if body_start_idx != -1:
            header_lines = request_text[request_text.find("\r\n") + 2:body_start_idx].split("\r\n")
            for line in header_lines:
                if ":" in line:
                    k, v = line.split(":", 1)
                    headers[k.strip().lower()] = v.strip()

        body = request_text[body_start_idx + 4:] if body_start_idx != -1 else ""

        # 解析路径和查询参数
        parsed_path = urlparse(path)
        route = parsed_path.path.rstrip("/")
        query_params = parse_qs(parsed_path.query)

        # ── OPTIONS 预检请求 ──
        if method == "OPTIONS":
            await send_http_response(writer, 204, "application/json", "")
            return

        # ── 路由分发 ──

        if route == "" or route == "/":
            response_data = json.dumps({
                "server": "EIP 门户集成服务",
                "version": "2.0.0",
                "port": MCP_PORT,
                "endpoints": {
                    "tools": list(server.tools.keys()),
                    "mcp": "POST /mcp (JSON-RPC)",
                    "tool_endpoint": "POST /tools/<tool_name>",
                    "restful": [
                        "GET  /api/mail?pageSize=50",
                        "GET  /api/todo?pageSize=10",
                        "GET  /api/task-history?pageSize=10",
                        "POST /api/refresh",
                        "POST /api/set-credentials",
                        "GET  /api/personal-notes?keyword=&pageSize=20&pageNo=1",
                        "POST /api/personal-notes (add)",
                        "DELETE /api/personal-notes (delete, body: {\"id\":\"...\"})",
                        "GET  /api/reminders/pending (轮询待确认提醒)",
                        "POST /api/reminders/ack (body: {\"id\":\"...\"})",
                    ],
                },
            }, ensure_ascii=False)
            await send_http_response(writer, 200, "application/json", response_data)

        # ── RESTful API 路由 ──
        elif route == "/api/mail":
            page_size = int(query_params.get("pageSize", [50])[0])
            page_no = int(query_params.get("pageNo", [1])[0])
            status = query_params.get("status", [""])[0]
            result = await handle_eip_mail(page_size, page_no, status)
            response_data = json.dumps(result, ensure_ascii=False, indent=2)
            await send_http_response(writer, 200, "application/json", response_data)

        elif route == "/api/todo":
            page_size = int(query_params.get("pageSize", [10])[0])
            result = await handle_eip_todo(page_size)
            response_data = json.dumps(result, ensure_ascii=False, indent=2)
            await send_http_response(writer, 200, "application/json", response_data)

        elif route == "/api/task-history":
            page_size = int(query_params.get("pageSize", [10])[0])
            keyword = query_params.get("keyword", [""])[0]
            app_id = query_params.get("appId", [""])[0]
            result = await handle_eip_task_history(page_size, keyword, app_id)
            response_data = json.dumps(result, ensure_ascii=False, indent=2)
            await send_http_response(writer, 200, "application/json", response_data)

        elif route == "/api/refresh" and method == "POST":
            try:
                post_data = json.loads(body) if body else {}
            except json.JSONDecodeError:
                post_data = {}
            username = post_data.get("username", _session["username"])
            password = post_data.get("password", _session["password"])
            result = await handle_eip_refresh(username, password)
            response_data = json.dumps(result, ensure_ascii=False, indent=2)
            await send_http_response(writer, 200, "application/json", response_data)

        elif route == "/api/set-credentials" and method == "POST":
            try:
                post_data = json.loads(body) if body else {}
            except json.JSONDecodeError:
                post_data = {}
            username = post_data.get("username", "")
            password = post_data.get("password", "")
            result = await handle_eip_set_credentials(username, password)
            response_data = json.dumps(result, ensure_ascii=False, indent=2)
            await send_http_response(writer, 200, "application/json", response_data)

        # ── 个人重点事项 RESTful API ──
        elif route == "/api/personal-notes" and method == "GET":
            keyword = query_params.get("keyword", [""])[0]
            page_size = int(query_params.get("pageSize", [20])[0])
            page_no = int(query_params.get("pageNo", [1])[0])
            result = server._handle_list_personal_notes({
                "keyword": keyword,
                "pageSize": page_size,
                "pageNo": page_no,
            })
            response_data = result["result"]["content"][0]["text"]
            await send_http_response(writer, 200, "application/json", response_data)

        elif route == "/api/personal-notes" and method == "POST":
            try:
                post_data = json.loads(body) if body else {}
            except json.JSONDecodeError:
                post_data = {}
            result = server._handle_add_personal_note(post_data)
            response_data = result["result"]["content"][0]["text"]
            await send_http_response(writer, 200, "application/json", response_data)

        elif route == "/api/personal-notes" and method == "DELETE":
            try:
                post_data = json.loads(body) if body else {}
            except json.JSONDecodeError:
                post_data = {}
            result = server._handle_delete_personal_note(post_data)
            response_data = result["result"]["content"][0]["text"]
            await send_http_response(writer, 200, "application/json", response_data)

        # ── 提醒 RESTful API（前端轮询用）──
        elif route == "/api/reminders/pending" and method == "GET":
            result = server._handle_list_due_reminders({})
            response_data = result["result"]["content"][0]["text"]
            await send_http_response(writer, 200, "application/json", response_data)

        elif route == "/api/reminders/ack" and method == "POST":
            try:
                post_data = json.loads(body) if body else {}
            except json.JSONDecodeError:
                post_data = {}
            result = server._handle_ack_reminder(post_data)
            response_data = result["result"]["content"][0]["text"]
            await send_http_response(writer, 200, "application/json", response_data)

        # ── MCP 协议路由 ──
        elif path.startswith("/tools/") and method == "POST":
            tool_name = path.split("/tools/")[1].split("?")[0]
            tool_name = tool_name.rstrip("/")

            try:
                arguments = json.loads(body) if body else {}
            except json.JSONDecodeError:
                arguments = {}

            if tool_name == "get_mail_list":
                result = server._handle_get_mail_list(arguments)
            elif tool_name == "get_todo_list":
                result = server._handle_get_todo_list(arguments)
            elif tool_name == "get_task_history":
                result = server._handle_get_task_history(arguments)
            elif tool_name == "eip_refresh_session":
                result = server._handle_eip_refresh(arguments)
            elif tool_name == "eip_set_credentials":
                result = server._handle_eip_set_credentials(arguments)
            elif tool_name == "add_personal_note":
                result = server._handle_add_personal_note(arguments)
            elif tool_name == "delete_personal_note":
                result = server._handle_delete_personal_note(arguments)
            elif tool_name == "list_personal_notes":
                result = server._handle_list_personal_notes(arguments)
            elif tool_name == "list_due_reminders":
                result = server._handle_list_due_reminders(arguments)
            elif tool_name == "ack_reminder":
                result = server._handle_ack_reminder(arguments)
            else:
                result = {
                    "error": {
                        "code": -32601,
                        "message": f"Tool not found: {tool_name}",
                    }
                }

            response_data = json.dumps(result, ensure_ascii=False)
            await send_http_response(writer, 200, "application/json", response_data)

        elif path == "/mcp" and method == "POST":
            try:
                body_dict = json.loads(body)
            except json.JSONDecodeError:
                response_data = json.dumps({"error": {"code": -32700, "message": "Parse error"}})
                await send_http_response(writer, 400, "application/json", response_data)
                return

            result = server.handle_request(body_dict)
            response_data = json.dumps(result, ensure_ascii=False)
            await send_http_response(writer, 200, "application/json", response_data)

        else:
            response_data = json.dumps({"error": "Not Found"})
            await send_http_response(writer, 404, "application/json", response_data)

    except Exception as e:
        try:
            error_data = json.dumps({"error": str(e)})
            await send_http_response(writer, 500, "application/json", error_data)
        except:
            pass
    finally:
        try:
            writer.close()
        except:
            pass


# ══════════════════════════════════════════════════════════════════════════
# 第五部分：主入口
# ══════════════════════════════════════════════════════════════════════════

# 提醒扫描间隔（秒）：20 秒扫一次，对提醒场景精度足够
REMINDER_SCAN_INTERVAL = 20


async def reminder_loop():
    """后台协程：每 20 秒扫描一次个人重点事项，把已到提醒时间且状态为 pending 的置为 sent。

    置为 sent 后即进入"待确认提醒"列表，前端轮询 GET /api/reminders/pending 拉取。
    用户确认（ack）后状态为 acked，不再返回。重启后 pending 且已到期的会补触发一次（提醒不丢）。
    """
    while True:
        try:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for note in PERSONAL_NOTES:
                remind_time = note.get("remindTime", "")
                if remind_time and note.get("remindStatus") == "pending" and remind_time <= now_str:
                    note["remindStatus"] = "sent"
                    note["updateTime"] = now_str
                    print(f"  [提醒] 已触发: {note['title']} (id={note['id']})")
        except Exception as e:  # 扫描协程绝不能挂掉
            print(f"  [提醒] 扫描异常: {e}")
        await asyncio.sleep(REMINDER_SCAN_INTERVAL)


async def main():
    """启动 HTTP 服务"""
    global mcp_server, _event_loop
    mcp_server = MCPServer()
    _event_loop = asyncio.get_event_loop()

    # 初始设置凭据（从环境变量读取，禁止硬编码默认值）
    _session["username"] = os.environ.get("EIP_USERNAME", "")
    _session["password"] = os.environ.get("EIP_PASSWORD", "")

    # 启动提醒扫描后台协程
    asyncio.create_task(reminder_loop())

    server = await asyncio.start_server(
        handle_http_request,
        host=MCP_HOST,
        port=MCP_PORT,
    )

    addr = server.sockets[0].getsockname()
    print("")
    print(f"  EIP 门户集成服务已启动")
    print(f"  ─────────────────────────────")
    print(f"  监听端口: {addr[0]}:{addr[1]}")
    print(f"  当前用户: {_session['username']}")
    print("")
    print(f"  [MCP 工具] 共 {len(mcp_server.tools)} 个:")
    print(f"    代理: get_mail_list, get_todo_list, get_task_history, eip_refresh_session, eip_set_credentials")
    print(f"    重点事项: add_personal_note, delete_personal_note, list_personal_notes")
    print(f"  [API 端点]")
    print(f"    MCP:        POST http://127.0.0.1:{MCP_PORT}/mcp")
    print(f"    Tool:       POST http://127.0.0.1:{MCP_PORT}/tools/<tool_name>")
    print(f"    Mail:       GET  http://127.0.0.1:{MCP_PORT}/api/mail?pageSize=50")
    print(f"    Todo:       GET  http://127.0.0.1:{MCP_PORT}/api/todo?pageSize=10")
    print(f"    TaskHist:   GET  http://127.0.0.1:{MCP_PORT}/api/task-history?pageSize=10")
    print(f"    Refresh:    POST http://127.0.0.1:{MCP_PORT}/api/refresh")
    print(f"    SetCreds:   POST http://127.0.0.1:{MCP_PORT}/api/set-credentials")
    print(f"    Notes:      GET  http://127.0.0.1:{MCP_PORT}/api/personal-notes")
    print(f"    Notes:      POST http://127.0.0.1:{MCP_PORT}/api/personal-notes")
    print(f"    Notes:      DELETE http://127.0.0.1:{MCP_PORT}/api/personal-notes")
    print(f"    Reminder:   GET  http://127.0.0.1:{MCP_PORT}/api/reminders/pending")
    print(f"    Reminder:   POST http://127.0.0.1:{MCP_PORT}/api/reminders/ack (body: {{\"id\":\"...\"}})")
    print(f"  提醒扫描: 每 {REMINDER_SCAN_INTERVAL} 秒一次（pending -> sent）")
    print("")

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
