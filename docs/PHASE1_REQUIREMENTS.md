# SIH26031 — Onion Quality Assessment & Grading System

## Phase 1 Requirements & Specification Freeze

**Document status:** FROZEN pending Technical Lead review  
**Phase:** 1 of 14 — Requirements & official quality specification  
**Date:** 2026-09-09  
**Problem statement:** SIH26031 — Onion Quality Assessment and Grading  
**Authority:** Technical Lead corrections dated 2026-09-09 are binding. This document supersedes conflicting text in the original project brief for all locked decisions below.

This is a specification freeze only. It is not an implementation, architecture bootstrap, dataset, or application codebase.

---

## 1. Purpose

Build a genuinely working software prototype that assists onion quality assessment at procurement centres using a camera and computer vision.

The system must reduce subjectivity by producing:

- per-onion visible-condition observations
- GOOD / BAD decisions from explicit rules
- a primary defect reason when BAD
- approximate size estimates
- batch statistics
- a digital quality report

The prototype must not be a mockup or a fake AI demonstration.

---

## 2. Locked MVP objective

### 2.1 End-to-end pipeline

```
PHONE CAMERA
→ LIVE VIDEO STREAM TO LAPTOP
→ ONION DETECTION
→ VISIBLE CONDITION CLASSIFICATION
→ SIZE ESTIMATION (REFERENCE-BASED)
→ GOOD / BAD CLASSIFICATION (QUALITY ENGINE)
→ CAPTURED/FROZEN FRAME BATCH STATISTICS
→ DIGITAL QUALITY REPORT
```

### 2.2 Camera architecture (MVP)

- Phone provides the camera.
- Laptop performs AI processing, application logic, and display.
- No native mobile application.
- No phone-side display requirement.
- Live prediction is shown on the laptop.

### 2.3 First technical proof (before backend/frontend)

The first implementation proof, after this freeze is approved, must be:

```
camera → OpenCV capture → YOLO inference → on-screen detections
```

React, FastAPI, database, and dashboard work are **not** part of Phase 1 and must not start until later approved phases.

---

## 3. Locked decisions from Technical Lead review

These decisions are frozen.

| ID | Decision |
|----|----------|
| D1 | `UNDERSIZED` is **removed** from AI visual classes. |
| D2 | Final model visual classes are exactly: `HEALTHY`, `DAMAGED`, `ROTTEN`, `SPROUTED`. |
| D3 | Final quality grade is strictly `GOOD` or `BAD`. |
| D4 | `REVIEW REQUIRED` is an uncertainty / manual-review **state**, not a third grade. |
| D5 | When multiple visible defects apply, primary displayed reason uses priority: `ROTTEN > SPROUTED > DAMAGED > HEALTHY`. |
| D6 | Live camera prediction is in scope. Object tracking is **not** implemented in MVP. |
| D7 | Batch assessment uses a **captured / frozen frame** to avoid double-counting. |
| D8 | MVP capture setup is a **fixed / top-down** camera with reasonably separated onions. |
| D9 | Preferred size reference is an **ArUco marker**. Fallback: known-size ruler or coin. |
| D10 | Do **not** hard-code an undersized fail threshold until the applicable official standard is finalized. |
| D11 | Do **not** start React or backend in this phase. |
| D12 | Do not claim that ordinary RGB imagery can detect hidden internal rot. |

---

## 4. In-scope MVP capabilities

The first version must eventually do all of the following. Phase 1 only documents them; it does not implement them.

1. Live camera input on the laptop.
2. Detect individual onions.
3. Identify visible onion condition using the four locked visual classes.
4. Identify the primary visible defect type using the locked priority order.
5. Classify each onion as `GOOD` or `BAD`.
6. Identify the reason when an onion is `BAD`.
7. Estimate onion size using a practical reference-based method.
8. Count onions in a batch from a captured/frozen frame.
9. Calculate:
   - total onions
   - good count
   - bad count
   - good percentage
   - bad percentage
   - defect-category counts
10. Display results live on the laptop, with batch totals taken from the frozen assessment frame.
11. Produce a digital quality assessment report.

---

## 5. Explicitly out of MVP scope

Do not implement unless the Technical Lead later approves:

- Internal rot detection through RGB camera
- NIR hardware
- Multispectral hardware
- 3D computer vision
- Industrial conveyor automation
- Native mobile application
- Food-safety certification
- Automatic declaration that a defective onion is safe for consumption
- Processing / compost recommendations
- Complex cloud architecture
- Unnecessary microservices
- Unnecessary technologies
- Object tracking / unique-ID counting across frames
- React frontend (until later approved phase)
- Backend API / database (until later approved phase)
- Hard-coded official undersize fail threshold (until the applicable standard is finalized)
- Secondary recommendation features

---

## 6. Known limitation — internal defects

