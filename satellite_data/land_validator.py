"""
land_validator.py
-----------------
Uses Sentinel-2 NDVI and NDWI scores to identify the land type.
No Gemini Vision — saves API quota + more accurate!

Logic:
  NDVI > 0.4   → Dense vegetation (farmland/forest)
  NDVI 0.2-0.4 → Moderate vegetation (farmland with crop)
  NDVI < 0.15  → Non-vegetation (urban/bare)
  NDWI > 0.3   → Water body
  High variance → farmland (crop patches)
  Low variance + high NDVI → forest (uniform canopy)
"""

import sys
import os
import math
from datetime import datetime, timezone, timedelta

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from gee_auth import setup_gee

try:
    import ee
except ImportError:
    print("❌ earthengine-api not installed")
    sys.exit(1)


def fetch_land_metrics(lat, lon, buffer_meters=60, days_back=30):
    """
   Extracts NDVI and NDWI values at the exact point and within a small surrounding area.
    Plus Sentinel-2 thumbnail URL (farmer visual confirmation).

    Three measurements:
    1. CENTER pixel  → 10m × 10m (exact click)
    2. CORE area     → 30m × 30m (3x3 pixels — click tolerance)
    3. BUFFER area   → 60m buffer (context/variance)
    """
    lat_deg_big = buffer_meters / 111320
    lon_deg_big = buffer_meters / (111320 * abs(math.cos(math.radians(lat))))

    # Small core area (30m) — accounts for click imprecision
    core_meters = 15
    lat_deg_core = core_meters / 111320
    lon_deg_core = core_meters / (111320 * abs(math.cos(math.radians(lat))))

    # Thumbnail area (larger for visual context — 500m)
    thumb_meters = 500
    lat_deg_thumb = thumb_meters / 111320
    lon_deg_thumb = thumb_meters / (111320 * abs(math.cos(math.radians(lat))))

    # Geometries
    buffer_geom = ee.Geometry.Rectangle([
        lon - lon_deg_big, lat - lat_deg_big,
        lon + lon_deg_big, lat + lat_deg_big
    ])
    core_geom = ee.Geometry.Rectangle([
        lon - lon_deg_core, lat - lat_deg_core,
        lon + lon_deg_core, lat + lat_deg_core
    ])
    thumb_geom = ee.Geometry.Rectangle([
        lon - lon_deg_thumb, lat - lat_deg_thumb,
        lon + lon_deg_thumb, lat + lat_deg_thumb
    ])
    center_point = ee.Geometry.Point([lon, lat])

    end_date   = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days_back)

    collection = (
        ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
        .filterBounds(buffer_geom)
        .filterDate(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
        .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30))
        .sort('CLOUDY_PIXEL_PERCENTAGE')
    )

    count = collection.size().getInfo()
    if count == 0:
        return None

    best = collection.first()
    img = best.divide(10000)

    ndvi = img.normalizedDifference(['B8', 'B4']).rename('NDVI')
    ndwi = img.normalizedDifference(['B3', 'B8']).rename('NDWI')

    # ── BUFFER AREA STATS (60m) — context ──
    ndvi_buf = ndvi.reduceRegion(
        reducer   = ee.Reducer.mean().combine(ee.Reducer.stdDev(), sharedInputs=True),
        geometry  = buffer_geom,
        scale     = 10,
        maxPixels = 1e9
    )
    ndwi_buf = ndwi.reduceRegion(
        reducer   = ee.Reducer.mean(),
        geometry  = buffer_geom,
        scale     = 10,
        maxPixels = 1e9
    )

    # ── CORE AREA STATS (30m) — primary ──
    ndvi_core = ndvi.reduceRegion(
        reducer   = ee.Reducer.mean().combine(ee.Reducer.stdDev(), sharedInputs=True),
        geometry  = core_geom,
        scale     = 10,
        maxPixels = 1e9
    )
    ndwi_core = ndwi.reduceRegion(
        reducer   = ee.Reducer.mean(),
        geometry  = core_geom,
        scale     = 10,
        maxPixels = 1e9
    )

    # ── EXACT CENTER PIXEL ──
    ndvi_ctr = ndvi.reduceRegion(
        reducer   = ee.Reducer.first(),
        geometry  = center_point,
        scale     = 10,
        maxPixels = 1e9
    )
    ndwi_ctr = ndwi.reduceRegion(
        reducer   = ee.Reducer.first(),
        geometry  = center_point,
        scale     = 10,
        maxPixels = 1e9
    )

    # ── THUMBNAIL (RGB satellite image for farmer preview) ──
    thumb_url = best.getThumbURL({
        'region':     thumb_geom,
        'dimensions': 768,
        'bands':      ['B4', 'B3', 'B2'],
        'min':        300,
        'max':        2800,
        'gamma':      1.2
    })

    try:
        return {
            # Center pixel (exact click)
            "center_ndvi": round(ndvi_ctr.get('NDVI').getInfo() or 0, 4),
            "center_ndwi": round(ndwi_ctr.get('NDWI').getInfo() or 0, 4),
            # Core area (3x3 pixels — primary classification)
            "core_ndvi":   round(ndvi_core.get('NDVI_mean').getInfo() or 0, 4),
            "core_ndwi":   round(ndwi_core.get('NDWI').getInfo() or 0, 4),
            "core_std":    round(ndvi_core.get('NDVI_stdDev').getInfo() or 0, 4),
            # Buffer area (60m — context)
            "mean_ndvi":   round(ndvi_buf.get('NDVI_mean').getInfo() or 0, 4),
            "mean_ndwi":   round(ndwi_buf.get('NDWI').getInfo() or 0, 4),
            "std_ndvi":    round(ndvi_buf.get('NDVI_stdDev').getInfo() or 0, 4),
            "image_count": count,
            "cloud_cover": best.get('CLOUDY_PIXEL_PERCENTAGE').getInfo(),
            "thumbnail_url": thumb_url
        }
    except Exception as e:
        print(f"  ⚠️  Stats extraction failed: {e}")
        return None


