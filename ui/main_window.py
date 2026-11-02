# -*- coding: utf-8 -*-
"""主窗口：左侧歌曲列表 + 右侧详情，全部原生 Qt 控件。"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QSize, Signal, QStringListModel
from PySide6.QtGui import QAction, QIcon, QColor, QPixmap, QPainter, QFont, QLinearGradient
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QListWidget, QListWidgetItem, QFrame, QComboBox, QFileDialog,
    QMenu, QMessageBox, QProgressBar, QSizePolicy, QSystemTrayIcon, QCheckBox,
    QCompleter,
)

from core import autostart, env, library
from core import exporter as _exporter
from core.exporter import ExportResult, is_exported, load_index, export_song
from . import theme
from .settings_dialog import SettingsDialog
from .workers import (BatchExportWorker, ExportWorker, LocalizeWorker,
                      RefreshExportWorker, ScanWorker)

APP_TITLE = "汽水音乐 · 原生导出器"


def _human_size(n):
    if not n:
        return "-"
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f}{unit}" if unit == "B" else f"{n/1:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def _human_dur(ms):
    """duration 字段单位是毫秒，统一格式化为 m:ss。"""
    if not ms:
        return "--:--"
    sec = int(ms) // 1000
    return f"{sec//60}:{sec%60:02d}"


def _soda_found() -> bool:
    """汽水客户端是否检测到（用于把空列表文案换成「请先装客户端」）。"""
    try:
        from core import env
        return bool(env.soda_status().get("found"))
    except Exception:
        return True


def _avatar_pixmap(text: str, size: int = 56) -> QPixmap:
    """用歌名首字生成彩色封面块（无网络、无图片依赖）。"""
    colors = ["#3ea6ff", "#8e7cff", "#ff7c9c", "#3ddc84", "#ffb84d", "#4ecdc4"]
    ch = (text or "?").strip()[:1]
    idx = sum(ord(c) for c in (text or "")) % len(colors)
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    grad = QLinearGradient(0, 0, size, size)
    grad.setColorAt(0, QColor(colors[idx]))
    grad.setColorAt(1, QColor(colors[idx]).darker(140))
    p.setBrush(grad)
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(0, 0, size, size, 12, 12)
    p.setPen(QColor("#ffffff"))
    f = QFont("Microsoft YaHei UI", int(size * 0.42), QFont.Bold)
    p.setFont(f)
    p.drawText(pm.rect(), Qt.AlignCenter, ch)
    p.end()
    return pm


class SongList(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setUniformItemSizes(True)
        self.setSpacing(0)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1000, 680)
        self.setMinimumSize(760, 520)
        _ico = env.icon_path()
        if _ico:
            self.setWindowIcon(QIcon(str(_ico)))

        self.lib: library.Library | None = None
        self.current_song: library.Song | None = None
        self._scan_worker = None
        self._export_worker = None
        self._batch_worker = None
        self._cfg = env.load_config()

        self._build_ui()
        self._build_tray()
        autostart.sync_to_config(self._cfg)
        self._apply_capabilities()
        self._refresh_list()

    # ------------------------------------------------------------ 构建
    def _build_ui(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # 左侧栏
        side = QWidget()
        side.setObjectName("sidebar")
        side.setFixedWidth(380)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(0)

        # 顶部品牌 + 搜索
        head = QWidget()
        hl = QVBoxLayout(head)
        hl.setContentsMargins(16, 16, 16, 8)
        hl.setSpacing(10)
        brand = QLabel("汽水音乐")
        brand.setObjectName("title")
        hl.addWidget(brand)
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索歌名 / 歌手 / 专辑（支持拼音、空格多关键词）")
        self.search.textChanged.connect(self._apply_filter)
        hl.addWidget(self.search)

        # 候选下拉：列出模糊匹配到的歌，可用鼠标/键盘直接选
        self._sug_model = QStringListModel(self)
        self._sug_map: dict[str, str] = {}          # 候选项文本 → track_id
        self._completer = QCompleter(self._sug_model, self)
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
        self._completer.setMaxVisibleItems(10)
        self._completer.activated.connect(self._on_suggestion_picked)
        self.search.setCompleter(self._completer)
        # 下拉列表样式（completer 的 popup 是独立窗口，需要单独给 objectName）
        try:
            self._completer.popup().setObjectName("searchPopup")
        except Exception:
            pass
        self.search.textEdited.connect(self._update_suggestions)
        self._cur_songs: list = []

        # 过滤：只看本地有可解密缓存、真正能导出的曲目（隐藏仅播放列表无缓存的条目）
        self.chk_exportable = QCheckBox("只看可导出（隐藏无缓存条目）")
        self.chk_exportable.setChecked(True)
        self.chk_exportable.toggled.connect(self._apply_filter)
        hl.addWidget(self.chk_exportable)

        row = QHBoxLayout()
        self.btn_refresh = QPushButton("刷新")
        self.btn_refresh.clicked.connect(self._refresh_list)
        self.btn_settings = QPushButton("设置")
        self.btn_settings.clicked.connect(self._open_menu_settings)
        self.btn_localize = QPushButton("整理本地文件")
        self.btn_localize.setToolTip("把同目录的歌词(.lrc/.krc)与封面图片写进音频文件标签")
        self.btn_localize.clicked.connect(self._localize_folder)
        row.addWidget(self.btn_refresh)
        row.addWidget(self.btn_localize)
        row.addWidget(self.btn_settings)
        hl.addLayout(row)
        sl.addWidget(head)

        # 列表 + 状态
        self.list = SongList()
        self.list.itemSelectionChanged.connect(self._on_select)
        self.list.itemDoubleClicked.connect(lambda _: self._export_current())
        sl.addWidget(self.list, 1)

        self.stat_label = QLabel("准备就绪（公开版：本地整理）")
        self.stat_label.setObjectName("subtitle")
        self.stat_label.setContentsMargins(16, 6, 16, 12)
        sl.addWidget(self.stat_label)

        outer.addWidget(side)

        # 右侧详情
        detail = QWidget()
        detail.setObjectName("detail")
        dl = QVBoxLayout(detail)
        dl.setContentsMargins(28, 24, 28, 20)
        dl.setSpacing(18)
        self._build_detail(dl, detail)
        outer.addWidget(detail, 1)

        self.setStatusBar(self.statusBar())
        self.statusBar().showMessage("就绪")

    def _build_detail(self, dl, parent):
        # 空状态提示
        self.empty_hint = QLabel("从左侧选择一首歌查看详情")
        self.empty_hint.setObjectName("subtitle")
        self.empty_hint.setAlignment(Qt.AlignCenter)
        dl.addWidget(self.empty_hint, 1)

        # 详情主体（选中后显示）
        self.detail_body = QWidget()
        bl = QVBoxLayout(self.detail_body)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(18)

        # 头部：封面 + 标题
        header = QHBoxLayout()
        header.setSpacing(18)
        self.cover = QLabel()
        self.cover.setFixedSize(96, 96)
        header.addWidget(self.cover)
        tcol = QVBoxLayout()
        tcol.setSpacing(6)
        self.d_title = QLabel()
        self.d_title.setObjectName("title")
        self.d_title.setWordWrap(True)
        self.d_artist = QLabel()
        self.d_artist.setObjectName("subtitle")
        self.d_album = QLabel()
        self.d_album.setObjectName("subtitle")
        self.d_meta = QLabel()
        self.d_meta.setObjectName("subtitle")
        tcol.addWidget(self.d_title)
        tcol.addWidget(self.d_artist)
        tcol.addWidget(self.d_album)
        tcol.addWidget(self.d_meta)
        tcol.addStretch()
        header.addLayout(tcol, 1)
        bl.addLayout(header)

        # 档位选择
        card = QFrame()
        card.setObjectName("card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(18, 16, 18, 16)
        cl.setSpacing(12)
        lbl = QLabel("可用音质")
        lbl.setObjectName("section")
        cl.addWidget(lbl)
        self.quality_combo = QComboBox()
        cl.addWidget(self.quality_combo)
        self.gear_info = QLabel()
        self.gear_info.setObjectName("subtitle")
        self.gear_info.setWordWrap(True)
        cl.addWidget(self.gear_info)

        btnrow = QHBoxLayout()
        self.btn_export = QPushButton("导出此歌")
        self.btn_export.setObjectName("primary")
        self.btn_export.clicked.connect(self._export_current)
        self.btn_refresh_export = QPushButton("刷新音源并导出")
        self.btn_refresh_export.setToolTip(
            "缓存里的下载链接会过期（约 1~3 天）。此按钮会向汽水服务端重新签发最新链接后导出，\n"
            "适合『只看可导出里有歌但导出提示链接已过期』的情况。")
        self.btn_refresh_export.clicked.connect(self._refresh_export_current)
        self.btn_open_dir = QPushButton("打开目录")
        self.btn_open_dir.clicked.connect(self._open_out_dir)
        btnrow.addWidget(self.btn_export, 1)
        btnrow.addWidget(self.btn_refresh_export)
        btnrow.addWidget(self.btn_open_dir)
        cl.addLayout(btnrow)

        self.batch_check = QCheckBox("导出全部可用歌曲（批量）")
        cl.addWidget(self.batch_check)
        bl.addWidget(card)

        bl.addStretch()
        dl.addWidget(self.detail_body, 1)
        self.detail_body.hide()

    def _build_tray(self):
        self.tray = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        _ico = env.icon_path()
        icon = QIcon(str(_ico)) if _ico else QIcon(_avatar_pixmap("汽"))
        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip(APP_TITLE)
        menu = QMenu()
        act_show = QAction("显示窗口", self)
        act_show.triggered.connect(self._show_from_tray)
        act_quit = QAction("退出", self)
        act_quit.triggered.connect(self._quit)
        menu.addAction(act_show)
        menu.addSeparator()
        menu.addAction(act_quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

    # ------------------------------------------------------------ 扫描/刷新
    def _refresh_list(self):
        self.btn_refresh.setEnabled(False)
        self.stat_label.setText("正在扫描缓存…")
        self._scan_worker = ScanWorker(decode=True, parent=self)
        self._scan_worker.done.connect(self._on_scan_done)
        self._scan_worker.failed.connect(self._on_scan_failed)
        self._scan_worker.warn.connect(self._on_scan_warn)
        self._scan_worker.start()

    def _on_scan_warn(self, msg):
        self.statusBar().showMessage(msg, 8000)

    def _on_scan_done(self, lib):
        self.lib = lib
        self.btn_refresh.setEnabled(True)
        self._apply_filter()   # _apply_filter 内部会设置正确的统计文案，这里不再覆盖
        if getattr(lib, "error", None):
            self.stat_label.setToolTip(lib.error)
            self.statusBar().showMessage(lib.error, 10000)
        else:
            self.stat_label.setToolTip("")
            self.statusBar().showMessage("扫描完成", 3000)

    def _on_scan_failed(self, msg):
        self.btn_refresh.setEnabled(True)
        self.stat_label.setText("扫描失败")
        self.statusBar().showMessage(msg, 6000)
        QMessageBox.warning(self, "无法读取缓存", msg)

    # ------------------------------------------------- 搜索候选
    def _update_suggestions(self, text: str):
        """输入时刷新候选；不改变列表本身（列表由 textChanged→_apply_filter 驱动）。"""
        if not self.lib or not (text or "").strip():
            self._sug_map.clear()
            self._sug_model.setStringList([])
            return
        try:
            only_exp = self.chk_exportable.isChecked()
            songs = self.lib.suggest(text, limit=10, only_exportable=only_exp)
        except Exception:
            return
        items, mapping = [], {}
        for s in songs:
            label = f"{s.name} · {s.artist_text}"
            if label in mapping:          # 同名同歌手，加时长区分
                label = f"{label} · {_human_dur(s.duration)}"
            mapping[label] = s.track_id
            items.append(label)
        self._sug_map = mapping
        self._sug_model.setStringList(items)
        if items:
            self._completer.complete()

    def _on_suggestion_picked(self, label: str):
        """从候选里选中一首：把搜索框钉到该歌名并定位到它。"""
        tid = self._sug_map.get(label)
        if not tid:
            return
        song = self.lib.songs.get(tid) if self.lib else None
        if song is None:
            return
        self.search.blockSignals(True)
        self.search.setText(song.name)
        self.search.blockSignals(False)
        self.chk_exportable.setChecked(False)   # 选中后就别被「只看可导出」藏掉
        self._apply_filter()
        for row in range(self.list.count()):
            item = self.list.item(row)
            if item and item.data(Qt.UserRole) == tid:
                self.list.setCurrentRow(row)
                self.list.scrollToItem(item)
                break
        self.search.setFocus()

    def _apply_filter(self):
        if not self.lib:
            return
        text = self.search.text()
        only_exp = self.chk_exportable.isChecked()
        songs = self.lib.search_ranked(text, only_exportable=only_exp)
        songs = [s for _, s in songs]
        self._cur_songs = songs
        cur_tid = self.current_song.track_id if self.current_song else None
        self.list.blockSignals(True)
        self.list.clear()
        cur_still = False
        for s in songs:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, s.track_id)
            item.setSizeHint(QSize(0, 54))
            self.list.addItem(item)
            w = self._make_row(s)
            self.list.setItemWidget(item, w)
            if s.track_id == cur_tid:
                item.setSelected(True)
                cur_still = True
        self.list.blockSignals(False)

        c = self.lib.counts()
        total_shown = len(songs)
        exportable_total = c['exportable'] + c['url_only']  # 本地可解 + 可下载解密
        if only_exp:
            self.stat_label.setText(
                f"显示 {total_shown} 首可导出 · 已隐藏 {c['none']} 首无可用档位"
            )
        else:
            self.stat_label.setText(
                f"共 {self.lib.stats()['total']} 首 · 可导出 {exportable_total} · "
                f"无可用档位 {c['none']}"
            )

        # 当前选中项被过滤掉了 → 清空详情
        if not cur_still:
            self.current_song = None
            self.empty_hint.show()
            self.detail_body.hide()

        if songs and self.current_song is None:
            self.list.setCurrentRow(0)
        elif not songs:
            self.current_song = None
            if only_exp and not _soda_found():
                self.empty_hint.setText(
                    "未检测到汽水音乐客户端\n"
                    "请先安装汽水音乐（设置里可指定安装目录，也能打开官网下载），\n"
                    "装好后在客户端播放几首歌生成缓存"
                )
            else:
                self.empty_hint.setText(
                    "没有可导出的歌曲（需本地缓存 .bin）\n请先在汽水音乐播放几首歌生成缓存"
                    if only_exp else "没有匹配的歌曲"
                )
            self.empty_hint.show()
            self.detail_body.hide()

    def _make_row(self, s: library.Song) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(6, 4, 8, 4)
        lay.setSpacing(10)
        av = QLabel()
        av.setPixmap(_avatar_pixmap(s.name, 38))
        av.setFixedSize(38, 38)
        lay.addWidget(av)
        col = QVBoxLayout()
        col.setSpacing(1)
        n = QLabel(s.name)
        n.setStyleSheet("font-weight:600;")
        n.setMaximumWidth(240)
        n.setWordWrap(False)
        a = QLabel(s.artist_text)
        a.setObjectName("subtitle")
        col.addWidget(n)
        col.addWidget(a)
        lay.addLayout(col, 1)
        # 右上角音质标记：显示「可用档位中码率最高的」那一档（按 kbps 最大）
        best = s.top_bitrate_gear
        if best:
            br = f" {best.bitrate // 1000}k" if best.bitrate else ""
            tag_text = f"{best.qname}{br}"
        else:
            tag_text = "无档位"
        tag = QLabel(tag_text)
        tag.setStyleSheet(
            f"color:{theme.GREEN if (best and (best.decryptable or best.downloadable)) else theme.TEXT_DIM}; font-size:11px;"
        )
        lay.addWidget(tag)
        return w

    # ------------------------------------------------------------ 选择
    def _on_select(self):
        items = self.list.selectedItems()
        if not items or not self.lib:
            return
        tid = items[0].data(Qt.UserRole)
        song = self.lib.songs.get(tid)
        if not song:
            return
        self.current_song = song
        self._show_detail(song)

    def _show_detail(self, s: library.Song):
        self.empty_hint.hide()
        self.detail_body.show()
        self.cover.setPixmap(_avatar_pixmap(s.name, 96))
        self.d_title.setText(s.name)
        self.d_artist.setText(s.artist_text)
        self.d_album.setText(f"专辑：{s.album}" if s.album else "专辑：—")
        self.d_meta.setText(f"时长：{_human_dur(s.duration)}")

        self.quality_combo.blockSignals(True)
        self.quality_combo.clear()
        for g in s.gears:
            if g.decryptable:
                state = "可导出·本地缓存"
            elif g.downloadable:
                state = "可下载导出"
            elif g.available and not g.key_hex:
                state = "本地有缓存·缺密钥"
            else:
                state = "缺密钥·不可导出"
            bit = f" · {g.bitrate//1000}kbps" if g.bitrate else ""
            self.quality_combo.addItem(f"{g.qname}{bit}  （{state}）", g.quality)
        self.quality_combo.blockSignals(False)
        self._update_gear_info()
        self.quality_combo.currentIndexChanged.connect(self._update_gear_info)

        has_exportable = any(g.decryptable or g.downloadable for g in s.gears)
        self.btn_export.setEnabled(has_exportable or bool(s.gears))
        # 默认选档策略：优先「无损音质」(lossless)，其次按 rank 最高可导出档
        chosen = None
        for g in s.gears:  # 优先无损
            if g.quality == "lossless" and (g.decryptable or g.downloadable):
                chosen = g
                break
        if chosen is None:
            for g in s.gears:  # 否则 rank 最高可导出档
                if g.decryptable or g.downloadable:
                    chosen = g
                    break
        if chosen is None:
            best = s.best_gear
            if best and best.decryptable:
                chosen = best
        if chosen is not None:
            idx = self.quality_combo.findData(chosen.quality)
            if idx >= 0:
                self.quality_combo.setCurrentIndex(idx)

    def _update_gear_info(self):
        if not self.current_song:
            return
        q = self.quality_combo.currentData()
        g = self.current_song.gear_by_quality(q) if q else None
        if not g:
            self.gear_info.setText("")
            return
        bits = []
        if g.bitrate:
            bits.append(f"{g.bitrate//1000} kbps")
        if g.fmt:
            bits.append(g.fmt)
        if g.size:
            bits.append(_human_size(g.size))
        if is_exported(self.current_song.track_id, g.quality):
            bits.append("✓ 已导出")
        self.gear_info.setText(" · ".join(bits) if bits else "")

    # ------------------------------------------------------------ 导出
    def _export_current(self):
        if self.batch_check.isChecked():
            self._export_all()
            return
        if not self.current_song:
            return
        q = self.quality_combo.currentData()
        self._run_export(self.current_song, q)

    def _export_all(self):
        if not self.lib:
            return
        cfg = env.load_config()
        allow_dl = bool(cfg.get("allow_download", True))
        scrape = bool(cfg.get("scrape", True))
        sidecar = bool(cfg.get("scrape_sidecar", True))
        # 可导出的歌：本地可解密，或（开启下载时）有 url+key 可下载解密
        if allow_dl:
            songs = [s for s in self.lib.songs.values()
                     if any(g.decryptable or g.downloadable for g in s.gears)]
        else:
            songs = [s for s in self.lib.songs.values()
                     if any(g.decryptable for g in s.gears)]
        if not songs:
            QMessageBox.information(self, "批量导出",
                                    "当前没有可导出的歌曲。\n"
                                    "请先在汽水音乐播放几首歌以生成缓存/下发音源。")
            return
        out = env.out_dir()
        self.btn_export.setEnabled(False)
        self.btn_refresh.setEnabled(False)
        self._batch_worker = BatchExportWorker(songs, out, allow_download=allow_dl,
                                               scrape=scrape, scrape_sidecar=sidecar, parent=self)
        self._batch_worker.progress.connect(
            lambda d, t: self.statusBar().showMessage(f"批量导出中 {d}/{t}…")
        )
        self._batch_worker.finished_all.connect(self._on_batch_done)
        self._batch_worker.start()
        self.statusBar().showMessage(f"开始批量导出 {len(songs)} 首…")

    def _on_batch_done(self, ok, total):
        self.btn_export.setEnabled(True)
        self.btn_refresh.setEnabled(True)
        self.statusBar().showMessage(f"批量导出完成：成功 {ok}/{total}", 6000)
        QMessageBox.information(self, "批量导出", f"完成：成功 {ok} / 共 {total} 首")

    def _refresh_export_current(self):
        """向服务端刷新音源链接后导出当前选中档位。"""
        if not self.current_song:
            return
        q = self.quality_combo.currentData()
        out = env.out_dir()
        self.statusBar().showMessage(f"正在刷新音源：{self.current_song.name}…")
        self.btn_export.setEnabled(False)
        self.btn_refresh_export.setEnabled(False)
        cfg = env.load_config()
        self._refresh_worker = RefreshExportWorker(
            self.current_song, q, out,
            scrape=bool(cfg.get("scrape", True)),
            scrape_sidecar=bool(cfg.get("scrape_sidecar", True)), parent=self)
        self._refresh_worker.progress.connect(lambda t: self.statusBar().showMessage(t))
        self._refresh_worker.done.connect(self._on_refresh_export_done)
        self._refresh_worker.start()

    def _on_refresh_export_done(self, r: ExportResult):
        self.btn_export.setEnabled(True)
        self.btn_refresh_export.setEnabled(True)
        if r.ok:
            self.statusBar().showMessage(f"刷新并导出成功：{r.path.name}", 6000)
            self._update_gear_info()
            QMessageBox.information(self, "导出成功", f"已刷新音源并导出：\n{r.path}")
        else:
            self.statusBar().showMessage(f"刷新导出失败：{r.reason}", 7000)
            QMessageBox.warning(self, "刷新导出失败", r.reason)

    def _run_export(self, song, quality):
        out = env.out_dir()
        cfg = env.load_config()
        allow_dl = bool(cfg.get("allow_download", True))
        self.statusBar().showMessage(f"正在导出：{song.name}…")
        self.btn_export.setEnabled(False)
        self._export_worker = ExportWorker(
            song, quality, out, allow_download=allow_dl,
            scrape=bool(cfg.get("scrape", True)),
            scrape_sidecar=bool(cfg.get("scrape_sidecar", True)), parent=self)
        self._export_worker.progress.connect(lambda t: self.statusBar().showMessage(t))
        self._export_worker.done.connect(self._on_export_done)
        self._export_worker.start()

    def _on_export_done(self, r: ExportResult):
        self.btn_export.setEnabled(True)
        if r.ok:
            extra = ""
            sc = getattr(r, "scrape", None)
            if sc is not None:
                tagsx = []
                if sc.got_cover:
                    tagsx.append("封面")
                if sc.got_lyric:
                    tagsx.append(f"歌词{sc.lyric_lines}行")
                extra = ("　+刮削：" + "、".join(tagsx)) if tagsx else "　（无歌词/封面）"
            self.statusBar().showMessage(f"导出成功：{r.path.name}{extra}", 6000)
            self._update_gear_info()
        else:
            self.statusBar().showMessage(f"导出失败：{r.reason}", 6000)
            if "过期" in (r.reason or ""):
                QMessageBox.warning(
                    self, "导出失败",
                    f"{r.reason}\n\n可点下方『刷新音源并导出』按钮，"
                    "向汽水服务端重新获取最新链接后直接导出。")
            else:
                QMessageBox.warning(self, "导出失败", r.reason)

    def _open_out_dir(self):
        out = env.out_dir()
        import os
        try:
            os.startfile(str(out))
        except Exception as e:
            QMessageBox.information(self, "目录", f"{out}\n{e}")

    def _apply_capabilities(self):
        """公开版没有音源实现时，把导出入口隐藏，只留本地整理。"""
        if getattr(_exporter, "HAS_SOURCE", True):
            return
        try:
            self.btn_export.hide()
            self.btn_refresh_export.hide()
            self.chk_exportable.hide()
            self.chk_exportable.setChecked(False)
        except Exception:
            pass

    # ---------------------------------------------------------------- 本地整理
    def _localize_folder(self):
        from core import localtool
        folder = QFileDialog.getExistingDirectory(
            self, "选择文件夹（音频 + 同名歌词/封面）")
        if not folder:
            return
        items = localtool.scan(folder)
        if not items:
            QMessageBox.information(
                self, "整理本地文件",
                "该文件夹里没有找到音频文件。\n\n支持：" + " / ".join(localtool.AUDIO_EXT))
            return
        usable = [i for i in items if i.lyric or i.cover]
        if not usable:
            QMessageBox.information(
                self, "整理本地文件",
                f"找到 {len(items)} 首音频，但都没有同名歌词或封面。\n\n"
                "命名规则：\n"
                "· 歌词：与音频同名，后缀 .lrc / .krc / .txt\n"
                "· 封面：与音频同名图片，或 cover.jpg / folder.jpg")
            return
        if QMessageBox.question(
                self, "整理本地文件",
                f"共 {len(items)} 首音频，其中 {len(usable)} 首有歌词或封面。\n\n"
                "将把歌词与封面写入文件标签（只改标签，不动音频数据）。是否继续？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes) != QMessageBox.Yes:
            return
        self.btn_localize.setEnabled(False)
        self._loc_worker = LocalizeWorker(usable, embed=True, sidecar=False)
        self._loc_worker.progress.connect(
            lambda d, t: self.stat_label.setText(f"整理中… {d}/{t}"))
        self._loc_worker.finished_all.connect(self._on_localize_done)
        self._loc_worker.start()

    def _on_localize_done(self, ok, fail, total):
        self.btn_localize.setEnabled(True)
        self.stat_label.setText(f"本地整理完成：成功 {ok} / 失败 {fail}（共 {total}）")
        QMessageBox.information(
            self, "整理本地文件",
            f"完成：成功 {ok} 首，失败 {fail} 首。\n\n"
            "失败的通常是容器不支持写标签或文件只读。")

    def _open_menu_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec():
            self._cfg = env.load_config()
            self.statusBar().showMessage("设置已保存", 3000)
            self._update_gear_info()

    def _choose_out_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择导出目录", str(env.out_dir()))
        if d:
            cfg = env.load_config()
            cfg["out_dir"] = d
            env.save_config(cfg)
            self.statusBar().showMessage(f"导出目录已设为：{d}", 4000)

    def _about(self):
        info = env.describe()
        QMessageBox.information(
            self, "关于",
            f"{APP_TITLE}\n\n缓存：{info['cache']}\n数据：{info['data_dir']}\n\n"
            "原生 PySide6 界面，本地解密导出。"
        )

    # ------------------------------------------------------------ 托盘/关闭
    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self._show_from_tray()

    def _show_from_tray(self):
        self.showNormal()
        self.activateWindow()

    def _quit(self):
        if self._batch_worker and self._batch_worker.isRunning():
            self._batch_worker.stop()
        if self.tray:
            self.tray.hide()
        from PySide6.QtWidgets import QApplication
        QApplication.quit()

    def closeEvent(self, e):
        cfg = env.load_config()
        if cfg.get("close_to_tray", True) and self.tray:
            e.ignore()
            self.hide()
            self.tray.showMessage(APP_TITLE, "已最小化到托盘，双击图标恢复。",
                                  QSystemTrayIcon.Information, 2000)
        else:
            if self.tray:
                self.tray.hide()
            e.accept()
