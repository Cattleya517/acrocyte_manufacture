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

`uv run python test_stitch.py` is the only automated check: it writes synthetic MetaMorph
tiles (2×2 grid, 2 channels, one incomplete well), stitches them, and asserts the mosaic
reproduces the source image and ScanTime/StitchTime landed in the OME-XML. Run it after any
change to the three modules below. Real-data verification is still end-to-end on a tile folder.

Docker: see README (build is `--platform linux/amd64` only; publish target `ghcr.io/cattleya517/acrocyte-manufacture`). User guides mount `/Users` + `/Volumes` (Mac) or `C:\` at `/c` (Windows) so dragged paths pass straight through; `cli.main` maps `C:\...` to `/c/...` when the literal path doesn't exist.

## Architecture

Three layers, top-down:

1. **`cli.py`** — argparse entry, plate discovery (`find_plates`), sequential batch loop, per-channel output, OME-XML metadata injection, human-readable failure summary.
2. **`ashlar_adapter.py`** — `FileSeriesReader2` / `FileSeriesMetadata2`: ashlar `PlateReader`/`PlateMetadata` subclasses over the site list from `scan()`.
3. **`metamorphtiff.py`** — `scan(path)`: regex-matches filenames against `MD_PATTERN`, reads MetaMorph `PlaneInfo` (plus the `DateTime` tag) from each TIFF's `ImageDescription`, assigns series indices by binning stage positions in raster order (not from filename, not from a sqrt() forced grid). Returns plain lists: `sites` (one dict per stage position with `channels`/`paths` tuples in rank order) and `plates` (`[(plate_name, [(well_name, [site_idx...])])]`). No pandas — it was only ever a grouped dict-of-tuples, and dropping it keeps the Docker image and startup smaller.

The `_RANK` table in `metamorphtiff.py` only orders channels within a site (DAPI before FITC). **It is NOT used to rename output files** — `cli.py` writes the raw `_IllumSetting_` string from TIFF metadata directly into the filename (so `FITC` stays `FITC`, not `CD45`). Don't reintroduce the lab-convention rename without an explicit request — earlier versions did and it confused users when FITC stained something other than CD45.

### Things future-you will trip over

- **`jnius` / `jnius_config` are mocked in `cli.py` before importing `ashlar.reg`.** Ashlar 1.20 imports them at module load and *also calls into them at module load* (`jnius_config.vm_running`, `jnius.autoclass(...)`, `DebugTools.setRootLevel(...)`), even though we never use BioFormats for plain TIFF. Without the mock the import chain calls `jnius.env.get_jdk_home()` which raises `Exception('Unable to find JAVA_HOME')` on machines without a JDK — i.e. every fresh Windows install. The mock is a single `_Stub` object whose `__call__` and `__getattr__` both return self, so arbitrary chains (`DebugTools.setRootLevel("ERROR")`) and truthy reads (`jnius_config.vm_running`) succeed without a JVM. Order matters — the `sys.modules.setdefault(...)` calls must be above `from ashlar.reg import ...`. (Earlier ashlar versions used `javabridge` / `bioformats` directly; if you ever upgrade and see those names back in tracebacks, mock them the same way.)

- **Four hard version pins in `pyproject.toml`, all for ashlar compatibility.** Don't loosen any without rerunning a full stitch on real data.
  - `scikit-image>=0.19.3,<0.23` — 0.23 lazy-loading breaks ashlar import. Mirrors acrocyte main repo.
  - `tifffile>=2022.7.28,<2025.2.18` — newer versions changed a resolution-param API ashlar patches against.
  - `numpy>=1.24,<2.0` — scikit-image 0.22's compiled wheels target the numpy 1.x ABI; numpy 2 crashes with `numpy.dtype size changed` at `skimage._shared.geometry` import.
  - `zarr>=2.18,<3` — ashlar 1.20's `PyramidWriter` does `zarr.open(tiff.aszarr(...))`. zarr 3.x's `make_store` no longer accepts a `ZarrTiffStore`, so the pyramid step fails after a full mosaic merge with `TypeError: Unsupported type for store_like: 'ZarrTiffStore'`.

- **`metadata.num_channels` is the max channel count across the plate, not the first site's.** Acquisition sometimes drops a channel at a single site (a well of 25 sites with 24 having both channels and 1 having only one). A short `paths` tuple later crashes deep in `PyramidWriter.run()` with `IndexError: tuple index out of range` inside `assemble_channel`. `cli.py` validates per-well that every site has the full tuple — incomplete wells are skipped with a printed warning, complete wells still process. ashlar itself reads `metadata.num_channels` inside `Mosaic`, so the adapter property must agree with what the CLI iterates.

- **Per-channel output is `Mosaic(channels=[c])` in a loop**, not `PyramidWriter([mosaic1, mosaic2, ...])`. The latter would produce a single multi-channel OME-TIFF; we want one file per channel, named `{dataset}-{channel_title}.tif`. Memory-wise the loop is also better — ashlar holds at most one channel's worth of pixels.

- **`ScanTime` / `StitchTime` are injected by string-replacing `</OME>` in the OME-XML ImageDescription** of the first IFD, via `tifffile.tiffcomment()`. Not a proper XML parse. Works because ashlar's OME-XML output is stable; if it ever stops working, switch to ElementTree. Failure is silent on purpose — metadata is nice-to-have, never blocks the output. **Important encoding caveat:** TIFF's ImageDescription is an ASCII tag, but ashlar writes `PhysicalSizeXUnit="µm"` (non-ASCII `\xb5`). Writing it back as-is raises `UnicodeEncodeError` deep inside `tifffile.overwrite`, which our `try/except: pass` would silently swallow — leaving every output without ScanTime/StitchTime. The fix is `desc.encode("ascii", errors="xmlcharrefreplace").decode("ascii")` before the write, which turns `µ` into `&#181;`. Don't remove that escape.