def classify_land(metrics):
    """
    Zoom-independent classification using CORE AREA (30m × 30m = 9 pixels).
    this will solve the click precision.

    Decision order:
    1. Water (core NDWI > NDVI)
    2. Urban/Barren (core NDVI very low)
    3. Forest (high NDVI + low variance)
    4. Farmland (moderate NDVI)
    """
    # CORE area metrics (30m — primary classification)
    ndvi = metrics['core_ndvi']
    ndwi = metrics['core_ndwi']

    # Buffer area (context — variance check)
    a_std  = metrics['std_ndvi']
    core_std = metrics['core_std']

    # Center single pixel (for reference)
    c_ndvi = metrics['center_ndvi']
    c_ndwi = metrics['center_ndwi']

    # ── WATER DETECTION (core-based, strict) ──
    # Water signature: NDWI >= NDVI
    # Even muddy/shallow: NDWI usually positive
    if ndwi >= ndvi - 0.05 and ndwi > -0.1:
        # Strong water signal
        if ndwi > 0.0 or ndvi < 0.15:
            return {
                "land_type": "water", "is_farmland": False,
                "confidence": "high", "crop_visible": False,
                "reasoning": f"Water detected (NDWI={ndwi} ≥ NDVI={ndvi})",
                "recommendation": "This is water body. Click on green land"
            }

    # ── URBAN / ROAD / BARREN ──
    if ndvi < 0.15:
        if ndvi < 0.05:
            ltype, reason = "urban", f"Concrete/road surface (NDVI={ndvi})"
        else:
            ltype, reason = "barren", f"Bare ground (NDVI={ndvi})"

        return {
            "land_type": ltype, "is_farmland": False,
            "confidence": "high", "crop_visible": False,
            "reasoning": reason,
            "recommendation": "Click on green farm area, not roads/buildings"
        }

    # ── FOREST (dense + uniform canopy) ──
    # Forest: NDVI > 0.5 AND low variance at BOTH core and buffer
    if ndvi > 0.5 and core_std < 0.08 and a_std < 0.12:
        return {
            "land_type": "forest", "is_farmland": False,
            "confidence": "high", "crop_visible": False,
            "reasoning": f"Uniform dense canopy (NDVI={ndvi}, std={core_std}) — forest",
            "recommendation": "This is forest. Select farmland with crop rows"
        }

    # ── FARMLAND ──
    if ndvi >= 0.2:
        conf = "high" if ndvi >= 0.35 else "medium"
        return {
            "land_type": "farmland", "is_farmland": True,
            "confidence": conf, "crop_visible": ndvi >= 0.3,
            "reasoning": f"Crop vegetation (NDVI={ndvi}, variance={core_std})",
            "recommendation": "Proceed to enter acres"
        }

    # ── UNCERTAIN ──
    return {
        "land_type": "mixed", "is_farmland": False,
        "confidence": "low", "crop_visible": False,
        "reasoning": f"Unclear land type (NDVI={ndvi})",
        "recommendation": "Zoom in and click clearly on farm patches"
    }


