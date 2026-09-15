"""Independent verification of the Model V2 prepared dataset.

Re-derives every check from what is on disk (it does not reuse build_v2_split
logic) and additionally proves the frozen test split still matches git HEAD.

Run:  .venv\\Scripts\\python.exe data\\processed\\yolo\\verify_v2_split.py
"""
from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
YOLO = ROOT / "data" / "processed" / "yolo"
IMAGES = YOLO / "images"
LABELS = YOLO / "labels"
SPLITS = ("train", "val", "test")
CLS = {0: "HEALTHY", 1: "DAMAGED", 2: "ROTTEN", 3: "SPROUTED"}
GROUP_RE = re.compile(r"_v[0-9]+$")

failures: list[str] = []
warnings: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        failures.append(msg)


def group_key(stem: str) -> str:
    return GROUP_RE.sub("", stem).replace("onion_sample_s-", "onion_sample_s_")


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def git_blob(relpath: str) -> bytes | None:
    r = subprocess.run(
        ["git", "show", f"HEAD:{relpath}"], cwd=ROOT, capture_output=True
    )
    return r.stdout if r.returncode == 0 else None


def main() -> None:
    per_split: dict[str, dict[str, Path]] = {}
    class_dist: dict[str, Counter] = {sp: Counter() for sp in SPLITS}
    group_split: dict[str, str] = {}
    hashes: dict[str, list[tuple[str, str]]] = defaultdict(list)
    group_members: dict[str, list[str]] = defaultdict(list)
    total = 0

    for sp in SPLITS:
        imgs = {p.stem: p for p in (IMAGES / sp).iterdir() if p.is_file()}
        labs = {p.stem: p for p in (LABELS / sp).glob("*.txt")}
        per_split[sp] = imgs
        check(bool(imgs), f"{sp}: split is empty")
        # image / label pairing
        check(
            set(imgs) == set(labs),
            f"{sp}: pairing mismatch only_image={sorted(set(imgs) - set(labs))} "
            f"only_label={sorted(set(labs) - set(imgs))}",
        )
        for stem in sorted(imgs):
            total += 1
            # image integrity
            raw = imgs[stem].read_bytes()
            check(raw[:2] == b"\xff\xd8", f"{sp}/{stem}: not a JPEG")
            hashes[sha_bytes(raw)].append((sp, stem))
            # group bookkeeping
            g = group_key(stem)
            group_members[g].append(stem)
            if g in group_split and group_split[g] != sp:
                failures.append(f"GROUP LEAK: {g} in {group_split[g]} and {sp}")
            group_split[g] = sp
            # label validity
            lab = labs.get(stem)
            if lab is None:
                continue
            text = lab.read_bytes().decode("utf-8", errors="replace")
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            check(bool(lines), f"{sp}/{stem}: EMPTY label")
            for ln in lines:
                parts = ln.split()
                check(len(parts) == 5, f"{sp}/{stem}: field count {len(parts)} in {ln!r}")
                if len(parts) != 5:
                    continue
                try:
                    cid = int(float(parts[0]))
                    nums = [float(x) for x in parts[1:]]
                except ValueError:
                    failures.append(f"{sp}/{stem}: unparsable line {ln!r}")
                    continue
                check(cid in CLS, f"{sp}/{stem}: class id {cid} outside 0-3")
                check(
                    all(0.0 <= n <= 1.0 for n in nums),
                    f"{sp}/{stem}: coord outside 0-1 {nums}",
                )
                check(nums[2] > 0 and nums[3] > 0, f"{sp}/{stem}: non-positive w/h {nums}")
                x, y, w, h = nums
                check(
                    x - w / 2 >= -1e-6 and x + w / 2 <= 1 + 1e-6 and
                    y - h / 2 >= -1e-6 and y + h / 2 <= 1 + 1e-6,
                    f"{sp}/{stem}: box extends outside image {nums}",
                )
                class_dist[sp][cid] += 1
            check(len(lines) == 1, f"{sp}/{stem}: {len(lines)} boxes (expected 1)")

    # one physical onion lives in exactly one split
    for g, members in sorted(group_members.items()):
        splits = {group_split[m] for m in members if m in group_split}
        splits.add(group_split[g])
        check(len(splits) == 1, f"group {g} spans splits {sorted(splits)}")

    # duplicate / conflicting images
    conflicts = 0
    dupes = 0
    for h, entries in hashes.items():
        if len(entries) < 2:
            continue
        classes = set()
        for sp, stem in entries:
            lab = LABELS / sp / (stem + ".txt")
            if lab.is_file():
                classes.add(int(lab.read_text(encoding="utf-8").split()[0]))
        if len({sp for sp, _ in entries}) > 1:
            # the same pixels must never sit in two splits
            failures.append(f"identical image bytes in multiple splits: {entries}")
        if len(classes) > 1:
            conflicts += 1
            failures.append(f"byte-identical images, conflicting classes: {entries} -> {classes}")
        else:
            dupes += 1
            warnings.append(f"byte-identical duplicate images (same class): {entries}")

    # frozen test split vs git HEAD
    test_changed: list[str] = []
    for kind, base in (("images", IMAGES / "test"), ("labels", LABELS / "test")):
        for p in sorted(base.iterdir()):
            if not p.is_file():
                continue
            rel = str(p.relative_to(ROOT)).replace("\\", "/")
            blob = git_blob(rel)
            if blob is None:
                test_changed.append(f"NEW in working tree: {rel}")
                continue
            if sha_bytes(blob) != sha_bytes(p.read_bytes()):
                test_changed.append(f"CONTENT CHANGED: {rel}")
    # nothing may be missing from the committed test set either
    tracked_test = subprocess.run(
        ["git", "ls-files", "data/processed/yolo/images/test", "data/processed/yolo/labels/test"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    ).stdout.split()
    for t in tracked_test:
        if not (ROOT / t).is_file():
            test_changed.append(f"DELETED: {t}")
    check(not test_changed, "frozen test split differs from git HEAD: " + str(test_changed))

    # dataset.yaml sanity
    yaml_text = (YOLO / "dataset.yaml").read_text(encoding="utf-8")
    for sp in SPLITS:
        check(f"images/{sp}" in yaml_text, f"dataset.yaml missing images/{sp}")
    for cid, name in CLS.items():
        check(f"{cid}: {name}" in yaml_text, f"dataset.yaml missing class {cid} {name}")
    classes_txt = [
        ln.strip() for ln in (YOLO / "classes.txt").read_text(encoding="utf-8").splitlines() if ln.strip()
    ]
    check(
        classes_txt == [CLS[i] for i in sorted(CLS)],
        f"classes.txt mismatch: {classes_txt}",
    )

    # ---- report ----------------------------------------------------------
    print("INDEPENDENT VERIFICATION OF MODEL V2 PREPARED DATASET")
    print(f"splits: " + " ".join(f"{sp}={len(per_split[sp])}" for sp in SPLITS) + f" total={total}")
    print(f"groups: {len(group_members)}  (train={sum(1 for g in group_members if group_split[g]=='train')}"
          f" val={sum(1 for g in group_members if group_split[g]=='val')}"
          f" test={sum(1 for g in group_members if group_split[g]=='test')})")
    for sp in SPLITS:
        d = class_dist[sp]
        print(f"class {sp}: H={d[0]} D={d[1]} R={d[2]} S={d[3]} total={sum(d.values())}")
    tot = Counter()
    for sp in SPLITS:
        tot.update(class_dist[sp])
    print(f"class TOTAL: H={tot[0]} D={tot[1]} R={tot[2]} S={tot[3]} total={sum(tot.values())}")
    print(f"byte_identical_conflicts={conflicts} same_class_duplicates={dupes}")
    print(f"frozen_test_vs_git_HEAD={'IDENTICAL' if not test_changed else 'DIFFERS'}")
    for w in warnings:
        print(f"WARN {w}")
    if failures:
        print(f"\nFAILURES ({len(failures)}):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("\nRESULT: PASS (0 failures)")


if __name__ == "__main__":
    main()
