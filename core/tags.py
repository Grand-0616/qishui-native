# -*- coding: utf-8 -*-
"""把元数据 / 封面 / 歌词写进音频文件（内嵌），并可选落同名旁挂文件。

支持容器：FLAC（Vorbis comment + METADATA_BLOCK_PICTURE）、M4A/MP4（ilst: ©nam/©ART/©alb/aART/©lyr/covr）、MP3（ID3v2.3）。
依赖 mutagen（纯 Python，可打包）。
"""
from __future__ import annotations

import base64
from pathlib import Path

try:
    import mutagen
    from mutagen.flac import FLAC, Picture
    from mutagen.id3 import APIC, TALB, TIT2, TPE1, TPE2, USLT, ID3
    from mutagen.mp4 import MP4, MP4Cover
    from mutagen.mp3 import MP3
    HAVE_MUTAGEN = True
except Exception:  # pragma: no cover
    HAVE_MUTAGEN = False


def _guess_mime(data: bytes) -> str:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def sniff_ext(data: bytes) -> str:
    mime = _guess_mime(data)
    return {"image/png": "png", "image/webp": "webp"}.get(mime, "jpg")


def _tag_flac(path: Path, meta: dict, lyric: str, cover: bytes | None) -> None:
    audio = FLAC(str(path))
    if meta.get("title"):
        audio["title"] = meta["title"]
    if meta.get("artists"):
        audio["artist"] = meta["artists"]
        audio["albumartist"] = meta.get("album_artist") or meta["artists"][0]
    if meta.get("album"):
        audio["album"] = meta["album"]
    if meta.get("date"):
        audio["date"] = meta["date"]
    if meta.get("track_id"):
        audio["qishui_track_id"] = meta["track_id"]
    if lyric:
        audio["lyrics"] = lyric
        audio["unsyncedlyrics"] = lyric
    audio.clear_pictures()
    if cover:
        pic = Picture()
        pic.type = 3  # front cover
        pic.mime = _guess_mime(cover)
        pic.desc = "Cover"
        pic.data = cover
        audio.add_picture(pic)
    audio.save()


def _tag_mp4(path: Path, meta: dict, lyric: str, cover: bytes | None) -> None:
    audio = MP4(str(path))
    if audio.tags is None:
        audio.add_tags()
    t = audio.tags
    if meta.get("title"):
        t["\xa9nam"] = [meta["title"]]
    if meta.get("artists"):
        t["\xa9ART"] = [meta["artists"]]
        t["aART"] = [meta.get("album_artist") or meta["artists"][0]]
    if meta.get("album"):
        t["\xa9alb"] = [meta["album"]]
    if meta.get("date"):
        t["\xa9day"] = [meta["date"]]
    if meta.get("track_id"):
        t["----:com.apple.iTunes:qishui_track_id"] = [meta["track_id"].encode("utf-8")]
    if lyric:
        t["\xa9lyr"] = [lyric]
    if cover:
        fmt = MP4Cover.FORMAT_PNG if _guess_mime(cover) == "image/png" else MP4Cover.FORMAT_JPEG
        t["covr"] = [MP4Cover(cover, imageformat=fmt)]
    audio.save()


def _tag_mp3(path: Path, meta: dict, lyric: str, cover: bytes | None) -> None:
    try:
        tags = ID3(str(path))
    except Exception:
        tags = ID3()
    if meta.get("title"):
        tags.setall("TIT2", [TIT2(encoding=3, text=[meta["title"]])])
    if meta.get("artists"):
        tags.setall("TPE1", [TPE1(encoding=3, text=[meta["artists"]])])
        tags.setall("TPE2", [TPE2(encoding=3, text=[meta.get("album_artist") or meta["artists"][0]])])
    if meta.get("album"):
        tags.setall("TALB", [TALB(encoding=3, text=[meta["album"]])])
    if lyric:
        tags.setall("USLT", [USLT(encoding=3, lang="chi", desc="", text=lyric)])
    if cover:
        tags.setall("APIC", [APIC(encoding=3, mime=_guess_mime(cover), type=3, desc="Cover", data=cover)])
    tags.save(str(path))


_WRITERS = {".flac": _tag_flac, ".m4a": _tag_mp4, ".mp3": _tag_mp3, ".mp4": _tag_mp4}


def write_tags(path: Path, meta: dict, lyric: str = "", cover: bytes | None = None) -> str | None:
    """写入内嵌标签；返回 None 表示成功，否则返回中文失败原因（不抛异常，导出不被标签拖垮）。"""
    if not HAVE_MUTAGEN:
        return "未安装 mutagen，跳过标签写入"
    writer = _WRITERS.get(path.suffix.lower())
    if not writer:
        return f"不支持的容器：{path.suffix}"
    try:
        writer(path, meta, lyric, cover)
        return None
    except Exception as e:
        return f"写标签失败：{type(e).__name__}: {e}"


def write_sidecar_lyric(audio_path: Path, lrc: str, *, enhanced: str | None = None) -> Path | None:
    """在音频旁写同名 .lrc（若已存在则不覆盖，尊重用户手改）。"""
    if not lrc:
        return None
    p = audio_path.with_suffix(".lrc")
    if p.exists():
        return None
    p.write_text(enhanced or lrc, encoding="utf-8")
    return p


def write_sidecar_cover(audio_path: Path, cover: bytes) -> Path | None:
    """在音频旁写 cover.jpg（目录封面，若同目录已有 cover.* 则跳过）。"""
    d = audio_path.parent
    for ext in ("png", "jpg", "jpeg", "webp"):
        if (d / f"cover.{ext}").exists():
            return None
    p = d / ("cover." + sniff_ext(cover))
    p.write_bytes(cover)
    return p
