# -*- coding: utf-8 -*-
"""刮削器：给已导出的音频文件补「海报 + 内置歌词 + 标签」。

为什么能做到：汽水的 track_v2 接口（本项目已用于刷新音源）同一次响应里就带
  - track.album.url_cover  → 封面（拼 URL 规则见 refresher.cover_url）
  - lyric.content / type   → KRC 逐字歌词（type='krc'），部分歌为 'lrc'
所以刮削不需要任何第三方站点，零额外请求：导出时本来就要打这个接口。

用法：
    res = scrape.attach(final_path, track_id)          # 内嵌 + 旁挂
    res = scrape.attach(final_path, track_id, embed=False)  # 只写 .lrc/cover.jpg
"""
from __future__ import annotations

import hashlib
import io
import re
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from . import env, krc, netease, refresher, tags

_UA = "Mozilla/5.0"
_LAST_REASON = ""


@dataclass
class ScrapeMeta:
    track_id: str
    title: str = ""
    artists: list = field(default_factory=list)
    album: str = ""
    date: str = ""
    cover_url: str | None = None
    duration: int | None = None
    lyric_type: str = ""
    lyric_raw: str = ""
    lyric_hidden: bool = False

    def tag_dict(self) -> dict:
        return {
            "title": self.title,
            "artists": "、".join(self.artists) if self.artists else "",
            "album": self.album,
            "date": self.date,
            "track_id": self.track_id,
        }


@dataclass
class ScrapeResult:
    ok: bool = False
    reason: str = ""
    got_cover: bool = False
    got_lyric: bool = False
    lyric_lines: int = 0
    lrc_path: Path | None = None
    cover_path: Path | None = None

    def __repr__(self):
        return (f"<Scrape ok={self.ok} cover={self.got_cover} lyric={self.got_lyric}"
                f"/{self.lyric_lines} {self.reason}>")


# ---------------------------------------------------------------- 封面
def _cover_cache_dir() -> Path:
    p = env.data_path("covers")
    p.mkdir(parents=True, exist_ok=True)
    return p


def _optimize_image(data: bytes, max_side: int = 1200, quality: int = 85) -> bytes:
    """缩到 max_side 内并转 JPEG（体积可控）。Pillow 缺失时原样返回。"""
    try:
        from PIL import Image
    except Exception:
        return data
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
        if im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
        w, h = im.size
        if max(w, h) > max_side:
            scale = max_side / float(max(w, h))
            im = im.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=quality, optimize=True)
        out = buf.getvalue()
        return out if len(out) < len(data) else data
    except Exception:
        return data


def fetch_cover(url: str, *, timeout: int = 20) -> bytes | None:
    if not url:
        return None
    key = hashlib.sha1(url.encode("utf-8")).hexdigest()
    cache = _cover_cache_dir() / f"{key}.jpg"
    if cache.is_file() and cache.stat().st_size > 0:
        return cache.read_bytes()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except Exception:
        return None
    if not raw:
        return None
    data = _optimize_image(raw)
    try:
        cache.write_bytes(data)
    except OSError:
        pass
    return data


# ---------------------------------------------------------------- 主流程
def fetch_meta(track_id: str) -> ScrapeMeta | None:
    """向在线接口取元数据。开源版没有该接口，返回 None（随后走文件名猜测 + 第三方兜底）。"""
    global _LAST_REASON
    try:
        full = refresher.fetch_full(track_id)
    except NotImplementedError:
        _LAST_REASON = "本版本不含在线元数据接口"
        return None
    except Exception as e:
        _LAST_REASON = f"{type(e).__name__}: {e}"
        return None
    if not full:
        _LAST_REASON = "接口无响应"
        return None
    return meta_from_full(full)


def meta_from_full(full: dict) -> ScrapeMeta:
    """把 refresher.fetch_full 的响应转成 ScrapeMeta（供刷新导出复用同一次响应）。"""
    ly = full.get("lyric") or {}
    return ScrapeMeta(
        track_id=str(full.get("track_id") or ""),
        title=full.get("name") or "",
        artists=list(full.get("artists") or []),
        album=full.get("album") or "",
        date=_date_text(full.get("release_date")),
        cover_url=full.get("cover_url"),
        duration=full.get("duration"),
        lyric_type=(ly.get("type") or ""),
        lyric_raw=(ly.get("content") or ""),
        lyric_hidden=bool(ly.get("hide_request_lyrics")),
    )


def _date_text(ts) -> str:
    try:
        import datetime
        n = int(ts)
        if n > 0:
            return datetime.date.fromtimestamp(n).isoformat()
    except Exception:
        pass
    return ""


_AUDIO_EXT = {".mp3", ".flac", ".m4a", ".aac", ".wav", ".ogg", ".opus"}
_TAIL_RE = re.compile(r"\s*[\[\(\u3010][^\]\)\u3011]*[\]\)\u3011]\s*$")


