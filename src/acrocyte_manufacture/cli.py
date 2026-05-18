"""acrocyte-manufacture CLI: batch stitching of MetaXpress TIFF tiles."""

# Mock javabridge/bioformats BEFORE importing ashlar — ashlar.reg imports
# them at module load but we only ever read plain TIFFs, so the Java stack
# is dead weight that breaks Windows installs.
import sys
import types
sys.modules.setdefault("javabridge", types.ModuleType("javabridge"))
sys.modules.setdefault("bioformats", types.ModuleType("bioformats"))

import argparse
import datetime
import logging
import os
import re
import traceback
import warnings
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)
logging.disable(logging.WARNING)

import tifffile
from ashlar.reg import EdgeAligner, Mosaic, PyramidWriter

from . import __version__
from .ashlar_adapter import FileSeriesReader2


# ---------------------------------------------------------------------------
# Plate discovery
# ---------------------------------------------------------------------------
# MetaXpress's deep layout looks like:
#   <plate>/<scan-date>/<run-id>/TimePoint_N/*.tif
# We walk up from the tile folder, skipping these noise levels, to find the
# plate name. The plate is the first ancestor whose name doesn't match a
# noise pattern.
_NOISE_PATTERNS = [
    re.compile(r"^TimePoint_\d+$"),
    re.compile(r"^\d{4}-\d{2}-\d{2}$"),
    re.compile(r"^\d+$"),
]

# Tile filenames must contain "_<well>_" (e.g. _A01_, _H12_). Our own output
# files use "-" separators and therefore won't match — important when re-running
# in a plate folder that already contains a previous stitch.
_WELL_RE = re.compile(r"_[A-Z]\d{2}_")


def _is_noise_name(name: str) -> bool:
    return any(p.match(name) for p in _NOISE_PATTERNS)


def _dir_has_meta_tifs(path: Path) -> bool:
    for entry in path.iterdir():
        if entry.is_file() and entry.suffix.lower() in {".tif", ".tiff"} \
                and _WELL_RE.search(entry.name):
            return True
    return False


def _find_tile_leaves(root: Path, max_depth: int = 8) -> list[Path]:
    """Return every directory under root containing MetaXpress-pattern .tif files."""
    leaves: list[Path] = []

    def walk(p: Path, depth: int):
        if depth > max_depth or p.name.startswith("."):
            return
        try:
            entries = list(p.iterdir())
        except (PermissionError, OSError):
            return

        has_tiles = any(
            e.is_file()
            and e.suffix.lower() in {".tif", ".tiff"}
            and _WELL_RE.search(e.name)
            for e in entries
        )
        if has_tiles:
            leaves.append(p)
            return  # don't descend below a tile folder

        for child in entries:
            if child.is_dir():
                walk(child, depth + 1)

    walk(root, 0)
    return leaves


def _plate_for_leaf(leaf: Path, input_root: Path) -> Path:
    """Walk up from leaf, returning the first ancestor with a non-noise name.

    Clamps at input_root so we never escape what the user dragged in.
    """
    p = leaf
    # Don't treat the leaf itself as the plate unless it's input_root
    if p != input_root:
        p = p.parent
    while p != input_root and _is_noise_name(p.name) and p.parent != p:
        p = p.parent
    return p


def find_plates(input_root: Path) -> list[tuple[str, Path, Path]]:
    """Return list of (plate_name, plate_dir, tile_dir) for one input path.

    - plate_dir: where outputs go (the meaningful folder the user thinks of as
      one plate, e.g. RCE-24W-Sample-V52-Control-G-HT2).
    - tile_dir: the leaf folder actually containing .tif files (e.g.
      TimePoint_1, usually 3 levels below the plate).
    """
    leaves = _find_tile_leaves(input_root)
    out = []
    for leaf in leaves:
        plate_dir = _plate_for_leaf(leaf, input_root)
        out.append((plate_dir.name, plate_dir, leaf))
    return out


# ---------------------------------------------------------------------------
# Metadata helpers
# ---------------------------------------------------------------------------
def _extract_scan_time(tile_dir: Path):
    """Read the DateTime tag from the first usable TIFF in the tile dir."""
    for ext in ("*.tif", "*.tiff"):
        for p in sorted(tile_dir.glob(ext)):
            try:
                with tifffile.TiffFile(p) as tif:
                    dt = tif.pages[0].tags.get("DateTime")
                    if dt and dt.value:
                        return dt.value
            except Exception:
                continue
    return None


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
        output_dir = plate_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    reader = FileSeriesReader2(tile_dir)
    metadata = reader.metadata
    # Use the max channel count across the whole plate, not the first row —
    # acquisition can drop a channel at a single site (we then skip the well).
    n_channels = max(len(fp) for fp in metadata.df["file_path"])
    # Pick channel names from a complete site (first row might be missing one).
    complete_names = next(
        (names for names in metadata.df["channel_name"] if len(names) == n_channels),
        metadata.df.iloc[0]["channel_name"],
    )

    scan_time = _extract_scan_time(tile_dir)
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
            1 for image_idx in metadata.active_series
            if len(metadata.df.iloc[image_idx]["file_path"]) != n_channels
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
            out_path = output_dir / f"{tag}-{safe_title}.tif"

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
    return written


# ---------------------------------------------------------------------------
# Error formatting
# ---------------------------------------------------------------------------
def _human_error(exc: BaseException) -> str:
    msg = str(exc)
    if "MetaXpress 檔名" in msg or "沒有任何 TIFF" in msg:
        return msg
    if "spatial-calibration" in msg:
        return "TIFF metadata 缺少 spatial-calibration 欄位（非 MetaXpress 來源？）"
    if "PlaneInfo" in msg:
        return "TIFF 中找不到 PlaneInfo 區塊（非 MetaXpress 來源？）"
    if "non-square pixels" in msg:
        return "TIFF 的 pixel 不是正方形，ashlar 不支援"
    return f"{type(exc).__name__}: {msg}"


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
        help="（進階）統一輸出資料夾；預設輸出到每個盤的資料夾內。",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="顯示完整 Python traceback 與 ashlar 進度。",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    args = parser.parse_args(argv)

    # Expand every input to (plate_name, plate_dir, tile_dir) entries.
    plates: list[tuple[str, Path, Path]] = []
    for raw in args.paths:
        path = raw.expanduser().resolve()
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
    for i, (name, plate_dir, tile_dir) in enumerate(plates, 1):
        print(f"\n=== [{i}/{len(plates)}] {name} ===")
        try:
            out_files = stitch_plate(name, plate_dir, tile_dir, args.output_dir, verbose=args.verbose)
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
        n_wells = len({f.stem.rsplit("-", 1)[0] for f in out_files})
        n_channels_out = len(out_files) // max(n_wells, 1)
        print(f"  ✓ 完成（{len(out_files)} 個檔案 = {n_wells} well × {n_channels_out} channel）")
        for f in out_files:
            print(f"    - {f}")

    print("\n" + "=" * 50)
    print(f"批次結果：✓ 成功 {len(succeeded)} 個   ✗ 失敗 {len(failed)} 個")
    if failed:
        print("\n失敗清單：")
        for name, reason in failed:
            print(f"  - {name}：{reason}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
