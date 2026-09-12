# 🧅 ONIONVISION

## AI-Powered Onion Quality Assessment & Digital Inspection

> **From subjective visual inspection to evidence-based digital quality assessment.**

ONIONVISION is an AI-assisted computer vision system developed for **Smart India Hackathon 2026 — SIH26031**, addressing the problem of subjective and inconsistent onion quality assessment across procurement centres.

The system uses camera images to detect individual onions, identify visible quality conditions, estimate physical diameter when a calibration reference is available, convert observations into explainable **GOOD/BAD** decisions, aggregate results at batch level, and generate a structured digital inspection report.

---

## 🎯 Problem Statement

### SIH26031

**“Quality assessment and grading of onions are often subjective and vary across procurement centers, resulting in disputes and inconsistencies.”**

Traditional visual inspection can depend heavily on individual judgement. Differences in how inspectors interpret visible defects can lead to inconsistent decisions and make it difficult to maintain standardized digital evidence for an inspection.

ONIONVISION addresses this gap by introducing an **AI-assisted, explainable and traceable inspection workflow**.

---

# 💡 Our Solution

ONIONVISION transforms the inspection process from:

```text
Onion
   ↓
Manual Visual Judgement
   ↓
Quality Decision
   ↓
Manual Record
```

into:

```text
Onion Batch
   ↓
Camera / Image
   ↓
AI Onion Detection
   ↓
Visible Defect Classification
   ↓
Size Evidence
   ↓
GOOD / BAD / REVIEW_REQUIRED
   ↓
Batch Statistics
   ↓
Digital Quality Report
```

The goal is not to replace human inspectors.

> **ONIONVISION gives inspectors standardized visual evidence and structured digital records to support more consistent quality decisions.**

---

# 🚀 Key Features

### 🔍 AI-Based Onion Detection

Detects individual onions from an image or camera frame using a lightweight **YOLOv8n** object-detection model.

### 🧅 Four Visible Quality Classes

The current prototype recognizes:

| Class    | Meaning                    | Quality Decision |
| -------- | -------------------------- | ---------------- |
| HEALTHY  | No visible defect detected | GOOD             |
| DAMAGED  | Visible physical damage    | BAD              |
| ROTTEN   | Visible signs of rot/decay | BAD              |
| SPROUTED | Visible sprouting          | BAD              |

### ⚖️ Explainable Quality Decision

Each detected onion can provide:

* Class
* Confidence
* GOOD/BAD decision
* Visible reason
* Bounding-box coordinates
* Review state
* Size information when calibrated

This allows the system to provide more than a simple classification label.

### 🧠 Uncertainty-Aware Inspection

When model confidence is below the configured confidence threshold, the system can mark the result as:

**`REVIEW_REQUIRED`**

Instead of forcing an uncertain prediction into a final decision, the system keeps a human reviewer in the loop.

### 📏 Calibrated Size Estimation

ONIONVISION supports physical diameter estimation using a known **50 mm ArUco reference marker**.

```text
ArUco Reference
      ↓
Pixel-to-mm Calibration
      ↓
Onion Diameter Estimation
```

If a valid physical reference is not detected, the system does **not** invent a measurement and reports the size as unavailable.

### 📊 Batch-Level Quality Analysis

Individual onion observations are aggregated into:

* Total onions
* GOOD count
* BAD count
* GOOD percentage
* BAD percentage
* Defect-wise breakdown
* Individual onion results

This converts individual observations into useful batch-level information.

### 📄 Digital Inspection Reports

Each completed assessment can generate:

* HTML report
* JSON report
* Evidence frame

Reports contain batch information, quality statistics and onion-level inspection results.

### 🗃️ Persistent Inspection History

Inspection results are stored in **SQLite**, allowing completed batches to be retrieved later.

### 📱 Mobile / IP Webcam Support

A smartphone running an IP Webcam application can be used as the camera source.

The user can enter the current phone address through the interface instead of modifying source code whenever the phone's local IP changes.

