"""
sentinel_fetch.py
-----------------
Fetches Sentinel-1 and Sentinel-2 data from Google Earth Engine (GEE).
Uses the `calculate_grid()` function from `grid_maker.py` to determine the boundaries of the 9 grid cells.


Test:
    python sentinel_fetch.py
"""

import ee
import sys
import os
import json
from datetime import datetime, timedelta


sys.path.append(os.path.dirname(__file__))
from gee_auth import setup_gee
from grid_maker import calculate_grid


# ──────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────

def get_date_range(days_back=15):
    """Last N days range return pannum."""
    end   = datetime.utcnow()
    start = end - timedelta(days=days_back)
    return start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')


def bounds_to_ee_geometry(lat, lon, acres):
    """grid_maker bounds -> GEE ee.Geometry.Rectangle"""
    start_lat, start_lon, sub_lat, sub_lon = calculate_grid(lat, lon, acres)

    west  = start_lon
    east  = start_lon + 3 * sub_lon
    south = start_lat
    north = start_lat + 3 * sub_lat

    return ee.Geometry.Rectangle([west, south, east, north])


def cell_bounds_to_geometry(cell_bounds):
    """Single cell bounds dict -> ee.Geometry"""
    return ee.Geometry.Rectangle([
        cell_bounds['west'],
        cell_bounds['south'],
        cell_bounds['east'],
        cell_bounds['north']
    ])


# ──────────────────────────────────────────────────
# SENTINEL-2 FETCH
# ──────────────────────────────────────────────────

def fetch_sentinel2(lat, lon, acres, days_back=15):
    """
    Uses the Sentinel-2 L2A (Surface Reflectance) collection.
    Cloud masking is handled separately using `cloud_mask.py`.

    Returns: ee.ImageCollection
    """
    start_date, end_date = get_date_range(days_back)
    geometry = bounds_to_ee_geometry(lat, lon, acres)

    print(f"  📡 Sentinel-2 fetch: {start_date} → {end_date}")

    collection = (
        ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
        .filterBounds(geometry)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 80))  # Heavy cloud images skip
        .select([
            'B2',   # Blue
            'B3',   # Green
            'B4',   # Red
            'B8',   # NIR
            'B11',  # SWIR1
            'B12',  # SWIR2
            'QA60'  # Cloud mask band
        ])
    )

    count = collection.size().getInfo()
    print(f"  ✅ Sentinel-2: {count} images found")

    if count == 0:
        print("  ⚠️  No images found — days_back increase pannunga (e.g. 30)")
        return None

    return collection


# ──────────────────────────────────────────────────
# SENTINEL-1 FETCH
# ──────────────────────────────────────────────────

def fetch_sentinel1(lat, lon, acres, days_back=15):
    """
    Sentinel-1 SAR GRD collection edukum.
    Clouds-ah penetrate pannum — rainy season ku useful.
    Returns: ee.ImageCollection
    """
    start_date, end_date = get_date_range(days_back)
    geometry = bounds_to_ee_geometry(lat, lon, acres)

    print(f"  📡 Sentinel-1 fetch: {start_date} → {end_date}")

    collection = (
        ee.ImageCollection('COPERNICUS/S1_GRD')
        .filterBounds(geometry)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.eq('instrumentMode', 'IW'))           # Interferometric Wide mode
        .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
        .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'))
        .select(['VV', 'VH'])
    )

    count = collection.size().getInfo()
    print(f"  ✅ Sentinel-1: {count} images found")

    if count == 0:
        print("  ⚠️  No SAR images found — days_back increase pannunga")
        return None

    return collection


# ──────────────────────────────────────────────────
# COMPOSITE (15-day mosaic)
# ──────────────────────────────────────────────────

def get_s2_composite(collection, geometry):
    """
    Multiple images -> one composite image (median mosaic).
    Call this after applying cloud_mask.py.
    """
    if collection is None:
        return None
    composite = collection.median().clip(geometry)
    print("  ✅ Sentinel-2 composite ready")
    return composite


def get_s1_composite(collection, geometry):
    """Sentinel-1 SAR median composite."""
    if collection is None:
        return None
    composite = collection.median().clip(geometry)
    print("  ✅ Sentinel-1 composite ready")
    return composite


# ──────────────────────────────────────────────────
# MAIN FETCH FUNCTION (app.py / indices.py used)
# ──────────────────────────────────────────────────

def fetch_all(lat, lon, acres, days_back=15):
    """
    Full fetch pipeline.
    Returns dict with s2_collection, s1_collection, geometry.
    """
    print("\n" + "="*45)
    print("  AGSKY Satellite Fetch Starting...")
    print("="*45)

    geometry = bounds_to_ee_geometry(lat, lon, acres)

    # Sentinel-2
    s2_col = fetch_sentinel2(lat, lon, acres, days_back)
    # Sentinel-1
    s1_col = fetch_sentinel1(lat, lon, acres, days_back)

    # Composites (Uses the raw composite without applying a cloud mask)
    s2_comp = get_s2_composite(s2_col, geometry)
    s1_comp = get_s1_composite(s1_col, geometry)

    print("\n  📦 Fetch complete. pass to cloud_mask.py")
    print("="*45 + "\n")

    return {
        "s2_collection":  s2_col,
        "s1_collection":  s1_col,
        "s2_composite":   s2_comp,   # raw (no cloud mask yet)
        "s1_composite":   s1_comp,
        "geometry":       geometry,
        "lat":            lat,
        "lon":            lon,
        "acres":          acres
    }


# ──────────────────────────────────────────────────
# STANDALONE TEST
# ──────────────────────────────────────────────────

if __name__ == "__main__":
    print("Starting sentinel_fetch.py test...")

    if not setup_gee():
        print("❌ GEE auth failed. Check gee_auth.py")
        sys.exit(1)

    # Test coordinates (Tamil Nadu farm)
    test_lat   = 11.0168
    test_lon   = 76.9558
    test_acres = 5.0

    result = fetch_all(test_lat, test_lon, test_acres, days_back=15)

    if result['s2_composite']:
        # Band names verify
        bands = result['s2_composite'].bandNames().getInfo()
        print(f"  S2 Bands available: {bands}")

    if result['s1_composite']:
        bands = result['s1_composite'].bandNames().getInfo()
        print(f"  S1 Bands available: {bands}")

    print("\n✅ sentinel_fetch.py test passed!")
    print("   Next: Run cloud_mask.py.")