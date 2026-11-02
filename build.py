# -*- coding: utf-8 -*-
"""打包脚本：PyInstaller 生成单文件夹 exe（推荐 onedir，启动快、体积小）。

用法：
    python build.py            # 生成 dist/QishuiNative/ 目录，内含 QishuiNative.exe
    python build.py --onefile  # 单文件（启动慢，不推荐）

说明：
- node.exe 与 客户端原生模块 不打包进 exe，运行时从客户端目录探测；
  也可在 exe 同级放 node\\node.exe、resources\\app.asar.unpacked\\客户端原生模块 覆盖。
- 可选把 ffmpeg.exe 放到 exe 同级 tools\\ 下以启用导出后时长校验。
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NAME = "QishuiNative"
ICON = ROOT / "assets" / "icon.ico"


def ensure_pyinstaller():
    try:
        import PyInstaller  # noqa: F401
        return
    except ImportError:
        print("未安装 PyInstaller，正在安装…")
        subprocess.check_call([sys.executable, "-m", "pip", "install",
                               "-i", "https://pypi.tuna.tsinghua.edu.cn/simple",
                               "pyinstaller"])


def build(onefile: bool):
    ensure_pyinstaller()
    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--name", NAME,
        "--windowed",                       # 无控制台窗口（GUI）
    ]
    if onefile:
        args.append("--onefile")
    else:
        args.append("--onedir")
    if ICON.is_file():
        args += ["--icon", str(ICON)]
    # 隐藏导入：core 子模块动态使用，PySide6 插件自动收集
    args += [
             # 刮削：mutagen 按扩展名动态派发，需显式收集各格式子模块
             "--hidden-import", "mutagen",
             "--hidden-import", "mutagen.flac",
             "--hidden-import", "mutagen.mp4",
             "--hidden-import", "mutagen.id3",
             "--hidden-import", "mutagen.mp3",
             "--hidden-import", "mutagen.oggvorbis",
             "--hidden-import", "mutagen.wave",
             "--hidden-import", "PIL.Image",
             "--hidden-import", "PIL.ImageFile",
             # 模糊搜索用拼音（可选依赖）
             "--hidden-import", "pypinyin",
             "--collect-data", "pypinyin"]
    if ICON.is_file():
        # 图标必须进 _internal，运行时 env.resource_path 才能找到
        args += ["--add-data", f"{ICON}{';' if sys.platform == 'win32' else ':'}assets"]
    args.append(str(ROOT / "app.py"))
    print("PyInstaller 参数：", " ".join(args))
    subprocess.check_call(args, cwd=str(ROOT))

    # 拷贝 assets 到输出（onedir 时）
    out = ROOT / "dist" / (NAME if not onefile else "")
    if not onefile and (ROOT / "dist" / NAME).is_dir():
        target = ROOT / "dist" / NAME
        if ICON.is_file():
            shutil.copy2(ICON, target / "icon.ico")
    print("\n打包完成。输出目录：", ROOT / "dist")


if __name__ == "__main__":
    build("--onefile" in sys.argv)
