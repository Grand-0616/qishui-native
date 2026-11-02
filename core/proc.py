"""统一的子进程调用入口。

为什么要这个模块：
    PyInstaller `--windowed` 打包后本进程没有控制台，但只要去启动一个控制台程序
    （node.exe / ffmpeg.exe / ffprobe.exe），Windows 就会为子进程新建一个控制台窗口，
    表现为界面上「闪一下黑框」。刷新音源会连续调多个 node 进程，所以闪得最明显。

    修法：所有子进程一律带 CREATE_NO_WINDOW（0x08000000）。
    同时把 stdin 钉到 DEVNULL，避免子进程在某些情况下等输入。

用法：
    from . import proc
    p = proc.run([str(node), tmp], capture_output=True, timeout=30)
"""

from __future__ import annotations

import subprocess
import sys

# Windows: 不为子进程创建控制台窗口。非 Windows 传 0（该参数在 posix 上被忽略）。
CREATE_NO_WINDOW = 0x08000000
_NO_WINDOW = CREATE_NO_WINDOW if sys.platform == "win32" else 0


def run(cmd, **kwargs):
    """subprocess.run 的包装：默认隐藏控制台窗口。

    注意：调用方传了 input= 时不能再设 stdin（subprocess 会报
    "stdin and input arguments may not both be used"）。
    """
    kwargs.setdefault("creationflags", _NO_WINDOW)
    if "input" not in kwargs:
        kwargs.setdefault("stdin", subprocess.DEVNULL)
    return subprocess.run(cmd, **kwargs)


def popen(cmd, **kwargs):
    """subprocess.Popen 的包装：默认隐藏控制台窗口。"""
    kwargs.setdefault("creationflags", _NO_WINDOW)
    if "input" not in kwargs:
        kwargs.setdefault("stdin", subprocess.DEVNULL)
    return subprocess.Popen(cmd, **kwargs)
