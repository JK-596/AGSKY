"""
crop_stress.py
--------------
grid_analyzer.py output → detects crop stress.
Each cell's stress type, severity, and action will be recommened.

Pipeline:
    sentinel_fetch → cloud_mask → indices → grid_analyzer → crop_stress ✅

Stress Types Detected:
    1. Water Stress      → NDWI low, NDVI dropping
    2. Nutrient Stress   → NDVI low but NDWI ok
    3. Pest/Disease      → Sudden NDVI drop in specific cells
    4. Waterlogging      → NDWI very high
    5. Healthy           → All indices good

Test:
    python crop_stress.py
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from gee_auth import setup_gee
from grid_analyzer import analyze_grid


# ──────────────────────────────────────────────────
# STRESS DETECTION RULES
# ──────────────────────────────────────────────────

def detect_cell_stress(cell_data):
    """
    Each cell's NDVI + NDWI + EVI → detects the stress type.
    Returns: { type, severity, confidence, actions }
    """
    ndvi = cell_data.get('ndvi')
    ndwi = cell_data.get('ndwi')
    evi  = cell_data.get('evi')

    if ndvi is None or ndwi is None:
        return {
            "stress_type": "unknown",
            "severity":    "unknown",
            "confidence":  "low",
            "actions":     ["No Satellite data today — inspect manually"]
        }

    stress_type = "healthy"
    severity    = "none"
    confidence  = "high"
    actions     = []

    # ── WATERLOGGING ──
    if ndwi > 0.3:
        stress_type = "waterlogging"
        severity    = "high"
        actions     = [
            "Open Drainage channel",
            "Stop Irrigation",
            "watch for root Rot"
        ]

    # ── SEVERE WATER STRESS ──
    elif ndwi < -0.3 and ndvi < 0.3:
        stress_type = "water_stress"
        severity    = "critical"
        actions     = [
            "immediate irrigation needed",
            "Consider Drip irrigation",
            "water in morning hours (evaporation will reduce)"
        ]

    # ── MILD WATER STRESS ──
    elif ndwi < -0.15 and ndvi < 0.4:
        stress_type = "water_stress"
        severity    = "moderate"
        actions     = [
            "within 2-3 days irrigate the land",
            "Check the Soil moisture",
            "putting Mulching will reduce the evaporation"
        ]

    # ── NUTRIENT STRESS ──
    # NDVI low but NDWI ok → water present but no crop growth
    elif ndvi < 0.25 and ndwi > -0.2:
        stress_type = "nutrient_stress"
        severity    = "moderate" if ndvi < 0.15 else "mild"
        actions     = [
            "Soil test (N, P, K levels check)",
            "Urea or DAP can be applied",
            "See the Leaf color — if yellowing Nitrogen deficiency"
        ]

    # ── PEST / DISEASE ──
    # EVI and NDVI both low but inconsistent pattern
    elif ndvi < 0.3 and evi is not None and evi < 0.15:
        stress_type = "pest_disease"
        severity    = "moderate"
        confidence  = "medium"  # Ground truth should be confirmed
        actions     = [
            "should Field visit and physically inspected",
            "Leaf damage, discoloration checked",
            "Before applying Pesticide confirm it"
        ]

    # ── HEALTHY ──
    elif ndvi >= 0.4:
        stress_type = "healthy"
        severity    = "none"
        actions     = ["Normal maintenance can be continued"]
        if ndvi >= 0.6:
            actions.append("Excellent growth — see the harvest timeline")

    # ── GENERAL LOW VEGETATION ──
    else:
        stress_type = "low_vegetation"
        severity    = "mild"
        confidence  = "medium"
        actions     = [
            "Crop stage should be confirmed (In early stage NDVI will be low)",
            "IF Bare soil — consider replanting",
            "Irrigation + fertilizer combo can be tried out"
        ]

    return {
        "stress_type": stress_type,
        "severity":    severity,
        "confidence":  confidence,
        "actions":     actions
    }


# ──────────────────────────────────────────────────
# FARM-LEVEL STRESS SUMMARY
# ──────────────────────────────────────────────────

def get_priority_stress(all_stress):
    """
    Returns the most critical cell among the 9 cells based on stress levels 
    tells the farmer which area needs to be addressed first.
    """
    severity_order = ["critical", "high", "moderate", "mild", "none", "unknown"]
    priority = None

    for cell_label, stress in all_stress.items():
        if priority is None:
            priority = (cell_label, stress)
        else:
            curr_sev  = stress['severity']
            best_sev  = priority[1]['severity']
            if severity_order.index(curr_sev) < severity_order.index(best_sev):
                priority = (cell_label, stress)

    return priority


def summarize_stress_types(all_stress):
    """Stress type count summary."""
    counts = {}
    for label, stress in all_stress.items():
        stype = stress['stress_type']
        counts[stype] = counts.get(stype, [])
        counts[stype].append(label)
    return counts


def get_overall_farm_status(summary, stress_summary):
    """
    Farm-wide overall status — report_builder.py should be used.
    """
    health = summary['health_score']
    critical_cells = stress_summary.get('water_stress', []) + \
                     stress_summary.get('pest_disease', [])

    if health >= 70:
        status = "GOOD"
        message = "Farm overall is healthy"
    elif health >= 40:
        status = "MODERATE"
        message = f"some areas need attention — {len(critical_cells)} cells critical"
    else:
        status = "CRITICAL"
        message = f"in Farm there is a widespread  — urgent action needed"

    return {"status": status, "message": message, "health_score": health}


# ──────────────────────────────────────────────────
# MAIN FUNCTION
# ──────────────────────────────────────────────────

def analyze_crop_stress(lat, lon, acres, days_back=20):
    """
    Full stress analysis pipeline.
    Returns complete stress report dict.
    """
    print("\n" + "="*45)
    print("  AGSKY Crop Stress Analysis Starting...")
    print("="*45)

    # Step 1: Grid analysis
    grid_result = analyze_grid(lat, lon, acres, days_back)
    if not grid_result:
        print("❌ Grid analysis failed")
        return None

    grid    = grid_result['grid']
    summary = grid_result['summary']
    zones   = grid_result['zones']

    # Step 2: Per-cell stress detection
    print("\n  🔬 Analyzing stress per cell...\n")
    all_stress = {}

    for label, cell_data in grid.items():
        stress = detect_cell_stress(cell_data)
        all_stress[label] = stress

        sev_emoji = {
            "critical": "🚨", "high": "🔴", "moderate": "🟠",
            "mild": "🟡", "none": "🟢", "unknown": "⬜"
        }.get(stress['severity'], "⬜")

        print(f"  [{label:^6}]  {sev_emoji} {stress['stress_type'].upper()}"
              f"  ({stress['severity']})")
        for action in stress['actions']:
            print(f"            → {action}")
        print()

    # Step 3: Farm-level summary
    stress_summary = summarize_stress_types(all_stress)
    farm_status    = get_overall_farm_status(summary, stress_summary)
    priority       = get_priority_stress(all_stress)

    print("="*45)
    print(f"  🌾 Farm Status    : {farm_status['status']}")
    print(f"  📋 Message        : {farm_status['message']}")
    print(f"  ⚠️  Priority Cell  : {priority[0]} → {priority[1]['stress_type']}")
    print()

    for stype, cells in stress_summary.items():
        emoji = {
            "water_stress":   "💧",
            "nutrient_stress":"🌿",
            "pest_disease":   "🐛",
            "waterlogging":   "🌊",
            "low_vegetation": "🟤",
            "healthy":        "🟢",
            "unknown":        "⬜"
        }.get(stype, "📍")
        print(f"  {emoji} {stype.replace('_',' ').title():20} : {cells}")

    print("\n  ✅ Crop stress analysis complete!")
    print("  📤 Next: Run weather_api.py")
    print("="*45 + "\n")

    return {
        "cell_stress":    all_stress,
        "stress_summary": stress_summary,
        "farm_status":    farm_status,
        "priority_cell":  priority,
        "grid_result":    grid_result
    }


# ──────────────────────────────────────────────────
# STANDALONE TEST
# ──────────────────────────────────────────────────

if __name__ == "__main__":
    print("Starting crop_stress.py test...")

    if not setup_gee():
        print("❌ GEE auth failed.")
        sys.exit(1)

    result = analyze_crop_stress(
        lat      = 11.0168,
        lon      = 76.9558,
        acres    = 5.0,
        days_back= 20
    )

    if result:
        print("✅ crop_stress.py test passed!")
        print("   Next: Run weather_api.py ")
    else:
        print("❌ crop_stress.py failed")