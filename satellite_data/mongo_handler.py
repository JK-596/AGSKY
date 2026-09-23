"""
mongo_handler.py
----------------
Saves crop stress analysis results in MongoDB Atlas.
The stored data is later retrieved and passed to Gemini AI for generating the advisory report.


Collections:
    farm_sessions  → Each analysis run (lat, lon, acres, timestamp)
    cell_data      → 9 cells NDVI/NDWI/EVI values
    stress_reports → Crop stress results per session

Test:
    python mongo_handler.py
"""

import sys
import os
from datetime import datetime, timezone

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from config import MONGO_URI, MONGO_DB_NAME

try:
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
except ImportError:
    print("❌ pymongo not installed!")
    print("   Run: pip install pymongo")
    sys.exit(1)


# ──────────────────────────────────────────────────
# CONNECTION
# ──────────────────────────────────────────────────

def get_db():
    """MongoDB connection return pannum."""
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        db = client[MONGO_DB_NAME]
        return db
    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        print(f"❌ MongoDB connection failed: {e}")
        print("check the config.py for MONGO_URI ")
        return None


# ──────────────────────────────────────────────────
# SAVE FUNCTIONS
# ──────────────────────────────────────────────────

def save_analysis(crop_stress_result, user_id=None):
    """
    crop_stress.py output → saved in MongoDB.
    user_id (optional) — link session to user.
    Returns: session_id (for fetching later)
    """
    db = get_db()
    if db is None:
        return None

    meta  = crop_stress_result['grid_result']['meta']
    grid  = crop_stress_result['grid_result']['grid']

    # ── Session document ──
    session = {
        "user_id":      user_id,  # Link to users collection
        "timestamp":    datetime.now(timezone.utc),
        "lat":          meta['lat'],
        "lon":          meta['lon'],
        "acres":        meta['acres'],
        "health_score": crop_stress_result['grid_result']['summary']['health_score'],
        "farm_status":  crop_stress_result['farm_status']['status'],
        "farm_message": crop_stress_result['farm_status']['message'],
        "priority_cell": crop_stress_result['priority_cell'][0],
        "priority_stress": crop_stress_result['priority_cell'][1]['stress_type']
    }

    session_id = db['farm_sessions'].insert_one(session).inserted_id
    print(f"  ✅ Session saved → ID: {session_id} (user: {user_id})")

    # ── Cell data documents ──
    cell_docs = []
    for label, cell in grid.items():
        stress = crop_stress_result['cell_stress'].get(label, {})
        cell_docs.append({
            "session_id":  session_id,
            "user_id":     user_id,
            "label":       label,
            "ndvi":        cell.get('ndvi'),
            "ndwi":        cell.get('ndwi'),
            "evi":         cell.get('evi'),
            "ndvi_status": cell.get('ndvi_status'),
            "ndwi_status": cell.get('ndwi_status'),
            "stress_type": stress.get('stress_type'),
            "severity":    stress.get('severity'),
            "actions":     stress.get('actions', []),
            # Store bounds for cached dashboard rendering
            "bounds":      cell.get('bounds'),
            "timestamp":   datetime.now(timezone.utc)
        })

    db['cell_data'].insert_many(cell_docs)
    print(f"  ✅ {len(cell_docs)} cells saved")

    # ── Stress summary document ──
    stress_doc = {
        "session_id":    session_id,
        "user_id":       user_id,
        "stress_summary": crop_stress_result['stress_summary'],
        "zones":          crop_stress_result['grid_result']['zones'],
        "water_zones":    crop_stress_result['grid_result']['water_zones'],
        "timestamp":      datetime.now(timezone.utc)
    }

    db['stress_reports'].insert_one(stress_doc)
    print(f"  ✅ Stress report saved")

    # Also update user's profile with farm link
    if user_id:
        from bson import ObjectId
        try:
            db['users'].update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {
                    "last_session_id": session_id,
                    "last_lat":        meta['lat'],
                    "last_lon":        meta['lon'],
                    "last_acres":      meta['acres'],
                    "last_analyzed":   datetime.now(timezone.utc)
                }}
            )
            print(f"  ✅ User profile updated with latest session")
        except Exception as e:
            print(f"  ⚠️  User profile update failed: {e}")

    return str(session_id)


# ──────────────────────────────────────────────────
# FETCH FUNCTIONS
# ──────────────────────────────────────────────────

def get_latest_session():
    """Most recent analysis fetch pannum."""
    db = get_db()
    if db is None:
        return None

    session = db['farm_sessions'].find_one(sort=[("timestamp", -1)])
    return session


