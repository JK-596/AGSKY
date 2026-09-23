"""
gemini_chat.py
--------------
AGSKY-oda CONVERSATIONAL BRAIN.

3 modes:
    1. generate_farm_report()  → Full analysis report (satellite+weather+market)
    2. chat_with_farmer()      → Live chatbot for farmer questions
    3. quick_advice()          → Specific question-ku quick answer

Uses all previous files:
    crop_stress + weather_api + market_price + mongo_handler → Gemini

Test:
    python gemini_chat.py
"""

import sys
import os
import json
import requests

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from config import GEMINI_API_KEY, GEMINI_MODEL
try:
    from config import GEMINI_MODEL_VISION
except ImportError:
    GEMINI_MODEL_VISION = "gemini-2.5-flash"

from gee_auth import setup_gee
from crop_stress import analyze_crop_stress
from weather_api import get_weather_report
from market_price import get_market_report
from mongo_handler import save_analysis, get_latest_session


# ──────────────────────────────────────────────────
# GEMINI API CALL (TEXT)
# ──────────────────────────────────────────────────

def call_gemini(prompt, temperature=0.7, max_tokens=2000):
    """
    Default text-based Gemini call.
    Uses GEMINI_MODEL from config (default: gemini-1.5-flash).
    Used for: cell chat, farmer advice, reports.
    """
    if not GEMINI_API_KEY:
        return None

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature":     temperature,
            "maxOutputTokens": max_tokens
        }
    }

    headers = {"Content-Type": "application/json"}
    params  = {"key": GEMINI_API_KEY}

    try:
        res  = requests.post(url, json=payload, headers=headers,
                             params=params, timeout=60)
        data = res.json()

        if res.status_code != 200:
            print(f"  ❌ Gemini error: {data.get('error', data)}")
            return None

        text = data['candidates'][0]['content']['parts'][0]['text']
        return text.strip()

    except Exception as e:
        print(f"  ❌ Gemini call failed: {e}")
        return None


def call_gemini_vision(prompt, image_base64, temperature=0.4, max_tokens=1500):
    """
    Vision-based Gemini call (uses 2.5 Flash multimodal).
    Used for: pest detection from crop leaf photos.
    
    Args:
        prompt: Text instruction for the AI
        image_base64: Base64-encoded image string (without data:image prefix)
    """
    if not GEMINI_API_KEY:
        return None

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL_VISION}:generateContent"

    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": image_base64
                    }
                }
            ]
        }],
        "generationConfig": {
            "temperature":     temperature,
            "maxOutputTokens": max_tokens
        }
    }

    headers = {"Content-Type": "application/json"}
    params  = {"key": GEMINI_API_KEY}

    try:
        res = requests.post(url, json=payload, headers=headers,
                            params=params, timeout=90)
        data = res.json()

        if res.status_code != 200:
            print(f"  ❌ Gemini Vision error: {data.get('error', data)}")
            return None

        text = data['candidates'][0]['content']['parts'][0]['text']
        return text.strip()

    except Exception as e:
        print(f"  ❌ Gemini Vision call failed: {e}")
        return None


def call_gemini_smart(prompt, temperature=0.5, max_tokens=1500):
    """
    Text-only call using Gemini 2.5 Flash (higher quality).
    Used for: pest prediction, detailed analyses (no image).
    """
    if not GEMINI_API_KEY:
        return None

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL_VISION}:generateContent"

    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature":     temperature,
            "maxOutputTokens": max_tokens
        }
    }

    headers = {"Content-Type": "application/json"}
    params  = {"key": GEMINI_API_KEY}

    try:
        res = requests.post(url, json=payload, headers=headers,
                            params=params, timeout=60)
        data = res.json()

        if res.status_code != 200:
            print(f"  ❌ Gemini Smart error: {data.get('error', data)}")
            return None

        text = data['candidates'][0]['content']['parts'][0]['text']
        return text.strip()

    except Exception as e:
        print(f"  ❌ Gemini Smart call failed: {e}")
        return None


# ──────────────────────────────────────────────────
# FULL FARM REPORT GENERATOR
# ──────────────────────────────────────────────────

