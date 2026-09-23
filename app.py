"""
app.py - AGSKY Main Flask Server (Phase 1)
Focused only on: satellite + grid + cell chat
Weather/Market/AI-report REMOVED from dashboard (used elsewhere in Phase 3).
"""

import sys
import os
import webbrowser
import threading
from flask import Flask, render_template, request, jsonify

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(BASE_DIR, 'satellite_data'))

from gee_auth       import setup_gee
from grid_maker     import calculate_grid
from land_validator import validate_land
from crop_stress    import analyze_crop_stress
from gemini_chat    import call_gemini, call_gemini_vision, call_gemini_smart
from mongo_handler  import save_analysis, get_latest_session, get_all_sessions, get_user_cached_dashboard
from config         import GEMINI_API_KEY


app = Flask(__name__)
GEE_READY = False


def init_gee():
    global GEE_READY
    GEE_READY = setup_gee()
    return GEE_READY


# ── PAGES ──
@app.route('/')
def welcome():
    return render_template('welcome.html')


@app.route('/auth')
def auth_page():
    return render_template('auth.html')


@app.route('/map')
def map_page():
    return render_template('map.html')


@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')


# ── API: AUTH (SIGN UP / SIGN IN) ──
@app.route('/api/signup', methods=['POST'])
def api_signup():
    """
    Simple signup — no password hashing (demo MVP).
    Stores user in MongoDB 'users' collection.
    """
    from mongo_handler import get_db
    from datetime import datetime, timezone

    data = request.get_json() or {}
    name          = (data.get('name') or '').strip()
    phone         = (data.get('phone') or '').strip()
    password      = (data.get('password') or '').strip()
    land_type     = data.get('land_type', '')
    crop          = data.get('crop', '')
    days_planted  = data.get('days_planted', 0)

    # Validation
    if not name or not phone or not password:
        return jsonify({"error": "All fields required"}), 400
    if not phone.isdigit() or len(phone) != 10:
        return jsonify({"error": "Invalid phone number"}), 400
    if land_type not in ('nanjai', 'punjai'):
        return jsonify({"error": "Invalid land type"}), 400
    if not crop:
        return jsonify({"error": "Crop required"}), 400

    try:
        db = get_db()
        users = db['users']

        # Check existing
        existing = users.find_one({"phone": phone})
        if existing:
            return jsonify({"error": "Phone already registered. Please sign in."}), 400

        user_doc = {
            "name":          name,
            "phone":         phone,
            "password":      password,  # plain - demo only
            "land_type":     land_type,
            "crop":          crop,
            "days_planted":  int(days_planted),
            "created_at":    datetime.now(timezone.utc),
            "updated_at":    datetime.now(timezone.utc)
        }

        result = users.insert_one(user_doc)
        user_doc['_id'] = str(result.inserted_id)
        del user_doc['password']  # don't return password
        user_doc['created_at'] = user_doc['created_at'].isoformat()
        user_doc['updated_at'] = user_doc['updated_at'].isoformat()

        return jsonify({"success": True, "user": user_doc})

    except Exception as e:
        print(f"  ❌ Signup error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/signin', methods=['POST'])
def api_signin():
    """Simple signin — phone + password match."""
    from mongo_handler import get_db

    data = request.get_json() or {}
    phone    = (data.get('phone') or '').strip()
    password = (data.get('password') or '').strip()

    if not phone or not password:
        return jsonify({"error": "Phone and password required"}), 400

    try:
        db = get_db()
        user = db['users'].find_one({"phone": phone, "password": password})

        if not user:
            return jsonify({"error": "Invalid phone or password"}), 401

        # Clean response — convert ALL ObjectIds and datetimes recursively
        user = _clean_mongo_doc(user)
        user.pop('password', None)  # Never return password

        return jsonify({"success": True, "user": user})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


def _clean_mongo_doc(doc):
    """Recursively convert ObjectIds + datetimes to JSON-safe values."""
    from bson import ObjectId
    from datetime import datetime

    if isinstance(doc, dict):
        return {k: _clean_mongo_doc(v) for k, v in doc.items()}
    elif isinstance(doc, list):
        return [_clean_mongo_doc(v) for v in doc]
    elif isinstance(doc, ObjectId):
        return str(doc)
    elif isinstance(doc, datetime):
        return doc.isoformat()
    else:
        return doc


@app.route('/api/update-profile', methods=['POST'])
def api_update_profile():
    """Update user's farm details (crop, land_type, days_planted)."""
    from mongo_handler import get_db
    from bson import ObjectId
    from datetime import datetime, timezone

    data = request.get_json() or {}
    user_id = data.get('user_id')

    if not user_id:
        return jsonify({"error": "User ID required"}), 400

    update_fields = {}
    for field in ['name', 'land_type', 'crop', 'days_planted']:
        if field in data:
            update_fields[field] = data[field]

    if not update_fields:
        return jsonify({"error": "No fields to update"}), 400

    update_fields['updated_at'] = datetime.now(timezone.utc)

    try:
        db = get_db()
        db['users'].update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update_fields}
        )
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500



