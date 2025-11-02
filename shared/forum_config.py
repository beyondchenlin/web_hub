"""
统一论坛配置加载器。

该模块从 `config/forum_settings.yaml` 读取论坛地址与凭证，并允许环境变量覆盖。
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "forum_settings.yaml"


class ForumConfigError(RuntimeError):
    """论坛配置异常。"""


def _merge_env_overrides(config: Dict[str, Any]) -> Dict[str, Any]:
    """使用环境变量覆盖配置文件中的值。"""
    forum = config.setdefault("forum", {})
    credentials = config.setdefault("credentials", {})

    forum["base_url"] = os.getenv("FORUM_BASE_URL", forum.get("base_url", "")).rstrip("/")
    forum["target_url"] = os.getenv("FORUM_TARGET_URL", forum.get("target_url", ""))
    forum["forum_id"] = int(os.getenv("FORUM_TARGET_FORUM_ID", forum.get("forum_id", 0) or 0))

    credentials["username"] = os.getenv(
        "FORUM_USERNAME",
        os.getenv("AICUT_ADMIN_USERNAME", credentials.get("username", "")),
    )
    credentials["password"] = os.getenv(
        "FORUM_PASSWORD",
        os.getenv("AICUT_ADMIN_PASSWORD", credentials.get("password", "")),
    )

    return config


@lru_cache()
def load_forum_settings(config_path: str | Path | None = None) -> Dict[str, Any]:
    """
    加载论坛配置。

    Args:
        config_path: 可选自定义配置路径，缺省读取默认路径或环境变量 `FORUM_CONFIG_PATH`。

    Returns:
        dict: 包含 forum、credentials 等键的配置。
    """

    path = Path(
        config_path
        or os.getenv("FORUM_CONFIG_PATH", DEFAULT_CONFIG_PATH)
    ).expanduser().resolve()

    if not path.exists():
        raise ForumConfigError(f"未找到论坛配置文件: {path}")

    try:
        with path.open("r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
    except yaml.YAMLError as exc:
        raise ForumConfigError(f"解析论坛配置失败: {exc}") from exc

    if "forum" not in config:
        config["forum"] = {}
    if "credentials" not in config:
        config["credentials"] = {}

    config = _merge_env_overrides(config)

    # 基础校验
    if not config["forum"].get("base_url") or not config["forum"].get("target_url"):
        raise ForumConfigError("论坛地址配置不完整，请检查 base_url 与 target_url")

    if not config["credentials"].get("username") or not config["credentials"].get("password"):
        print("⚠️ 论坛凭证未在配置或环境变量中设置，登录可能失败")

    return config


def get_forum_base_url() -> str:
    """获取论坛基础 URL。"""
    return load_forum_settings()["forum"]["base_url"]


def get_forum_target_url() -> str:
    """获取目标板块 URL。"""
    return load_forum_settings()["forum"]["target_url"]


def get_forum_credentials() -> Dict[str, str]:
    """获取论坛用户名与密码。"""
    settings = load_forum_settings()
    return {
        "username": settings["credentials"].get("username", ""),
        "password": settings["credentials"].get("password", ""),
    }


__all__ = [
    "ForumConfigError",
    "load_forum_settings",
    "get_forum_base_url",
    "get_forum_target_url",
    "get_forum_credentials",
]

