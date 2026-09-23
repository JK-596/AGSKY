"""
weather_api.py
--------------
Uses the OpenWeatherMap API to fetch current weather conditions and a 5-day forecast for the farm location.
Provides irrigation and pesticide application timing recommendations based on weather conditions.


Pipeline:
    crop_stress → weather_api → market_price → gemini ✅

Test:
    python weather_api.py
"""

import sys
import os
import requests
from datetime import datetime, timezone

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from config import WEATHER_API_KEY


# ──────────────────────────────────────────────────
# CURRENT WEATHER
# ──────────────────────────────────────────────────

def get_current_weather(lat, lon):
    """for Farm location current weather is fetched."""
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "lat":   lat,
        "lon":   lon,
        "appid": WEATHER_API_KEY,
        "units": "metric"
    }

    try:
        res  = requests.get(url, params=params, timeout=10)
        data = res.json()

        if res.status_code != 200:
            print(f"  ❌ Weather API error: {data.get('message', 'Unknown')}")
            return None

        current = {
            "temp":        data['main']['temp'],
            "feels_like":  data['main']['feels_like'],
            "humidity":    data['main']['humidity'],
            "description": data['weather'][0]['description'].title(),
            "wind_speed":  data['wind']['speed'],
            "clouds":      data['clouds']['all'],
            "rain_1h":     data.get('rain', {}).get('1h', 0),
            "city":        data.get('name', 'Farm Location')
        }
        return current

    except requests.exceptions.RequestException as e:
        print(f"  ❌ Request failed: {e}")
        return None


# ──────────────────────────────────────────────────
# 5-DAY FORECAST
# ──────────────────────────────────────────────────

def get_forecast(lat, lon):
    """Next 5 days forecast (3-hour intervals → daily summary)."""
    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {
        "lat":   lat,
        "lon":   lon,
        "appid": WEATHER_API_KEY,
        "units": "metric"
    }

    try:
        res  = requests.get(url, params=params, timeout=10)
        data = res.json()

        if res.status_code != 200:
            print(f"  ❌ Forecast API error: {data.get('message')}")
            return None

        # 3-hour intervals → daily summary group are done
        daily = {}
        for item in data['list']:
            date = item['dt_txt'].split(' ')[0]
            if date not in daily:
                daily[date] = {
                    "temps":       [],
                    "humidity":    [],
                    "rain":        0,
                    "description": item['weather'][0]['description'].title(),
                    "clouds":      item['clouds']['all']
                }
            daily[date]['temps'].append(item['main']['temp'])
            daily[date]['humidity'].append(item['main']['humidity'])
            daily[date]['rain'] += item.get('rain', {}).get('3h', 0)

        # Clean daily summary
        forecast = []
        for date, d in list(daily.items())[:5]:
            forecast.append({
                "date":        date,
                "temp_max":    round(max(d['temps']), 1),
                "temp_min":    round(min(d['temps']), 1),
                "humidity":    round(sum(d['humidity']) / len(d['humidity']), 1),
                "rain_mm":     round(d['rain'], 2),
                "description": d['description'],
                "clouds":      d['clouds']
            })

        return forecast

    except requests.exceptions.RequestException as e:
        print(f"  ❌ Request failed: {e}")
        return None


# ──────────────────────────────────────────────────
# FARMING ADVICE
# ──────────────────────────────────────────────────

def get_irrigation_advice(forecast, stress_summary):
    """
    Weather forecast + crop stress combine பண்ணி
    irrigation timing advice kudukum.
    """
    if not forecast:
        return "No Weather data — manually decide"

    total_rain = sum(d['rain_mm'] for d in forecast[:3])  # Next 3 days rain
    has_water_stress = 'water_stress' in (stress_summary or {})

    if total_rain > 20:
            return "🌧️ Heavy rain is expected over the next 3 days — irrigation can be skipped."
    elif total_rain > 8:
        if has_water_stress:
            return "🌦️ Some rain is expected — apply only light irrigation."
        return "🌦️ Rain is expected — irrigation is not required."
    elif total_rain > 0:
        if has_water_stress:
            return "⚠️ Low rainfall is expected — plan irrigation accordingly."
        return "🌤️ Light rain is expected — monitor the field conditions."

    else:
        if has_water_stress:
            return "🚨 No rain is expected and water stress is detected — irrigate immediately."
        return "☀️ No rain is expected — check soil moisture before irrigating."