# ── API: LAND VALIDATION ──
@app.route('/api/validate-land', methods=['POST'])
def api_validate_land():
    data = request.get_json()
    try:
        lat = float(data['lat'])
        lon = float(data['lon'])
    except (KeyError, ValueError, TypeError):
        return jsonify({"error": "Invalid lat/lon"}), 400

    if not GEE_READY:
        return jsonify({"error": "GEE not ready. Please wait a moment and retry."}), 503

    try:
        result = validate_land(lat, lon)
        if not result:
            return jsonify({
                "error": "Could not validate this location. Try a different area or check internet connection."
            }), 500
        return jsonify(result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Validation error: {str(e)}"}), 500


# ── API: GRID PREVIEW ──
@app.route('/api/grid', methods=['POST'])
def api_grid():
    data = request.get_json()
    try:
        lat   = float(data['lat'])
        lon   = float(data['lon'])
        acres = float(data['acres'])
    except (KeyError, ValueError):
        return jsonify({"error": "Invalid input"}), 400

    start_lat, start_lon, sub_lat, sub_lon = calculate_grid(lat, lon, acres)

    labels = [
        ["SW", "S",      "SE"],
        ["W",  "CENTER", "E" ],
        ["NW", "N",      "NE"],
    ]

    cells = []
    for row in range(3):
        for col in range(3):
            label = labels[row][col]
            ctype = ("center" if label == "CENTER"
                     else "cardinal" if label in ["N","S","E","W"]
                     else "diagonal")
            cells.append({
                "label": label, "type": ctype,
                "bounds": {
                    "south": start_lat + row * sub_lat,
                    "north": start_lat + (row + 1) * sub_lat,
                    "west":  start_lon + col * sub_lon,
                    "east":  start_lon + (col + 1) * sub_lon,
                }
            })

    return jsonify({
        "cells":  cells,
        "center": {"lat": lat, "lon": lon},
        "acres":  acres,
        "grid_bounds": {
            "south": start_lat, "north": start_lat + 3 * sub_lat,
            "west":  start_lon, "east":  start_lon + 3 * sub_lon,
        }
    })


# ── API: FULL ANALYSIS (Phase 1 — satellite only) ──
@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    """
    Phase 1: ONLY satellite + grid + stress analysis.
    """
    data = request.get_json()
    try:
        lat   = float(data['lat'])
        lon   = float(data['lon'])
        acres = float(data['acres'])
    except (KeyError, ValueError):
        return jsonify({"error": "Invalid input"}), 400

    user_id = data.get('user_id')  # Link session to user

    if not GEE_READY:
        return jsonify({"error": "GEE not ready"}), 503

    try:
        # Step 1: Crop stress analysis
        stress = analyze_crop_stress(lat, lon, acres, days_back=20)
        if not stress:
            return jsonify({"error": "Satellite analysis failed"}), 500

        # Step 2: Get Sentinel-2 thumbnail
        sentinel_url = _get_sentinel_thumbnail(lat, lon, acres)

        # Step 3: Save to MongoDB (WITH user_id)
        session_id = save_analysis(stress, user_id=user_id)

        # Step 4: Return clean response
        return jsonify({
            "session_id":   session_id,
            "lat":          lat,
            "lon":          lon,
            "acres":        acres,
            "health_score": stress['grid_result']['summary']['health_score'],
            "farm_status":  stress['farm_status'],
            "grid":         stress['grid_result']['grid'],
            "grid_bounds":  _get_grid_bounds(lat, lon, acres),
            "sentinel_url": sentinel_url,
            "zones":        stress['grid_result']['zones'],
            "water_zones":  stress['grid_result']['water_zones'],
            "cell_stress":  stress['cell_stress'],
            "priority_cell": {
                "label":  stress['priority_cell'][0],
                "stress": stress['priority_cell'][1]['stress_type']
            },
            "cached": False
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ── API: CACHED DASHBOARD (for returning users) ──
@app.route('/api/cached-dashboard/<user_id>', methods=['GET'])
def api_cached_dashboard(user_id):
    """
    User's last saved dashboard data. No satellite re-fetch.
    Used when user signs in — instant dashboard load.
    """
    try:
        data = get_user_cached_dashboard(user_id)
        if not data:
            return jsonify({"has_cache": False}), 200
        data['has_cache'] = True
        # Recursively clean any remaining ObjectIds / datetimes
        data = _clean_mongo_doc(data)
        return jsonify(data)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e), "has_cache": False}), 500


def _get_grid_bounds(lat, lon, acres):
    start_lat, start_lon, sub_lat, sub_lon = calculate_grid(lat, lon, acres)
    return {
        "south": start_lat, "north": start_lat + 3 * sub_lat,
        "west":  start_lon, "east":  start_lon + 3 * sub_lon,
    }


