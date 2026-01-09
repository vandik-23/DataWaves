# DataWaves 🌊  
**Webcam-based wave detection and wave-height estimation on Lake Thun (Switzerland), benchmarked against a physics-based spectral wave model.**

## Scientific context
This repository accompanies my master thesis and implements a **dual-pipeline monitoring concept** for inland wave dynamics:

1. **Computer Vision (CV) pipeline:** detect small wave features in panoramic webcam imagery and convert detections into **metric wave-height estimates** using an empirical **pixel-per-meter (PPM) calibration** derived from a field experiment.
2. **Spectral wave model pipeline:** generate a physically consistent reference wave climate using **MIKE 21 SW**, forced by terrain-aware wind fields produced with **WindNinja** and supported by bathymetry/mesh preparation.
3. **Comparative analysis:** evaluate agreement and systematic deviations between both approaches across different wind regimes.

A schematic overview of the research workflow is shown in this image: ![Alt](Research_Project_Structure.png):

---

## Data sources
### Webcam imagery
- **Beatus Wellness- & Spa-Hotel Webcam (2025)** — Roundshot Live Cam Gen 4 (Merligen):  
  https://beatuswellness.roundshot.com/

### Bathymetry (Lake Thun)
- **Bathymetrie Thunersee (2025)** — Amt für Geoinformation des Kantons Bern (AGI), Geoportal dataset:  
  https://www.agi.dij.be.ch/de/start/geoportal/geodaten/detail.html?type=geoproduct&code=BATHYTHU
- **Bathymetrie Thunersee (2025)** — swisstopo / opendata.swiss:  
  https://opendata.swiss/en/dataset/bathymetrie-thunersee

### Meteorological data
- **MeteoSwiss Automatic Weather Station Data (2025)** — Federal Office of Meteorology and Climatology MeteoSwiss  
  Stations used: Thun (THU), Interlaken (INT), Frutigen (FRU):  
  https://opendatadocs.meteoswiss.ch/a-data-groundbased/a2-automatic-precipitation-stations
- **Meteoblue Historical Weather Data (2025)** — Merligen station:  
  https://www.meteoblue.com/en/weather/archive/export

> Please respect the individual licensing/terms of use of each provider when reusing or redistributing data.

---

## Research structure ↔ repository structure
Below, the main repository folders are mapped directly to the corresponding steps in the research flowchart (Data Acquisition → Preprocessing → Model Setup → Processing → Evaluation).

### A) Computer Vision pipeline (webcam → wave heights)

**Data acquisition**
- [webscraper](web_scraper/)  
  Retrieval of panoramic webcam images (Merligen) and basic handling of image archives/metadata.
- `ppm_experiment/`  
  Field experiment inputs and processing for geometric calibration (SUP-based reference measurements).

**Data preprocessing**
- `ppm_experiment/`  
  GPS/geometry extraction and computation of the **PPM conversion rate** used to translate pixel distances into meters.
- `img_labeling/`  
  Dataset construction outputs supporting *stratified image sampling* and *label preparation* in YOLO format.

**Model setup**
- `waves_yolo_dataset_*/`  
  Training configurations and experiment artefacts for **YOLOv8 Nano & Small** fine-tuning.

**Processing**
- `results/`  
  Inference outputs and derived wave-height products (e.g., detection outputs used for wave-height calculation).

---

### B) Spectral wave model pipeline (wind + bathymetry → wave heights)

**Data acquisition**
- `wind_pipeline/`  
  Ingestion and preparation of wind station measurements (e.g., Thun / Interlaken / Frutigen).
- 'MIKE21/bathymetry/'  
  Where licensing or data permissions apply, large model input datasets may not be fully included; see the thesis for details.

**Data preprocessing**
- `wind_pipeline/`  
  Harmonization of wind observations and preparation for modelling workflows (including coordinate handling).
- `windninja/`  
  WindNinja automation/configuration and processing artefacts used for **terrain-informed wind downscaling** (wind forcing fields).

**Model setup & processing**
- `wind_pipeline/` and `results/`  
  MIKE 21 SW setup references, run outputs, and postprocessing products used in the evaluation.

---

### C) Comparative evaluation (CV vs spectral model)
- `results/`  
  Comparative metrics, figures, and summary artefacts combining:
  - webcam-derived wave heights (CV pipeline)
  - modelled wave characteristics (spectral pipeline)

---

## Notes on reproducibility
- Some components (e.g., **MIKE 21 SW**) are proprietary and may require a license.
- Paths and data locations may need adaptation depending on your environment and data availability.
