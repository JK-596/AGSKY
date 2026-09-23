"""
grid_analyzer.py
----------------
The indices.py output is integrated into a 9-cell grid structure.

For each cell, it performs relative comparisons and classifies the zone based on stress levels.

Pipeline:
    sentinel_fetch → cloud_mask → indices → grid_analyzer ✅

Output:
    {
        "grid": { "CENTER": {...}, "N": {...}, ... },
        "summary": { best_cell, worst_cell, avg_ndvi, ... },
        "zones": { "critical": [...], "good": [...], ... }
    }

Test:
    python grid_analyzer.py
"""

import sys
import os

# Same folder — satellite data/ la irukrom
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from gee_auth import setup_gee
from indices import calculate_all_indices


# ──────────────────────────────────────────────────
# GRID STRUCTURE BUILD
# ──────────────────────────────────────────────────

def build_grid_map(indices_results):
    """
    indices.py list output → label-keyed dict.
    { "CENTER": {ndvi, ndwi, evi, ...}, "N": {...}, ... }
    """
    grid = {}
    for cell in indices_results:
        grid[cell['label']] = cell
    return grid


# ──────────────────────────────────────────────────
# RELATIVE ANALYSIS
# ──────────────────────────────────────────────────

def calculate_summary(grid):
    """
    Grid-wide stats:
    - Average NDVI / NDWI / EVI
    - Best / worst cell
    - Overall farm health score (0-100)
    """
    ndvi_vals = {k: v['ndvi'] for k, v in grid.items() if v['ndvi'] is not None}
    ndwi_vals = {k: v['ndwi'] for k, v in grid.items() if v['ndwi'] is not None}
    evi_vals  = {k: v['evi']  for k, v in grid.items() if v['evi']  is not None}

    if not ndvi_vals:
        return None

    avg_ndvi = round(sum(ndvi_vals.values()) / len(ndvi_vals), 4)
    avg_ndwi = round(sum(ndwi_vals.values()) / len(ndwi_vals), 4)
    avg_evi  = round(sum(evi_vals.values())  / len(evi_vals),  4)

    best_cell  = max(ndvi_vals, key=ndvi_vals.get)
    worst_cell = min(ndvi_vals, key=ndvi_vals.get)

    # Farm health score: NDVI 0-1 → 0-100 scale
    # Healthy crop = 0.6+ NDVI → 100 score
    health_score = min(100, round((avg_ndvi / 0.6) * 100, 1))

    return {
        "avg_ndvi":     avg_ndvi,
        "avg_ndwi":     avg_ndwi,
        "avg_evi":      avg_evi,
        "best_cell":    best_cell,
        "worst_cell":   worst_cell,
        "health_score": health_score,
        "cell_count":   len(ndvi_vals)
    }


# ──────────────────────────────────────────────────
# ZONE CLASSIFICATION
# ──────────────────────────────────────────────────

def classify_zones(grid):
    """
    Each cell-ah 4 zones-la classify pannum:
    - critical  : NDVI < 0.2  (urgent attention needed)
    - stressed  : NDVI 0.2-0.4 (monitor closely)
    - healthy   : NDVI 0.4-0.6 (good condition)
    - excellent : NDVI > 0.6  (thriving)
    """
    zones = {
        "critical":  [],
        "stressed":  [],
        "healthy":   [],
        "excellent": []
    }

    for label, cell in grid.items():
        ndvi = cell.get('ndvi')
        if ndvi is None:
            continue
        if ndvi < 0.2:
            zones["critical"].append(label)
        elif ndvi < 0.4:
            zones["stressed"].append(label)
        elif ndvi < 0.6:
            zones["healthy"].append(label)
        else:
            zones["excellent"].append(label)

    return zones


def classify_water_zones(grid):
    """
    NDWI-based water stress zones:
    - drought   : NDWI < -0.3
    - dry       : -0.3 to 0.0
    - moist     : 0.0 to 0.3
    - saturated : > 0.3
    """
    water_zones = {
        "drought":   [],
        "dry":       [],
        "moist":     [],
        "saturated": []
    }

    for label, cell in grid.items():
        ndwi = cell.get('ndwi')
        if ndwi is None:
            continue
        if ndwi < -0.3:
            water_zones["drought"].append(label)
        elif ndwi < 0.0:
            water_zones["dry"].append(label)
        elif ndwi < 0.3:
            water_zones["moist"].append(label)
        else:
            water_zones["saturated"].append(label)

    return water_zones


# ──────────────────────────────────────────────────
# CELL DEVIATION (relative to farm average)
# ──────────────────────────────────────────────────

