# -*- coding: utf-8 -*-
"""导出后校验：ffprobe 能否识别 + 时长是否对得上。

校验设计为三态（与旧项目经验一致，但封装成 Enum 式返回）：
  True  —— ffprobe 成功识别且时长接近
  False —— ffprobe 明确报错/无音轨
  None  —— 环境无 ffmpeg / 超时等，无法判定（不能当失败）
"""
from __future__ import annotations

import json
import subprocess

from . import proc as procmod
from pathlib import Path

from . import env


class Verdict:
    OK = True
    BAD = False
    UNKNOWN = None


def probe_duration(ffprobe: Path, path: Path, timeout: int = 20):
    try:
        proc = procmod.run(
            [str(ffprobe), "-v", "error", "-show_entries", "format=duration",
             "-of", "json", str(path)],
            capture_output=True, timeout=timeout,
        )
        if proc.returncode != 0:
            return False, None
        data = json.loads(proc.stdout.decode("utf-8", "replace") or "{}")
        dur = float(data.get("format", {}).get("duration", 0) or 0)
        if dur <= 0:
            return False, None
        return True, dur
    except Exception:
        return None, None


def verify(path: Path, expected_seconds: float | None = None) -> dict:
    """返回 {verdict: True/False/None, duration, reason}。"""
    ffprobe = env.find_ffmpeg("ffprobe.exe")
    if not ffprobe or not ffprobe.is_file():
        return {"verdict": Verdict.UNKNOWN, "duration": None,
                "reason": "未找到 ffprobe，跳过时长校验"}
    ok, dur = probe_duration(ffprobe, path)
    if ok is None:
        return {"verdict": Verdict.UNKNOWN, "duration": None, "reason": "ffprobe 超时/异常"}
    if not ok:
        return {"verdict": Verdict.BAD, "duration": None, "reason": "ffprobe 无法识别或无可播放音轨"}
    if expected_seconds and dur:
        if expected_seconds > 5 and dur < expected_seconds * 0.5:
            return {"verdict": Verdict.BAD, "duration": dur,
                    "reason": f"时长异常：{dur:.1f}s / 期望 {expected_seconds:.1f}s"}
    return {"verdict": Verdict.OK, "duration": dur, "reason": "校验通过"}
