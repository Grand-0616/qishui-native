# -*- coding: utf-8 -*-
"""后台任务线程：扫描 / 单曲导出 / 批量导出。全部走 QThread，UI 只收信号。"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal

from core import env, library
from core.exporter import ExportResult, export_song, refresh_and_export


class ScanWorker(QThread):
    done = Signal(object)      # Library
    failed = Signal(str)
    warn = Signal(str)         # 非致命：能扫到歌但解不了 key（多半没装客户端/node）

    def __init__(self, decode: bool = True, parent=None):
        super().__init__(parent)
        self._decode = decode

    def run(self):
        try:
            lib = library.Library().refresh(decode=self._decode)
            if lib.error and lib.cache_missing:
                self.failed.emit(lib.error)
                return
            if lib.error:
                self.warn.emit(lib.error)
            self.done.emit(lib)
        except Exception as e:  # pragma: no cover
            self.failed.emit(str(e))


class ExportWorker(QThread):
    """单曲导出。"""
    progress = Signal(str)     # 状态文本
    done = Signal(object)      # ExportResult

    def __init__(self, song, quality, out_dir, allow_download=False,
                 scrape=True, scrape_sidecar=True, parent=None):
        super().__init__(parent)
        self._song = song
        self._quality = quality
        self._out_dir = out_dir
        self._allow_download = allow_download
        self._scrape = scrape
        self._scrape_sidecar = scrape_sidecar

    def run(self):
        try:
            self.progress.emit("正在解密…")
            r = export_song(self._song, quality=self._quality,
                            out_dir=self._out_dir, allow_download=self._allow_download,
                            scrape=self._scrape, scrape_sidecar=self._scrape_sidecar)
            self.done.emit(r)
        except Exception as e:  # pragma: no cover
            self.done.emit(ExportResult(False, reason=str(e)))


class RefreshExportWorker(QThread):
    """刷新音源链接后导出（解决缓存 URL 过期 403）。"""
    progress = Signal(str)
    done = Signal(object)      # ExportResult

    def __init__(self, song, quality, out_dir, scrape=True, scrape_sidecar=True, parent=None):
        super().__init__(parent)
        self._song = song
        self._quality = quality
        self._out_dir = out_dir
        self._scrape = scrape
        self._scrape_sidecar = scrape_sidecar

    def run(self):
        try:
            self.progress.emit("正在向服务端刷新音源链接…")
            r = refresh_and_export(self._song, quality=self._quality, out_dir=self._out_dir,
                                   scrape=self._scrape, scrape_sidecar=self._scrape_sidecar)
            self.done.emit(r)
        except Exception as e:  # pragma: no cover
            self.done.emit(ExportResult(False, reason=str(e)))


class BatchExportWorker(QThread):
    """批量导出多首歌。每完成一首发一次 item_done。"""
    item_done = Signal(object, str, object)   # song, quality, ExportResult
    progress = Signal(int, int)               # done, total
    finished_all = Signal(int, int)           # ok, total

    def __init__(self, songs, out_dir, allow_download=False, quality=None,
                 scrape=True, scrape_sidecar=True, parent=None):
        super().__init__(parent)
        self._songs = list(songs)
        self._out_dir = out_dir
        self._allow_download = allow_download
        self._quality = quality      # 指定档位；None=自动选每首最高可导出档
        self._scrape = scrape
        self._scrape_sidecar = scrape_sidecar
        self._stop = False

    def stop(self):
        self._stop = True

    def _pick_quality(self, song):
        """批量时每首的导出档位：指定档优先；否则选 rank 最高的可导出档
        （本地可解密或可下载解密），都没有则退回最佳档。"""
        if self._quality:
            return self._quality
        for g in song.gears:  # gears 已按 rank 降序
            if g.decryptable or (self._allow_download and g.downloadable):
                return g.quality
        best = song.best_gear
        return best.quality if best else None

    def run(self):
        total = len(self._songs)
        ok = 0
        for i, song in enumerate(self._songs):
            if self._stop:
                break
            q = self._pick_quality(song)
            try:
                r = export_song(song, quality=q, out_dir=self._out_dir,
                                allow_download=self._allow_download,
                                scrape=self._scrape, scrape_sidecar=self._scrape_sidecar)
            except Exception as e:
                r = ExportResult(False, reason=str(e))
            if r.ok:
                ok += 1
            self.item_done.emit(song, r.quality or "", r)
            self.progress.emit(i + 1, total)
        self.finished_all.emit(ok, total)


class LocalizeWorker(QThread):
    """批量把本地歌词/封面写进音频文件标签（不联网、不改音频数据）。"""
    progress = Signal(int, int)      # done, total
    finished_all = Signal(int, int, int)   # ok, fail, total

    def __init__(self, items, embed: bool = True, sidecar: bool = False, parent=None):
        super().__init__(parent)
        self._items = list(items)
        self._embed = embed
        self._sidecar = sidecar

    def run(self):
        from core import localtool
        ok = fail = 0
        total = len(self._items)
        for idx, item in enumerate(self._items, 1):
            try:
                good, _msg = localtool.apply(item, embed=self._embed, sidecar=self._sidecar)
            except Exception:
                good = False
            if good:
                ok += 1
            else:
                fail += 1
            self.progress.emit(idx, total)
        self.finished_all.emit(ok, fail, total)
