"""mcp_embed.py - 随主网关启动内嵌拉起 MCP 服务

MCP 原本需要单独启动 (python server.py)：
  1. mcp-eip-mock         ->  8200  (MCP JSON-RPC / REST / reminder_loop)

说明：mcp-core-indicators (8100) 已迁移为主网关内置的 Indicators API
(indicators/ 模块，/api/indicators/* 路由)，不再以独立 MCP 服务方式随
网关启动。原 project/mcp-core-indicators/server.py 保留，可单独运行。

本模块在主网关 (api_server) 启动时通过 importlib 按文件路径加载
server.py 并作为后台 asyncio 服务启动，网关一跑即自动在线。

关键点：
- server.py 模块名可能重复，必须按路径加载
- eip-mock 需要额外初始化: mcp_server 实例、_event_loop、_session 凭据、
  reminder_loop 后台扫描协程（每 20 秒扫一次个人重点事项）
- 任一 MCP 启动失败只记告警，绝不阻塞网关启动
- start_all() 幂等：已启动则直接跳过（connect() 可能被调用多次）
"""
import asyncio
import importlib.util
import logging
import os
import sys

logger = logging.getLogger(__name__)

# ── 路径 ────────────────────────────────────────────────────────────────────
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_EIP_MOCK_PATH = os.path.join(_BASE_DIR, "project", "mcp-eip-mock", "server.py")

# 保持强引用，防止被 GC
_servers: list = []
_tasks: list = []
_started = False


def _load_module(name: str, path: str):
    """按文件路径加载模块（避免模块名冲突）。"""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载模块: {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


async def start_all() -> None:
    """启动 eip-mock MCP 服务。幂等：已启动则跳过。失败仅告警不抛出。"""
    global _started
    if _started:
        return

    # ── mcp-eip-mock (8200) ────────────────────────────────────────────────
    try:
        eip_mod = _load_module("mcp_eip_mock_embedded", _EIP_MOCK_PATH)
        # 复刻 server.py main() 中的初始化步骤
        eip_mod.mcp_server = eip_mod.MCPServer()
        eip_mod._event_loop = asyncio.get_event_loop()
        eip_mod._session["username"] = os.environ.get("EIP_USERNAME", "")
        eip_mod._session["password"] = os.environ.get("EIP_PASSWORD", "")
        _tasks.append(asyncio.create_task(eip_mod.reminder_loop()))
        eip_server = await asyncio.start_server(
            eip_mod.handle_http_request, eip_mod.MCP_HOST, eip_mod.MCP_PORT
        )
        _servers.append(eip_server)
        logger.info("[mcp-embed] eip-mock MCP 已随网关启动: %s:%s（提醒扫描已开启）",
                    eip_mod.MCP_HOST, eip_mod.MCP_PORT)
    except Exception:
        logger.exception("[mcp-embed] eip-mock MCP 启动失败（不影响网关）")

    _started = True
