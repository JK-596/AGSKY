"""
indices.py
----------
Calculates NDVI and NDWI from a cloud-free composite.
Generates a separate score for each of the 9 grid cells.


Pipeline:
    sentinel_fetch.py → cloud_mask.py → indices.py ✅

NDVI = (NIR - Red) / (NIR + Red)   [B8 - B4] / [B8 + B4]
NDWI = (Green - NIR) / (Green + NIR) [B3 - B8] / [B3 + B8]

Score Range:
    NDVI:  -1 to +1  (healthy crop: 0.4+, stressed: 0.2-0.4, bare soil: <0.2)
    NDWI:  -1 to +1  (water stress: <0, good moisture: 0+)

Test:
    python indices.py
"""

import ee
import sys
import os

sys.path.append(os.path.dirname(__file__))
from gee_auth import setup_gee
from grid_maker import calculate_grid
from sentinel_fetch import fetch_all
from cloud_mask import get_cloudless_composite


# ──────────────────────────────────────────────────
# INDEX CALCULATIONS
# ──────────────────────────────────────────────────

def calculate_ndvi(composite):
    """
    NDVI = (NIR - Red) / (NIR + Red)
    Healthy vegetation: > 0.4
    """
    ndvi = composite.normalizedDifference(['B8', 'B4']).rename('NDVI')
    return ndvi


def calculate_ndwi(composite):
    """
    NDWI = (Green - NIR) / (Green + NIR)
    Water content / moisture stress detect pannum.
    """
    ndwi = composite.normalizedDifference(['B3', 'B8']).rename('NDWI')
    return ndwi


def calculate_evi(composite):
    """
    EVI (Enhanced Vegetation Index)
    In Dense canopy areas will be NDVI saturate So EVI better.
    EVI = 2.5 * (NIR - Red) / (NIR + 6*Red - 7.5*Blue + 1)
    """
    evi = composite.expression(
        '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))',
        {
            'NIR':  composite.select('B8'),
            'RED':  composite.select('B4'),
            'BLUE': composite.select('B2')
        }
    ).rename('EVI')
    return evi


# ──────────────────────────────────────────────────
# CELL-WISE STATS
# ──────────────────────────────────────────────────

def get_cell_geometry(cell_bounds):
    """Cell bounds dict → ee.Geometry"""
    return ee.Geometry.Rectangle([
        cell_bounds['west'],
        cell_bounds['south'],
        cell_bounds['east'],
        cell_bounds['north']
    ])


def extract_cell_stats(index_image, cell_geometry, index_name, scale=10):
    """
    Calculates the mean index value for each cell.
    Sentinel-2 resolution: 10m (B4, B8) or 20m (B11, B12)
    """
    try:
        stats = index_image.reduceRegion(
            reducer   = ee.Reducer.mean(),
            geometry  = cell_geometry,
            scale     = scale,
            maxPixels = 1e9
        )
        value = stats.get(index_name).getInfo()
        if value is None:
            return None
        return round(value, 4)
    except Exception as e:
        print(f"    ⚠️  {index_name} extract error: {e}")
        return None


def build_cell_list(lat, lon, acres):
    """9 cells-oda bounds list will be returned."""
    start_lat, start_lon, sub_lat, sub_lon = calculate_grid(lat, lon, acres)

    labels = [
        ["SW", "S",      "SE"],
        ["W",  "CENTER", "E" ],
        ["NW", "N",      "NE"],
    ]

    cells = []
    for row in range(3):
        for col in range(3):
            cells.append({
                "label": labels[row][col],
                "bounds": {
                    "south": start_lat + row * sub_lat,
                    "north": start_lat + (row + 1) * sub_lat,
                    "west":  start_lon + col * sub_lon,
                    "east":  start_lon + (col + 1) * sub_lon,
                }
            })
    return cells


# ──────────────────────────────────────────────────
# INTERPRET SCORES
# ──────────────────────────────────────────────────

def interpret_ndvi(value):
    if value is None:
        return "No data"
    if value >= 0.6:
        return "🟢 Excellent — Healthy dense crop"
    elif value >= 0.4:
        return "🟡 Good — Moderate vegetation"
    elif value >= 0.2:
        return "🟠 Stressed — Check water/nutrients"
    elif value >= 0.0:
        return "🔴 Poor — Sparse / bare soil"
    else:
        return "⚫ Very low — Water body / no crop"


