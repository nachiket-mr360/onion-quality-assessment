"""Build the Model V2 YOLO dataset split (group-aware) from corrected + new labels.

Policy (do not relax without review):

* `images/test` and `labels/test` are FROZEN. This script never writes to them.
  Their bytes are hashed before and after and must match.
* `data/raw/` and `labels_pending/` are read-only inputs. Nothing is renamed,
  moved, rewritten or deleted there.
* Only `images/train`, `images/val`, `labels/train`, `labels/val` are rewritten.
* A physical onion (`..._v1`..`v4` share one group key) is assigned to exactly
  one split, so no view of an onion can leak across splits.
* Invalid or conflicting material is excluded from the dataset but kept on disk.

Run:  .venv\\Scripts\\python.exe data\\processed\\yolo\\build_v2_split.py
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import random
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "raw"
YOLO = ROOT / "data" / "processed" / "yolo"
PENDING = YOLO / "labels_pending"
IMAGES = YOLO / "images"
LABELS = YOLO / "labels"

SEED = 42
CLS = {0: "HEALTHY", 1: "DAMAGED", 2: "ROTTEN", 3: "SPROUTED"}
IMG_EXT = {".jpg", ".jpeg", ".png"}
SPLITS = ("train", "val", "test")
EDITABLE = ("train", "val")
FROZEN = "test"
VAL_FRACTION = 0.15

# Material that must never enter the dataset. Kept on disk; reasons are carried
# over verbatim from the V1 build plus one label defect found during the V2 audit.
EXCLUDE = {
    "onion_sample_r_010_v2": ("unpaired_missing_pending", "stem"),
    "onion_sample_030_v1": ("mixed_id_physical_group", "physical_group_030"),
    "onion_sample_030_v3": ("mixed_id_physical_group", "physical_group_030"),
    "onion_sample_030_v4": ("mixed_id_physical_group", "physical_group_030"),
    "onion_sample_036_v1": ("mixed_id_physical_group", "physical_group_036"),
    "onion_sample_036_v2": ("malformed_label_missing_class_id", "physical_group_036"),
    "onion_sample_036_v3": ("mixed_id_physical_group", "physical_group_036"),
    "onion_sample_003_v1": ("byte_identical_conflict", "conflict_pair"),
    "onion_sample_003_v2": ("byte_identical_conflict", "conflict_pair"),
    "onion_sample_003_v3": ("byte_identical_conflict", "conflict_pair"),
    "onion_sample_003_v4": ("byte_identical_conflict", "conflict_pair"),
    "onion_sample_s_005_v1": ("byte_identical_conflict", "conflict_pair"),
    "onion_sample_s_005_v2": ("byte_identical_conflict", "conflict_pair"),
    "onion_sample_s_005_v3": ("byte_identical_conflict", "conflict_pair"),
    "onion_sample_s_005_v4": ("byte_identical_conflict", "conflict_pair"),
    "onion_sample_016_v1": ("byte_identical_conflict", "conflict_pair"),
    "onion_sample_016_v2": ("byte_identical_conflict", "conflict_pair"),
    "onion_sample_016_v3": ("byte_identical_conflict", "conflict_pair"),
    "onion_sample_016_v4": ("byte_identical_conflict", "conflict_pair"),
    "onion_sample_s_004_v1": ("byte_identical_conflict", "conflict_pair"),
    "onion_sample_s_004_v2": ("byte_identical_conflict", "conflict_pair"),
    "onion_sample_s_004_v3": ("byte_identical_conflict", "conflict_pair"),
    "onion_sample_s_004_v4": ("byte_identical_conflict", "conflict_pair"),
    "onion_sample_r_015_v1": ("byte_identical_conflict", "conflict_pair"),
    "onion_sample_r_015_v3": ("byte_identical_conflict", "conflict_pair"),
    "onion_sample_s_002_v1": ("byte_identical_conflict", "conflict_pair"),
    "onion_sample_s_002_v2": ("byte_identical_conflict", "conflict_pair"),
    "onion_sample_s_006_v1": ("byte_identical_agreement_duplicate", "keep_s_001"),
    "onion_sample_s_006_v2": ("byte_identical_agreement_duplicate", "keep_s_001"),
    "onion_sample_s_006_v3": ("byte_identical_agreement_duplicate", "keep_s_001"),
}

notes: list[str] = []


def note(msg: str) -> None:
    notes.append(msg)
    print(msg)


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def group_key(stem: str) -> str:
    """v1..v4 of one physical onion collapse to one key."""
    g = re.sub(r"_v[0-9]+$", "", stem)
    return g.replace("onion_sample_s-", "onion_sample_s_")


def parse_label(text: str) -> tuple[list[tuple[int, list[float]]], list[str]]:
    rows: list[tuple[int, list[float]]] = []
    issues: list[str] = []
    body = text.strip()
    if not body:
        return rows, ["empty_label"]
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 5:
            issues.append(f"bad_field_count:{len(parts)}")
            continue
        try:
            cid = int(float(parts[0]))
            nums = [float(x) for x in parts[1:]]
        except ValueError:
            issues.append("unparsable")
            continue
        if cid not in CLS:
            issues.append(f"class_id_out_of_range:{cid}")
        if any(not (0.0 <= n <= 1.0) for n in nums):
            issues.append("coord_out_of_range")
        if nums[2] <= 0.0 or nums[3] <= 0.0:
            issues.append("non_positive_wh")
        rows.append((cid, nums))
    return rows, issues


def walk_images(base: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for dp, _, fs in os.walk(base):
        for f in fs:
            p = Path(dp) / f
            if p.suffix.lower() in IMG_EXT:
                out[p.stem] = p
    return out


def walk_pending() -> dict[str, Path]:
    out: dict[str, Path] = {}
    for dp, _, fs in os.walk(PENDING):
        for f in fs:
            if f.lower() == "classes.txt":
                continue
            p = Path(dp) / f
            if p.suffix.lower() == ".txt":
                out[p.stem[:-8] if f.endswith(".xml.txt") else p.stem] = p
    return out


def frozen_snapshot() -> dict[str, str]:
    snap: dict[str, str] = {}
    for d in (IMAGES / FROZEN, LABELS / FROZEN):
        for p in sorted(d.iterdir()):
            if p.is_file():
                snap[str(p.relative_to(ROOT)).replace("\\", "/")] = sha_file(p)
    return snap


def clear_split(split: str) -> None:
    """Delete only the files of a train/val directory. Never called for test."""
    if split == FROZEN:
        raise SystemExit("REFUSING TO CLEAR FROZEN TEST SPLIT")
    for d in (IMAGES / split, LABELS / split):
        d.mkdir(parents=True, exist_ok=True)
        for p in d.iterdir():
            if p.is_file():
                p.unlink()


def main() -> None:
    errors: list[str] = []

    # ---- 0. freeze test and read every source into memory up front -----------
    test_snap_before = frozen_snapshot()
    raw_imgs = walk_images(RAW)
    pending = walk_pending()

    prepared_imgs: dict[str, tuple[str, Path]] = {}
    prepared_labs: dict[str, tuple[str, Path]] = {}
    for split in SPLITS:
        for p in sorted((IMAGES / split).iterdir()):
            if p.is_file():
                prepared_imgs.setdefault(p.stem, (split, p))
        for p in sorted((LABELS / split).glob("*.txt")):
            prepared_labs.setdefault(p.stem, (split, p))

    test_stems = sorted(p.stem for p in (IMAGES / FROZEN).iterdir() if p.is_file())
    if not test_stems:
        raise SystemExit("INTEGRITY STOP: frozen test split is empty")
    note(f"frozen test split: {len(test_stems)} images, {len(test_snap_before)} files hashed")

    candidates = sorted(set(raw_imgs) | set(prepared_imgs))
    sources: dict[str, dict] = {}
    excluded_rows: list[dict] = []
    for stem in candidates:
        img_path = raw_imgs.get(stem)
        lab_path = pending.get(stem)
        origin = "raw+pending"
        if img_path is None or lab_path is None:
            pi = prepared_imgs.get(stem)
            pl = prepared_labs.get(stem)
            if img_path is None and pi is None:
                errors.append(f"no image source:{stem}")
                continue
            if lab_path is None and pl is None:
                if stem in EXCLUDE:
                    # known unpaired material: record it and keep it out of the dataset
                    reason, scope = EXCLUDE[stem]
                    excluded_rows.append(
                        {
                            "stem": stem,
                            "group": group_key(stem),
                            "reason": reason,
                            "scope": scope,
                            "image_src": str(img_path.relative_to(ROOT)).replace("\\", "/")
                            if img_path
                            else "",
                            "label_src": "",
                            "kept_on_disk": "yes",
                        }
                    )
                    continue
                errors.append(f"no label source:{stem}")
                continue
            origin = "prepared_copy_only"
        img_path = img_path or prepared_imgs[stem][1]
        lab_path = lab_path or prepared_labs[stem][1]
        # Snapshot bytes so later directory clearing cannot invalidate a source.
        label_bytes = lab_path.read_bytes()
        sources[stem] = {
            "image_bytes": img_path.read_bytes(),
            "label_bytes": label_bytes,
            "label_text": label_bytes.decode("utf-8", errors="replace"),
            "origin": origin,
            "image_src": str(img_path.relative_to(ROOT)).replace("\\", "/"),
            "label_src": str(lab_path.relative_to(ROOT)).replace("\\", "/"),
            "image_sha": sha_file(img_path),
            "ext": img_path.suffix.lower(),
        }

    for d in sorted(set(EXCLUDE) - set(sources)):
        note(f"excluded stem absent from disk (already gone): {d}")

    # ---- 1. per-stem validation --------------------------------------------
    valid: dict[str, dict] = {}
    for stem in sorted(sources):
        s = sources[stem]
        rows, issues = parse_label(s["label_text"])
        reason = None
        scope = ""
        if stem in EXCLUDE:
            reason, scope = EXCLUDE[stem]
        elif issues:
            reason, scope = "invalid_label:" + ",".join(sorted(set(issues))), "auto"
        elif len(rows) != 1:
            reason, scope = f"box_count_not_one:{len(rows)}", "auto"
        if reason:
            excluded_rows.append(
                {
                    "stem": stem,
                    "group": group_key(stem),
                    "reason": reason,
                    "scope": scope,
                    "image_src": s["image_src"],
                    "label_src": s["label_src"],
                    "kept_on_disk": "yes",
                }
            )
            continue
        cid = rows[0][0]
        valid[stem] = {
            "stem": stem,
            "group": group_key(stem),
            "class_id": cid,
            "class_name": CLS[cid],
            "image_bytes": s["image_bytes"],
            "label_bytes": s["label_bytes"],
            "label_text": s["label_text"],
            "ext": s["ext"],
            "origin": s["origin"],
            "image_src": s["image_src"],
            "label_src": s["label_src"],
            "image_sha": s["image_sha"],
        }

    note(f"candidate stems on disk: {len(candidates)} (with a usable source: {len(sources)})")

    # ---- 2. group integrity + test group capture ---------------------------
    groups: dict[str, list[str]] = defaultdict(list)
    for stem in sorted(valid):
        groups[valid[stem]["group"]].append(stem)

    group_class: dict[str, int] = {}
    for g, members in sorted(groups.items()):
        classes = {valid[m]["class_id"] for m in members}
        if len(classes) != 1:
            errors.append(f"mixed class inside group {g}: {sorted(classes)} -> {members}")
            continue
        group_class[g] = next(iter(classes))

    missing_test_label = [s for s in test_stems if s not in prepared_labs]
    if missing_test_label:
        errors.append(f"frozen test stems without label: {missing_test_label}")
    frozen_bad = [s for s in test_stems if s not in valid]
    if frozen_bad:
        errors.append(f"frozen test stems that did not validate: {frozen_bad}")

    test_groups = {group_key(s) for s in test_stems}
    for g in sorted(test_groups):
        if g not in groups:
            errors.append(f"frozen test group not in valid set: {g}")
            continue
        outside = sorted(set(groups[g]) - set(test_stems))
        if outside:
            errors.append(f"frozen test group {g} also has stems outside test: {outside}")

    # ---- 3. group-aware train/val plan for everything outside test ----------
    pool = sorted(g for g in groups if g not in test_groups)
    total_images = len(valid)
    pool_images = sum(len(groups[g]) for g in pool)
    val_target = int(round(VAL_FRACTION * total_images))

    rng = random.Random(SEED)
    per_class_groups: dict[int, list[str]] = defaultdict(list)
    for g in pool:
        per_class_groups[group_class[g]].append(g)

    assignment: dict[str, str] = {}
    for cid in sorted(per_class_groups):
        gl = sorted(per_class_groups[cid])
        rng.shuffle(gl)  # seeded, so the plan is reproducible
        class_imgs = sum(len(groups[g]) for g in gl)
        class_target = max(1, int(round(val_target * class_imgs / max(1, pool_images))))
        acc = 0
        for i, g in enumerate(gl):
            if acc >= class_target or len(gl) - (i + 1) < 1:
                break
            assignment[g] = "val"
            acc += len(groups[g])
        if len(gl) > 1 and not any(assignment.get(g) == "val" for g in gl):
            # keep at least one group per class in val when the class allows it
            assignment[gl[0]] = "val"
        for g in gl:
            assignment.setdefault(g, "train")

    for g in test_groups:
        assignment[g] = FROZEN

    missing = [g for g in groups if g not in assignment]
    if missing:
        errors.append(f"groups without split assignment: {missing}")

    # ---- 4. write editable splits only ------------------------------------
    for split in EDITABLE:
        clear_split(split)
    for cache in (LABELS / "train.cache", LABELS / "val.cache"):
        if cache.exists():
            cache.unlink()  # stale caches for rebuilt splits

    manifest_rows: list[dict] = []
    split_counts = Counter()
    grp_counts = Counter()
    cls_counts: dict[str, Counter] = {sp: Counter() for sp in SPLITS}
    for g in sorted(groups):
        split = assignment[g]
        grp_counts[split] += 1
        for stem in groups[g]:
            m = valid[stem]
            if split != FROZEN:
                dst_img = IMAGES / split / (stem + m["ext"])
                dst_lab = LABELS / split / (stem + ".txt")
                dst_img.write_bytes(m["image_bytes"])
                dst_lab.write_bytes(m["label_bytes"])
            split_counts[split] += 1
            cls_counts[split][m["class_id"]] += 1
            manifest_rows.append(
                {
                    "stem": stem,
                    "group": g,
                    "split": split,
                    "class_id": m["class_id"],
                    "class_name": m["class_name"],
                    "source": m["origin"],
                    "image_src": m["image_src"],
                    "label_src": m["label_src"],
                    "image_sha256": m["image_sha"],
                }
            )

    with (YOLO / "v2_split_manifest.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "stem",
                "group",
                "split",
                "class_id",
                "class_name",
                "source",
                "image_src",
                "label_src",
                "image_sha256",
            ],
        )
        w.writeheader()
        w.writerows(sorted(manifest_rows, key=lambda r: (r["split"], r["group"], r["stem"])))

    with (YOLO / "v2_exclusion_manifest.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "stem",
                "group",
                "reason",
                "scope",
                "image_src",
                "label_src",
                "kept_on_disk",
            ],
        )
        w.writeheader()
        w.writerows(excluded_rows)

    # ---- 5. validation over what is now on disk ---------------------------
    seen_stem: dict[str, str] = {}
    group_split: dict[str, str] = {}
    on_disk_stems: dict[str, str] = {}
    for split in SPLITS:
        imgs = sorted((IMAGES / split).iterdir())
        imgs = [p for p in imgs if p.is_file()]
        labs = {p.stem: p for p in (LABELS / split).glob("*.txt")}
        img_stems = {p.stem for p in imgs}
        if img_stems != set(labs):
            errors.append(
                f"{split}: image/label pairing mismatch "
                f"only_img={sorted(img_stems - set(labs))} only_lab={sorted(set(labs) - img_stems)}"
            )
        if not imgs:
            errors.append(f"{split}: empty split")
        on_disk_stems[split] = img_stems
        for p in imgs:
            stem = p.stem
            if stem in seen_stem:
                errors.append(f"stem in two splits: {stem} ({seen_stem[stem]}, {split})")
            seen_stem[stem] = split
            if stem in EXCLUDE:
                errors.append(f"excluded stem present in dataset: {split}/{stem}")
            lab = labs.get(stem)
            if lab is None:
                continue
            rows, issues = parse_label(lab.read_text(encoding="utf-8", errors="replace"))
            if issues:
                errors.append(f"invalid label on disk {split}/{stem}: {issues}")
            if len(rows) != 1:
                errors.append(f"box count != 1 on disk {split}/{stem}: {len(rows)}")
            g = group_key(stem)
            if g in group_split and group_split[g] != split:
                errors.append(f"GROUP LEAK {g} in {group_split[g]} and {split}")
            group_split[g] = split

    # class ids on disk
    disk_class = Counter()
    for split in SPLITS:
        for p in (LABELS / split).glob("*.txt"):
            rows, _ = parse_label(p.read_text(encoding="utf-8", errors="replace"))
            for cid, _ in rows:
                disk_class[cid] += 1
                if cid not in CLS:
                    errors.append(f"class id outside 0-3: {split}/{p.stem}={cid}")

    # duplicate / conflicting images inside the prepared dataset
    by_hash: dict[str, list[dict]] = defaultdict(list)
    for r in manifest_rows:
        by_hash[r["image_sha256"]].append(r)
    dup_groups = {h: rs for h, rs in by_hash.items() if len(rs) > 1}
    hard_conflicts = [
        rs for rs in dup_groups.values() if len({x["class_id"] for x in rs}) > 1
    ]
    soft_dupes = [rs for rs in dup_groups.values() if len({x["class_id"] for x in rs}) == 1]
    if hard_conflicts:
        errors.append(
            "byte-identical images with conflicting classes: "
            + json.dumps([[x["stem"] for x in rs] for rs in hard_conflicts])
        )
    for rs in soft_dupes:
        # not a labelling conflict, but still duplicate material worth reporting
        note("duplicate image (identical bytes, same class): " + json.dumps([x["stem"] for x in rs]))

    # a conflicting/excluded twin must not be able to leak in
    leak = sorted(set(EXCLUDE) & {r["stem"] for r in manifest_rows})
    if leak:
        errors.append(f"excluded twins present in dataset: {leak}")

    # frozen test must be byte-identical after the rebuild
    test_snap_after = frozen_snapshot()
    if test_snap_before != test_snap_after:
        errors.append("FROZEN TEST SPLIT CHANGED")

    # every split must expose all four classes
    for split in SPLITS:
        present = {cid for cid in CLS if cls_counts[split][cid] > 0}
        if present != set(CLS):
            errors.append(f"{split} missing classes: {sorted(set(CLS) - present)}")

    if set(test_stems) != on_disk_stems[FROZEN]:
        errors.append("frozen test membership changed after rebuild")

    # previously used images must all still be present. The V1 manifest is the
    # stable historical record; fall back to the prepared dirs if it is missing.
    v1_manifest = YOLO / "fresh_split_manifest.csv"
    if v1_manifest.is_file():
        with v1_manifest.open(newline="", encoding="utf-8") as f:
            baseline = {r["stem"] for r in csv.DictReader(f)}
        baseline_src = "fresh_split_manifest.csv"
    else:
        baseline = set(prepared_imgs)
        baseline_src = "prepared directories"
    lost = sorted(baseline - set(seen_stem))
    if lost:
        errors.append(f"previously present images lost: {lost}")
    added = sorted(set(seen_stem) - baseline)
    note(f"baseline={baseline_src} baseline_images={len(baseline)}")
    note(f"images newly added to the dataset: {len(added)} -> {added}")

    # ---- 6. report --------------------------------------------------------
    origin_counts = Counter(m["origin"] for m in valid.values())
    prepared_only = sorted(s for s, m in valid.items() if m["origin"] == "prepared_copy_only")

    lines: list[str] = []
    lines.append("MODEL V2 DATASET SPLIT VALIDATION")
    lines.append(f"seed={SEED} val_fraction={VAL_FRACTION}")
    lines.append(f"candidates_with_source={len(sources)}")
    lines.append(f"candidate_stems={len(candidates)}")
    lines.append(f"excluded={len(excluded_rows)}")
    lines.append(f"valid_images={len(valid)}")
    lines.append(f"valid_groups={len(groups)}")
    lines.append(
        f"sources raw_plus_pending={origin_counts['raw+pending']} "
        f"prepared_copy_only={origin_counts['prepared_copy_only']}"
    )
    if prepared_only:
        lines.append(f"prepared_copy_only_stems={prepared_only}")
    lines.append(
        f"counts images train={split_counts['train']} val={split_counts['val']} "
        f"test={split_counts[FROZEN]} total={sum(split_counts.values())}"
    )
    lines.append(
        f"counts groups train={grp_counts['train']} val={grp_counts['val']} "
        f"test={grp_counts[FROZEN]} total={sum(grp_counts.values())}"
    )
    for split in SPLITS:
        d = cls_counts[split]
        lines.append(f"class {split} H={d[0]} D={d[1]} R={d[2]} S={d[3]} total={sum(d.values())}")
    tot = Counter()
    for split in SPLITS:
        tot.update(cls_counts[split])
    lines.append(f"class TOTAL H={tot[0]} D={tot[1]} R={tot[2]} S={tot[3]} total={sum(tot.values())}")
    for split in SPLITS:
        present = sorted(cid for cid in CLS if cls_counts[split][cid] > 0)
        lines.append(f"classes_present_{split}={[CLS[c] for c in present]}")
    lines.append(
        "split_fraction "
        + " ".join(
            f"{sp}={split_counts[sp] / max(1, sum(split_counts.values())):.3f}" for sp in SPLITS
        )
    )
    lines.append(f"test_frozen_unchanged={'PASS' if test_snap_before == test_snap_after else 'FAIL'}")
    lines.append(f"test_groups={len(test_groups)}")
    lines.append(f"group_leakage={'FAIL' if any('GROUP LEAK' in e for e in errors) else 'PASS_ZERO'}")
    lines.append(f"byte_identical_conflicts={len(hard_conflicts)}")
    lines.append(f"byte_identical_same_class_duplicates={len(soft_dupes)}")
    lines.append(f"empty_labels={sum(1 for r in excluded_rows if 'empty_label' in r['reason'])}")
    lines.append(f"class_ids_on_disk={dict(sorted(disk_class.items()))}")
    lines.append(f"errors={errors}")
    lines.append("")
    lines.append("notes:")
    lines.extend(f"  - {n}" for n in notes)
    report = "\n".join(lines) + "\n"
    (YOLO / "v2_validation_report.txt").write_text(report, encoding="utf-8")
    print()
    print(report)
    if errors:
        raise SystemExit("VALIDATION FAILED")


if __name__ == "__main__":
    main()