def _get_sentinel_thumbnail(lat, lon, acres):
    """
    Sentinel-2 RGB image of EXACT grid bounds (the farmer's real land).
    Returns: thumbnail URL for image overlay on map.
    """
    try:
        import ee
        from datetime import datetime, timezone, timedelta

        start_lat, start_lon, sub_lat, sub_lon = calculate_grid(lat, lon, acres)

        # Exact grid bounds
        geometry = ee.Geometry.Rectangle([
            start_lon,
            start_lat,
            start_lon + 3 * sub_lon,
            start_lat + 3 * sub_lat
        ])

        end_date   = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=30)

        collection = (
            ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
            .filterBounds(geometry)
            .filterDate(start_date.strftime('%Y-%m-%d'),
                        end_date.strftime('%Y-%m-%d'))
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30))
            .sort('CLOUDY_PIXEL_PERCENTAGE')
        )

        count = collection.size().getInfo()
        if count == 0:
            return None

        best = collection.first()
        thumb_url = best.getThumbURL({
            'region':     geometry,
            'dimensions': 1024,
            'bands':      ['B4', 'B3', 'B2'],
            'min':        300,
            'max':        2800,
            'gamma':      1.2,
            'format':     'png'
        })
        return thumb_url
    except Exception as e:
        print(f"  ⚠️  Sentinel thumbnail failed: {e}")
        return None


