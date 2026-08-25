"""indicators/config.py - 指标模块配置加载

从 indicators/config.toml 读取配置，支持环境变量覆盖（Docker 部署用）。
"""
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = _BASE_DIR / "config.toml"

_DEFAULTS = {
    "platform_base_url": "http://22.56.118.69:8086",
    "backend_base_url": "https://localhost:18082",
    "backend_api_prefix": "/indicators",
    "auth_mode": "login_md5",
    "scripts_dir": "~/.hermes/custom_indicators",
    "area_js_path": str(_BASE_DIR / "area.js"),
    "cache_login_context": True,
}


def _load_toml() -> dict:
    """读取 config.toml 的 [indicators] 段，失败时返回空。"""
    try:
        import tomllib
    except ImportError:  # Python < 3.11
        try:
            import tomli as tomllib  # type: ignore
        except ImportError:
            return {}
    try:
        with open(CONFIG_PATH, "rb") as f:
            data = tomllib.load(f)
        return data.get("indicators", {}) or {}
    except Exception as e:
        logger.warning("load config.toml failed: %s", e)
        return {}


def _resolve_path(raw: str) -> str:
    """展开 ~ 为用户主目录；相对路径基于 hermes-agent 根目录解析，返回绝对路径。"""
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = _BASE_DIR.parent / p  # hermes-agent 根目录
    return str(p.resolve())


def get_config() -> dict:
    """合并 config.toml + 环境变量，返回完整配置。"""
    cfg = dict(_DEFAULTS)
    cfg.update(_load_toml())

    # 环境变量覆盖（Docker 部署用）
    env_map = {
        "INDICATOR_PLATFORM_URL": "platform_base_url",
        "INDICATOR_BACKEND_URL": "backend_base_url",
        "INDICATOR_SCRIPTS_DIR": "scripts_dir",
        "INDICATOR_AREA_JS": "area_js_path",
    }
    for env_key, cfg_key in env_map.items():
        val = os.environ.get(env_key)
        if val:
            cfg[cfg_key] = val

    # 路径展开
    cfg["scripts_dir"] = _resolve_path(cfg["scripts_dir"])
    if cfg.get("area_js_path"):
        cfg["area_js_path"] = _resolve_path(cfg["area_js_path"])

    cfg["cache_login_context"] = str(cfg.get("cache_login_context", True)).lower() in ("1", "true", "yes")
    return cfg


# 模块级单例（首次 import 时加载一次，热加载脚本时不需要重载此配置）
CONFIG = get_config()
