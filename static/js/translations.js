/* ═══════════════════════════════════════════════════
   AGSKY — TRANSLATIONS (EN + TA only)
   ═══════════════════════════════════════════════════ */

window.AGSKY_TRANSLATIONS = {
  english: {
    // ── Common / topbar ──
    back: "Back",
    logout: "Logout",
    loading: "Loading...",
    save: "Save",
    cancel: "Cancel",
    submit: "Submit",

    // ── Auth ──
    auth_welcome: "Welcome to AGSKY",
    auth_tagline: "Your AI farming assistant",
    sign_in: "Sign In",
    sign_up: "Sign Up",
    name: "Name",
    phone: "Phone Number",
    password: "Password",
    land_type: "Land Type",
    nanjai: "Nanjai (Wetland)",
    punjai: "Punjai (Dryland)",
    crop: "Crop",
    select_crop: "Select your crop",
    days_planted: "Days since planting",
    days_placeholder: "e.g. 30",
    create_account: "Create Account",
    have_account: "Already have an account?",
    no_account: "Don't have an account?",
    phone_placeholder: "10 digit phone",
    name_placeholder: "Your full name",
    password_placeholder: "Choose a password",

    // ── Dashboard ──
    farm_grid: "Farm Grid",
    pest_ai: "Pest & Disease AI",
    dashboard_welcome: "Welcome",
    your_farm: "Your Farm",
    your_farm_grid: "Your Farm Grid",
    health_score: "Health Score",
    status: "Status",
    area: "Area",
    priority: "Needs Attention",
    tap_hint: "👆 Tap any cell to chat",
    btn_satellite: "Satellite",
    btn_roadmap: "Map",
    chat_placeholder: "Ask this cell anything...",
    suggestions: [
      "How are you feeling?",
      "What do you need?",
      "Any problems?",
      "What should I do?"
    ],
    legend: {
      healthy: "Healthy Crop",
      water_stress: "Water Stress",
      nutrient_stress: "Needs Nutrients",
      waterlogging: "Waterlogging",
      pest_disease: "Pest/Disease",
      low_vegetation: "Low Crop",
      unknown: "Unknown"
    },
    loading_steps: [
      "Fetching satellite data...",
      "Removing clouds...",
      "Calculating NDVI & NDWI...",
      "Detecting crop stress...",
      "Almost ready..."
    ],

    // ── Pest AI ──
    pest_tab_camera: "📷 Camera Scanner",
    pest_tab_grid: "🗺️ Grid Prediction",
    scanner_title: "Crop Disease Scanner",
    scanner_subtitle: "Take a photo of your crop leaf to detect diseases",
    take_photo: "📷 Take Photo",
    upload_gallery: "🖼️ Upload from Gallery",
    scanning: "Analyzing image...",
    disease_detected: "Disease Detected",
    confidence: "AI Confidence",
    chemical_remedy: "Chemical Remedy",
    natural_remedy: "Natural Remedy",
    find_shops: "🛒 Find Shops Nearby",
    scan_another: "Scan Another",
    grid_predict_title: "Grid-Based Pest Prediction",
    grid_predict_subtitle: "Select a cell from your farm to predict disease risk",
    predict_for_cell: "Predict for this cell",
    prediction_loading: "Predicting disease risk...",

    // ── Farming Stages ──
    stages: {
      "soil_prep":     "Preparation of Soil",
      "sowing":        "Sowing / Planting",
      "manuring":      "Manuring / Fertilizing",
      "irrigation":    "Irrigation",
      "weeding":       "Weeding",
      "protection":    "Crop Protection",
      "harvesting":    "Harvesting",
      "storage":       "Storage / Post-Harvest"
    }
  },

  tamil: {
    back: "பின்",
    logout: "வெளியேறு",
    loading: "Load ஆகுது...",
    save: "சேமி",
    cancel: "ரத்து",
    submit: "சமர்ப்பி",

    auth_welcome: "AGSKY-க்கு வரவேற்கிறோம்",
    auth_tagline: "உங்கள் AI விவசாய உதவியாளர்",
    sign_in: "உள்நுழை",
    sign_up: "பதிவு செய்",
    name: "பெயர்",
    phone: "தொலைபேசி எண்",
    password: "கடவுச்சொல்",
    land_type: "நிலத்தின் வகை",
    nanjai: "நஞ்சை (ஈரநிலம்)",
    punjai: "புஞ்சை (வறண்ட நிலம்)",
    crop: "பயிர்",
    select_crop: "உங்கள் பயிரை தேர்ந்தெடுக்கவும்",
    days_planted: "விதைத்து எத்தனை நாள் ஆச்சு?",
    days_placeholder: "உதா. 30",
    create_account: "கணக்கை உருவாக்கு",
    have_account: "கணக்கு இருக்கா?",
    no_account: "கணக்கு இல்லையா?",
    phone_placeholder: "10 இலக்க எண்",
    name_placeholder: "உங்கள் முழு பெயர்",
    password_placeholder: "கடவுச்சொல் தேர்ந்தெடு",

    farm_grid: "பண்ணை கிரிட்",
    pest_ai: "பூச்சி & நோய் AI",
    dashboard_welcome: "வணக்கம்",
    your_farm: "உங்கள் பண்ணை",
    your_farm_grid: "உங்கள் பண்ணை கிரிட்",
    health_score: "ஆரோக்கியம்",
    status: "நிலை",
    area: "பரப்பு",
    priority: "உடனடி கவனம்",
    tap_hint: "👆 எந்த cell-lum click பண்ணி பேசலாம்",
    btn_satellite: "செயற்கைக்கோள்",
    btn_roadmap: "வரைபடம்",
    chat_placeholder: "இந்த cell-a edhuvum kelunga...",
    suggestions: [
      "Eppadi iruka?",
      "Enna thevai?",
      "Edhavadhu problem?",
      "Naan enna panna?"
    ],
    legend: {
      healthy: "நல்ல பயிர்",
      water_stress: "தண்ணீர் தேவை",
      nutrient_stress: "சத்து பற்றாக்குறை",
      waterlogging: "அதிக நீர்",
      pest_disease: "பூச்சி/நோய்",
      low_vegetation: "குறைந்த பயிர்",
      unknown: "தெரியல"
    },
    loading_steps: [
      "செயற்கைக்கோள் data edukurom...",
      "Clouds ah remove panrom...",
      "NDVI, NDWI calculate panrom...",
      "Crop stress detect panrom...",
      "Konjam neram..."
    ],

    pest_tab_camera: "📷 கேமரா ஸ்கேனர்",
    pest_tab_grid: "🗺️ கிரிட் கணிப்பு",
    scanner_title: "பயிர் நோய் ஸ்கேனர்",
    scanner_subtitle: "உங்கள் பயிர் இலையை photo edunga — நோயை கண்டுபிடிப்போம்",
    take_photo: "📷 Photo எடு",
    upload_gallery: "🖼️ Gallery-la irunthu",
    scanning: "Image analyze panrom...",
    disease_detected: "நோய் கண்டறியப்பட்டது",
    confidence: "AI நம்பகத்தன்மை",
    chemical_remedy: "இரசாயன மருந்து",
    natural_remedy: "இயற்கை வழி",
    find_shops: "🛒 அருகில் கடை தேடு",
    scan_another: "மீண்டும் ஸ்கேன்",
    grid_predict_title: "கிரிட் அடிப்படையிலான பூச்சி கணிப்பு",
    grid_predict_subtitle: "உங்கள் பண்ணையில் ஒரு cell ஐ select பண்ணுங்க",
    predict_for_cell: "இந்த cell-ku predict பண்ணு",
    prediction_loading: "நோய் ஆபத்து கணிக்கிறோம்...",

    stages: {
      "soil_prep":     "உழவு / நிலம் தயார்",
      "sowing":        "விதைத்தல் / நடவு",
      "manuring":      "உரமிடுதல்",
      "irrigation":    "நீர் பாய்ச்சுதல்",
      "weeding":       "களை எடுத்தல்",
      "protection":    "பயிர் பாதுகாப்பு",
      "harvesting":    "அறுவடை",
      "storage":       "சேமிப்பு / விற்பனை"
    }
  }
};

