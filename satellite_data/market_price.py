"""
market_price.py
---------------
Fetches Tamil Nadu crop market prices using the data.gov.in API.
Uses fallback prices if the API fails.


Pipeline:
    crop_stress → weather_api → market_price → gemini ✅

Test:
    python market_price.py
"""

import sys
import os
import requests
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from config import MARKET_API_KEY


# ──────────────────────────────────────────────────
# FALLBACK PRICES (Tamil Nadu avg — April 2026)
# Price per Quintal (100 kg) in INR
# ──────────────────────────────────────────────────

FALLBACK_PRICES = {
    "Rice":        {"min": 1800, "max": 2200, "modal": 2000},
    "Paddy":       {"min": 1500, "max": 1900, "modal": 1700},
    "Maize":       {"min": 1400, "max": 1700, "modal": 1550},
    "Sugarcane":   {"min": 2800, "max": 3200, "modal": 3000},
    "Cotton":      {"min": 5800, "max": 6500, "modal": 6200},
    "Groundnut":   {"min": 4500, "max": 5500, "modal": 5000},
    "Tomato":      {"min": 800,  "max": 2500, "modal": 1500},
    "Onion":       {"min": 600,  "max": 1800, "modal": 1200},
    "Banana":      {"min": 1200, "max": 2000, "modal": 1600},
    "Turmeric":    {"min": 7000, "max": 9000, "modal": 8000},
    "Chilli":      {"min": 8000, "max": 12000,"modal": 10000},
    "Soybean":     {"min": 3800, "max": 4500, "modal": 4200},
    "Wheat":       {"min": 1800, "max": 2200, "modal": 2000},
    "Sunflower":   {"min": 4500, "max": 5500, "modal": 5000},
    "Coconut":     {"min": 1500, "max": 2500, "modal": 2000},
}

# Tamil Nadu major markets
TN_MARKETS = [
    "Coimbatore", "Salem", "Madurai",
    "Trichy", "Chennai", "Tirunelveli"
]


# ──────────────────────────────────────────────────
# DATA.GOV.IN API FETCH
# ──────────────────────────────────────────────────

def fetch_from_api(crop_name, state="Tamil Nadu"):
    """
    data.gov.in Agmarknet API will be called.
    Returns price data or None if failed.
    """
    if not MARKET_API_KEY:
        return None

    url = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
    params = {
        "api-key": MARKET_API_KEY,
        "format":  "json",
        "limit":   20,
        "filters[state]":     state,
        "filters[commodity]": crop_name
    }

    try:
        res  = requests.get(url, params=params, timeout=10)
        data = res.json()

        if res.status_code != 200 or data.get('total', 0) == 0:
            return None

        records = data.get('records', [])
        if not records:
            return None

        # Extract prices from records (lowercase field names!)
        prices = []
        for r in records:
            try:
                prices.append({
                    "market":    r.get('market', 'Unknown'),
                    "min_price": float(r.get('min_price', 0)),
                    "max_price": float(r.get('max_price', 0)),
                    "modal":     float(r.get('modal_price', 0)),
                    "date":      r.get('arrival_date', 'N/A'),
                    "variety":   r.get('variety', 'N/A'),
                    "district":  r.get('district', 'N/A')
                })
            except (ValueError, TypeError):
                continue

        return prices if prices else None

    except requests.exceptions.RequestException:
        return None


# ──────────────────────────────────────────────────
# PRICE FETCHER (API + Fallback)
# ──────────────────────────────────────────────────

def get_crop_price(crop_name):
    """
    Crop price fetch pannum.
    API success → real data
    API fail    → fallback prices
    """
    # Try API first
    api_data = fetch_from_api(crop_name)

    if api_data:
        # Calculate average from API records
        modals = [r['modal'] for r in api_data if r['modal'] > 0]
        mins   = [r['min_price'] for r in api_data if r['min_price'] > 0]
        maxs   = [r['max_price'] for r in api_data if r['max_price'] > 0]

        return {
            "crop":       crop_name,
            "min_price":  round(min(mins), 0) if mins else 0,
            "max_price":  round(max(maxs), 0) if maxs else 0,
            "modal":      round(sum(modals) / len(modals), 0) if modals else 0,
            "source":     "data.gov.in (Live)",
            "markets":    [r['market'] for r in api_data[:3]],
            "date":       api_data[0]['date']
        }

    # Fallback
    crop_key = next(
        (k for k in FALLBACK_PRICES if k.lower() == crop_name.lower()),
        None
    )

    if crop_key:
        fb = FALLBACK_PRICES[crop_key]
        return {
            "crop":      crop_key,
            "min_price": fb['min'],
            "max_price": fb['max'],
            "modal":     fb['modal'],
            "source":    "Fallback (Tamil Nadu avg)",
            "markets":   TN_MARKETS[:3],
            "date":      datetime.now().strftime('%Y-%m-%d')
        }

    return None


# ──────────────────────────────────────────────────
# PROFIT CALCULATOR
# ──────────────────────────────────────────────────

