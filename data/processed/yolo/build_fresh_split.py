"""Fresh physical-onion YOLO split. Does not modify raw JPEGs or pending labels."""
from __future__ import annotations

import csv
import hashlib
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
IMG_EXT = {".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG"}

EXCLUDE = {
    "onion_sample_r_010_v2": ("unpaired_missing_pending", "stem"),
    "onion_sample_030_v1": ("mixed_id_physical_group", "physical_group_030"),
    "onion_sample_030_v3": ("mixed_id_physical_group", "physical_group_030"),
    "onion_sample_030_v4": ("mixed_id_physical_group", "physical_group_030"),
    "onion_sample_036_v1": ("mixed_id_physical_group", "physical_group_036"),
    "onion_sample_036_v2": ("mixed_id_physical_group", "physical_group_036"),
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


def stem_label(name: str) -> str:
    return name[:-8] if name.endswith(".xml.txt") else Path(name).stem


def parse_yolo(path: Path):
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    rows = []
    issues = []
    if not text:
        return rows, ["empty"]
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 5:
            issues.append("bad_fields")
            continue
        try:
            cid = int(float(parts[0]))
            nums = [float(x) for x in parts[1:]]
        except ValueError:
            issues.append("parse")
            continue
        if cid not in CLS:
            issues.append(f"bad_id:{cid}")
        if any(not (0.0 <= n <= 1.0) for n in nums):
            issues.append("oob")
        rows.append(cid)
    return rows, issues


def group_key(stem: str) -> str:
    g = re.sub(r"_v[0-9]+$", "", stem)
    g = g.replace("onion_sample_s-", "onion_sample_s_")
    return g


def list_raw():
    out = {}
    for dp, _, fs in os.walk(RAW):
        for f in fs:
            if Path(f).suffix in IMG_EXT:
                p = Path(dp) / f
                out[p.stem] = p
    return out


def list_pending():
    out = {}
    for dp, _, fs in os.walk(PENDING):
        for f in fs:
            if f.lower() == "classes.txt":
                continue
            if f.endswith(".txt"):
                p = Path(dp) / f
                out[stem_label(f)] = p
    return out


def assign_groups(groups: dict, rng: random.Random) -> dict:
    by_cls = defaultdict(list)
    for g, members in groups.items():
        classes = {m["cid"] for m in members}
        if len(classes) != 1:
            raise SystemExit(f"INTEGRITY: mixed class in keep group {g}: {classes}")
        cid = next(iter(classes))
        by_cls[cid].append(g)
    for cid in by_cls:
        by_cls[cid].sort()
        rng.shuffle(by_cls[cid])

    assignment = {}
    # Reserve DAMAGED(1) and SPROUTED(3) into val and test when possible.
    for cid in (1, 3, 0, 2):
        lst = by_cls.get(cid, [])
        if len(lst) >= 3:
            assignment[lst[0]] = "val"
            assignment[lst[1]] = "test"
        elif len(lst) == 2:
            assignment[lst[0]] = "val"
            assignment[lst[1]] = "test"

    def nimg(g):
        return len(groups[g])

    total = sum(nimg(g) for g in groups)
    targets = {"train": 0.70 * total, "val": 0.15 * total, "test": 0.15 * total}
    counts = Counter()
    for g, sp in assignment.items():
        counts[sp] += nimg(g)

    remaining = [g for g in groups if g not in assignment]
    remaining.sort()
    rng.shuffle(remaining)

    # Ensure every class appears in train.
    for cid in (0, 1, 2, 3):
        train_has = any(
            assignment.get(g) == "train" and next(iter({m["cid"] for m in groups[g]})) == cid
            for g in assignment
        )
        if train_has:
            continue
        for g in remaining:
            if next(iter({m["cid"] for m in groups[g]})) == cid:
                assignment[g] = "train"
                counts["train"] += nimg(g)
                remaining.remove(g)
                break

    for g in remaining:
        deficits = {sp: targets[sp] - counts[sp] for sp in ("train", "val", "test")}
        # Prefer the most under-filled split; tie-break train, val, test.
        sp = max(("train", "val", "test"), key=lambda s: (deficits[s], {"train": 2, "val": 1, "test": 0}[s]))
        assignment[g] = sp
        counts[sp] += nimg(g)
    return assignment


def clear_split_dir(d: Path):
    d.mkdir(parents=True, exist_ok=True)
    for p in d.iterdir():
        if p.is_file():
            p.unlink()


def main():
    raw = list_raw()
    pending = list_pending()
    problems = []

    manifest_rows = []
    for stem, (reason, scope) in sorted(EXCLUDE.items()):
        jpg = raw.get(stem)
        lab = pending.get(stem)
        manifest_rows.append(
            {
                "stem": stem,
                "reason": reason,
                "scope": scope,
                "jpeg_path": str(jpg.relative_to(ROOT)).replace("\\", "/") if jpg else "",
                "pending_label_path": str(lab.relative_to(ROOT)).replace("\\", "/") if lab else "",
                "kept_on_disk": "yes",
            }
        )

    man_path = YOLO / "exclusion_manifest.csv"
    with man_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["stem", "reason", "scope", "jpeg_path", "pending_label_path", "kept_on_disk"],
        )
        w.writeheader()
        w.writerows(manifest_rows)

    keep = []
    for stem, jpg in sorted(raw.items()):
        if stem in EXCLUDE:
            continue
        lab = pending.get(stem)
        if lab is None:
            if stem == "onion_sample_r_010_v2":
                continue
            problems.append(f"paired_eligible_missing_label:{stem}")
            continue
        rows, issues = parse_yolo(lab)
        if issues or len(rows) != 1:
            problems.append(f"bad_label:{stem}:{issues}:{rows}")
            continue
        keep.append({"stem": stem, "jpeg": jpg, "label": lab, "cid": rows[0], "group": group_key(stem)})

    if problems:
        raise SystemExit("INTEGRITY STOP\n" + "\n".join(problems))

    if len(keep) != 293:
        raise SystemExit(f"INTEGRITY STOP: expected 293 keep stems, got {len(keep)}")

    groups = defaultdict(list)
    for m in keep:
        groups[m["group"]].append(m)

    rng = random.Random(SEED)
    assignment = assign_groups(groups, rng)

    # Copy prepared split (replace obsolete 215-image copies only).
    for split in ("train", "val", "test"):
        clear_split_dir(IMAGES / split)
        clear_split_dir(LABELS / split)

    split_rows = []
    copied = Counter()
    cls_counts = defaultdict(Counter)
    grp_counts = Counter()
    seen_stem = set()
    for g, members in groups.items():
        sp = assignment[g]
        grp_counts[sp] += 1
        for m in members:
            if m["stem"] in seen_stem:
                raise SystemExit(f"duplicate stem {m['stem']}")
            seen_stem.add(m["stem"])
            dst_img = IMAGES / sp / (m["stem"] + m["jpeg"].suffix.lower())
            dst_lab = LABELS / sp / (m["stem"] + ".txt")
            shutil.copy2(m["jpeg"], dst_img)
            shutil.copy2(m["label"], dst_lab)
            copied[sp] += 1
            cls_counts[sp][m["cid"]] += 1
            split_rows.append(
                {
                    "stem": m["stem"],
                    "group": g,
                    "split": sp,
                    "class_id": m["cid"],
                    "class_name": CLS[m["cid"]],
                    "jpeg_src": str(m["jpeg"].relative_to(ROOT)).replace("\\", "/"),
                    "label_src": str(m["label"].relative_to(ROOT)).replace("\\", "/"),
                }
            )

    split_path = YOLO / "fresh_split_manifest.csv"
    with split_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["stem", "group", "split", "class_id", "class_name", "jpeg_src", "label_src"],
        )
        w.writeheader()
        w.writerows(sorted(split_rows, key=lambda r: (r["split"], r["group"], r["stem"])))

    # Validation
    errors = []
    all_prepared_stems = []
    group_split = {}
    for split in ("train", "val", "test"):
        imgs = sorted((IMAGES / split).glob("*"))
        labs = {p.stem: p for p in (LABELS / split).glob("*.txt")}
        if len(imgs) != len(labs):
            errors.append(f"{split} img/lab count {len(imgs)}/{len(labs)}")
        for img in imgs:
            all_prepared_stems.append((img.stem, split))
            if img.stem not in labs:
                errors.append(f"missing label {split}/{img.stem}")
                continue
            if img.stem in EXCLUDE:
                errors.append(f"excluded in split {img.stem}")
            rows, issues = parse_yolo(labs[img.stem])
            if issues or len(rows) != 1:
                errors.append(f"invalid {split}/{img.stem} {issues} {rows}")
            g = group_key(img.stem)
            if g in group_split and group_split[g] != split:
                errors.append(f"GROUP LEAK {g} in {group_split[g]} and {split}")
            group_split[g] = split
    stems_only = [s for s, _ in all_prepared_stems]
    if len(stems_only) != len(set(stems_only)):
        errors.append("stem in multiple splits")
    if set(stems_only) & set(EXCLUDE):
        errors.append("excluded stem present")
    if len(stems_only) != 293:
        errors.append(f"prepared count {len(stems_only)} != 293")

    report = YOLO / "fresh_split_validation.txt"
    lines = []
    lines.append(f"seed={SEED}")
    lines.append(f"keep_images={len(keep)}")
    lines.append(f"keep_groups={len(groups)}")
    lines.append(f"counts images train={copied['train']} val={copied['val']} test={copied['test']} total={sum(copied.values())}")
    lines.append(f"counts groups train={grp_counts['train']} val={grp_counts['val']} test={grp_counts['test']} total={sum(grp_counts.values())}")
    for split in ("train", "val", "test"):
        d = cls_counts[split]
        lines.append(
            f"class {split} H={d[0]} D={d[1]} R={d[2]} S={d[3]} total={sum(d.values())}"
        )
    tot = Counter()
    for split in ("train", "val", "test"):
        tot.update(cls_counts[split])
    lines.append(f"class TOTAL H={tot[0]} D={tot[1]} R={tot[2]} S={tot[3]}")
    for split in ("train", "val", "test"):
        present = sorted(cid for cid in CLS if cls_counts[split][cid] > 0)
        lines.append(f"classes_present_{split}={[CLS[c] for c in present]}")
    old215 = {
        "onion_sample_003_v1",
        "onion_sample_016_v1",
        "onion_sample_030_v1",
        "onion_sample_r_015_v1",
    }
    overlap_excluded = [s for s in old215 if s in stems_only]
    lines.append(f"old_split_not_blindly_reused excluded_markers_in_new={overlap_excluded}")
    lines.append(f"group_leakage={'FAIL' if any('GROUP LEAK' in e for e in errors) else 'PASS_ZERO'}")
    lines.append(f"errors={errors}")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    if errors:
        raise SystemExit("VALIDATION FAILED")


if __name__ == "__main__":
    main()
