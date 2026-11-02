# -*- coding: utf-8 -*-
"""开机自启：写入 HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run。

打包后写 exe 路径；源码运行时写 pythonw + app.py，避免弹控制台。
"""
from __future__ import annotations

import sys
from pathlib import Path

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_APP_NAME = "QishuiNative"


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _launch_command() -> str:
    if _is_frozen():
        return f'"{Path(sys.executable).resolve()}"'
    app_py = Path(__file__).resolve().parent.parent / "app.py"
    pyw = Path(sys.executable).with_name("pythonw.exe")
    exe = pyw if pyw.is_file() else Path(sys.executable)
    return f'"{exe}" "{app_py}"'


def is_enabled() -> bool:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as k:
            try:
                winreg.QueryValueEx(k, _APP_NAME)
                return True
            except FileNotFoundError:
                return False
    except Exception:
        return False


def set_enabled(enabled: bool) -> bool:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as k:
            if enabled:
                winreg.SetValueEx(k, _APP_NAME, 0, winreg.REG_SZ, _launch_command())
            else:
                try:
                    winreg.DeleteValue(k, _APP_NAME)
                except FileNotFoundError:
                    pass
        return True
    except Exception:
        return False


def sync_to_config(cfg: dict) -> None:
    """按配置同步自启状态（幂等）。"""
    want = bool(cfg.get("autostart", False))
    if want != is_enabled():
        set_enabled(want)
