"""HTTP client for XiangDian LiaoWang (湘电瞭望) intelligence API.

对外接口保持与情报中心版一致：
- fetch_list   -> 调湘电 recommendNew，网关侧分页
- fetch_detail -> 从最近一次 recommendNew 缓存按 id 取（湘电无独立详情接口）
- fetch_categories -> 湘电无栏目概念，返回空列表
"""
import json
import logging
import time
from typing import Any

import aiohttp

from intelligence.config import get_config

logger = logging.getLogger(__name__)

# 湘电 recommendNew 返回的全量 records 缓存（供 detail 查询）
_records_cache: list[dict[str, Any]] = []
_records_cache_at: float = 0.0


def _map_record(rec: dict[str, Any]) -> dict[str, Any]:
    """把湘电 records 条目映射为对外接口格式。"""
    content = rec.get("content") or ""
    summary = (rec.get("summary") or content[:80] or "").strip()
    return {
        "id": str(rec.get("id", "")),
        "title": rec.get("title") or "",
        "summary": summary,
        "source": rec.get("source") or "",
        "publishTime": rec.get("publishTime") or "",
        "image": rec.get("image") or "",
        "content": content,
        "status": "已发布",
        "author": rec.get("author") or "",
        "viewCount": int(rec.get("viewCount") or 0),
        "hasDetail": True,
    }


async def _request(method: str, url: str, **kwargs) -> dict[str, Any]:
    """发送 HTTP 请求到湘电瞭望（xt-token 鉴权）。"""
    headers = kwargs.pop("headers", {})
    headers.setdefault("Content-Type", "application/json")

    token = await _get_token()
    if token:
        headers["xt-token"] = token

    try:
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, headers=headers, **kwargs) as resp:
                text = await resp.text()
                if resp.status >= 400:
                    logger.warning("XDLW API error: %s %s -> %s", method, url, text)
                    return {"success": False, "error": f"HTTP {resp.status}: {text[:200]}"}
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return {"success": True, "data": text}
    except aiohttp.ClientError as e:
        logger.error("XDLW API request failed: %s", e)
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error("XDLW API unexpected error: %s", e)
        return {"success": False, "error": str(e)}


_token_cache: dict[str, Any] = {}


async def _get_token() -> str | None:
    """获取 xt-token（带缓存，按 tokenTimeout 过期自动刷新）。"""
    now = time.time()
    if _token_cache.get("token") and _token_cache.get("expires_at", 0) > now:
        return _token_cache["token"]

    cfg = get_config()
    if not cfg.app_key:
        return None

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                cfg.token_url,
                params={"appKey": cfg.app_key, "appName": cfg.app_name},
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    inner = data.get("data") or {}
                    token = inner.get("tokenValue") or data.get("tokenValue")
                    timeout = int(inner.get("tokenTimeout") or data.get("tokenTimeout") or 1699)
                    if token:
                        _token_cache["token"] = token
                        # 提前 60 秒过期，避免临界失效
                        _token_cache["expires_at"] = now + timeout - 60
                        return token
                    logger.warning("XDLW token response missing tokenValue: %s", str(data)[:200])
    except Exception as e:
        logger.warning("Failed to get XDLW token: %s", e)

    return None


async def _fetch_all_records() -> list[dict[str, Any]]:
    """调用湘电 recommendNew 获取全量新闻列表。"""
    global _records_cache, _records_cache_at

    cfg = get_config()
    result = await _request("POST", cfg.list_url, json={"isc": cfg.isc})
    if not result.get("success", True) or "error" in result:
        logger.warning("XDLW recommendNew failed: %s", result)
        return _records_cache  # 失败时回退上次缓存

    data = result.get("data") or {}
    records = data.get("records") or []
    _records_cache = [_map_record(r) for r in records]
    _records_cache_at = time.time()
    return _records_cache


async def fetch_list(page: int = 1, limit: int = 10, category: str = "") -> dict[str, Any]:
    """获取资讯列表（调湘电 recommendNew 后网关侧分页）。"""
    try:
        records = await _fetch_all_records()
    except Exception as e:
        logger.error("XDLW fetch_list error: %s", e)
        return {"success": False, "code": 500, "error": str(e)}

    total = len(records)
    start = (page - 1) * limit
    end = min(start + limit, total)
    items = []
    for rec in records[start:end]:
        slim = dict(rec)
        # list 接口不带完整 content
        slim.pop("content", None)
        items.append(slim)

    return {"success": True, "code": 200, "data": items, "total": total, "page": page, "limit": limit}


async def fetch_detail(item_id: str | int) -> dict[str, Any]:
    """获取资讯详情（从 recommendNew 缓存按 id 查，miss 时重新拉取）。"""
    item_id = str(item_id)
    records = _records_cache or await _fetch_all_records()
    for rec in records:
        if rec["id"] == item_id:
            return {"success": True, "code": 200, "data": rec}

    # 缓存 miss：重新拉一次再查
    records = await _fetch_all_records()
    for rec in records:
        if rec["id"] == item_id:
            return {"success": True, "code": 200, "data": rec}

    return {"success": False, "code": 404, "error": f"资讯不存在: {item_id}"}


async def fetch_categories() -> dict[str, Any]:
    """获取栏目分类（湘电无栏目概念，返回空列表）。"""
    return {"success": True, "code": 200, "data": []}
