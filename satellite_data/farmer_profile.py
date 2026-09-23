"""
farmer_profile.py
-----------------
Farmer Onboarding — Collects crop details from the farmer and stores them in MongoDB.

Conversational chatbot style:
  1. Farmer name
  2. Phone number (for future SMS alerts)
  3. Crop type
  4. Planting date
  5. Current stage
  6. Last irrigation date
  7. Last pesticide date
  8. Soil type (optional)

Linked to farm_sessions via session_id.

Test:
    python farmer_profile.py
"""

import sys
import os
from datetime import datetime, timezone, timedelta

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from mongo_handler import get_db, get_latest_session


# ──────────────────────────────────────────────────
# CROP STAGES (Tamil Nadu common crops)
# ──────────────────────────────────────────────────

CROP_STAGES = {
    "Rice":      ["Seedling", "Tillering", "Panicle Initiation", "Flowering", "Grain Filling", "Harvest"],
    "Paddy":     ["Seedling", "Tillering", "Panicle Initiation", "Flowering", "Grain Filling", "Harvest"],
    "Tomato":    ["Seedling", "Vegetative", "Flowering", "Fruiting", "Ripening", "Harvest"],
    "Onion":     ["Seedling", "Bulb Formation", "Bulb Development", "Maturity", "Harvest"],
    "Maize":     ["Germination", "Vegetative", "Tasseling", "Silking", "Grain Filling", "Harvest"],
    "Groundnut": ["Seedling", "Vegetative", "Flowering", "Pegging", "Pod Development", "Harvest"],
    "Cotton":    ["Seedling", "Vegetative", "Squaring", "Flowering", "Boll Development", "Harvest"],
    "Sugarcane": ["Germination", "Tillering", "Grand Growth", "Maturity", "Harvest"],
    "Banana":    ["Vegetative", "Flowering", "Fruit Development", "Harvest"],
    "Turmeric":  ["Sprouting", "Vegetative", "Rhizome Formation", "Maturity", "Harvest"],
    "Chilli":    ["Seedling", "Vegetative", "Flowering", "Fruiting", "Harvest"]
}

SOIL_TYPES = [
    "Red Soil", "Black Soil", "Alluvial Soil",
    "Laterite Soil", "Sandy Soil", "Clay Soil", "Loamy Soil", "Unknown"
]


# ──────────────────────────────────────────────────
# VALIDATION HELPERS
# ──────────────────────────────────────────────────

def ask(question, validator=None, default=None):
    """Input wrapper with validation."""
    prompt = f"{question}"
    if default:
        prompt += f" (default: {default})"
    prompt += ": "

    while True:
        answer = input(prompt).strip()
        if not answer and default:
            return default
        if not answer:
            print("  ⚠️  Please enter a value")
            continue
        if validator:
            valid, msg = validator(answer)
            if not valid:
                print(f"  ⚠️  {msg}")
                continue
        return answer


def validate_phone(val):
    """Indian phone number check."""
    digits = ''.join(filter(str.isdigit, val))
    if len(digits) == 10:
        return True, ""
    if len(digits) == 12 and digits.startswith('91'):
        return True, ""
    return False, "Valid 10-digit Indian phone needed"


def validate_date(val):
    """YYYY-MM-DD format check."""
    try:
        d = datetime.strptime(val, "%Y-%m-%d")
        if d > datetime.now():
            return False, "Enter a past or today's date. Future dates are not allowed."
        return True, ""
    except ValueError:
        return False, "Format YYYY-MM-DD (e.g. 2026-03-15)"


def pick_from_list(items, label):
    """Numbered list checked"""
    print(f"\n  {label}:")
    for i, item in enumerate(items, 1):
        print(f"    {i}. {item}")

    while True:
        try:
            choice = int(input(f"  Choice (1-{len(items)}): "))
            if 1 <= choice <= len(items):
                return items[choice - 1]
            print(f"  ⚠️  1-{len(items)} in this range")
        except ValueError:
            print("  ⚠️  Number needed")


# ──────────────────────────────────────────────────
# COLLECT PROFILE
# ──────────────────────────────────────────────────

