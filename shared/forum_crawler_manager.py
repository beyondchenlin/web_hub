"""Centralised manager for forum crawler instances."""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

from .forum_config import load_forum_settings

# Lazy import to avoid circular dependencies at module import time
from web_hub.aicut_forum_crawler import AicutForumCrawler


class ForumCrawlerManager:
    """Provide shared access to forum crawlers."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._crawlers: Dict[str, AicutForumCrawler] = {}
        self._settings = load_forum_settings()

    def refresh_settings(self) -> None:
        with self._lock:
            self._settings = load_forum_settings()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------
    def get_crawler(self, forum_name: str = "main") -> AicutForumCrawler:
        name = self._resolve_forum_name(forum_name)
        with self._lock:
            if name not in self._crawlers:
                self._crawlers[name] = self._build_crawler(name)
            return self._crawlers[name]

    def get_forum_threads(self, forum_name: str = "main") -> List[Dict[str, Any]]:
        crawler = self.get_crawler(forum_name)
        self._ensure_logged_in(crawler)
        return crawler.get_forum_threads()

    def monitor_new_posts(self, forum_name: str = "main") -> List[Dict[str, Any]]:
        crawler = self.get_crawler(forum_name)
        self._ensure_logged_in(crawler)
        return crawler.monitor_new_posts()

    def get_post_detail(self, thread_url: str, forum_name: str = "main") -> Dict[str, Any]:
        crawler = self.get_crawler(forum_name)
        self._ensure_logged_in(crawler)
        return crawler.get_thread_content(thread_url)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _resolve_forum_name(self, requested: str) -> str:
        settings = self._settings
        if "forums" in settings:
            if requested in settings["forums"]:
                return requested
            if requested == "default" and "main" in settings["forums"]:
                return "main"
            # fallback to first defined forum
            return next(iter(settings["forums"].keys()))
        return "default"

    def _build_crawler(self, forum_name: str) -> AicutForumCrawler:
        config = self._get_forum_config(forum_name)
        credentials = config.get("credentials", {})
        defaults = self._settings.get("credentials", {})

        crawler = AicutForumCrawler(
            username=credentials.get("username") or defaults.get("username", ""),
            password=credentials.get("password") or defaults.get("password", ""),
            test_mode=config.get("test_mode", False),
            test_once=config.get("test_once", False),
            base_url=config.get("base_url", ""),
            forum_url=config.get("target_url", ""),
        )

        return crawler

    def _get_forum_config(self, forum_name: str) -> Dict[str, Any]:
        settings = self._settings
        if "forums" in settings and forum_name in settings["forums"]:
            return settings["forums"][forum_name]

        # backwards compatibility with old config format
        forum_cfg = settings.get("forum", {}).copy()
        forum_cfg.setdefault("credentials", settings.get("credentials", {}))
        return forum_cfg

    def _ensure_logged_in(self, crawler: AicutForumCrawler) -> None:
        if getattr(crawler, "logged_in", False):
            return
        crawler.login()


_CRAWLER_MANAGER_SINGLETON: Optional[ForumCrawlerManager] = None
_CRAWLER_MANAGER_LOCK = threading.Lock()


def get_forum_crawler_manager() -> ForumCrawlerManager:
    global _CRAWLER_MANAGER_SINGLETON
    if _CRAWLER_MANAGER_SINGLETON is None:
        with _CRAWLER_MANAGER_LOCK:
            if _CRAWLER_MANAGER_SINGLETON is None:
                _CRAWLER_MANAGER_SINGLETON = ForumCrawlerManager()
    return _CRAWLER_MANAGER_SINGLETON


__all__ = ["ForumCrawlerManager", "get_forum_crawler_manager"]

