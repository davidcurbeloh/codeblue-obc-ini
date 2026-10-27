#!/usr/bin/env python3
"""Download NOAA WOA23 monthly and annual BGC climatologies.

Reagan, James R.; Boyer, Tim P.; García, Hernán E.; Locarnini, Ricardo A.; Baranova, Olga K.; Bouchard, Courtney; Cross, Scott L.; 
Mishonov, Alexey V.; Paver, Christopher R.; Seidov, Dan; Wang, Zhankun; Dukhovskoy, Dmitry. (2024). World Ocean Atlas 2023. 
NOAA National Centers for Environmental Information. Dataset: NCEI Accession 0270533.

Oxygen: Garcia, H.E., Z. Wang, C. Bouchard, S.L. Cross, C.R. Paver, J.R. Reagan, T.P. Boyer, R.A. 
Locarnini, A.V. Mishonov, O. Baranova, D. Seidov, and D. Dukhovskoy (2024). World Ocean Atlas 2023, 
Volume 3: Dissolved Oxygen, Apparent Oxygen Utilization, and Oxygen Saturation. A. Mishonov, 
Tech. Ed. NOAA Atlas NESDIS 91, doi.org/10.25923/rb67-ns53

Nutrients: Garcia, H.E., C. Bouchard, S.L. Cross, C.R. Paver, Z. Wang, J.R. Reagan, T.P. Boyer, R.A. 
Locarnini, A.V. Mishonov, O. Baranova, D. Seidov, and D. Dukhovskoy (2024b). World Ocean Atlas 2023, 
Volume 4: Dissolved Inorganic Nutrients (phosphate, nitrate, silicate). A. Mishonov, 
Tech. Ed. NOAA Atlas NESDIS 92, doi.org/10.25923/39qw-7j08

Monthly:
    NO3, PO4, Si: 0-800 m
    O2:           0-1500 m

Annual:
    All variables: 0-5500 m

No vertical interpolation is performed.
"""

import argparse
import os
import tempfile
import time
from pathlib import Path
from urllib.request import Request, urlopen

import numpy as np
import xarray as xr

from region import add_region_arguments, get_region


BASE = "https://www.ncei.noaa.gov/data/oceans/woa/WOA23/DATA"

FIELDS = {
    "no3": ("nitrate", "n"),
    "po4": ("phosphate", "p"),
    "si": ("silicate", "i"),
    "o2": ("oxygen", "o"),
}


def url_for(variable, month):
    folder, code = FIELDS[variable]
    name = f"woa23_all_{code}{month:02d}_01.nc"
    return f"{BASE}/{folder}/netcdf/all/1.00/{name}"


def download(url, target):
    """Download a NOAA file with retries."""

    for attempt in range(1, 4):
        try:
            target.unlink(missing_ok=True)

            request = Request(
                url,
                headers={"User-Agent": "CodeBlue-data-workflows/1.0"}
            )

            with urlopen(request, timeout=180) as source:
                with target.open("wb") as dest:
                    while True:
                        block = source.read(2 * 1024 * 1024)
                        if not block:
                            break
                        dest.write(block)

            if target.stat().st_size == 0:
                raise RuntimeError("Empty download")

            return

        except Exception as exc:
            target.unlink(missing_ok=True)

            if attempt == 3:
                raise

            print(f"RETRY {attempt}: {exc}", flush=True)
            time.sleep(20 * attempt)


def subset_woa(path, variable, bounds):
    """Extract the user-defined region from a global WOA file."""

    code = FIELDS[variable][1]

    with xr.open_dataset(path, decode_times=False) as ds:

        field_name = code + "_an"

        if field_name not in ds:
            raise ValueError(
                f"Missing {field_name} in {path.name}"
            )

        da = ds[field_name]

        if "time" in da.dims:
            if da.sizes["time"] != 1:
                raise ValueError(
                    f"Expected one climatological time in {path.name}"
                )

            da = da.isel(time=0, drop=True)

        # Normalize longitude to -180..180.
        lon = ((da.lon + 180) % 360) - 180

        da = (
            da.assign_coords(lon=lon)
              .sortby("lon")
              .sortby("lat")
        )

        west, east, south, north = bounds

        da = da.sel(
            lon=slice(west, east),
            lat=slice(south, north)
        )

        if (
            da.sizes.get("lat", 0) == 0
            or da.sizes.get("lon", 0) == 0
        ):
            raise ValueError(
                f"Empty region for {path.name}: {bounds}"
            )

        return da.rename(variable).load()


