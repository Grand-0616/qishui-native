# -*- coding: utf-8 -*-
"""运行环境探测：定位 node / 客户端原生模块 / 缓存目录 / ffmpeg，并管理可写数据目录。

设计要点（与旧项目一致的经验，但结构重写）：

- 客户端升级会让写死的版本路径失效 → 一律运行时探测，取最高版本目录。
- 每个定位都支持环境变量覆盖（QISHUI_*）。
- 只读资源（源码目录 / PyInstaller _MEIPASS）与可写数据（app_dir/data）分离。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
from functools import lru_cache
from pathlib import Path

# ---- 打包环境判定 ----
FROZEN = bool(getattr(sys, "frozen", False))
if FROZEN:
    APP_DIR = Path(sys.executable).resolve().parent
    _RES = Path(getattr(sys, "_MEIPASS", APP_DIR))
else:
    APP_DIR = Path(__file__).resolve().parent.parent  # qishui-native/
    _RES = APP_DIR

DATA_DIR = APP_DIR / "data"

_APP_ROOTS = ("Soda Music", "SodaMusic")
# 客户端安装目录里存放原生模块的子路径。模块文件名按通用命名，可用环境变量覆盖。
NATIVE_LIB = os.environ.get("QISHUI_CLIENT_LIB_NAME", "runtime.node")
NATIVE_TRANSPORT_LIB = os.environ.get("QISHUI_TRANSPORT_LIB_NAME", "transport.node")
_CLIENT_LIB_REL = Path("resources") / "app.asar.unpacked" / NATIVE_LIB

_VRE = re.compile(r"\d+(?:\.\d+)*")


def _vkey(name: str):
    if not _VRE.fullmatch(name or ""):
        return None
    return tuple(int(x) for x in name.split("."))


def _latest_version_dir(parent: Path):
    if not parent.is_dir():
        return None
    cands = []
    for d in parent.iterdir():
        if d.is_dir():
            k = _vkey(d.name)
            if k:
                cands.append((k, d))
    return max(cands, key=lambda kv: kv[0])[1] if cands else None


# ---------------------------------------------------------------- 汽水客户端定位
# 官网（供设置页给用户下载客户端）
SODA_SITE = "https://music.douyin.com/qishui/"


def soda_site() -> str:
    return SODA_SITE


def _reg_soda_dirs() -> list[Path]:
    """从卸载表 / App Paths 里找汽水音乐安装目录（仅 Windows，失败静默返回空）。"""
    if sys.platform != "win32":
        return []
    try:
        import winreg
    except Exception:
        return []
    out: list[Path] = []
    keys = [
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    for hive, path in keys:
        try:
            with winreg.OpenKey(hive, path) as k:
                total = winreg.QueryInfoKey(k)[0]
                for i in range(total):
                    try:
                        sub = winreg.EnumKey(k, i)
                        with winreg.OpenKey(k, sub) as sk:
                            name = str(winreg.QueryValueEx(sk, "DisplayName")[0] or "")
                            low = name.lower()
                            if "汽水" not in name and "soda" not in low:
                                continue
                            for vname in ("InstallLocation", "DisplayIcon"):
                                try:
                                    val = str(winreg.QueryValueEx(sk, vname)[0] or "")
                                except OSError:
                                    continue
                                if not val:
                                    continue
                                p = Path(val.strip('"').split(",")[0])
                                out.append(p.parent if p.suffix.lower() in (".exe", ".ico") else p)
                    except OSError:
                        continue
        except OSError:
            continue
    for app in ("汽水音乐.exe", "SodaMusic.exe"):
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                rf"Software\Microsoft\Windows\CurrentVersion\App Paths\{app}",
            ) as k:
                val = str(winreg.QueryValueEx(k, "")[0] or "")
                if val:
                    out.append(Path(val.strip('"')).parent)
        except OSError:
            continue
    return out


_NATIVE_SUBDIR = Path("resources") / "app.asar.unpacked"


def _native_libs_in(base: Path | None) -> list[Path]:
    """列出某个安装目录下客户端的原生模块（resources/app.asar.unpacked/*.node）。"""
    if not base:
        return []
    try:
        d = base / _NATIVE_SUBDIR
        if not d.is_dir():
            return []
        return sorted(p for p in d.glob("*.node") if p.is_file())
    except OSError:
        return []


def _client_lib_in(root: Path | None) -> Path | None:
    """在候选安装目录里找客户端原生模块（兼容版本子目录 / Packages 布局 / 直接是版本目录）。"""
    if not root:
        return None
    for base in (root, _latest_version_dir(root)):
        hit = _native_libs_in(base)
        if hit:
            return hit[0]
    pkgs = root / "Packages"
    if pkgs.is_dir():
        try:
            for sub in pkgs.iterdir():
                for base in (sub, _latest_version_dir(sub)):
                    hit = _native_libs_in(base)
                    if hit:
                        return hit[0]
        except OSError:
            return None
    return None


def _soda_candidate_roots() -> list[Path]:
    """候选安装目录，按优先级：用户指定 → 默认安装位置 → 注册表 → 常见目录扫一层。"""
    seen: set[str] = set()
    res: list[Path] = []

    def add(p) -> None:
        try:
            path = Path(p)
        except Exception:
            return
        key = str(path).lower()
        if not key or key in seen:
            return
        seen.add(key)
        res.append(path)

    try:
        cfg_dir = str(load_config().get("soda_dir") or "").strip()
    except Exception:
        cfg_dir = ""
    if cfg_dir:
        add(cfg_dir)

    localapp = Path(os.environ.get("LOCALAPPDATA", "") or "")
    for name in _APP_ROOTS:
        add(localapp / "Programs" / name)
    for p in _reg_soda_dirs():
        add(p)
    # 常见目录扫一层：命中 resources\app.asar.unpacked\客户端原生模块 就算
    for base in (localapp / "Programs",
                 Path(os.environ.get("PROGRAMFILES", "") or ""),
                 Path(os.environ.get("PROGRAMFILES(X86)", "") or ""),
                 localapp):
        try:
            if not base.is_dir():
                continue
            for sub in base.iterdir():
                if sub.is_dir() and _client_lib_in(sub) is not None:
                    add(sub)
        except OSError:
            continue
    return res


# ---------------------------------------------------------------- 可写目录
def ensure_data_dir() -> Path:
    """保证可写数据目录存在且真能写；失败退回 %APPDATA%\\QishuiNative。"""
    global DATA_DIR
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        probe = DATA_DIR / ".wtest"
        probe.write_text("1", encoding="utf-8")
        probe.unlink()
        return DATA_DIR
    except OSError:
        fb = Path(os.environ.get("APPDATA", str(Path.home()))) / "QishuiNative"
        fb.mkdir(parents=True, exist_ok=True)
        DATA_DIR = fb
        return fb


def data_path(*parts) -> Path:
    return ensure_data_dir().joinpath(*parts)


def resource_path(*parts) -> Path:
    return _RES.joinpath(*parts)


def app_path(*parts) -> Path:
    return APP_DIR.joinpath(*parts)


@lru_cache(maxsize=1)
def icon_path() -> Path | None:
    """窗口 / 托盘图标。打包后可能在 _MEIPASS 或 exe 同级，源码态在 assets/。"""
    for cand in (resource_path("assets", "icon.ico"), resource_path("icon.ico"),
                 APP_DIR / "assets" / "icon.ico", APP_DIR / "icon.ico"):
        try:
            if cand.is_file():
                return cand
        except OSError:
            continue
    return None


# ---------------------------------------------------------------- 外部工具
@lru_cache(maxsize=1)
def find_node() -> Path:
    """定位可 require(客户端原生模块) 的 node 可执行文件。"""
    env = os.environ.get("QISHUI_NODE")
    if env and Path(env).is_file():
        return Path(env)
    for cand in (app_path("node", "node.exe"), app_path("node.exe")):
        if cand.is_file():
            return cand
    which = shutil.which("node")
    if which:
        return Path(which)
    base = Path(os.environ.get("USERPROFILE", "")) / ".ai-manager" / "runtimes" / "node"
    vdir = _latest_version_dir(base)
    if vdir and (vdir / "node.exe").is_file():
        return vdir / "node.exe"
    raise RuntimeError("找不到 node.exe：请安装 node、放到软件目录 node\\ 下，或设 QISHUI_NODE")


@lru_cache(maxsize=1)
def find_client_lib() -> Path:
    """定位客户端提供的原生模块（提供密钥解析能力）。

    顺序：环境变量 → 用户指定/默认/注册表/常见目录（自动兼容任意安装位置）。
    """
    env = os.environ.get("QISHUI_CLIENT_LIB_PATH")
    if env and Path(env).is_file():
        return Path(env)
    for root in _soda_candidate_roots():
        hit = _client_lib_in(root)
        if hit:
            return hit
    raise RuntimeError(
        "未找到客户端原生模块：未检测到汽水音乐客户端。请先安装客户端，"
        f"或在设置里指定安装目录（官网 {SODA_SITE}）"
    )


@lru_cache(maxsize=1)
def find_transport_lib() -> Path:
    """定位客户端提供的传输层原生模块（提供请求签名能力），与原生模块同目录。"""
    env_ = os.environ.get("QISHUI_TRANSPORT_LIB_PATH")
    if env_ and Path(env_).is_file():
        return Path(env_)
    try:
        d = find_client_lib().parent
        libs = sorted(p for p in d.glob("*.node") if p.is_file())
        for p in libs:
            if p.name == NATIVE_TRANSPORT_LIB:
                return p
        if len(libs) > 1:
            return libs[1]
        if libs:
            return libs[0]
    except (RuntimeError, OSError):
        pass
    for root in _soda_candidate_roots():
        for base in (root, _latest_version_dir(root)):
            hit = _native_libs_in(base)
            if hit:
                return hit[0]
    raise RuntimeError(
        "未找到传输层原生模块：未检测到汽水音乐客户端。请先安装客户端，"
        f"或在设置里指定安装目录（官网 {SODA_SITE}）"
    )


@lru_cache(maxsize=8)
def find_ffmpeg(name: str = "ffmpeg.exe"):
    """定位 ffmpeg/ffprobe；找不到返回 None（只影响校验/转封装，不影响导出）。"""
    env = os.environ.get("QISHUI_FFMPEG")
    if env and (Path(env) / name).is_file():
        return Path(env) / name
    for base in (app_path("tools"), app_path("bin"), APP_DIR):
        if not base.is_dir():
            continue
        for direct in (base / name, base / "bin" / name):
            if direct.is_file():
                return direct
        for sub in sorted(base.glob("ffmpeg*")):
            cand = sub / "bin" / name
            if cand.is_file():
                return cand
    # 系统 PATH
    found = shutil.which(name)
    if found:
        return Path(found)
    # 常见安装位置（Windows）
    stem = Path(name).stem  # ffmpeg / ffprobe
    home = Path(os.environ.get("USERPROFILE", "") or "")
    localapp = Path(os.environ.get("LOCALAPPDATA", "") or "")
    candidates = [
        localapp / "Programs" / "ffmpeg" / "bin" / name,
        home / "scoop" / "apps" / "ffmpeg" / "current" / "bin" / name,
        Path("C:/ffmpeg/bin") / name,
        Path("C:/Program Files/ffmpeg/bin") / name,
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


# ---------------------------------------------------------------- 数据源
def cache_dir() -> Path:
    env = os.environ.get("QISHUI_CACHE")
    if env:
        return Path(env)
    # 开源版不使用任何客户端缓存；默认指向本程序自己的目录，
    # 需要时用环境变量 QISHUI_CACHE 指到别处。
    return data_path("media")


def storage_dir() -> Path:
    env = os.environ.get("QISHUI_STORAGE")
    if env:
        return Path(env)
    return data_path("storage")


# ---------------------------------------------------------------- 配置
CONFIG_FILE = lambda: data_path("config.json")  # noqa: E731
DEFAULT_OUT = lambda: app_path("music")  # noqa: E731

_DEFAULT_CFG = {
    "out_dir": None,
    "soda_dir": None,          # 汽水音乐安装目录（留空=自动探测）
    "close_to_tray": True,
    "theme": "dark",
    "allow_download": True,
    "scrape": True,
    "scrape_sidecar": True,
    "scrape_overwrite_sidecar": False,
}


def load_config() -> dict:
    cfg = dict(_DEFAULT_CFG)
    try:
        raw = json.loads(CONFIG_FILE().read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            cfg.update(raw)
    except Exception:
        pass
    if not cfg.get("out_dir"):
        cfg["out_dir"] = str(DEFAULT_OUT())
    return cfg


def save_config(cfg: dict) -> None:
    p = CONFIG_FILE()
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)


def out_dir() -> Path:
    """当前导出目录；不存在就建，建不了退回默认目录。"""
    p = Path(load_config()["out_dir"])
    try:
        p.mkdir(parents=True, exist_ok=True)
        return p
    except OSError:
        d = DEFAULT_OUT()
        d.mkdir(parents=True, exist_ok=True)
        return d


# ---------------------------------------------------------------- 手工命名库
def names_local_file() -> Path:
    return data_path("names_local.json")


def load_local_names() -> dict:
    try:
        d = json.loads(names_local_file().read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(d, dict):
        return {}
    out = {}
    for tid, m in d.items():
        if isinstance(m, dict) and m.get("name"):
            arts = m.get("artists")
            out[str(tid)] = {
                "name": str(m["name"]),
                "artists": [str(a) for a in arts if a] if isinstance(arts, list) else [],
                "album": m.get("album") or None,
            }
    return out


def save_local_names(d: dict) -> None:
    p = names_local_file()
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)


def reset_caches() -> None:
    """设置里改了安装目录后调用：清掉探测缓存，下次重新找。"""
    for fn in (find_node, find_client_lib, find_transport_lib, find_ffmpeg):
        try:
            fn.cache_clear()
        except Exception:
            pass


def soda_status() -> dict:
    """汽水客户端检测结果，给 UI 显示用（不抛异常）。"""
    device = bdms = None
    try:
        device = find_client_lib()
    except Exception:
        device = None
    if device is not None:
        try:
            bdms = find_transport_lib()
        except Exception:
            bdms = None
    root = None
    if device is not None:
        # <root>\resources\app.asar.unpacked\客户端原生模块
        try:
            root = device.parents[2]
        except IndexError:
            root = device.parent
    return {
        "found": device is not None,
        "client_lib": str(device) if device else None,
        "transport_lib": str(bdms) if bdms else None,
        "root": str(root) if root else None,
        "site": SODA_SITE,
    }


def describe() -> dict:
    return {
        "frozen": FROZEN,
        "app_dir": str(APP_DIR),
        "data_dir": str(ensure_data_dir()),
        "cache": str(cache_dir()),
        "cache_exists": cache_dir().is_dir(),
        "soda": soda_status(),
    }