def interpret_ndwi(value):
    if value is None:
        return "No data"
    if value >= 0.3:
        return "💧 High moisture — Possible waterlogging"
    elif value >= 0.0:
        return "🟢 Good moisture — Adequate water"
    elif value >= -0.3:
        return "🟡 Mild stress — Irrigation check pannunga"
    else:
        return "🔴 Water stress — Urgent irrigation needed"


# ──────────────────────────────────────────────────
# MAIN FUNCTION
# ──────────────────────────────────────────────────

def calculate_all_indices(lat, lon, acres, days_back=20):
    """
    Full pipeline:
    fetch → cloud mask → NDVI/NDWI/EVI per cell → results dict

    Returns:
        list of dicts, one per cell:
        {
            label, bounds,
            ndvi, ndwi, evi,
            ndvi_status, ndwi_status
        }
    """
    print("\n" + "="*45)
    print("  AGSKY Indices Calculation Starting...")
    print("="*45)

    # Step 1: Fetch
    fetch_result = fetch_all(lat, lon, acres, days_back)

    # Step 2: Cloud mask
    composite = get_cloudless_composite(fetch_result, method='auto')

    if composite is None:
        print("❌ Composite failed — days_back increase pannunga")
        return None

    # Step 3: Calculate index images
    print("  📊 Calculating NDVI, NDWI, EVI...")
    ndvi_img = calculate_ndvi(composite)
    ndwi_img = calculate_ndwi(composite)
    evi_img  = calculate_evi(composite)

    # Step 4: Per-cell extraction
    cells = build_cell_list(lat, lon, acres)
    results = []

    print(f"  🔍 Extracting stats for 9 cells...\n")

    for cell in cells:
        label    = cell['label']
        geom     = get_cell_geometry(cell['bounds'])

        ndvi_val = extract_cell_stats(ndvi_img, geom, 'NDVI', scale=10)
        ndwi_val = extract_cell_stats(ndwi_img, geom, 'NDWI', scale=10)
        evi_val  = extract_cell_stats(evi_img,  geom, 'EVI',  scale=10)

        cell_result = {
            "label":       label,
            "bounds":      cell['bounds'],
            "ndvi":        ndvi_val,
            "ndwi":        ndwi_val,
            "evi":         evi_val,
            "ndvi_status": interpret_ndvi(ndvi_val),
            "ndwi_status": interpret_ndwi(ndwi_val),
        }
        results.append(cell_result)

        print(f"  [{label:^6}]  NDVI: {str(ndvi_val):>7}  {interpret_ndvi(ndvi_val)}")
        print(f"           NDWI: {str(ndwi_val):>7}  {interpret_ndwi(ndwi_val)}")
        print(f"           EVI : {str(evi_val):>7}")
        print()

    print("="*45)
    print("  ✅ All 9 cells processed!")
    print("  📤 Next: Pass to crop_stress.py")
    print("="*45 + "\n")

    return results


# ──────────────────────────────────────────────────
# STANDALONE TEST
# ──────────────────────────────────────────────────

if __name__ == "__main__":
    print("Starting indices.py test...")

    if not setup_gee():
        print("❌ GEE auth failed.")
        sys.exit(1)

    results = calculate_all_indices(
        lat      = 11.0168,
        lon      = 76.9558,
        acres    = 5.0,
        days_back= 20
    )

    if results:
        print("\n📋 SUMMARY TABLE")
        print(f"  {'Cell':^8} {'NDVI':>8} {'NDWI':>8} {'EVI':>8}")
        print("  " + "-"*36)
        for r in results:
            ndvi = f"{r['ndvi']:.4f}" if r['ndvi'] is not None else "  None"
            ndwi = f"{r['ndwi']:.4f}" if r['ndwi'] is not None else "  None"
            evi  = f"{r['evi']:.4f}"  if r['evi']  is not None else "  None"
            print(f"  {r['label']:^8} {ndvi:>8} {ndwi:>8} {evi:>8}")

        print("\n✅ indices.py test passed!")
        print("   Next: Run crop_stress.py")
    else:
        print("❌ indices.py failed — cloud_mask.py output should be checked")