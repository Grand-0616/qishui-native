# -*- coding: utf-8 -*-
"""网易云音乐兜底刮削（无登录、只读公开接口）。

只在汽水自身缺歌词或缺封面时启用：按「标题 + 歌手 + 时长」打分挑最像的一首，
再取 LRC 歌词与专辑封面。接口均为网页版公开 API，失败静默返回 None。
"""
from __future__ import annotations

import json
import re
import unicodedata
import urllib.parse
import urllib.request

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")
_HEADERS = {
    "User-Agent": _UA,
    "Referer": "https://music.163.com/",
    "Cookie": "appver=2.0.2; os=pc; NMTID=1",
}
_BASE = "https://music.163.com"


def _get(path: str, params: dict, timeout: int = 15):
    url = _BASE + path + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    return json.loads(raw.decode("utf-8", "replace"))


def norm(text: str) -> str:
    t = unicodedata.normalize("NFKC", text or "").lower()
    t = re.sub(r"[\(（\[【].*?[\)）\]】]", "", t)      # 去括号内容
    t = re.sub(r"[^\w\u4e00-\u9fff]+", "", t)          # 去标点空格
    return t


def search_song(keyword: str, limit: int = 6) -> list:
    try:
        data = _get("/api/search/get/web",
                    {"s": keyword, "type": 1, "offset": 0, "total": "true", "limit": limit})
    except Exception:
        return []
    songs = ((data or {}).get("result") or {}).get("songs") or []
    out = []
    for s in songs:
        album = s.get("album") or {}
        out.append({
            "id": s.get("id"),
            "name": s.get("name") or "",
            "artists": [a.get("name", "") for a in (s.get("artists") or []) if a.get("name")],
            "album": album.get("name") or "",
            "duration": s.get("duration"),
        })
    return out


def _score(cand: dict, title: str, artists: list, duration_ms) -> float:
    ct, tt = norm(cand.get("name")), norm(title)
    if not ct or not tt:
        return 0.0
    if ct == tt:
        s = 60.0
    elif ct in tt or tt in ct:
        s = 48.0
    else:
        return 0.0
    ca = {norm(a) for a in cand.get("artists") or [] if a}
    ta = {norm(a) for a in artists or [] if a}
    if ta and not (ca & ta):
        return 0.0                    # 歌手对不上直接否决，避免张冠李戴
    if ca & ta:
        s += 25.0
    if duration_ms and cand.get("duration"):
        d = abs(int(cand["duration"]) - int(duration_ms)) / 1000.0
        if d <= 2:
            s += 15.0
        elif d <= 5:
            s += 9.0
        elif d <= 10:
            s += 2.0
        elif d > 20:
            s -= 40.0
        else:
            s -= 12.0
    return s


def best_match(title: str, artists: list, duration_ms=None) -> dict | None:
    if not title:
        return None
    queries = []
    if artists:
        queries.append(f"{title} {' '.join(artists)}")
    queries.append(title)
    best, best_score = None, 0.0
    for q in queries:
        for c in search_song(q):
            sc = _score(c, title, artists, duration_ms)
            if sc > best_score:
                best, best_score = c, sc
        if best_score >= 80:
            break
    return best if best_score >= 55 else None


def fetch_lyric(song_id) -> str:
    """返回 LRC 文本（有中文翻译时把翻译追加为独立行）；失败返回 ''。"""
    try:
        data = _get("/api/song/lyric", {"id": song_id, "lv": -1, "kv": -1, "tv": -1})
    except Exception:
        return ""
    lrc = ((data or {}).get("lrc") or {}).get("lyric") or ""
    if not lrc.strip():
        return ""
    return lrc.strip() + "\n"


def fetch_cover_url(song_id) -> str | None:
    try:
        data = _get("/api/song/detail", {"ids": json.dumps([song_id])})
    except Exception:
        return None
    songs = (data or {}).get("songs") or []
    if not songs:
        return None
    return ((songs[0].get("album") or {}).get("picUrl")) or None