/* ═══════════════════════════════════════════════════
   CROP DATA (EN + TA + Land type filter)
   ═══════════════════════════════════════════════════ */

window.AGSKY_CROPS = [
  { id: "paddy",       name_en: "Paddy",              name_ta: "நெல் (Nellu)",             land: ["nanjai"] },
  { id: "sugarcane",   name_en: "Sugarcane",          name_ta: "கரும்பு (Karumbu)",        land: ["nanjai"] },
  { id: "banana",      name_en: "Banana",             name_ta: "வாழை (Vaazhai)",           land: ["nanjai"] },
  { id: "groundnut",   name_en: "Groundnut",          name_ta: "நிலக்கடலை (Nilakkadalai)", land: ["punjai"] },
  { id: "cotton",      name_en: "Cotton",             name_ta: "பருத்தி (Paruthi)",        land: ["punjai"] },
  { id: "maize",       name_en: "Maize",              name_ta: "மக்காச்சோளம் (Makka Cholam)", land: ["punjai"] },
  { id: "coconut",     name_en: "Coconut",            name_ta: "தென்னை (Thennai)",         land: ["nanjai", "punjai"] },
  { id: "blackgram",   name_en: "Black Gram",         name_ta: "உளுந்து (Ulunthu)",        land: ["nanjai", "punjai"] },
  { id: "tapioca",     name_en: "Tapioca",            name_ta: "மரவள்ளி (Maravalli)",      land: ["punjai"] },
  { id: "millet",      name_en: "Sorghum/Millet",     name_ta: "சோளம்/கம்பு (Cholam/Kambu)", land: ["punjai"] }
];

/* ═══════════════════════════════════════════════════
   FARMING STAGES (used to calc based on days_planted)
   ═══════════════════════════════════════════════════ */

window.AGSKY_STAGES = [
  { id: "soil_prep",  min_days: -30, max_days: 0 },
  { id: "sowing",     min_days: 0,   max_days: 15 },
  { id: "manuring",   min_days: 15,  max_days: 30 },
  { id: "irrigation", min_days: 30,  max_days: 60 },
  { id: "weeding",    min_days: 60,  max_days: 75 },
  { id: "protection", min_days: 75,  max_days: 100 },
  { id: "harvesting", min_days: 100, max_days: 140 },
  { id: "storage",    min_days: 140, max_days: 9999 }
];

function getStageByDays(days) {
  for (const s of window.AGSKY_STAGES) {
    if (days >= s.min_days && days < s.max_days) return s.id;
  }
  return "unknown";
}