# ── API: CELL CHAT (NEW for Phase 1) ──
@app.route('/api/cell-chat', methods=['POST'])
def api_cell_chat():
    """
    Gemini speaks AS THE CELL in first person.
    Used by dashboard.html when farmer clicks any grid cell.
    """
    data = request.get_json()
    cell_label = data.get('cell_label', '')
    cell_data  = data.get('cell_data', {})
    question   = data.get('question', '')
    history    = data.get('history', [])
    language   = data.get('language', 'english')

    if not cell_label:
        return jsonify({"error": "No cell"}), 400

    # ── LANGUAGE INSTRUCTION (strict with examples) ──
    # 3 language options: english, tamil (pure Tamil script), tanglish (Tamil in English letters)
    lang_instructions = {
        "english": """RESPOND ONLY IN SIMPLE ENGLISH.
Use short farmer-friendly English sentences.
Example: "Hi farmer! I'm your North patch. I'm feeling thirsty today, please give me water tomorrow morning."
""",
        "tamil": """தமிழில் மட்டுமே பதில் சொல்லுங்கள். ஆங்கில எழுத்துக்கள் பயன்படுத்த வேண்டாம். ஆங்கில வார்த்தைகள் சேர்க்க வேண்டாம்.

சரியான பதில் எடுத்துக்காட்டு (இப்படி மட்டுமே எழுதுங்கள்):
✅ "வணக்கம் விவசாயி! நான் உங்கள் வடக்கு பகுதி. இன்று கொஞ்சம் தாகமாக இருக்கிறேன். தயவுசெய்து நாளை காலை தண்ணீர் கொடுங்கள்."
✅ "நான் நன்றாக இருக்கிறேன். ஆனால் என்னுடைய இலைகள் மஞ்சளாக மாறுகின்றன."

தவறான பதில் (இப்படி எழுத வேண்டாம்):
❌ "Vanakkam farmer! Naan unga North patch..." (தமிழ் எழுத்துக்கள் இல்லை)
❌ "வணக்கம் farmer! Water kudunga" (ஆங்கிலம் கலந்தது)

விதிகள்:
- அனைத்து வார்த்தைகளும் தமிழ் எழுத்துக்களில் மட்டுமே
- NDVI, EVI போன்ற technical terms ஆங்கிலத்தில் இருக்கலாம் (அவை brand names மாதிரி)
- வெளிப்படையான, எளிமையான தமிழ் பயன்படுத்துங்கள்
- விவசாயிக்கு புரியும் சாதாரண தமிழ் வார்த்தைகள்
""",
        "tanglish": """RESPOND ONLY IN TANGLISH (Tamil words written in English alphabet). DO NOT write pure English.
Every sentence must have Tamil words written in English letters.
Examples of CORRECT tanglish:
  ✅ "Vanakkam farmer! Naan unga north patch. Ippo konjam thaagama iruken, nalaikku kaalaila thanni kudunga."
  ✅ "Bro enaku thanni thevai, leaves laam yellow ah iruku."
  ✅ "Konjam drip irrigation pannunga, 30 min pothum."

Examples of WRONG (pure English) — DO NOT do this:
  ❌ "Hi farmer! I'm your north patch, I'm feeling thirsty."
  ❌ "I need water, please give me some."

You MUST use Tamil words like: naan (I), unga (your), iruken (I am), thanni (water),
kudunga (give), nalaikku (tomorrow), ippo (now), konjam (little), aagum (will), illa (no),
paarunga (see), pannunga (do), thevai (need), iruku (there is), romba (very), seri (ok).

MIXING is fine ("drip irrigation pannunga" = mixing English noun with Tamil verb)
but majority verbs/pronouns MUST be Tanglish."""
    }

    lang_note = lang_instructions.get(language, lang_instructions['english'])

    # Extract cell details
    cell = cell_data.get('cell', {})
    stress = cell_data.get('stress', {})
    ndvi = cell.get('ndvi', 'unknown')
    ndwi = cell.get('ndwi', 'unknown')
    evi  = cell.get('evi',  'unknown')
    stress_type = stress.get('stress_type', 'unknown')
    severity    = stress.get('severity', 'unknown')
    actions     = stress.get('actions', [])

    # Build conversation context
    history_text = ""
    if history:
        history_text = "\n\nPrevious conversation:\n"
        for msg in history:
            role = "Farmer" if msg.get('role') == 'user' else "Cell"
            history_text += f"{role}: {msg.get('content', '')}\n"

    # Friendly status interpretation
    def interpret_ndvi(v):
        try: v = float(v)
        except: return "unknown"
        if v >= 0.6: return "very healthy, lush green"
        if v >= 0.4: return "healthy, good vegetation"
        if v >= 0.2: return "moderate, some vegetation"
        if v >= 0.1: return "poor, sparse vegetation"
        return "very poor, almost bare"

    def interpret_ndwi(v):
        try: v = float(v)
        except: return "unknown"
        if v >= 0.3:  return "very wet, possibly waterlogged"
        if v >= 0.1:  return "adequately moist"
        if v >= -0.1: return "slightly dry"
        if v >= -0.3: return "dry, needs water"
        return "very dry, drought condition"

    ndvi_status = interpret_ndvi(ndvi)
    ndwi_status = interpret_ndwi(ndwi)

    # Intro mode - cell introduces itself
    if question == '__intro__':
        prompt = f"""You ARE the {cell_label} patch of a farmer's land — speak in FIRST PERSON as this land.
You are alive, sentient, emotional. You feel things based on your data.

YOUR CURRENT DATA:
- NDVI (vegetation health): {ndvi} → {ndvi_status}
- NDWI (water content): {ndwi} → {ndwi_status}
- EVI: {evi}
- Stress condition: {stress_type}
- Severity: {severity}
- What you need: {', '.join(actions[:3]) if actions else 'nothing urgent'}

{lang_note}

TASK: Introduce yourself to the farmer warmly in 3-4 sentences.
Structure your intro like this:
1. Greet the farmer + identify yourself ("Hi farmer! I'm your {cell_label} patch...")
2. Share how you're FEELING right now (based on stress/ndvi)
   - Use emotional words: "tired", "thirsty", "happy", "struggling", "doing great"
3. Share your CURRENT CONDITION in farmer terms (not technical)
   - Example: "My crops are looking yellow" vs "NDVI is 0.3"
4. Mention ONE thing you need most (water/nutrients/attention)

Be warm, human, emotional. Use 1-2 emojis. Simple words only.

Respond as the cell:"""
    else:
        prompt = f"""You ARE the {cell_label} patch of a farmer's land — speak in FIRST PERSON.
You are alive, sentient, emotional. You feel the weather, water, stress.

YOUR DATA:
- NDVI (vegetation): {ndvi} → {ndvi_status}
- NDWI (water): {ndwi} → {ndwi_status}
- EVI: {evi}
- Stress: {stress_type} ({severity} severity)
- Recommended actions: {', '.join(actions[:3]) if actions else 'None'}

{lang_note}

{history_text}

THE FARMER ASKS: "{question}"

TASK: Respond as the cell in FIRST PERSON.
- Show emotion and personality (you're not a robot!)
- Give SPECIFIC, actionable advice if they ask
- Use farmer-friendly language (no NDVI jargon)
- Reference your CURRENT condition naturally
- Keep response 3-5 sentences max
- Add 1 emoji naturally
- Be warm, caring, like talking to a friend

Respond:"""

    answer = call_gemini(prompt, temperature=0.75, max_tokens=500)

    # DEBUG: print what Gemini returned
    print(f"\n  🤖 Cell Chat Debug:")
    print(f"     Cell: {cell_label}")
    print(f"     Question: {question[:50]}")
    print(f"     Gemini returned: {repr(answer)[:100]}")
    print(f"     Has API key: {'Yes' if GEMINI_API_KEY else 'NO - empty!'}")

    if not answer:
        # Graceful fallback (quota exceeded or error)
        fallback = {
            "english": f"Hi! I'm the {cell_label} patch. Right now I can't chat much, please try again shortly.",
            "tamil":   f"Vanakkam! Naan {cell_label} patch. Ippo konjam busy, konja neram kazhichi pesalam.",
            "hindi":   f"Namaste! Main {cell_label} patch hoon. Abhi thoda busy hoon, kuch samay baad baat karenge.",
            "telugu":  f"Namaste! Nenu {cell_label} patch. Ippudu koncham busy, konchem tarvata matladudaam."
        }
        answer = fallback.get(language, fallback['english'])

    return jsonify({"answer": answer})


# ── API: SESSIONS (existing) ──
@app.route('/api/session', methods=['GET'])
def api_latest_session():
    session = get_latest_session()
    if not session:
        return jsonify({"session": None})
    session['_id'] = str(session['_id'])
    if 'timestamp' in session:
        session['timestamp'] = session['timestamp'].isoformat()
    return jsonify({"session": session})


@app.route('/api/sessions', methods=['GET'])
def api_all_sessions():
    sessions = get_all_sessions()
    for s in sessions:
        s['_id'] = str(s['_id'])
        if 'timestamp' in s:
            s['timestamp'] = s['timestamp'].isoformat()
    return jsonify({"sessions": sessions})


