# Phase 4 — Annotation Guideline and Workflow

**Status:** workflow setup only. Images are **not** annotated yet.  
**Raw data:** `data/raw/` is source of truth. Do not rename, move, resize, overwrite, or delete it.

This document is the annotation contract for SIH26031 onion detection + visible-condition classification.

---

## 1. Goal

Produce **YOLO detection** labels so the later Phase 5 model can:

1. Detect each visible onion.
2. Assign one visible-condition class.

This is **not** GOOD/BAD grading and **not** size grading.

---

## 2. Tool

**Selected tool: LabelImg** (local desktop, YOLO txt export).

Why:

- Runs on this Windows laptop, no cloud, no Docker, no extra web stack.
- Writes YOLO detection labels directly: `class_id x_center y_center width height` (normalized 0–1).
- Matches the locked training format.
- No React, FastAPI, Roboflow, or database.

Launch (after `labelImg` is installed in `.venv`):

```bat
cd C:\College\SIH
.venv\Scripts\activate
python cv\launch_labelimg.py
```

Or:

```bat
.venv\Scripts\labelImg.exe data\raw data\processed\yolo\classes.txt data\processed\yolo\labels_pending
```

Annotators must **Save in YOLO format** (not Pascal VOC).

---

## 3. Class mapping

File: `data/processed/yolo/classes.txt`

| class_id | Name | Meaning |
|---------:|------|---------|
| 0 | HEALTHY | Visually healthy; no clear target defect |
| 1 | DAMAGED | Visible mechanical/physical damage |
| 2 | ROTTEN | Visible decay / rot / fungal spoilage |
| 3 | SPROUTED | Visible sprouting |

**Do not annotate these as classes:**

- GOOD
- BAD
- UNDERSIZED
- REVIEW REQUIRED

GOOD/BAD = later quality engine.  
UNDERSIZED = later size measurement.  
REVIEW REQUIRED = uncertainty process, not a YOLO class.

---

## 4. Box rules

1. Every **visible onion** gets **one** bounding box.
2. Box tightly around the onion (include neck/sprout if that is part of the onion).
3. Do not box table, hands, coins, or background junk unless it is a second onion.
4. If two onion objects are visible, draw two boxes. Assign each its own class.
5. One image can have mixed classes only if multiple onions are actually present.
6. Folder name (`healthy/`, `damaged/`, …) is a **hint**, not an automatic label. Label what is visible in **this** view.
7. Do not invent boxes. If you cannot see an onion, skip the image and add it to the review list.

YOLO line format:

```
class_id x_center y_center width height
```

All four geometry values are relative to image width/height, range 0–1.

Example (single healthy onion, roughly centred):

```
0 0.51 0.48 0.42 0.55
```

---

## 5. Class definitions

### HEALTHY (0)

Use when the onion looks sound in this photo:

- intact bulb
- no clear cut, crack, crush, or exposed flesh that is the target defect
- no obvious rot/mould/decay
- no visible sprout

Dry papery skin, dirt, or mild colour variation **alone** is not DAMAGED.

### DAMAGED (1)

Use when there is **visible mechanical/physical injury**, for example:

- cuts, cracks, splits
- significant bruising
- crushed / deformed tissue
- clearly exposed inner flesh from injury

### ROTTEN (2)

Use when there is **visible decay**, for example:

- soft rot, wet collapse
- mould / fungal patches
- blackened or obviously rotting tissue

Priority if several defects are visible on the **same** onion:

```
ROTTEN > SPROUTED > DAMAGED > HEALTHY
```

Draw **one** box and assign the highest-priority visible class.

### SPROUTED (3)

Use when a **sprout is visible** (green/white/pink shoot emerging from the neck or body).

A dry root plate, a long neck, or leftover stem **without a sprout** is not SPROUTED.

---

## 6. Ambiguous cases — do not guess

Do **not** silently force a class when the view is genuinely unclear.