The prototype uses RGB camera imagery only.

It cannot reliably detect hidden internal rot or other internal defects that are not visible on the exterior.

This limitation must be stated in documentation and in the quality report. It must not be contradicted by UI copy, model claims, or demo narration.

Future NIR / multispectral sensing may be proposed later. It is not part of this MVP.

---

## 7. Official quality criteria policy

Grading rules must be based on applicable Government of India onion quality / procurement standards.

**Do not invent government thresholds.**

Relevant quality characteristics in the official domain include:

- size / diameter
- maturity
- firmness
- skin condition
- rot
- disease
- damage
- sprouting
- mould
- insect attack
- drying
- abnormal external moisture
- neck / stem condition

For this MVP:

- The application performs `GOOD` / `BAD` classification from **visible** observations plus explicit rules.
- It does **not** attempt to reproduce every government procurement rule.
- Numerical grading thresholds must not be hard-coded until the Technical Lead verifies the applicable current standard.

Until that verification:

- Size may be estimated and displayed.
- Size must **not** by itself force `BAD`.
- No `UNDERSIZED` model class exists.
- No undersize fail threshold exists in software.

---

## 8. Visual model classes

### 8.1 Locked detector / classifier classes

The computer vision model may output only these visual classes:

| Class ID | Class name | Meaning |
|----------|------------|---------|
| 0 | `HEALTHY` | No visible damage, rot, or sprouting |
| 1 | `DAMAGED` | Visible external damage, cuts, bruises, crushed tissue, or similar surface injury |
| 2 | `ROTTEN` | Visible rot, decay, mould, or similarly obvious spoilage |
| 3 | `SPROUTED` | Visible sprouting |

No other AI class may be added without Technical Lead approval.

### 8.2 Removed class

`UNDERSIZED` is **not** a visual model class.

Small physical size, if later used as a fail rule, is a quality-engine measurement rule, not a learned appearance class.

### 8.3 Multi-defect handling

An onion may show more than one visible defect. The model may still emit one primary class per onion.

The **primary displayed reason** is selected by this frozen priority:

```
ROTTEN > SPROUTED > DAMAGED > HEALTHY
```

Interpretation:

- If rot is present, primary reason = `ROTTEN`.
- Else if sprouting is present, primary reason = `SPROUTED`.
- Else if damage is present, primary reason = `DAMAGED`.
- Else primary reason = `HEALTHY`.

The quality engine uses that primary visual class, not a separate invented taxonomy.

---

## 9. Quality engine

### 9.1 Separation of concerns

| Stage | Responsibility |
|-------|----------------|
| Detection | Where is the onion? |
| Condition classification | What is the visible condition? |
| Measurement | What is the approximate size? |
| Quality engine | Is the onion `GOOD` or `BAD`, and why? |

The quality engine is separate from the model. Quality rules may change without retraining.

The model produces observations. The quality engine produces the operational decision.

### 9.2 Final grade

The only quality grades are:

- `GOOD`
- `BAD`

### 9.3 Initial mapping (frozen for MVP, pending official threshold work)

| Primary visual class | Quality grade | Reason if BAD |
|----------------------|---------------|----------------|
| `HEALTHY` | `GOOD` | — |
| `DAMAGED` | `BAD` | Damaged |
| `ROTTEN` | `BAD` | Rotten |
| `SPROUTED` | `BAD` | Sprouted |

Size is **not** included in this mapping until an official diameter cutoff is provided.

### 9.4 Worked example

```
AI observation:
  visual_class = ROTTEN
  confidence   = 0.94
  size_cm      = 6.2   # displayed only; not a fail rule yet

Quality engine:
  grade  = BAD
  reason = Rotten
```

---

## 10. Confidence and REVIEW REQUIRED

Predictions must expose confidence.

| Confidence situation | Behaviour |
|----------------------|-----------|
| High confidence | Quality engine applies the `GOOD` / `BAD` mapping automatically |
| Low confidence | Onion is flagged `REVIEW REQUIRED` for manual review |

Rules:

- `REVIEW REQUIRED` is **not** a grade.
- It does not replace `GOOD` or `BAD` as a quality class.
- Uncertain onions must not be silently forced into a definitive displayed result in a way that hides uncertainty.
- The numeric confidence cutoff is **not frozen** in Phase 1. It will be set after validation evidence exists.
- Until that cutoff is set, confidence must still be computed and displayed.

Manual correction UI may be added later only if time permits and the Technical Lead approves.

---

## 11. Capture and counting protocol

### 11.1 Frozen assessment method

Batch assessment is performed on a **single captured / frozen frame**.

Rationale: live streams without tracking will double-count onions as boxes appear, disappear, or flicker.

### 11.2 Live view vs assessment frame

