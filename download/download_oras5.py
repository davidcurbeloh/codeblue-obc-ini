#!/usr/bin/env python3
"""Download monthly ORAS5 physics from ECMWF CDS.

https://cds.climate.copernicus.eu/datasets/reanalysis-oras5?tab=overview

Variables:
    votemper : Potential temperature
    vosaline : Salinity
    vozocrtx : Zonal velocity
    vomecrty : Meridional velocity
    sossheig : Sea surface height

Global archives are downloaded temporarily.
Native T/U/V grids are cropped separately.
"""

import argparse
import os
import shutil
import tarfile
import tempfile
import time
import zipfile

from pathlib import Path

import numpy as np
import xarray as xr

from region import add_region_arguments, get_region


DATASET = "reanalysis-oras5"

FIELDS = [
    ("potential_temperature", "votemper", "all_levels"),
    ("salinity", "vosaline", "all_levels"),
    ("zonal_velocity", "vozocrtx", "all_levels"),
    ("meridional_velocity", "vomecrty", "all_levels"),
    ("sea_surface_height", "sossheig", "single_level"),
]


def parse_month(value):
    """Parse dates in YYYY-MM format."""

    try:
        year, month = map(int, value.split("-"))

        if year < 1958 or not 1 <= month <= 12:
            raise ValueError

        return year, month

    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Expected YYYY-MM, year >= 1958"
        ) from exc


def months(start, end):
    """Iterate over months in an inclusive interval."""

    year, month = start

    while (year, month) <= end:

        yield year, month

        month += 1

        if month == 13:
            year += 1
            month = 1


def unpack(archive, folder):
    """Extract NetCDF files from a CDS archive."""

    folder.mkdir(exist_ok=True)

    if zipfile.is_zipfile(archive):

        with zipfile.ZipFile(archive) as file:

            for member in file.infolist():

                dest = (
                    folder / member.filename
                ).resolve()

                if not dest.is_relative_to(
                    folder.resolve()
                ):
                    raise ValueError(
                        "Unsafe ZIP member"
                    )

            file.extractall(folder)

    elif tarfile.is_tarfile(archive):

        with tarfile.open(archive) as file:
            file.extractall(
                folder,
                filter="data"
            )

    else:

        shutil.copy2(
            archive,
            folder / "field.nc"
        )

    files = list(folder.rglob("*.nc"))

    if not files:
        raise RuntimeError(
            f"No NetCDF in {archive}"
        )

    return files


def crop_native(ds, bounds):
    """Crop an ORAS5 native grid to the selected region."""

    coordinate_pairs = [
        ("nav_lat", "nav_lon"),
        ("latitude", "longitude"),
        ("lat", "lon"),
    ]

    for latkey, lonkey in coordinate_pairs:

        if latkey in ds and lonkey in ds:
            lat = ds[latkey]
            lon = ds[lonkey]
            break

    else:
        raise ValueError(
            "No geographic coordinates found"
        )

    west, east, south, north = bounds

    longitude = ((lon + 180) % 360) - 180

    mask = (
        (lat >= south)
        & (lat <= north)
        & (longitude >= west)
        & (longitude <= east)
    )

    if lat.ndim == 2:

        rows, cols = np.where(mask.values)

        if not len(rows):
            raise ValueError(
                "Selected region contains no grid points"
            )

        d0, d1 = lat.dims

        region = {
            d0: slice(rows.min(), rows.max() + 1),
            d1: slice(cols.min(), cols.max() + 1),
        }

        trimmed = ds.isel(region)

        return trimmed.where(
            mask.isel(region)
        )

    if lat.ndim == lon.ndim == 1:

        return ds.where(
            mask,
            drop=True
        )

    raise ValueError(
        "Unexpected coordinate dimensions"
    )


