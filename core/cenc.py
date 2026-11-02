# -*- coding: utf-8 -*-
"""加密音频容器解析与解密（开源版：接口占位，未包含实现）。

真实实现解析容器头部、取出每帧的加密信息、按密钥逐样本解密并校验帧结构。
故不在此仓库提供。
"""


def parse_bin(path) -> dict:
    raise NotImplementedError("开源版未包含该实现，见 docs/SECURITY.md")


def decrypt_layout(layout, key_hex: str, dst) -> bool:
    raise NotImplementedError("开源版未包含该实现，见 docs/SECURITY.md")


def decrypt_file(src, key_hex: str, dst) -> bool:
    raise NotImplementedError("开源版未包含该实现，见 docs/SECURITY.md")


def probe(layout, key_hex: str, frames: int = 12) -> bool:
    raise NotImplementedError("开源版未包含该实现，见 docs/SECURITY.md")
