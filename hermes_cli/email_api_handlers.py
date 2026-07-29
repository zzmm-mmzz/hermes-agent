"""邮箱配置管理 API Handler

独立文件，由 gateway/platforms/api_server.py 导入并注册路由。
"""

import json
from typing import Optional

from aiohttp import web
from mailcli.storage import config as cfg


async def handle_email_accounts(request: web.Request) -> web.Response:
    """GET /api/email/accounts — 列出所有账号"""
    auth_err = _check_auth(request)
    if auth_err:
        return auth_err

    data = cfg.load_config()
    accounts = []
    for name, acct in data.get("accounts", {}).items():
        auth = acct.get("auth", {})
        accounts.append({
            "name": name,
            "username": auth.get("username", ""),
            "receive": acct.get("receive", {}).get("host", ""),
            "send": acct.get("send", {}).get("host", ""),
        })
    return web.json_response({"accounts": accounts})


async def handle_email_account_get(request: web.Request) -> web.Response:
    """GET /api/email/accounts/{name} — 查看账号详情"""
    auth_err = _check_auth(request)
    if auth_err:
        return auth_err

    name = request.match_info.get("name", "")
    acct = cfg.get_account_config(name)
    if not acct:
        return web.json_response(
            {"error": f"账号 '{name}' 不存在"}, status=404
        )
    safe = {}
    for section in ("auth", "receive", "send"):
        if section in acct:
            safe[section] = {k: v for k, v in acct[section].items() if k != "secret"}
    return web.json_response({"account": safe})


async def handle_email_account_add(request: web.Request) -> web.Response:
    """POST /api/email/accounts — 添加账号"""
    auth_err = _check_auth(request)
    if auth_err:
        return auth_err

    body = await request.json()
    name = body.pop("name", "default")
    data = cfg.load_config()
    if "accounts" not in data:
        data["accounts"] = {}
    if name in data["accounts"]:
        return web.json_response(
            {"error": f"账号 '{name}' 已存在"}, status=400
        )
    data["accounts"][name] = body
    cfg.write_config(data)
    return web.json_response({"message": f"账号 '{name}' 已创建"})


async def handle_email_account_update(request: web.Request) -> web.Response:
    """PATCH /api/email/accounts/{name} — 更新账号（深度合并）"""
    auth_err = _check_auth(request)
    if auth_err:
        return auth_err

    name = request.match_info.get("name", "")
    data = cfg.load_config()
    if "accounts" not in data or name not in data.get("accounts", {}):
        return web.json_response(
            {"error": f"账号 '{name}' 不存在"}, status=404
        )
    body = await request.json()
    data["accounts"][name] = _deep_merge(data["accounts"][name], body)
    cfg.write_config(data)
    return web.json_response({"message": f"账号 '{name}' 已更新"})


async def handle_email_account_delete(request: web.Request) -> web.Response:
    """DELETE /api/email/accounts/{name} — 删除账号"""
    auth_err = _check_auth(request)
    if auth_err:
        return auth_err

    name = request.match_info.get("name", "")
    data = cfg.load_config()
    if "accounts" not in data or name not in data.get("accounts", {}):
        return web.json_response(
            {"error": f"账号 '{name}' 不存在"}, status=404
        )
    del data["accounts"][name]
    cfg.write_config(data)
    return web.json_response({"message": f"账号 '{name}' 已删除"})


def _check_auth(request: web.Request) -> Optional[web.Response]:
    """验证请求认证"""
    adapter = request.app.get("api_server_adapter")
    if adapter and hasattr(adapter, "_check_auth"):
        return adapter._check_auth(request)
    return None


def _deep_merge(base: dict, override: dict) -> dict:
    """递归深度合并"""
    result = dict(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result