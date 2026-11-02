# -*- coding: utf-8 -*-
"""离线自测：KRC 解析 / LRC 生成 / 内嵌标签写入。不需要联网与汽水客户端。

运行：python tests/test_scraper_offline.py
"""
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import krc, tags  # noqa: E402

SAMPLE = "[19962,2279]<0,378,0>笔<378,377,0>锋<755,400,0>纸<1155,400,0>上<1555,400,0>落\n" \
         "[22240,2000]<0,480,0>写<480,360,0>尽 <840,760,0>半<1600,360,0>生<1960,580,0>的<2540,380,0>凉<2920,420,0>薄\n"


def test_parse_krc():
    lines, head = krc.parse_krc(SAMPLE)
    assert len(lines) == 2, lines
    assert lines[0].start == 19962 and lines[0].duration == 2279
    assert lines[0].text.replace(" ", "") == "笔锋纸上落", lines[0].text
    assert len(lines[0].words) == 5
    # 首字相对偏移 0 → 绝对 19962；第二字 378 → 20340
    assert lines[0].words[1][0] == 19962 + 378
    lrc = krc.to_lrc(lines, {"ti": "测试", "ar": "歌手"})
    assert "[ti:测试]" in lrc and "[00:19.96]笔锋纸上落" in lrc, lrc
    enh = krc.to_enhanced_lrc(lines, {})
    assert "<00:19.96>" in enh, enh
    plain = krc.plain_text(lines)
    assert plain.splitlines()[0].replace(" ", "") == "笔锋纸上落"


def test_apply_translation():
    lines, _ = krc.parse_krc(SAMPLE)
    krc.apply_translation(lines, "[00:19.96]A brush tip falls on paper\n[00:22.24]writing\n")
    assert lines[0].translation.startswith("A brush")
    assert "A brush" in krc.to_lrc(lines, {})


def _make_audio(work: Path, ext: str, codec: str) -> Path | None:
    f = work / f"t.{ext}"
    try:
        r = subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
                            "sine=frequency=440:duration=1", "-c:a", codec, str(f)],
                           capture_output=True)
    except FileNotFoundError:
        return None
    return f if r.returncode == 0 and f.is_file() else None


def test_write_tags():
    work = Path(tempfile.mkdtemp(prefix="qstest_"))
    try:
        cover = None
        try:
            from PIL import Image
            import io
            buf = io.BytesIO()
            Image.new("RGB", (300, 300), (30, 90, 160)).save(buf, "JPEG")
            cover = buf.getvalue()
        except Exception:
            pass
        meta = {"title": "测试歌", "artists": "某歌手", "album": "某专辑",
                "date": "2026-01-01", "track_id": "123456"}
        lines, _ = krc.parse_krc(SAMPLE)
        lyric = krc.to_enhanced_lrc(lines, {})
        checked = 0
        for ext, codec in (("flac", "flac"), ("m4a", "aac"), ("mp3", "libmp3lame")):
            f = _make_audio(work, ext, codec)
            if f is None:
                print(f"  (跳过 {ext}：无 ffmpeg)")
                continue
            err = tags.write_tags(f, meta, lyric=lyric, cover=cover)
            assert err is None, (ext, err)
            checked += 1
        # 旁挂
        f = _make_audio(work, "flac", "flac")
        if f:
            lp = tags.write_sidecar_lyric(f, "[00:01.00]hi\n")
            cp = tags.write_sidecar_cover(f, cover) if cover else None
            assert lp and lp.is_file()
            if cover:
                assert cp and cp.is_file()
            checked += 1
        print(f"  已校验 {checked} 个载体")
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    fails = 0
    for fn in (test_parse_krc, test_apply_translation, test_write_tags):
        try:
            fn()
            print(f"[PASS] {fn.__name__}")
        except Exception as e:
            fails += 1
            print(f"[FAIL] {fn.__name__}: {type(e).__name__}: {e}")
    sys.exit(1 if fails else 0)
