# 范围说明 / Scope

本仓库是**界面与工具层**的开源版本。下列能力属于未公开的私有实现，**未包含**在仓库内，
相关文件保留了函数签名与说明，调用时会抛 `NotImplementedError` 或返回说明性失败。

## 未包含的模块

| 文件 | 原本职责 | 现在的状态 |
| --- | --- | --- |
| `core/keys.py` | 从本机客户端的原生模块解出音频密钥 | 占位，抛 `NotImplementedError` |
| `core/cenc.py` | 解析加密音频容器、按密钥逐帧解密 | 占位，抛 `NotImplementedError` |
| `core/msgbuf.py` | 解析客户端缓存的二进制索引，重建「曲目 → 档位」 | 占位，抛 `NotImplementedError` |
| `core/refresher.py` | 向服务端请求曲目详情（音源地址 / 加密参数 / 签名） | 占位，`fetch_full()` 等抛 `NotImplementedError` |
| `core/exporter.py` | 上述模块的编排：取源 → 解密 → 封装 → 落盘 | 保留命名/索引/选档工具，`export_song()` 返回失败 |

## 为什么移除

1. 这些实现与某个第三方客户端的具体版本、私有协议、私有签名算法强绑定，公开会直接暴露其内部接口细节。
2. 它们依赖本机已安装的客户端资源文件，脱离该环境没有可复现的意义。
3. 仓库定位是「桌面端工程实践示例」：PySide6 的窗口/托盘/线程、模糊搜索打分、音频标签与歌词写入、
   打包与安装脚本。这些都可以独立阅读、运行和验证。

## 保留下来的部分为什么可以公开

- `core/tags.py`、`core/krc.py`：只做「文本解析 + 写标准音频标签」，是公开格式（Vorbis comment、
  ID3v2、MP4 atom、LRC）的通用读写。
- `core/env.py`：只是找路径与读写 JSON 配置。
- `core/proc.py`、`core/autostart.py`、`core/verify.py`：进程封装、注册表 Run 项、ffprobe 校验。
- `ui/`：纯界面与线程调度。
- `core/netease.py`：第三方公开检索接口的查询封装（带请求节流，仅作兜底）。

## 若你要在自己的环境中补全

在 `core/` 下按 `docs/` 的说明实现对应函数即可，`exporter.export_song()` 期望的返回值是
`ExportResult(ok, quality, path, reason, scrape)`。仓库不提供这些实现，也不接受相关 PR。

## 隐私

仓库内不含：登录凭证、Cookie、导出记录、用户目录路径、音频文件、封面缓存、
第三方客户端的解包源码。`.gitignore` 已覆盖这些路径，提交前请再检查一次 `git status`。
