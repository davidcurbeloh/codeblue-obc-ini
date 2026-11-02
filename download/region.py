#!/usr/bin/env python3
"""
Shared geographical configuration for CodeBlue downloads.

Two methods are supported:

1. Manual geographical limits:
   --west --east --south --north

2. Automatic limits from a NetCDF model grid:
   --grid-file croco_grd.nc

The geographical padding is applied to the resulting domain.

NetCDF coordinate names supported:
    lon_rho / lat_rho
    longitude / latitude
    lon / lat

The module returns a Region object compatible with
the existing CodeBlue download scripts.
"""

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np


# ============================================================
# 1. REGION CLASS
# ============================================================

@dataclass(frozen=True)
class Region:
    """Geographical domain in degrees."""

    west: float
    east: float
    south: float
    north: float
    padding: float = 1.0

    def __post_init__(self):

        if not -180 <= self.west < self.east <= 180:
            raise ValueError(
                "Invalid longitude limits."
            )

        if not -90 <= self.south < self.north <= 90:
            raise ValueError(
                "Invalid latitude limits."
            )

        if self.padding < 0:
            raise ValueError(
                "Padding must be non-negative."
            )

        if self.south - self.padding < -90:
            raise ValueError(
                "Southern limit exceeds -90 degrees."
            )

        if self.north + self.padding > 90:
            raise ValueError(
                "Northern limit exceeds 90 degrees."
            )

        if self.west - self.padding < -180:
            raise ValueError(
                "Western limit exceeds -180 degrees."
            )

        if self.east + self.padding > 180:
            raise ValueError(
                "Eastern limit exceeds 180 degrees."
            )

    @property
    def bounds(self):
        """Return padded (west, east, south, north)."""

        return (
            self.west - self.padding,
            self.east + self.padding,
            self.south - self.padding,
            self.north + self.padding,
        )


# ============================================================
# 2. READ GEOGRAPHICAL LIMITS FROM NETCDF GRID
# ============================================================

def region_from_grid(grid_file, padding=1.0):
    """
    Read a NetCDF grid and determine its geographical bounds.

    Supports CROCO grids containing lon_rho and lat_rho,
    as well as NetCDF grids with standard lon/lat coordinates.

    The full geographical extent of the grid is considered,
    independently of its orientation.

    Parameters
    ----------
    grid_file : str or Path
        Path to the NetCDF grid file.

    padding : float
        Additional geographical margin in degrees.

    Returns
    -------
    Region
        Region containing the entire grid.
    """

    import xarray as xr

    grid_file = Path(grid_file).expanduser()

    if not grid_file.is_file():
        raise FileNotFoundError(
            f"Grid file not found: {grid_file}"
        )

    # --------------------------------------------------------
    # Open NetCDF
    # --------------------------------------------------------

    with xr.open_dataset(grid_file) as ds:

        coordinate_pairs = [
            ("lon_rho", "lat_rho"),
            ("longitude", "latitude"),
            ("lon", "lat"),
            ("nav_lon", "nav_lat"),
        ]

        lon_name = None
        lat_name = None

        for candidate_lon, candidate_lat in coordinate_pairs:

            if candidate_lon in ds.variables and candidate_lat in ds.variables:

                lon_name = candidate_lon
                lat_name = candidate_lat
                break

        if lon_name is None:
            raise ValueError(
                "No recognized longitude/latitude variables found "
                "in the NetCDF grid. Expected lon_rho/lat_rho, "
                "longitude/latitude, lon/lat or nav_lon/nav_lat."
            )

        lon = np.asarray(
            ds[lon_name].values,
            dtype=float
        )

        lat = np.asarray(
            ds[lat_name].values,
            dtype=float
        )

    # --------------------------------------------------------
    # Validate coordinates
    # --------------------------------------------------------

    if lon.ndim not in (1, 2) or lat.ndim not in (1, 2):
        raise ValueError(
            "Longitude and latitude must be 1D or 2D arrays."
        )

    if lon.ndim == 2 and lat.ndim == 2 and lon.shape != lat.shape:
        raise ValueError(
            "2D longitude and latitude arrays have different shapes."
        )

    if lon.ndim != lat.ndim:
        raise ValueError(
            "Longitude and latitude must both be 1D "
            "or both be 2D."
        )

    # 1D coordinates may represent independent lon/lat axes.
    # For bounding-box calculations, separate extrema suffice.

    lon = lon[np.isfinite(lon)]
    lat = lat[np.isfinite(lat)]

    if lon.size == 0 or lat.size == 0:
        raise ValueError(
            "The grid contains no valid geographical coordinates."
        )

    if np.any((lat < -90) | (lat > 90)):
        raise ValueError(
            "Latitude values outside [-90, 90] were found."
        )

    # --------------------------------------------------------
    # Normalize longitude to [-180, 180)
    # --------------------------------------------------------

    lon = ((lon + 180) % 360) - 180

    # Detect grids crossing the antimeridian.
    # These need a split download rather than one bounding box.

    lon_span = float(np.max(lon) - np.min(lon))

    if lon_span > 180:
        raise ValueError(
            "The grid may cross the antimeridian (180°). "
            "A single bounding box is not appropriate. "
            "Split-region downloads are not implemented."
        )

    # --------------------------------------------------------
    # Calculate original grid bounds
    # --------------------------------------------------------

    west = float(np.min(lon))
    east = float(np.max(lon))

    south = float(np.min(lat))
    north = float(np.max(lat))

    # --------------------------------------------------------
    # Create Region and apply padding
    # --------------------------------------------------------

    region = Region(
        west=west,
        east=east,
        south=south,
        north=north,
        padding=padding,
    )

    print("\n" + "=" * 55)
    print("CODEBLUE — GRID GEOGRAPHICAL CONFIGURATION")
    print("=" * 55)

    print(f"Grid file: {grid_file}")
    print(f"Longitude variable: {lon_name}")
    print(f"Latitude variable:  {lat_name}")

    print("\nOriginal grid limits:")
    print(f"  West:  {region.west:.4f}")
    print(f"  East:  {region.east:.4f}")
    print(f"  South: {region.south:.4f}")
    print(f"  North: {region.north:.4f}")

    print(f"\nPadding: {region.padding:.2f} degrees")

    w, e, s, n = region.bounds

    print("\nDownload limits:")
    print(f"  West:  {w:.4f}")
    print(f"  East:  {e:.4f}")
    print(f"  South: {s:.4f}")
    print(f"  North: {n:.4f}")

    print("=" * 55 + "\n")

    return region


