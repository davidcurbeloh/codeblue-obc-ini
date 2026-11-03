# CodeBlue — oceanographic data download and visualization

Tools developed within the **CodeBlue project (Ifremer, DYNECO–PELAGOS)** to download regional physical and biogeochemical data and assess their spatial, vertical and temporal variability near ocean-model boundaries.

The repository includes:
- Download scripts for **Copernicus Marine BGC**, **World Ocean Atlas 2023 (WOA23)** and **ORAS5**.
- An interactive Jupyter notebook comparing CMEMS and WOA23 in user-selected domains and boundary bands.
- An exported **MANGAE–Ifremer example** (static HTML), when available.

> **Scope:** These tools retrieve and visualize external datasets. They do **not** directly generate CROCO initial or open-boundary condition files. Additional interpolation and processing are needed.

## Data products

| Product | Variables | Time resolution | Files |
| --- | --- | --- | --- |
| Copernicus Marine BGC | `no3`, `po4`, `si`, `o2` | **Monthly** | `data/CMEMS/YYYY/BGC_monthly_YYYYMM.nc` |
| WOA23 | `no3`, `po4`, `si`, `o2` | 12 monthly climatologies + annual | `data/WOA/WOA_01.nc` … `WOA_12.nc`, `WOA_ANNUAL.nc` |
| ORAS5 | Potential temperature, salinity, U/V velocities, SSH | Monthly | `data/ORAS5/YYYY/ORAS5_YYYYMM.nc` |

**CMEMS product:** `cmems_mod_glo_bgc_my_0.25deg_P1M-m` (monthly means on a 0.25° grid). Its available dates depend on the provider.

**WOA23 coverage:** monthly nutrients extend to approximately 800 m, monthly oxygen to approximately 1500 m; annual climatologies extend to approximately 5500 m. WOA23 monthly and annual fields are separate products, and the downloader does not vertically extrapolate them.

**ORAS5:** retains the product's native horizontal grid and does not regrid its variables onto a CROCO mesh.

## Installation

```bash
git clone https://github.com/davidcurbeloh/codeblue-obc-ini.git
cd codeblue-obc-ini
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

The interactive notebook additionally requires packages such as `ipywidgets`, `dask`, `shapely`, `pyproj` and `cartopy`. Install these in the notebook's Python environment if not already present:

```bash
python -m pip install ipywidgets dask shapely pyproj cartopy
```

Use a Python version compatible with the installed scientific libraries. The download services may require credentials: Copernicus Marine Toolbox for CMEMS and CDS API access for ORAS5; WOA23 is publicly accessible.

## Geographic selection: manual coordinates or CROCO grid

All three downloaders share `download/region.py`. You can choose **one** geographic input method:

1. `--west`, `--east`, `--south`, `--north`: the original model-domain bounds, in decimal degrees; **or**
2. `--grid-file /path/to/croco_grd.nc`: determine the enclosing geographic rectangle from longitude/latitude coordinates of the model grid (typically `lon_rho`/`lat_rho`).

By default, `--padding 1` extends the download rectangle by 1° on every side. This is a *download margin*, not necessarily the width of the visualization boundary bands. The current single-box procedure does not handle domains crossing the antimeridian.

For the MANGAE2500 example, the model rectangle is W −18°, E 9.5°, S 41°, N 55°; with a 1° margin the requested download region is W −19°, E 10.5°, S 40°, N 56°. For rotated/curvilinear meshes, the download box encloses the full grid; the notebook can use the actual grid edges for visualization.

## Download commands

Run commands from the repository root. Replace `/path/to/croco_grd.nc` with the grid of your own model. Add `--dry-run` to inspect the planned operation without downloading.

**Monthly CMEMS BGC:**

```bash
python download/download_cmems_bgc.py \
  --grid-file /path/to/croco_grd.nc --padding 1 \
  --start 1993-01 --end 1993-12 \
  --output ./data/CMEMS
```

**WOA23 monthly + annual climatologies:**

```bash
python download/download_woa23.py \
  --grid-file /path/to/croco_grd.nc --padding 1 \
  --output ./data/WOA
```

Omit `--month` to download all 13 climatologies, set `--month 1` … `12` to download one monthly climatology, or `--month 0` for the annual product.

**ORAS5 monthly fields:**

```bash
python download/download_oras5.py \
  --grid-file /path/to/croco_grd.nc --padding 1 \
  --start 1960-01 --end 1960-12 \
  --output ./data/ORAS5
```

ORAS5 retrieves large source fields before regional subsetting: allow sufficient temporary storage and first test a single month.

**Manual-coordinate alternative** (valid for any of the download commands):

```bash
--west -18 --east 9.5 --south 41 --north 55 --padding 1
```

Do not combine `--grid-file` and manual coordinates. Downloaded files are not intended to be committed to GitHub.

## Interactive visualization

Open **[CodeBlue_OBC_BGC_Visualization.ipynb](visualization/CodeBlue_OBC_BGC_Visualization.ipynb)** in JupyterLab. Detailed guidance is in **[visualization/README.md](visualization/README.md)**.

In the notebook, set the **model/visualization geometry independently of the downloaded-data extent**: enter the *unpadded* original domain rectangle or read a CROCO NetCDF grid. Select the active boundaries (e.g. North/South/West), define the sampling-band width, and optionally exclude Mediterranean cells using the regional mask (approximate polygon; inspect it for your domain). The notebook includes maps, vertical profiles, seasonal climatologies, time series, and Hovmöller diagrams.

Before 1993, combined historical displays repeat WOA23 monthly climatology in the depths where it exists, and otherwise use WOA23 annual climatology. These repeated climatologies **are not interannual historical reconstructions**; CMEMS monthly data are used from 1993 onward as available.

**[View the MANGAE–Ifremer example in your browser (HTML, GitHub Pages)](https://davidcurbeloh.github.io/codeblue-obc-ini/visualization/CodeBlue_OBC_BGC_Visualization_MANGAE-Ifremer_example.html)** — static notebook export with figures and results. This link opens the rendered HTML page, not GitHub's source-file preview. The GitHub Pages deployment must be enabled for `main` / `(root)`.

## Repository layout

```text
codeblue-obc-ini/
├── README.md
├── requirements.txt
├── download/
│   ├── region.py
│   ├── download_cmems_bgc.py
│   ├── download_woa23.py
│   └── download_oras5.py
└── visualization/
    ├── README.md
    ├── CodeBlue_OBC_BGC_Visualization.ipynb
    └── CodeBlue_OBC_BGC_Visualization_MANGAE-Ifremer_example.html
```

## Data sources and credits

- [Copernicus Marine Service](https://marine.copernicus.eu/) — global BGC reanalysis.
- [NOAA World Ocean Atlas 2023](https://www.ncei.noaa.gov/products/world-ocean-atlas) — nutrient and oxygen climatologies.
- [ECMWF Copernicus Climate Data Store / ORAS5](https://cds.climate.copernicus.eu/datasets/reanalysis-oras5) — ocean reanalysis.

Acknowledge the original products and their applicable citation/licensing terms in scientific work.

**Initial development:** David Curbelo-Hernández · **Ifremer, DYNECO–PELAGOS** · **CodeBlue project**.

**License:** No license is currently specified in the repository. Reuse and redistribution remain subject to applicable institutional/project requirements; source-data licenses are set by the providers.
