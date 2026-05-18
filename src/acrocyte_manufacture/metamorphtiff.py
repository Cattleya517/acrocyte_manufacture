"""MetaMorph / MetaXpress TIFF helper.

Adapted from acrocyte_simple-stitch-app/stitcher/metamorphtiff.py — trimmed
to remove the SpatialData/dask export paths which are not needed in the CLI
stitching pipeline.
"""

import re
import xml.etree.ElementTree as ET
from itertools import groupby

import numpy as np
import pandas as pd
import tifffile
from tqdm import tqdm

from ._channelinfo import name_to_rank


# MD (Molecular Devices) image filename pattern.
# - plate_name: anything up to the well separator
# - well_name:  one uppercase letter + two digits (A01, B12, ...)
# - everything after the well is matched loosely (series/channel/UUID/extension)
MD_PATTERN = r"(?P<plate_name>.+)_(?P<well_name>[A-Z]\d{2})_.+\.tiff?"


class MetaMorphTIFFHelper:
    def __init__(self, path, pattern=MD_PATTERN):
        self.path = path
        self.pattern = pattern

    def to_dataframe(self):
        records = []
        self._collect_image_files(records)
        self._extract_image_metadata(records)
        self._sort_raster_order(records)
        return self._convert_to_dataframe(records)

    # ---------------------------------------------------------------------
    # Filter out thumbnails / sidecars by size and match MD_PATTERN.
    def _collect_image_files(self, records, min_filesize=1_000_000):
        all_files = [
            p for p in self.path.iterdir()
            if p.is_file() and not p.name.startswith(".")
        ]
        all_files = [p for p in all_files if p.stat().st_size >= min_filesize]
        for p in tqdm(all_files, desc="掃描檔名"):
            match = re.match(self.pattern, p.name)
            if match is not None:
                gd = match.groupdict()
                records.append({
                    "plate_name":  gd["plate_name"],
                    "well_name":   gd["well_name"],
                    "series_idx":  None,
                    "channel_idx": None,
                    "file_path":   str(p),
                })

    # ---------------------------------------------------------------------
    # Read MetaMorph PlaneInfo block from each TIFF's ImageDescription tag.
    def _extract_image_metadata(self, records):
        extracted_properties = [
            "pixel-size-x", "pixel-size-y",
            "bits-per-pixel",
            "spatial-calibration-x", "spatial-calibration-y", "spatial-calibration-units",
            "stage-position-x", "stage-position-y",
            "_IllumSetting_",
        ]
        convert = {"int": int, "float": float, "string": str}

        for record in tqdm(records, desc="讀取 TIFF metadata"):
            prop = {}
            with tifffile.TiffFile(record["file_path"]) as tif:
                root = ET.fromstring(tif.pages[0].tags["ImageDescription"].value)
                for p in root.find("PlaneInfo").findall("prop"):
                    if p.attrib["id"] in extracted_properties:
                        prop[p.attrib["id"]] = convert[p.attrib["type"]](p.attrib["value"])

            assert prop["spatial-calibration-units"] == "um", "unsupported pixel size unit"
            assert prop["spatial-calibration-x"] == prop["spatial-calibration-y"], "non-square pixels are not supported"

            delta = prop["spatial-calibration-x"]
            record["pixel_size"]    = delta
            record["pixel_dtype"]   = np.dtype(f"uint{prop['bits-per-pixel']}")
            record["tile_size"]     = np.array([prop["pixel-size-y"], prop["pixel-size-x"]])
            record["tile_position"] = np.array([prop["stage-position-y"], prop["stage-position-x"]]) / delta
            record["channel_name"]  = prop.get("_IllumSetting_", str(record["channel_idx"]))

    # ---------------------------------------------------------------------
    # Group tiles by (plate, well), then by binned stage position. Within
    # each tile position, sort channels by channel rank (DAPI first).
    @staticmethod
    def _sort_raster_order(records, tol=10):
        for r in records:
            r["_pos"] = tuple((r["tile_position"] // tol).astype(int))

        key_well = lambda r: (r["plate_name"], r["well_name"])
        records.sort(key=key_well)

        for _, well_group in groupby(records, key=key_well):
            well_records = list(well_group)
            well_records.sort(key=lambda r: r["_pos"])

            series_idx = 0
            for _, pos_group in groupby(well_records, key=lambda r: r["_pos"]):
                pos_records = sorted(pos_group, key=lambda r: name_to_rank(r["channel_name"]))
                for channel_idx, r in enumerate(pos_records):
                    r["series_idx"]  = series_idx
                    r["channel_idx"] = channel_idx
                series_idx += 1

        for r in records:
            del r["_pos"]

    # ---------------------------------------------------------------------
    def _convert_to_dataframe(self, records):
        df = pd.DataFrame.from_records(records)
        if df.empty:
            raise ValueError("沒有任何 TIFF 通過 MetaXpress 檔名過濾")

        df["plate_idx"] = df["plate_name"].astype("category").cat.codes
        df["well_idx"]  = (
            df.groupby("plate_name")["well_name"]
            .transform(lambda w: w.astype("category").cat.codes)
        )
        df = df.set_index(["plate_idx", "well_idx", "series_idx", "channel_idx"]).sort_index()

        df = df.groupby(level=["plate_idx", "well_idx", "series_idx"], sort=False).agg({
            "plate_name":    "first",
            "well_name":     "first",
            "pixel_size":    "first",
            "pixel_dtype":   "first",
            "tile_size":     "first",
            "tile_position": "first",
            "channel_name":  tuple,
            "file_path":     tuple,
        }).sort_index()

        return df


__all__ = ["MetaMorphTIFFHelper", "MD_PATTERN"]