| Mode | Allowed in MVP | Counting |
|------|----------------|----------|
| Live camera preview with detections | Yes | Do **not** use as the official batch count |
| Captured / frozen assessment frame | Yes | Official batch count and statistics |
| Multi-frame tracking / unique IDs | No | Out of MVP scope |

### 11.3 Physical setup

Required for MVP:

- Camera fixed, approximately top-down
- Onions reasonably separated (minimize overlap)
- Entire batch intended for assessment visible in the frozen frame
- Size reference visible in the same frame
- Controlled, reasonably stable lighting where possible

Not required for MVP:

- Moving conveyor
- Hand-held unconstrained phone motion during assessment
- Stacked or heavily overlapping onions

### 11.4 Counting rule

```
total_onions = number of onion detections in the frozen assessment frame
```

Do not count unique onions across time. Do not implement ByteTrack, SORT, or similar.

---

## 12. Size estimation

### 12.1 Method

Reference-based 2D measurement only. No 3D reconstruction.

Concept:

```
known physical dimension of reference
→ measured pixels of reference
→ pixels-per-centimetre (or mm) scale
→ onion dimension estimate from bounding box or contour
```

A visual measurement overlay (line / dotted line with estimated cm) may be shown.

### 12.2 Reference object

Preference order:

1. **ArUco marker** of known printed size (preferred)
2. Known-size ruler
3. Known-size coin

The exact marker ID, printed side length, ruler length, or coin denomination will be recorded when the physical reference is chosen. That choice is operational, not an architecture change.

### 12.3 Geometric assumptions

MVP assumes:

- approximately top-down camera
- reference and onions roughly in the same plane
- limited perspective distortion

If the camera is tilted, size estimates become unreliable. That is a known limitation.

### 12.4 Undersize rule

- Size is estimated and may be displayed.
- Size is recorded in batch outputs when available.
- Size must **not** currently force `BAD`.
- No undersize threshold constant may be hard-coded until the Technical Lead finalizes the applicable official standard.

---

## 13. Batch analytics

Computed from the frozen assessment frame.

Example:

```
Total     = 20
Healthy   = 15
Damaged   = 2
Rotten    = 1
Sprouted  = 1

Good      = 15
Bad       = 5
Good %    = 75%
Bad %     = 25%
```

Required calculated fields:

- total onions
- good count
- bad count
- good percentage
- bad percentage
- defect-category counts: `HEALTHY`, `DAMAGED`, `ROTTEN`, `SPROUTED`

There is no `UNDERSIZED` defect-category count from the model.

Onions flagged `REVIEW REQUIRED` must be visible in the UI/report as an uncertainty count. They are not a quality grade. How they affect good/bad totals will be specified when the confidence cutoff is set. Until then, they must not be hidden.

---

## 14. Digital quality report (future content; not implemented in Phase 1)

The report should eventually contain:

- Batch ID
- Date / time
- Total onions
- Good count
- Bad count
- Good percentage
- Bad percentage
- Defect-category counts (`HEALTHY`, `DAMAGED`, `ROTTEN`, `SPROUTED`)
- Size information where available
- Model confidence information
- `REVIEW REQUIRED` count / notes where applicable
- Overall assessment
- Limitations / notes, including:
  - RGB cannot detect hidden internal rot
  - size is approximate
  - no official undersize fail rule is applied until the standard is finalized
  - counts come from one frozen frame, not tracked unique IDs

---

## 15. Dataset principles (requirements only)

Primary data must come from real onions photographed by the team.

Collect examples of:

- healthy
- damaged
- rotten
- sprouted

Also collect difficult cases:

- subtle damage
- partial rot
- early sprouting
- different orientations
- different sizes
- different lighting
- different onion varieties
- dirty onions
- partially overlapping onions (for robustness; MVP inference still prefers separated onions)
- different backgrounds

Do **not** collect or label an `UNDERSIZED` visual class.

Public datasets may supplement team photos only after license/usage conditions are checked.

Final validation must include real onions not seen during training.

Dataset collection itself is Phase 3. This section only freezes the labelling contract.

---

## 16. Model evaluation requirements (later phases)

Do not report accuracy alone.

Evaluate:

- Precision
- Recall
- mAP where appropriate
- Confusion matrix
- Per-class performance for `HEALTHY`, `DAMAGED`, `ROTTEN`, `SPROUTED`
- False positives
- False negatives

Most important: test on unseen real onions / batches.

Do not claim accuracy that has not been measured.

---

## 17. Technology stack (approved; not installed in Phase 1)

