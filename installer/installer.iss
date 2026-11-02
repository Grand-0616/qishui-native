; 汽水音乐原生导出器 —— Inno Setup 安装包脚本
; 用法：安装 Inno Setup 6 后，运行 build_installer.ps1（或右键本文件 Compile）
; 产物：installer\output\QishuiNative-Setup-<版本>.exe

#define AppName "汽水音乐原生导出器"
#define AppVer "1.0.0"
#define AppExe "QishuiNative.exe"
#define AppPublisher "local"
#define SrcDir "..\dist\QishuiNative"

[Setup]
AppId={{B7C41E52-9C1D-4F6B-8A03-2E0D5F1C7A44}
AppName={#AppName}
AppVersion={#AppVer}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\QishuiNative
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; 按用户安装，不需要管理员权限
PrivilegesRequired=lowest
OutputDir=output
OutputBaseFilename=QishuiNative-Setup-{#AppVer}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
; selftest.txt 是构建期自检输出，不打进安装包
Source: "{#SrcDir}\*"; DestDir: "{app}"; Excludes: "selftest.txt"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\卸载 {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
