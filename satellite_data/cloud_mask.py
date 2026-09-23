"""
cloud_mask.py
-------------
Sentinel-2 cloud masking — two methods:
  1. QA60 band masking     (fast, built-in GEE)
  2. s2cloudless algorithm (accurate, probability-based)

sentinel_fetch.py → cloud_mask.py → indices.py

Test:
    python cloud_mask.py
"""

import ee
import sys
import os

sys.path.append(os.path.dirname(__file__))
from gee_auth import setup_gee
from sentinel_fetch import fetch_all


# ──────────────────────────────────────────────────
# METHOD 1: QA60 BAND MASKING
# ──────────────────────────────────────────────────

def apply_qa60_mask(image):
    """
    QA60 band-la:
      Bit 10 → Opaque clouds
      Bit 11 → Cirrus clouds
    both of them masked here
    """
    qa = image.select('QA60')

    cloud_bit_mask  = 1 << 10   # Opaque cloud
    cirrus_bit_mask = 1 << 11   # Cirrus

    # Both bits 0 aana pixel thaan clear sky
    mask = (
        qa.bitwiseAnd(cloud_bit_mask).eq(0)
        .And(qa.bitwiseAnd(cirrus_bit_mask).eq(0))
    )

    # Scale factor: Sentinel-2 L2A values 0-10000 → 0-1
    return image.updateMask(mask).divide(10000)


def mask_s2_collection_qa60(s2_collection):
    """
    For Entire collection QA60 mask applied 
    cloud-free composite will be returned
    """
    if s2_collection is None:
        print("  ⚠️  s2_collection is None — sentinel_fetch.py should be runned")
        return None

    masked = s2_collection.map(apply_qa60_mask)
    print("  ✅ QA60 mask applied to collection")
    return masked


# ──────────────────────────────────────────────────
# METHOD 2: S2CLOUDLESS (Probability-based)
# ──────────────────────────────────────────────────

def get_s2cloudless_collection(start_date, end_date, geometry):
    """
    COPERNICUS/S2_CLOUD_PROBABILITY dataset will be taken.
    S2_SR_HARMONIZED-oda system:index match will be matched.
    """
    return (
        ee.ImageCollection('COPERNICUS/S2_CLOUD_PROBABILITY')
        .filterBounds(geometry)
        .filterDate(start_date, end_date)
    )


def add_cloud_bands(img):
    """It will add Cloud probability band."""
    cloud_prob = ee.Image(img.get('cloud_mask'))
    is_cloud   = cloud_prob.gt(50).rename('clouds')  # >50% probability = cloud
    return img.addBands([cloud_prob.rename('cloud_prob'), is_cloud])


def add_shadow_bands(img, nir_drk_thresh=0.15):
    """
    Cloud shadow detect:
    NIR band dark pixels → potential shadow areas.
    """
    not_water = img.select('B8').gt(nir_drk_thresh)
    dark_pixels = img.select('B8').lt(nir_drk_thresh).rename('dark_pixels')

    # Cloud projection direction (sun angle based)
    shadow_azimuth = ee.Number(90).subtract(
        ee.Number(img.get('MEAN_SOLAR_AZIMUTH_ANGLE'))
    )

    # Project clouds to find shadows
    cld_proj = (
        img.select('clouds')
        .directionalDistanceTransform(shadow_azimuth, 15)
        .reproject(crs=img.select(0).projection(), scale=100)
        .select('distance')
        .mask()
        .rename('cloud_transform')
    )

    shadows = cld_proj.multiply(dark_pixels).rename('shadows')
    return img.addBands([dark_pixels, cld_proj, shadows])


def apply_s2cloudless_mask(img, cloud_prob_thresh=50):
    """
    Cloud + shadow mask will be combined and final mask will be applied.
    """
    is_cld_shdw = img.select('clouds').add(img.select('shadows')).gt(0)

    # Dilate: cloud edges also be masked (30m buffer)
    is_cld_shdw = (
        is_cld_shdw.focalMax(3)
        .reproject(crs=img.select([0]).projection(), scale=20)
        .rename('cloudmask')
    )

    return img.updateMask(is_cld_shdw.Not())


