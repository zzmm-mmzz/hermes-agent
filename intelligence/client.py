"""HTTP client for intelligence center API."""
import json
import logging
from typing import Any

import aiohttp

from intelligence.config import get_config

logger = logging.getLogger(__name__)


async def _request(method: str, url: str, **kwargs) -> dict[str, Any]:
    """发送 HTTP 请求到情报中心"""
    cfg = get_config()
    headers = kwargs.pop("headers", {})
    headers.setdefault("Content-Type", "application/json")

    # Bearer token 认证（如果有 client_id/secret，先获取 token）
    if cfg.client_id and cfg.client_secret:
        token = await _get_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, headers=headers, **kwargs) as resp:
                text = await resp.text()
                if resp.status >= 400:
                    logger.warning("Intelligence API error: %s %s -> %s", method, url, text)
                    return {"success": False, "error": f"HTTP {resp.status}: {text[:200]}"}
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return {"success": True, "data": text}
    except aiohttp.ClientError as e:
        logger.error("Intelligence API request failed: %s", e)
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error("Intelligence API unexpected error: %s", e)
        return {"success": False, "error": str(e)}


_token_cache: dict[str, Any] = {}


async def _get_token() -> str | None:
    """获取 Bearer token（带缓存）"""
    import time
    now = time.time()
    if _token_cache.get("token") and _token_cache.get("expires_at", 0) > now:
        return _token_cache["token"]

    cfg = get_config()
    if not cfg.client_id or not cfg.client_secret:
        return None

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                cfg.token_url,
                json={"client_id": cfg.client_id, "client_secret": cfg.client_secret},
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    token = data.get("access_token") or data.get("token")
                    expires_in = data.get("expires_in", 3600)
                    if token:
                        _token_cache["token"] = token
                        _token_cache["expires_at"] = now + expires_in - 60
                        return token
    except Exception as e:
        logger.warning("Failed to get intelligence token: %s", e)

    return None


async def fetch_list(page: int = 1, limit: int = 10, category: str = "") -> dict[str, Any]:
    """获取情报资讯列表（接口 3.1）"""
    cfg = get_config()
    payload = {"page": page, "limit": limit}
    if category:
        payload["category"] = category
    return await _request("POST", cfg.list_url, json=payload)


async def fetch_detail(item_id: str | int) -> dict[str, Any]:
    """获取情报资讯详情（接口 3.2）"""
    cfg = get_config()
    return await _request("GET", cfg.detail_url, params={"id": str(item_id)})


async def fetch_categories() -> dict[str, Any]:
    """获取栏目分类"""
    cfg = get_config()
    return await _request("GET", cfg.categories_url)
