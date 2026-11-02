# -*- coding: utf-8 -*-
"""档位密钥解析（开源版：接口占位，未包含实现）。

真实实现通过客户端自带的原生模块解出加密资源所需的密钥。
该逻辑与本机已安装客户端强绑定，且属于未公开的私有协议，故不在本仓库内。
"""


def decode_keys(tokens) -> dict:
    raise NotImplementedError("开源版未包含该实现，见 docs/SECURITY.md")


def key_from_token(token: str) -> str | None:
    raise NotImplementedError("开源版未包含该实现，见 docs/SECURITY.md")
