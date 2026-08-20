"""mcp_embed.py - 随主网关内嵌集成 EIP Mock 服务

EIP Mock 原本需要单独启动 (python server.py, 端口 8200)：
  1. mcp-eip-mock         ->  8200  (MCP JSON-RPC / REST / reminder_loop)

改造后（方案 B：aiohttp 路由挂载）：
  - mcp-eip-mock 的路由通过 make_app() 直接挂进主网关 (api_server)，
    不再占用独立端口 8200；
  - 本模块只负责：加载 server.py（模块单例）、初始化全局状态、
    启动 reminder_loop 后台扫描协程（每 20 秒扫一次个人重点事项）。

说明：mcp-core-indicators (8100) 已迁移为主网关内置的 Indicators API
(indicators/ 模块，/api/indicators/* 路由)，不再以独立 MCP 服务方式随
网关启动。原 project/mcp-core-indicators/server.py 保留，可单独运行。

关键点：
- server.py 模块名可能重复，必须按路径加载；_get_module() 幂等，保证
  make_app() 与 start_all() 拿到同一个模块实例（同一份 PERSONAL_NOTES /
  _session / mcp_server 全局状态），避免状态分裂；
- eip-mock 需要额外初始化: mcp_server 实例、_session 凭据、
  reminder_loop 后台扫描协程（每 20 秒扫一次个人重点事项）；
- 任一 MCP 启动失败只记告警，绝不阻塞网关启动；
- start_all() 幂等：已启动则直接跳过（connect() 可能被调用多次）。
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
_module = None  # server.py 模块单例


def _load_module(name: str, path: str):
    """按文件路径加载模块（避免模块名冲突）。"""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载模块: {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _get_module():
    """获取 server.py 模块单例（幂等）。make_app 与 start_all 共用同一实例。"""
    global _module
    if _module is None:
        _module = _load_module("mcp_eip_mock_embedded", _EIP_MOCK_PATH)
    return _module


def _init_state(mod) -> None:
    """复刻 server.py main() 中的初始化步骤（mcp_server / _session 凭据）。"""
    if mod.mcp_server is None:
        mod.mcp_server = mod.MCPServer()
    mod._session["username"] = os.environ.get("EIP_USERNAME", "")
    mod._session["password"] = os.environ.get("EIP_PASSWORD", "")


def make_app(prefix: str = "/api/eip"):
    """返回 eip-mock 的 aiohttp 应用（供 api_server 挂载复用）。

    Args:
        prefix: 路由前缀，默认 "/api/eip"，避免 /mcp、/tools/<name> 等通用
                路径与主网关其他路由冲突。传 "" 则注册原始路径。
    """
    mod = _get_module()
    _init_state(mod)
    return mod.make_app(prefix=prefix)


async def start_all() -> None:
    """初始化 eip-mock 并启动后台扫描协程。幂等：已启动则跳过。失败仅告警不抛出。

    注意：不再以独立端口 8200 启动 HTTP 服务——路由已由 api_server 通过
    make_app() 挂载进主网关。若需独立运行，直接 python server.py 即可。
    """
    global _started
    if _started:
        return

    # ── mcp-eip-mock（挂载模式，无独立端口）────────────────────────────────
    try:
        eip_mod = _get_module()
        _init_state(eip_mod)
        _tasks.append(asyncio.create_task(eip_mod.reminder_loop()))
        logger.info("[mcp-embed] eip-mock 已挂载进主网关（路由前缀 /api/eip，提醒扫描已开启）")
    except Exception:
        logger.exception("[mcp-embed] eip-mock 初始化失败（不影响网关）")

    _started = True