def generate_farm_report(lat, lon, acres, crops=None, save_db=True):
    """
    Full AI-powered farm report generate pannum.
    Steps:
      1. Crop stress analysis (satellite)
      2. Weather fetch
      3. Market price check
      4. Combine all → Gemini → Tamil report
    """
    print("\n" + "="*50)
    print("  🌾 AGSKY FULL FARM REPORT GENERATION")
    print("="*50)

    # ── Step 1: Satellite + Crop Stress ──
    print("\n  📡 Step 1/4: Satellite analysis...")
    stress_result = analyze_crop_stress(lat, lon, acres, days_back=20)
    if not stress_result:
        return None

    health_score = stress_result['grid_result']['summary']['health_score']
    stress_summary = stress_result['stress_summary']

    # ── Step 2: Weather ──
    print("\n  🌤️  Step 2/4: Weather forecast...")
    weather = get_weather_report(lat, lon, stress_summary)

    # ── Step 3: Market ──
    print("\n  💰 Step 3/4: Market prices...")
    market = get_market_report(
        acres, health_score,
        crops or ["Rice", "Tomato", "Onion", "Maize", "Groundnut"]
    )

    # ── Step 4: Gemini Combined Report ──
    print("\n  🤖 Step 4/4: AI report generation...")
    report_text = _build_combined_report(
        lat, lon, acres,
        stress_result, weather, market
    )

    # ── Step 5: Save to MongoDB ──
    if save_db:
        print("\n  💾 Saving to MongoDB...")
        session_id = save_analysis(stress_result)
    else:
        session_id = None

    print("\n" + "="*50)
    print("  ✅ REPORT GENERATED")
    print("="*50)
    print(report_text)
    print("="*50 + "\n")

    return {
        "session_id":    session_id,
        "report":        report_text,
        "stress_result": stress_result,
        "weather":       weather,
        "market":        market
    }


def _build_combined_report(lat, lon, acres, stress, weather, market):
    """Passes all the collected data to Gemini AI to generate a consolidated report in Tamil."""

    # Compact data summary for prompt
    grid = stress['grid_result']['grid']
    summary = stress['grid_result']['summary']

    cell_data = "\n".join([
        f"  {lbl}: NDVI={c['ndvi']}, NDWI={c['ndwi']}, "
        f"Stress={stress['cell_stress'][lbl]['stress_type']}"
        for lbl, c in grid.items()
    ])

    forecast_str = "Weather data not available"
    if weather and weather.get('forecast'):
        forecast_str = "\n".join([
            f"  {d['date']}: {d['temp_min']}-{d['temp_max']}°C, "
            f"Rain={d['rain_mm']}mm, Humidity={d['humidity']}%"
            for d in weather['forecast']
        ])

    market_str = "Market data not available"
    if market:
        market_str = "\n".join([
            f"  {m['price']['crop']}: ₹{m['price']['modal']}/q, "
            f"Profit=₹{m['profit']['net_profit']:,} ({m['profit']['profit_per_acre']:,}/acre)"
            for m in market if m.get('profit')
        ])

    prompt = f"""You are AGSKY — an AI agriculture advisor for Maharastra farmers.

FARM DETAILS:
- Location: {lat}, {lon}
- Area: {acres} acres
- Health Score: {summary['health_score']}/100
- Farm Status: {stress['farm_status']['status']}
- Worst Zone: {summary['worst_cell']}
- Best Zone: {summary['best_cell']}

SATELLITE DATA (9 cells):
{cell_data}

STRESS ZONES:
- Critical: {stress['grid_result']['zones']['critical']}
- Drought: {stress['grid_result']['water_zones']['drought']}

WEATHER (Next 5 days):
{forecast_str}

MARKET PRICES & PROFIT:
{market_str}

Task: Generate a Complete Farmer Advisory Report

Generate a complete farm advisory report in simple, easy-to-understand English for the farmer.

Structure:

🌾 YOUR FARM CONDITION – Summarize the farm's current condition in 2–3 sentences.
🚨 URGENT ACTIONS – List the top 3 priorities as bullet points.
💧 IRRIGATION PLAN – Provide an irrigation plan based on weather conditions and crop stress.
🐛 PESTICIDE ADVICE – Recommend specific application timings.
💰 BEST CROP TO SELL – Identify the crop with the highest profit potential and suggest when to harvest and sell.
📅 NEXT 5 DAYS ACTION PLAN – Provide a day-wise action plan for the next 5 days.

Rules:
Use simple English so farmers can easily understand.
Use emojis for clarity. 🌱
Include specific numbers and days wherever reliable data is available.
Avoid technical jargon.
Keep each section within 3–4 sentences (except bullet-point sections where necessary).
End with an encouraging line for the farmer. 💪🌾
"""

    report = call_gemini(prompt, temperature=0.6, max_tokens=2500)
    return report or "⚠️ Report generation failed"


# ──────────────────────────────────────────────────
# LIVE CHATBOT (Farmer Q&A)
# ──────────────────────────────────────────────────

