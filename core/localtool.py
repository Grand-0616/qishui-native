# -*- coding: utf-8 -*-
"""本地音乐整理：把同目录的歌词 / 封面写进音频文件（纯本地，不联网）。

常见场景：
    某人把歌拷出来，旁边放着 `歌名.lrc` 和 `cover.jpg`，
    但播放器不认旁挂文件。这里一次性把它们塞进文件本身的标签里。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import krc, scraper, tags

AUDIO_EXT = (".mp3", ".flac", ".m4a", ".aac", ".wav", ".ogg", ".opus")
LYRIC_EXT = (".lrc", ".txt", ".krc")
COVER_STEMS = ("cover", "folder", "front", "album", "artwork")
COVER_EXT = (".jpg", ".jpeg", ".png", ".webp")


@dataclass
class Item:
    audio: Path
    lyric: Path | None = None
    cover: Path | None = None

    @property
    def status(self) -> str:
        return ("歌词✓" if self.lyric else "歌词✗") + " · " + ("封面✓" if self.cover else "封面✗")


def scan_audio(directory) -> list[Path]:
    try:
        return sorted(p for p in Path(directory).iterdir()
                      if p.is_file() and p.suffix.lower() in AUDIO_EXT
                      and not p.name.startswith("."))
    except OSError:
        return []


def find_lyric(audio: Path) -> Path | None:
    # 1) track.flac → track.lrc / track.krc
    for e in LYRIC_EXT:
        p = audio.with_suffix(e)
        if p.is_file():
            return p
    # 2) track.flac → track.flac.lrc
    for e in LYRIC_EXT:
        p = audio.parent / (audio.name + e)
        if p.is_file():
            return p
    # 3) 目录里只有一首歌时，允许唯一的歌词文件
    if len(scan_audio(audio.parent)) == 1:
        lyr = [p for p in audio.parent.iterdir()
               if p.is_file() and p.suffix.lower() in LYRIC_EXT]
        if len(lyr) == 1:
            return lyr[0]
    return None


def find_cover(audio: Path) -> Path | None:
    for e in COVER_EXT:
        p = audio.with_suffix(e)
        if p.is_file():
            return p
    for stem in COVER_STEMS:
        for e in COVER_EXT:
            p = audio.parent / (stem + e)
            if p.is_file():
                return p
    return None


def scan(directory) -> list[Item]:
    return [Item(a, find_lyric(a), find_cover(a)) for a in scan_audio(directory)]


def read_lyric(path: Path) -> tuple[str, str, int]:
    """返回 (标准 LRC, 增强 LRC, 行数)；.krc 自动转 LRC。"""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "", "", 0
    if path.suffix.lower() == ".krc":
        body = text
        if body.lstrip().lower().startswith("krc1"):
            body = body.split("\n", 1)[1] if "\n" in body else ""
        try:
            lines, tagmap = krc.parse_krc(body)
        except Exception:
            return "", "", 0
        if not lines:
            return "", "", 0
        return krc.to_lrc(lines, tagmap), krc.to_enhanced_lrc(lines), len(lines)
    n = sum(1 for ln in text.splitlines() if ln.strip().startswith("["))
    return text, text, n


def _merge_existing(audio: Path, md: dict) -> dict:
    """文件里已有的标签优先，避免把正确信息覆盖成文件名。"""
    try:
        from mutagen import File as _MF
        f = _MF(str(audio))
        if f is None:
            return md

        def first(key: str) -> str:
            v = f.get(key)
            if not v:
                return ""
            if isinstance(v, list):
                return str(v[0]) if v else ""
            return str(v)

        for key in ("title", "album"):
            v = first(key)
            if v:
                md[key] = v
        art = first("artist") or first("albumartist")
        if art:
            md["artists"] = art
        date = first("date")
        if date:
            md["date"] = date
    except Exception:
        pass
    return md


def apply(item: Item, *, embed: bool = True, sidecar: bool = False,
          overwrite: bool = False) -> tuple[bool, str]:
    """整理一首：返回 (成功, 说明)。"""
    audio = item.audio
    if not audio.is_file():
        return False, "文件不存在"
    if not item.lyric and not item.cover:
        return False, "没有找到同名歌词或封面"

    meta = scraper.guess_meta_from_filename(audio)
    md = (meta.tag_dict() if meta else
          {"title": audio.stem, "artists": "", "album": "", "date": "", "track_id": ""})
    md = _merge_existing(audio, md)

    lrc = enh = ""
    nlines = 0
    if item.lyric:
        lrc, enh, nlines = read_lyric(item.lyric)

    cover_bytes = None
    if item.cover:
        try:
            cover_bytes = scraper._optimize_image(item.cover.read_bytes())
        except Exception:
            cover_bytes = None

    if embed:
        err = tags.write_tags(audio, md, lyric=enh or lrc, cover=cover_bytes)
        if err:
            return False, err
    if sidecar:
        if lrc:
            tags.write_sidecar_lyric(audio, lrc, enhanced=enh or None)
        if cover_bytes:
            tags.write_sidecar_cover(audio, cover_bytes)

    done = []
    if lrc:
        done.append(f"歌词{nlines}行")
    if cover_bytes:
        done.append("封面")
    return True, "、".join(done) or "完成"
