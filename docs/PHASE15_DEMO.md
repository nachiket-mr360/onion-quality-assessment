# Phase 15 — Final demo preparation (ONIONVISION)

Team **FANTASTIC6**. Product **ONIONVISION**. Problem **SIH26031**.

This is presentation readiness for the existing prototype. No retraining. No UI redesign. No fabricated results.

**Current prototype (frozen wording):**  
*AI-assisted visible onion quality assessment using RGB imagery.*

---

## Demo story (3–5 minutes)

```
PROBLEM     Subjective onion quality assessment
SOLUTION    AI-assisted visual inspection
INPUT       Mobile/IP Webcam or uploaded image
AI          Onion detection + visible defect class
DECISION    GOOD / BAD
EXPLAIN     Class + confidence + visible reason
MEASURE     Diameter when a physical reference is detected
BATCH       Counts, percentages, defect breakdown
DIGITAL     SQLite + HTML/JSON report
IMPACT      Potential impact simulation (assumptions only)
FUTURE      NIR / multispectral (not implemented)
```

---

## Primary live sequence (~4 minutes)

1. Open ONIONVISION (`http://127.0.0.1:8000/`).
2. Point to **ONIONVISION** and **FANTASTIC6** in the header.
3. Confirm status badge: system ready (`/health` model loaded).
4. **Mobile camera / IP Webcam** → enter address → **Test Connection** → **Connect**.
5. Show stream (1–2 clearly visible onions, even light, moderate distance).
6. **Capture image** (frozen frame — official count).
7. Show boxes, GOOD/BAD, batch summary.
8. Click one onion: class, confidence, reason.
9. **View details** (Decision Trace).
10. **Batch Analysis**: totals + defect breakdown.
11. **Reports**: open HTML, download HTML/JSON.
12. **Impact**: say the warning out loud — simulation only.
13. **Technology**: RGB now; NIR/multispectral planned, not built.

If the phone is slow, skip laptop webcam and go to **Upload image** (Backup A).

---

## Safe demo produce / stills

Prefer (Phase 14 observation):

| Use | Why |
|-----|-----|
| Clearly **healthy** onion | Strongest reliable class on TEST |
| Clearly **rotten** (external rot) | Strong ROTTEN behaviour |
| **1–2** onions, even light, mid distance, little occlusion | Fewer extra boxes |

Stills on this laptop:

| Role | Path |
|------|------|
| Healthy | `data/processed/yolo/images/test/onion_sample_007_v1.jpeg` |
| Rotten | `data/processed/yolo/images/test/onion_sample_r_005_v1.jpeg` |
| Optional damaged | `data/processed/yolo/images/test/onion_sample_d_005_v3.jpeg` |
| Optional sprouted | `data/processed/yolo/images/test/onion_sample_s_001_v1.jpeg` |
| UI examples (education, not live output) | `frontend/assets/ex_*.jpg` |

Do **not** headline damaged or sprouted as the live proof. The model can still be shown on those images if a judge asks; do not claim they are the safest cases.

---

## Backup (not a live camera result)

Label out loud: **BACKUP DEMO RESULT**.

**A — camera down:** **Upload image** → healthy `onion_sample_007_v1.jpeg`, then rotten `onion_sample_r_005_v1.jpeg` if time.

**B — assessment/UI glitch:** open verified files (stitched stills, **not** a phone freeze):

- `captures/reports/phase14_batch.html`
- `captures/reports/phase14_batch.json`
- `captures/reports/phase14_batch_frame.jpg`

Batch: total 2, GOOD 1, BAD 1, HEALTHY 1, ROTTEN 1. Do not describe this as a live IP Webcam capture.

---

## Demo assets (keep ready — do not copy the dataset)

- Weights: `runs/fresh_yolov8n_293_final/weights/best.pt`
- Backend: `backend/main.py` · Frontend: `frontend/`
- DB: `data/onion_quality.db`
- Healthy + rotten TEST stills above
- `captures/reports/phase14_batch.*`
- Browser, phone, IP Webcam, same Wi-Fi