def get_pesticide_advice(forecast):
    """
  Suggests the best day for pesticide spraying.

Recommends a day with no rain and low wind for effective pesticide application.

    """
    if not forecast:
        return "no Weather data"

    best_days = []
    for day in forecast:
        if day['rain_mm'] < 2 and day['clouds'] < 60:
            best_days.append(day['date'])

    if best_days:
        return f"✅ To Spray best days: {', '.join(best_days[:2])}"
    return "⚠️ this week rain / cloud high — spray postpone should be postpone"


def get_heat_stress_advice(forecast):
    """High temperature crop stress warning."""
    if not forecast:
        return "🌡️ No Weather data — No temperature check "
    hot_days = [d for d in forecast if d['temp_max'] > 38]
    if hot_days:
        dates = ', '.join(d['date'] for d in hot_days)
        return f"🌡️ Heat stress warning: {dates} — do Morning irrigation "
    return "🌡️ Temperature in normal range"


# ──────────────────────────────────────────────────
# MAIN FUNCTION
# ──────────────────────────────────────────────────

def get_weather_report(lat, lon, stress_summary=None):
    """
    Full weather report + farming advice.
    gemini_chat.py will use this
    """
    print("\n" + "="*45)
    print("  AGSKY Weather Analysis Starting...")
    print("="*45)

    # Current weather
    print("\n  🌤️ Fetching current weather...")
    current = get_current_weather(lat, lon)

    if current:
        print(f"  📍 Location    : {current['city']}")
        print(f"  🌡️  Temperature : {current['temp']}°C "
              f"(Feels {current['feels_like']}°C)")
        print(f"  💧 Humidity    : {current['humidity']}%")
        print(f"  ☁️  Clouds      : {current['clouds']}%")
        print(f"  🌬️  Wind        : {current['wind_speed']} m/s")
        print(f"  🌧️  Rain (1hr)  : {current['rain_1h']} mm")
        print(f"  📋 Condition   : {current['description']}")

    # 5-day forecast
    print("\n  📅 Fetching 5-day forecast...")
    forecast = get_forecast(lat, lon)

    if forecast:
        print(f"\n  {'Date':^12} {'Max':>6} {'Min':>6} {'Rain':>8} {'Humidity':>10}")
        print("  " + "-"*46)
        for d in forecast:
            print(f"  {d['date']:^12} {d['temp_max']:>5}°C "
                  f"{d['temp_min']:>5}°C "
                  f"{d['rain_mm']:>6.1f}mm "
                  f"{d['humidity']:>8}%")

    # Farming advice
    print("\n  🌾 Farming Advice:")
    irrigation = get_irrigation_advice(forecast, stress_summary)
    pesticide  = get_pesticide_advice(forecast)
    heat       = get_heat_stress_advice(forecast)

    print(f"  💧 Irrigation  : {irrigation}")
    print(f"  🐛 Pesticide   : {pesticide}")
    print(f"  {heat}")

    print("\n  ✅ Weather report complete!")
    print("  📤 Next: Run market_price.py ")
    print("="*45 + "\n")

    return {
        "current":          current,
        "forecast":         forecast,
        "irrigation_advice": irrigation,
        "pesticide_advice":  pesticide,
        "heat_advice":       heat
    }


# ──────────────────────────────────────────────────
# STANDALONE TEST
# ──────────────────────────────────────────────────

if __name__ == "__main__":
    print("Starting weather_api.py test...")

    if not WEATHER_API_KEY:
        print("❌ WEATHER_API_KEY empty — Add config.py")
        sys.exit(1)

    # Test with dummy stress summary
    dummy_stress = {"water_stress": ["SE", "SW"]}

    result = get_weather_report(
        lat            = 11.0168,
        lon            = 76.9558,
        stress_summary = dummy_stress
    )

    if result['current']:
        print("✅ weather_api.py test passed!")
        print("   Next: Run market_price.py")
    else:
        print("❌ weather_api.py failed — Check API key")