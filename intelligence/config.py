"""Configuration for intelligence center integration (XiangDian LiaoWang data source)."""
import os
import tomllib
from pathlib import Path
from dataclasses import dataclass


@dataclass
class IntelligenceConfig:
    """湘电瞭望数据源配置"""
    base_url: str = "http://25.212.193.27:18080"
    app_key: str = ""
    app_name: str = "XDLW_THRID_10_AUTH"
    isc: str = "XDLW_THRID_10_AUTH"

    @property
    def token_url(self) -> str:
        return f"{self.base_url}/upms/thrid/authorize"

    @property
    def list_url(self) -> str:
        return f"{self.base_url}/qbzx/article/recommendNew"


def load_config() -> IntelligenceConfig:
    """加载湘电瞭望配置"""
    # 优先从环境变量读取（Docker 部署用）
    env_base_url = os.environ.get("XDLW_BASE_URL")
    env_app_key = os.environ.get("XDLW_APP_KEY")
    env_app_name = os.environ.get("XDLW_APP_NAME")
    env_isc = os.environ.get("XDLW_ISC")

    if env_base_url:
        return IntelligenceConfig(
            base_url=env_base_url,
            app_key=env_app_key or "",
            app_name=env_app_name or "XDLW_THRID_10_AUTH",
            isc=env_isc or "XDLW_THRID_10_AUTH",
        )

    # 其次从 config.toml 读取
    config_paths = [
        Path(__file__).resolve().parent / "config.toml",               # 源码目录
        Path("/app/intelligence/config.toml"),                         # Docker 容器内
    ]

    for path in config_paths:
        if path.exists():
            try:
                data = tomllib.loads(path.read_text(encoding="utf-8"))
                cfg = data.get("intelligence", {})
                return IntelligenceConfig(
                    base_url=cfg.get("base_url", IntelligenceConfig.base_url),
                    app_key=cfg.get("app_key", IntelligenceConfig.app_key),
                    app_name=cfg.get("app_name", IntelligenceConfig.app_name),
                    isc=cfg.get("isc", IntelligenceConfig.isc),
                )
            except Exception:
                pass

    return IntelligenceConfig()


# 全局配置实例
_config: IntelligenceConfig | None = None


def get_config() -> IntelligenceConfig:
    """获取全局配置实例"""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reload_config() -> IntelligenceConfig:
    """重新加载配置"""
    global _config
    _config = load_config()
    return _config
