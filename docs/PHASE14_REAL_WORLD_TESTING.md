# Phase 14 — Real-world testing preparation + non-physical validation

**Date:** 2026-09-13  
**Weights:** `runs/fresh_yolov8n_293_final/weights/best.pt` (no retraining)  
**Data:** existing YOLO TEST split under `data/processed/yolo/images/test` (44 images still on disk)  
**Scope:** everything that can be completed without a physical IP Webcam / phone.

This document is a **test procedure and observational dump**. It is **not** a new official accuracy measurement. Recorded training/validation curves remain in `runs/fresh_yolov8n_293_final/results.csv` (last logged epoch: precision 0.595, recall 0.760, mAP50 0.767, mAP50-95 0.638). Those figures are **not** restated here as Phase 14 test-set accuracy.

Machine-readable observational output: `captures/reports/phase14_test_summary.json`.

---

## 1. Real-world test matrix

| ID | Test | Method | Expected behavior | Actual result | Status | Notes |
|----|------|--------|-------------------|---------------|--------|-------|
| A | Healthy onions | Inference on TEST images whose label class is HEALTHY (18 files, e.g. `onion_sample_007_*`, `023_*`, `028_*`, `034_*`, `037_*`) | Detect onion(s); class HEALTHY → grade GOOD | 13/18 images had top-1 HEALTHY. 5/18 top-1 ROTTEN. | OBSERVED | File-label vs top-1 only; not official mAP. |
| B | Damaged onions | TEST files `onion_sample_d_*` (3 images) | Detect; DAMAGED → BAD | Top-1 DAMAGED: 0/3. All 3 top-1 ROTTEN. 2 DAMAGED boxes appeared in the whole 44-image dump (not as top-1 on DAMAGED GT). | OBSERVED | Matches known weaker DAMAGED behaviour. |
| C | Rotten onions | TEST files `onion_sample_r_*` (19 images) | Detect; ROTTEN → BAD | 17/19 top-1 ROTTEN. | OBSERVED | Strongest of the four classes in this dump. |
| D | Sprouted onions | TEST files `onion_sample_s_001_*` (4 images) | Detect; SPROUTED → BAD | Top-1 SPROUTED: 0/4. 2 HEALTHY, 2 ROTTEN. Zero SPROUTED predictions in the 70 detections. | OBSERVED | Matches known weak SPROUTED recall on untouched test. |
| E | Multiple onions in one frame | Stitch `onion_sample_007_v1.jpeg` + `onion_sample_r_005_v1.jpeg`; `save_freeze` | ≥2 onions after overlap merge; mixed GOOD/BAD possible | `phase14_batch`: total 2, HEALTHY 1 GOOD, ROTTEN 1 BAD, raw_detections 3 | PASS | Stitched stills, not a physical tray. |
| F | Different onion orientations | Same bulb, views v1–v4 already in TEST | Detections across views | Views exist and were run; class can change by view (e.g. HEALTHY GT predicted ROTTEN on some views) | OBSERVED | Physical re-orientation on a table: PENDING USER TEST |
| G | Different distances | Physical camera distance sweep | Detect at moderate distance; miss/low-conf if too far | Not run (needs camera) | PENDING USER TEST | |
| H | Different lighting | Physical lighting change | Detect under even indoor light; fail/confuse in poor light | Not run | PENDING USER TEST | |
| I | Partial occlusion | Physical occlusion or cropped still | Partial box or miss; no crash | Not a dedicated crop suite. Closest: extra overlapping boxes (`multi_box` on 17 images) | PENDING USER TEST | Physical occlusion not performed. |
| J | Low-confidence detections | Conf &lt; 0.50 on real inference | Grade still from class; `review_state=REVIEW_REQUIRED` | 16 detections flagged REVIEW_REQUIRED. Example: `onion_sample_028_v2.jpeg` HEALTHY 0.2728 → REVIEW_REQUIRED | PASS | Threshold `grading.LOW_CONFIDENCE = 0.50`. |
| K | Size calibration | Synthetic ArUco artifact `make_test_calibration_image` + real TEST image without marker | Calibrated → diameter_mm set; no marker → diameter unavailable | Synthetic: calibrated, diameter_mm=40.2 vs expected 40.0, pixels_per_mm≈3.98. Real TEST image: `reference_not_detected`, diameter_mm=null | PASS | Not physical millimetre accuracy. No undersized class. Detector rounding ≠ printed ruler. |
| L | Batch statistics | Frozen stitched frame through `assess_frame` + `build_report` | total, GOOD, BAD, class breakdown, percentages | total=2, good=1 (50%), bad=1 (50%), HEALTHY=1, ROTTEN=1, DAMAGED=0, SPROUTED=0 | PASS | Matches the two clustered onions. |
| M | Report generation | `write_report` + frame JPEG | HTML, JSON, frame image; values = batch | `phase14_batch.html`, `.json`, `_frame.jpg` exist; JSON totals match batch | PASS | |
| N | Camera / IP Webcam | Open stream URL, freeze live frame | Preview + freeze assess | Not run in this phase | PENDING USER TEST | Default URL is env `ONION_STREAM_URL` (see `cv/live_assess.py`). |

