# -*- coding: utf-8 -*-
"""KRC 歌词解析与 LRC 转换。

汽水 PC 端 `lyric.content` 是 KRC 文本（逐字时间轴），形如：
    [19962,2279]<0,378,0>笔<378,377,0>锋<760,395,0>纸...
即 [行开始ms,行时长ms] 后跟若干 <字相对偏移ms,字时长ms,0>字。

输出两种：
  - 标准 LRC（[mm:ss.xx]整行文本）——兼容一切播放器/车机
  - 增强 LRC（行内 <mm:ss.xx> 逐字）——支持逐字的播放器自动识别
"""
from __future__ import annotations

import re

_LINE_RE = re.compile(r"^\[(\d+),(\d+)\](.*)$")
_WORD_RE = re.compile(r"<(\d+),(\d+),\d+>([^<]*)")
_TAG_RE = re.compile(r"^\[(ti|ar|al|by|offset|kana|language):(.*)\]$", re.I)


def _fmt(ms: int) -> str:
    if ms < 0:
        ms = 0
    m, rem = divmod(ms, 60000)
    s, milli = divmod(rem, 1000)
    return f"{m:02d}:{s:02d}.{milli // 10:02d}"


class Line:
    __slots__ = ("start", "duration", "text", "words", "translation")

    def __init__(self, start, duration, text, words):
        self.start = start
        self.duration = duration
        self.text = text
        self.words = words  # [(abs_ms, dur_ms, text)]
        self.translation = ""

    @property
    def end(self) -> int:
        return self.start + (self.duration or 0)


def parse_krc(content: str) -> tuple[list[Line], dict]:
    """解析 KRC 文本 → (行列表, 头部标签)。无法识别的行原样作为纯文本行保留。"""
    tags: dict = {}
    lines: list[Line] = []
    for raw in (content or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        s = raw.strip()
        if not s:
            continue
        m = _TAG_RE.match(s)
        if m:
            tags[m.group(1).lower()] = m.group(2).strip()
            continue
        m = _LINE_RE.match(s)
        if not m:
            continue
        start, dur = int(m.group(1)), int(m.group(2))
        body = m.group(3)
        words = []
        if "<" in body:
            for w in _WORD_RE.finditer(body):
                off, wdur, txt = int(w.group(1)), int(w.group(2)), w.group(3)
                words.append((start + off, wdur, txt))
            text = "".join(w[2] for w in words)
        else:
            # 少数行没有逐字信息，只有纯文本
            text = body.strip()
            words = []
        lines.append(Line(start, dur, text, words))
    lines.sort(key=lambda x: x.start)
    return lines, tags


def to_lrc(lines: list[Line], tags: dict | None = None, *, offset_ms: int = 0) -> str:
    """标准 LRC：每行一个时间戳 + 整行文本（含翻译行）。"""
    tags = tags or {}
    out = []
    for key, name in (("ti", "ti"), ("ar", "ar"), ("al", "al"), ("by", "by")):
        if tags.get(key):
            out.append(f"[{name}:{tags[key]}]")
    if not tags.get("by"):
        out.append("[by:qishui-native]")
    for ln in lines:
        out.append(f"[{_fmt(ln.start + offset_ms)}]{ln.text}")
        if ln.translation:
            out.append(f"[{_fmt(ln.start + offset_ms)}]{ln.translation}")
    return "\n".join(out) + "\n"


def to_enhanced_lrc(lines: list[Line], tags: dict | None = None, *, offset_ms: int = 0) -> str:
    """增强 LRC：行首时间戳 + 行内 <mm:ss.xx> 逐字标记（无逐字信息时退回整行）。"""
    tags = tags or {}
    out = []
    for key, name in (("ti", "ti"), ("ar", "ar"), ("al", "al"), ("by", "by")):
        if tags.get(key):
            out.append(f"[{name}:{tags[key]}]")
    out.append("[by:qishui-native]")
    for ln in lines:
        head = f"[{_fmt(ln.start + offset_ms)}]"
        if ln.words:
            body = "".join(f"<{_fmt(w[0] + offset_ms)}>{w[2]}" for w in ln.words if w[2])
        else:
            body = ln.text
        out.append(head + body)
        if ln.translation:
            out.append(f"[{_fmt(ln.start + offset_ms)}]{ln.translation}")
    return "\n".join(out) + "\n"


def plain_text(lines: list[Line]) -> str:
    return "\n".join(ln.text for ln in lines if ln.text)


def apply_translation(lines: list[Line], translation: str) -> None:
    """把翻译轨按起始时间对齐到主轨（兼容 KRC 与标准 LRC 两种写法）。"""
    if not translation:
        return
    tr_lines, _ = parse_krc(translation)
    by_time = {ln.start: ln.text for ln in tr_lines}
    if not by_time:
        by_time = _parse_lrc_times(translation)
    if not by_time:
        return
    times = sorted(by_time)
    for ln in lines:
        t = by_time.get(ln.start)
        if not t:
            # 容差匹配：KRC 取整与 LRC 时间轴常有 10~100ms 偏差
            near = [x for x in times if abs(x - ln.start) <= 150]
            if near:
                t = by_time[min(near, key=lambda x: abs(x - ln.start))]
        if t:
            ln.translation = t


_LRC_TAG_RE = __import__("re").compile(r"\[(\d{1,3}):(\d{1,2})(?:[.:](\d{1,3}))?\]")


def _parse_lrc_times(text: str) -> dict:
    """标准 LRC 文本 -> {起始毫秒: 文本}。"""
    out = {}
    for raw in (text or "").splitlines():
        ms = _LRC_TAG_RE.match(raw.strip())
        if not ms:
            continue
        mm, ss = int(ms.group(1)), int(ms.group(2))
        frac = ms.group(3) or "0"
        if len(frac) == 1:
            frac_ms = int(frac) * 100
        elif len(frac) == 2:
            frac_ms = int(frac) * 10
        else:
            frac_ms = int(frac[:3])
        start = mm * 60000 + ss * 1000 + frac_ms
        body = raw.strip()[ms.end():].strip()
        if body:
            out[start] = body
    return out
