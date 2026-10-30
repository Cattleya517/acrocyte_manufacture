"""End-to-end self-check on synthetic MetaMorph tiles.  Run: uv run python test_stitch.py

Builds plate/<date>/<run>/TimePoint_1/*.tif (2x2 grid, 2 channels, 10% overlap)
plus a second well missing one channel at one site, stitches, and checks the
mosaic reproduces the source image and the OME-XML carries ScanTime/StitchTime.
"""

import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
import tifffile

from acrocyte_manufacture.cli import _parse_dragged, main

TILE, OVERLAP, PX = 1024, 100, 0.65  # px, px, µm
SCAN = "2026:10:28 10:00:00"


def _desc(y_px, x_px, channel):
    props = {
        "pixel-size-x": ("int", TILE), "pixel-size-y": ("int", TILE),
        "bits-per-pixel": ("int", 16),
        "spatial-calibration-x": ("float", PX), "spatial-calibration-y": ("float", PX),
        "spatial-calibration-units": ("string", "um"),
        "stage-position-x": ("float", x_px * PX), "stage-position-y": ("float", y_px * PX),
        "_IllumSetting_": ("string", channel),
    }
    body = "".join(f'<prop id="{k}" type="{t}" value="{v}"/>' for k, (t, v) in props.items())
    return f"<MetaData><PlaneInfo>{body}</PlaneInfo></MetaData>"


def make_plate(root: Path, rng):
    size = 2 * TILE - OVERLAP
    src = {c: rng.integers(1, 4000, (size, size), dtype=np.uint16) for c in ("DAPI", "FITC")}
    tiles = root / "P1" / "2026-10-28" / "1234" / "TimePoint_1"
    tiles.mkdir(parents=True)
    for well in ("A01", "B02"):
        s = 0
        for r in range(2):
            for c in range(2):
                y, x = r * (TILE - OVERLAP), c * (TILE - OVERLAP)
                # w1=FITC, w2=DAPI on purpose: channel order must come from rank, not filename
                for w, ch in enumerate(("FITC", "DAPI"), 1):
                    # per-tile noise: exactly identical overlaps trip an ashlar precision guard
                    tile = src[ch][y:y + TILE, x:x + TILE] + rng.integers(0, 4, (TILE, TILE), dtype=np.uint16)
                    tifffile.imwrite(
                        tiles / f"P1_{well}_s{s}_w{w}.tif", tile,
                        description=_desc(y, x, ch), metadata=None, datetime=SCAN,
                    )
                s += 1
    (tiles / "P1_B02_s3_w2.tif").unlink()  # incomplete site → well B02 must be skipped
    return src


def check(root: Path, src):
    from acrocyte_manufacture.ashlar_adapter import FileSeriesMetadata2
    site0 = FileSeriesMetadata2(root / "P1" / "2026-10-28" / "1234" / "TimePoint_1").sites[0]
    assert site0["channels"] == ("DAPI", "FITC"), f"rank order broken: {site0['channels']}"
    out = root / "P1" / "stitched"
    assert not list(out.glob("P1-B02-*.ome.tif")), "incomplete well was not skipped"
    for ch in ("DAPI", "FITC"):
        f = out / f"P1-A01-{ch}.ome.tif"
        assert f.exists(), f"missing {f}"
        img = np.squeeze(tifffile.imread(f, level=0))
        assert img.shape == src[ch].shape, (img.shape, src[ch].shape)
        assert np.abs(img.astype(int) - src[ch].astype(int)).max() <= 4, "mosaic != source"
        xml = tifffile.tiffcomment(str(f))
        assert f"<ScanTime>{SCAN}</ScanTime>" in xml and "<StitchTime>" in xml, "times not injected"
        assert "&#181;m" in xml, "µ not escaped"


if __name__ == "__main__":
    tmp = Path(tempfile.mkdtemp())
    try:
        src = make_plate(tmp, np.random.default_rng(0))
        assert main([str(tmp), "-y"]) == 0
        # dragged-path parsing: macOS escaped spaces, Windows quoted/& forms, several per line
        assert _parse_dragged(r"/Volumes/Crucial\ X6/Day3") == ["/Volumes/Crucial X6/Day3"]
        assert _parse_dragged(r"""& 'E:\RCE Monitor\Day3' "C:\a b" D:\c""") == ["E:/RCE Monitor/Day3", "C:/a b", "D:/c"]
        check(tmp, src)
        print("\nOK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    sys.exit(0)
