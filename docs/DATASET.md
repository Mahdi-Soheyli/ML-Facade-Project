# E1300 research dataset

This repository builds **`E1300_Research_Dataset.csv`** from a deterministic implementation of **ASTM E1300-24** load-resistance logic (Section 7, Tables 1–7, Annex A1–A2 context).

## What is modeled

- **Tables** in `building_code/e1300_data/`: Table 4 minimum thicknesses, GTF (Tables 1, 2, 3, 7), LSF (Tables 5–6), chart-to-figure mapping (`chart_catalog.json`).
- **LR** for single lites, double IG, and triple IG using Section 7.2 formulas (`LR = NFL × GTF ÷ LSF` for IG lites), including Table 6 for long-duration **monolithic + laminated** pairs where applicable.
- **NFL (non-factored load)** uses a **smooth surrogate** calibrated so Annex A3 numerical examples match within stated test tolerances. The **official** method is graphical lookup on **Figs. A1.1–A1.44** in the standard; raster exports are saved under `building_code/e1300_data/chart_images/` (see `tools/extract_chart_images.py`).

## Columns (CSV)

- **`case`**: `single_monolithic`, `double_ig_momo`, `double_ig_molg`, `triple_ig`.
- **`short_m`, `long_m`**: rectangle dimensions (m); `long_m >= short_m`.
- **`support_family`**: default `monolithic_four_sides` (curtain-wall style four-side support).
- **Lite fields**: nominal keys (Table 4), glass type AN/HS/FT, construction monolithic vs laminated.
- **`design_load_kpa`**: assumed specified uniform lateral load for the `acceptable` label.
- **`governing_LR_kpa`**: computed load resistance for the case.
- **`acceptable`**: `governing_LR_kpa >= design_load_kpa`.

## Regenerate

```bash
pip install -r requirements.txt
python generate_data.py
```

The CSV writer uses the Python standard library only so generation does not depend on `pandas`.

## Tests

```bash
pip install pytest
pytest tests/test_annex_a3.py
```
