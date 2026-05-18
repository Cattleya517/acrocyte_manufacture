# acrocyte_manufacture — Windows 啟動安裝腳本
# 用法（推薦）：在這個資料夾上按右鍵，點「在終端開啟」(Windows 11) 後執行
#     .\setup.ps1
# 若被執行原則擋住，改用：
#     powershell -ExecutionPolicy Bypass -File .\setup.ps1
# 或者雙擊本資料夾內的 setup.bat（會自動繞過執行原則）

#Requires -Version 5
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# 強制 console 輸出用 UTF-8（避免 Write-Host 中文亂碼）
try { [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new() } catch {}

# 切換到腳本所在目錄
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

function Write-Step($msg)    { Write-Host "→ $msg" -ForegroundColor Yellow }
function Write-OK($msg)      { Write-Host "✓ $msg" -ForegroundColor Green }
function Write-Title($msg)   { Write-Host $msg -ForegroundColor White }
function Write-ErrLine($msg) { Write-Host $msg -ForegroundColor Red }

Write-Title "=== acrocyte_manufacture 啟動安裝 ==="
Write-Host ""

# ---------------------------------------------------------------------------
# 1. 偵測 / 安裝 uv
# ---------------------------------------------------------------------------
# uv 安裝後預設位置是 %USERPROFILE%\.local\bin\uv.exe —— 先確保這個路徑在 PATH
$UvBin = Join-Path $HOME ".local\bin"
if ($env:PATH -notlike "*$UvBin*") {
    $env:PATH = "$UvBin;$env:PATH"
}

if (Get-Command uv -ErrorAction SilentlyContinue) {
    $uvVer = (uv --version) -join ""
    Write-OK "偵測到 uv ($uvVer)"
}
else {
    Write-Step "偵測不到 uv，開始安裝..."
    try {
        Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    }
    catch {
        Write-ErrLine "錯誤：uv 下載/安裝失敗。請檢查網路連線後重試。"
        Write-ErrLine $_.Exception.Message
        exit 1
    }

    # uv 安裝腳本不會立刻把 PATH 注入到當前 PowerShell session，強制加入
    if ($env:PATH -notlike "*$UvBin*") {
        $env:PATH = "$UvBin;$env:PATH"
    }

    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Write-ErrLine "錯誤：uv 安裝完成但仍找不到指令，請關閉並重開 PowerShell 後再執行一次。"
        exit 1
    }
    $uvVer = (uv --version) -join ""
    Write-OK "uv 安裝完成 ($uvVer)"
}

Write-Host ""

# ---------------------------------------------------------------------------
# 2. 安裝指定版本的 Python（由 .python-version 決定）
# ---------------------------------------------------------------------------
$PyVersionFile = Join-Path $ScriptDir ".python-version"
if (Test-Path $PyVersionFile) {
    $PythonVersion = (Get-Content $PyVersionFile -Raw).Trim()
} else {
    $PythonVersion = "3.11"
}
Write-Step "安裝 Python $PythonVersion ..."
uv python install $PythonVersion
Write-OK "Python $PythonVersion 就緒"
Write-Host ""

# ---------------------------------------------------------------------------
# 3. 安裝相依套件（ashlar、scikit-image、tifffile、numpy、pandas、tqdm、networkx）
# ---------------------------------------------------------------------------
Write-Step "安裝相依套件（首次執行可能需要幾分鐘）..."
uv sync
Write-OK "相依套件安裝完成"
Write-Host ""

# ---------------------------------------------------------------------------
# 完成訊息
# ---------------------------------------------------------------------------
Write-Host "✓ 安裝完成！" -ForegroundColor Green
Write-Host ""
Write-Host "縫圖指令："
Write-Host "  uv run stitch  " -NoNewline
Write-Host "  ← 後面空一格，再把要縫的資料夾拖進視窗，按 Enter"
Write-Host ""
Write-Host "詳細用法請看「使用說明.md」。"
