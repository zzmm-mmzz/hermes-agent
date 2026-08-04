"""Intelligence center tool for Hermes Agent."""
import json
import logging

from tools.registry import registry

logger = logging.getLogger(__name__)

# Tool schema
INTELLIGENCE_SEARCH_SCHEMA = {
    "description": "查询情报中心的电力相关资讯。可以按分页和栏目分类获取资讯列表、查看详情。",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "操作类型：list=获取资讯列表，detail=获取资讯详情，categories=获取栏目分类",
                "enum": ["list", "detail", "categories"],
            },
            "page": {
                "type": "integer",
                "description": "页码（仅 list 用），默认 1",
            },
            "limit": {
                "type": "integer",
                "description": "每页条数（仅 list 用），默认 10",
            },
            "category": {
                "type": "string",
                "description": "栏目分类（仅 list 用），空字符串表示全部",
            },
            "item_id": {
                "type": "string",
                "description": "资讯ID（仅 detail 用）",
            },
        },
        "required": ["action"],
    },
}


def intelligence_tool_handler(args: dict, **kwargs) -> str:
    """Handler for intelligence center queries."""
    import asyncio

    from intelligence.client import fetch_list, fetch_detail, fetch_categories

    action = args.get("action")

    try:
        if action == "list":
            page = args.get("page", 1)
            limit = args.get("limit", 10)
            category = args.get("category", "")
            result = asyncio.run(fetch_list(page=page, limit=limit, category=category))
        elif action == "detail":
            item_id = args.get("item_id", "")
            if not item_id:
                return json.dumps({"error": "item_id is required for detail action"}, ensure_ascii=False)
            result = asyncio.run(fetch_detail(item_id))
        elif action == "categories":
            result = asyncio.run(fetch_categories())
        else:
            return json.dumps({"error": f"Unknown action: {action}"}, ensure_ascii=False)

        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.exception("Intelligence tool error: %s", e)
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# Register the tool
registry.register(
    name="intelligence",
    toolset="general",
    schema=INTELLIGENCE_SEARCH_SCHEMA,
    handler=intelligence_tool_handler,
    emoji="📡",
    description="查询情报中心的电力相关资讯",
)