# ============================================================
# 3. ARGUMENT PARSER
# ============================================================

def add_region_arguments(parser):
    """
    Add geographical arguments to an argparse parser.

    Users must provide either:

    --grid-file

    OR

    --west --east --south --north

    These methods cannot be combined.
    """

    group = parser.add_mutually_exclusive_group(
        required=False
    )

    group.add_argument(
        "--grid-file",
        type=str,
        default=None,
        help=(
            "NetCDF grid file. Geographical limits are "
            "automatically calculated from its coordinates."
        ),
    )

    group.add_argument(
        "--west",
        type=float,
        default=None,
        help="Western longitude limit (degrees).",
    )

    parser.add_argument(
        "--east",
        type=float,
        default=None,
        help="Eastern longitude limit (degrees).",
    )

    parser.add_argument(
        "--south",
        type=float,
        default=None,
        help="Southern latitude limit (degrees).",
    )

    parser.add_argument(
        "--north",
        type=float,
        default=None,
        help="Northern latitude limit (degrees).",
    )

    parser.add_argument(
        "--padding",
        type=float,
        default=1.0,
        help=(
            "Additional geographical margin in degrees "
            "(default: 1)."
        ),
    )


# ============================================================
# 4. BUILD REGION
# ============================================================

def get_region(args):
    """
    Build and validate a Region from parsed arguments.

    Automatically detects whether the user provided
    a grid file or manual geographical limits.
    """

    grid_file = getattr(
        args,
        "grid_file",
        None
    )

    if grid_file is not None:

        extra_manual = [
            name
            for name in ("east", "south", "north")
            if getattr(args, name, None) is not None
        ]

        if extra_manual:
            raise ValueError(
                "Do not combine --grid-file with manual "
                "geographical limits."
            )

        return region_from_grid(
            grid_file=grid_file,
            padding=args.padding,
        )

    # --------------------------------------------------------
    # Manual region
    # --------------------------------------------------------

    required = (
        "west",
        "east",
        "south",
        "north"
    )

    missing = [
        name
        for name in required
        if getattr(args, name, None) is None
    ]

    if missing:
        raise ValueError(
            "Provide --grid-file or all four manual limits: "
            "--west --east --south --north. "
            f"Missing: {', '.join(missing)}"
        )

    return Region(
        west=args.west,
        east=args.east,
        south=args.south,
        north=args.north,
        padding=args.padding,
    )


# ============================================================
# 5. STANDALONE TEST
# ============================================================

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description=(
            "Calculate geographical download limits "
            "from manual coordinates or a NetCDF grid."
        )
    )

    add_region_arguments(parser)

    args = parser.parse_args()

    region = get_region(args)

    print("Final geographical bounds:")
    print(
        "West={:.4f}, East={:.4f}, "
        "South={:.4f}, North={:.4f}".format(
            *region.bounds
        )
    )
