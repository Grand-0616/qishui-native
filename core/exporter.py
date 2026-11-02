# -*- coding: utf-8 -*-
"""导出器（开源版）：只保留命名、索引、选档等通用工具，导出主流程为占位。

被移除的部分：加密音频流的获取与解密、容器转封装调度。
"""
from __future__ import annotations

# 是否具备「取音源 + 解密」的实现。公开版为 False，界面据此隐藏导出入口。
HAS_SOURCE = False

import json
import re
import shutil
import tempfile
import urllib.request
from pathlib import Path

from . import env, verify
from .library import Gear, Song, ext_for

_ILLEGAL = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def sanitize(name: str, limit: int = 120) -> str:
    name = _ILLEGAL.sub("_", name).strip(" .")
    if len(name) > limit:
        name = name[:limit].rstrip()
    return name or "unknown"


def build_filename(song: Song, gear: Gear) -> str:
    base = f"{sanitize(song.artist_text)} - {sanitize(song.name)}"
    q = gear.qname
    if q:
        base += f" [{q}]"
    return base


# ---------------------------------------------------------------- 已导出索引
def index_file() -> Path:
    return env.data_path("exported.json")


def load_index() -> dict:
    try:
        d = json.loads(index_file().read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save_index(d: dict) -> None:
    p = index_file()
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)


def index_key(track_id: str, quality: str) -> str:
    return f"{track_id}:{quality}"


def is_exported(track_id: str, quality: str) -> bool:
    rec = load_index().get(index_key(track_id, quality))
    if not rec:
        return False
    f = Path(rec.get("path", ""))
    return f.is_file()


def mark_exported(track_id: str, quality: str, path: Path, meta: dict) -> None:
    d = load_index()
    d[index_key(track_id, quality)] = {
        "path": str(path), "size": path.stat().st_size if path.is_file() else 0,
        "quality": quality, **meta,
    }
    save_index(d)


# ---------------------------------------------------------------- 导出
class ExportResult:
    def __init__(self, ok, path=None, reason="", quality=None, fmt=None, verify=None, scrape=None):
        self.ok = ok
        self.path = path
        self.reason = reason
        self.quality = quality
        self.fmt = fmt
        self.verify = verify or {}
        self.scrape = scrape

    def __repr__(self):
        return f"<ExportResult ok={self.ok} {self.path} {self.reason}>"


def _unique_path(directory: Path, stem: str, ext: str) -> Path:
    p = directory / f"{stem}.{ext}"
    if not p.exists():
        return p
    i = 1
    while True:
        p2 = directory / f"{stem} ({i}).{ext}"
        if not p2.exists():
            return p2
        i += 1


def pick_gear(song: Song, quality: str | None = None) -> Gear | None:
    """选档：优先指定 quality，否则最优可解密档（无则可解密档返回 None）。"""
    if quality:
        g = song.gear_by_quality(quality)
        if g and g.decryptable:
            return g
        if g:
            return g  # 返回它，由导出时报原因
    for g in song.gears:
        if g.decryptable:
            return g
    return song.best_gear


def _download(url: str, dst: Path, timeout: int = 60) -> str | None:
    """下载成功返回 None；失败返回中文错误原因（供上层拼提示）。
    区分 403：预签名 URL 有时效，过期会 403，需要客户端重新播放生成新链接。"""
    import urllib.error
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp, open(dst, "wb") as f:
            shutil.copyfileobj(resp, f)
        if dst.stat().st_size <= 0:
            return "下载内容为空"
        return None
    except urllib.error.HTTPError as e:
        if e.code in (403, 401, 410):
            return "音质链接已过期（请在汽水音乐重新播放该歌生成新链接后刷新）"
        return f"下载失败 HTTP {e.code}"
    except Exception as e:
        return f"下载异常：{type(e).__name__}"


def _remux_to_flac(src: Path, dst: Path) -> bool:
    """把「MP4壳+fLaC codec」无损转封装成真裸 FLAC（-c:a copy，不重编码）。
    成功返回 True；无 ffmpeg 或失败返回 False（调用方保留原文件兜底）。"""
    ff = env.find_ffmpeg("ffmpeg.exe")
    if not ff:
        return False
    from . import proc
    try:
        p = proc.run(
            [str(ff), "-y", "-v", "error", "-i", str(src), "-c:a", "copy", str(dst)],
            capture_output=True, timeout=120)
    except Exception:
        return False
    if p.returncode != 0 or not dst.is_file() or dst.stat().st_size == 0:
        try:
            dst.unlink(missing_ok=True)
        except OSError:
            pass
        return False
    return True



def export_song(song: Song, *, quality: str | None = None,
                out_dir: Path | None = None, allow_download: bool = True,
                scrape: bool = True, scrape_sidecar: bool = True,
                scrape_meta=None, **_ignored) -> ExportResult:
    """导出单曲到标准音频文件（开源版占位）。

    真实实现涉及：定位音源、解密加密音频流、封装容器、写标签/封面。
    这部分不在本仓库内，见 docs/SECURITY.md「被移除的模块」。
    """
    return ExportResult(False, reason="开源版不含音源获取与解密实现，仅保留界面与工具层")


def refresh_and_export(song: Song, *, quality: str | None = None,
                       out_dir: Path | None = None,
                       scrape: bool = True, scrape_sidecar: bool = True) -> ExportResult:
    """刷新音源链接后导出（开源版占位）。"""
    return ExportResult(False, reason="开源版不含音源获取与解密实现，仅保留界面与工具层")


def export_raw(src: Path, key_hex: str, out_dir: Path, stem: str) -> ExportResult:
    """把一个已解密的裸音频落盘（开源版占位）。"""
    return ExportResult(False, reason="开源版不含解密实现")