# ═══════════════════════════════════════════════════
# PEST DETECTION APIs (Phase 2)
# ═══════════════════════════════════════════════════

@app.route('/api/scan-disease', methods=['POST'])
def api_scan_disease():
    """
    Camera/upload scan → Gemini Vision analyzes crop leaf image.
    Uses user's specific crop + days planted for contextual advice.
    """
    import json as json_lib
    import re
    from mongo_handler import get_db
    from bson import ObjectId

    data = request.get_json() or {}
    image_base64 = data.get('image_base64', '')
    user_id      = data.get('user_id', '')
    crop         = data.get('crop', 'unknown crop')
    language     = data.get('language', 'english')

    if not image_base64:
        return jsonify({"error": "No image provided"}), 400

    # Strip data URL prefix if present
    if ',' in image_base64:
        image_base64 = image_base64.split(',', 1)[1]

    # Fetch user's full farm context
    days_planted = 0
    land_type = "unknown"
    try:
        db = get_db()
        user = db['users'].find_one({"_id": ObjectId(user_id)})
        if user:
            if crop == 'unknown crop':
                crop = user.get('crop', 'unknown')
            days_planted = user.get('days_planted', 0)
            land_type = user.get('land_type', 'unknown')
    except Exception as e:
        print(f"  ⚠️  User fetch failed: {e}")

    # Farming stage
    if days_planted < 15:      stage = "early (sowing/germination)"
    elif days_planted < 30:    stage = "young (fertilizing)"
    elif days_planted < 60:    stage = "growing (irrigation)"
    elif days_planted < 75:    stage = "mid-growth (weeding)"
    elif days_planted < 100:   stage = "mature (protection)"
    elif days_planted < 140:   stage = "harvest-ready"
    else:                      stage = "post-harvest"

    # Language instruction
    lang_map = {
        "english": "Respond in simple conversational English.",
        "tanglish": "Respond in Tanglish (Tamil in English letters). Natural friend-like tone. Example: 'Unga payir leaf curl virus apadi theriyudhu...'",
        "tamil": "தமிழில் மட்டும் பதில். ஆங்கில எழுத்துக்கள் கலக்க வேண்டாம். எடுத்துக்காட்டு: 'உங்கள் பயிருக்கு இலை சுருட்டு நோய் உள்ளது'"
    }
    lang_note = lang_map.get(language, lang_map['english'])

    prompt = f"""You are an expert agricultural pathologist analyzing a crop leaf image.

FARMER'S SPECIFIC CONTEXT:
• Crop: {crop}
• Days since planting: {days_planted} days ({stage} stage)
• Land type: {land_type}
• Location: Tamil Nadu, India

TASK:
1. Analyze the image carefully
2. Identify any disease, pest damage, nutrient deficiency, or health issues
3. Give advice SPECIFIC to this crop at this growth stage
4. If image is NOT a crop leaf, say so clearly

{lang_note}

Respond in STRICT JSON format (no markdown, no code blocks):
{{
  "is_valid_leaf": true or false,
  "disease_name": "name of disease/pest/issue OR 'healthy plant' if no issue",
  "disease_name_local": "disease name in user's chosen language",
  "confidence": "high" or "moderate" or "low",
  "severity": "mild" or "moderate" or "severe" or "none",
  "description": "2-3 sentence farmer-friendly explanation mentioning {crop} at {days_planted} days stage",
  "symptoms": ["symptom 1", "symptom 2", "symptom 3"],
  "natural_remedy": {{
    "name": "remedy name",
    "ingredients": "ingredients with quantities",
    "application": "how to apply",
    "frequency": "how often"
  }},
  "chemical_remedy": {{
    "name": "chemical name",
    "dosage": "amount per liter",
    "application": "how to apply",
    "price_range": "approx cost in INR",
    "caution": "safety note"
  }},
  "prevention_tips": ["tip 1", "tip 2", "tip 3"]
}}

If image is clearly NOT a crop leaf, return:
{{"is_valid_leaf": false, "error_message": "Please upload a clear photo of a crop leaf"}}
"""

    raw_response = call_gemini_vision(prompt, image_base64, temperature=0.3, max_tokens=1500)

    if not raw_response:
        return jsonify({
            "error": "AI analysis failed. Please try again.",
            "is_valid_leaf": False
        }), 500

    # ── ROBUST JSON EXTRACTION ──
    def extract_json(text):
        import json as json_lib
        import re
        if not text:
            return None
        try:
            return json_lib.loads(text.strip())
        except:
            pass
        cleaned = re.sub(r'```(?:json)?\s*', '', text)
        cleaned = re.sub(r'```\s*$', '', cleaned).strip()
        try:
            return json_lib.loads(cleaned)
        except:
            pass
        match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if match:
            try:
                return json_lib.loads(match.group(0))
            except:
                pass
        start = cleaned.find('{')
        if start >= 0:
            depth = 0
            for i in range(start, len(cleaned)):
                if cleaned[i] == '{': depth += 1
                elif cleaned[i] == '}':
                    depth -= 1
                    if depth == 0:
                        try:
                            return json_lib.loads(cleaned[start:i+1])
                        except:
                            break
        return None

    result = extract_json(raw_response)

    if result and isinstance(result, dict):
        result['crop'] = crop
        result['days_planted'] = days_planted

        # Save to MongoDB if valid leaf
        if result.get('is_valid_leaf', True) and user_id:
            try:
                from datetime import datetime, timezone
                db = get_db()
                if db is not None:
                    db['pest_scans'].insert_one({
                        "user_id":     user_id,
                        "timestamp":   datetime.now(timezone.utc),
                        "crop":        crop,
                        "days_planted": days_planted,
                        "disease":     result.get('disease_name', 'unknown'),
                        "confidence":  result.get('confidence', 'low'),
                        "severity":    result.get('severity', 'unknown'),
                        "language":    language
                    })
            except Exception as e:
                print(f"  ⚠️  Pest scan save failed: {e}")

        return jsonify(result)

    # Fallback
    print(f"  ⚠️  Scan JSON parse failed. Raw: {raw_response[:300]}")
    return jsonify({
        "is_valid_leaf": True,
        "disease_name": "Analysis needs retry",
        "description": "Could not fully parse. Please scan again.",
        "confidence": "low",
        "severity": "none",
        "parse_error": True
    })


