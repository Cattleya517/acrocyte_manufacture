"""acrocyte-manufacture CLI: batch stitching of MetaXpress TIFF tiles."""

# Mock jnius / jnius_config BEFORE importing ashlar — ashlar.reg imports
# them at module load (and calls into them: `jnius_config.vm_running`,
# `jnius.autoclass(...)`, `DebugTools.setRootLevel(...)`) but we only
# ever read plain TIFFs, so the JVM is dead weight that breaks Windows
# installs where no JDK is present.
import sys
import time


class _Stub:
    # Any attribute access or call returns self, so chained calls like
    # `DebugTools.setRootLevel("ERROR")` and truthy reads like
    # `jnius_config.vm_running` both succeed without a JVM.
    def __call__(self, *a, **kw): return self
    def __getattr__(self, name): return self


_stub = _Stub()
sys.modules.setdefault("jnius", _stub)
sys.modules.setdefault("jnius_config", _stub)

import argparse
import datetime
import logging
import os
import re
import traceback
import warnings
from importlib.metadata import version
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)
logging.disable(logging.WARNING)

import tifffile
from ashlar.reg import EdgeAligner, Mosaic, PyramidWriter

from .ashlar_adapter import FileSeriesReader2


# ---------------------------------------------------------------------------
# Plate discovery
# ---------------------------------------------------------------------------
# MetaXpress's deep layout looks like:
#   <plate>/<scan-date>/<run-id>/TimePoint_N/*.tif
# We walk up from the tile folder, skipping these noise levels, to find the
# plate name. The plate is the first ancestor whose name doesn't match a
# noise pattern.
_NOISE_RE = re.compile(r"^(TimePoint_\d+|\d{4}-\d{2}-\d{2}|\d+)$")

# Tile filenames must contain "_<well>_" (e.g. _A01_, _H12_). Our own output
# files use "-" separators and therefore won't match — important when re-running
# in a plate folder that already contains a previous stitch.
_WELL_RE = re.compile(r"_[A-Z]\d{2}_")


def _find_tile_leaves(root: Path) -> list[Path]:
    """Every directory under root containing MetaXpress-pattern .tif files."""
    leaves = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        if any(f.lower().endswith((".tif", ".tiff")) and _WELL_RE.search(f) for f in filenames):
            leaves.append(Path(dirpath))
            dirnames[:] = []  # don't descend below a tile folder
    return leaves


def _plate_for_leaf(leaf: Path, input_root: Path) -> Path:
    """Walk up from leaf, returning the first ancestor with a non-noise name.

    Clamps at input_root so we never escape what the user dragged in.
    """
    p = leaf
    # Don't treat the leaf itself as the plate unless it's input_root
    if p != input_root:
        p = p.parent
    while p != input_root and _NOISE_RE.match(p.name) and p.parent != p:
        p = p.parent
    return p


def find_plates(input_root: Path) -> list[tuple[str, Path, Path]]:
    """Return list of (plate_name, plate_dir, tile_dir) for one input path.

    - plate_dir: where outputs go (the meaningful folder the user thinks of as
      one plate, e.g. RCE-24W-Sample-V52-Control-G-HT2).
    - tile_dir: the leaf folder actually containing .tif files (e.g.
      TimePoint_1, usually 3 levels below the plate).
    """
    out = []
    for leaf in _find_tile_leaves(input_root):
        plate_dir = _plate_for_leaf(leaf, input_root)
        out.append((plate_dir.name, plate_dir, leaf))
    return out