| Area | Approved technology |
|------|---------------------|
| Language | Python |
| Camera / image I/O | OpenCV |
| Detection / visual classification | YOLO (Ultralytics YOLOv8 or YOLO11, to be confirmed in Phase 5) |
| Deep learning runtime | PyTorch (via Ultralytics as needed) |
| Numerics | NumPy, Pandas |
| Annotation | Roboflow or CVAT |
| Backend (later phase) | FastAPI |
| Database (later phase) | SQLite |
| Frontend (later phase) | React, only after the CV pipeline is proven |
| Charts (later phase) | Plotly or Chart.js |
| Reports (later phase) | Python PDF generation |

Phase 1 installs none of these.

Unauthorized without prior approval:

- replacing YOLO
- replacing FastAPI
- Docker
- PostgreSQL
- cloud services
- authentication systems
- extra AI classes
- tracking libraries as a counting solution
- Streamlit as a stack substitute

---

## 18. Development phases

Do not skip ahead without Technical Lead approval.

| Phase | Name | This document |
|-------|------|----------------|
| 1 | Requirements & official quality specification | **Current — freeze only** |
| 2 | System architecture & development environment | Not started |
| 3 | Dataset collection | Not started |
| 4 | Annotation & dataset preparation | Not started |
| 5 | Computer vision model development | Not started |
| 6 | Size estimation & feature extraction | Not started |
| 7 | Quality assessment engine | Not started |
| 8 | Real-time camera pipeline | Not started |
| 9 | Backend & API | Not started |
| 10 | Database | Not started |
| 11 | Frontend / dashboard | Not started |
| 12 | Integration | Not started |
| 13 | Testing & validation | Not started |
| 14 | Deployment / demo preparation | Not started |

After Phase 1 approval, the next proposed phase is Phase 2: system architecture and development environment.

The first runtime proof in later phases remains:

```
camera → OpenCV → YOLO inference
```

before React or backend work.

---

## 19. Success condition (updated to frozen decisions)

The project is successful when we can demonstrate:

1. Phone camera provides live video.
2. Laptop receives the video.
3. AI detects onions.
4. AI identifies visible condition as one of `HEALTHY`, `DAMAGED`, `ROTTEN`, `SPROUTED`.
5. Quality engine determines `GOOD` or `BAD`.
6. System explains `BAD` using the locked priority reason.
7. System estimates size using ArUco (preferred) or known ruler/coin.
8. System counts onions from a captured/frozen frame.
9. System calculates batch statistics.
10. Laptop display shows live detections and frozen-frame assessment results.
11. A digital report can be generated.
12. The complete pipeline works on a new real batch.
13. Uncertain predictions can be marked `REVIEW REQUIRED` without treating that mark as a grade.
14. No internal-rot capability is claimed.

---

## 20. Open items — not frozen

These require later Technical Lead or team input. They must not be silently decided in code.

| ID | Open item |
|----|-----------|
| O1 | Exact applicable GoI standard document and numeric size / defect thresholds |
| O2 | Numeric confidence cutoff for `REVIEW REQUIRED` |
| O3 | How `REVIEW REQUIRED` onions are included or excluded from good/bad percentages once the cutoff exists |
| O4 | Exact ArUco dictionary, marker ID, and printed size — or fallback coin/ruler millimetre value |
| O5 | Phone-to-laptop transport: USB webcam mode vs IP webcam / equivalent |
| O6 | YOLO version pin (YOLOv8 vs YOLO11) at Phase 5 |
| O7 | Team role assignment confirmation |
| O8 | Physical onion availability and per-class photo counts |
| O9 | Public dataset names and licenses, if any are used |
| O10 | Batch ID generation scheme |
| O11 | Whether later phases allow a secondary recommendation feature |

---

## 21. Constraints for all later implementation

- Prioritize working functionality over unnecessary complexity.
- Use the simplest reliable architecture.
- Do not introduce technologies because they sound impressive.
- Do not build UI before the core AI pipeline is validated.
- Do not create fake functionality.
- Do not claim unmeasured accuracy.
- Test every major component before continuing.
- After every meaningful development step, stop and report.
- Do not proceed to the next phase without Technical Lead approval.
- If a component fails, report the error, fix it, retest, and do not build unrelated features on top of it.

---

## 22. Phase 1 deliverable statement

Phase 1 is complete when this specification freeze exists and the Technical Lead accepts it.

Phase 1 does **not** include:

- repository scaffolding beyond this document
- `requirements.txt` / environment setup
- model weights
- camera code
- backend
- frontend
- dataset folders populated with images

Those belong to later phases.

---

## 23. Proposed next step (not started)

After Technical Lead approval of this freeze:

**Phase 2 — System architecture & development environment**

Proposed Phase 2 contents, subject to approval:

- minimal project skeleton
- `.gitignore`
- `README.md` stating scope and limitations
- `requirements.txt` with only packages needed for the first camera → OpenCV → YOLO proof
- no React
- no FastAPI
- no database
- no tracking

No Phase 2 work will start until this Phase 1 document is reviewed and approved.