---

## Environment

| Item | Notes |
|------|--------|
| Laptop | Windows, project at `C:\College\SIH` |
| Python | 3.12, `.venv` if present (`requirements.txt`) |
| App | FastAPI + Uvicorn, SQLite, static frontend |
| Model | `runs/fresh_yolov8n_293_final/weights/best.pt` |
| DB | `data/onion_quality.db` |
| Camera | IP Webcam on same Wi-Fi; address in UI (no Python edit) |
| Browser | Chrome/Edge → `http://127.0.0.1:8000/` |

Start:

```bat
cd C:\College\SIH
.venv\Scripts\activate
python -m uvicorn backend.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

If `.venv` is missing, use the Python 3.12 that has OpenCV + Ultralytics:

```bat
cd C:\College\SIH
C:\Users\nachi\AppData\Local\Programs\Python\Python312\python.exe -m uvicorn backend.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Then: open `http://127.0.0.1:8000/` → `/health` should be 200 with `model_loaded: true`.

---

## Camera if the phone IP changes (UI only)

1. Mobile camera / IP Webcam  
2. New IP (e.g. `192.168.x.x:8080`)  
3. Test Connection  
4. Connect  
5. Preview  
6. Capture  

If the phone fails → Backup A (upload).

---

## Pre-demo checklist (tick on the laptop; do not fake PASS)

```
[ ] FastAPI starts
[ ] GET /health = 200
[ ] model_loaded = true
[ ] model_path is .../fresh_yolov8n_293_final/weights/best.pt
[ ] http://127.0.0.1:8000/ opens ONIONVISION
[ ] Upload Image works
[ ] Assessment returns onions
[ ] Boxes display
[ ] Click onion → class / confidence / reason
[ ] Decision Trace
[ ] Batch statistics
[ ] Report opens
[ ] Report downloads
[ ] History lists batches
[ ] data/onion_quality.db exists
[ ] phase14_batch.html exists
[ ] Camera UI available (live connect = user)
```

---

## Claims (use only these)

| Topic | Say |
|-------|-----|
| What it is | AI-assisted visible onion quality assessment using RGB imagery |
| Classes | HEALTHY, DAMAGED, ROTTEN, SPROUTED |
| Mapping | HEALTHY→GOOD; DAMAGED/ROTTEN/SPROUTED→BAD |
| Size | Diameter measurement is available when a physical reference is detected |
| Limit | RGB imagery assesses visible surface characteristics and does not directly observe hidden/internal quality |
| Future | NIR/multispectral imaging is a planned extension for additional spectral information that could support assessment of hidden/internal quality indicators |

**Do not say:** 100% accurate, production-ready, eliminates human error, detects internal rot, reduces waste by X%, NIR is implemented.

Use: prototype, AI-assisted, visible defect assessment, potential to improve consistency.

Impact page already states: *Simulation only — values are user-defined assumptions, not measured field results.*

---

## Report fields (pipeline)

Inspection ID (`batch_id`), timestamp, total onions, GOOD, BAD, class breakdown, per-onion confidence/reason, `calibrated` / `size_status`, per-onion `diameter_mm` / `measurement_status`. No Grade A / URS values.

---

## Layout (unchanged)

`cv/` `backend/` `frontend/` `data/` `captures/` `runs/` `docs/`

Final model: `runs/fresh_yolov8n_293_final/weights/best.pt`

---

## Laptop packing list

Project folder, Python 3.12 + deps (`.venv` preferred), `best.pt`, `data/onion_quality.db`, TEST healthy/rotten JPEGs, `phase14_batch` reports, browser, phone + IP Webcam, Wi-Fi.

---

## Physical tests still on the user

IP Webcam connect, live freeze on real onions, lighting/distance, optional ArUco 4×4 id 0 @ 50 mm.
