# -*- coding: utf-8 -*-
"""在线音源刷新（开源版：接口占位，未包含实现）。

真实实现会向服务端请求曲目详情，拿到音源地址与加密参数，并包含请求签名逻辑。
签名算法与接口细节不在本仓库提供。
"""
from pathlib import Path

from . import env


def _cookie_cache_file() -> Path:
    """凭证缓存文件位置（仅路径，不含任何凭证内容）。"""
    return env.data_path("credential.cache")


def cache_cookie_from_db() -> bool:
    """从本机客户端读取登录凭证（开源版未实现，永远返回 False）。"""
    return False


def fetch_full(track_id: str) -> dict:
    raise NotImplementedError("开源版未包含该实现，见 docs/SECURITY.md")


def fetch_fresh(track_id: str) -> list:
    raise NotImplementedError("开源版未包含该实现，见 docs/SECURITY.md")


def cover_url(track: dict) -> str | None:
    raise NotImplementedError("开源版未包含该实现，见 docs/SECURITY.md")


def last_error() -> str:
    """最近一次失败原因（开源版不发请求，恒为空串）。"""
    return ""
