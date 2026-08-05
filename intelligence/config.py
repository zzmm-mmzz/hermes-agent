"""Configuration for intelligence center integration."""
import os
import tomllib
from pathlib import Path
from dataclasses import dataclass


@dataclass
class IntelligenceConfig:
    """情报中心配置"""
    base_url: str = "http://127.0.0.1:10010"
    client_id: str = ""
    client_secret: str = ""

    @property
    def token_url(self) -> str:
        return f"{self.base_url}/api/auth/token"

    @property
    def list_url(self) -> str:
        return f"{self.base_url}/api/intelligence/list"

    @property
    def detail_url(self) -> str:
        return f"{self.base_url}/api/intelligence/detail"

    @property
    def categories_url(self) -> str:
        return f"{self.base_url}/api/intelligence/categories"


def load_config() -> IntelligenceConfig:
    """加载情报中心配置"""
    # 优先从环境变量读取（Docker 部署用）
    env_base_url = os.environ.get("INTELLIGENCE_BASE_URL")
    env_client_id = os.environ.get("INTELLIGENCE_CLIENT_ID")
    env_client_secret = os.environ.get("INTELLIGENCE_CLIENT_SECRET")

    if env_base_url:
        return IntelligenceConfig(
            base_url=env_base_url,
            client_id=env_client_id or "",
            client_secret=env_client_secret or "",
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
                    client_id=cfg.get("client_id", IntelligenceConfig.client_id),
                    client_secret=cfg.get("client_secret", IntelligenceConfig.client_secret),
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
