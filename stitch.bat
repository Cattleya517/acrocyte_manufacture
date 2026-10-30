<# : batch portion
@echo off
REM Double-click this file. PowerShell below re-reads this same file as UTF-8 and runs the part after #>.
chcp 65001 >nul
set "STITCH_SELF=%~f0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-Expression ([IO.File]::ReadAllText($env:STITCH_SELF, [Text.Encoding]::UTF8))"
echo.
echo 按任意鍵關閉此視窗...
pause >nul
exit /b
#>
# acrocyte_manufacture — Windows 縫圖啟動器（單一檔案，放桌面雙擊）
# 做的事：收你拖進來的資料夾 → 看是哪個磁碟機 → 掛進 Docker → 啟動縫圖。
# 縫圖程式本身在 Docker 映像檔裡，升級只要 docker pull，這個檔不用換。
try { [Console]::OutputEncoding = [Text.UTF8Encoding]::new(); [Console]::InputEncoding = [Text.UTF8Encoding]::new() } catch {}
$image = "ghcr.io/cattleya517/acrocyte-manufacture"

Write-Host "=== acrocyte_manufacture 縫圖 ===" -ForegroundColor White
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "找不到 docker 指令。請先安裝 Docker Desktop 並重開機。" -ForegroundColor Red; exit 1
}
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker Desktop 沒有在跑。請先打開 Docker Desktop，等左下角出現「Engine running」再雙擊一次。" -ForegroundColor Red; exit 1
}

Write-Host "把要縫的資料夾拖進這個視窗（可以一次拖多個），然後按 Enter："
$line = Read-Host ">"
# 拖進來的樣子可能是  C:\a  或  "C:\a b"  或  & 'C:\a b'  ，一次多個就是空白分隔。
$line = $line -replace '^\s*&\s*', ''
$paths = @()
foreach ($m in [regex]::Matches($line, '''([^'']*)''|"([^"]*)"|(\S+)')) {
    $p = @($m.Groups[1].Value, $m.Groups[2].Value, $m.Groups[3].Value) | Where-Object { $_ } | Select-Object -First 1
    if ($p) { $paths += $p }
}
if ($paths.Count -eq 0) { Write-Host "沒有收到路徑。"; exit 1 }

# 每個用到的磁碟機各掛一次：E:\... → -v E:\:/e，容器裡會看成 /e/...
$drives = @($paths | ForEach-Object { if ($_ -match '^([A-Za-z]):') { $Matches[1].ToLower() } } | Sort-Object -Unique)
if ($drives.Count -eq 0) {
    Write-Host "路徑要以磁碟機代號開頭（例如 C:\ 或 E:\）。網路路徑（\\server\...）不支援，請先把資料複製到本機。" -ForegroundColor Red; exit 1
}
$vols = @()
foreach ($d in $drives) { $vols += "-v"; $vols += "$($d.ToUpper()):\:/$d" }

docker run -it --rm @vols $image @paths
exit $LASTEXITCODE