- **Tile series indices come from stage positions, not filenames.** `scan()` bins stage position (microns/delta from PlaneInfo) to 10 px and sorts `(plate, well, bin, channel rank)`; each bin is one series, in raster order. Side effect: filename-only assumptions from ashlar.sh (`_A01_s##_w#`, forced square grid) do not apply here — non-square grids and arbitrary well codes work automatically.

- **`MD_PATTERN`** is intentionally loose: `r"(?P<plate_name>.+)_(?P<well_name>[A-Z]\d{2})_.+\.tiff?$"`. Series and channel are *not* captured from the filename — only used to filter what to scan. Real series/channel are derived from PlaneInfo metadata.

- **Plate discovery (`find_plates`)** walks the input with `os.walk`, stops descending at the first folder containing `_<well>_` TIFs (the tile leaf), then walks back up past "noise" folder names (`TimePoint_N`, `YYYY-MM-DD`, bare numbers) to find the plate folder, clamped at the input root. Outputs go next to the plate folder, not the leaf.

- **Sequential by design.** No `--workers` flag. Parallel stitching of multiple datasets risks OOM because each `EdgeAligner` loads all DAPI tiles for one dataset into memory. Add concurrency only after measuring real footprints. The only in-scope I/O cost is the serial metadata pass over every tile header in `scan()`; thread it only if a NAS measurement says so — alignment and pyramid writing dominate everything else.

- **Errors meant for users are `ValueError`s with zh-TW messages** raised in `scan()`; `cli._human_error` passes those through verbatim and prefixes anything else with the exception type.

## Distribution model

Users get the whole repo (zip from Releases, or `git clone`), run the setup script once, then `uv run acrocyte-manufacture` from inside the repo. There is no `uv tool install`, no pip-publish, no PyInstaller / Electron packaging. The end-user-facing docs are **`使用說明-Docker.md`** (Docker Desktop + `docker pull`, both OSes; the intended future sole path) and the older per-OS **`使用說明-Mac.md`** / **`使用說明-Windows.md`** (Traditional Chinese, assume zero CLI literacy). `README.md` is for developers.

Upgrades: replace the repo folder (or `git pull`), re-run setup. `uv sync` is idempotent.