def read_duration_ms(audio_path) -> int | None:
    """读音频时长（毫秒），读不到返回 None。"""
    try:
        from mutagen import File as _MF
        mf = _MF(str(audio_path))
        info = getattr(mf, "info", None)
        length = getattr(info, "length", None) if info is not None else None
        if length:
            return int(float(length) * 1000)
    except Exception:
        pass
    return None


def guess_meta_from_filename(audio_path) -> ScrapeMeta | None:
    """没有在线接口时，从文件名猜「歌手 - 歌名」（导出工具常见命名）。"""
    p = Path(audio_path)
    stem = p.stem
    for _ in range(3):
        stripped = _TAIL_RE.sub("", stem)
        if stripped == stem:
            break
        stem = stripped
    stem = stem.replace("_", " ").strip()
    if not stem:
        return None
    artists: list[str] = []
    title = stem
    for sep in (" - ", " \u2013 ", " \u2014 ", "-"):
        if sep in stem:
            left, right = stem.split(sep, 1)
            if left.strip() and right.strip():
                artists = [x.strip() for x in re.split(r"[&\u3001,\uff0c]", left) if x.strip()]
                title = right.strip()
            break
    return ScrapeMeta(track_id="", title=title, artists=artists,
                      duration=read_duration_ms(p))


def build_lyric(meta: ScrapeMeta) -> tuple[str, str, int]:
    """→ (标准LRC, 增强LRC, 行数)。无歌词返回 ("","",0)。"""
    raw = (meta.lyric_raw or "").replace("\x00", "")
    if not raw.strip():
        return "", "", 0
    if (meta.lyric_type or "").lower() == "krc" or "<" in raw:
        lines, head = krc.parse_krc(raw)
        head.setdefault("ti", meta.title)
        head.setdefault("ar", "、".join(meta.artists))
        head.setdefault("al", meta.album)
        if not lines:
            return "", "", 0
        return krc.to_lrc(lines, head), krc.to_enhanced_lrc(lines, head), len(lines)
    # 已是 LRC 文本（type='lrc'）
    text = raw.strip() + "\n"
    return text, text, sum(1 for ln in raw.splitlines() if ln.strip().startswith("["))


def attach(audio_path: Path, track_id: str = "", *, embed: bool = True, sidecar: bool = True,
           overwrite_sidecar: bool = False, fallback: bool = True, guess: bool = True,
           meta: "ScrapeMeta | None" = None, timeout: int = 20) -> ScrapeResult:
    """给一个已落盘的音频文件刮削：内嵌标签/封面/歌词 + 可选旁挂 .lrc / cover.jpg。"""
    res = ScrapeResult()
    audio_path = Path(audio_path)
    if not audio_path.is_file():
        res.reason = "文件不存在"
        return res
    if meta is None and track_id:
        meta = fetch_meta(track_id)
    if meta is None and guess:
        meta = guess_meta_from_filename(audio_path)
    if meta is None:
        res.reason = f"取元数据失败：{_LAST_REASON or '无法识别文件名'}"
        return res

    lrc, enhanced, nlines = build_lyric(meta)
    cover = fetch_cover(meta.cover_url, timeout=timeout) if meta.cover_url else None

    # 兜底：汽水缺歌词或缺封面时，按标题+歌手+时长到网易云找最像的一首补齐
    if fallback and (not lrc or not cover):
        try:
            cand = netease.best_match(meta.title, meta.artists, meta.duration)
        except Exception:
            cand = None
        if cand:
            if not lrc:
                nl = netease.fetch_lyric(cand["id"])
                if nl.strip():
                    lrc, enhanced = nl, nl
                    nlines = sum(1 for ln in nl.splitlines() if ln.strip().startswith("["))
                    res.reason = ""
            if not cover:
                cu = netease.fetch_cover_url(cand["id"])
                if cu:
                    cover = fetch_cover(cu, timeout=timeout)

    if embed:
        err = tags.write_tags(audio_path, meta.tag_dict(), lyric=enhanced or lrc, cover=cover)
        if err:
            res.reason = err
    res.got_cover = bool(cover)
    res.got_lyric = bool(lrc)
    res.lyric_lines = nlines

    if sidecar:
        if lrc:
            p = audio_path.with_suffix(".lrc")
            if overwrite_sidecar or not p.exists():
                p.write_text(lrc, encoding="utf-8")
                res.lrc_path = p
        if cover:
            d = audio_path.parent
            if overwrite_sidecar or not any((d / f"cover.{e}").exists() for e in ("png", "jpg", "jpeg", "webp")):
                p = d / ("cover." + tags.sniff_ext(cover))
                p.write_bytes(cover)
                res.cover_path = p

    res.ok = bool(res.got_cover or res.got_lyric) and not res.reason
    if not res.ok and not res.reason:
        res.reason = "该曲无封面也无歌词"
    return res
