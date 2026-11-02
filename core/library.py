# -*- coding: utf-8 -*-
"""数据模型与检索：曲目、档位、模糊搜索。

本文件只做「数据结构 + 字符串匹配」，不含任何与音乐客户端缓存/密钥相关的实现。
Library.refresh() 在开源版里读取用户自备的 data/library.json（结构见 docs/library.example.json），
读不到就返回空库，UI 会显示空态提示。
"""
from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from dataclasses import dataclass, field
from pathlib import Path

from . import env


QUALITY_RANK = {
    "hi_res": 60, "spatial": 50, "lossless": 40,
    "highest": 30, "higher": 20, "medium": 10,
}
QUALITY_NAME = {
    "lossless": "无损音质",
    "hi_res": "录音室音质",
    "spatial": "全景声",
    "highest": "极高音质",
    "higher": "较高音质",
    "medium": "标准音质",
}
FORMAT_EXT = {"fLaC": "flac", "mp4a": "m4a", "alac": "m4a", "ec-3": "m4a", "ac-3": "m4a"}


# ---------------------------------------------------------------- 模糊匹配
_PUNC_RE = re.compile(
    r"[\s\-_/\\·・,，.。!！?？'\"“”‘’()（）\[\]【】<>《》~～|:：;；&+*#@$%^=`]+"
)
_BRACKET_RE = re.compile(r"[（(\[【][^）)\]】]*[）)\]】]")


def _norm(s: str) -> str:
    """归一化：NFKC（全角→半角）+ 小写 + 去标点空白。"""
    s = unicodedata.normalize("NFKC", s or "").lower()
    return _PUNC_RE.sub("", s)


def _strip_brackets(s: str) -> str:
    """去掉括号里的副标题：`上岸（巴扎黑）` → `上岸`。"""
    return _BRACKET_RE.sub("", s or "")


def _query_tokens(text: str) -> list[str]:
    """查询串分词：先按空白/逗号切，再各自归一化，丢掉空 token。"""
    parts = [p for p in re.split(r"[\s,，]+", (text or "").strip()) if p.strip()]
    return [n for n in (_norm(p) for p in parts) if n]


def _subseq_score(q: str, t: str) -> float:
    """q 是否为 t 的子序列；是则按「紧凑度 + 覆盖密度」给 0.5~1.0。"""
    if not q or not t:
        return 0.0
    pos = []
    j = 0
    for i, ch in enumerate(t):
        if j < len(q) and ch == q[j]:
            pos.append(i)
            j += 1
    if j < len(q):
        return 0.0
    span = pos[-1] - pos[0] + 1
    compact = len(q) / span
    density = len(q) / max(len(t), 1)
    return 0.5 + 0.32 * compact + 0.18 * min(1.0, density * 3)


def _token_score(t: str, field: str) -> float:
    """单个 token 对单个字段的匹配分：完全相同 > 前缀 > 子串 > 子序列。"""
    if not t or not field:
        return 0.0
    if t == field:
        return 1.0
    if field.startswith(t):
        return 0.95
    idx = field.find(t)
    if idx >= 0:
        return 0.90 - 0.10 * (idx / max(len(field), 1))
    return _subseq_score(t, field)


def _best_of(t: str, fields: list[tuple[str, float]]) -> float:
    """在若干 (字段值, 权重) 里取最高分。"""
    best = 0.0
    for val, w in fields:
        if val:
            sc = _token_score(t, val) * w
            if sc > best:
                best = sc
    return best


# ---- 拼音支持（可选依赖 pypinyin；缺失时自动降级为纯文本匹配）----
try:
    from pypinyin import lazy_pinyin, Style
    _HAS_PINYIN = True
except Exception:  # pragma: no cover
    _HAS_PINYIN = False


