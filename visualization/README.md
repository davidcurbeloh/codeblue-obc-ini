# CodeBlue — OBC/BGC visualization notebook

This folder contains the interactive analysis notebook:

- **[CodeBlue_OBC_BGC_Visualization.ipynb](CodeBlue_OBC_BGC_Visualization.ipynb)** — configure a study domain and active model boundaries; compare monthly CMEMS BGC reanalysis against WOA23 climatologies.
- **[View MANGAE–Ifremer example (HTML, GitHub Pages)](https://davidcurbeloh.github.io/codeblue-obc-ini/visualization/CodeBlue_OBC_BGC_Visualization_MANGAE-Ifremer_example.html)** — open the static notebook export directly in your browser, with its figures and results. This is a read-only example, not an executable notebook.

> The interactive notebook requires downloaded data; the HTML example can be viewed without running Python, when the example file has been uploaded.

## 1. Prerequisites

Run from a cloned repository containing regional NetCDF products downloaded using the scripts in `../download/`. The notebook expects CMEMS files named `BGC_monthly_YYYYMM.nc` in yearly subdirectories and WOA23 monthly files `WOA_01.nc` … `WOA_12.nc` plus `WOA_ANNUAL.nc`.

Install the packages in the root `requirements.txt`, as well as notebook-specific dependencies `ipywidgets`, `dask`, `shapely`, `pyproj` and `cartopy`, in the selected Jupyter kernel. For a Conda setup, the following is an option:

```bash
conda install -c conda-forge jupyterlab ipywidgets dask shapely pyproj cartopy
```

Launch `jupyter lab` from the repository root and open the notebook under `visualization/`. On a remote HPC cluster, use the site's recommended Jupyter/SSH port-forwarding procedure.

## 2. Configure study geometry (Section 1)

**Download bounds and visualization/model bounds are different quantities.** A download typically includes extra padding, while the model's domain ends at its own perimeter.

In the first interactive panel, select either:
- **Manual model bounds:** input the *original unpadded* West/East/South/North coordinates, in degrees. For MANGAE2500: W −18, E 9.5, S 41, N 55.
- **NetCDF model grid:** provide the path to a `croco_grd.nc` file containing geographic grid coordinates such as `lon_rho` and `lat_rho`. This allows tilted or curvilinear perimeter lines.

Select which **open/active boundaries** to analyse (North, South, West and/or East). Unselected sides are excluded from the boundary-specific statistics and panels. MANGAE–Ifremer defaults to North/South/West (East unchecked). Choose a band *half-width* and its units (degrees or km). For the manual MANGAE example, ±1° is the intended analysis band.

The **Exclude Mediterranean Sea data** checkbox is enabled by default. The notebook applies an *approximate regional polygon* to the loaded CMEMS/WOA23 datasets, setting excluded cells to NaN in memory; it does not alter NetCDF files on disk. Review the resulting map, especially for domains outside the NE Atlantic or near the Strait of Gibraltar.

Click **Apply geometry** after changes. If you change the Mediterranean checkbox, rerun data loading (Section 2) before recomputing analyses.

## 3. Load and inspect data (Sections 2–3)

The notebook reads the regionally downloaded CMEMS and WOA23 products (adjust input directory paths if necessary). Confirm that the selected NetCDFs cover the complete model region **and the analysis bands**.

Use the domain/map figure to check:
- The true **model perimeter**, not the padded download rectangle.
- The full **CMEMS download coverage**.
- Which boundary bands are active.
- Which grid cells are excluded by the Mediterranean mask.

If a band falls outside the downloaded products, its statistics will have missing coverage; enlarge and redownload the source region rather than extrapolating.

## 4. Analysis sections

The interactive notebook provides:
- CMEMS and WOA23 monthly climatology maps and CMEMS–WOA23 anomalies.
- Vertical profiles of nitrate, phosphate, silicate and dissolved oxygen with spatial-variability bands.
- Time–depth seasonal Hovmöller diagrams and seasonal climatology comparisons.
- Boundary-layer time series with mean ± standard deviation for user-selected variables, depth intervals and dates.
- Continuous-display Hovmöller diagrams combining climatological WOA23 (pre-1993) and monthly CMEMS (1993 onward).

Choose variables, calendar months, start/end dates, and depth ranges using the panels; press the plot/generate buttons to refresh figures. Re-run downstream cells after modifying active boundaries. Subplots should only represent selected boundaries.

### How the WOA23/CMEMS combination works

| Period | Source | Interpretation |
| --- | --- | --- |
| Before 1993, nutrient depths within ~0–800 m | WOA23 monthly climatology repeated by year | Seasonal reference, **no year-to-year variability** |
| Before 1993, oxygen depths within ~0–1500 m | WOA23 monthly climatology repeated by year | Seasonal reference, **no year-to-year variability** |
| Before 1993, deeper levels where monthly WOA23 is unavailable | WOA23 annual climatology repeated by month | Annual reference, **no seasonal cycle** |
| From 1993 onward (available months) | CMEMS monthly reanalysis | Actual reanalysis temporal variability |

No vertical extrapolation should be inferred from the displayed panels. Always check depth coverage and missing values.

## 5. Example, limitations and reproducibility

**[Open the MANGAE–Ifremer HTML example in your browser](https://davidcurbeloh.github.io/codeblue-obc-ini/visualization/CodeBlue_OBC_BGC_Visualization_MANGAE-Ifremer_example.html)** to inspect the notebook's rendered outputs. GitHub's normal file view may show “View raw” for large HTML files; use the GitHub Pages URL above instead. If Pages is unavailable, [download the HTML source](https://github.com/davidcurbeloh/codeblue-obc-ini/raw/refs/heads/main/visualization/CodeBlue_OBC_BGC_Visualization_MANGAE-Ifremer_example.html) and open it locally.

- Boundary statistics describe a band near the model perimeter, not values interpolated directly onto CROCO open-boundary points.
- In curved grids, inspect whether the selected edges are genuinely open and whether halo/land cells are present.
- The Mediterranean polygon is approximate and primarily tailored to a NE Atlantic setting.
- WOA23 pre-1993 repetition is a display/reference convention, not a historical hindcast.
- Keep large NetCDF data outside GitHub; share the scripts, configuration and reproducible examples instead.

See the [repository README](../README.md) for downloading and attribution.