@app.route('/api/predict-pest', methods=['POST'])
def api_predict_pest():
    """
    Grid-based pest prediction using:
    - Cell's NDVI/NDWI/EVI scores
    - User's crop + days_planted
    - Location (lat/lon) → climate zone
    - Farming stage (auto-calculated)
    """
    from mongo_handler import get_db
    from bson import ObjectId

    data = request.get_json() or {}
    cell_label   = data.get('cell_label', '')
    cell_data    = data.get('cell_data', {})
    user_id      = data.get('user_id', '')
    language     = data.get('language', 'english')

    if not cell_label or not user_id:
        return jsonify({"error": "Missing cell or user info"}), 400

    # Fetch user profile for full context
    user_crop = "unknown"
    days_planted = 0
    land_type = "unknown"
    lat = 0
    lon = 0
    try:
        db = get_db()
        user = db['users'].find_one({"_id": ObjectId(user_id)})
        if user:
            user_crop = user.get('crop', 'unknown')
            days_planted = user.get('days_planted', 0)
            land_type = user.get('land_type', 'unknown')
            lat = user.get('last_lat', 0)
            lon = user.get('last_lon', 0)
    except Exception as e:
        print(f"  ⚠️  User fetch failed: {e}")

    cell = cell_data.get('cell', {})
    stress = cell_data.get('stress', {})
    ndvi = cell.get('ndvi', 'unknown')
    ndwi = cell.get('ndwi', 'unknown')
    evi = cell.get('evi', 'unknown')
    stress_type = stress.get('stress_type', 'unknown')
    severity = stress.get('severity', 'unknown')

    # Auto-detect farming stage based on days
    stage = "unknown"
    if days_planted < 0:       stage = "soil preparation"
    elif days_planted < 15:    stage = "sowing"
    elif days_planted < 30:    stage = "manuring/fertilizing"
    elif days_planted < 60:    stage = "irrigation/early growth"
    elif days_planted < 75:    stage = "weeding"
    elif days_planted < 100:   stage = "crop protection"
    elif days_planted < 140:   stage = "harvesting"
    else:                      stage = "post-harvest"

    # NDVI health interpretation
    def ndvi_meaning(v):
        try: v = float(v)
        except: return "unknown"
        if v >= 0.6: return "very healthy"
        if v >= 0.4: return "healthy"
        if v >= 0.25: return "moderate (some stress)"
        if v >= 0.1: return "poor (stressed crop)"
        return "very poor (weak/dying)"

    ndvi_desc = ndvi_meaning(ndvi)

    # Language instruction
    lang_map = {
        "english": """Respond in conversational English — like a knowledgeable friend chatting.
Example style: "Hey! Looking at your tomato at 30 days with low NDVI of 0.25, I'd say you're at moderate risk for leaf curl virus..."
Keep it natural, friendly, not formal.""",
        "tanglish": """Respond in Tanglish (Tamil in English letters) — like a knowledgeable friend chatting naturally.
Example style: "Bro unga tomato 30 naal aachu, NDVI 0.25 la iruku konjam low. Ithu leaf curl virus ku risk iruku..."
Natural conversation tone, not formal.""",
        "tamil": """தமிழில் மட்டும் பதில் — நண்பர் மாதிரி எளிமையாக பேசுங்கள்.
எடுத்துக்காட்டு: "உங்கள் தக்காளி 30 நாள் ஆச்சு, NDVI 0.25 குறைவு. இலை சுருட்டு நோய் வர வாய்ப்பு இருக்கு..."
ஆங்கில எழுத்துக்கள் கலக்க வேண்டாம்."""
    }
    lang_note = lang_map.get(language, lang_map['english'])

    prompt = f"""You are an agricultural pest expert advising a Tamil Nadu farmer.

═══ FARMER'S SPECIFIC CONTEXT ═══
• Crop: {user_crop}
• Land type: {land_type}
• Days since planting: {days_planted} days
• Current farming stage: {stage}
• Location: {lat}, {lon} (Tamil Nadu region)

═══ THIS SPECIFIC CELL'S DATA ═══
• Grid position: {cell_label}
• NDVI: {ndvi} → {ndvi_desc}
• NDWI (water): {ndwi}
• EVI: {evi}
• Current stress detected: {stress_type} ({severity})

═══ TASK ═══
Based on ALL of the above data, predict the MOST LIKELY pest/disease threat for THIS specific cell.
Reference the SPECIFIC numbers in your reasoning. Don't be generic.

Determine confidence:
- HIGH: Strong evidence (matching NDVI pattern + known crop-stage pest)
- MODERATE: Good indicators but not certain
- LOW: General precaution, not specific evidence

{lang_note}

⚠️ CRITICAL: You MUST respond with ONLY valid JSON. Start your response with {{ and end with }}.
Do NOT include any explanation, markdown, code blocks, or text outside the JSON.

═══ RESPONSE LOGIC — FOLLOW THESE RULES STRICTLY ═══

Based on the data, determine which SCENARIO applies:

**SCENARIO A — WATER ISSUE (no pest):**
When NDWI is very negative (< -0.1) OR stress_type is 'water_stress' / 'drought':
→ This is NOT a pest problem — it's a WATER problem
→ threat_type = "water_stress"
→ primary_threat = "Water Deficiency" (or Tamil equivalent)
→ natural_remedy object → give IRRIGATION advice (how much water, when)
→ chemical_remedy → SET TO null (no chemical needed for water issue)
→ show_shop_map = false

**SCENARIO B — MILD PEST/DISEASE:**
When NDVI is moderate (0.3-0.5) AND severity would be 'mild' or 'moderate':
→ threat_type = "mild_pest"
→ Organic treatment is sufficient
→ natural_remedy object → specific organic solution for THIS pest
→ chemical_remedy → SET TO null (organic is enough)
→ show_shop_map = false

**SCENARIO C — CRITICAL PEST/DISEASE:**
When NDVI is very low (< 0.3) OR specific pest pattern detected strongly:
→ threat_type = "critical_pest"
→ BOTH natural + chemical needed
→ natural_remedy object → organic option
→ chemical_remedy object → specific chemical with brand names
→ show_shop_map = true

═══ NATURAL REMEDY VARIETY ═══
Do NOT always say "neem oil". Pick SPECIFIC remedy based on pest type:
• Aphids → "Garlic-chili extract" or "Ladybug release" or "Soap spray"
• Whiteflies → "Yellow sticky traps" or "Neem seed kernel extract (NSKE 5%)"
• Leaf Curl Virus → "Milk spray (1:10)" or "Turmeric + neem decoction"
• Fungal (rust, blight) → "Cow urine spray (1:10)" or "Trichoderma viride"
• Bacterial blight → "Garlic-ginger extract" or "Panchagavya"
• Stem Borer → "Pheromone traps" or "Trichogramma release"
• Mites → "Sulphur dust" or "Garlic spray"
• Thrips → "Blue sticky traps" or "Beauveria bassiana"
• Water stress → "Drip irrigation schedule" (not neem!)
• Nutrient stress → "Vermicompost tea" or "Panchagavya"

═══ JSON STRUCTURE ═══
Return THIS EXACT structure (keep null where applicable):
{{
  "scenario": "water" or "mild_pest" or "critical_pest",
  "risk_level": "high" or "moderate" or "low",
  "confidence": "high" or "moderate" or "low",
  "primary_threat": "specific threat name (not generic)",
  "short_summary": "One sentence: mention crop name, {days_planted} days, NDVI {ndvi}, NDWI {ndwi}, and threat (max 35 words)",
  "key_reason": "WHY this threat — reference specific NDVI/NDWI values",
  "action_now": "Single most important action TODAY",
  "natural_remedy": {{
    "name": "specific name (DIVERSE — not always neem)",
    "recipe": "ingredients with quantities",
    "how_to_use": "application instructions"
  }},
  "chemical_remedy": null OR {{
    "chemical_name": "EXACT chemical name (e.g. 'Imidacloprid 17.8% SL')",
    "brand_names": "Indian brands (e.g. 'Confidor, Tata Bahaar')",
    "dosage": "amount per liter",
    "price_range": "₹ range (e.g. '₹150-250')",
    "how_to_use": "when and how to spray"
  }},
  "show_shop_map": true or false
}}

IMPORTANT: If scenario is "water" or "mild_pest", set chemical_remedy to null and show_shop_map to false.

RESPOND ONLY WITH THE JSON."""

    # Use 2.5 Flash (smart model) for better accuracy
    raw_response = call_gemini_smart(prompt, temperature=0.3, max_tokens=1200)

    if not raw_response:
        return jsonify({"error": "Prediction failed"}), 500

    # ── ROBUST JSON EXTRACTION ──
    def extract_json(text):
        import json as json_lib
        import re

        if not text:
            return None

        # Try 1: Parse as-is
        try:
            return json_lib.loads(text.strip())
        except:
            pass

        # Try 2: Remove markdown code fences
        cleaned = re.sub(r'```(?:json)?\s*', '', text)
        cleaned = re.sub(r'```\s*$', '', cleaned).strip()
        try:
            return json_lib.loads(cleaned)
        except:
            pass

        # Try 3: Extract first {...} block using regex (handles nested braces)
        match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if match:
            try:
                return json_lib.loads(match.group(0))
            except:
                pass

        # Try 4: Find balanced braces manually
        start = cleaned.find('{')
        if start >= 0:
            depth = 0
            for i in range(start, len(cleaned)):
                if cleaned[i] == '{': depth += 1
                elif cleaned[i] == '}':
                    depth -= 1
                    if depth == 0:
                        try:
                            return json_lib.loads(cleaned[start:i+1])
                        except:
                            break
        return None

    result = extract_json(raw_response)

    if result and isinstance(result, dict):
        result['cell_label'] = cell_label
        result['crop'] = user_crop
        result['days_planted'] = days_planted
        result['stage'] = stage
        result['ndvi'] = ndvi
        return jsonify(result)

    # If all JSON parsing fails, return structured fallback
    print(f"  ⚠️  JSON parse failed. Raw response: {raw_response[:300]}")
    return jsonify({
        "risk_level": "moderate",
        "confidence": "low",
        "primary_threat": "Analysis in progress",
        "short_summary": f"Your {user_crop} at {days_planted} days — please try again for detailed analysis.",
        "key_reason": "Parse error, please retry",
        "action_now": "Monitor crop daily for visible symptoms",
        "natural_remedy": {
            "name": "Neem oil spray",
            "recipe": "5ml neem oil + 1L water + 1g mild soap",
            "how_to_use": "Spray evening, cover both sides of leaves"
        },
        "chemical_remedy": {
            "chemical_name": "Consult local agriculture officer",
            "dosage": "—",
            "price_range": "—",
            "how_to_use": "Retry for specific recommendation"
        },
        "parse_error": True
    })