@lru_cache(maxsize=16384)
def _pinyin_fields(text: str) -> tuple[str, str]:
    """返回 (全拼, 首字母)，如 上岸 → ("shangan","sa")。"""
    if not _HAS_PINYIN or not text:
        return ("", "")
    try:
        full = "".join(lazy_pinyin(text, errors="ignore")).lower()
        ini = "".join(lazy_pinyin(text, style=Style.FIRST_LETTER, errors="ignore")).lower()
        return (_norm(full), _norm(ini))
    except Exception:
        return ("", "")


_TOKEN_MIN = 0.5   # token 低于该分视为没匹配上（多关键词 AND 语义）


def _score_song(tokens: list[str], s) -> float:
    """多 token AND：每个 token 都要命中，取各 token 均分。

    字段权重：主标题 1.0 > 全名（含副标题）0.93 > 歌手 0.95 > 专辑 0.88；
    拼音：主标题全拼 0.95 / 首字母 0.92，全名拼音 0.85 / 0.83。
    """
    name = _norm(s.name)
    name_main = _norm(_strip_brackets(s.name))
    artist = _norm(s.artist_text)
    album = _norm(s.album or "")

    name_fields = [(name_main, 1.0), (name, 0.93)]
    artist_fields = [(artist, 0.95)]
    album_fields = [(album, 0.88)]
    if _HAS_PINYIN:
        pf_main, pi_main = _pinyin_fields(_strip_brackets(s.name))
        pf_all, pi_all = _pinyin_fields(s.name)
        name_fields += [(pf_main, 0.95), (pi_main, 0.92), (pf_all, 0.85), (pi_all, 0.83)]
        apf, api = _pinyin_fields(s.artist_text)
        artist_fields += [(apf, 0.82), (api, 0.80)]

    total = 0.0
    for t in tokens:
        best = max(_best_of(t, name_fields),
                   _best_of(t, artist_fields),
                   _best_of(t, album_fields))
        if best < _TOKEN_MIN:
            return 0.0
        total += best
    return total / len(tokens)


def _safe_size(path) -> int | None:
    try:
        return Path(path).stat().st_size
    except OSError:
        return None


@dataclass
class Gear:
    """某首歌的某个可用档位。"""
    quality: str            # medium/higher/highest/lossless/spatial/hi_res
    bitrate: int | None
    path: Path | None       # 本地 .bin 文件（已缓存时）
    size: int | None
    fmt: str | None         # 解密后格式 fLaC/mp4a
    key_hex: str | None     # 解出的 ASE key
    url: str | None = None  # 无本地缓存时的下载 URL

    @property
    def rank(self) -> int:
        return QUALITY_RANK.get(self.quality, 0)

    @property
    def qname(self) -> str:
        return QUALITY_NAME.get(self.quality, self.quality)

    @property
    def available(self) -> bool:
        return bool(self.path and self.path.is_file())

    @property
    def decryptable(self) -> bool:
        return bool(self.available and self.key_hex and self.fmt)

    @property
    def downloadable(self) -> bool:
        """有下载 URL 且能解出密钥 —— 可在线下载后解密导出（无需本地缓存）。"""
        return bool(self.url and self.key_hex)


@dataclass
class Song:
    track_id: str
    name: str
    artists: list = field(default_factory=list)
    album: str | None = None
    duration: int | None = None
    gears: list = field(default_factory=list)  # list[Gear]，已按 rank 降序

    @property
    def artist_text(self) -> str:
        return "、".join(self.artists) if self.artists else "未知歌手"

    @property
    def best_gear(self) -> Gear | None:
        for g in self.gears:
            if g.decryptable:
                return g
        return self.gears[0] if self.gears else None

    @property
    def top_bitrate_gear(self) -> Gear | None:
        """可用档位里「码率最高」的一个（用于列表标签显示最高音质）。

        优先在「可导出（本地可解 or 可下载解密）」的档里取 bitrate 最高；
        若都不可导出，则退而取全部档里 bitrate 最高的。"""
        usable = [g for g in self.gears if (g.decryptable or g.downloadable)]
        pool = usable or self.gears
        if not pool:
            return None
        return max(pool, key=lambda g: (g.bitrate or 0))

    def gear_by_quality(self, q: str) -> Gear | None:
        for g in self.gears:
            if g.quality == q:
                return g
        return None



