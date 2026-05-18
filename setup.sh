#!/bin/bash
# acrocyte_manufacture — macOS / Linux 啟動安裝腳本
# 用法：在 Terminal 切換到此資料夾後執行 `bash setup.sh`
#       或直接 `./setup.sh`（若已 chmod +x）

set -e

# 切換到腳本所在目錄（讓使用者從哪裡呼叫都不會出錯）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

BOLD=$'\033[1m'
GREEN=$'\033[32m'
YELLOW=$'\033[33m'
RED=$'\033[31m'
RESET=$'\033[0m'

echo "${BOLD}=== acrocyte_manufacture 啟動安裝 ===${RESET}"
echo ""

# ---------------------------------------------------------------------------
# 1. 偵測 / 安裝 uv
# ---------------------------------------------------------------------------
# uv 安裝後預設位置是 $HOME/.local/bin/uv —— 確保這個路徑也在 PATH 裡
export PATH="$HOME/.local/bin:$PATH"

if command -v uv &> /dev/null; then
    echo "${GREEN}✓${RESET} 偵測到 uv ($(uv --version))"
else
    echo "${YELLOW}→${RESET} 偵測不到 uv，開始安裝..."
    if ! command -v curl &> /dev/null; then
        echo "${RED}錯誤：${RESET}系統內找不到 curl，請先安裝 curl 再執行此腳本。" >&2
        exit 1
    fi
    curl -LsSf https://astral.sh/uv/install.sh | sh

    # uv 安裝腳本會把 binary 放到 $HOME/.local/bin，但不會立即影響當前 shell。
    # 強制把它加進 PATH 讓接下來的 uv 指令能找到。
    export PATH="$HOME/.local/bin:$PATH"

    if ! command -v uv &> /dev/null; then
        echo "${RED}錯誤：${RESET}uv 安裝完成但仍找不到指令，請關閉並重開 Terminal 後再試一次。" >&2
        exit 1
    fi
    echo "${GREEN}✓${RESET} uv 安裝完成 ($(uv --version))"
fi

echo ""

# ---------------------------------------------------------------------------
# 2. 安裝指定版本的 Python（由 .python-version 決定）
# ---------------------------------------------------------------------------
PYTHON_VERSION="$(cat "$SCRIPT_DIR/.python-version" 2>/dev/null || echo "3.11")"
echo "${YELLOW}→${RESET} 安裝 Python ${PYTHON_VERSION} ..."
uv python install "$PYTHON_VERSION"
echo "${GREEN}✓${RESET} Python ${PYTHON_VERSION} 就緒"
echo ""

# ---------------------------------------------------------------------------
# 3. 安裝相依套件（ashlar、scikit-image、tifffile、numpy、pandas、tqdm、networkx）
# ---------------------------------------------------------------------------
echo "${YELLOW}→${RESET} 安裝相依套件（首次執行可能需要幾分鐘）..."
uv sync
echo "${GREEN}✓${RESET} 相依套件安裝完成"
echo ""

# ---------------------------------------------------------------------------
# 完成訊息
# ---------------------------------------------------------------------------
echo "${BOLD}${GREEN}✓ 安裝完成！${RESET}"
echo ""
echo "縫圖指令："
echo "  ${BOLD}uv run stitch${RESET}  ← 後面空一格，再把要縫的資料夾拖進視窗，按 Enter"
echo ""
echo "詳細用法請看「使用說明.md」。"
