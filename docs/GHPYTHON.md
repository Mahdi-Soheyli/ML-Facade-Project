# Grasshopper GhPython client

Send a JSON payload to your Railway **public URL** + `/api/analyze`.

## Example (IronPython 2.7 compatible: use `urllib2`)

```python
import json
import urllib2

url = "https://YOUR-SERVICE.up.railway.app/api/analyze"
body = {
    "wind": {"v1_m_s": 17.56, "h1_m": 10, "z0_m": 0.4, "pressure_factor": 1.0},
    "panels": []
}

# Build one dict per glazing panel (match your DataTree branches)
body["panels"].append({
    "id": "floor_12_A",
    "width_m": 1.5,
    "height_m": 2.1,
    "elevation_m": 42.0,
    "case": "single_monolithic",
    "support_family": "monolithic_four_sides",
    "duration": "short",
    "lites": [{"glass": "AN", "construction": "monolithic"}]
})

req = urllib2.Request(url, json.dumps(body), {"Content-Type": "application/json"})
resp = urllib2.urlopen(req, timeout=60)
print(resp.read())
```

## CPython 3 in GhPython (if available)

Use `urllib.request` or `requests`.

## Response

Each panel includes:

- `wind.design_load_kpa` — dynamic pressure × `pressure_factor` at `elevation_m`.
- `oracle.governing_LR_kpa`, `oracle.acceptable`, `oracle.minimum_nominal_key` (when nominal omitted on single lites).
- `ml.predicted_nominal_key`, `ml.predicted_governing_LR_kpa` — KNN on oracle training rows.

Poll `GET /api/last` if you want the browser dashboard to mirror the last run without re-posting from the browser.