class Library:
    """曲库快照：UI 只读它，刷新时整份替换。

    - 开源版数据来源：``data/library.json``（可选，自己放一个就有演示数据）
    - 未包含：读客户端缓存数据库、解析加密资源、解出档位密钥
    """

    def __init__(self):
        self.songs: dict[str, Song] = {}
        self.error: str | None = None
        self.cache_missing: bool = False

    def refresh(self, *, decode: bool = True) -> "Library":
        self.songs = {}
        self.error = None
        self.cache_missing = False
        path = env.data_path("library.json")
        if not path.is_file():
            self.cache_missing = True
            self.error = ("开源版不含本地缓存解析实现。放一个 data/library.json "
                          "（结构见 docs/library.example.json）即可看到演示数据。")
            return self
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            for item in raw.get("songs", []):
                gears = []
                for g in item.get("gears", []):
                    gears.append(Gear(
                        quality=g.get("quality", "medium"),
                        bitrate=g.get("bitrate"),
                        path=None,
                        size=g.get("size"),
                        fmt=g.get("fmt"),
                        key_hex=None,
                        url=None,
                    ))
                gears.sort(key=lambda g: g.rank, reverse=True)
                song = Song(
                    track_id=str(item.get("track_id", "")),
                    name=item.get("name", "未命名"),
                    artists=list(item.get("artists") or []),
                    album=item.get("album"),
                    duration=item.get("duration"),
                    gears=gears,
                )
                self.songs[song.track_id] = song
        except Exception as e:
            self.error = f"读取 data/library.json 失败：{e}"
        return self

    # ---- 查询 ----
    @staticmethod
    def _song_exportable(s) -> bool:
        return any(g.decryptable or g.downloadable for g in s.gears)

    def search(self, text: str, *, only_exportable: bool = False) -> list:
        """模糊搜索：空格分词 + 子串/前缀/子序列/字符覆盖，按相关度降序。"""
        return [s for _, s in self.search_ranked(text, only_exportable=only_exportable)]

    def search_ranked(self, text: str, *, only_exportable: bool = False) -> list:
        """返回 [(score, Song)]，score 越大越相关；空查询返回全部（score=0）。"""
        tokens = _query_tokens(text)
        out = []
        for s in self.songs.values():
            if only_exportable and not self._song_exportable(s):
                continue
            if not tokens:
                out.append((0.0, s))
                continue
            sc = _score_song(tokens, s)
            if sc > 0:
                out.append((sc, s))
        out.sort(key=lambda p: (-p[0], p[1].name))
        return out

    def suggest(self, text: str, *, limit: int = 10, only_exportable: bool = False) -> list:
        """给下拉候选用的前 N 首。"""
        return self.search(text, only_exportable=only_exportable)[:limit]

    def counts(self) -> dict:
        exportable = url_only = none = 0
        for s in self.songs.values():
            if any(g.decryptable for g in s.gears):
                exportable += 1
            elif any(g.downloadable for g in s.gears):
                url_only += 1
            else:
                none += 1
        return {"exportable": exportable, "url_only": url_only, "none": none}

    def stats(self) -> dict:
        total = len(self.songs)
        with_gear = sum(1 for s in self.songs.values() if s.gears)
        decryptable = sum(1 for s in self.songs.values() if any(g.decryptable for g in s.gears))
        downloadable = sum(1 for s in self.songs.values() if any(g.downloadable for g in s.gears))
        return {"total": total, "with_gear": with_gear,
                "decryptable": decryptable, "downloadable": downloadable}


def ext_for(fmt: str | None) -> str:
    return FORMAT_EXT.get(fmt or "", "m4a")
