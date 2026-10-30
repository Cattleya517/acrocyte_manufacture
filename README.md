# acrocyte_manufacture

批次顯微鏡影像縫圖 CLI，建構於 [Ashlar](https://github.com/labsyspharm/ashlar)
之上，支援 MetaXpress / MetaMorph 系列檔名格式。

跨平台：macOS、Windows。

## 給使用者

請看 [使用說明-Docker.md](./使用說明-Docker.md)。使用者只需要 Docker Desktop + `docker pull`；
Windows 再從 [Releases](https://github.com/Cattleya517/acrocyte_manufacture/releases/latest) 下載 `stitch.bat`（單一檔案的啟動器，幫拖進來的磁碟機組 `-v`）。
沒有其他安裝方式。

## 給開發者

```bash
uv sync
uv run stitch <資料夾路徑> [-y]        # 短別名；-y 跳過「要縫嗎」確認
uv run acrocyte-manufacture              # 不給路徑 → 互動模式（提示拖資料夾）
```

自我檢查（合成 tile，約 5 秒）：`uv run python test_stitch.py`

Docker（映像檔只有 linux/amd64：numcodecs 0.15 沒有 aarch64 wheel，Apple Silicon 走 Rosetta）：

```bash
docker build --platform linux/amd64 -t ghcr.io/cattleya517/acrocyte-manufacture .
docker run --rm --platform linux/amd64 -v /path/to/plates:/data ghcr.io/cattleya517/acrocyte-manufacture /data
# Linux 主機上輸出檔會是 root 所有，加 --user "$(id -u):$(id -g)"；Docker Desktop 不用。
# 發佈給使用者 docker pull（PAT 需 write:packages 權限；第一次推完到 GitHub Packages 把 visibility 改 Public）：
echo "$GITHUB_PAT" | docker login ghcr.io -u <GitHub 帳號> --password-stdin
docker push ghcr.io/cattleya517/acrocyte-manufacture
# 發版：bump pyproject version → uv lock → commit → build/push latest 與 <ver> 兩個 tag → git tag v<ver>
#       → gh release create v<ver> stitch.bat（使用說明的下載連結指向 releases/latest/download/stitch.bat）
```

主要相依：

- `ashlar>=1.17.0`
- `scikit-image>=0.19.3,<0.23`（ashlar 相容上限）
- `tifffile>=2022.7.28,<2025.2.18`（ashlar 相容上限）
- `numpy`、`tqdm`

Python 版本：`3.11`（由 `.python-version` 指定）。
