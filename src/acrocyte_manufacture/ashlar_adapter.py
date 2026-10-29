"""Ashlar PlateReader/PlateMetadata bridge over the site list from metamorphtiff.scan."""

import ashlar.reg as reg
import tifffile

from .metamorphtiff import scan


class FileSeriesMetadata2(reg.PlateMetadata):
    def __init__(self, path):
        self.sites, self.plates = scan(path)
        super().__init__()

    @property
    def num_plates(self):
        return len(self.plates)

    @property
    def num_wells(self):
        return [len(wells) for _, wells in self.plates]

    @property
    def plate_well_series(self):
        return [[idx for _, idx in wells] for _, wells in self.plates]

    def plate_name(self, plate_idx):
        return self.plates[plate_idx][0]

    def well_name(self, plate_idx, well_idx):
        return self.plates[plate_idx][1][well_idx][0]

    @property
    def _num_images(self):
        return len(self.sites)

    @property
    def num_channels(self):
        # Max across the plate: a single site may have dropped a channel
        # (cli skips that well), and the first site might be the short one.
        return max(len(s["paths"]) for s in self.sites)

    @property
    def pixel_size(self):
        return self.sites[0]["pixel_size"]

    @property
    def pixel_dtype(self):
        return self.sites[0]["dtype"]

    def tile_position(self, image_idx):
        return self.sites[image_idx]["position"]

    def tile_size(self, image_idx):
        return self.sites[image_idx]["size"]

    def file_path(self, series_idx, channel_idx):
        return self.sites[self.active_series[series_idx]]["paths"][channel_idx]


class FileSeriesReader2(reg.PlateReader):
    def __init__(self, path):
        self.metadata = FileSeriesMetadata2(path)

    def read(self, series_idx, channel_idx):
        return tifffile.memmap(self.metadata.file_path(series_idx, channel_idx))