### 🌐 Browser-Based Dashboard

The system provides a browser-based interface for:

* Inspection
* Results
* Batch analysis
* Inspection history
* Digital reports
* Camera connection
* Quality visualization

---

# 🧠 System Architecture

```text
                   ┌─────────────────────┐
                   │   Camera / Image     │
                   │      Input           │
                   └──────────┬──────────┘
                              │
                              ▼
                   ┌─────────────────────┐
                   │    OpenCV Frame     │
                   │     Processing      │
                   └──────────┬──────────┘
                              │
                              ▼
                   ┌─────────────────────┐
                   │     YOLOv8n         │
                   │ Onion Detection &   │
                   │ Classification      │
                   └──────────┬──────────┘
                              │
                              ▼
                   ┌─────────────────────┐
                   │   Quality Engine    │
                   │ GOOD / BAD / REVIEW │
                   └──────────┬──────────┘
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
          ┌─────────────────┐   ┌─────────────────┐
          │ Size Estimation │   │ Batch Analytics │
          │    + ArUco      │   │ Counts & %      │
          └────────┬────────┘   └────────┬────────┘
                   │                     │
                   └──────────┬──────────┘
                              ▼
                   ┌─────────────────────┐
                   │    FastAPI Backend  │
                   └──────────┬──────────┘
                              │
                  ┌───────────┴───────────┐
                  ▼                       ▼
          ┌───────────────┐       ┌───────────────┐
          │ SQLite        │       │ Digital       │
          │ Database      │       │ Reports       │
          └───────────────┘       └───────────────┘
                             
                              ▼
                   ┌─────────────────────┐
                   │ Browser Dashboard   │
                   └─────────────────────┘
```

---

# 🔬 AI Decision Logic

The current prototype uses four visual classes.

```text
HEALTHY
   ↓
GOOD
```

```text
DAMAGED ─┐
ROTTEN   ├──→ BAD
SPROUTED ┘
```

For uncertain predictions:

```text
Low Confidence
      ↓
REVIEW_REQUIRED
      ↓
Human Verification
```

### Classification Priority

When multiple defect conditions are relevant, the current quality logic follows:

```text
ROTTEN
   ↓
SPROUTED
   ↓
DAMAGED
   ↓
HEALTHY
```

---

# 📏 Size Measurement

ONIONVISION does not treat image pixels as physical measurements.

A known physical reference is required.

The prototype uses:

**ArUco Dictionary:** `DICT_4X4_50`
**Marker ID:** `0`
**Reference Size:** `50 mm`

The system uses the detected reference to estimate pixels-per-millimetre and then calculate onion diameter.

### Important

If the reference marker is not detected:

```text
diameter_mm = unavailable
measurement_status = reference_not_detected
```

No fabricated physical measurement is produced.

### Size and Quality Decision

The current MVP keeps size measurement separate from the GOOD/BAD classification.

The system does **not** claim that every onion below a particular diameter is automatically classified as BAD.

Official procurement thresholds can be incorporated as configurable grading rules in a future deployment after the applicable procurement specification is formally configured and validated.

---

# 📊 Dataset

The final prepared dataset used for the prototype contains:

### **293 paired images**

organized into:

### **92 physical onion groups**

The dataset was split using physical groups to prevent images of the same physical onion from appearing across training, validation and test sets.

| Split      |  Images | Physical Groups |
| ---------- | ------: | --------------: |
| TRAIN      |     205 |              66 |
| VALIDATION |      44 |              13 |
| TEST       |      44 |              13 |
| **TOTAL**  | **293** |          **92** |

### Class Distribution

#### Training

* HEALTHY: 86
* DAMAGED: 33
* ROTTEN: 48
* SPROUTED: 38

#### Validation

* HEALTHY: 19
* DAMAGED: 9
* ROTTEN: 8
* SPROUTED: 8

#### Test

