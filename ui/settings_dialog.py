# -*- coding: utf-8 -*-
"""设置对话框：导出目录 / 关闭到托盘 / 开机自启 / 下载兜底。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox,
    QLineEdit, QFileDialog, QDialogButtonBox,
)

from core import autostart, env


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumWidth(520)
        self.cfg = env.load_config()
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(14)
        lay.setContentsMargins(20, 20, 20, 16)

        # 导出目录
        lay.addWidget(self._section("导出目录"))
        row = QHBoxLayout()
        self.out_edit = QLineEdit(self.cfg.get("out_dir", ""))
        btn = QPushButton("选择…")
        btn.clicked.connect(self._choose_dir)
        row.addWidget(self.out_edit, 1)
        row.addWidget(btn)
        lay.addLayout(row)

        # 汽水音乐客户端
        lay.addSpacing(10)
        lay.addWidget(self._section("汽水音乐客户端"))
        self.soda_edit = QLineEdit(self.cfg.get("soda_dir") or "")
        self.soda_edit.setPlaceholderText("留空 = 自动探测（默认安装位置 / 注册表 / 常见目录）")
        self.soda_edit.textChanged.connect(self._refresh_soda_status)
        srow = QHBoxLayout()
        sbtn = QPushButton("选择…")
        sbtn.clicked.connect(self._choose_soda_dir)
        srow.addWidget(self.soda_edit, 1)
        srow.addWidget(sbtn)
        lay.addLayout(srow)

        self.soda_status_lbl = QLabel()
        self.soda_status_lbl.setObjectName("subtitle")
        self.soda_status_lbl.setWordWrap(True)
        self.soda_status_lbl.setContentsMargins(0, 2, 0, 2)
        lay.addWidget(self.soda_status_lbl)
        lay.addSpacing(2)

        site = QLabel(
            f'没装客户端？<a href="{env.SODA_SITE}">前往汽水音乐官网下载</a>'
            f'（<span style="color:#8b8b8b">{env.SODA_SITE}</span>）'
        )
        site.setOpenExternalLinks(True)
        site.setObjectName("subtitle")
        site.setWordWrap(True)
        site.setContentsMargins(0, 2, 0, 2)
        site.setTextInteractionFlags(Qt.TextBrowserInteraction)
        lay.addWidget(site)
        self._refresh_soda_status()

        # 开关项
        lay.addSpacing(6)
        self.chk_tray = QCheckBox("关闭窗口时最小化到托盘")
        self.chk_tray.setChecked(bool(self.cfg.get("close_to_tray", True)))
        lay.addWidget(self.chk_tray)

        self.chk_auto = QCheckBox("开机自动启动")
        self.chk_auto.setChecked(autostart.is_enabled())
        lay.addWidget(self.chk_auto)

        self.chk_dl = QCheckBox("允许从网络下载音源（无需本地缓存，支持导出无损/高清档）")
        self.chk_dl.setChecked(bool(self.cfg.get("allow_download", True)))
        lay.addWidget(self.chk_dl)

        # 刮削
        lay.addSpacing(10)
        lay.addWidget(self._section("导出后刮削（海报 + 歌词）"))
        self.chk_scrape = QCheckBox("自动写入封面与内置歌词（FLAC/M4A/MP3 内嵌标签）")
        self.chk_scrape.setChecked(bool(self.cfg.get("scrape", True)))
        lay.addWidget(self.chk_scrape)
        self.chk_sidecar = QCheckBox("同时生成同名 .lrc 歌词与目录 cover 图片")
        self.chk_sidecar.setChecked(bool(self.cfg.get("scrape_sidecar", True)))
        lay.addWidget(self.chk_sidecar)
        self.chk_scrape.toggled.connect(self.chk_sidecar.setEnabled)
        self.chk_sidecar.setEnabled(self.chk_scrape.isChecked())
        hint = QLabel("歌词为汽水逐字歌词（KRC）转换的增强型 LRC，可用逐字滚动显示；"
                      "数据来自导出时同一个 track_v2 响应，不额外联网请求。")
        hint.setObjectName("subtitle")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        # 账户凭证（用于「刷新音源」向服务端重新签发链接）
        lay.addSpacing(10)
        lay.addWidget(self._section("账户凭证（刷新音源链接用）"))
        self.ck_status = QLabel()
        self.ck_status.setObjectName("subtitle")
        self.ck_status.setWordWrap(True)
        lay.addWidget(self.ck_status)
        ckrow = QHBoxLayout()
        self.btn_extract = QPushButton("提取登录凭证")
        self.btn_extract.setToolTip(
            "从本机汽水音乐读取登录 cookie 缓存到本软件，供『刷新音源并导出』使用。\n"
            "汽水音乐正在运行时其 cookie 库被独占，需先关闭汽水再提取，提取完可重新打开。\n"
            "登录态约 60 天有效，提取一次可长期使用。")
        self.btn_extract.clicked.connect(self._extract_cookie)
        ckrow.addWidget(self.btn_extract)
        ckrow.addStretch()
        lay.addLayout(ckrow)
        self._refresh_ck_status()

        # 环境信息
        lay.addSpacing(8)
        info = env.describe()
        info_lbl = QLabel(
            f"缓存目录：{info['cache']}\n数据目录：{info['data_dir']}"
        )
        info_lbl.setObjectName("subtitle")
        info_lbl.setWordWrap(True)
        info_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(info_lbl)

        lay.addStretch()
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("保存")
        bb.button(QDialogButtonBox.Cancel).setText("取消")
        bb.accepted.connect(self._save)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _section(self, text):
        lbl = QLabel(text)
        lbl.setObjectName("section")
        return lbl

    def _choose_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择导出目录", self.out_edit.text())
        if d:
            self.out_edit.setText(d)

    def _choose_soda_dir(self):
        d = QFileDialog.getExistingDirectory(
            self, "选择汽水音乐安装目录（含 resources 文件夹的那一层）", self.soda_edit.text()
        )
        if d:
            self.soda_edit.setText(d)

    def _refresh_soda_status(self):
        from pathlib import Path
        d = self.soda_edit.text().strip()
        hit = None
        try:
            if d:
                hit = env._device_in(Path(d))
            else:
                st = env.soda_status()
                hit = Path(st["device_node"]) if st.get("found") and st.get("device_node") else None
        except Exception:
            hit = None
        if hit:
            try:
                root = hit.parents[2]
            except IndexError:
                root = hit.parent
            self.soda_status_lbl.setText(f"✓ 已检测到客户端：{root}")
        else:
            self.soda_status_lbl.setText(
                "✗ 未检测到汽水音乐客户端（未找到客户端原生模块）。"
                "装好后可直接导出；也可手动指定安装目录。"
            )

    def _refresh_ck_status(self):
        from core import refresher
        p = refresher._cookie_cache_file()
        if p.is_file() and p.stat().st_size > 0:
            self.ck_status.setText("✓ 已缓存登录凭证（可用于刷新音源链接）")
        else:
            self.ck_status.setText("尚未提取登录凭证。若要用『刷新音源并导出』，请先提取。")

    def _extract_cookie(self):
        from PySide6.QtWidgets import QMessageBox
        from core import refresher
        try:
            refresher.cache_cookie_from_db()
        except Exception as e:
            QMessageBox.warning(self, "提取失败", str(e))
            return
        self._refresh_ck_status()
        QMessageBox.information(self, "提取成功", "登录凭证已缓存，现在可以使用『刷新音源并导出』。")

    def _save(self):
        self.cfg["out_dir"] = self.out_edit.text().strip() or str(env.DEFAULT_OUT())
        self.cfg["soda_dir"] = self.soda_edit.text().strip() or None
        self.cfg["close_to_tray"] = self.chk_tray.isChecked()
        self.cfg["allow_download"] = self.chk_dl.isChecked()
        self.cfg["scrape"] = self.chk_scrape.isChecked()
        self.cfg["scrape_sidecar"] = self.chk_sidecar.isChecked()
        env.save_config(self.cfg)
        env.reset_caches()          # 安装目录可能变了，清掉探测缓存
        autostart.set_enabled(self.chk_auto.isChecked())
        self.accept()
