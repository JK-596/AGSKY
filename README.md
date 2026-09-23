
# 🌾 AGSKY: AI-Powered Satellite & Intelligent Pest Detection System

> **An AI-Driven Smart Agriculture Platform for Early Crop Stress Detection, Pest Identification & Intelligent Farming Recommendations**

---

## 🌍 Overview

Agriculture faces challenges such as unpredictable crop diseases, pest attacks, inefficient pesticide usage, and the lack of continuous field monitoring.

**AGSKY** is an AI-powered smart agriculture platform that combines **Satellite Remote Sensing, Artificial Intelligence, Weather Analysis, and Computer Vision** to help farmers detect potential crop stress, identify pests, and receive intelligent farming recommendations.

The system uses Sentinel-1 and Sentinel-2 satellite data to monitor agricultural fields, analyzes crop-related indicators, and provides localized field guidance through a nine-grid monitoring system.

When visible symptoms are detected, farmers can capture crop images, which are analyzed by an AI model to identify potential pests or diseases and provide verified agricultural treatment guidance.

---

## 🚀 Key Features

- 🛰️ **Satellite-Based Crop Monitoring:** Uses Sentinel-1 and Sentinel-2 data to analyze agricultural field conditions.
- 📊 **Vegetation Index Analysis:** Calculates NDVI, NDWI, EVI, and other selected indicators.
- 🧭 **Nine-Grid Field Mapping:** Divides the registered farm into nine logical monitoring grids per acre.
- 🌦️ **Preventive Risk Prediction:** Combines weather, crop, soil, and agricultural data to identify potential risks.
- 📸 **AI Pest & Disease Detection:** Analyzes farmer-uploaded crop images using AI.
- 🧪 **Intelligent Treatment Guidance:** Connects AI predictions with a verified agricultural knowledge base.
- 🗺️ **Compass-Based Guidance:** Helps farmers locate areas requiring field inspection.
- 🌱 **Scalable Architecture:** Supports future IoT sensor integration and advanced agricultural analytics.

---

## 🛠️ Technology Stack

| **Technology** | **Purpose** |
|---|---|
| **Python** | Backend development & data processing |
| **Flask** | REST API & server |
| **Google Earth Engine** | Satellite data processing |
| **Sentinel-1** | Radar-based field monitoring |
| **Sentinel-2** | Multispectral crop monitoring |
| **Gemini API** | AI-assisted image analysis & guidance |
| **MongoDB Atlas** | Database & farm information |
| **Leaflet.js** | Farm mapping & boundary selection |
| **HTML / CSS / JavaScript** | Frontend development |
| **NDVI / NDWI / EVI** | Vegetation & environmental analysis |

---

## 🛰️ Satellite Data & Vegetation Indices

AGSKY combines optical and radar satellite data for agricultural monitoring.

| **Data / Index** | **Application** |
|---|---|
| **Sentinel-2** | Multispectral crop monitoring |
| **Sentinel-1** | Radar-based field & surface analysis |
| **NDVI** | Vegetation greenness & crop condition |
| **NDWI** | Water-related vegetation monitoring |
| **EVI** | Enhanced vegetation monitoring |
| **Temporal Analysis** | Identifying changes over time |
| **Grid-Level Analysis** | Localized field monitoring |

### Important Sentinel-2 Bands

| **Band** | **Application** |
|---|---|
| **B2** | Blue — EVI |
| **B4** | Red — NDVI / EVI |
| **B8** | Near Infrared — NDVI |
| **B11** | SWIR — NDWI |

> Satellite indices indicate environmental and vegetation-related changes. They do not independently confirm a specific pest or disease.

---

## 🧩 Software Modules

### 1. 👨‍🌾 Farmer & Farm Registration

- Farmer account creation
- Crop and soil information
- Sowing date and crop growth stage
- Farm boundary selection using latitude and longitude
- Multiple plot and mixed-crop information

### 2. 🛰️ Satellite Processing Engine

- Sentinel-1 and Sentinel-2 integration
- Farm boundary-based image retrieval
- Satellite image preprocessing
- NDVI, NDWI, and EVI calculations
- Nine-grid spatial analysis

### 3. 🌦️ Preventive Risk Prediction

- Weather data integration
- Crop-specific risk analysis
- Soil and crop growth information
- Regional agricultural knowledge
- Potential risk alerts

### 4. 📸 AI Pest Detection

