# acrocyte_manufacture 使用說明（macOS）

這份說明假設你**完全沒用過命令列**，每一步都會講清楚。

縫圖工具一共就兩件事要做：

1. **只做一次**：安裝（執行一次啟動腳本，幫你裝好所有東西）。
2. **每次拿到新資料**：開終端機 → 打一行指令 → 把資料夾拖進去 → 按 Enter。

---

## 一、第一次安裝（只需要做一次）

### Step 0：拿到本工具的資料夾

請向工程師索取 `acrocyte_manufacture` 整包資料夾（通常是一個 `.zip` 檔），
解壓縮後放在你電腦上**容易找到的地方**，例如「文件 / Documents」資料夾下。

> 路徑請**不要包含中文字或空白**（例如「我的縫圖工具」就會出問題）。
> 建議直接用 `acrocyte_manufacture` 這個英文名。

---

### Step 1：打開「終端機」

- 按 `⌘ + 空白鍵` 開啟 Spotlight 搜尋
- 輸入「終端機」或「Terminal」
- 按 Enter

會出現一個白色（或黑色）的視窗，可以打字進去。

---

### Step 2：進入 `acrocyte_manufacture` 資料夾

在終端機輸入 `cd ` （**注意 cd 後面有一個空白**），
然後把 Finder 裡的 `acrocyte_manufacture` 資料夾**拖進終端機視窗**，
你會看到完整路徑被自動填上，按 Enter。

例如：

```
cd /Users/yourname/Documents/acrocyte_manufacture
```

---

### Step 3：執行啟動腳本

輸入：

```
bash setup.sh
```

按 Enter。

接下來腳本會自動：

1. **偵測有沒有 `uv`**（Python 套件管理工具），沒有就幫你裝
2. **偵測 / 安裝 Python 3.11**
3. **安裝縫圖需要的所有套件**（ashlar、scikit-image、tifffile、numpy、tqdm）

第一次跑大約需要 **3–10 分鐘**，請耐心等到看到：

```
✓ 安裝完成！
```

如果中途出現紅色錯誤訊息，**請截圖傳給工程師**，不要自己亂試。

---

## 二、每次拿到新資料時：縫圖

### Step 1：打開「終端機」

（同上，⌘ + 空白鍵搜尋「終端機」）

### Step 2：進入 `acrocyte_manufacture` 資料夾

```
cd 
```

（cd 後面空一格，然後把 `acrocyte_manufacture` 資料夾從 Finder 拖進來，按 Enter）

### Step 3：輸入縫圖指令並拖入要縫的資料夾

輸入：

```
uv run stitch 
```

（指令後面**保留一個空白**，**不要按 Enter**）

然後把你要縫的資料夾**從 Finder 拖到終端機視窗**。可以拖：

- **某個盤的資料夾**（例如 `RCE-24W-Sample-V52-Control-G-HT2`）
- **分類資料夾**（例如裡面放好幾盤的 `BF_FITC`）
- **母資料夾**（例如整個 `For Adam`，工具會自動找到底下所有的盤）

你會看到指令變成類似：

```
uv run stitch /Users/yourname/Desktop/今日批次
```

確認沒問題後按 Enter。

---

## 三、一次縫好幾個資料夾（批次）

兩種方式：

### 方式 A：拖多個資料夾

打完 `uv run stitch ` 之後，**依序把每個要縫的資料夾都拖進來**
（每拖一個，再空一格，再拖下一個）：

```
uv run stitch /path/to/A /path/to/B /path/to/C
```

按 Enter，會**一個接一個**依序縫（不會同時跑，避免你的電腦負荷不了）。

### 方式 B：拖一個母資料夾

如果你已經把今天所有 dataset 各自放在子資料夾裡，拖**母資料夾**進去，
工具會自動找到所有子層的盤，每個都縫一遍。

### 開跑前會看到偵測清單

按 Enter 後，工具會先列出找到哪些盤，例如：

```
偵測到 3 個盤：
    1. RCE-24W-Sample-V52-Control-G-HT2
        tile: /Users/yourname/.../HT2/2026-05-08/487/TimePoint_1
    2. RCE-24W-Sample-V52-Control-G-LT3
        tile: ...
    3. RCE-24W-Sample-V52-Control-G-RT3
        tile: ...
```

如果清單錯了（例如盤名怪怪的、或多了不該縫的東西），按 `Control + C` 中止，
然後改拖正確的資料夾再來一次。

### 中途出錯怎麼辦？

批次中如果某個盤失敗，**其他的會繼續跑**，最後會印出一張總表：

```
✓ 成功 2 個   ✗ 失敗 1 個
失敗清單：
  - 20240501-plate04：偵測到 4 張 tile，但檔名不符合 MetaXpress 格式
```

把失敗訊息**截圖給工程師**就好。

---

## 四、縫好的圖在哪？

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

1. 到 <https://fiji.sc/> 點「Download」→ 選 **macOS**
2. 下載到的 `.zip` 解壓後得到 `Fiji.app`
3. 把 `Fiji.app` 拖到「應用程式 / Applications」資料夾
4. 第一次打開若被擋下，到「系統設定 → 隱私權與安全性」按「仍要開啟」

**開縫好的圖**：

- **不要把縫好的圖搬到跟顯微鏡 `.HTD` 檔同一個資料夾**，Bio-Formats 看到 `.HTD` 會誤判成 MetaXpress 原始資料而開不了（Log 會出現 `CellWorxReader ... ArrayIndexOutOfBoundsException`）。留在 `stitched/` 裡就沒事
- 直接把 `.ome.tif` 從 Finder 拖到 Fiji 視窗，或用 `File → Open`（副檔名是 `.ome.tif` Fiji 才會自動用 Bio-Formats 開；如果檔名被改成 `.tif`，請改用 `File → Import → Bio-Formats`）
- 會跳出「Bio-Formats Import Options」對話框，**直接按 OK 即可**（預設值就好）
- 不想每次都跳對話框：Plugins → Bio-Formats → **Bio-Formats Plugins Configuration** → **Formats** 分頁 → 找到 **OME-TIFF** → 勾 **Windowless**。之後拖進去直接開，會沿用最後一次按 OK 的設定。每台電腦設一次
- 第一次打開大圖可能要 5–30 秒讀金字塔，之後縮放就很順

> 進階選項：QuPath（病理影像專用）、napari（Python）也能讀。看個人習慣。

---

## 五、如果有 well 缺檔

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

## 六、常見錯誤

| 現象 | 可能原因 | 怎麼辦 |
|---|---|---|
| `command not found: uv` | 安裝後沒重開終端機 | 關掉終端機重新開一次 |
| `找不到任何 .tif 檔` | 拖錯資料夾，或檔名被改過 | 確認資料夾裡是顯微鏡原始輸出的 `.tif` |
| 跑到一半電腦變很慢 | 縫圖吃很多記憶體，正常 | 不要同時開太多其他程式，耐心等 |
| 跑很久沒反應 | 第一次 `uv sync` 在下載套件 | 等就好，最久不會超過 15 分鐘 |

其他任何錯誤訊息**直接截圖**問工程師，不要自己嘗試修改檔案。

---

## 七、要升級工具時

如果工程師告訴你「有新版本」：

1. 把新的 `acrocyte_manufacture` 資料夾**整包換掉**舊的
2. 在終端機進到資料夾後再跑一次 `bash setup.sh`
3. 完成