def calculate_deviation(grid, summary):
    """
    Each cell-oda NDVI — farm average = deviation.
    Positive = above average (better zone)
    Negative = below average (problem zone)
    """
    avg = summary['avg_ndvi']
    deviations = {}

    for label, cell in grid.items():
        if cell['ndvi'] is not None:
            dev = round(cell['ndvi'] - avg, 4)
            deviations[label] = {
                "deviation":  dev,
                "relative":   "above average" if dev > 0.05
                              else "below average" if dev < -0.05
                              else "near average"
            }
    return deviations


# ──────────────────────────────────────────────────
# PRINT GRID (Visual terminal output)
# ──────────────────────────────────────────────────

def print_grid_visual(grid, zones):
    """
    Terminal-la 3x3 grid visual print pannum.
    Color code: zone type based.
    """
    zone_symbol = {}
    for label in grid:
        if label in zones['critical']:   zone_symbol[label] = '🔴'
        elif label in zones['stressed']: zone_symbol[label] = '🟠'
        elif label in zones['healthy']:  zone_symbol[label] = '🟡'
        else:                            zone_symbol[label] = '🟢'

    layout = [
        ["NW", "N",      "NE"],
        ["W",  "CENTER", "E" ],
        ["SW", "S",      "SE"],
    ]

    print("\n  📍 FARM GRID (North = Top)")
    print("  ┌─────────┬─────────┬─────────┐")
    for i, row in enumerate(layout):
        row_str = "  │"
        for label in row:
            sym  = zone_symbol.get(label, '⬜')
            ndvi = grid[label]['ndvi']
            val  = f"{ndvi:.2f}" if ndvi is not None else " N/A"
            row_str += f" {sym}{label:^5}{val} │"
        print(row_str)
        if i < 2:
            print("  ├─────────┼─────────┼─────────┤")
    print("  └─────────┴─────────┴─────────┘")
    print("  🔴 Critical  🟠 Stressed  🟡 Healthy  🟢 Excellent\n")


# ──────────────────────────────────────────────────
# MAIN FUNCTION
# ──────────────────────────────────────────────────

def analyze_grid(lat, lon, acres, days_back=20):
    """
    Full grid analysis pipeline.
    Returns complete analysis dict for crop_stress.py.
    """
    print("\n" + "="*45)
    print("  AGSKY Grid Analyzer Starting...")
    print("="*45)

    # Step 1: Get indices
    indices_results = calculate_all_indices(lat, lon, acres, days_back)
    if not indices_results:
        print("❌ Indices calculation failed")
        return None

    # Step 2: Build grid map
    grid = build_grid_map(indices_results)

    # Step 3: Summary stats
    summary = calculate_summary(grid)
    if not summary:
        print("❌ Summary calculation failed")
        return None

    # Step 4: Zone classification
    zones       = classify_zones(grid)
    water_zones = classify_water_zones(grid)
    deviations  = calculate_deviation(grid, summary)

    # Step 5: Visual print
    print_grid_visual(grid, zones)

    # Step 6: Print summary
    print(f"  🌾 Farm Health Score : {summary['health_score']}/100")
    print(f"  📊 Avg NDVI          : {summary['avg_ndvi']}")
    print(f"  💧 Avg NDWI          : {summary['avg_ndwi']}")
    print(f"  🏆 Best Cell         : {summary['best_cell']}")
    print(f"  ⚠️  Worst Cell        : {summary['worst_cell']}")
    print()
    print(f"  🔴 Critical zones    : {zones['critical']  or 'None'}")
    print(f"  🟠 Stressed zones    : {zones['stressed']  or 'None'}")
    print(f"  🟡 Healthy zones     : {zones['healthy']   or 'None'}")
    print(f"  🟢 Excellent zones   : {zones['excellent'] or 'None'}")
    print()
    print(f"  🏜️  Drought zones     : {water_zones['drought']   or 'None'}")
    print(f"  🌵 Dry zones         : {water_zones['dry']        or 'None'}")
    print(f"  💧 Moist zones       : {water_zones['moist']      or 'None'}")

    print("\n  ✅ Grid analysis complete!")
    print("  📤 Next: Pass to crop_stress.py")
    print("="*45 + "\n")

    return {
        "grid":        grid,
        "summary":     summary,
        "zones":       zones,
        "water_zones": water_zones,
        "deviations":  deviations,
        "meta": {
            "lat":   lat,
            "lon":   lon,
            "acres": acres
        }
    }


# ──────────────────────────────────────────────────
# STANDALONE TEST
# ──────────────────────────────────────────────────

if __name__ == "__main__":
    print("Starting grid_analyzer.py test...")

    if not setup_gee():
        print("❌ GEE auth failed.")
        sys.exit(1)

    result = analyze_grid(
        lat      = 11.0168,
        lon      = 76.9558,
        acres    = 5.0,
        days_back= 20
    )

    if result:
        print("✅ grid_analyzer.py test passed!")
        print("   Next: Run crop_stress.py")
    else:
        print("❌ grid_analyzer.py failed")