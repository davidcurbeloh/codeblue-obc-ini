#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
===========================================
CodeBlue - Copernicus Marine BGC downloader
===========================================

Download daily biogeochemical fields for a user-defined region.

Dataset:
    GLOBAL_MULTIYEAR_BGC_001_029
    cmems_mod_glo_bgc_my_0.25deg_P1D-m
    https://data.marine.copernicus.eu/product/GLOBAL_MULTIYEAR_BGC_001_029/description
    
Variables:
    no3 : Nitrate
    po4 : Phosphate
    si  : Silicate
    o2  : Dissolved oxygen

Features:
    - User-defined geographic boundaries
    - Automatic 1-degree padding
    - User-defined start and end months
    - One NetCDF file per month
    - Annual output directories
    - Validation of existing files
    - Download retries
    - No HPC-specific configuration

Example (MANGAE-Ifremer):
    python download/download_cmems_bgc.py \
        --west -18 --east 9.5 \
        --south 41 --north 55 \
        --start 1993-01 --end 1993-12 \
        --output ./data/CMEMS
"""

import argparse
import calendar
import logging
import time

from pathlib import Path

import copernicusmarine
import xarray as xr

from region import add_region_arguments, get_region


# ============================================================
# 1. DATASET CONFIGURATION
# ============================================================

DATASET_ID = "cmems_mod_glo_bgc_my_0.25deg_P1D-m"

VARIABLES = [
    "no3",
    "po4",
    "si",
    "o2",
]

MAX_RETRIES = 3

RETRY_DELAY = 30


# ============================================================
# 2. LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("codeblue-cmems")


# ============================================================
# 3. DATE FUNCTIONS
# ============================================================

def parse_month(value):
    """Convert YYYY-MM into a year/month tuple."""

    try:
        year, month = map(int, value.split("-"))

        if year < 1 or not 1 <= month <= 12:
            raise ValueError

        return year, month

    except ValueError:
        raise argparse.ArgumentTypeError(
            "Dates must use YYYY-MM format."
        )


def iter_months(start, end):
    """Iterate over all months in an inclusive interval."""

    year, month = start

    while (year, month) <= end:

        yield year, month

        month += 1

        if month == 13:
            year += 1
            month = 1


# ============================================================
# 4. NETCDF VALIDATION
# ============================================================

def valid_file(path, year, month, bounds):
    """
    Check whether a monthly NetCDF is usable.

    Checks:
        - File exists and is not empty
        - All requested variables exist
        - Number of daily records matches the month
        - Geographic coordinates cover the requested area
    """

    if not path.is_file():
        return False

    if path.stat().st_size == 0:
        return False

    west, east, south, north = bounds

    try:

        with xr.open_dataset(path) as ds:

            # Check variables
            for variable in VARIABLES:

                if variable not in ds.data_vars:
                    return False

                if ds[variable].size == 0:
                    return False

            # Check daily time records
            expected_days = calendar.monthrange(
                year, month
            )[1]

            if ds.sizes.get("time", 0) != expected_days:
                return False

            dates = ds["time"].dt

            if not bool((dates.year == year).all().item()):
                return False

            if not bool((dates.month == month).all().item()):
                return False

            # Check geographic coordinates
            if "latitude" not in ds.coords:
                return False

            if "longitude" not in ds.coords:
                return False

            lat = ds["latitude"].values
            lon = ds["longitude"].values

            if lat.size == 0 or lon.size == 0:
                return False

            # Allow half a grid cell at the boundaries.
            tolerance = 0.26

            if abs(float(lat.min()) - south) > tolerance:
                return False

            if abs(float(lat.max()) - north) > tolerance:
                return False

            if abs(float(lon.min()) - west) > tolerance:
                return False

            if abs(float(lon.max()) - east) > tolerance:
                return False

        return True

    except Exception as exc:

        logger.warning(
            "Validation failed for %s: %s",
            path,
            exc,
        )

        return False


# ============================================================
# 5. DOWNLOAD ONE MONTH
# ============================================================

def download_month(
    year,
    month,
    bounds,
    output_dir,
):
    """Download one month of daily BGC data."""

    west, east, south, north = bounds

    year_dir = output_dir / str(year)

    year_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    filename = f"BGC_{year}{month:02d}.nc"

    target = year_dir / filename

    logger.info("=" * 60)
    logger.info("Processing %04d-%02d", year, month)
    logger.info("Output: %s", target)

    if valid_file(
        target,
        year,
        month,
        bounds,
    ):

        logger.info("SKIP: valid file already exists.")
        return

    last_day = calendar.monthrange(
        year, month
    )[1]

    start_date = f"{year}-{month:02d}-01T00:00:00"

    end_date = (
        f"{year}-{month:02d}-{last_day:02d}T23:59:59"
    )

    # Download to a temporary file first.
    # An incomplete download must never be accepted
    # as a finished monthly NetCDF.

    temporary_name = (
        f".BGC_{year}{month:02d}.incomplete.nc"
    )

    temporary_path = year_dir / temporary_name

    for attempt in range(1, MAX_RETRIES + 1):

        try:

            if temporary_path.exists():
                temporary_path.unlink()

            logger.info(
                "Download attempt %d/%d",
                attempt,
                MAX_RETRIES,
            )

            copernicusmarine.subset(
                dataset_id=DATASET_ID,
                variables=VARIABLES,
                minimum_longitude=west,
                maximum_longitude=east,
                minimum_latitude=south,
                maximum_latitude=north,
                start_datetime=start_date,
                end_datetime=end_date,
                output_directory=str(year_dir),
                output_filename=temporary_name,
                overwrite=True,
            )

            if not valid_file(
                temporary_path,
                year,
                month,
                bounds,
            ):

                raise RuntimeError(
                    "Downloaded NetCDF failed validation."
                )

            # Atomic replacement within the same directory.
            temporary_path.replace(target)

            size_mb = (
                target.stat().st_size / 1024**2
            )

            logger.info(
                "SUCCESS: %s (%.1f MB)",
                target,
                size_mb,
            )

            return

        except Exception as exc:

            logger.warning(
                "Attempt %d failed: %s",
                attempt,
                exc,
            )

            temporary_path.unlink(
                missing_ok=True
            )

            if attempt == MAX_RETRIES:
                raise

            time.sleep(RETRY_DELAY * attempt)


# ============================================================
# 6. MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Download daily Copernicus Marine BGC "
            "data for a user-defined region."
        )
    )

    # Shared CodeBlue geographic arguments
    add_region_arguments(parser)

    parser.add_argument(
        "--start",
        required=True,
        type=parse_month,
        help="First month: YYYY-MM",
    )

    parser.add_argument(
        "--end",
        required=True,
        type=parse_month,
        help="Last month: YYYY-MM",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("./data/CMEMS"),
        help="Output directory (default: ./data/CMEMS)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Display planned downloads without downloading.",
    )

    args = parser.parse_args()

    if args.start > args.end:
        parser.error(
            "--start must be earlier than or equal to --end."
        )

    region = get_region(args)

    bounds = region.bounds

    logger.info("CodeBlue - Copernicus Marine BGC")
    logger.info("Dataset: %s", DATASET_ID)

    logger.info(
        "Original region: %s",
        (
            region.west,
            region.east,
            region.south,
            region.north,
        ),
    )

    logger.info(
        "Download region (+%.1f degrees): %s",
        region.padding,
        bounds,
    )

    logger.info("Variables: %s", VARIABLES)
    logger.info("Output: %s", args.output)

    for year, month in iter_months(
        args.start,
        args.end,
    ):

        if args.dry_run:

            logger.info(
                "DRY RUN: BGC_%04d%02d.nc",
                year,
                month,
            )

        else:

            download_month(
                year,
                month,
                bounds,
                args.output,
            )

    logger.info("Processing completed.")


if __name__ == "__main__":
    main()