def expected_depth(month, variable):
    """Expected maximum depth for each climatology."""

    if month == 0:
        return 5500

    return 1500 if variable == "o2" else 800


def valid(path, month, bounds):
    """Check an existing regional NetCDF."""

    if not path.is_file() or path.stat().st_size == 0:
        return False

    try:
        with xr.open_dataset(path) as ds:

            if not all(v in ds for v in FIELDS):
                return False

            expected_levels = 102 if month == 0 else 57

            if ds.sizes.get("depth") != expected_levels:
                return False

            if ds.attrs.get("climatology_month") != month:
                return False

            keys = ("west", "east", "south", "north")

            saved_bounds = [
                ds.attrs.get(k) for k in keys
            ]

            if saved_bounds != list(bounds):
                return False

            for variable in FIELDS:
                surface = ds[variable].isel(depth=0)

                if not bool(surface.notnull().any()):
                    return False

            return True

    except Exception:
        return False


def run_month(month, output, bounds, dry_run):
    """Download and prepare one climatology."""

    if month == 0:
        filename = "WOA_ANNUAL.nc"
    else:
        filename = f"WOA_{month:02d}.nc"

    target = output / filename

    print(
        f"\nMONTH={month:02d} "
        f"OUTPUT={target} "
        f"BOUNDS={bounds}",
        flush=True
    )

    for variable in FIELDS:
        print(
            f"  {variable}: {url_for(variable, month)}",
            flush=True
        )

    if dry_run:
        return

    output.mkdir(parents=True, exist_ok=True)

    if valid(target, month, bounds):
        print(f"SKIP {target}", flush=True)
        return

    with tempfile.TemporaryDirectory(
        prefix=".woa23_",
        dir=output
    ) as tmp:

        tmpdir = Path(tmp)
        pieces = []

        for variable in FIELDS:

            source = tmpdir / f"{variable}.nc"

            download(
                url_for(variable, month),
                source
            )

            field = subset_woa(
                source,
                variable,
                bounds
            )

            bottom = float(field.depth.max())

            if not np.isclose(
                bottom,
                expected_depth(month, variable)
            ):
                raise ValueError(
                    f"{variable}: unexpected deepest "
                    f"level {bottom} m"
                )

            pieces.append(field.to_dataset())

            source.unlink()

        # Combine native depths without interpolation.
        # Missing nutrient values below 800 m become NaN.
        result = xr.merge(
            pieces,
            join="outer",
            compat="no_conflicts"
        )

        expected_levels = 102 if month == 0 else 57

        if result.sizes.get("depth") != expected_levels:
            raise ValueError(
                "Unexpected combined vertical levels"
            )

        result.attrs.update(
            source="NOAA World Ocean Atlas 2023",
            climatology_month=month,
            climatology_type=(
                "annual" if month == 0 else "monthly"
            ),
            west=bounds[0],
            east=bounds[1],
            south=bounds[2],
            north=bounds[3],
            description=(
                "Monthly nutrients: 0-800 m; "
                "monthly oxygen: 0-1500 m; "
                "annual fields: 0-5500 m. "
                "No vertical interpolation."
            )
        )

        temporary = tmpdir / filename

        encoding = {
            v: {"zlib": True, "complevel": 3}
            for v in FIELDS
        }

        result.to_netcdf(
            temporary,
            encoding=encoding
        )

        if not valid(temporary, month, bounds):
            raise RuntimeError(
                f"Output failed validation: {temporary}"
            )

        os.replace(temporary, target)

        size_mb = target.stat().st_size / 1024**2

        print(
            f"SUCCESS {target} ({size_mb:.1f} MiB)",
            flush=True
        )


def main():

    parser = argparse.ArgumentParser(
        description=__doc__
    )

    add_region_arguments(parser)

    parser.add_argument(
        "--month",
        type=int,
        choices=range(13),
        help=(
            "0=annual, 1..12=monthly; "
            "omit to download all 13"
        )
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("./data/WOA")
    )

    parser.add_argument(
        "--dry-run",
        action="store_true"
    )

    args = parser.parse_args()

    bounds = get_region(args).bounds

    if args.month is None:
        selected_months = range(13)
    else:
        selected_months = [args.month]

    for month in selected_months:
        run_month(
            month,
            args.output,
            bounds,
            args.dry_run
        )


if __name__ == "__main__":
    main()
