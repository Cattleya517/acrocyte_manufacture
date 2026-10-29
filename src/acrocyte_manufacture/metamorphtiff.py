"""Scan a MetaMorph / MetaXpress tile folder into a plain list of sites.

Series indices come from binned stage positions (raster order), channels from
the ``_IllumSetting_`` PlaneInfo prop — never from the filename.
"""

import re
import xml.etree.ElementTree as ET
from itertools import groupby
from pathlib import Path

import numpy as np
import tifffile
from tqdm import tqdm

# Loose on purpose: only filters what to scan. plate/well come from the name,
# everything else (series, channel) from TIFF metadata.
MD_PATTERN = re.compile(r"(?P<plate_name>.+)_(?P<well_name>[A-Z]\d{2})_.+\.tiff?$")

# Channel ordering within a site: DAPI first, unknown names last (alphabetical).
_RANK = {alias: rank for rank, aliases in enumerate([
    ("B", "DAPI", "HOECHST", "W0"),
    ("G", "FITC", "CD45"),
    ("TRANSMITTEDLIGHT", "TX"),
    ("Y", "TRITC", "HER2", "PDL1", "PD-L1", "TEXASRED"),
    ("K", "TL25"),
    ("R", "CY5", "EPCAM"),
]) for alias in aliases}

_PROPS = {
    "pixel-size-x": int, "pixel-size-y": int, "bits-per-pixel": int,
    "spatial-calibration-x": float, "spatial-calibration-y": float,
    "spatial-calibration-units": str,
    "stage-position-x": float, "stage-position-y": float,
    "_IllumSetting_": str,
}


def _rank(channel_name):
    n = channel_name.replace(" ", "").upper()
    return _RANK.get(n, 99), n


def _plane_info(path: Path) -> dict:
    with tifffile.TiffFile(path) as tif:
        tags = tif.pages[0].tags
        desc = tags.get("ImageDescription")
        try:
            plane = ET.fromstring(desc.value).find("PlaneInfo") if desc else None
        except ET.ParseError:
            plane = None
        if plane is None:
            raise ValueError(f"{path.name}: TIFF 中找不到 PlaneInfo 區塊（非 MetaXpress 來源？）")
        info = {
            p.attrib["id"]: _PROPS[p.attrib["id"]](p.attrib["value"])
            for p in plane.findall("prop") if p.attrib["id"] in _PROPS
        }
        dt = tags.get("DateTime")
        info["DateTime"] = dt.value if dt else None
    if "spatial-calibration-x" not in info:
        raise ValueError(f"{path.name}: TIFF metadata 缺少 spatial-calibration 欄位（非 MetaXpress 來源？）")
    if info["spatial-calibration-units"] != "um":
        raise ValueError(f"{path.name}: 不支援的 pixel 單位 {info['spatial-calibration-units']!r}")
    if info["spatial-calibration-x"] != info["spatial-calibration-y"]:
        raise ValueError(f"{path.name}: TIFF 的 pixel 不是正方形，ashlar 不支援")
    return info


def scan(path: Path, min_filesize=1_000_000, tol=10):
    """Return (sites, plates).

    sites[i]  = {"position", "size", "pixel_size", "dtype", "channels", "paths", "scan_time"}
                position/size are (y, x) in pixels; channels/paths are tuples in rank order.
    plates    = [(plate_name, [(well_name, [site_idx, ...]), ...]), ...], lexical order.

    Files under ``min_filesize`` bytes (thumbnails, sidecars) are ignored.
    Stage positions are binned to ``tol`` pixels so jitter doesn't break raster order.
    """
    files = [
        p for p in sorted(path.iterdir())
        if p.is_file() and not p.name.startswith(".")  # macOS ._ sidecars
        and MD_PATTERN.match(p.name) and p.stat().st_size >= min_filesize
    ]
    if not files:
        raise ValueError("沒有任何 TIFF 通過 MetaXpress 檔名過濾")

    recs = []
    # ponytail: serial header reads; ThreadPoolExecutor here if a NAS scan measures slow
    for p in tqdm(files, desc="讀取 TIFF metadata"):
        m = MD_PATTERN.match(p.name).groupdict()
        info = _plane_info(p)
        delta = info["spatial-calibration-x"]
        pos = np.array([info["stage-position-y"], info["stage-position-x"]]) / delta
        recs.append({
            "plate": m["plate_name"], "well": m["well_name"],
            "bin": tuple((pos // tol).astype(int)), "channel": info.get("_IllumSetting_", ""),
            "position": pos, "size": np.array([info["pixel-size-y"], info["pixel-size-x"]]),
            "pixel_size": delta, "dtype": np.dtype(f"uint{info['bits-per-pixel']}"),
            "path": str(p), "scan_time": info["DateTime"],
        })
    recs.sort(key=lambda r: (r["plate"], r["well"], r["bin"], _rank(r["channel"])))

    # Normalize positions to start at (0, 0) — avoids float precision issues in ashlar.
    origin = np.min([r["position"] for r in recs], axis=0)

    sites, plates = [], []
    for plate, prs in groupby(recs, key=lambda r: r["plate"]):
        wells = []
        for well, wrs in groupby(prs, key=lambda r: r["well"]):
            idx = []
            for _, srs in groupby(wrs, key=lambda r: r["bin"]):
                srs = list(srs)
                idx.append(len(sites))
                sites.append({
                    **{k: srs[0][k] for k in ("size", "pixel_size", "dtype", "scan_time")},
                    "position": srs[0]["position"] - origin,
                    "channels": tuple(r["channel"] for r in srs),
                    "paths": tuple(r["path"] for r in srs),
                })
            wells.append((well, idx))
        plates.append((plate, wells))
    return sites, plates