def obtain(
    client,
    year,
    month,
    name,
    variable,
    levels,
    scratch,
    bounds
):
    """Download and crop one ORAS5 variable."""

    archive = scratch / f"{variable}.download"

    folder = scratch / f"{variable}_files"

    request = {
        "product_type": (
            "consolidated"
            if year <= 2014
            else "operational"
        ),
        "vertical_resolution": levels,
        "variable": [name],
        "year": str(year),
        "month": f"{month:02d}",
    }

    print("CDS", request, flush=True)

    for attempt in range(1, 4):

        try:
            archive.unlink(missing_ok=True)

            client.retrieve(
                DATASET,
                request,
                str(archive)
            )

            break

        except Exception as exc:

            if attempt == 3:
                raise

            print(
                f"RETRY {attempt}: {exc}",
                flush=True
            )

            time.sleep(attempt * 45)

    files = unpack(
        archive,
        folder
    )

    matches = []

    for path in files:

        with xr.open_dataset(
            path,
            decode_times=False
        ) as ds:

            if variable in ds.data_vars:
                matches.append(path)

    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one field {variable}, "
            f"found {matches}"
        )

    with xr.open_dataset(
        matches[0],
        decode_times=False
    ) as ds:

        keep = [variable]

        for key in (
            "nav_lat",
            "nav_lon",
            "latitude",
            "longitude",
            "lat",
            "lon"
        ):
            if key in ds.variables:
                keep.append(key)

        cut = crop_native(
            ds[keep],
            bounds
        )

        # Preserve independent horizontal grids.
        rename = {
            d: f"{d}_{variable}"
            for d in cut.dims
            if d.lower() not in (
                "time",
                "time_counter",
                "depth",
                "deptht",
                "depthu",
                "depthv"
            )
        }

        for key in (
            "nav_lat",
            "nav_lon",
            "latitude",
            "longitude",
            "lat",
            "lon"
        ):
            if key in cut.variables:
                rename[key] = f"{key}_{variable}"

        # Avoid renaming a dimension twice.
        rename = {
            key: value
            for key, value in rename.items()
            if key in cut.variables or key in cut.dims
        }

        cut = cut.rename(rename).load()

    shutil.rmtree(folder)

    archive.unlink(missing_ok=True)

    return cut


def valid(path, year, month, bounds):
    """Validate a downloaded monthly NetCDF."""

    if not path.is_file():
        return False

    if path.stat().st_size == 0:
        return False

    try:

        with xr.open_dataset(
            path,
            decode_times=False
        ) as ds:

            for _, variable, _ in FIELDS:

                if variable not in ds.data_vars:
                    return False

                if ds[variable].size == 0:
                    return False

            if ds.attrs.get("download_year") != year:
                return False

            if ds.attrs.get("download_month") != month:
                return False

            keys = (
                "west",
                "east",
                "south",
                "north"
            )

            saved_bounds = [
                ds.attrs.get(k)
                for k in keys
            ]

            return saved_bounds == list(bounds)

    except Exception:
        return False


def main():

    parser = argparse.ArgumentParser(
        description=__doc__
    )

    add_region_arguments(parser)

    parser.add_argument(
        "--start",
        type=parse_month,
        required=True
    )

    parser.add_argument(
        "--end",
        type=parse_month,
        required=True
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("./data/ORAS5")
    )

    parser.add_argument(
        "--dry-run",
        action="store_true"
    )

    args = parser.parse_args()

    if args.start > args.end:
        parser.error(
            "--start must not be after --end"
        )

    bounds = get_region(args).bounds

    if not args.dry_run:

        import cdsapi

        client = cdsapi.Client()

    for year, month in months(
        args.start,
        args.end
    ):

        target = (
            args.output
            / str(year)
            / f"ORAS5_{year}{month:02d}.nc"
        )

        print(
            f"\nTARGET {target}; BOUNDS {bounds}",
            flush=True
        )

        if args.dry_run:
            continue

        target.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        if valid(
            target,
            year,
            month,
            bounds
        ):
            print(
                "SKIP valid",
                target,
                flush=True
            )
            continue

        with tempfile.TemporaryDirectory(
            prefix=".oras5_",
            dir=target.parent
        ) as tmpdir:

            scratch = Path(tmpdir)

            parts = [
                obtain(
                    client,
                    year,
                    month,
                    name,
                    variable,
                    levels,
                    scratch,
                    bounds
                )
                for name, variable, levels in FIELDS
            ]

            merged = xr.merge(
                parts,
                compat="override",
                join="outer"
            )

            merged.attrs.update(
                source=DATASET,
                download_year=year,
                download_month=month,
                west=bounds[0],
                east=bounds[1],
                south=bounds[2],
                north=bounds[3],
                grid="ORAS5 native tripolar",
                cadence="monthly mean"
            )

            temporary = scratch / "output.nc"

            encoding = {
                variable: {
                    "zlib": True,
                    "complevel": 3
                }
                for _, variable, _ in FIELDS
            }

            merged.to_netcdf(
                temporary,
                encoding=encoding
            )

            if not valid(
                temporary,
                year,
                month,
                bounds
            ):
                raise RuntimeError(
                    f"Invalid output NetCDF: {temporary}"
                )

            os.replace(
                temporary,
                target
            )

            size_mb = (
                target.stat().st_size / 1024**2
            )

            print(
                "SUCCESS",
                target,
                f"{size_mb:.1f} MiB",
                flush=True
            )


if __name__ == "__main__":
    main()
