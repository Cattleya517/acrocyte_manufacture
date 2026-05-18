# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Batch image-stitching CLI built on [Ashlar](https://github.com/labsyspharm/ashlar) for MetaXpress / MetaMorph TIFF tiles. Distributed as a uv-managed Python project that colleagues install with one script and run from a terminal. Intended replacement for `acrocyte_simple-stitch-app` (Electron+PyInstaller desktop app — too painful to package).

The source for the stitching adapter classes was copied and stripped down from `../acrocyte_simple-stitch-app/stitcher/`. The original ashlar.sh bash pipeline in `../acrocyte/bin/ashlar.sh` is *not* the reference — Simple Stitch's `runner.py` / `ashlar_adapter.py` are.

## Commands

```bash
uv sync                                          # install/update all deps
uv run acrocyte-manufacture <tile_dir> [...]     # stitch one or more datasets
uv run acrocyte-manufacture --version
uv run python -m acrocyte_manufacture.cli ...    # equivalent, useful for debugging
```

First-time end-user setup (also valid for a fresh dev checkout):

- macOS: `bash setup.sh`
- Windows: double-click `setup.bat` (wraps `setup.ps1` with `-ExecutionPolicy Bypass`)

The setup scripts (a) install `uv` via the official one-liner if missing, (b) prepend `~/.local/bin` to PATH for the current shell session — needed so the just-installed uv is findable in the same script — (c) `uv python install` the version from `.python-version`, (d) `uv sync`.

No test suite, no CI. Verification is end-to-end: run the CLI against a real tile folder.

## Architecture

Three layers, top-down:

1. **`cli.py`** — argparse entry, path classification, sequential batch loop, per-channel output, OME-XML metadata injection, human-readable failure summary.
2. **`ashlar_adapter.py`** — `FileSeriesReader2` / `FileSeriesMetadata2`: ashlar `PlateReader`/`PlateMetadata` subclasses that bridge our DataFrame-based file index to ashlar's API.
3. **`metamorphtiff.py`** — `MetaMorphTIFFHelper`: scans a directory, regex-matches filenames against `MD_PATTERN`, reads MetaMorph `PlaneInfo` from each TIFF's `ImageDescription`, assigns series indices by binning stage positions in raster order (not from filename, not from a sqrt() forced grid).

`_channelinfo.py` is a tiny lookup table over MetaMorph channel names. **It is NOT used to rename output files** — `cli.py` writes the raw `_IllumSetting_` string from TIFF metadata directly into the filename (so `FITC` stays `FITC`, not `CD45`). The lookup is kept only for two side uses: `name_to_rank` orders channels within a tile position (so DAPI sorts before FITC) in `metamorphtiff._sort_raster_order`, and `name_to_color` fills in a default colour in `FileSeriesMetadata2.channels` (cosmetic, never written to disk). Don't reintroduce the lab-convention rename without an explicit request — earlier versions did and it confused users when FITC stained something other than CD45.

### Things future-you will trip over

- **`jnius` / `jnius_config` are mocked in `cli.py` before importing `ashlar.reg`.** Ashlar 1.20 imports them at module load and *also calls into them at module load* (`jnius_config.vm_running`, `jnius.autoclass(...)`, `DebugTools.setRootLevel(...)`), even though we never use BioFormats for plain TIFF. Without the mock the import chain calls `jnius.env.get_jdk_home()` which raises `Exception('Unable to find JAVA_HOME')` on machines without a JDK — i.e. every fresh Windows install. The mock is a single `_Stub` object whose `__call__` and `__getattr__` both return self, so arbitrary chains (`DebugTools.setRootLevel("ERROR")`) and truthy reads (`jnius_config.vm_running`) succeed without a JVM. Order matters — the `sys.modules.setdefault(...)` calls must be above `from ashlar.reg import ...`. (Earlier ashlar versions used `javabridge` / `bioformats` directly; if you ever upgrade and see those names back in tracebacks, mock them the same way.)