- Crop image upload
- AI-based image analysis
- Potential pest and disease identification
- Confidence and uncertainty reporting
- Symptom-based observations

### 5. 🧪 Agricultural Recommendation Engine

- Crop and pest knowledge base
- Verified treatment information
- Crop-specific guidance
- Safety and application instructions
- Expert verification for uncertain cases

### 6. 🧭 Field Guidance System

- Nine-grid field representation
- Affected area identification
- Compass-style UI
- Farmer inspection guidance
- Field feedback collection

---

## 🗺️ Nine-Grid Field Monitoring

The registered farm is divided into **9 logical grids per acre** for internal analysis.

```text
+----------------+----------------+----------------+
|  North-West    |     North      |  North-East    |
+----------------+----------------+----------------+
|     West       |     Center     |     East       |
+----------------+----------------+----------------+
|  South-West    |     South      |  South-East    |
+----------------+----------------+----------------+
```

- Satellite indicators are analyzed across grid areas.
- Potential stress areas are identified for inspection.
- The farmer receives simplified location-based guidance.
- The grid structure is used internally and does not require technical knowledge from the farmer.

---

## ⚙️ Prototype Workflow

1. Farmer registers and maps the agricultural land.
2. Application stores crop, soil, and cultivation information.
3. Backend retrieves Sentinel-1 and Sentinel-2 satellite data.
4. System calculates selected vegetation indices.
5. Farm is divided into nine logical grids.
6. Grid-level indicators are analyzed for unusual changes.
7. Weather and agricultural data support preventive risk analysis.
8. Farmer receives an alert and location guidance.
9. Farmer inspects the relevant field area.
10. If symptoms are visible, the farmer captures a crop image.
11. Image is uploaded to the backend for AI analysis.
12. AI predicts a supported pest or disease condition.
13. Agricultural knowledge base provides relevant treatment guidance.
14. Farmer receives the result and recommended next steps.



## 🧠 AI & Agricultural Analysis

| **Challenge** | **Proposed Strategy** |
|---|---|
| Crop stress monitoring | Satellite vegetation index analysis |
| Localized field monitoring | Nine-grid spatial analysis |
| Early risk identification | Weather + crop + agricultural data |
| Visible pest detection | AI-based crop image analysis |
| Treatment guidance | Verified agricultural knowledge base |
| Uncertain predictions | Confidence reporting & expert verification |
| Farmer accessibility | Simplified alerts & compass UI |

---

## 📅 Development Roadmap

| **Phase** | **Task** |
|---|---|
| **Phase 1** | Backend, database & farmer registration |
| **Phase 2** | Farm boundary mapping & nine-grid division |
| **Phase 3** | Google Earth Engine integration |
| **Phase 4** | NDVI, NDWI & EVI calculation |
| **Phase 5** | Weather-based risk analysis |
| **Phase 6** | AI crop image analysis |
| **Phase 7** | Treatment knowledge base integration |
| **Phase 8** | Testing, field validation & deployment |

---

## 🌱 Future Enhancements

- **IoT Integration:** Soil moisture, NPK, pH, and temperature sensors.
- **Tamil Voice Assistant:** Local-language agricultural guidance.
- **Advanced AI:** Crop-specific pest and disease models.
- **Time-Series Monitoring:** Continuous crop health tracking.
- **Smart Irrigation:** Weather and soil moisture-based recommendations.
- **Expert Verification:** Agricultural expert feedback and validation.
- **Offline Support:** Low-bandwidth and offline-assisted farmer workflows.

---

## 📊 Expected Impact

- 🌾 Early identification of potential crop stress.
- 🔍 Improved field inspection efficiency.
- 🤖 AI-assisted pest and disease identification.
- 🛰️ Satellite-powered agricultural monitoring.
- 🧪 More informed crop protection decisions.
- 💧 Potentially more efficient use of agricultural resources.
- 👨‍🌾 Farmer-friendly intelligent farming support.

> The system's accuracy and agricultural impact will be evaluated through testing and field validation.

---

## 🎯 Project Goals

- Build an integrated satellite-based agricultural monitoring platform.
- Combine satellite data with weather and crop information.
- Develop AI-powered pest and disease image analysis.
- Provide localized field guidance through grid-based monitoring.
- Connect predictions to a verified agricultural knowledge base.
- Support farmers with accessible, data-informed recommendations.



