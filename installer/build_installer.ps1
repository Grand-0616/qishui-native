# 汽水音乐原生导出器 —— 生成安装包
# 前置：先跑 `python build.py`（或用 build.py --clean）产生 dist\QishuiNative\；
#      再装 Inno Setup 6（winget install JRSoftware.InnoSetup）。
# 产物：installer\output\QishuiNative-Setup-<版本>.exe

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$dist = Join-Path $root "dist\QishuiNative"

if (-not (Test-Path (Join-Path $dist "QishuiNative.exe"))) {
    throw "未找到 $dist\QishuiNative.exe，请先运行 python build.py"
}

$candidates = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe",
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 5\ISCC.exe")
)
$iscc = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
    $cmd = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($cmd) { $iscc = $cmd.Source }
}
if (-not $iscc) {
    throw "未找到 ISCC.exe。请先安装 Inno Setup 6：winget install JRSoftware.InnoSetup"
}

Write-Host "使用 ISCC: $iscc"
& $iscc (Join-Path $PSScriptRoot "installer.iss")
if ($LASTEXITCODE -ne 0) { throw "ISCC 编译失败，退出码 $LASTEXITCODE" }

$out = Join-Path $PSScriptRoot "output"
Get-ChildItem $out -Filter *.exe | ForEach-Object {
    "生成: $($_.FullName)  $([math]::Round($_.Length/1MB,1)) MB"
}
