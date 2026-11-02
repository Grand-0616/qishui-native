# QishuiNative

作者：[@Grand-0616](https://github.com/Grand-0616) · 许可：[MIT](LICENSE)

一个基于 **PySide6** 的 Windows 桌面工具：曲库浏览、模糊搜索、批量导出队列，以及**把歌词与封面写进音频文件**。
本仓库是**开源版**，只包含界面层与通用工具层。

能独立使用的部分：**本地音乐整理**（把散落的歌词 `.lrc/.krc` 与封面图片批量写进 FLAC / M4A / MP3 的标签），
以及曲库浏览、模糊搜索、设置页、打包与安装脚本。

> **重要说明**：与第三方音乐客户端交互、音源获取、加密音频解密、请求签名等实现**未包含**在本仓库内
> （原因与清单见 [docs/SECURITY.md](docs/SECURITY.md)）。因此「导出音频」这条链路在本仓库中是占位实现，
> 点击导出会返回一条说明性错误。界面、搜索、标签/歌词写入、打包与安装脚本都可独立运行与验证。

## 功能

| 部分 | 状态 | 说明 |
| --- | --- | --- |
| 主界面 / 托盘 / 单实例 | ✅ 完整 | PySide6 主窗口、系统托盘、命名互斥锁 |
| 曲库列表与筛选 | ✅ 完整 | 表格、只看可导出、统计栏 |
| 模糊搜索 + 候选下拉 | ✅ 完整 | 分词 + 子串/前缀/子序列 + 拼音（可选 pypinyin） |
| 导出队列与进度 | ✅ 界面完整 | 线程、进度、批量、取消 |
| 音源获取 / 解密 | ⛔ 占位 | 见 `docs/SECURITY.md` |
| 导出后写标签 | ✅ 完整 | FLAC / M4A / MP3 的标题、歌手、专辑、歌词、封面 |
| **本地文件整理** | ✅ 完整 | 扫描目录，把同名歌词/封面批量写进音频标签（工具栏「整理本地文件」） |
| 逐字歌词转 LRC | ✅ 完整 | KRC 解析 → 标准 LRC / 增强 LRC / 纯文本 |
| 封面优化与缓存 | ✅ 完整 | Pillow 缩放、内容寻址缓存 |
| 设置页 / 开机自启 | ✅ 完整 | 含客户端目录探测、官网入口 |
| 打包 / 安装包脚本 | ✅ 完整 | PyInstaller onedir + Inno Setup |

## 快速开始

```powershell
# 1. 依赖（Python 3.10+）
pip install -r requirements.txt

# 2. 可选：放一份演示曲库，界面里就有数据可看
Copy-Item docs\library.example.json data\library.json

# 3. 运行
python app.py
```

放好演示数据后，**取消勾选左侧「只看可导出」** 就能看到曲目列表——示例档位不带密钥，
按默认筛选会被隐藏（这是预期行为）。`data\library.json` 结构见
[docs/library.example.json](docs/library.example.json)（`songs[].gears[]` 里的 `quality` 取
`medium / higher / highest / lossless / spatial / hi_res`）。

## 本地整理怎么用

```
工具栏「整理本地文件」→ 选择一个文件夹 → 确认
```

识别规则：

| 内容 | 认哪些文件 |
| --- | --- |
| 音频 | `.mp3` `.flac` `.m4a` `.aac` `.wav` `.ogg` `.opus` |
| 歌词 | 与音频同名：`歌名.lrc` / `歌名.krc` / `歌名.txt`，或 `歌名.flac.lrc` |
| 封面 | 与音频同名图片，或目录里的 `cover.*` / `folder.*` / `front.*`（jpg/png/webp） |

写入内容：标题、歌手、专辑（已有标签优先，不会被文件名覆盖）、内嵌歌词、内嵌封面
（`METADATA_BLOCK_PICTURE` / `covr` / `APIC`）。**只改标签，不动音频数据**；`.krc` 会自动转成标准 LRC。

## 打包

```powershell
python build.py --clean                # 产物 dist\QishuiNative\QishuiNative.exe
dist\QishuiNative\QishuiNative.exe --selftest   # 退出码 0 = 依赖齐全

# 安装包（需要 Inno Setup 6：winget install JRSoftware.InnoSetup）
powershell -ExecutionPolicy Bypass -File installer\build_installer.ps1
```

## 目录结构

```
qishui-native/
├─ app.py                 入口：单实例锁、应用图标、依赖体检、--selftest
├─ build.py               PyInstaller onedir 打包脚本
├─ make_icon.py           生成 assets/icon.ico
├─ requirements.txt
├─ assets/icon.ico
├─ core/
│  ├─ env.py              路径与外部依赖探测（客户端目录/Node/ffmpeg）、配置读写
│  ├─ proc.py             子进程封装（Windows 下不弹黑框）
│  ├─ library.py          数据模型 + 模糊搜索（数据源为可选的 data/library.json）
│  ├─ exporter.py         命名/索引/选档工具；导出主流程为占位
│  ├─ tags.py             写 FLAC / M4A / MP3 标签与封面
│  ├─ krc.py              逐字歌词解析与 LRC 转换
│  ├─ scraper.py          用「曲目信息」给音频补封面与歌词（依赖 server 层返回的数据）
│  ├─ netease.py          第三方歌词/封面兜底检索
│  ├─ verify.py           ffprobe 校验导出结果
│  ├─ autostart.py        HKCU Run 开机自启
│  ├─ keys.py             ⛔ 接口占位
│  ├─ cenc.py             ⛔ 接口占位
│  ├─ msgbuf.py           ⛔ 接口占位
│  └─ refresher.py        ⛔ 接口占位
├─ ui/                    main_window / settings_dialog / workers / theme
├─ tests/                 离线单测（歌词解析、标签写入）
├─ installer/             installer.iss + build_installer.ps1
└─ docs/                  SECURITY.md、示例数据
```

## 已知限制

- 本仓库的「导出音频」不工作，`export_song()` 直接返回失败原因。
- `Library.refresh()` 读 `data/library.json`；未放文件时界面显示空态提示，这是预期行为。
- 「提取登录凭证」按钮在开源版恒为失败，仅保留交互。

## 许可

MIT，见 [LICENSE](LICENSE)。