@app.route('/api/pest-chat', methods=['POST'])
def api_pest_chat():
    """
    Follow-up conversation about the predicted pest.
    Uses 2.5 Flash (smart) for domain expertise.
    """
    data = request.get_json() or {}
    question = data.get('question', '').strip()
    context = data.get('context', {})  # predicted pest details
    history = data.get('history', [])
    language = data.get('language', 'english')

    if not question:
        return jsonify({"error": "No question"}), 400

    history_text = ""
    if history:
        history_text = "\n\nPREVIOUS CHAT:\n"
        for msg in history[-6:]:
            role = "Farmer" if msg.get('role') == 'user' else "Expert"
            history_text += f"{role}: {msg.get('content', '')}\n"

    lang_map = {
        "english": "Respond in simple conversational English. Short and clear.",
        "tanglish": "Respond in Tanglish (Tamil in English letters). Natural friend-like tone.",
        "tamil": "தமிழில் மட்டும் பதில். ஆங்கிலம் கலக்க வேண்டாம்."
    }
    lang_note = lang_map.get(language, lang_map['english'])

    prompt = f"""You are a friendly pest/disease expert talking to a Tamil Nadu farmer.

CURRENT SITUATION (from earlier prediction):
• Crop: {context.get('crop', 'unknown')}
• Days planted: {context.get('days_planted', 0)}
• Cell: {context.get('cell_label', '—')}
• NDVI: {context.get('ndvi', '—')}
• Predicted threat: {context.get('primary_threat', 'unknown')}
• Risk level: {context.get('risk_level', 'unknown')}

{history_text}

FARMER ASKS: "{question}"

{lang_note}

Respond like a friendly expert:
- 2-4 sentences max
- Specific and actionable
- Natural conversation (not robotic)
- Use farmer-friendly words
- Add emoji if helpful

Response:"""

    answer = call_gemini_smart(prompt, temperature=0.7, max_tokens=400)

    if not answer:
        return jsonify({"answer": "Sorry, please try again."}), 200

    return jsonify({"answer": answer})


@app.route('/api/pest-history/<user_id>', methods=['GET'])
def api_pest_history(user_id):
    """Get user's past pest scans."""
    from mongo_handler import get_db
    try:
        db = get_db()
        scans = list(db['pest_scans'].find(
            {"user_id": user_id}
        ).sort("timestamp", -1).limit(10))

        scans = [_clean_mongo_doc(s) for s in scans]
        return jsonify({"scans": scans})
    except Exception as e:
        return jsonify({"error": str(e), "scans": []}), 500


# ── RUN ──
if __name__ == '__main__':
    print("\n" + "="*50)
    print("  🌾 AGSKY — Phase 1 (Satellite + Cell Chat)")
    print("="*50)

    print("\n  🔐 Initializing Google Earth Engine...")
    if init_gee():
        print("  ✅ GEE Ready!")
    else:
        print("  ⚠️  GEE init failed")

    print("\n  🚀 Starting Flask server...")
    print("  🌐 Opening http://127.0.0.1:5000")
    print("  ❌ Stop: Ctrl + C")
    print("="*50 + "\n")

    threading.Timer(
        1.5,
        lambda: webbrowser.open('http://127.0.0.1:5000')
    ).start()

    app.run(debug=False, port=5000)