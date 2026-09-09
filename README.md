# SIH26031 — Onion Quality Assessment & Grading

Working software prototype for Smart India Hackathon 2026 problem statement **SIH26031**.

This repository is in **Phase 2**: development environment and a camera → OpenCV → YOLO *infrastructure* proof.

It is **not** yet an onion quality grader.

---

## Current phase

| Phase | Status |
|-------|--------|
| 1 — Requirements freeze | Complete (`docs/PHASE1_REQUIREMENTS.md`) |
| 2 — Architecture & environment | In progress |
| 3+ — Dataset, onion model, quality engine, backend, UI | Not started |

---

## Locked MVP scope (from Phase 1)

Pipeline we are building toward:

```
PHONE CAMERA
→ LIVE VIDEO ON LAPTOP
→ ONION DETECTION
→ VISIBLE CONDITION (HEALTHY / DAMAGED / ROTTEN / SPROUTED)
→ SIZE ESTIMATE (ArUco preferred; ruler/coin fallback)
→ QUALITY ENGINE: GOOD / BAD
→ FROZEN-FRAME BATCH STATISTICS
→ DIGITAL REPORT
```

Locked rules:

- Visual AI classes: `HEALTHY`, `DAMAGED`, `ROTTEN`, `SPROUTED` only.
- `UNDERSIZED` is **not** an AI class. Size is displayed only and does **not** force `BAD` until an official threshold is approved.
- Final grade is strictly `GOOD` or `BAD`.
- `REVIEW REQUIRED` is an uncertainty / manual-review **state**, not a third grade.
- Multi-defect primary reason priority: `ROTTEN > SPROUTED > DAMAGED > HEALTHY`.
- Live prediction is allowed. **No tracking** in MVP.
- Official batch count comes from a **captured/frozen frame**.
- Camera setup: **fixed / top-down**, onions reasonably separated.
- RGB cannot detect hidden internal rot. Do not claim that it can.

---

## Phase 2 — what this folder is for

Phase 2 only proves that the laptop can:

1. Receive a camera stream (phone or local webcam).
2. Read frames with OpenCV.
3. Run a **standard pretrained YOLO** model on a frame.

The pretrained model is **COCO**, not an onion model. Detections such as `person`, `bottle`, or `apple` only mean “YOLO inference works”. They are not quality results.

Phase 2 does **not** include:

- React
- FastAPI
- database
- PDF reports
- tracking
- dashboard
- quality/grading engine
- onion dataset training

---

## Project layout (Phase 2)

```
.
├── README.md
├── requirements.txt
├── .gitignore
├── docs/
│   └── PHASE1_REQUIREMENTS.md
└── cv/
    ├── capture_utils.py
    ├── camera_preview.py
    └── yolo_proof.py
```

Weights download to `models/yolov8n.pt` on first YOLO run (gitignored).  
Test frames write to `captures/` (gitignored).

---

## Setup

Python **3.12** is the intended interpreter.

```bat
cd C:\College\SIH
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Activate when working interactively:

```bat
.venv\Scripts\activate
```

---

## Phone camera → laptop (simplest practical methods)

The phone does not need a custom app from this project. OpenCV only needs a camera index or a video URL.

### Method A — IP Webcam over Wi‑Fi (recommended first try on Android)

1. Install **IP Webcam** (or equivalent) on the phone.
2. Put phone and laptop on the **same Wi‑Fi**.
3. Start the server in the app and note the HTTP address, e.g. `http://192.168.0.12:8080`.
4. Use the video URL as `--source`:

```bat
.venv\Scripts\python.exe cv\camera_preview.py --source http://192.168.0.12:8080/video --preview
```

Keep the phone **fixed / top-down** for later MVP work. A hand-held angled phone is acceptable only for this connectivity test.

### Method B — Phone as a USB / virtual webcam

Apps such as **DroidCam** or **Iriun Webcam** make the phone appear as a normal Windows camera.

Then:

```bat
.venv\Scripts\python.exe cv\camera_preview.py --list
.venv\Scripts\python.exe cv\camera_preview.py --source 0 --preview
```

Use the index that actually opens.

### Method C — Laptop webcam (infrastructure fallback)

If the phone is not available yet, index `0` is enough to prove OpenCV capture and YOLO plumbing. It does **not** replace the phone-camera architecture for the final demo.

---

## Commands

Headless camera test (no window; writes one frame and exits):

```bat
.venv\Scripts\python.exe cv\camera_preview.py --source 0 --frames 20 --save captures\camera_test.jpg
```

Live window (press `q` to quit):

```bat
.venv\Scripts\python.exe cv\camera_preview.py --source 0 --preview
```

YOLO infrastructure proof on a saved frame:

```bat
.venv\Scripts\python.exe cv\yolo_proof.py --source captures\camera_test.jpg --save captures\yolo_test.jpg
```

YOLO on live camera (pretrained COCO, not onions):

```bat
.venv\Scripts\python.exe cv\yolo_proof.py --source 0 --frames 5 --save captures\yolo_camera.jpg
```

---

## Limitations (must remain visible)

- No onion-specific model exists yet.
- No dataset is in this repository yet.
- Size, grading, batch reports, backend, and UI are not implemented.
- Official undersize thresholds are not hard-coded.
- Hidden internal rot is out of scope for RGB.
- CPU inference may be slow; that is acceptable for this proof.

---

## Next phase (not started)

Phase 3 — dataset collection — starts only after Technical Lead approval of Phase 2.
