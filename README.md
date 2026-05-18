# acrocyte_manufacture

批次顯微鏡影像縫圖 CLI，建構於 [Ashlar](https://github.com/labsyspharm/ashlar)
之上，支援 MetaXpress / MetaMorph 系列檔名格式。

跨平台：macOS、Windows。

## 給使用者

請看 [使用說明-Mac.md](./使用說明-Mac.md) 或 [使用說明-Windows.md](./使用說明-Windows.md)。
第一次使用時跑一次 `setup.sh`（macOS）或 `setup.bat`（Windows）即可。

## 給開發者

```bash
uv sync
uv run stitch <資料夾路徑>           # 短別名
uv run acrocyte-manufacture <資料夾路徑>   # 完整名稱（等效）
```

主要相依：

- `ashlar>=1.17.0`
- `scikit-image>=0.19.3,<0.23`（ashlar 相容上限）
- `tifffile>=2022.7.28,<2025.2.18`（ashlar 相容上限）
- `numpy`、`pandas`、`tqdm`、`networkx`

Python 版本：`3.11`（由 `.python-version` 指定）。