def calculate_profit(crop_name, acres, price_data, health_score=50):
    """
    Expected yield + profit calculate pannum.
    health_score → satellite NDVI-based yield adjustment.
    """
    # Average yield per acre (quintals) — Tamil Nadu standards
    yield_per_acre = {
        "Rice":      25, "Paddy":     25, "Maize":     20,
        "Sugarcane": 300,"Cotton":    8,  "Groundnut": 10,
        "Tomato":    80, "Onion":     60, "Banana":    120,
        "Turmeric":  25, "Chilli":    12, "Soybean":   10,
        "Wheat":     18, "Sunflower": 8,  "Coconut":   150,
    }

    crop_key = next(
        (k for k in yield_per_acre if k.lower() == crop_name.lower()),
        None
    )

    if not crop_key or not price_data:
        return None

    base_yield = yield_per_acre[crop_key] * acres

    # Health score adjustment (NDVI-based)
    # 100 score → 100% yield, 23 score → ~60% yield
    yield_factor = 0.5 + (health_score / 200)  # Range: 0.5 to 1.0
    adjusted_yield = round(base_yield * yield_factor, 1)

    modal_price   = price_data['modal']
    gross_revenue = round(adjusted_yield * modal_price, 0)

    # Rough input cost (seeds + fertilizer + labor + water)
    input_cost_per_acre = {
        "Rice": 15000, "Paddy": 15000, "Maize": 12000,
        "Sugarcane": 35000, "Cotton": 20000, "Groundnut": 18000,
        "Tomato": 25000, "Onion": 20000, "Banana": 30000,
        "Turmeric": 40000, "Chilli": 35000, "Soybean": 12000,
        "Wheat": 12000, "Sunflower": 12000, "Coconut": 8000,
    }

    total_input  = input_cost_per_acre.get(crop_key, 15000) * acres
    net_profit   = round(gross_revenue - total_input, 0)
    profit_per_acre = round(net_profit / acres, 0) if acres > 0 else 0

    return {
        "crop":             crop_key,
        "acres":            acres,
        "base_yield_q":     base_yield,
        "adjusted_yield_q": adjusted_yield,
        "yield_factor":     round(yield_factor * 100, 0),
        "modal_price":      modal_price,
        "gross_revenue":    gross_revenue,
        "input_cost":       total_input,
        "net_profit":       net_profit,
        "profit_per_acre":  profit_per_acre,
        "profitable":       net_profit > 0
    }


# ──────────────────────────────────────────────────
# MAIN FUNCTION
# ──────────────────────────────────────────────────

def get_market_report(acres, health_score=50, crops=None):
    """
    For Multiple crops price + profit report.
    gemini_chat.py will use this.
    """
    if crops is None:
        # Default Tamil Nadu common crops
        crops = ["Rice", "Maize", "Tomato", "Onion", "Groundnut"]

    print("\n" + "="*45)
    print("  AGSKY Market Price Analysis...")
    print("="*45)
    print(f"  📐 Farm: {acres} acres | "
          f"Health Score: {health_score}/100\n")

    results = []

    for crop in crops:
        price_data = get_crop_price(crop)
        if not price_data:
            continue

        profit_data = calculate_profit(crop, acres, price_data, health_score)

        print(f"  🌾 {crop}")
        print(f"     Price  : ₹{price_data['min_price']:,} – "
              f"₹{price_data['max_price']:,} /quintal")
        print(f"     Modal  : ₹{price_data['modal']:,} /quintal")
        print(f"     Source : {price_data['source']}")

        if profit_data:
            profit_emoji = "✅" if profit_data['profitable'] else "❌"
            print(f"     Yield  : {profit_data['adjusted_yield_q']}q "
                  f"({profit_data['yield_factor']}% efficiency)")
            print(f"     Revenue: ₹{profit_data['gross_revenue']:,}")
            print(f"     Profit : {profit_emoji} ₹{profit_data['net_profit']:,} "
                  f"(₹{profit_data['profit_per_acre']:,}/acre)")

        print()
        results.append({
            "price":  price_data,
            "profit": profit_data
        })

    # Best crop recommendation
    profitable = [
        r for r in results
        if r['profit'] and r['profit']['profitable']
    ]
    if profitable:
        best = max(profitable, key=lambda x: x['profit']['net_profit'])
        print(f"  🏆 Best crop this season: "
              f"{best['profit']['crop']} "
              f"→ ₹{best['profit']['net_profit']:,} profit")

    print("\n  ✅ Market analysis complete!")
    print("  📤 Next: Run the gemini_chat.py")
    print("="*45 + "\n")

    return results


# ──────────────────────────────────────────────────
# STANDALONE TEST
# ──────────────────────────────────────────────────

if __name__ == "__main__":
    print("Starting market_price.py test...")

    result = get_market_report(
        acres        = 5.0,
        health_score = 23.2,   # From grid_analyzer output
        crops        = ["Rice", "Maize", "Tomato", "Onion", "Groundnut"]
    )

    if result:
        print("✅ market_price.py test passed!")
        print("   Next: Run the gemini_chat.py")
    else:
        print("❌ market_price.py failed")