---

## 2. Observational TEST-split dump (not official metrics)

Command: `python cv/_phase14_prepare.py` with `best.pt`.

| Item | Value |
|------|--------|
| Test images | 44 |
| Detections (conf≥0.25) | 70 |
| REVIEW_REQUIRED | 16 |
| Predicted classes | HEALTHY 22, ROTTEN 46, DAMAGED 2, SPROUTED 0 |
| GT images (from label files) | HEALTHY 18, DAMAGED 3, ROTTEN 19, SPROUTED 4 |
| Top-1 match vs label file | HEALTHY 13/18, DAMAGED 0/3, ROTTEN 17/19, SPROUTED 0/4 |

**Obvious failure categories (observable, not diagnosed):**

- `multi_box`: 17 images (extra boxes; batch clustering still used for official count)
- `pred_ROTTEN_gt_HEALTHY`: 5
- `pred_ROTTEN_gt_DAMAGED`: 3
- `no_detection`: 2
- `pred_HEALTHY_gt_SPROUTED`: 2
- `pred_ROTTEN_gt_SPROUTED`: 2

Do not treat top-1/label-file match as mAP.

---

## 3. Known model limitations (do not hide)

Already observed before this phase; this dump is consistent:

1. **DAMAGED is weaker** than HEALTHY/ROTTEN. On this TEST subset, no DAMAGED image had top-1 DAMAGED.
2. **SPROUTED recall is weak** on the untouched test set. Zero SPROUTED boxes in 70 detections; all four sprouted test views were HEALTHY or ROTTEN.
3. **Visible classes can be confused** (HEALTHY↔ROTTEN on some views). Real-camera confusion is expected; live confirmation is PENDING USER TEST.
4. **RGB cannot observe hidden/internal quality.** Reports already state this.
5. **Low confidence → REVIEW_REQUIRED**, not a third grade. GOOD/BAD still comes from class.
6. **Size never changes grade.** No undersized AI class.

---

## 4. Size pipeline (synthetic / smoke only)

Approach (code: `cv/size_measure.py`):

- ArUco `DICT_4X4_50`, default marker id 0, default printed side **50 mm**.
- `pixels_per_mm = marker_side_px / marker_mm`.
- Onion diameter ≈ mean of bbox width/height in px, then `/ pixels_per_mm`.
- If no marker: `calibrated=false`, `diameter_mm=None`, status `reference_not_detected`.

Results this run:

- Synthetic artifact: calibration **ok**; diameter **40.2 mm** vs constructed **40.0 mm** (marker side detection vs generated 200 px). Pipeline works. **Not field accuracy.**
- Real TEST photo: diameter unavailable as expected.

---

## 5. Batch test

Stitched HEALTHY-like `onion_sample_007_v1.jpeg` + ROTTEN `onion_sample_r_005_v1.jpeg`.

| Field | Value |
|-------|--------|
| total_onions | 2 |
| GOOD | 1 |
| BAD | 1 |
| good_pct / bad_pct | 50.0 / 50.0 |
| breakdown | HEALTHY 1, DAMAGED 0, ROTTEN 1, SPROUTED 0 |
| raw_detections | 3 (merged to 2) |
| calibrated | false |

Individual stills: 007_v1 → 1× HEALTHY GOOD (conf 0.979); r_005_v1 is a ROTTEN GT file. Stitched batch GOOD+BAD matches those two roles.

---

## 6. Report test

| Artifact | Present |
|----------|---------|
| `captures/reports/phase14_batch.html` | yes |
| `captures/reports/phase14_batch.json` | yes |
| `captures/reports/phase14_batch_frame.jpg` | yes |