def collect_profile(session_id=None):
    """
    Interactive farmer profile collection.
    Returns profile dict ready to save.
    """
    print("\n" + "="*50)
    print("  🌾 AGSKY Farmer Onboarding")
    print("="*50)
    print("  Welcome bro! need your farm details...")
    print("-"*50)

    # ── Basic Info ──
    print("\n📌 BASIC INFO")
    name  = ask("  👨‍🌾 Your Name")
    phone = ask("  📱 Phone number (10 digits)", validator=validate_phone)

    # ── Crop Info ──
    print("\n🌾 CROP INFO")
    crops = list(CROP_STAGES.keys())
    crop  = pick_from_list(crops, "What crop u had puted")

    plant_date = ask(
        "  📅 When Planted (YYYY-MM-DD)",
        validator=validate_date
    )

    stage = pick_from_list(CROP_STAGES[crop], f"{crop}-current stage")

    # ── Maintenance History ──
    print("\n💧 MAINTENANCE HISTORY")
    last_irrigation = ask(
        "  💦 Last irrigation date (YYYY-MM-DD, If skip press Enter)",
        default="never"
    )
    if last_irrigation != "never":
        valid, msg = validate_date(last_irrigation)
        if not valid:
            print(f"  ⚠️  Skipping: {msg}")
            last_irrigation = "never"

    last_pesticide = ask(
        "  🐛 Last pesticide date (YYYY-MM-DD, If skip press Enter)",
        default="never"
    )
    if last_pesticide != "never":
        valid, msg = validate_date(last_pesticide)
        if not valid:
            print(f"  ⚠️  Skipping: {msg}")
            last_pesticide = "never"

    last_fertilizer = ask(
        "  🌱 Last fertilizer date (YYYY-MM-DD, If skip press Enter)",
        default="never"
    )
    if last_fertilizer != "never":
        valid, msg = validate_date(last_fertilizer)
        if not valid:
            last_fertilizer = "never"

    # ── Soil Info ──
    print("\n🪨 SOIL INFO")
    soil = pick_from_list(SOIL_TYPES, "Soil type")

    # ── Optional Notes ──
    notes = input("\n  📝 Any extra notes? (Enter to skip): ").strip()

    # ── Build profile ──
    profile = {
        "name":             name,
        "phone":            phone,
        "crop":             crop,
        "plant_date":       plant_date,
        "current_stage":    stage,
        "last_irrigation":  last_irrigation,
        "last_pesticide":   last_pesticide,
        "last_fertilizer":  last_fertilizer,
        "soil_type":        soil,
        "notes":            notes or None,
        "session_id":       session_id,
        "created_at":       datetime.now(timezone.utc),
        "updated_at":       datetime.now(timezone.utc)
    }

    # ── Calculated fields ──
    try:
        plant_dt = datetime.strptime(plant_date, "%Y-%m-%d")
        days_since_planting = (datetime.now() - plant_dt).days
        profile["days_since_planting"] = days_since_planting
    except ValueError:
        profile["days_since_planting"] = None

    return profile


# ──────────────────────────────────────────────────
# SAVE / FETCH
# ──────────────────────────────────────────────────

def save_profile(profile):
    """Profile Will be saved in MongoDB"""
    db = get_db()
    if db is None:
        print("❌ DB connection fail")
        return None

    # Check if profile already exists for this phone
    existing = db['farmer_profiles'].find_one({"phone": profile['phone']})

    if existing:
        # Update existing
        profile['updated_at'] = datetime.now(timezone.utc)
        profile.pop('created_at', None)  # Don't overwrite created_at
        db['farmer_profiles'].update_one(
            {"phone": profile['phone']},
            {"$set": profile}
        )
        print(f"  ✅ Profile updated for {profile['name']}")
        return str(existing['_id'])
    else:
        # Insert new
        result = db['farmer_profiles'].insert_one(profile)
        print(f"  ✅ New profile created for {profile['name']}")
        return str(result.inserted_id)


def get_profile_by_phone(phone):
    """profile will be fetched from Phone."""
    db = get_db()
    if db is None:
        return None

    digits = ''.join(filter(str.isdigit, phone))[-10:]  # Last 10 digits
    return db['farmer_profiles'].find_one({
        "phone": {"$regex": digits + "$"}
    })