* HEALTHY: 18
* DAMAGED: 3
* ROTTEN: 19
* SPROUTED: 4

The dataset is a prototype dataset and is not yet representative of all real-world procurement environments.

---

# 🤖 Model Training

### Model

**YOLOv8n**

### Training Configuration

* Pretrained model: Yes
* Maximum epochs: 40
* Image size: 416 × 416
* Batch size: 8
* Device: CPU
* Workers: 0
* AMP: Disabled
* Seed: 42
* Patience: 15
* Resume: No

The best model was produced during training before the maximum epoch limit because of early stopping.

### Model File

```text
runs/fresh_yolov8n_293_final/weights/best.pt
```

---

# 📈 Model Evaluation

## Validation Results

| Metric    |    Result |
| --------- | --------: |
| Precision |     0.669 |
| Recall    |     0.885 |
| mAP@50    | **0.896** |
| mAP@50–95 |     0.733 |

## Untouched Test Results

| Metric    | Result |
| --------- | -----: |
| Precision |  0.695 |
| Recall    |  0.562 |
| mAP@50    |  0.579 |
| mAP@50–95 |  0.484 |

The untouched test results are reported separately to provide a more realistic view of prototype performance.

### Interpretation

The prototype demonstrates a functioning end-to-end detection system, but the current model is **not production-grade**.

Further data collection and training are particularly important for:

* DAMAGED
* SPROUTED
* Different lighting conditions
* Different onion varieties
* Different orientations
* Occlusion and overlapping onions
* Real procurement environments

---

# 🧪 Prototype Validation

The system has been tested across multiple components of the pipeline.

### Computer Vision

* Onion detection
* Multi-onion images
* Visible defect classification
* Confidence handling
* Invalid/empty image handling

### Size Measurement

* ArUco reference detection
* Synthetic calibration validation
* Diameter calculation
* No-reference behaviour

### Quality Engine

* GOOD/BAD mapping
* Defect reason generation
* Confidence-based review state

### Backend

* `/health`
* `/assess`
* Batch persistence
* Batch retrieval
* Invalid upload handling

### Database

* Batch records
* Onion-level records
* Duplicate persistence protection
* Historical retrieval

### Reporting

* HTML report
* JSON report
* Evidence frame
* Batch statistics

### Camera

* IP Webcam address validation
* Camera reachability checking
* Frame capture workflow
* Camera-based assessment pipeline

---

# 🖥️ Technology Stack

| Layer           | Technology            |
| --------------- | --------------------- |
| AI Model        | YOLOv8n               |
| Deep Learning   | PyTorch               |
| Computer Vision | OpenCV                |
| Backend         | FastAPI               |
| Database        | SQLite                |
| Frontend        | HTML, CSS, JavaScript |
| Camera          | Phone / IP Webcam     |
| Data Processing | Python                |
| Reports         | HTML + JSON           |
| Calibration     | OpenCV ArUco          |

---

# 📁 Project Structure

```text
ONIONVISION/
│
├── backend/
│   ├── main.py
│   ├── database.py
│   ├── __init__.py
│   └── ...
│
├── cv/
│   ├── pipeline.py
│   ├── onion_infer.py
│   ├── grading.py
│   ├── size_measure.py
│   ├── report.py
│   ├── live_assess.py
│   ├── batch_assess.py
│   └── ...
│
├── frontend/
│   ├── index.html
│   ├── css/
│   │   └── app.css
│   ├── js/
│   │   ├── api.js
│   │   ├── app.js
│   │   └── viz.js
│   └── assets/
│
├── data/
│   ├── raw/
│   └── processed/
│       └── yolo/
│
├── captures/
│   └── reports/
│
├── runs/
│   └── ...
│
├── docs/
│   ├── PHASE14_REAL_WORLD_TESTING.md
│   └── PHASE15_DEMO.md
│
├── requirements.txt
├── README.md
├── START_DEMO.bat
├── yolov8n.pt
└── .gitignore
```

---

# ⚙️ Requirements

