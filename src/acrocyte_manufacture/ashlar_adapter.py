"""Ashlar reader adapter for MetaMorph file-series tiles.

Adapted from acrocyte_simple-stitch-app/stitcher/ashlar_adapter.py — only the
PlateReader/PlateMetadata bridge is kept. Zarr / SpatialData / OME-Zarr
writers and the BaSiC illumination estimator are removed; this CLI writes
straight to OME-TIFF via ashlar's PyramidWriter.
"""

import ashlar.reg as reg
import numpy as np
import pandas as pd
import tifffile

from ._channelinfo import name_to_color
from .metamorphtiff import MD_PATTERN, MetaMorphTIFFHelper


class FileSeriesMetadata2(reg.PlateMetadata):
    def __init__(self, path, pattern=MD_PATTERN):
        super().__init__()
        helper = MetaMorphTIFFHelper(path, pattern)
        self.path = path
        self.pattern = pattern
        self.df = helper.to_dataframe()
        self.idx = pd.IndexSlice
        # Normalize tile positions to start from (0,0) to avoid floating-point
        # precision issues in ashlar's alignment.
        self._normalize_positions()

    @property
    def num_plates(self):
        return len(self.df.loc[self.idx[:, 0, 0], "plate_name"])

    @property
    def num_wells(self):
        return [
            len(self.df.loc[self.idx[p, :, 0], "well_name"])
            for p in range(self.num_plates)
        ]

    def plate_name(self, plate_idx):
        return self.df.loc[self.idx[plate_idx, 0, 0], "plate_name"]

    def well_name(self, plate_idx, well_idx):
        return self.df.loc[self.idx[plate_idx, well_idx, 0], "well_name"]

    @property
    def well_naming(self):
        return [["letter", "number"]] * self.num_plates

    @property
    def plate_well_series(self):
        if not hasattr(self, "_plate_well_series"):
            self._plate_well_series = [
                [
                    [self.df.index.get_loc(i) for i in self.df.loc[self.idx[p, w, :], :].index]
                    for w in range(self.num_wells[p])
                ]
                for p in range(self.num_plates)
            ]
        return self._plate_well_series

    @property
    def _num_images(self):
        return len(self.df)

    @property
    def num_channels(self):
        return len(self.df.iloc[0]["file_path"])

    @property
    def pixel_size(self):
        return self.df.iloc[0]["pixel_size"]

    @property
    def pixel_dtype(self):
        return self.df.iloc[0]["pixel_dtype"]

    def _normalize_positions(self):
        positions = np.vstack(self.df["tile_position"].values)
        origin = positions.min(axis=0)
        self.df["tile_position"] = [pos - origin for pos in self.df["tile_position"]]

    def tile_position(self, image_idx):
        return self.df.iloc[image_idx]["tile_position"]

    def tile_size(self, image_idx):
        return self.df.iloc[image_idx]["tile_size"]

    def file_path(self, series_idx, channel_idx):
        image_idx = self.active_series[series_idx]
        return self.df.iloc[image_idx]["file_path"][channel_idx]

    @property
    def channels(self):
        if not hasattr(self, "_channels"):
            channel_names = self.df.iloc[0]["channel_name"]
            self._channels = []
            for i, name in enumerate(channel_names):
                resolved_name = name or str(i)
                self._channels.append({
                    "name":  resolved_name,
                    "color": name_to_color(resolved_name) or "FFFFFF",
                })
        return self._channels


class FileSeriesReader2(reg.PlateReader):
    def __init__(self, path, plate=None, well=None, pattern=MD_PATTERN):
        self.path = path
        self.pattern = pattern
        self.metadata = FileSeriesMetadata2(self.path, self.pattern)
        self.metadata.set_active_plate_well(plate, well)

    def read(self, series_idx, channel_idx):
        file_path = self.metadata.file_path(series_idx, channel_idx)
        return tifffile.memmap(file_path)


__all__ = ["FileSeriesReader2", "FileSeriesMetadata2"]
