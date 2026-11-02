# -*- coding: utf-8 -*-
"""入口：启动原生 PySide6 主窗口（含单实例锁）。"""
from __future__ import annotations

import sys


def _acquire_single_instance():
    """用 Windows 命名互斥锁保证单实例；已存在则返回 None。"""
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.CreateMutexW(None, False, "Global\\QishuiNativeSingleton")
        if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            return None
        return handle
    except Exception:
        return True  # 非 Windows 或失败时不阻塞启动


def main():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFont
    from ui import theme
    from ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("QishuiNative")
    # 应用级图标：任务栏 / Alt-Tab / 窗口标题栏都取这个
    try:
        from core import env as _env
        from PySide6.QtGui import QIcon as _QIcon
        _ico = _env.icon_path()
        if _ico:
            app.setWindowIcon(_QIcon(str(_ico)))
    except Exception:
        pass
    app.setStyleSheet(theme.QSS)
    app.setFont(QFont("Microsoft YaHei UI", 9))
    app.setQuitOnLastWindowClosed(False)  # 支持托盘常驻

    win = MainWindow()
    win.show()
    _check_runtime_deps(win)
    sys.exit(app.exec())


def _check_runtime_deps(win):
    """启动时检查外部依赖（汽水客户端 / Node.js / ffmpeg），缺失就提示怎么补。"""
    try:
        from core import env
        missing = []
        if not env.find_node():
            missing.append(("Node.js", "安装 Node.js LTS（nodejs.org），或在设置里放置 node/node.exe"))
        if not env.find_client_lib():
            missing.append(("汽水音乐客户端", "安装汽水音乐 PC 客户端并播放过至少一首歌（提供客户端原生模块与缓存）"))
        if not env.find_ffmpeg("ffmpeg.exe"):
            missing.append(("ffmpeg（可选）", "缺它只能导出 .m4a，装了才能转成真裸 FLAC"))
        if not missing:
            return
        from PySide6.QtWidgets import QMessageBox
        hard = [m for m in missing if "可选" not in m[0]]
        box = QMessageBox(win)
        box.setWindowTitle("缺少运行依赖" if hard else "可选依赖缺失")
        box.setIcon(QMessageBox.Warning if hard else QMessageBox.Information)
        box.setText("检测到必需依赖缺失，导出会失败：" if hard else "以下可选依赖缺失，部分功能受限：")
        text = "\n".join(f"· {n}：{tip}" for n, tip in missing)
        box.setInformativeText(text + (f"\n\n汽水音乐官网：{env.SODA_SITE}" if any("汽水" in n for n, _ in missing) else ""))
        open_btn = None
        if any("汽水" in n for n, _ in missing):
            open_btn = box.addButton("打开汽水官网", QMessageBox.ActionRole)
        box.addButton("知道了", QMessageBox.AcceptRole)
        box.exec()
        if open_btn is not None and box.clickedButton() is open_btn:
            try:
                from PySide6.QtGui import QDesktopServices
                from PySide6.QtCore import QUrl
                QDesktopServices.openUrl(QUrl(env.SODA_SITE))
            except Exception:
                pass
    except Exception:
        pass


def _selftest() -> int:
    """离线自检（打包后验证依赖是否齐全）：QishuiNative.exe --selftest

    结果写到 data/selftest.txt；退出码 0=通过。
    """
    import traceback
    from pathlib import Path
    lines, ok = [], True
    try:
        import mutagen
        from mutagen.flac import FLAC  # noqa: F401
        from PIL import Image  # noqa: F401
        from core import krc, tags, scraper, netease  # noqa: F401
        lines.append("import ok: mutagen " + getattr(mutagen, "version_string", "?"))
        sample = "[1000,500]<0,200,0>你<200,300,0>好\n"
        ls, _ = krc.parse_krc(sample)
        assert len(ls) == 1 and ls[0].words[0][0] == 1000
        assert "[00:01.00]你好" in krc.to_lrc(ls, {})
        lines.append("krc ok")
        assert callable(tags.write_tags) and callable(scraper.attach)
        lines.append("scraper ok")
    except Exception:
        ok = False
        lines.append(traceback.format_exc())
    try:
        from core import env
        p = env.data_path("selftest.txt")
    except Exception:
        p = Path.cwd() / "selftest.txt"
    try:
        p.write_text(("OK\n" if ok else "FAIL\n") + "\n".join(lines), encoding="utf-8")
    except OSError:
        pass
    return 0 if ok else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    _h = _acquire_single_instance()
    if _h is None:  # 已有实例在跑：本进程直接退出（互斥锁随原进程释放）
        sys.exit(0)
    main()