def get_user_cached_dashboard(user_id):
    """
    User-oda latest saved session + cells + stress data.
    In Dashboard cached will be showed.
    Returns: full dashboard-ready dict OR None if no cached data.
    """
    from bson import ObjectId
    from datetime import datetime, timezone
    db = get_db()
    if db is None:
        return None

    try:
        # Find user's latest session
        session = db['farm_sessions'].find_one(
            {"user_id": user_id},
            sort=[("timestamp", -1)]
        )
        if not session:
            return None

        session_id = session['_id']

        # Fetch all cells for that session
        cells = list(db['cell_data'].find({"session_id": session_id}))
        if not cells:
            return None

        # Fetch stress report
        stress_report = db['stress_reports'].find_one({"session_id": session_id})

        # Build grid dict (label → cell data)
        grid = {}
        cell_stress = {}
        for c in cells:
            label = c.get('label')
            grid[label] = {
                "ndvi":        c.get('ndvi'),
                "ndwi":        c.get('ndwi'),
                "evi":         c.get('evi'),
                "ndvi_status": c.get('ndvi_status'),
                "ndwi_status": c.get('ndwi_status'),
                "bounds":      c.get('bounds')
            }
            cell_stress[label] = {
                "stress_type": c.get('stress_type', 'unknown'),
                "severity":    c.get('severity', 'unknown'),
                "actions":     c.get('actions', [])
            }

        # Calculate grid bounds
        import math
        from grid_maker import calculate_grid
        start_lat, start_lon, sub_lat, sub_lon = calculate_grid(
            session['lat'], session['lon'], session['acres']
        )

        # Calculate time since analysis
        ts = session.get('timestamp')
        if ts and hasattr(ts, 'replace'):
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            time_diff = (datetime.now(timezone.utc) - ts).total_seconds()
            if time_diff < 3600:
                time_ago = f"{int(time_diff/60)} min ago"
            elif time_diff < 86400:
                time_ago = f"{int(time_diff/3600)} hours ago"
            else:
                time_ago = f"{int(time_diff/86400)} days ago"
        else:
            time_ago = "recently"

        return {
            "session_id":   str(session_id),
            "user_id":      user_id,
            "lat":          session['lat'],
            "lon":          session['lon'],
            "acres":        session['acres'],
            "health_score": session.get('health_score', 50),
            "farm_status": {
                "status":  session.get('farm_status', 'MODERATE'),
                "message": session.get('farm_message', '')
            },
            "grid":         grid,
            "grid_bounds": {
                "south": start_lat, "north": start_lat + 3 * sub_lat,
                "west":  start_lon, "east":  start_lon + 3 * sub_lon,
            },
            "cell_stress":  cell_stress,
            "zones":        stress_report.get('zones', {}) if stress_report else {},
            "water_zones":  stress_report.get('water_zones', {}) if stress_report else {},
            "priority_cell": {
                "label":  session.get('priority_cell', 'CENTER'),
                "stress": session.get('priority_stress', 'unknown')
            },
            "last_analyzed": time_ago,
            "cached":        True
        }

    except Exception as e:
        print(f"  ❌ Cached fetch failed: {e}")
        return None


def get_session_cells(session_id):
    """Specific session-oda 9 cells data will be fetched."""
    from bson import ObjectId
    db = get_db()
    if db is None:
        return None

    cells = list(db['cell_data'].find({"session_id": ObjectId(session_id)}))
    return cells


def get_all_sessions():
    """All past analysis sessions list."""
    db = get_db()
    if db is None:
        return []

    sessions = list(db['farm_sessions'].find(
        {}, {"lat": 1, "lon": 1, "acres": 1,
             "health_score": 1, "farm_status": 1, "timestamp": 1}
    ).sort("timestamp", -1).limit(20))
    return sessions


# ──────────────────────────────────────────────────
# STANDALONE TEST
# ──────────────────────────────────────────────────

if __name__ == "__main__":
    print("Starting mongo_handler.py test...")
    print("="*45)

    # Step 1: Connection test
    print("\n  🔌 Testing MongoDB connection...")
    db = get_db()
    if db is None:
        print("❌ Connection failed — config.py check the password")
        sys.exit(1)
    print("  ✅ MongoDB connected!")

    # Step 2: Dummy data save test
    print("\n  💾 Testing save with dummy data...")
    dummy_result = {
        "cell_stress": {
            label: {
                "stress_type": "water_stress",
                "severity": "moderate",
                "actions": ["Test action"]
            } for label in ["SW","S","SE","W","CENTER","E","NW","N","NE"]
        },
        "stress_summary": {"water_stress": ["SW","S","SE"]},
        "farm_status": {"status": "MODERATE", "message": "Test run"},
        "priority_cell": ("SE", {"stress_type": "water_stress", "severity": "moderate"}),
        "grid_result": {
            "meta": {"lat": 11.0168, "lon": 76.9558, "acres": 5.0},
            "summary": {"health_score": 23.2, "avg_ndvi": 0.139, "avg_ndwi": -0.21},
            "grid": {
                label: {
                    "ndvi": 0.15, "ndwi": -0.20, "evi": 0.10,
                    "ndvi_status": "🔴 Poor", "ndwi_status": "🟡 Mild stress"
                } for label in ["SW","S","SE","W","CENTER","E","NW","N","NE"]
            },
            "zones":       {"critical": ["W","NW"], "stressed": ["SE"], "healthy": [], "excellent": []},
            "water_zones": {"drought": ["SE"], "dry": ["SW","S"], "moist": [], "saturated": []}
        }
    }

    session_id = save_analysis(dummy_result)

    if session_id:
        print(f"\n  🔍 Fetching saved session: {session_id}")
        session = get_latest_session()
        if session:
            print(f"  ✅ Fetched → Status: {session['farm_status']}, "
                  f"Health: {session['health_score']}/100")

        print("\n  📋 All sessions:")
        all_s = get_all_sessions()
        for s in all_s[:3]:
            ts = s['timestamp'].strftime('%Y-%m-%d %H:%M')
            print(f"     {ts} | {s['farm_status']:8} | {s['health_score']}/100")

        print("\n✅ mongo_handler.py test passed!")
        print("   Next: Run weather_api.py")
    else:
        print("❌ Save failed")