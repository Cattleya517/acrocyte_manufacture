# acrocyte_manufacture 使用說明（Docker 版：macOS / Windows 通用）

這份說明假設你**完全沒用過命令列**，每一步都會講清楚。

**不用拿工具資料夾、不用裝 Python**。裝好 Docker Desktop 之後，縫圖就是拖資料夾、按 Enter。

縫圖工具一共就兩件事要做：

1. **只做一次**：安裝 Docker Desktop，下載縫圖映像檔，Windows 再多下載一個 `stitch.bat`。
2. **每次拿到新資料**：Windows 雙擊 `stitch.bat`（macOS 貼一行指令）→ 把資料夾拖進去 → Enter → Enter。

---

## 一、第一次安裝（只需要做一次）

### Step 1：安裝 Docker Desktop

到 <https://www.docker.com/products/docker-desktop/> 下載並安裝。

- **macOS**：有兩個版本。點左上角  → 「關於這台 Mac」：
  看到「晶片 Apple M…」就下載 **Apple Silicon** 版，看到「Intel」就下載 **Intel** 版。
  打開 `.dmg`，把 Docker 拖到「應用程式」。
- **Windows**：下載 `Docker Desktop Installer.exe` 雙擊安裝，保持「Use WSL 2」勾選，裝完**重開機**。

> **Windows 注意**：安裝需要**管理員權限**，並會啟用 WSL 2（Windows 內建的 Linux 子系統）。
> 公司電腦如果被 IT 鎖住，請先找 IT 開通。
> 裝完 Docker Desktop 啟動時如果說 WSL 2 不完整：用**系統管理員**身分開 PowerShell，
> 貼 `wsl --install --no-distribution`，重開機再試。還是不行就是 BIOS 沒開虛擬化，找工程師。

安裝完**打開 Docker Desktop 一次**（之後它會常駐在背景，開機自動啟動）。
第一次會問你要不要登入帳號，**按 Skip 跳過即可**。
等到視窗左下角出現綠色的「Engine running」就可以了。

### Step 2：下載縫圖映像檔

打開終端機（macOS：`⌘ + 空白鍵` 搜「終端機」；Windows：`Win + X` → 「終端機」），
**不用進任何資料夾**，直接貼這行：

```
docker pull ghcr.io/cattleya517/acrocyte-manufacture
```

按 Enter。會下載大約 400–500 MB，幾分鐘。看到 `Status: Downloaded newer image` 就完成了。

如果中途出現紅色錯誤訊息，**請截圖傳給工程師**，不要自己亂試。

### Step 3（只有 Windows）：下載 `stitch.bat` 放桌面

這是一個小啟動器，幫你把拖進來的資料夾所在的磁碟機接給 Docker。下載一次放桌面就好：

<https://github.com/Cattleya517/acrocyte_manufacture/releases/latest/download/stitch.bat>

> 瀏覽器會擋 `.bat`：Edge / Chrome 下載列會說「無法安全下載」，點「⋯」→「**保留**」→「**仍要保留**」。
> 第一次雙擊時 Windows 會跳藍色的 SmartScreen 視窗，點「**其他資訊**」→「**仍要執行**」。
> 之後就不會再問了。

macOS 不需要這一步。

---

## 二、每次拿到新資料時：縫圖

### Windows

1. 雙擊桌面的 `stitch.bat`，會開一個黑色視窗。
2. 看到「把要縫的資料夾拖進這個視窗」，就把資料夾**從檔案總管拖到那個視窗**，按 Enter。
3. 工具會列出偵測到的盤（見下面「開跑前會看到偵測清單」），**再按一次 Enter** 就開始縫。
4. 縫完會印結果和耗時，「按任意鍵關閉此視窗」。

要縫下一批就再雙擊一次。

### macOS

1. 打開終端機（`⌘ + 空白鍵` 搜「終端機」），貼這行按 Enter：

   ```
   docker run -it --rm --platform linux/amd64 -v /Users:/Users -v /Volumes:/Volumes ghcr.io/cattleya517/acrocyte-manufacture
   ```

2. 看到「把要縫的資料夾拖進這個視窗」，就把資料夾**從 Finder 拖到終端機視窗**，按 Enter。
3. 列出偵測到的盤後，**再按一次 Enter** 就開始縫。

> 這行指令每次都一模一樣，建議存在備忘錄裡。

### 可以拖什麼？