def chat_with_farmer(question, farm_context=None):
    """
    For Farmer question live answer.
    farm_context = latest session data (from MongoDB)
    """
    context_str = ""
    if farm_context:
        context_str = f"""
FARMER'S CURRENT FARM:
- Location: {farm_context.get('lat')}, {farm_context.get('lon')}
- Area: {farm_context.get('acres')} acres
- Health Score: {farm_context.get('health_score')}/100
- Status: {farm_context.get('farm_status')}
- Priority Issue: {farm_context.get('priority_stress')} in cell {farm_context.get('priority_cell')}
"""

    prompt = f"""You are AGSKY — a friendly AI farming advisor for Maharastra farmers.
 Keep answers practical and under 100 words.

{context_str}

FARMER ASKED:
"{question}"

YOUR RESPONSE (Tanglish, simple, practical):"""

    return call_gemini(prompt, temperature=0.7, max_tokens=500)


# ──────────────────────────────────────────────────
# QUICK ADVICE (Single-purpose helper)
# ──────────────────────────────────────────────────

def quick_advice(topic, data):
    """
    Specific topic-ku quick advice.
    topic: 'irrigation' | 'pesticide' | 'harvest' | 'market'
    """
    topics = {
        "irrigation": "when and how much to irrigate",
        "pesticide":  "which pesticide and when to spray",
        "harvest":    "when to harvest for best price",
        "market":     "best crop and market to sell"
    }

    guidance = topics.get(topic, "general farming advice")

    prompt = f"""You are AGSKY farming advisor.
Farmer needs advice on: {guidance}

Farm data:
{json.dumps(data, indent=2, default=str)}

Give a 3-point Tanglish advice (max 80 words total).
Use emojis. Be practical."""

    return call_gemini(prompt, temperature=0.5, max_tokens=400)


# ──────────────────────────────────────────────────
# INTERACTIVE CHAT MODE (Terminal)
# ──────────────────────────────────────────────────

def interactive_chat():
    """In Terminal live chat with farmer."""
    print("\n" + "="*50)
    print("  🤖 AGSKY Live Chatbot")
    print("  Type 'exit' to quit")
    print("="*50)

    # Load latest farm context from MongoDB
    print("\n  📂 Loading your farm data...")
    latest = get_latest_session()

    if latest:
        print(f"  ✅ Farm found: {latest['acres']} acres at "
              f"({latest['lat']:.4f}, {latest['lon']:.4f})")
        print(f"     Status: {latest['farm_status']} | "
              f"Health: {latest['health_score']}/100")
    else:
        print("  ⚠️  No farm data found. Chat will be general.")
        latest = None

    print("\n" + "-"*50)
    print("ask what you needed — Tamil or English OK")
    print("-"*50 + "\n")

    while True:
        try:
            question = input("👨‍🌾 You: ").strip()
            if not question:
                continue
            if question.lower() in ['exit', 'quit', 'bye']:
                print("\n🤖 AGSKY: Ok bro, happy farming! 🌾")
                break

            print("\n🤖 AGSKY: ", end="", flush=True)
            answer = chat_with_farmer(question, latest)
            if answer:
                print(answer + "\n")
            else:
                print("⚠️  Sorry,please try again after sometime\n")

        except KeyboardInterrupt:
            print("\n\n🤖 AGSKY: Bye bro! 👋")
            break


# ──────────────────────────────────────────────────
# STANDALONE TEST
# ──────────────────────────────────────────────────

if __name__ == "__main__":
    print("Starting gemini_chat.py test...")

    if not GEMINI_API_KEY:
        print("❌ GEMINI_API_KEY empty")
        sys.exit(1)

    print("\nSelect mode:")
    print("  1. Generate full farm report (lat/lon/acres)")
    print("  2. Chat mode (Q&A with farmer)")
    print("  3. Quick chat test (single question)")
    choice = input("\nChoice (1/2/3): ").strip()

    if choice == "1":
        if not setup_gee():
            print("❌ GEE auth failed")
            sys.exit(1)

        print("\nEnter farm details:")
        try:
            lat   = float(input("  Latitude  (e.g. 11.0168): "))
            lon   = float(input("  Longitude (e.g. 76.9558): "))
            acres = float(input("  Acres     (e.g. 5): "))
        except ValueError:
            print("❌ Invalid input")
            sys.exit(1)

        result = generate_farm_report(lat, lon, acres)
        if result:
            print(f"\n✅ Report saved! Session: {result['session_id']}")

    elif choice == "2":
        interactive_chat()

    elif choice == "3":
        # Quick test
        test_context = {
            "lat": 11.0168, "lon": 76.9558, "acres": 5.0,
            "health_score": 23.2, "farm_status": "CRITICAL",
            "priority_cell": "SE", "priority_stress": "water_stress"
        }
        print("\n👨‍🌾 Test: 'is my tomato needs to grow?'")
        answer = chat_with_farmer(
            "is my tomato is growthing?", test_context
        )
        print(f"\n🤖 AGSKY: {answer}")

    else:
        print("❌ Invalid choice")