def get_profile_by_session(session_id):
    """From Session_id profile fetched."""
    from bson import ObjectId
    db = get_db()
    if db is None:
        return None

    try:
        return db['farmer_profiles'].find_one({
            "session_id": ObjectId(session_id)
        })
    except Exception:
        return db['farmer_profiles'].find_one({"session_id": session_id})


def list_all_farmers():
    """All registered farmers list will be returned."""
    db = get_db()
    if db is None:
        return []
    return list(db['farmer_profiles'].find(
        {},
        {"name": 1, "phone": 1, "crop": 1, "current_stage": 1,
         "days_since_planting": 1, "created_at": 1}
    ).sort("created_at", -1))


# ──────────────────────────────────────────────────
# DISPLAY
# ──────────────────────────────────────────────────

def print_profile_summary(profile):
    """Profile summary will be printed."""
    print("\n" + "="*50)
    print("  📋 FARMER PROFILE SUMMARY")
    print("="*50)
    print(f"  👨‍🌾 Name           : {profile['name']}")
    print(f"  📱 Phone          : {profile['phone']}")
    print(f"  🌾 Crop           : {profile['crop']}")
    print(f"  📅 Planted        : {profile['plant_date']}")
    if profile.get('days_since_planting') is not None:
        print(f"  ⏱️  Days since     : {profile['days_since_planting']} days")
    print(f"  🌱 Stage          : {profile['current_stage']}")
    print(f"  💧 Last Irrigation: {profile['last_irrigation']}")
    print(f"  🐛 Last Pesticide : {profile['last_pesticide']}")
    print(f"  🌱 Last Fertilizer: {profile['last_fertilizer']}")
    print(f"  🪨 Soil           : {profile['soil_type']}")
    if profile.get('notes'):
        print(f"  📝 Notes          : {profile['notes']}")
    print("="*50 + "\n")


# ──────────────────────────────────────────────────
# INTERACTIVE MENU
# ──────────────────────────────────────────────────

def main():
    """Interactive entry point."""
    print("\n" + "="*50)
    print("  🌾 AGSKY Farmer Profile Manager")
    print("="*50)
    print("  1. New farmer onboarding")
    print("  2. Update existing farmer (by phone)")
    print("  3. View farmer profile (by phone)")
    print("  4. List all farmers")
    print("  5. Exit")

    choice = input("\n  Choice (1-5): ").strip()

    if choice == "1":
        # Link to latest session if available
        session = get_latest_session()
        session_id = session['_id'] if session else None

        if session:
            print(f"\n  ℹ️  Linking to latest farm session "
                  f"({session['acres']} acres at "
                  f"{session['lat']:.4f}, {session['lon']:.4f})")

        profile = collect_profile(session_id)
        print_profile_summary(profile)

        confirm = input("  Save this profile? (y/n): ").strip().lower()
        if confirm == 'y':
            profile_id = save_profile(profile)
            if profile_id:
                print(f"\n  🎉 Profile saved! ID: {profile_id}")
                print("  📤 Next: daily_advisor.py will use this data")
        else:
            print("  ❌ Cancelled")

    elif choice == "2":
        phone = input("\n  📱 Farmer phone: ").strip()
        existing = get_profile_by_phone(phone)
        if not existing:
            print(f"  ❌ No farmer found with phone {phone}")
            return
        print_profile_summary(existing)
        print("  Re-enter details to update (existing values shown as default)")
        # Re-run collection (simplified update)
        profile = collect_profile(existing.get('session_id'))
        profile['phone'] = phone  # Keep same phone
        save_profile(profile)

    elif choice == "3":
        phone = input("\n  📱 Farmer phone: ").strip()
        profile = get_profile_by_phone(phone)
        if profile:
            print_profile_summary(profile)
        else:
            print(f"  ❌ No farmer found with phone {phone}")

    elif choice == "4":
        farmers = list_all_farmers()
        if not farmers:
            print("  ℹ️  No farmers registered yet")
            return
        print(f"\n  📋 {len(farmers)} Registered Farmers:")
        print("  " + "-"*60)
        for f in farmers:
            print(f"  {f['name']:<20} | {f['phone']:<12} | "
                  f"{f['crop']:<12} | {f.get('current_stage', 'N/A')}")

    elif choice == "5":
        print("  👋 Bye!")

    else:
        print("  ❌ Invalid choice")


if __name__ == "__main__":
    main()