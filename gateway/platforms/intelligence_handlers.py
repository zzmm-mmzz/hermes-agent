"""HTTP handlers for intelligence center API - for web page consumption."""
import json
import logging

from aiohttp import web

from intelligence.client import fetch_list, fetch_detail, fetch_categories

logger = logging.getLogger(__name__)


async def handle_intelligence_list(request: web.Request) -> web.Response:
    """GET /api/intelligence/list — 资讯列表"""
    try:
        page = int(request.query.get("page", 1))
        limit = int(request.query.get("limit", 10))
        category = request.query.get("category", "")
        result = await fetch_list(page=page, limit=limit, category=category)
        return web.json_response(result)
    except Exception as e:
        logger.error("Intelligence list error: %s", e)
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def handle_intelligence_detail(request: web.Request) -> web.Response:
    """GET /api/intelligence/detail — 资讯详情"""
    try:
        item_id = request.query.get("id", "")
        if not item_id:
            return web.json_response({"success": False, "error": "id is required"}, status=400)
        result = await fetch_detail(item_id)
        return web.json_response(result)
    except Exception as e:
        logger.error("Intelligence detail error: %s", e)
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def handle_intelligence_categories(request: web.Request) -> web.Response:
    """GET /api/intelligence/categories — 栏目分类"""
    try:
        result = await fetch_categories()
        return web.json_response(result)
    except Exception as e:
        logger.error("Intelligence categories error: %s", e)
        return web.json_response({"success": False, "error": str(e)}, status=500)