# ---------------------------------------------------------------------------
# Metadata helpers
# ---------------------------------------------------------------------------
def _inject_times_into_ome(path: Path, scan_time, stitch_time):
    """Append ScanTime/StitchTime into the OME-XML's StructuredAnnotations.

    Only touches the first IFD's ImageDescription. If the description isn't
    OME XML, silently skip — never block output on metadata.
    """
    try:
        desc = tifffile.tiffcomment(str(path))
    except Exception:
        return
    if not desc or "</OME>" not in desc:
        return

    sa = (
        "<StructuredAnnotations>"
        f'<XMLAnnotation ID="Annotation:scan-time"><Value><ScanTime>{scan_time or ""}</ScanTime></Value></XMLAnnotation>'
        f'<XMLAnnotation ID="Annotation:stitch-time"><Value><StitchTime>{stitch_time}</StitchTime></Value></XMLAnnotation>'
        "</StructuredAnnotations>"
    )
    new_desc = desc.replace("</OME>", sa + "</OME>")
    # TIFF ImageDescription is an ASCII tag — escape any non-ASCII (e.g. ashlar
    # writes "µm" for PhysicalSizeXUnit) as XML numeric entities so the write
    # succeeds without losing information.
    new_desc = new_desc.encode("ascii", errors="xmlcharrefreplace").decode("ascii")
    try:
        tifffile.tiffcomment(str(path), new_desc)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Stitch one plate → per-channel OME-TIFFs
# ---------------------------------------------------------------------------
def stitch_plate(plate_name: str, plate_dir: Path, tile_dir: Path,
                 output_dir, verbose: bool = False):
    if output_dir is None:
        # Not plate_dir itself: MetaXpress leaves a .HTD there, and Bio-Formats
        # then picks CellWorxReader for *any* TIFF in that folder and crashes
        # (ArrayIndexOutOfBounds in CellWorxReader.getFile). A subfolder has no HTD.
        output_dir = plate_dir / "stitched"
    output_dir.mkdir(parents=True, exist_ok=True)

    reader = FileSeriesReader2(tile_dir)
    metadata = reader.metadata
    n_channels = metadata.num_channels
    # Channel names from a complete site (a site may have dropped a channel).
    complete_names = next(s["channels"] for s in metadata.sites if len(s["channels"]) == n_channels)

    scan_time = metadata.sites[0]["scan_time"]
    stitch_time = datetime.datetime.now().isoformat(timespec="seconds")

    # Enumerate (plate, well) pairs. MetaXpress data is almost always a single
    # "plate" with N wells; we still loop both axes to stay general.
    plate_wells = [
        (p, w)
        for p in range(metadata.num_plates)
        for w in range(metadata.num_wells[p])
    ]
    multi_well = len(plate_wells) > 1
    print(f"  偵測到 {len(plate_wells)} 個 well, {n_channels} 個 channel")

    written = []
    skipped_wells = []
    for plate_idx, well_idx in plate_wells:
        metadata.set_active_plate_well(plate_idx, well_idx)
        well_name = metadata.well_name(plate_idx, well_idx)
        tag = f"{plate_name}-{well_name}" if multi_well else plate_name

        # Each site must have a TIFF for every channel — otherwise ashlar
        # crashes deep in the pyramid writer with a tuple IndexError.
        incomplete = sum(
            len(metadata.sites[i]["paths"]) != n_channels for i in metadata.active_series
        )
        if incomplete:
            msg = f"{incomplete} 個 site channel 不齊（預期 {n_channels}）"
            print(f"  → well {well_name}: ⚠ 跳過 — {msg}")
            skipped_wells.append((well_name, msg))
            continue

        print(f"  → well {well_name} ({len(metadata.active_series)} tile)")

        aligner = EdgeAligner(reader, channel=0, verbose=verbose)
        aligner.run()

        for c in range(n_channels):
            # Use the raw _IllumSetting_ string from TIFF metadata as the
            # channel label. No lab-convention mapping (FITC → CD45 etc.) —
            # we want the physical channel name as recorded by the microscope.
            raw_name = complete_names[c] or str(c)
            safe_title = "".join(ch for ch in raw_name if ch.isalnum() or ch in "-_") or f"c{c}"
            # .ome.tif so Fiji hands the file to Bio-Formats; plain .tif goes to
            # ImageJ's native reader, which cannot open BigTIFF.
            out_path = output_dir / f"{tag}-{safe_title}.ome.tif"

            mosaic = Mosaic(
                aligner,
                shape=aligner.mosaic_shape,
                channels=[c],
                verbose=verbose,
            )
            PyramidWriter([mosaic], str(out_path), verbose=verbose).run()
            _inject_times_into_ome(out_path, scan_time, stitch_time)
            written.append(out_path)

    if skipped_wells:
        print(f"  ⚠ 略過 {len(skipped_wells)} 個 well（資料不齊）：")
        for w, reason in skipped_wells:
            print(f"      {w}: {reason}")
    return written, len(plate_wells) - len(skipped_wells)