def mask_s2_with_s2cloudless(s2_collection, geometry, start_date, end_date):
    """
    Full s2cloudless pipeline:
    S2 SR + Cloud Probability → join → mask → composite
    """
    if s2_collection is None:
        return None

    print("  🔄 s2cloudless algorithm running...")

    # Cloud probability collection
    s2_cloud_col = get_s2cloudless_collection(start_date, end_date, geometry)

    # Join by system:index
    index_filter = ee.Filter.equals(
        leftField='system:index',
        rightField='system:index'
    )
    join = ee.Join.saveFirst('cloud_mask')
    joined = ee.ImageCollection(
        join.apply(s2_collection, s2_cloud_col, index_filter)
    )

    # Add cloud + shadow bands
    with_clouds  = joined.map(add_cloud_bands)
    with_shadows = with_clouds.map(add_shadow_bands)

    # Apply mask
    masked = with_shadows.map(apply_s2cloudless_mask)

    # Scale to 0-1
    masked = masked.map(lambda img: img.divide(10000))

    print("  ✅ s2cloudless mask applied")
    return masked


# ──────────────────────────────────────────────────
# SMART SELECTOR: Which method to use?
# ──────────────────────────────────────────────────

def apply_best_cloud_mask(fetch_result, method='auto'):
    """
    method='auto'  → cloud coverage are auto decided
    method='qa60'  → always QA60 (fast)
    method='s2cl'  → always s2cloudless (accurate)

    Returns: cloud-masked ee.ImageCollection
    """
    s2_col   = fetch_result['s2_collection']
    geometry = fetch_result['geometry']

    if s2_col is None:
        print("  ❌ No S2 collection — mask apply panna mudiyathu")
        return None

    if method == 'qa60':
        print("  🎯 Method: QA60 (fast)")
        return mask_s2_collection_qa60(s2_col)

    elif method == 's2cl':
        from datetime import datetime, timedelta
        end   = datetime.utcnow()
        start = end - timedelta(days=15)
        print("  🎯 Method: s2cloudless (accurate)")
        return mask_s2_with_s2cloudless(
            s2_col, geometry,
            start.strftime('%Y-%m-%d'),
            end.strftime('%Y-%m-%d')
        )

    else:  # auto
        # Collection size check — For small area s2cloudless better
        count = s2_col.size().getInfo()
        if count >= 3:
            print(f"  🎯 Method: s2cloudless (auto — {count} images found)")
            from datetime import datetime, timedelta
            end   = datetime.utcnow()
            start = end - timedelta(days=15)
            return mask_s2_with_s2cloudless(
                s2_col, geometry,
                start.strftime('%Y-%m-%d'),
                end.strftime('%Y-%m-%d')
            )
        else:
            print(f"  🎯 Method: QA60 (auto — only {count} images, fast mode)")
            return mask_s2_collection_qa60(s2_col)


def get_cloudless_composite(fetch_result, method='auto'):
    """
    Final function: cloud-free composite image return pannum.
    indices.py ithai use panum.
    """
    print("\n" + "="*45)
    print("  AGSKY Cloud Masking Starting...")
    print("="*45)

    masked_col = apply_best_cloud_mask(fetch_result, method)

    if masked_col is None:
        return None

    geometry  = fetch_result['geometry']
    composite = masked_col.median().clip(geometry)

    print("  ✅ Cloud-free composite ready!")
    print("  📤 Next: it should be passed to indices.py (NDVI/NDWI)")
    print("="*45 + "\n")

    return composite


# ──────────────────────────────────────────────────
# STANDALONE TEST
# ──────────────────────────────────────────────────

if __name__ == "__main__":
    print("Starting cloud_mask.py test...")

    if not setup_gee():
        print("❌ GEE auth failed.")
        sys.exit(1)

    # Fetch first
    fetch_result = fetch_all(11.0168, 76.9558, 5.0, days_back=20)

    # Apply cloud mask
    composite = get_cloudless_composite(fetch_result, method='auto')

    if composite:
        bands = composite.bandNames().getInfo()
        print(f"  Available bands after masking: {bands}")
        print("\n✅ cloud_mask.py test passed!")
        print("   Next: run indices.py (NDVI / NDWI)")
    else:
        print("❌ Composite failed — increase the days_back")