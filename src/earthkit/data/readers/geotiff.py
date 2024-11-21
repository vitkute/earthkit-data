import logging
import struct

from earthkit.data.readers import Reader

LOG = logging.getLogger(__name__)


class GeotiffReader(Reader):
    def __init__(self, source, path):
        super().__init__(source, path)

    def __repr__(self):
        return f"GeotiffReader ({self.path})"

    def to_pandas(self, **kwargs):
        raise NotImplementedError("method to_pandas() not implemented")

    def to_xarray(self, **kwargs):
        raise NotImplementedError("method to_xarray() not implemented")


def is_geotiff(data):
    try:
        # Check if there are at least 8 bytes for TIFF header
        if len(data) < 8:
            return False  # Not enough data to be a valid TIFF file

        # Read endianness (first 2 byte)
        endian_indicator = data[:2]
        if endian_indicator == b"II":
            endian = "<"  # Little-endian
        elif endian_indicator == b"MM":
            endian = ">"  # Big-endian
        else:
            return False  # It is not a valid TIFF file

        # Check the magic number (byte 2-4)
        magic_number = struct.unpack(endian + "H", data[2:4])[0]
        if magic_number != 42:
            return False  # It is not a valid TIFF file

        # Get offset to first Image File Directory (IFD)
        ifd_offset = struct.unpack(endian + "I", data[4:8])[0]
        if ifd_offset >= len(data):
            # if IFD offset is beyond data length, then not ok
            return False

        # Read number of IFD entries (2 bytes at the offset)
        num_ifd_entries = struct.unpack(
            endian + "H", data[ifd_offset : ifd_offset + 2]
        )[0]

        # Check each IFD entry (12 bytes per entry)
        found_geotiff_tag = False
        for i in range(num_ifd_entries):
            entry_offset = ifd_offset + 2 + i * 12
            if entry_offset + 12 > len(data):
                return False

            tag_id = struct.unpack(endian + "H", data[entry_offset : entry_offset + 2])[
                0
            ]

            # Check for GeoKeyDirectoryTag (34735)
            if tag_id == 34735:
                found_geotiff_tag = True
                break

        if not found_geotiff_tag:
            return False

        return True

    except Exception as e:
        print(f"An error occurred in is_geotiff: {e}")
        return False


def reader(source, path, *, magic=None, deeper_check=False, **kwargs):
    """
    'is_geotiff' function checks if a file is a valid geotiff
    """
    if is_geotiff(magic):
        return GeotiffReader(source, path)