# ---------------------------------------------------------------------------
# Error formatting
# ---------------------------------------------------------------------------
def _timing(seconds: float, n_wells: int) -> str:
    """'  耗時 1 分 23 秒（3 個 well，平均 27.7 秒/well）' — well 部分在 0 well 時省略。"""
    m, sec = divmod(int(seconds), 60)
    txt = f"  耗時 {m} 分 {sec} 秒" if m else f"  耗時 {seconds:.1f} 秒"
    if n_wells:
        txt += f"（{n_wells} 個 well，平均 {seconds / n_wells:.1f} 秒/well）"
    return txt


def _human_error(exc: BaseException) -> str:
    # metamorphtiff.scan raises ValueError with a user-facing (zh-TW) message.
    return str(exc) if isinstance(exc, ValueError) else f"{type(exc).__name__}: {exc}"


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="acrocyte-manufacture",
        description="批次顯微鏡影像縫圖（MetaXpress / MetaMorph TIFF）",
    )
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="一個或多個資料夾。可以拖盤資料夾、分類資料夾、或母資料夾——工具自動找到盤名跟 tile 位置。",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="（進階）統一輸出資料夾；預設輸出到每個盤資料夾下的 stitched/ 子資料夾。",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="顯示完整 Python traceback 與 ashlar 進度。",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {version('acrocyte-manufacture')}",
    )
    args = parser.parse_args(argv)

    # Expand every input to (plate_name, plate_dir, tile_dir) entries.
    plates: list[tuple[str, Path, Path]] = []
    for raw in args.paths:
        path = raw.expanduser().resolve()
        # ponytail: Docker on Windows mounts `-v C:\:/c`, so dragged C:\... paths map to /c/...
        if not path.exists() and (m := re.match(r"([A-Za-z]):[\\/](.*)", str(raw))):
            path = Path("/" + m[1].lower(), m[2].replace("\\", "/"))
        if not path.exists():
            print(f"✗ 略過 {path}：路徑不存在")
            continue
        if not path.is_dir():
            print(f"✗ 略過 {path}：不是資料夾")
            continue
        found = find_plates(path)
        if not found:
            print(f"✗ 略過 {path}：找不到任何 .tif 檔")
            continue
        plates.extend(found)

    if not plates:
        print("沒有任何盤可以縫，結束。")
        return 1

    # Preview: list detected plates so user can Ctrl-C if wrong.
    print(f"\n偵測到 {len(plates)} 個盤：")
    for i, (name, _, tile_dir) in enumerate(plates, 1):
        print(f"  {i:>3}. {name}")
        print(f"        tile: {tile_dir}")
    print()

    succeeded, failed = [], []
    total_wells = 0
    t_batch = time.monotonic()
    for i, (name, plate_dir, tile_dir) in enumerate(plates, 1):
        print(f"\n=== [{i}/{len(plates)}] {name} ===")
        t0 = time.monotonic()
        try:
            out_files, n_wells = stitch_plate(name, plate_dir, tile_dir, args.output_dir, verbose=args.verbose)
        except KeyboardInterrupt:
            print("\n中斷。")
            raise
        except Exception as exc:
            if args.verbose:
                traceback.print_exc()
            reason = _human_error(exc)
            failed.append((name, reason))
            print(f"  ✗ 失敗：{reason}")
            continue

        succeeded.append((name, out_files))
        total_wells += n_wells
        print(f"  ✓ 完成（{len(out_files)} 個檔案）{_timing(time.monotonic() - t0, n_wells)}")
        for f in out_files:
            print(f"    - {f}")

    print("\n" + "=" * 50)
    print(f"批次結果：✓ 成功 {len(succeeded)} 個   ✗ 失敗 {len(failed)} 個"
          f"{_timing(time.monotonic() - t_batch, total_wells)}")
    if failed:
        print("\n失敗清單：")
        for name, reason in failed:
            print(f"  - {name}：{reason}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