Recommended environment:

* Python **3.12**
* Windows / Linux
* CPU is sufficient for the prototype
* Webcam or smartphone/IP Webcam for camera testing

The project uses Python dependencies listed in:

```text
requirements.txt
```

---

# 🚀 Installation

## 1. Clone the repository

```bash
git clone https://github.com/nachiket-mr360/onion-quality-assessment.git
cd onion-quality-assessment
```

## 2. Create a virtual environment

### Windows

```powershell
python -m venv .venv
```

Activate it:

```powershell
.venv\Scripts\activate
```

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 3. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

---

# ▶️ Run ONIONVISION

Start the FastAPI application:

```powershell
python -m uvicorn backend.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000/
```

API documentation:

```text
http://127.0.0.1:8000/docs
```

Health check:

```text
http://127.0.0.1:8000/health
```

---

# 📱 Using a Phone as an IP Camera

ONIONVISION supports an IP Webcam workflow for mobile-camera testing.

### Basic workflow

1. Connect the phone and computer to the same local network.
2. Start an IP Webcam application on the phone.
3. Note the phone's local IP address and port.
4. Open the ONIONVISION dashboard.
5. Select the Mobile Camera / IP Webcam option.
6. Enter the address.
7. Test the connection.
8. Capture a frame.
9. Run the inspection.

The system normalizes the entered address into the expected video stream format.

You do not need to modify Python source code every time the phone's local IP address changes.

---

# 📄 Digital Reports

Completed inspections can generate reports containing:

* Batch ID
* Timestamp
* Total onions
* GOOD count
* BAD count
* GOOD percentage
* BAD percentage
* Defect breakdown
* Onion-level classifications
* Confidence values
* Quality decisions
* Reasons
* Review state
* Diameter when available
* Measurement status
* Bounding-box coordinates
* Evidence frame

Reports are generated as:

```text
HTML
JSON
Evidence Image
```

Reports are stored under:

```text
captures/reports/
```

---

# 🗃️ Database

ONIONVISION uses **SQLite** for local inspection persistence.

### `batches`

Stores:

* Batch ID
* Timestamp
* Total onions
* GOOD/BAD counts
* Percentages
* Calibration status
* Size status
* Report paths

### `onion_results`

Stores:

* Onion number
* Class
* Class ID
* Confidence
* Grade
* Reason
* Review state
* Diameter
* Measurement status
* Bounding-box coordinates

This creates a persistent connection between an individual onion result and its complete inspection batch.

---

# 🔌 API Endpoints

### Health

```http
GET /health
```

Returns backend and model status.

### Assess Image

```http
POST /assess
```

Uploads an image and performs the complete assessment pipeline.

### List Batches

```http
GET /batches
```

Returns stored inspection batches.

### Get Batch

```http
GET /batches/{batch_id}
```

Returns a stored batch and its onion-level results.

### Camera Test

```http
POST /camera/test
```

Checks whether a configured IP Webcam source is reachable and producing frames.

### Camera Snapshot

```http
GET /camera/snapshot
```

Retrieves a camera frame for the configured source.

### Camera Assessment

```http
POST /camera/assess
```

Captures and assesses a frame from the configured camera source.

---

# 🧭 Typical Inspection Workflow

```text
1. Open ONIONVISION
        ↓
2. Connect camera or upload image
        ↓
3. Capture inspection frame
        ↓
4. Detect individual onions
        ↓
5. Classify visible quality condition
        ↓
6. Estimate size if calibrated
        ↓
7. Generate GOOD / BAD / REVIEW_REQUIRED
        ↓
8. Aggregate batch statistics
        ↓
9. Store inspection in SQLite
        ↓
10. Generate digital report
```

---

# ⚠️ Current Limitations

ONIONVISION is a working prototype and has important limitations.

### Visible Surface Assessment

The current system uses RGB imagery and is designed for visible-surface quality assessment.

It does **not** reliably detect hidden or internal rot that cannot be observed in an RGB image.