- **Four hard version pins in `pyproject.toml`, all for ashlar compatibility.** Don't loosen any without rerunning a full stitch on real data.
  - `scikit-image>=0.19.3,<0.23` — 0.23 lazy-loading breaks ashlar import. Mirrors acrocyte main repo.
  - `tifffile>=2022.7.28,<2025.2.18` — newer versions changed a resolution-param API ashlar patches against.
  - `numpy>=1.24,<2.0` — scikit-image 0.22's compiled wheels target the numpy 1.x ABI; numpy 2 crashes with `numpy.dtype size changed` at `skimage._shared.geometry` import.
  - `zarr>=2.18,<3` — ashlar 1.20's `PyramidWriter` does `zarr.open(tiff.aszarr(...))`. zarr 3.x's `make_store` no longer accepts a `ZarrTiffStore`, so the pyramid step fails after a full mosaic merge with `TypeError: Unsupported type for store_like: 'ZarrTiffStore'`.

- **`n_channels` is the max channel count across the plate, not `df.iloc[0]`.** Acquisition sometimes drops a channel at a single site (a well of 25 sites with 24 having both channels and 1 having only one). The DataFrame stores `file_path` as a tuple per row; a short tuple later crashes deep in `PyramidWriter.run()` with `IndexError: tuple index out of range` inside `assemble_channel`. We compute `max(len(fp) ...)` and then validate per-well that every site has the full tuple — incomplete wells are skipped with a printed warning, complete wells still process. The first-row assumption was the original bug.

- **Per-channel output is `Mosaic(channels=[c])` in a loop**, not `PyramidWriter([mosaic1, mosaic2, ...])`. The latter would produce a single multi-channel OME-TIFF; we want one file per channel, named `{dataset}-{channel_title}.tif`. Memory-wise the loop is also better — ashlar holds at most one channel's worth of pixels.

- **`ScanTime` / `StitchTime` are injected by string-replacing `</OME>` in the OME-XML ImageDescription** of the first IFD, via `tifffile.tiffcomment()`. Not a proper XML parse. Works because ashlar's OME-XML output is stable; if it ever stops working, switch to ElementTree. Failure is silent on purpose — metadata is nice-to-have, never blocks the output. **Important encoding caveat:** TIFF's ImageDescription is an ASCII tag, but ashlar writes `PhysicalSizeXUnit="µm"` (non-ASCII `\xb5`). Writing it back as-is raises `UnicodeEncodeError` deep inside `tifffile.overwrite`, which our `try/except: pass` would silently swallow — leaving every output without ScanTime/StitchTime. The fix is `desc.encode("ascii", errors="xmlcharrefreplace").decode("ascii")` before the write, which turns `µ` into `&#181;`. Don't remove that escape.

- **Tile series indices come from stage positions, not filenames.** `_sort_raster_order` bins `tile_position` (microns/delta from PlaneInfo) by tolerance and assigns series in raster order. Side effect: filename-only assumptions from ashlar.sh (`_A01_s##_w#`, forced square grid) do not apply here — non-square grids and arbitrary well codes work automatically.

- **`MD_PATTERN`** is intentionally loose: `r"(?P<plate_name>.+)_(?P<well_name>[A-Z]\d{2})_.+\.tiff?"`. Series and channel are *not* captured from the filename — only used to filter what to scan. Real series/channel are derived from PlaneInfo metadata.

- **Input classification (`classify_input`)** treats a directory as:
  - `dataset` if it directly contains `*.tif` / `*.tiff`
  - `batch` if it has no TIFs but at least one subdirectory does (one level deep only)
  - `empty` otherwise — skipped with a warning

- **Sequential by design.** No `--workers` flag. Parallel stitching of multiple datasets risks OOM because each `EdgeAligner` loads all DAPI tiles for one dataset into memory. Add concurrency only after measuring real footprints.

## Distribution model

Users get the whole repo (zip from Releases, or `git clone`), run the setup script once, then `uv run acrocyte-manufacture` from inside the repo. There is no `uv tool install`, no pip-publish, no PyInstaller / Electron packaging. The end-user-facing doc is split per OS: **`使用說明-Mac.md`** and **`使用說明-Windows.md`** (Traditional Chinese, assumes zero CLI literacy). `README.md` is for developers.

Upgrades: replace the repo folder (or `git pull`), re-run setup. `uv sync` is idempotent.