| Situation | Action |
|-----------|--------|
| Peeling / dry skin vs real damage | HEALTHY unless injury (cut, crush, exposed flesh) is clear. Otherwise **review**. |
| Weak sprout vs root-plate / neck | SPROUTED only if a sprout is clearly visible. Otherwise **review** (do not use SPROUTED on `s_001` views that show only a root plate). |
| Borderline decay vs dirt / stain | ROTTEN only if decay is clear. Otherwise **review**. |
| Folder says damaged/rotten/sprouted but this view does not show it | Label the **visible** condition, or **review**. Do not copy the folder name blindly. |
| Extra fragment / skin in background (`r_001` has this) | Box only if it is a distinct onion. Do not box loose skin as an onion. If unsure → **review**. |
| Cannot tell if the object is an onion | **review**; no box. |

**Review procedure (not a YOLO class):**

1. Do not write a fake label file for that image.
2. Add one line to `data/processed/annotation_review.csv`:

```text
path,onion_id,folder_class,reason,decision
data/raw/rotten/onion_sample_r_001_v1.jpeg,R001,ROTTEN,background fragment may or may not be a second onion,pending
```

3. A second person / Technical Lead decides later.
4. Until decided, that image is **excluded from train/val/test**.

The CSV is created when the first review case appears. Do not pre-fill invented rows.

---

## 7. Duplicate handling (healthy 011 / 013)

**Raw files stay.** Do not delete `data/raw/healthy/onion_sample_013_*.jpeg`.

SHA-256: `H011` and `H013` are the same four images (`v3`/`v4` swapped).

**Processed-dataset rule (later, not implemented now):**

- Canonical onion_id = **H011**
- `H013` is an alias, not a second onion
- Copy **at most one** of each duplicate pair into `data/processed/yolo/images/`
- If both paths were ever listed, they **must** share the same split
- Never treat 013 as independent train/test material

---

## 8. Onion IDs (metadata only — do not rename raw files)

| Folder | Filename | onion_id |
|--------|----------|----------|
| healthy | `onion_sample_{NNN}_v{K}.jpeg` | `H{NNN}` |
| damaged | `onion_sample_d_{NNN}_v{K}.jpeg` | `D{NNN}` |
| rotten | `onion_sample_r_{NNN}_v{K}.jpeg` | `R{NNN}` |
| sprouted | `onion_sample_s_{NNN}_v{K}.jpeg` | `S{NNN}` |

Example: `data/raw/damaged/onion_sample_d_004_v2.jpeg` → onion_id `D004`, view `2`.

---

## 9. Onion-level train / val / test (later)

**Not executed in this step.** When labels exist:

1. Group images by `onion_id` (class letter + number).
2. Merge `H013` → `H011`.
3. Assign each **onion**, not each file, to train or val or test.
4. All views `v1..v4` of that onion follow that split.
5. Prefer stratification by class at onion level, not image level.
6. Sprouted currently has **one** onion (`S001`). It cannot be in train and test. When more sprouted onions arrive, re-split.
7. Incomplete view sets (e.g. `H001` missing v1/v4) still stay together.

Suggested future ratio (subject to Technical Lead): about 70% / 15% / 15% of **onions**.

Do not split until annotation of the current batch is accepted.

---

## 10. Where labels will live (not populated yet)

Planned (empty until annotation starts):

```
data/processed/yolo/
  classes.txt          ← exists
  dataset.yaml         ← placeholder only
  labels_pending/      ← LabelImg output during annotation (later)
  images/{train,val,test}/   ← later copy, never overwrite raw
  labels/{train,val,test}/   ← later
```

LabelImg should write `.txt` files next to a **copy** or into `labels_pending/`, never into `data/raw/`.

---

## 11. What not to do

- Do not train YOLO.
- Do not create fake boxes.
- Do not annotate GOOD/BAD/UNDERSIZED.
- Do not use Roboflow/cloud unless the Technical Lead approves.
- Do not start FastAPI/React/database/ArUco/tracking.
- Do not rewrite `data/raw/`.