def validate_land(lat, lon):
    """Full validation using NDVI/NDWI only (no Gemini)."""
    print("\n" + "="*45)
    print("  AGSKY Land Validator (NDVI-based)")
    print("="*45)
    print(f"  📍 Checking: {lat}, {lon}")

    print("\n  🛰️  Fetching NDVI/NDWI metrics...")
    metrics = fetch_land_metrics(lat, lon)

    if not metrics:
        return {
            "valid": False, "land_type": "unknown",
            "is_farmland": False, "confidence": "low",
            "crop_visible": False,
            "reasoning": "No cloud-free satellite image available",
            "recommendation": "Try a different location or wait",
            "thumbnail_url": None
        }

    # DEBUG: Print all metrics
    print(f"\n  🔍 DEBUG METRICS:")
    print(f"     Image count  : {metrics.get('image_count')}")
    print(f"     Cloud cover  : {metrics.get('cloud_cover')}%")
    print(f"     CENTER pixel : NDVI={metrics['center_ndvi']:>7}  NDWI={metrics['center_ndwi']:>7}")
    print(f"     CORE (30m)   : NDVI={metrics['core_ndvi']:>7}  NDWI={metrics['core_ndwi']:>7}  std={metrics['core_std']}")
    print(f"     BUFFER (60m) : NDVI={metrics['mean_ndvi']:>7}  NDWI={metrics['mean_ndwi']:>7}  std={metrics['std_ndvi']}")

    print("\n  🧮 Classifying (math-based)...")
    analysis = classify_land(metrics)

    result = {
        "valid": analysis['is_farmland'],
        "land_type": analysis['land_type'],
        "is_farmland": analysis['is_farmland'],
        "confidence": analysis['confidence'],
        "crop_visible": analysis['crop_visible'],
        "reasoning": analysis['reasoning'],
        "recommendation": analysis['recommendation'],
        "metrics": metrics,
        "thumbnail_url": metrics.get('thumbnail_url')
    }

    print("\n" + "-"*45)
    emoji = "✅" if result['valid'] else "⚠️"
    print(f"  {emoji} Land Type     : {result['land_type'].upper()}")
    print(f"  🎯 Is Farmland   : {result['is_farmland']}")
    print(f"  📊 Confidence    : {result['confidence']}")
    print(f"  💭 Reasoning     : {result['reasoning']}")
    print(f"  💡 Recommendation: {result['recommendation']}")
    print("-"*45)

    if result['valid']:
        print("\n  ✅ FARMLAND CONFIRMED → acres input enabled")
    else:
        print(f"\n  ⚠️  NOT FARMLAND ({result['land_type']})")

    print("="*45 + "\n")
    return result


if __name__ == "__main__":
    print("Starting land_validator.py test...")

    if not setup_gee():
        sys.exit(1)

    test_cases = [
        ("Pollachi Farmland",  10.6589, 77.0084),
        ("Coimbatore City",    11.0168, 76.9558),
    ]

    for name, lat, lon in test_cases:
        print(f"\n🔍 Testing: {name}")
        result = validate_land(lat, lon)
        if result['valid']:
            print(f"✅ {name} → FARMLAND")
        else:
            print(f"⚠️  {name} → {result['land_type'].upper()}")

    print("\n✅ land_validator.py test complete!")