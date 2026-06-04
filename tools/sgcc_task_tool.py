"""
SGCC (State Grid / 国网湖南电力) 任务系统网关连接器

读取 config/sgcc.yaml 中的配置，提供查询主任务下子任务反馈情况的工具。

注册的 LLM 可调用工具:
- sgcc_query_dept_sub_task -- 按部门查询主任务下子任务反馈情况

此工具集默认启用（不在 _DEFAULT_OFF_TOOLSETS 中），
只要 config/sgcc.yaml 存在且配置正确即可使用。
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 配置加载
# ---------------------------------------------------------------------------

_CONFIG_CACHE: Optional[Dict[str, Any]] = None


def _get_config_path() -> Path:
    """查找 sgcc.yaml 配置文件路径。"""
    # 优先环境变量
    env_path = os.getenv("SGCC_CONFIG_PATH")
    if env_path:
        return Path(env_path)

    # 相对于 hermes-agent 项目根目录
    here = Path(__file__).resolve().parent  # tools/
    project_root = here.parent  # hermes-agent/
    candidate = project_root / "config" / "sgcc.yaml"
    if candidate.exists():
        return candidate

    # 回退到用户 home 目录
    home_candidate = Path.home() / ".hermes" / "sgcc.yaml"
    if home_candidate.exists():
        return home_candidate

    return candidate


def _load_config() -> Dict[str, Any]:
    """加载 sgcc.yaml 配置。"""
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE

    import yaml

    config_path = _get_config_path()
    if not config_path.exists():
        _CONFIG_CACHE = {}
        logger.warning("SGCC config not found at %s", config_path)
        return _CONFIG_CACHE

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            _CONFIG_CACHE = yaml.safe_load(f) or {}
        logger.info("Loaded SGCC config from %s", config_path)
    except Exception as e:
        _CONFIG_CACHE = {}
        logger.error("Failed to load SGCC config %s: %s", config_path, e)

    return _CONFIG_CACHE


def _build_url(endpoint_name: str) -> Optional[str]:
    """根据配置中的 endpoint 名称构建完整 URL。"""
    config = _load_config()
    if not config:
        return None

    host = config.get("host", "25.212.194.221")
    port = config.get("port", 18081)
    api_prefix = config.get("api_prefix", "/api/dcdb")
    endpoints = config.get("endpoints", {})

    ep = endpoints.get(endpoint_name)
    if not ep:
        logger.error("Endpoint '%s' not found in config", endpoint_name)
        return None

    path = ep.get("path", "")
    return f"http://{host}:{port}{api_prefix}{path}"


def _get_headers() -> Dict[str, str]:
    """返回 HTTP 请求头。"""
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _check_sgcc_available() -> bool:
    """检查配置是否可用（check_fn - 工具自动注册的条件）。"""
    config = _load_config()
    if not config:
        return False
    host = config.get("host")
    port = config.get("port")
    return bool(host) and bool(port)


# ---------------------------------------------------------------------------
# API 调用
# ---------------------------------------------------------------------------

async def _async_query_dept_sub_task(
    main_task_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    按部门查询主任务下子任务反馈情况。

    Args:
        main_task_id: 主任务ID。如果为 None 或空字符串，查询所有任务。

    Returns:
        包含 code、message 和 data 的字典。
    """
    import aiohttp

    url = _build_url("get_all_dept_sub_task")
    if not url:
        return {
            "code": "-1",
            "message": "配置加载失败，请检查 config/sgcc.yaml",
            "data": None,
        }

    payload: Dict[str, Any] = {}
    if main_task_id:
        payload["mainTaskId"] = main_task_id

    config = _load_config()
    timeout = config.get("timeout", 30)

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                url,
                json=payload,
                headers=_get_headers(),
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                resp.raise_for_status()
                result = await resp.json()
                return result
        except asyncio.TimeoutError:
            return {
                "code": "-1",
                "message": f"请求超时（{timeout}秒）",
                "data": None,
            }
        except aiohttp.ClientError as e:
            return {
                "code": "-1",
                "message": f"请求失败: {str(e)}",
                "data": None,
            }
        except Exception as e:
            return {
                "code": "-1",
                "message": f"未知错误: {str(e)}",
                "data": None,
            }


# ---------------------------------------------------------------------------
# 同步 Handler（LLM 调用入口）
# ---------------------------------------------------------------------------

def _handle_query_dept_sub_task(args: Dict[str, Any], **kwargs) -> str:
    """
    同步 handler - 按部门查询主任务下子任务反馈情况。
    """
    main_task_id = args.get("main_task_id", "") or None

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(
            _async_query_dept_sub_task(main_task_id=main_task_id)
        )
    finally:
        loop.close()

    return json.dumps(result, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# Tool Schema
# ---------------------------------------------------------------------------

SGCC_QUERY_DEPT_SUB_TASK_SCHEMA = {
    "type": "object",
    "properties": {
        "main_task_id": {
            "type": "string",
            "description": (
                "主任务ID。传入具体ID查询指定主任务下的子任务反馈；"
                "不传或传空则查询所有任务。"
            ),
        },
    },
}

# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

from tools.registry import registry, tool_error

registry.register(
    name="sgcc_query_dept_sub_task",
    toolset="sgcc",
    schema=SGCC_QUERY_DEPT_SUB_TASK_SCHEMA,
    handler=_handle_query_dept_sub_task,
    check_fn=_check_sgcc_available,
    emoji="",
    description=(
        "按部门查询国网湖南电力主任务下子任务反馈情况。"
        "通过 main_task_id 指定查询某个主任务的各子任务在各部门的反馈情况，"
        "或不传 main_task_id 查询所有任务。"
    ),
)