- **某個盤的資料夾**（例如 `RCE-24W-Sample-V52-Control-G-HT2`）
- **分類資料夾**（例如裡面放好幾盤的 `BF_FITC`）
- **母資料夾**（例如整個 `For Adam`，工具會自動找到底下所有的盤）
- **一次框選好幾個資料夾一起拖**，會一個接一個依序縫（不會同時跑，避免電腦負荷不了）

> **網路磁碟機**（NAS 對應出來的 Z 槽、`\\server\...`）Docker 讀不到，請先把資料複製到本機。

### 開跑前會看到偵測清單

```
偵測到 3 個盤：
    1. RCE-24W-Sample-V52-Control-G-HT2
        tile: /e/RCE-Cell culture Monitor/.../HT2/2026-05-08/487/TimePoint_1
    2. RCE-24W-Sample-V52-Control-G-LT3
        tile: ...
    3. RCE-24W-Sample-V52-Control-G-RT3
        tile: ...

要縫這 3 個盤嗎？[Y/n]
```

直接按 **Enter** 就開始。清單錯了（盤名怪怪的、多了不該縫的東西）就打 `n` 按 Enter 結束，改拖正確的資料夾再來一次。

> Windows 上路徑會顯示成 `/e/...`（Docker 裡面看到的寫法），就是你的 `E:\...`，正常。

### 中途出錯怎麼辦？

批次中如果某個盤失敗，**其他的會繼續跑**，最後會印出一張總表：

```
批次結果：✓ 成功 2 個   ✗ 失敗 1 個  耗時 12 分 3 秒（46 個 well，平均 15.7 秒/well）
失敗清單：
  - 20240501-plate04：偵測到 4 張 tile，但檔名不符合 MetaXpress 格式
```

把失敗訊息**截圖給工程師**就好。

---

## 三、縫好的圖在哪？

縫好的結果會放在**該盤資料夾下的 `stitched/` 子資料夾**（不是更深的 `TimePoint_1` 裡），
每個 well、每個 channel 一個獨立 TIF：

```
RCE-24W-Sample-V52-Control-G-HT2/
├─ 2026-05-08/...（原本的 tile 結構，沒動）
└─ stitched/                                            ← 新的縫好的圖都在這裡
   ├─ RCE-24W-Sample-V52-Control-G-HT2-A01-TX.ome.tif
   ├─ RCE-24W-Sample-V52-Control-G-HT2-A01-FITC.ome.tif
   ├─ RCE-24W-Sample-V52-Control-G-HT2-A02-TX.ome.tif
   ├─ RCE-24W-Sample-V52-Control-G-HT2-A02-FITC.ome.tif
   └─ ...
```

> Channel 名（`TX`、`FITC`、`TransmittedLight` 等）是來自顯微鏡 metadata 裡的 `_IllumSetting_`，
> 拍攝時設什麼這裡就顯示什麼。

每個 TIF 都會自動寫入：

- `ScanTime`：原始 tile 的拍攝時間
- `StitchTime`：這次縫圖完成的時間

### 用什麼軟體開縫好的 TIF？