### Model Performance

The current dataset is limited compared with the diversity of real procurement environments.

DAMAGED and SPROUTED conditions require additional representative data and validation.

### Lighting & Camera Conditions

Changes in:

* Lighting
* Distance
* Camera angle
* Onion orientation
* Occlusion
* Background
* Image quality

can affect detection performance.

### Size Measurement

Reliable physical diameter requires a detectable calibration reference.

Without the reference, the system reports the measurement as unavailable.

### Human Review

AI predictions are not treated as infallible.

Low-confidence cases can require human verification.

### Procurement Grading

The current MVP uses **GOOD/BAD** as its operational quality decision.

Formal procurement grades and thresholds should be configured against the applicable official procurement specification and validated before deployment.

---

# 🔮 Future Roadmap

## Phase 1 — Current MVP

**RGB camera + visible defect detection + GOOD/BAD + batch analytics + digital reporting**

## Phase 2 — Dataset Expansion

Build a larger multi-centre dataset covering:

* More onion varieties
* More lighting conditions
* More defect severity levels
* More orientations
* Different procurement environments
* More damaged and sprouted examples

## Phase 3 — Procurement Standardization

Introduce standardized capture conditions and configurable procurement rules for size and quality grading.

## Phase 4 — Multi-Centre Deployment

Enable inspection records and quality statistics to be collected across multiple procurement centres.

## Phase 5 — Advanced Sensing

Investigate **NIR/multispectral imaging** as a future extension for additional spectral information that may help assess quality characteristics not visible in ordinary RGB imagery.

> NIR/multispectral sensing is a future research direction and is not claimed as part of the current MVP.

---

# 🎯 Project Vision

ONIONVISION aims to move onion inspection from:

> **“What does the inspector think?”**

towards:

> **“What does the visual evidence show, what is the AI confidence, and what decision does the evidence support?”**

The long-term vision is a standardized digital inspection workflow where individual onion observations become **explainable, traceable and actionable batch-level quality information**.

---

# 🏆 Smart India Hackathon

**Problem Statement:** SIH26031
**Theme:** Smart Automation
**Category:** Software
**Team:** FANTASTIC6
**Project:** ONIONVISION

### Core Objective

> **Reduce subjectivity in onion quality assessment by combining computer vision, explainable AI decisions, physical size evidence and digital inspection records.**

---

# 👥 Team

## **FANTASTIC6**

**Project:** ONIONVISION
**SIH Problem Statement:** SIH26031

---

# 📌 Responsible AI & Project Scope

ONIONVISION is designed as an **AI-assisted inspection and decision-support system**.

It does not claim:

* 100% detection accuracy
* Complete automation of procurement decisions
* RGB-based internal rot detection
* Food-safety certification
* Already-validated NIR/multispectral detection
* Proven percentage reductions in food waste or disputes
* Production-scale deployment without further field validation

The prototype is intended to demonstrate a credible technical foundation that can be expanded through larger datasets, field validation, standardized procurement workflows and advanced sensing research.

---

# 📚 References

* Smart India Hackathon 2026 — Problem Statement SIH26031
* Department of Consumer Affairs — Price Stabilization Fund Operational Guidelines
* Ultralytics YOLO Documentation
* OpenCV Documentation
* PyTorch Documentation

---

# 📄 Project Status

### **Working Prototype — Demo Ready**

Implemented components include:

* AI onion detection
* Four-class visible quality classification
* GOOD/BAD quality engine
* Confidence-based review state
* ArUco-based size estimation
* FastAPI backend
* SQLite persistence
* Browser dashboard
* Batch history
* IP Webcam workflow
* Digital HTML/JSON reports
* Evidence frame generation
* End-to-end integration testing

Real-world field validation and broader dataset expansion remain future steps.

---

## License

This project was developed as a Smart India Hackathon prototype by **FANTASTIC6**.

Refer to the repository for the applicable project licensing and usage terms.