JSON `total_onions` / GOOD / BAD / breakdown match the batch dict (`values_match_batch: true`). Diameter null because no ArUco on the stitch.

---

## 7. Failure / edge cases

| Case | Result | Status |
|------|--------|--------|
| Invalid image (`frame is None`) | `ValueError: invalid frame` | PASS |
| Empty/black frame | 0 onions, `unavailable`, `good_pct` null | PASS |
| Nonsensical gray 100×100 | 0 onions, unavailable | PASS |
| No reference marker | `reference_not_detected`, diameter null | PASS |
| Low confidence | REVIEW_REQUIRED on conf 0.2728 | PASS |
| Multiple onions | stitch batch 2 onions | PASS |
| Partial detections | extra boxes clustered; physical occlusion | PENDING USER TEST |
| IP Webcam / network | not opened this session | PENDING USER TEST |

---

## 8. Demo safety (do not change the model)

Failure modes that can embarrass a live demo:

| Scenario | Risk |
|----------|------|
| Poor lighting | Misses, ROTTEN/HEALTHY swaps, low conf |
| Too many onions | Extra boxes, messy overlay, slow CPU |
| Extreme distance | No detection |
| Low confidence | REVIEW_REQUIRED banners; looks “unsure” |
| Unsupported / blank image | Empty report |
| Camera unavailable | Stream fail (already seen in Phase I when phone off) |
| Network / IP mismatch | `ONION_STREAM_URL` not the phone’s current address |
| Sprouted showcase | Model may call HEALTHY or ROTTEN |
| Damaged showcase | Model may call ROTTEN |
| Asking for internal rot | RGB cannot show it |
| Size without printed ArUco | diameter unavailable |

**Safer demo conditions:**

- Even indoor light, one or two onions, moderate distance, phone and PC on the same Wi-Fi, URL verified before the audience.
- Prefer a clearly healthy bulb and a clearly rotten bulb (external rot).
- Do not promise sprouted/damaged as the headline live class.
- Print ArUco 4×4 id 0 at 50 mm only if showing size; otherwise say size is unavailable.
- Freeze a frame for official counts; do not treat live preview counts as the report.
- Have `phase14_batch` HTML as a backup still-image report.

---

## 9. Recommended physical tests for the user (tomorrow)

Do **not** mark these PASS until performed.

1. Confirm IP Webcam URL; open `cv/live_assess.py` / backend preview.
2. Freeze: 1 healthy, 1 damaged, 1 rotten, 1 sprouted (if available).
3. Two+ onions in one frame; compare freeze count vs hand count.
4. Near / mid / far distance.
5. Bright vs dim light.
6. Partial hand occlusion.
7. Optional: printed ArUco 50 mm in frame; confirm diameter appears.
8. Generate HTML/JSON from a live freeze and check totals.
9. Disconnect camera; confirm a clean error, not a crash.

---

## 10. Phase 14 preparation status

**Preparation complete for non-physical work. Physical IP Webcam remains PENDING USER TEST. Phase 15 not started.**

| Category | Count |
|----------|--------|
| Tests actually performed | Observational TEST inference (44 images); size synthetic+no-marker; stitch batch; HTML/JSON/frame; invalid/empty/gray/low-conf |
| Tests passed | J, K (pipeline, not mm accuracy), L, M; edge invalid/empty/no-marker/low-conf/multi-still |
| Tests failed | None of the executed pipeline tests crashed. Class-level observational mismatches are **limitations**, not a Phase 14 harness fail. |
| Tests pending user | G, H, I (physical), N, live F, live A–D with real produce |

**Files created**

- `docs/PHASE14_REAL_WORLD_TESTING.md`
- `cv/_phase14_prepare.py`
- `captures/reports/phase14_test_summary.json`
- `captures/reports/phase14_batch.html`
- `captures/reports/phase14_batch.json`
- `captures/reports/phase14_batch_frame.jpg`

**Files modified:** none of application/model code.

**Files deleted:** none (temporary local helpers `_pycheck.py` / `_pipshow.py` removed if present).

**Dependencies changed:** `requirements.txt` unchanged. Local Python 3.12 received `opencv-python` / `ultralytics` so this machine could run inference.

**Commands run**

```
python cv/_phase14_prepare.py
```

(interpreter: Python 3.12)

**Not done:** commit, push, retrain, UI redesign, dataset/architecture change, Phase 15.