**請用 [Fiji](https://fiji.sc/)，不要用原版 ImageJ。**

原版 ImageJ 打開會出現 **「Unsupported format」** 錯誤，這不是檔案壞掉。
因為縫好的 `.ome.tif` 其實是 **OME-TIFF + BigTIFF + 多解析度金字塔**三合一格式：
裡面有完整的顯微鏡 metadata（pixel size、channel 名、拍攝時間），檔案可以超過 4GB，
並內建縮圖快取讓大圖能瞬開。原版 ImageJ 三個都不支援。

**Fiji = ImageJ + 一堆預裝插件**，其中 **Bio-Formats** 這個插件就能讀以上格式。
研究室裡做螢光影像的人幾乎都用 Fiji，不會跟原版 ImageJ 衝突，兩個可以並存。

**安裝 Fiji**：

1. 到 <https://fiji.sc/> 點「Download」→ 選 **macOS** 或 **Windows 64-bit**
2. 下載到的 `.zip` 解壓後得到 `Fiji.app`
3. **macOS**：把 `Fiji.app` 拖到「應用程式 / Applications」。第一次打開若被擋下，到「系統設定 → 隱私權與安全性」按「仍要開啟」
   **Windows**：把整個 `Fiji.app` 資料夾搬到方便的位置（例如 `C:\Fiji.app`），雙擊裡面的 `ImageJ-win64.exe` 啟動

**開縫好的圖**：

- **不要把縫好的圖搬到跟顯微鏡 `.HTD` 檔同一個資料夾**，Bio-Formats 看到 `.HTD` 會誤判成 MetaXpress 原始資料而開不了（Log 會出現 `CellWorxReader ... ArrayIndexOutOfBoundsException`）。留在 `stitched/` 裡就沒事
- 直接把 `.ome.tif` 從 Finder / 檔案總管拖到 Fiji 視窗，或用 `File → Open`（副檔名是 `.ome.tif` Fiji 才會自動用 Bio-Formats 開；如果檔名被改成 `.tif`，請改用 `File → Import → Bio-Formats`）
- 會跳出「Bio-Formats Import Options」對話框，**直接按 OK 即可**（預設值就好）
- 不想每次都跳對話框：Plugins → Bio-Formats → **Bio-Formats Plugins Configuration** → **Formats** 分頁 → 找到 **OME-TIFF** → 勾 **Windowless**。之後拖進去直接開，會沿用最後一次按 OK 的設定。每台電腦設一次
- 第一次打開大圖可能要 5–30 秒讀金字塔，之後縮放就很順

> 進階選項：QuPath（病理影像專用）、napari（Python）也能讀。看個人習慣。

---

## 四、如果有 well 缺檔

如果某個 well 的某個 site 缺了 channel 檔（採集時掉了），整個 well 會被**跳過**並印警告：

```
  → well A02: ⚠ 跳過 — 2 個 site channel 不齊（預期 2）
```

最後總結會列出跳過的 well：

```
  ⚠ 略過 2 個 well（資料不齊）：
      A02: 2 個 site channel 不齊（預期 2）
      D02: 4 個 site channel 不齊（預期 2）
```

其他完整的 well 不受影響，照常輸出。

---

## 五、常見錯誤

| 現象 | 可能原因 | 怎麼辦 |
|---|---|---|
| `command not found: docker` / `無法辨識 'docker'` | Docker Desktop 沒裝好，或裝完沒重開終端機 | 關掉終端機重開；還是不行就重開機 |
| `Cannot connect to the Docker daemon` / `error during connect` | Docker Desktop 沒有在跑 | 打開 Docker Desktop，等左下角「Engine running」再試 |
| `Unable to find image ... locally` 然後開始下載 | 還沒做過 `docker pull` | 等它下載完會自己開始跑，正常 |
| `✗ 略過 ...：路徑不存在` | 資料夾在網路磁碟機，或 macOS 上不在 `/Users`、`/Volumes` 底下 | 把資料複製到本機 / 使用者資料夾再試 |
| `沒有收到輸入。用 Docker 時請在 docker run 加上 -it` | macOS 貼的指令少了 `-it` | 照上面「二、macOS」那行重貼 |
| 雙擊 `stitch.bat` 視窗一閃就關 | Docker Desktop 沒開，或 `.bat` 被瀏覽器改過名 | 先開 Docker Desktop；確認檔名是 `stitch.bat` 不是 `stitch.bat.txt` |
| `WARNING: The requested image's platform (linux/amd64) does not match` | Apple Silicon Mac 用模擬跑，正常 | 不用理它 |
| Apple Silicon Mac 跑特別慢 | 沒開 Rosetta 模擬 | Docker Desktop → Settings → General → 勾「Use Rosetta for x86_64/amd64 emulation」 |
| 跑到一半電腦變很慢，或出現 `Killed` | 縫圖吃很多記憶體 | Docker Desktop → Settings → Resources → Memory 調到 8 GB 以上 |
| 跑很久沒反應 | 第一次在下載映像檔 | 等就好 |
| `TiffFileError: not a TIFF file` | 資料夾在 OneDrive，檔案只是雲端佔位（圖示有雲朵），還沒下載到本機 | 對資料夾按右鍵 →「永遠保留在此裝置上」，等下載完再跑 |

其他任何錯誤訊息**直接截圖**問工程師，不要自己嘗試修改檔案。

---

## 六、要升級工具時

如果工程師告訴你「有新版本」，再貼一次：

```
docker pull ghcr.io/cattleya517/acrocyte-manufacture
```

完成。`stitch.bat` 不用換，它只負責啟動，縫圖程式都在映像檔裡。
